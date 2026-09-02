"""Bounded USDA PVPO Application Status import.

Fetches the official monthly XLSX, keeps berry rows, writes inbox
Variety candidates only. Never writes trusted Evidence. Never auto-merges
canonical identity.

Usage:
    python scripts/import_usda_pvpo.py --json
    python scripts/import_usda_pvpo.py --json --dry-run
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.runtime_config import resolve_data_dir, resolve_inbox_dir
from app.services.authoritative_registries.usda_pvpo import run_bounded_import
from app.services.pipeline_lock import pipeline_lock


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--inbox-dir", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    data_dir = args.data_dir or resolve_data_dir(ROOT)
    inbox = args.inbox_dir or resolve_inbox_dir(ROOT)
    with pipeline_lock(inbox, "usda_pvpo"):
        payload = run_bounded_import(
            data_dir=data_dir,
            inbox_dir=inbox,
            persist=not args.dry_run,
        )
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    else:
        print(
            f"PVPO berry rows={payload.get('raw_berry_records')} "
            f"names={payload.get('distinct_variety_names')} "
            f"matched={payload.get('matched_canonical')} "
            f"candidates={payload.get('candidates')} "
            f"ambiguous={payload.get('ambiguous_identity')}"
        )
    return 0 if payload.get("state") in {"ok", "dry_run"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
