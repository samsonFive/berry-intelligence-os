"""Shared JSON-file persistence mechanics for one-file-per-record object
types (V2 Phase 2B.1).

Understands records and files -- nothing about Berries, entities, or any
specific object type's meaning lives here
(docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md Part 2: "the common base should
understand records/files, not berries"). A concrete repository
(app/repositories/json/evidence.py etc.) supplies only a folder and an
optional schema path; every mechanic below -- deterministic mtime-signature
caching, schema validation before write, duplicate-id rejection, safe
filesystem paths, JSON serialization, error normalization -- is shared.

This is a standalone reimplementation of app/main.py's existing
load_json_files()/save_X() pattern, not a wrapper around those functions:
app/main.py is not imported by, or imported into, this module (Part 8 --
no route migration, and keeping this layer import-independent of
app/main.py is what makes it provably not yet wired into runtime
behavior). The behavior is intentionally identical: same cache-by-
(filename, mtime) strategy as load_json_files(), same
indent=2/ensure_ascii=False/trailing-newline JSON formatting as every
save_X() function.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from app.repositories.base import DuplicateRecord, InvalidRecord, RecordNotFound, StorageError

_CacheSignature = tuple[tuple[str, int], ...]


def safe_record_id(record_id: str) -> str:
    """Reject an id that isn't a single, safe path component -- a path
    separator or a '..' segment would let a record id escape its intended
    folder. Every id in live use today is a slugified string with no such
    characters (new_signal_id() and siblings in app/main.py), so this
    never rejects real data; it exists as the "safe filesystem paths"
    concern docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md Part 2 names as a
    shared responsibility the current, pre-repository code never
    centralized (every save_X() today builds a path from an id with no
    validation at all)."""
    if not record_id or Path(record_id).name != record_id or record_id in {".", ".."}:
        raise InvalidRecord(record_id, [f"{record_id!r} is not a safe record id"])
    return record_id


class JsonRecordRepository:
    """One-file-per-record JSON persistence for a single object type.

    Read operations (`get`/`list`) scan `folder` recursively
    (`Path.rglob("*.json")`, matching `load_json_files()`'s own traversal
    exactly), so a repository whose records live in per-type subfolders
    (Entities -- see `entities.py`) needs no special read-side handling:
    pointing `folder` at the parent directory is sufficient. Write
    operations (`create`/`update`/`delete`) locate a record's *existing*
    file by scanning for it, so a record is always rewritten in its
    current location, never moved -- subclasses that place new records
    into a type-specific subfolder (again, Entities) override
    `_new_record_path()` only; every other method is inherited unchanged.
    """

    def __init__(self, folder: Path, schema_path: Path | None = None) -> None:
        self._folder = folder
        self._schema_path = schema_path
        self._validator: Draft202012Validator | None = None
        self._cache: tuple[_CacheSignature, list[tuple[Path, dict[str, Any]]]] | None = None

    # -- schema validation -------------------------------------------------

    def _validator_instance(self) -> Draft202012Validator | None:
        if self._schema_path is None:
            return None
        if self._validator is None:
            schema = json.loads(self._schema_path.read_text(encoding="utf-8"))
            self._validator = Draft202012Validator(schema, format_checker=FormatChecker())
        return self._validator

    def _validate(self, record: dict[str, Any]) -> None:
        validator = self._validator_instance()
        if validator is None:
            return
        errors = [e.message for e in validator.iter_errors(record)]
        if errors:
            raise InvalidRecord(record.get("id"), errors)

    # -- deterministic, cached loading --------------------------------------

    def _load_all_with_paths(self) -> list[tuple[Path, dict[str, Any]]]:
        if not self._folder.exists():
            return []
        paths = sorted(self._folder.rglob("*.json"))
        signature: _CacheSignature = tuple((str(p), p.stat().st_mtime_ns) for p in paths)
        if self._cache is not None and self._cache[0] == signature:
            return self._cache[1]
        pairs: list[tuple[Path, dict[str, Any]]] = []
        for path in paths:
            try:
                with path.open("r", encoding="utf-8") as handle:
                    pairs.append((path, json.load(handle)))
            except (OSError, json.JSONDecodeError) as exc:
                raise StorageError(f"could not read {path}: {exc}") from exc
        self._cache = (signature, pairs)
        return pairs

    def _invalidate_cache(self) -> None:
        self._cache = None

    def _locate(self, record_id: str) -> Path | None:
        for path, record in self._load_all_with_paths():
            if record.get("id") == record_id:
                return path
        return None

    # -- path for a brand-new record; override for non-flat layouts --------

    def _new_record_path(self, record: dict[str, Any]) -> Path:
        return self._folder / f"{safe_record_id(record['id'])}.json"

    # -- public persistence operations --------------------------------------

    def get(self, record_id: str) -> dict[str, Any] | None:
        for _path, record in self._load_all_with_paths():
            if record.get("id") == record_id:
                return record
        return None

    def list(self, **filters: Any) -> list[dict[str, Any]]:
        records = [record for _path, record in self._load_all_with_paths()]
        for field, value in filters.items():
            records = [r for r in records if r.get(field) == value]
        return records

    def create(self, record: dict[str, Any]) -> dict[str, Any]:
        record_id = record.get("id")
        if not record_id:
            raise InvalidRecord(None, ["record has no 'id' field"])
        if self._locate(record_id) is not None:
            raise DuplicateRecord(record_id)
        self._validate(record)
        path = self._new_record_path(record)
        self._write(path, record)
        return record

    def create_many(self, records: list[dict[str, Any]]) -> None:
        """Validated bulk-load hook used by Intelligence Package re-import.
        It preserves create semantics while avoiding an O(n²) rescan during
        migration-sized loads; it is not part of route-facing CRUD."""
        existing = {record.get("id") for _path, record in self._load_all_with_paths()}
        incoming: set[str] = set()
        for record in records:
            record_id = record.get("id")
            if not record_id:
                raise InvalidRecord(None, ["record has no 'id' field"])
            if record_id in existing or record_id in incoming:
                raise DuplicateRecord(record_id)
            self._validate(record)
            incoming.add(record_id)
        for record in records:
            self._write(self._new_record_path(record), record)

    def update(self, record_id: str, record: dict[str, Any]) -> dict[str, Any]:
        existing_path = self._locate(record_id)
        if existing_path is None:
            raise RecordNotFound(record_id)
        if record.get("id") != record_id:
            raise InvalidRecord(record_id, ["update() record's 'id' does not match record_id argument"])
        self._validate(record)
        self._write(existing_path, record)
        return record

    def delete(self, record_id: str) -> None:
        path = self._locate(record_id)
        if path is None:
            raise RecordNotFound(record_id)
        try:
            path.unlink()
        except OSError as exc:
            raise StorageError(f"could not delete {path}: {exc}") from exc
        self._invalidate_cache()

    def _write(self, path: Path, record: dict[str, Any]) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        except OSError as exc:
            raise StorageError(f"could not write {path}: {exc}") from exc
        self._invalidate_cache()
