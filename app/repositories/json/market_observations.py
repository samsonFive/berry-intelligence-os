"""Market Observation repository (Market Reality Data Layer V1).

One file per observation under data/market_observations/. Immutable by
construction: `create()` (inherited from JsonRecordRepository) rejects a
duplicate id, and callers derive id from the full logical key including
captured_at, so a later re-fetch of the same series produces a new record
rather than overwriting the prior one. `list()` sorts by period ascending
so a caller building a time series does not need to re-sort."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.repositories.json.base import JsonRecordRepository
from app.repositories.paths import DEFAULT_DATA_DIR, SCHEMAS_DIR


class MarketObservationRepository(JsonRecordRepository):
    def __init__(self, data_dir: Path = DEFAULT_DATA_DIR, schemas_dir: Path = SCHEMAS_DIR) -> None:
        super().__init__(
            folder=data_dir / "market_observations",
            schema_path=schemas_dir / "market-observation.schema.json",
        )

    def list(self, **filters: Any) -> list[dict[str, Any]]:
        records = super().list(**filters)
        return sorted(records, key=lambda r: (r.get("period", ""), r.get("captured_at", "")))

    def latest_by_key(self, **filters: Any) -> list[dict[str, Any]]:
        """One record per (metric, source_commodity_code, geography, period)
        -- the most recently captured_at value for each. Use this for any
        analyst-facing read; use list() only when the capture history
        itself (revisions) is what's being examined."""
        records = self.list(**filters)
        latest: dict[tuple[Any, ...], dict[str, Any]] = {}
        for record in records:
            key = (record.get("metric"), record.get("source_commodity_code"), record.get("geography"), record.get("period"))
            current = latest.get(key)
            if current is None or record.get("captured_at", "") >= current.get("captured_at", ""):
                latest[key] = record
        return sorted(latest.values(), key=lambda r: r.get("period", ""))
