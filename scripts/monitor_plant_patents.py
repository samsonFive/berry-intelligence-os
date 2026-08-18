"""One bounded plant-patent monitor cycle.

Discovers public berry plant patents, writes untrusted review drafts, and
stops at the existing human publication-review gate.

Usage:
    python scripts/monitor_plant_patents.py
    python scripts/monitor_plant_patents.py --dry-run --max-candidates 40 --json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.repositories.paths import DEFAULT_DATA_DIR
from app.services.patent_monitor.service import run_patent_monitor


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="Discover and score; do not write drafts or state")
    parser.add_argument("--max-candidates", type=int, default=40, help="Cap berry-relevant unique filings this run")
    parser.add_argument("--watchlist", type=Path, default=ROOT / "data" / "configuration" / "patent_watchlist.json")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--inbox-dir", type=Path, default=ROOT / "inbox")
    parser.add_argument("--json", action="store_true", help="Print machine-readable summary")
    return parser


def _human(payload: dict) -> str:
    lines = [
        f"Provider: {payload['provider']}",
        f"Discovered (provider totals): {payload['discovered']}",
        f"Berry relevant: {payload['berry_relevant']}",
        f"Skipped: {payload['skipped']}",
        f"Duplicates: {payload['duplicates']}",
        f"Review ready: {payload['review_ready']}",
        f"Failed queries: {len(payload['failed'])}",
    ]
    if payload["failed"]:
        lines.append("Failures:")
        for item in payload["failed"]:
            lines.append(f"  - {item}")
    if payload.get("created"):
        lines.append("Drafts:")
        for draft_id in payload["created"][:12]:
            lines.append(f"  - /review/{draft_id}")
    lines.append("Drafts remain untrusted until human Approve at /review.")
    return "\n".join(lines)


def main() -> int:
    parser = _parser()
    args = parser.parse_args()
    if args.max_candidates < 1:
        parser.error("--max-candidates must be >= 1")
    payload = run_patent_monitor(
        data_dir=args.data_dir,
        inbox_dir=args.inbox_dir,
        watchlist_path=args.watchlist,
        max_candidates=args.max_candidates,
        dry_run=args.dry_run,
    )
    public = {key: value for key, value in payload.items() if key != "filings"}
    if args.json:
        print(json.dumps(public, indent=2))
    else:
        print(_human(public))
    return 1 if payload["failed"] and not payload["berry_relevant"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
