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
        super().__init__(folder=data_dir / "evidence", schema_path=schemas_dir / "evidence.schema.json")

    def list(self, **filters: Any) -> list[dict[str, Any]]:
        records = super().list(**filters)
        return sorted(records, key=lambda r: r.get("published_date") or r.get("captured_date") or "", reverse=True)
