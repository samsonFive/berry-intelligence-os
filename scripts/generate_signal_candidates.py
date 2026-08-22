"""Generate deterministic, untrusted Signal candidates from real Evidence.

Reads trusted (data/evidence/) and pending (inbox/evidence/) Evidence,
clusters it by shared entity + real published_date via
app/services/signal_candidates.py, and writes any new candidate to
inbox/signal_candidates/ -- never to data/signals/. Existing candidate
files (which may carry a human review decision) are never overwritten.
After a non-dry run, live files whose ids are absent from the current
generated set are moved to inbox/signal_candidate_audit/ so counts
reflect the live set and prior decisions are not reassigned.

Usage:
    python scripts/generate_signal_candidates.py
    python scripts/generate_signal_candidates.py --dry-run --json
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
from app.services.signal_candidates import generate_candidates, persist_candidates
from app.services.signal_review import archive_candidates_absent_from


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="Generate and report; do not write candidate files")
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--inbox-dir", type=Path, default=None)
    parser.add_argument("--json", action="store_true", help="Print machine-readable summary")
    return parser


def _load_evidence(data_dir: Path, inbox_dir: Path) -> list[dict]:
    records = []
    for folder in (data_dir / "evidence", inbox_dir / "evidence"):
        if not folder.is_dir():
            continue
        for path in folder.glob("*.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(payload, dict) and payload.get("record_type") == "evidence":
                records.append(payload)
    return records


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.data_dir is None:
        args.data_dir = resolve_data_dir(ROOT)
    if args.inbox_dir is None:
        args.inbox_dir = resolve_inbox_dir(ROOT)

    records = _load_evidence(args.data_dir, args.inbox_dir)
    candidates = generate_candidates(records)
    written = [] if args.dry_run else persist_candidates(candidates, inbox_dir=args.inbox_dir)
    archived = [] if args.dry_run else archive_candidates_absent_from(candidates, inbox_dir=args.inbox_dir)

    by_pattern: dict[str, int] = {}
    for candidate in candidates:
        by_pattern[candidate["pattern_type"]] = by_pattern.get(candidate["pattern_type"], 0) + 1

    summary = {
        "evidence_considered": len(records),
        "candidates_generated": len(candidates),
        "candidates_written": len(written),
        "candidates_archived": len(archived),
        "by_pattern": by_pattern,
        "dry_run": args.dry_run,
    }
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"Evidence considered: {summary['evidence_considered']}")
        print(f"Candidates generated: {summary['candidates_generated']}")
        print(f"Candidates written: {summary['candidates_written']}")
        print(f"Stale candidates archived: {summary['candidates_archived']}")
        for pattern, count in sorted(by_pattern.items()):
            print(f"  {pattern}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
