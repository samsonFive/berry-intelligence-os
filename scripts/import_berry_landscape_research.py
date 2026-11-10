"""Dry-run or stage a source-checked landscape batch for publication review."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.berry_landscape_intake import reconcile
from app.services.collection_runner import CollectionLockedError


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet", type=Path, help="Reviewed JSON packet with hash-matched raw export")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data", help="Read-only canonical reference data")
    parser.add_argument("--inbox-dir", type=Path, required=True, help="Explicit local or staging inbox")
    operation = parser.add_mutually_exclusive_group()
    operation.add_argument("--apply", dest="mode", action="store_const", const="apply")
    operation.add_argument("--rollback", dest="mode", action="store_const", const="rollback")
    parser.set_defaults(mode="dry_run")
    args = parser.parse_args(argv)
    try:
        report = reconcile(args.packet, data_dir=args.data_dir, inbox_dir=args.inbox_dir, mode=args.mode)
    except (ValueError, KeyError, OSError, CollectionLockedError) as exc:
        parser.exit(2, f"Import failed: {exc}\n")
    print(json.dumps(report, indent=2, ensure_ascii=True))
    return bool(report.get("protected_drafts") or (report.get("workspace") or {}).get("protected"))


if __name__ == "__main__":
    raise SystemExit(main())
