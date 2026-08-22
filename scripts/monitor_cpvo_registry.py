"""One bounded CPVO (EU plant variety rights) registry monitor cycle.

Queries CPVO's real public register API (no auth) for every tracked
Variety's canonical name and aliases, and writes untrusted review drafts
for berry-relevant hits. Stops at the existing human publication-review
gate -- never writes trusted data, Facts, or Relationships.

Usage:
    python scripts/monitor_cpvo_registry.py
    python scripts/monitor_cpvo_registry.py --dry-run --max-queries 20 --json
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
from app.services.cpvo_registry import run_cpvo_registry_monitor
from app.services.pipeline_lock import pipeline_lock


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="Discover and score; do not write drafts or state")
    parser.add_argument("--max-queries", type=int, default=None, help="Cap the number of variety name/alias queries this run")
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--inbox-dir", type=Path, default=None)
    parser.add_argument("--json", action="store_true", help="Print machine-readable summary")
    return parser


def _human(payload: dict) -> str:
    lines = [
        "Provider: CPVO public register (online.plantvarieties.eu)",
        f"Variety name/alias queries run: {payload['queried']}",
        f"Berry-relevant filings found: {payload['berry_relevant_filings']}",
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
        for draft_id in payload["created"][:20]:
            lines.append(f"  - /review/{draft_id}")
    lines.append("Drafts remain untrusted until human Approve at /review.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.max_queries is not None and args.max_queries < 1:
        parser.error("--max-queries must be >= 1")
    if args.data_dir is None:
        args.data_dir = resolve_data_dir(ROOT)
    if args.inbox_dir is None:
        args.inbox_dir = resolve_inbox_dir(ROOT)
    if args.dry_run:
        payload = run_cpvo_registry_monitor(data_dir=args.data_dir, inbox_dir=args.inbox_dir, max_queries=args.max_queries, dry_run=True)
    else:
        with pipeline_lock(args.inbox_dir, "cpvo"):
            payload = run_cpvo_registry_monitor(data_dir=args.data_dir, inbox_dir=args.inbox_dir, max_queries=args.max_queries, dry_run=False)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(_human(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
