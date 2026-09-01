"""Run the Industry Pulse catch-net against live Google News RSS.

Discovery metadata only. Never publishes Evidence or onboards Sources.
"""

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
from app.services.industry_pulse import audit_freshness, query_count, run_pulse
from app.services.industry_pulse.providers import GoogleNewsRssProvider


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freshness-only", action="store_true", help="Corpus audit only; no network")
    parser.add_argument("--json", action="store_true", help="Print the report as JSON")
    parser.add_argument("--no-persist", action="store_true", help="Do not write inbox/industry_pulse/latest.json")
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
    today = datetime.now(timezone.utc).date()
    if args.freshness_only:
        report = audit_freshness(
            sources=sources,
            published_evidence=evidence,
            today=today,
        )
        report["live_query_count"] = query_count()
    else:
        report = run_pulse(
            provider=GoogleNewsRssProvider(),
            sources=sources,
            published_evidence=evidence,
            varieties=varieties,
            entities=entities,
            today=today,
            persist_dir=None if args.no_persist else inbox_dir,
        )
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0
    print(f"as_of={report.get('as_of') or report.get('as_of')}")
    if "windows" in report:
        for window, row in report["windows"].items():
            print(
                f"{window}: discovered={row['discovered']} qualifying={row['qualifying']} "
                f"novel={row['novel']} known={row['known']} dupes={row['duplicates']}"
            )
        print(f"live_queries={report['live_query_count']} novel_hosts={report['novel_source_count']}")
        print(
            f"item_missed={report['known_source_item_missed_count']} "
            f"known_not_collected={report.get('known_source_not_collected_count', 0)} "
            f"auto_trust={report['auto_trust']}"
        )
    else:
        newest = report.get("newest_trusted_evidence") or {}
        print(f"newest_evidence_published_date={newest.get('published_date')}")
        print(f"google_news_queries={report.get('existing_google_news_queries')}")
        print(f"no_recent_yield={report.get('sources_with_no_recent_yield_count')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
