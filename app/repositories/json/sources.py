"""Source repository (V2 Phase 2B.1) -- the deliberate test of whether the
persistence abstraction is real.

Every other object type in this package is stored one-file-per-record.
Sources are the one documented exception (`docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md`
Part 1.3, W4): all ~120 live sources live as one JSON array in a single
file, `data/configuration/sources.json`, and every existing write
(`save_sources()` in app/main.py) rewrites that entire file, every time,
regardless of how small the logical change is.

`JsonSourceRepository` presents the identical logical shape every other
repository in this package presents -- `get`/`list`/`create`/`update`/
`delete` against one record at a time, by id. The whole-collection
rewrite happens inside `_save_all()`, called by every mutating method, and
is invisible to a caller: nothing in this class's public surface reveals
that the backing store is one file, not one-file-per-record. A future
PostgreSQL `SourceRepository` implements the exact same logical contract
against a real `sources` table, with no collection rewriting at all and no
caller-visible difference -- which is the actual point of this exercise.

No JSON Schema exists for Source records (`schemas/` has no
`source.schema.json` -- Sources are Domain-Pack/collector configuration,
not a core intelligence object, per
`docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md` Part 1.1's classification of
this pattern). `create()`/`update()` therefore perform no schema
validation, unlike every other repository in this package -- a
deliberate, documented difference, not an oversight.

Exercised by the live application today: get is new in this repository
(no current route fetches a single source by id in isolation -- every
route loads the full list and searches it inline); list backs
`load_sources()`; create backs the add-source form; update backs
toggle/check-now/mark-checked (each currently implemented as its own
inline "load list, mutate one field, save list" in app/main.py -- this
repository is what lets a future caller express that as one `update()`
call instead); delete backs the source-delete route."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.repositories.base import DuplicateRecord, InvalidRecord, RecordNotFound, StorageError
from app.repositories.paths import DEFAULT_DATA_DIR


class JsonSourceRepository:
    def __init__(self, data_dir: Path = DEFAULT_DATA_DIR) -> None:
        self._path = data_dir / "configuration" / "sources.json"

    # -- collection-file mechanics, private ---------------------------------

    def _load_all(self) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise StorageError(f"could not read {self._path}: {exc}") from exc

    def _save_all(self, sources: list[dict[str, Any]]) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(sources, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        except OSError as exc:
            raise StorageError(f"could not write {self._path}: {exc}") from exc

    # -- public, logical-record operations -----------------------------------

    def get(self, record_id: str) -> dict[str, Any] | None:
        for source in self._load_all():
            if source.get("id") == record_id:
                return source
        return None

    def list(self, **filters: Any) -> list[dict[str, Any]]:
        records = self._load_all()
        for field, value in filters.items():
            records = [r for r in records if r.get(field) == value]
        return records

    def create(self, record: dict[str, Any]) -> dict[str, Any]:
        record_id = record.get("id")
        if not record_id:
            raise InvalidRecord(None, ["record has no 'id' field"])
        sources = self._load_all()
        if any(s.get("id") == record_id for s in sources):
            raise DuplicateRecord(record_id)
        sources.append(record)
        self._save_all(sources)
        return record

    def create_many(self, records: list[dict[str, Any]]) -> None:
        existing = {source.get("id") for source in self._load_all()}
        incoming = [record.get("id") for record in records]
        if any(record_id is None for record_id in incoming):
            raise InvalidRecord(None, ["record has no 'id' field"])
        if existing.intersection(incoming) or len(incoming) != len(set(incoming)):
            duplicate = next(record_id for record_id in incoming if record_id in existing or incoming.count(record_id) > 1)
            raise DuplicateRecord(duplicate)
        self._save_all([*self._load_all(), *records])

    def update(self, record_id: str, record: dict[str, Any]) -> dict[str, Any]:
        if record.get("id") != record_id:
            raise InvalidRecord(record_id, ["update() record's 'id' does not match record_id argument"])
        sources = self._load_all()
        for index, existing in enumerate(sources):
            if existing.get("id") == record_id:
                sources[index] = record
                self._save_all(sources)
                return record
        raise RecordNotFound(record_id)

    def delete(self, record_id: str) -> None:
        sources = self._load_all()
        remaining = [s for s in sources if s.get("id") != record_id]
        if len(remaining) == len(sources):
            raise RecordNotFound(record_id)
        self._save_all(remaining)
