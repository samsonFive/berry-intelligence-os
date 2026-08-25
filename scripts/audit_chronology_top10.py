#!/usr/bin/env python3
"""Production top-10 chronology audit: newest meaningful dates first.

Prints id, semantic label, ISO date, and which forbidden fields were present
but ignored. Does not print article bodies.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.repositories.json.evidence import EvidenceRepository
from app.repositories.paths import DEFAULT_DATA_DIR, SCHEMAS_DIR
from app.services.chronology import FORBIDDEN_FRESHNESS, date_label, meaningful_stamp


def audit(*, data_dir: Path, limit: int) -> list[dict]:
    rows = EvidenceRepository(data_dir=data_dir, schemas_dir=SCHEMAS_DIR).list(status="published")
    scored = []
    for record in rows:
        when, origin = meaningful_stamp(record)
        if when is None:
            continue
        ignored = [key for key in FORBIDDEN_FRESHNESS if record.get(key)]
        scored.append(
            {
                "id": record.get("id"),
                "title": (record.get("title") or "")[:80],
                "when": when.isoformat(),
                "origin": origin,
                "label": date_label(origin),
                "ignored_freshness": ignored,
                "published_date": record.get("published_date") or "",
                "captured_date": record.get("captured_date") or "",
                "event_date": record.get("event_date") or "",
            }
        )
    scored.sort(key=lambda row: row["when"], reverse=True)
    return scored[:limit]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    rows = audit(data_dir=args.data_dir, limit=args.limit)
    payload = {"limit": args.limit, "rows": rows}
    text = json.dumps(payload, indent=2)
    print(text)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
    # Fail closed if any top row used a forbidden field as its stamp (should be impossible).
    for row in rows:
        if row["origin"] in FORBIDDEN_FRESHNESS:
            print("ERROR: forbidden origin leaked", row["id"], file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
