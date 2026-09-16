"""Publication Review Command Service V1 -- durable review repository (Slice 2).

Implements `design/publication-review-contract-v1`'s `FAILURE-AND-RECOVERY.md`
authoritative-storage requirement: a shared, durable production repository
for review-draft state, versions, decisions, receipts, and recovery
metadata that survives process restart and a new checkout. A gitignored,
worktree-local `inbox/` is explicitly insufficient (see
`artifacts/publication-review-candidate-pack-v1/INVENTORY.md`'s own
"fresh isolated worktree has no backlog" finding, which this store fixes):
this module's storage root resolves the same way `app/runtime_config.py`'s
`resolve_data_dir()`/`resolve_inbox_dir()` already do -- `BIOS_RUNTIME_DIR`
(or an explicit override) points it at a persistent mount outside any one
git checkout; only the local-development default falls back to a
repo-relative, gitignored `review_state/` directory.

No external infrastructure dependency is introduced (per the contract's
own "avoid introducing an external infrastructure dependency unless the
contract explicitly requires one"): this is a plain-filesystem store using
the same one-file-per-record, atomic-rename-on-write discipline every
other repository in this codebase already uses
(`app.services.draft_delivery.atomic_write_json`, reused verbatim here
rather than reimplemented).

Storage layout under the resolved root:

    drafts/<draft_id>.json                     current DraftState snapshot
    drafts_archive/<draft_id>/<version>.json    append-only prior versions
    locks/<draft_id>.lock                       per-draft exclusive lock
    idempotency/<actor_id>/<key_hash>.json      idempotency receipts
    journal/<draft_id>/<transaction_id>/*.json  staged promotion protocol

Nothing here calls `ReviewPublishService.publish()`, writes to `data/` or
the real `inbox/`, or creates any canonical record. Locking and staging
are single-machine, multi-process safe (exclusive file creation); there is
no distributed-lock claim across separate hosts, which the contract does
not require this module to provide.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

from app.services.draft_delivery import atomic_write_json

REVIEW_STATE_DIRNAME = "review_state"
LOCK_STALE_SECONDS = 120


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds")


def resolve_review_state_dir(repo_root: Path | None = None) -> Path:
    """Mirrors `app.runtime_config.resolve_data_dir`/`resolve_inbox_dir`
    exactly: `BIOS_REVIEW_STATE_DIR` wins outright; otherwise
    `BIOS_RUNTIME_DIR/review_state` when a persistent runtime mount is
    configured; otherwise a repo-relative, gitignored `review_state/`
    directory for local development, kept distinct from `inbox/` per the
    contract's own "keep inbox/ as a local/test adapter only" instruction."""
    from app.runtime_config import REPO_ROOT, env_path

    root = repo_root or REPO_ROOT
    explicit = env_path("BIOS_REVIEW_STATE_DIR")
    if explicit is not None:
        return explicit
    runtime = env_path("BIOS_RUNTIME_DIR")
    if runtime is not None:
        return runtime / REVIEW_STATE_DIRNAME
    return root / REVIEW_STATE_DIRNAME


class ReviewRepositoryError(Exception):
    """Base class for every exception this module raises."""


class DraftNotFound(ReviewRepositoryError):
    def __init__(self, draft_id: str) -> None:
        super().__init__(f"no durable review draft with id {draft_id!r}")
        self.draft_id = draft_id


class StaleVersion(ReviewRepositoryError):
    """The caller's `expected_version` no longer matches durable state."""

    def __init__(self, draft_id: str, expected: int, current: int) -> None:
        super().__init__(f"draft {draft_id!r}: expected version {expected}, current version {current}")
        self.draft_id = draft_id
        self.expected_version = expected
        self.current_version = current


class LockUnavailable(ReviewRepositoryError):
    def __init__(self, draft_id: str) -> None:
        super().__init__(f"could not acquire lock for draft {draft_id!r}")
        self.draft_id = draft_id


class IdempotencyConflict(ReviewRepositoryError):
    def __init__(self, actor_id: str, idempotency_key: str) -> None:
        super().__init__(
            f"idempotency key {idempotency_key!r} for actor {actor_id!r} was already used with different parameters"
        )


