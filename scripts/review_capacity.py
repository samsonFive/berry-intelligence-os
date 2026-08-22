"""Report production review load and simulate conservative backpressure."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.composition import get_repositories
from app.runtime_config import resolve_data_dir, resolve_inbox_dir
from app.services.review_capacity import build_review_capacity_report, load_json_objects
from app.services.analyst_queue import load_state
from app.repositories.paths import SCHEMAS_DIR


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--inbox-dir", type=Path)
    parser.add_argument("--include-items", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def _human(report: dict) -> str:
    observed = report["observed_review_events"]
    derived = report["derived_operational_metrics"]
    arrival = derived["arrival"]
    simulation = report["simulated_policy_effect"]
    lines = [
        "REVIEW CAPACITY + COLLECTION BACKPRESSURE",
        f"Backlog: {derived['backlog_total']} ({derived['backlog_level'].upper()})",
        f"Median queue age: {derived['median_queue_age_days']} days",
        f"Oldest open: {(derived['oldest_open_item'] or {}).get('queue_age_days', 'unknown')} days",
        f"Arrivals: {arrival['mean_drafts_per_run']} drafts/run; {arrival['drafts_per_day']} drafts/day",
        f"Net growth: {arrival['net_backlog_growth_from_first_snapshot']} ({arrival['net_backlog_growth_per_day']} per day)",
        "",
        "OBSERVED REVIEW EVENTS",
        f"Published={observed['published']} Rejected={observed['rejected']} Dismissed={observed['dismissed_from_triage']} Deferred={observed['deferred']}",
        f"Rates measurable: {observed['rates_measurable']} ({observed['measurement_note']})",
        "",
        "SIMULATED POLICY EFFECT (NOT ENABLED)",
        f"Would defer={simulation['would_defer']} Would surface={simulation['would_surface']} Protected surfaced={simulation['protected_items_surface']}",
        simulation["enablement_decision"],
        "",
        "TOP SOURCE LOAD",
    ]
    for row in derived["source_economics"][:15]:
        lines.append(
            f"{row['source_id']}: pending={row['pending_backlog']} direct={row['direct_pending']} "
            f"adjacent={row['adjacent_pending']} duplicate_excess={row['duplicate_reprint_excess']} "
            f"recorded_decisions={row['recorded_decisions']} yield_measurable={row['yield_measurable']}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    data_dir = args.data_dir or resolve_data_dir(ROOT)
    inbox_dir = args.inbox_dir or resolve_inbox_dir(ROOT)
    repositories = get_repositories(data_dir, SCHEMAS_DIR)
    drafts = load_json_objects(inbox_dir / "evidence")
    run_records = load_json_objects(inbox_dir / "operations" / "runs")
    run_records += load_json_objects(inbox_dir / "operations" / "pipelines", recursive=True)
    run_records.sort(key=lambda row: str(row.get("completed_at") or row.get("started_at") or ""))
    discovered = load_json_objects(inbox_dir / "discovered_media")
    report = build_review_capacity_report(
        drafts=drafts,
        sources=repositories.sources.list(),
        entities=repositories.entities.list(),
        trusted=repositories.evidence.list(),
        run_records=run_records,
        analyst_state=load_state(inbox_dir),
        discovered=discovered,
        include_items=args.include_items,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) if args.json else _human(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
