"""Record-repository contracts (V2 Phase 2B.1).

Backend-agnostic: this module has no knowledge of JSON files, folders, or
SQL -- only of what operation a caller may perform against a persisted
record family, and what can predictably go wrong. A JSON implementation
(app/repositories/json/) and a future PostgreSQL implementation both
satisfy the shapes and exceptions defined here.

Scope discipline (docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md Part 3.1):
repositories are persistence abstractions -- get/list/create/update/delete
against one record family. They are not query services (reverse
references, timelines, lineage traversal -- Part 3.3), not domain services
(Berries-specific rollups -- Part 3.4), and not presentation/view-model
builders (Part 4). Nothing in this module or its JSON implementations
returns anything HTML- or template-shaped.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


class RepositoryError(Exception):
    """Base class for every exception a record repository may raise.
    Callers that only care whether persistence failed can catch this one
    type; callers that need to distinguish failure modes catch the
    specific subclasses below. No backend-native exception (a filesystem
    OSError, a future psycopg error) should ever reach a caller directly --
    every repository method that touches storage catches its backend's own
    exceptions and re-raises one of these (docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md
    Part 5)."""


class RecordNotFound(RepositoryError):
    """Raised by update()/delete() when the target id does not exist.
    get() does NOT raise this -- it returns None, per Part 5's explicit
    instruction that 'raising an HTTP-flavored exception is a route-layer
    decision, not a repository one': a repository must stay usable from a
    future API, CLI, or Report generator that wants different not-found
    handling than a 404 page. update()/delete() raise because, unlike a
    lookup, silently no-op-ing a write against a nonexistent id would hide
    a real caller bug."""

    def __init__(self, record_id: str) -> None:
        super().__init__(f"no record with id {record_id!r}")
        self.record_id = record_id


class DuplicateRecord(RepositoryError):
    """Raised by create() when a record with the same id already exists.
    Formalizes new behavior, not a preserved one: today's save_X()
    functions in app/main.py silently overwrite an existing file at the
    same path on a colliding id, which is a real, previously-undetected
    integrity gap (docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md Part 5) --
    generated ids already collision-avoid via timestamp+random suffix, but
    nothing structurally guaranteed it before this repository layer."""

    def __init__(self, record_id: str) -> None:
        super().__init__(f"a record with id {record_id!r} already exists")
        self.record_id = record_id


class InvalidRecord(RepositoryError):
    """The record failed its object type's JSON Schema. `errors` preserves
    the underlying jsonschema validator messages for callers that want
    detail (e.g. a create-form re-rendering with a validation banner,
    exactly as every existing create route does today) without forcing
    every caller to know jsonschema's own exception shape."""

    def __init__(self, record_id: str | None, errors: list[str]) -> None:
        joined = "; ".join(errors)
        label = f"record {record_id!r}" if record_id else "record"
        super().__init__(f"{label} failed validation: {joined}")
        self.record_id = record_id
        self.errors = errors


class StorageError(RepositoryError):
    """The underlying storage failed for a reason unrelated to the
    record's own validity (disk full, permission denied, a concurrent
    writer, a malformed file already on disk). Every backend-native
    exception a repository method doesn't already translate into a more
    specific RepositoryError subclass is caught and re-raised as this."""


class ReferentialIntegrityError(RepositoryError):
    """A write would create, or an existing record already contains, a
    reference to another record that does not resolve. Distinct from
    InvalidRecord, which is about a record's own shape, not what it points
    at. Write-time rejection of unknown referenced ids is existing,
    correct application behavior (the Signal/Assessment/Recommendation
    create routes in app/main.py already do this inline before calling
    save_X()); this exception formalizes it as a repository-level concept
    for a later phase to raise consistently. **Not yet raised by any
    repository in Phase 2B.1** -- checking whether a referenced id
    resolves requires knowing about *other* record families, which is a
    query-service concern (docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md Part
    3.3), out of scope for this task's record-repository-only slice. See
    this task's final report, Part 9, for where this lands."""


class TransactionError(RepositoryError):
    """Raised by a Unit of Work when a coordinated multi-repository write
    cannot be completed, or (for the JSON backend specifically) when a
    partial failure leaves storage in a state the caller must be told
    about explicitly rather than assume was rolled back. See
    app/repositories/unit_of_work.py for exactly what the JSON backend
    guarantees -- it is materially weaker than a database transaction, and
    this exception's docstring there says so plainly rather than implying
    a guarantee that doesn't exist."""


@runtime_checkable
class RecordRepository(Protocol):
    """The shared *shape* a record repository may implement for one
    persisted object type -- not a mandatory interface every repository
    must implement in full. Python's structural typing means a repository
    satisfies this Protocol by having the methods it has; a repository
    with no real delete behavior in the current application (Entities,
    Facts, Relationships, Signals, Assessments, Recommendations, Strategic
    Questions -- see docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md Part 1.3's
    write inventory, W1-W6) simply does not define delete(), rather than
    defining one that raises NotImplementedError -- an unused method that
    exists only to satisfy an interface is exactly the CRUD-cargo-cult
    pattern this phase's brief warns against.

    Every concrete repository's own class docstring states which of these
    operations the live application actually exercises today, and which
    (if any) are provided as uniform, harmless persistence mechanics ahead
    of a plausible future need (e.g. delete(), trivial to implement
    identically for every object type and required by a PostgreSQL
    backend's DELETE regardless) rather than a currently-used capability."""

    def get(self, record_id: str) -> dict[str, Any] | None:
        """Return the record, or None if no record with this id exists.
        Never raises for 'not found'."""
        ...

    def list(self, **filters: Any) -> list[dict[str, Any]]:
        """Return every record, optionally narrowed by simple, single-field
        exact-match filters on this object type's own top-level fields
        (e.g. status="published"). Cross-object filters (by related
        entity, by derived region, by fuzzy text) are query-service or
        domain-service concerns, not a repository's job -- see
        docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md Part 3.2's explicit
        'not proposed' note on this boundary."""
        ...

    def create(self, record: dict[str, Any]) -> dict[str, Any]:
        """Persist a brand-new record. The caller supplies a already-unique
        id (id generation is a route/domain concern -- new_signal_id() and
        siblings in app/main.py stay exactly where they are; this task does
        not move id generation into the repository layer). Validates
        against the object type's JSON Schema before writing. Raises
        DuplicateRecord if the id already exists, InvalidRecord if the
        record fails schema validation."""
        ...

    def update(self, record_id: str, record: dict[str, Any]) -> dict[str, Any]:
        """Replace an existing record in place -- read-modify-write of a
        known record, not an upsert (docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md
        Part 3.2 explicitly rejects a generic upsert: every real create
        call site generates a fresh id and never overwrites; the one real
        update call site, Evidence validate, already knows the id and is
        mutating a known record -- collapsing the two would hide that
        distinction). Raises RecordNotFound if the id does not exist."""
        ...

    def delete(self, record_id: str) -> None:
        """Remove a record. Raises RecordNotFound if the id does not exist."""
        ...
