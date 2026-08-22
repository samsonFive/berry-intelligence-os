"""Run enabled production pipelines that are due according to the registry."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.runtime_config import resolve_data_dir, resolve_inbox_dir
from app.services.pipeline_scheduler import run_due_pipelines


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pipeline", help="Limit execution to one registered pipeline")
    parser.add_argument("--force", action="store_true", help="Run the selected enabled/scheduled pipeline even when not due")
    parser.add_argument("--plan", action="store_true", help="Report due pipelines without executing them")
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--inbox-dir", type=Path)
    parser.add_argument("--config", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.force and not args.pipeline:
        raise SystemExit("--force requires --pipeline")
    data_dir = args.data_dir or resolve_data_dir(ROOT)
    inbox_dir = args.inbox_dir or resolve_inbox_dir(ROOT)
    config = args.config or data_dir / "configuration" / "collection_pipelines.json"
    payload = run_due_pipelines(
        data_dir=data_dir,
        inbox_dir=inbox_dir,
        config_path=config,
        pipeline_id=args.pipeline,
        force=args.force,
        plan_only=args.plan,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 1 if payload["state"] == "FAILED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
