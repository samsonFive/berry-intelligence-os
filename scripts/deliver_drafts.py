#!/usr/bin/env python3
"""Deliver untrusted drafts from one runtime inbox to another.

Default is dry-run. Apply never overwrites an existing destination draft,
never mutates analyst review state, and never writes trusted data/.

Production destinations require matching --destination-identity /
--expected-destination-identity and BIOS_DRAFT_DELIVERY_ALLOWED_DESTINATIONS.
Logs and audit files record ids, hashes, and outcomes only.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.draft_delivery import (  # noqa: E402
    DraftDeliveryError,
    deliver_drafts,
    format_summary,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-inbox", required=True, type=Path)
    parser.add_argument("--destination-inbox", required=True, type=Path)
    parser.add_argument("--destination-data", type=Path, default=None, help="Trusted data/ for SKIP_ALREADY_TRUSTED")
    parser.add_argument("--source-identity", required=True)
    parser.add_argument("--destination-identity", required=True)
    parser.add_argument("--expected-destination-identity", required=True)
    parser.add_argument("--ids", nargs="*", default=None, help="Optional draft ids to include")
    parser.add_argument("--include-tests", action="store_true")
    parser.add_argument("--apply", action="store_true", help="Write NEW_DRAFT files. Default is dry-run.")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = deliver_drafts(
            source_inbox=args.source_inbox.resolve(),
            destination_inbox=args.destination_inbox.resolve(),
            destination_data=args.destination_data.resolve() if args.destination_data else None,
            source_identity=args.source_identity,
            destination_identity=args.destination_identity,
            expected_identity=args.expected_destination_identity,
            dry_run=not args.apply,
            apply=args.apply,
            exclude_tests=not args.include_tests,
            selected_ids=set(args.ids) if args.ids else None,
        )
    except DraftDeliveryError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2
    if args.json:
        import json

        print(json.dumps(report.public_dict(), indent=2, sort_keys=True))
    else:
        print(format_summary(report))
        conflicts = report.conflict_ids()
        if conflicts:
            print("CONFLICT IDS " + " ".join(conflicts[:50]))
            if len(conflicts) > 50:
                print(f"... {len(conflicts) - 50} more")
        added = [row.draft_id for row in report.decisions if row.outcome == "NEW_DRAFT"]
        if added and not args.apply:
            print("WOULD ADD " + " ".join(added[:50]))
            if len(added) > 50:
                print(f"... {len(added) - 50} more")
    return 1 if report.conflict_ids() and args.apply else 0


if __name__ == "__main__":
    raise SystemExit(main())
