"""Build or verify the private Pending Review read model without serving traffic."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.queries.pending_review import JsonPendingDraftSnapshotProvider
from app.repositories.json.entities import EntityRepository
from app.repositories.json.sources import JsonSourceRepository
from app.repositories.paths import SCHEMAS_DIR
from app.runtime_config import resolve_data_dir, resolve_inbox_dir


def main() -> int:
    data_dir = resolve_data_dir(ROOT)
    inbox_dir = resolve_inbox_dir(ROOT)
    entities = {
        row["id"]: row
        for row in EntityRepository(data_dir=data_dir, schemas_dir=SCHEMAS_DIR).list()
        if row.get("id")
    }
    sources = {
        row["id"]: row
        for row in JsonSourceRepository(data_dir=data_dir).list()
        if row.get("id")
    }
    started = perf_counter()
    snapshot = JsonPendingDraftSnapshotProvider(inbox_dir).snapshot(entities=entities, sources=sources)
    print(
        json.dumps(
            {
                "status": "ready",
                "inventory_count": snapshot.inventory_count,
                "parsed_records": snapshot.parsed_records,
                "reused_records": snapshot.reused_records,
                "body_records_omitted": snapshot.body_records_omitted,
                "elapsed_seconds": round(perf_counter() - started, 4),
                "index": str(inbox_dir / "indexes" / "pending-review-v2.json"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
