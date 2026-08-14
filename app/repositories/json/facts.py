"""Fact repository (V2 Phase 2B.1).

Exercised by the live application today: get, list (`all_facts()`),
create (review/publish generates `fact-{evidence_id_suffix}-{n}` ids
inline -- not migrated by this task; id generation stays a route/domain
concern per app/repositories/base.py's RecordRepository.create() docstring).
No route edits or removes a Fact once published -- update/delete are not
exercised by any current application behavior."""

from __future__ import annotations

from pathlib import Path

from app.repositories.json.base import JsonRecordRepository
from app.repositories.paths import DEFAULT_DATA_DIR, SCHEMAS_DIR


class FactRepository(JsonRecordRepository):
    def __init__(self, data_dir: Path = DEFAULT_DATA_DIR, schemas_dir: Path = SCHEMAS_DIR) -> None:
        super().__init__(folder=data_dir / "facts", schema_path=schemas_dir / "fact.schema.json")
