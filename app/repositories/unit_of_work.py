"""Unit-of-Work / transaction-boundary seam (V2 Phase 2B.1).

Phase 2A (docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md Part 1.3, W6)
identified exactly one workflow in the whole application that writes
across multiple object families as one logical operation: Evidence
review/publish, which creates one Evidence record, up to `NUM_FACT_ROWS`
Facts, up to `NUM_RELATIONSHIP_ROWS` Relationships, and zero-or-more
implicitly-created Entities. **This task does not migrate that workflow.**
It defines the transaction boundary now, ahead of that migration
(Phase 2B.3), specifically so the interface doesn't have to be invented
after route code already depends on the repository interfaces frozen in
this task -- designing a Unit of Work after the fact tends to force an
awkward retrofit; this phase's whole job is to avoid exactly that.

## What this is

`UnitOfWork` is a context manager wrapping a set of record repositories.
Every repository method invoked *through* the unit of work (not directly
against the repository outside of one) is tracked, so that if the `with`
block raises, already-completed writes from *this* unit of work can be
best-effort compensated (Part 2, below) before the exception propagates.

    with JsonUnitOfWork(evidence=evidence_repo, facts=fact_repo, ...) as uow:
        evidence_record = uow.evidence.create(evidence_dict)
        for fact_dict in fact_dicts:
            uow.facts.create(fact_dict)
        # implicit commit on clean exit; implicit rollback attempt if an
        # exception is raised inside the block

This is deliberately not the exact API sketched in this task's own brief
(`with unit_of_work: ... commit()`) -- a context manager that commits
automatically on clean exit and rolls back automatically on an exception
fits Python idiom better than a manual `commit()` call every caller must
remember, and is the same pattern `contextlib`/most Python DB libraries
already use for this exact purpose.

## What the JSON implementation actually guarantees -- read this before using it

**`JsonUnitOfWork` is best-effort compensation, not a database
transaction.** It does not provide atomicity, isolation, or durability in
the sense those words have for a real transactional store. Precisely:

- Writes still happen one at a time, in the order the caller issues them,
  each one a real, immediately-visible file write -- there is no staging
  area and no atomic multi-file commit. A concurrent reader can observe a
  partially-completed unit of work (e.g. the new Evidence record visible,
  its Facts not yet written) at any point before rollback or commit
  finishes. This is not new risk introduced by this class -- it is exactly
  today's behavior for review/publish's sequential `save_evidence()`/
  `save_fact()`/... calls -- but it is *not fixed* by wrapping those calls
  in this class, and this docstring says so rather than implying otherwise.
- On failure, rollback means: for every repository `create()` call that
  already succeeded earlier in this same `with` block, best-effort call
  that repository's `delete()` for the id it created, in reverse order.
  This is genuinely better than today's behavior (which performs zero
  cleanup on a partial failure), but it is compensation, not a guarantee --
  if a delete itself fails during rollback (e.g. the file was already
  removed by something else), that failure is collected and reported
  inside the raised `TransactionError`, not silently swallowed, and not
  retried.
- A process crash between an individual file write completing and this
  class's own in-memory bookkeeping being updated is not protected against
  -- there is no write-ahead log. This is a real, accepted limitation of a
  flat-file backend without a staging/atomic-replace mechanism, which this
  task deliberately does not build (see "Alternatives considered" below).
- `update()` calls snapshot the prior record value and restore it on rollback.
  Phase 2B.2's audit found that review/publish updates linkage arrays on
  matched existing Entities, so Phase 2B.3 added this bounded compensation.
  `delete()` calls remain uncompensated; review/publish performs no repository
  deletes inside its unit of work (the inbox draft is removed only afterward).

## Alternatives considered, and why the above was chosen

- **Staged temporary writes + atomic file replacement per object type**:
  rejected for Phase 2B.1 as more complexity than the one real write
  pattern (review/publish) currently needs or than this task's own
  "choose the least complex implementation that preserves existing
  behavior and does not create false guarantees" instruction favors. It
  would also only make *individual* file writes atomic, not the
  *multi-file* operation atomic, so it would not actually close the gap
  above -- true multi-object atomicity is what PostgreSQL is for (D-001,
  `08-DECISION-LOG.md`), not something worth approximating expensively in
  JSON first.
- **Whole-file rollback backups** remain unnecessary. The narrower prior-value
  snapshot used for repository `update()` calls covers the one real mutation
  review/publish performs without adding a staging or journaling subsystem.
- **No seam at all until Phase 2B.3**: rejected per this task's own
  explicit instruction -- designing the boundary now, even in this
  minimal form, is what lets Phase 2B.3 build against a stable interface
  instead of inventing one under time pressure once route migration is
  already underway.

## What a future PostgreSQL implementation does instead

A `PostgresUnitOfWork` wraps a real `BEGIN`/`COMMIT`/`ROLLBACK` (or the
ORM/driver equivalent) around the same repository calls, achieving actual
atomicity and isolation with no compensation logic needed -- the point of
defining this seam now is that `app/main.py`'s future review/publish
implementation (Phase 2B.3) is written once, against this interface, and
gets materially stronger guarantees for free the moment the PostgreSQL
backend exists, with no caller-visible change.
"""

