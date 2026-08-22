"""Signal repository (V2 Phase 2B.1).

Exercised by the live application today: get, list (`all_signals()`),
create (`POST /signals` -- not migrated by this task). No route edits or
removes a Signal -- update/delete are not exercised by any current
application behavior.

`list()` returns records ordered by `last_updated` descending, the exact
sort `all_signals()` uses today. Note: the six imported blueberry Signals
(Phase 1.5A) do not populate `last_updated` (it's optional per
`signal.schema.json`, demoted from required for exactly this reason) --
records missing it sort using `""` as a fallback key, identical to
`all_signals()`'s own `r.get("last_updated", "")`, not a new behavior."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.repositories.json.base import JsonRecordRepository
from app.repositories.paths import DEFAULT_DATA_DIR, SCHEMAS_DIR


class SignalRepository(JsonRecordRepository):
    def __init__(self, data_dir: Path = DEFAULT_DATA_DIR, schemas_dir: Path = SCHEMAS_DIR) -> None:
        super().__init__(folder=data_dir / "signals", schema_path=schemas_dir / "signal.schema.json")

    def list(self, **filters: Any) -> list[dict[str, Any]]:
        records = super().list(**filters)
        return sorted(records, key=lambda r: r.get("last_updated", ""), reverse=True)
