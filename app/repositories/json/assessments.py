"""Assessment repository (V2 Phase 2B.1).

Exercised by the live application today: get, list (`all_assessments()`),
create (`POST /assessments` -- not migrated by this task). No route edits
or removes an Assessment -- update/delete are not exercised by any
current application behavior.

`list()` returns records ordered by `created_at` descending, the exact
sort `all_assessments()` uses today."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.repositories.json.base import JsonRecordRepository
from app.repositories.paths import DEFAULT_DATA_DIR, SCHEMAS_DIR


class AssessmentRepository(JsonRecordRepository):
    def __init__(self, data_dir: Path = DEFAULT_DATA_DIR, schemas_dir: Path = SCHEMAS_DIR) -> None:
        super().__init__(folder=data_dir / "assessments", schema_path=schemas_dir / "assessment.schema.json")

    def list(self, **filters: Any) -> list[dict[str, Any]]:
        records = super().list(**filters)
        return sorted(records, key=lambda r: r.get("created_at", ""), reverse=True)
