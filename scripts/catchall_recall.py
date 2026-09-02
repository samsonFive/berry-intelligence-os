"""Scheduled CatchAll recall → shared live discovery cache.

Usage:
    python scripts/catchall_recall.py --json
    python scripts/catchall_recall.py --json --inbox-dir PATH

Never starts a job from /week. Without a key the run succeeds as
awaiting_key so the scheduler stays green until SET NEWSCATCHER_API_KEY
or CATCHALL_API_KEY.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.runtime_config import resolve_inbox_dir
from app.services.industry_pulse.catchall_recall import run_catchall_recall
from app.services.pipeline_lock import pipeline_lock


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inbox-dir", type=Path, default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    inbox = args.inbox_dir or resolve_inbox_dir(ROOT)
    with pipeline_lock(inbox, "catchall_recall"):
        payload = run_catchall_recall(inbox_dir=inbox)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"CatchAll recall: {payload.get('state')} hits={payload.get('hit_count', 0)}")
        if payload.get("reason"):
            print(payload["reason"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
