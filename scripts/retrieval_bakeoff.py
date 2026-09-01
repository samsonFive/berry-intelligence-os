"""Run the retrieval-provider bake-off. Does not switch production pulse."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.composition import get_repositories
from app.repositories.paths import SCHEMAS_DIR
from app.runtime_config import resolve_data_dir, resolve_inbox_dir
from app.services.industry_pulse.bakeoff import run_bakeoff


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print the report as JSON")
    parser.add_argument("--offline", action="store_true", help="Credential status only; no network")
    parser.add_argument("--no-persist", action="store_true", help="Do not write inbox/retrieval_bakeoff/latest.json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    data_dir = resolve_data_dir(ROOT)
    inbox_dir = resolve_inbox_dir(ROOT)
    repos = get_repositories(data_dir, SCHEMAS_DIR)
    sources = repos.sources.list()
    evidence = [row for row in repos.evidence.list() if row.get("status") == "published"]
    entities = repos.entities.list()
    varieties = [row for row in entities if str(row.get("id") or "").startswith("variety-")]
    report = run_bakeoff(
        sources=sources,
        published_evidence=evidence,
        data_dir=data_dir,
        varieties=varieties,
        today=datetime.now(timezone.utc).date(),
        include_live=not args.offline,
    )
    if not args.no_persist:
        folder = inbox_dir / "retrieval_bakeoff"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "latest.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0
    print(f"as_of={report['as_of']} production_provider={report['production_provider']}")
    for row in report["providers"]:
        live = "live" if row["live"] else "unavailable"
        print(
            f"{row['provider']}: {live} unique={row['unique_urls']} qualifying={row['qualifying']} "
            f"tier1={row['tier1']} unknown_unknown={row['unknown_unknown']} "
            f"calls={row['api_calls']} cost={row['estimated_cost_usd']}"
        )
        if row.get("unavailable_reason"):
            print(f"  reason={row['unavailable_reason']}")
    for union in report.get("unions") or []:
        print(
            f"union {union['left_provider']}/{union['right_provider']}: "
            f"both={union['both']} only_left={union['only_left']} only_right={union['only_right']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