@dataclass
class DraftState:
    """Every field `IMPLEMENTATION SCOPE` item 1 names explicitly."""

    id: str
    version: int
    state: str
    draft: dict[str, Any]
    content_digest: str
    provenance_digest: str
    content_class: str
    acquisition_classification: str
    created_at: str
    updated_at: str
    decision_history: list[dict[str, Any]] = field(default_factory=list)
    publication_binding: dict[str, Any] | None = None
    recovery_state: dict[str, Any] = field(default_factory=lambda: {"pending_transaction_id": None, "phase": None})

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "record_type": "publication_review_draft_state",
            "version": self.version,
            "state": self.state,
            "draft": self.draft,
            "content_digest": self.content_digest,
            "provenance_digest": self.provenance_digest,
            "content_class": self.content_class,
            "acquisition_classification": self.acquisition_classification,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "decision_history": self.decision_history,
            "publication_binding": self.publication_binding,
            "recovery_state": self.recovery_state,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DraftState":
        return cls(
            id=payload["id"],
            version=payload["version"],
            state=payload["state"],
            draft=payload["draft"],
            content_digest=payload["content_digest"],
            provenance_digest=payload["provenance_digest"],
            content_class=payload.get("content_class", ""),
            acquisition_classification=payload.get("acquisition_classification", ""),
            created_at=payload["created_at"],
            updated_at=payload["updated_at"],
            decision_history=list(payload.get("decision_history") or []),
            publication_binding=payload.get("publication_binding"),
            recovery_state=dict(payload.get("recovery_state") or {"pending_transaction_id": None, "phase": None}),
        )