from __future__ import annotations

from types import TracebackType
from copy import deepcopy
from typing import Any, Protocol

from app.repositories.base import RepositoryError, TransactionError


class _TrackedRepository:
    """Track creates and prior values for updates made through a UnitOfWork.
    Other methods pass straight through; deletes are not compensated."""

    def __init__(self, repository: Any, on_create: Any, on_update: Any) -> None:
        self._repository = repository
        self._on_create = on_create
        self._on_update = on_update

    def create(self, record: dict[str, Any]) -> dict[str, Any]:
        created = self._repository.create(record)
        self._on_create(self._repository, created.get("id"))
        return created

    def update(self, record_id: str, record: dict[str, Any]) -> dict[str, Any]:
        previous = self._repository.get(record_id)
        updated = self._repository.update(record_id, record)
        if previous is not None:
            self._on_update(self._repository, record_id, deepcopy(previous))
        return updated

    def __getattr__(self, name: str) -> Any:
        return getattr(self._repository, name)


class UnitOfWork(Protocol):
    """The shared shape a Unit of Work implements, regardless of backend.
    Attribute names are assigned per use site (e.g. `.evidence`, `.facts`)
    rather than fixed here, since which repositories a given unit of work
    needs varies by caller -- review/publish needs four; a future,
    simpler multi-object write might need two."""

    def __enter__(self) -> "UnitOfWork": ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None: ...


class JsonUnitOfWork:
    """See the module docstring for exactly what this guarantees and does
    not guarantee. Construct with keyword repositories:

        JsonUnitOfWork(evidence=EvidenceRepository(), facts=FactRepository())

    Each keyword becomes a tracked attribute (`uow.evidence`, `uow.facts`)
    exposing that repository's normal interface, with `create()` calls
    recorded for best-effort rollback; `update()` calls also capture the prior
    value for restoration."""

    def __init__(self, **repositories: Any) -> None:
        self._operations: list[tuple[str, Any, str, dict[str, Any] | None]] = []
        for name, repository in repositories.items():
            setattr(self, name, _TrackedRepository(repository, self._record_created, self._record_updated))

    def _record_created(self, repository: Any, record_id: str | None) -> None:
        if record_id:
            self._operations.append(("create", repository, record_id, None))

    def _record_updated(self, repository: Any, record_id: str, previous: dict[str, Any]) -> None:
        self._operations.append(("update", repository, record_id, previous))

    def __enter__(self) -> "JsonUnitOfWork":
        self._operations = []
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        if exc_type is None:
            return False
        self._rollback(original_error=exc)
        return False  # never suppress the original exception

    def _rollback(self, original_error: BaseException) -> None:
        cleanup_failures: list[str] = []
        for operation, repository, record_id, previous in reversed(self._operations):
            try:
                if operation == "create":
                    repository.delete(record_id)
                else:
                    repository.update(record_id, previous)
            except RepositoryError as cleanup_exc:
                cleanup_failures.append(f"{record_id}: {cleanup_exc}")
        if cleanup_failures:
            raise TransactionError(
                f"rolled back after {original_error!r}, but cleanup failed for: {'; '.join(cleanup_failures)}"
            ) from original_error
