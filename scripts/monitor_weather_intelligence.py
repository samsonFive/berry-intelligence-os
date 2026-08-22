"""One bounded NASA POWER weather-context pilot run.

Real production-region/query-window lanes are defined in
data/configuration/weather_pilot_regions.json, resolved against
data/configuration/weather_production_regions.json. Writes untrusted review
drafts to inbox/evidence/ only -- never trusted data, Facts, or Relationships.

Usage:
    python scripts/monitor_weather_intelligence.py
    python scripts/monitor_weather_intelligence.py --dry-run --json
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
from app.services.weather_intelligence import WeatherRegionRequest, run_weather_intelligence_monitor
from app.services.pipeline_lock import pipeline_lock

def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="Fetch and score; do not write drafts or state")
    parser.add_argument("--inbox-dir", type=Path, default=None)
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--pilot", type=Path, default=None)
    parser.add_argument("--json", action="store_true", help="Print machine-readable summary")
    return parser


def _load_production_regions(path: Path) -> dict[str, dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {entry["id"]: entry for entry in payload["regions"]}


def _load_pilot_requests(path: Path) -> list[WeatherRegionRequest]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [
        WeatherRegionRequest(
            production_region_id=region["production_region_id"],
            baseline_range=(region["baseline_range"]["start"], region["baseline_range"]["end"]),
            comparison_range=(region["comparison_range"]["start"], region["comparison_range"]["end"]),
        )
        for region in payload["regions"]
    ]


def _human(payload: dict) -> str:
    lines = [
        "Provider: NASA POWER (public daily point API)",
        f"Regions requested: {payload['regions_requested']}",
        f"Regions with real data: {payload['regions_with_data']}",
        f"Duplicates: {payload['duplicates']}",
        f"Review ready: {payload['review_ready']}",
        f"Failed regions: {len(payload['failed'])}",
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
    pilot_path = args.pilot or data_dir / "configuration" / "weather_pilot_regions.json"
    production_regions = _load_production_regions(data_dir / "configuration" / "weather_production_regions.json")
    region_requests = _load_pilot_requests(pilot_path)
    if args.dry_run:
        payload = run_weather_intelligence_monitor(inbox_dir=inbox_dir, production_regions=production_regions, region_requests=region_requests, dry_run=True)
    else:
        with pipeline_lock(inbox_dir, "weather"):
            payload = run_weather_intelligence_monitor(inbox_dir=inbox_dir, production_regions=production_regions, region_requests=region_requests, dry_run=False)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(_human(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
