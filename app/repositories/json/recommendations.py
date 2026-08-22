"""Recommendation repository (V2 Phase 2B.1).

Exercised by the live application today: get, list
(`all_recommendations()`), create (`POST /recommendations` -- not migrated
by this task). No route edits or removes a Recommendation -- update/delete
are not exercised by any current application behavior.

`list()` returns records ordered by `created_at` descending, the exact
sort `all_recommendations()` uses today."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.repositories.json.base import JsonRecordRepository
from app.repositories.paths import DEFAULT_DATA_DIR, SCHEMAS_DIR


class RecommendationRepository(JsonRecordRepository):
    def __init__(self, data_dir: Path = DEFAULT_DATA_DIR, schemas_dir: Path = SCHEMAS_DIR) -> None:
        super().__init__(folder=data_dir / "recommendations", schema_path=schemas_dir / "recommendation.schema.json")

    def list(self, **filters: Any) -> list[dict[str, Any]]:
        records = super().list(**filters)
        return sorted(records, key=lambda r: r.get("created_at", ""), reverse=True)
