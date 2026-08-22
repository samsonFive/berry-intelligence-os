"""Back up, verify, or restore mutable runtime data without publishing it."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.runtime_config import env_path
from app.services.pipeline_lock import pipeline_lock
from app.services.runtime_backup import create_backup, restore_backup, rotate_backups, verify_backup


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    backup = sub.add_parser("create")
    backup.add_argument("--runtime-dir", type=Path, default=env_path("BIOS_RUNTIME_DIR") or ROOT)
    backup.add_argument("--output-dir", type=Path, required=True)
    rotate = sub.add_parser("rotate")
    rotate.add_argument("--runtime-dir", type=Path, default=env_path("BIOS_RUNTIME_DIR") or ROOT)
    rotate.add_argument("--output-dir", type=Path, default=env_path("BIOS_BACKUP_DIR"))
    rotate.add_argument("--keep", type=int, default=14)
    verify = sub.add_parser("verify")
    verify.add_argument("archive", type=Path)
    restore = sub.add_parser("restore")
    restore.add_argument("archive", type=Path)
    restore.add_argument("--target-runtime-dir", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "create":
        with pipeline_lock(args.runtime_dir / "inbox", "runtime-backup"):
            archive = create_backup(args.runtime_dir, args.output_dir)
        payload = {"state": "created_and_verified", "archive": str(archive), **verify_backup(archive)}
    elif args.command == "rotate":
        if args.output_dir is None:
            raise SystemExit("rotate requires --output-dir or BIOS_BACKUP_DIR")
        with pipeline_lock(args.runtime_dir / "inbox", "runtime-backup"):
            payload = rotate_backups(args.runtime_dir, args.output_dir, keep=args.keep)
    elif args.command == "verify":
        payload = {"state": "verified", "archive": str(args.archive), **verify_backup(args.archive)}
    else:
        payload = {"state": "restored_and_verified", "target": str(args.target_runtime_dir), **restore_backup(args.archive, args.target_runtime_dir)}
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
