"""Plan, apply/resume, or roll back physical source-record consolidation.

Apply/rollback run during a maintenance window, inside the same runtime/container
paths the application will use. The default plan command never writes files.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.information_migration import InformationMigrationError, apply_migration, dry_run, rollback_migration
from app.services.information_storage import InformationStorageError
from app.services.collection_runner import CollectionLockedError


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "apply", "rollback"))
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--inbox-dir", type=Path, required=True)
    parser.add_argument("--backup-dir", type=Path)
    parser.add_argument("--resume", metavar="MIGRATION_ID")
    parser.add_argument("--quiesced", action="store_true", help="The web service and acquisition jobs are stopped")
    args = parser.parse_args(argv)
    try:
        if args.command == "plan":
            result = dry_run(args.data_dir, args.inbox_dir)
        elif args.command == "apply":
            if args.backup_dir is None:
                parser.error("apply requires --backup-dir outside data/inbox")
            result = apply_migration(args.data_dir, args.inbox_dir, args.backup_dir,
                                     quiesced=args.quiesced, resume_id=args.resume)
        else:
            if args.backup_dir is None:
                parser.error("rollback requires --backup-dir naming the exact migration backup")
            result = rollback_migration(args.data_dir, args.inbox_dir, args.backup_dir, quiesced=args.quiesced)
    except (InformationStorageError, CollectionLockedError, OSError) as exc:
        print(json.dumps({"state": "blocked", "error": str(exc)}))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if result.get("conflicts") else 0


if __name__ == "__main__":
    raise SystemExit(main())
