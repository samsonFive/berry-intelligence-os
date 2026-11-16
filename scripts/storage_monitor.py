"""Sample host disk/inodes and emit bounded alerts; dry-run unless --apply."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.storage_monitor import DEFAULT_RELEASE_LOCKS, StorageMonitorError, load_config, read_public_status, run_monitor


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("/etc/berry-storage-controls/policy.json"))
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--status", type=Path, help="Read only the public status, without loading delivery credentials")
    args = parser.parse_args(argv)
    try:
        if args.status is not None:
            if args.apply:
                raise StorageMonitorError("status_is_read_only")
            result = read_public_status(args.status.absolute())
        else:
            if args.apply and (not sys.platform.startswith("linux") or os.geteuid() != 0):
                raise StorageMonitorError("host_root_linux_required")
            config = load_config(args.config.absolute())
            if config.release_locks != tuple(Path(p) for p in DEFAULT_RELEASE_LOCKS):
                raise StorageMonitorError("shared_release_lock_set_changed")
            result = run_monitor(config, apply=args.apply)
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as error:
        code = str(error) if isinstance(error, StorageMonitorError) else "monitor_failed_raw_details_suppressed"
        print(json.dumps({"status": "MONITOR_FAILED", "code": code, "notification_sent": False}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
