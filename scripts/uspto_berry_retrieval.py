"""Bounded berry-genetics USPTO / Google Patents retrieval.

Uses USPTO Open Data Portal when BIOS_USPTO_ODP_API_KEY is set.
Otherwise uses the existing public Google Patents JSON path.
Never automates Patent Public Search UI. Never promotes trust.

Usage:
    python scripts/uspto_berry_retrieval.py --json
    python scripts/uspto_berry_retrieval.py --json --dry-run
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.runtime_config import resolve_data_dir
from app.services.patent_monitor.berry_retrieval import run_bounded_berry_retrieval


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    data_dir = args.data_dir or resolve_data_dir(ROOT)
    payload = run_bounded_berry_retrieval(data_dir=data_dir, limit=args.limit)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    else:
        print(
            f"provider={payload.get('provider')} "
            f"found={payload.get('applications_or_grants')} "
            f"assignees={len(payload.get('assignees') or [])} "
            f"novel={payload.get('novel_entities')}"
        )
        if payload.get("reason"):
            print(payload["reason"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
