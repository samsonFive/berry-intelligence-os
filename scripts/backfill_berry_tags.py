"""Evidence Berry Tagging Backfill V1 (2026-08-22).

Backfills `berry_ids` on already-trusted `data/evidence/*.json` records that
currently carry none, using only the existing, word-boundary-safe
`app.services.deterministic_tagging.infer_berry_ids_from_text` matcher
against each record's own `title` + `summary`. Deliberately does not fetch
or read full article bodies -- title/summary is the same deterministic
signal already used elsewhere in this codebase for auto-tagging, and this
mission's own rule is "false specificity is worse than missing
classification": a record whose title/summary names no species stays
untagged, full stop.

This is metadata repair only. It never touches `status`, `review_state`,
`title`, `summary`, `source_authority`, `information_confidence`, or any
Fact/Assessment/Signal. It only ever adds to `berry_ids` (never removes an
existing tag) and records a `berry_tagging_provenance` audit object.

Usage:
    python scripts/backfill_berry_tags.py --dry-run   (default; writes nothing)
    python scripts/backfill_berry_tags.py --apply      (writes changes)
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.deterministic_tagging import infer_berry_ids_from_text  # noqa: E402

BACKFILL_VERSION = "berry-tagging-backfill-v1"
EVIDENCE_DIR = ROOT / "data" / "evidence"


def _classify(record: dict) -> list[str] | None:
    """Returns the deterministic berry_ids to apply, or None if the record
    should stay untagged (no deterministic species signal in title/summary)."""

    text = f"{record.get('title') or ''} {record.get('summary') or ''}"
    found = infer_berry_ids_from_text(text)
    return found or None


def run(*, apply: bool) -> dict:
    scanned = 0
    already_tagged = 0
    single_berry = 0
    multi_berry = 0
    unchanged_no_match = 0
    changes: list[tuple[Path, dict, list[str]]] = []

    for path in sorted(EVIDENCE_DIR.glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        scanned += 1

        if record.get("berry_ids"):
            already_tagged += 1
            continue

        berry_ids = _classify(record)
        if not berry_ids:
            unchanged_no_match += 1
            continue

        if len(berry_ids) == 1:
            single_berry += 1
        else:
            multi_berry += 1

        changes.append((path, record, berry_ids))

    if apply:
        applied_at = date.today().isoformat()
        for path, record, berry_ids in changes:
            record["berry_ids"] = berry_ids
            record["berry_tagging_provenance"] = {
                "method": "deterministic-title-summary-match",
                "version": BACKFILL_VERSION,
                "applied_at": applied_at,
            }
            path.write_text(
                json.dumps(record, indent=2, ensure_ascii=False, sort_keys=False) + "\n",
                encoding="utf-8",
            )

    return {
        "scanned": scanned,
        "already_tagged": already_tagged,
        "backfill_single_berry": single_berry,
        "backfill_multi_berry": multi_berry,
        "left_untagged_no_deterministic_match": unchanged_no_match,
        "total_backfilled": len(changes),
        "applied": apply,
        "sample_single": [
            {"id": r.get("id"), "title": r.get("title"), "berry_ids": b}
            for _, r, b in changes if len(b) == 1
        ][:10],
        "sample_multi": [
            {"id": r.get("id"), "title": r.get("title"), "berry_ids": b}
            for _, r, b in changes if len(b) > 1
        ][:10],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Report only, write nothing (default).")
    mode.add_argument("--apply", action="store_true", help="Write backfilled berry_ids to data/evidence/*.json.")
    args = parser.parse_args()

    apply = bool(args.apply)
    report = run(apply=apply)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
