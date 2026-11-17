"""Evidence repository (V2 Phase 2B.1).

Exercised by the live application today: get (evidence detail), list
(status="published" backs `published_evidence()`; unfiltered backs
`all_evidence()`), create (review/publish -- not migrated by this task),
update (the validate route reads, flips one field, writes back), delete
(the purge route -- one of only two real deletes in the whole application,
the other being Sources). Evidence is the most fully-exercised repository
in this set.

`list()` returns records ordered by `published_date` falling back to
`captured_date`, descending -- the exact sort `published_evidence()` uses
today, preserved here as the repository's own default ordering rather than
left for every caller to re-implement."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.repositories.json.base import JsonRecordRepository
from app.repositories.paths import DEFAULT_DATA_DIR, SCHEMAS_DIR


class EvidenceRepository(JsonRecordRepository):
    def __init__(self, data_dir: Path = DEFAULT_DATA_DIR, schemas_dir: Path = SCHEMAS_DIR) -> None:
        self.data_dir = Path(data_dir)
        super().__init__(folder=data_dir / "evidence", schema_path=schemas_dir / "evidence.schema.json")

    @property
    def information_store_enabled(self) -> bool:
        from app.services.information_storage import enabled
        return enabled(data_dir=self.data_dir)

    def _sync_folder(self) -> None:
        from app.services.information_storage import information_directory
        folder = information_directory(data_dir=self.data_dir)
        if folder != self._folder:
            self._folder = folder
            self._invalidate_cache()

    def _load_all_with_paths(self):
        self._sync_folder()
        return super()._load_all_with_paths()

    def get(self, record_id: str) -> dict[str, Any] | None:
        if self.information_store_enabled:
            from app.services.information_storage import get_record
            return get_record(record_id, data_dir=self.data_dir)
        return super().get(record_id)

    def _write(self, path: Path, record: dict[str, Any]) -> None:
        if self.information_store_enabled:
            from app.services.information_storage import write_record
            write_record(record, data_dir=self.data_dir, origin="canonical")
            self._invalidate_cache()
        else:
            super()._write(path, record)

    def list(self, **filters: Any) -> list[dict[str, Any]]:
        records = super().list(**filters)
        return sorted(records, key=lambda r: r.get("published_date") or r.get("captured_date") or "", reverse=True)