class DurableReviewRepository:
    """The authoritative, shared, durable review-state store. One instance
    per resolved root directory; safe to construct fresh in every process
    (a new checkout/worker included) and immediately see prior work,
    proving the exact durability property the contract requires."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.drafts_dir = self.root / "drafts"
        self.archive_dir = self.root / "drafts_archive"
        self.locks_dir = self.root / "locks"
        self.idempotency_dir = self.root / "idempotency"
        self.journal_dir = self.root / "journal"
        for directory in (self.drafts_dir, self.archive_dir, self.locks_dir, self.idempotency_dir, self.journal_dir):
            directory.mkdir(parents=True, exist_ok=True)

    # -- draft identity / safe paths --------------------------------------

    @staticmethod
    def _safe_id(value: str) -> str:
        if not value or Path(value).name != value or value in {".", ".."}:
            raise ReviewRepositoryError(f"{value!r} is not a safe draft/transaction id")
        return value

    def _draft_path(self, draft_id: str) -> Path:
        return self.drafts_dir / f"{self._safe_id(draft_id)}.json"

    # -- draft CRUD ---------------------------------------------------------

    def get_draft_state(self, draft_id: str) -> DraftState | None:
        path = self._draft_path(draft_id)
        if not path.is_file():
            return None
        return DraftState.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def list_draft_states(self, *, state: str | None = None) -> list[DraftState]:
        results = []
        for path in sorted(self.drafts_dir.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            draft_state = DraftState.from_dict(payload)
            if state is not None and draft_state.state != state:
                continue
            results.append(draft_state)
        return results

    def create_draft_state(self, draft_state: DraftState) -> DraftState:
        path = self._draft_path(draft_state.id)
        if path.exists():
            raise ReviewRepositoryError(f"durable draft {draft_state.id!r} already exists")
        atomic_write_json(path, draft_state.as_dict())
        return draft_state

    def _archive_version(self, draft_state: DraftState) -> None:
        archive_path = self.archive_dir / self._safe_id(draft_state.id) / f"{draft_state.version:010d}.json"
        atomic_write_json(archive_path, draft_state.as_dict())

    def compare_and_set(
        self, draft_id: str, expected_version: int, mutate: "callable[[DraftState], DraftState]",
    ) -> DraftState:
        """Read-modify-write under the per-draft lock. `mutate` receives the
        current DraftState and returns the new one (with `version`
        incremented and `updated_at` refreshed by the caller). Raises
        `StaleVersion` without writing anything if `expected_version`
        doesn't match -- the compare-and-set the contract requires for
        every mutation."""
        current = self.get_draft_state(draft_id)
        if current is None:
            raise DraftNotFound(draft_id)
        if current.version != expected_version:
            raise StaleVersion(draft_id, expected_version, current.version)
        self._archive_version(current)
        updated = mutate(current)
        atomic_write_json(self._draft_path(draft_id), updated.as_dict())
        return updated

    # -- per-draft locking (single-machine, multi-process safe) ------------

    def _lock_path(self, draft_id: str) -> Path:
        return self.locks_dir / f"{self._safe_id(draft_id)}.lock"

    @contextlib.contextmanager
    def lock_draft(self, draft_id: str, *, timeout_seconds: float = 5.0) -> Iterator[None]:
        """Exclusive per-draft lock via `O_CREAT|O_EXCL` -- the same
        primitive `review_events.append_review_event`'s exclusive-create
        already relies on for collision-safety. A lock older than
        `LOCK_STALE_SECONDS` is presumed abandoned by a crashed process and
        may be reclaimed; recovery/reconciliation is expected to have
        already resolved that process's transaction before a new one
        starts (see `reconcile_transaction`)."""
        path = self._lock_path(draft_id)
        deadline = time.monotonic() + timeout_seconds
        acquired = False
        while True:
            try:
                fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, json.dumps({"pid": os.getpid(), "acquired_at": _now_iso()}).encode("utf-8"))
                os.close(fd)
                acquired = True
                break
            except FileExistsError:
                try:
                    age = time.time() - path.stat().st_mtime
                except OSError:
                    age = 0.0
                if age > LOCK_STALE_SECONDS:
                    with contextlib.suppress(OSError):
                        path.unlink()
                    continue
                if time.monotonic() >= deadline:
                    raise LockUnavailable(draft_id)
                time.sleep(0.01)
        try:
            yield
        finally:
            if acquired:
                with contextlib.suppress(OSError):
                    path.unlink()

    # -- idempotency receipts -------------------------------------------------

    def _idempotency_path(self, actor_id: str, idempotency_key: str) -> Path:
        digest = hashlib.sha256(f"{actor_id}\x00{idempotency_key}".encode("utf-8")).hexdigest()
        return self.idempotency_dir / self._safe_id(actor_id.replace("/", "_")) / f"{digest}.json"

    def get_idempotency_receipt(self, actor_id: str, idempotency_key: str) -> dict[str, Any] | None:
        path = self._idempotency_path(actor_id, idempotency_key)
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def put_idempotency_receipt(
        self, actor_id: str, idempotency_key: str, *, payload_hash: str, result: dict[str, Any],
    ) -> None:
        path = self._idempotency_path(actor_id, idempotency_key)
        atomic_write_json(path, {
            "actor_id": actor_id, "idempotency_key": idempotency_key,
            "payload_hash": payload_hash, "result": result, "recorded_at": _now_iso(),
        })

    # -- staged promotion journal --------------------------------------------

    def _transaction_dir(self, draft_id: str, transaction_id: str) -> Path:
        return self.journal_dir / self._safe_id(draft_id) / self._safe_id(transaction_id)

    def write_journal_phase(self, draft_id: str, transaction_id: str, phase: str, payload: dict[str, Any]) -> Path:
        path = self._transaction_dir(draft_id, transaction_id) / f"{phase}.json"
        atomic_write_json(path, payload)
        return path

    def read_journal_phase(self, draft_id: str, transaction_id: str, phase: str) -> dict[str, Any] | None:
        path = self._transaction_dir(draft_id, transaction_id) / f"{phase}.json"
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def journal_phases_present(self, draft_id: str, transaction_id: str) -> set[str]:
        directory = self._transaction_dir(draft_id, transaction_id)
        if not directory.is_dir():
            return set()
        return {path.stem for path in directory.glob("*.json")}

    def pending_transactions(self) -> list[tuple[str, str]]:
        """Every (draft_id, transaction_id) with a journal directory but no
        `commit_marker` phase yet -- what a reconciler must inspect."""
        pending: list[tuple[str, str]] = []
        if not self.journal_dir.is_dir():
            return pending
        for draft_dir in sorted(self.journal_dir.iterdir()):
            if not draft_dir.is_dir():
                continue
            for txn_dir in sorted(draft_dir.iterdir()):
                if not txn_dir.is_dir():
                    continue
                if not (txn_dir / "commit_marker.json").is_file():
                    pending.append((draft_dir.name, txn_dir.name))
        return pending
