"""One bounded UN Comtrade trade-intelligence pilot run.

Real HS-code/country-pair lanes are defined in
data/configuration/trade_pilot_lanes.json. Writes untrusted review drafts
to inbox/evidence/ only -- never trusted data, Facts, or Relationships.

Usage:
    python scripts/monitor_trade_intelligence.py
    python scripts/monitor_trade_intelligence.py --dry-run --json
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
from app.services.trade_intelligence import TradeLaneRequest, run_trade_intelligence_monitor
from app.services.pipeline_lock import pipeline_lock

def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="Fetch and score; do not write drafts or state")
    parser.add_argument("--inbox-dir", type=Path, default=None)
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--lanes", type=Path, default=None)
    parser.add_argument("--json", action="store_true", help="Print machine-readable summary")
    return parser


def _load_taxonomy(path: Path) -> dict[str, dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {entry["hs_code"]: entry for entry in payload["codes"]}


def _load_lanes(path: Path) -> list[TradeLaneRequest]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [
        TradeLaneRequest(
            reporter_geo=lane["reporter_geo"], partner_geo=lane["partner_geo"],
            flow_code=lane["flow_code"], hs_code=lane["hs_code"], periods=lane["periods"],
        )
        for lane in payload["lanes"]
    ]


def _human(payload: dict) -> str:
    lines = [
        "Provider: UN Comtrade (public preview API)",
        f"Lanes requested: {payload['lanes_requested']}",
        f"Lanes with real data: {payload['lanes_with_data']}",
        f"Duplicates: {payload['duplicates']}",
        f"Review ready: {payload['review_ready']}",
        f"Failed period-queries: {len(payload['failed'])}",
    ]
    if payload["failed"]:
        lines.append("Failures:")
        for item in payload["failed"][:10]:
            lines.append(f"  - {item}")
    if payload.get("created"):
        lines.append("Drafts:")
        for draft_id in payload["created"]:
            lines.append(f"  - /review/{draft_id}")
    lines.append("Drafts remain untrusted until human Approve at /review.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    data_dir = args.data_dir or resolve_data_dir(ROOT)
    inbox_dir = args.inbox_dir or resolve_inbox_dir(ROOT)
    lanes_path = args.lanes or data_dir / "configuration" / "trade_pilot_lanes.json"
    taxonomy = _load_taxonomy(data_dir / "configuration" / "trade_hs_taxonomy.json")
    lanes = _load_lanes(lanes_path)
    if args.dry_run:
        payload = run_trade_intelligence_monitor(inbox_dir=inbox_dir, hs_taxonomy=taxonomy, lane_requests=lanes, dry_run=True)
    else:
        with pipeline_lock(inbox_dir, "trade"):
            payload = run_trade_intelligence_monitor(inbox_dir=inbox_dir, hs_taxonomy=taxonomy, lane_requests=lanes, dry_run=False)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(_human(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
