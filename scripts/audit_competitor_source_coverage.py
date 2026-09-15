"""Read-only five-level source/coverage audit for the required competitor roster."""
from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.composition import get_repositories
from app.repositories.paths import SCHEMAS_DIR
from app.runtime_config import resolve_data_dir, resolve_inbox_dir
from app.services.article_acquisition_outcomes import source_acquisition_summary
from app.services.company_news_coverage import company_news_coverage
from app.services.media_discovery import read_source_discovery_state
from app.services.source_freshness import source_execution_status


DEFAULT_ROSTER = [
    "Advanced Berry Breeding", "AgroBerries", "Australasian Plant Genetics", "BerryWorld",
    "Black Venture Farm", "California Giant", "Costa", "Denning Blueberries", "Expoberries",
    "Fall Creek", "Fresh Forward", "Fruitist", "Gem-Pack Berries", "Hortifrut Genetica",
    "IQ Berries", "Marionnet", "Mountain Blue", "Oishii", "Ozblu", "Pairwise",
    "Perfection Fresh", "Planasa", "Plant Sciences", "Royakkers", "Smart Berries",
    "Splendor Produce", "SunBelle", "The Berry Collective", "UC Davis",
    "University of Arkansas", "University of Florida", "Well-Pict", "Wish Farms",
]


def _fold(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def _load_roster(path: Path | None) -> list[str]:
    if path is None:
        return DEFAULT_ROSTER
    payload = json.loads(path.read_text(encoding="utf-8"))
    values = payload.get("competitors", payload) if isinstance(payload, dict) else payload
    return [str(value.get("name") if isinstance(value, dict) else value) for value in values]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--inbox-dir", type=Path)
    parser.add_argument("--roster", type=Path, help="Optional JSON list or {competitors:[...]} supplied by the entity owner.")
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    data_dir = args.data_dir or resolve_data_dir(ROOT)
    inbox_dir = args.inbox_dir or resolve_inbox_dir(ROOT)
    repos = get_repositories(data_dir, SCHEMAS_DIR)
    companies = [row for row in repos.entities.list() if row.get("entity_type") == "company"]
    sources = repos.sources.list()
    evidence = [row for row in repos.evidence.list() if row.get("status") == "published"]
    identity = {}
    for company in companies:
        for value in [company.get("name"), *(company.get("aliases") or [])]:
            if isinstance(value, str) and value.strip():
                identity.setdefault(_fold(value), []).append(company)

    rows = []
    for roster_name in _load_roster(args.roster):
        matches = identity.get(_fold(roster_name), [])
        company = matches[0] if len(matches) == 1 else None
        if company is None:
            rows.append({
                "roster_name": roster_name,
                "resolved": False,
                "resolution_issue": "ambiguous" if matches else "not represented in current base",
                "maturity_level": 0,
                "coverage_gap": "Canonical roster entity is not uniquely resolvable; entity-owner update required.",
            })
            continue
        entity_id = company["id"]
        linked = [source for source in sources if entity_id in (source.get("linked_competitor_ids") or [])]
        source_rows = []
        for source in linked:
            source_id = source["id"]
            discovery_state = read_source_discovery_state(inbox_dir, source_id)
            execution = source_execution_status(source, discovery_state=discovery_state)
            acquisition = source_acquisition_summary(inbox_dir, source_id)
            source_rows.append({
                "source_id": source_id,
                "label": source.get("label") or source_id,
                "discovery": execution,
                "article_body_acquisition": acquisition,
                "most_recent_successful_discovery": (discovery_state or {}).get("last_success_at"),
            })
        configured = [row for row in source_rows if row["discovery"].get("runnable")]
        successful = [row for row in source_rows if row["discovery"].get("state") == "SUCCESSFULLY_RUN"]
        readable_acquisitions = [
            row["article_body_acquisition"].get("latest_readable_acquired_at") for row in source_rows
            if row["article_body_acquisition"].get("latest_readable_acquired_at")
        ]
        readable_publication_dates = [
            row["article_body_acquisition"].get("most_recent_readable_article") for row in source_rows
            if row["article_body_acquisition"].get("most_recent_readable_article")
        ]
        current = company_news_coverage(company, published=evidence, days=args.days, today=args.as_of)
        maturity = 1
        if configured: maturity = 2
        if successful: maturity = 3
        if readable_acquisitions: maturity = 4
        if current["usable_count"]: maturity = 5
        gaps = []
        if not linked: gaps.append("no explicitly linked Sources")
        elif not configured: gaps.append("no runnable linked Source")
        elif not successful: gaps.append("no successful linked discovery run")
        if not readable_acquisitions: gaps.append("no readable article acquired from linked Sources")
        if not current["usable_count"]: gaps.append(f"no usable published company coverage in the last {args.days} days")
        rows.append({
            "roster_name": roster_name,
            "resolved": True,
            "canonical_entity": {"id": entity_id, "name": company.get("name")},
            "aliases_search_terms": [company.get("name"), *(company.get("aliases") or [])],
            "linked_sources": source_rows,
            "runnable_sources": len(configured),
            "successful_discovery_runs": len(successful),
            "never_run_sources": sum(row["discovery"].get("state") == "NEVER_RUN" for row in source_rows),
            "blocked_sources": sum(row["discovery"].get("state") == "BLOCKED" for row in source_rows),
            "most_recent_successful_discovery": max((row["most_recent_successful_discovery"] for row in source_rows if row["most_recent_successful_discovery"]), default=None),
            "most_recent_readable_article": max(readable_publication_dates, default=None),
            "current_usable_published_articles": current["usable_count"],
            "maturity_level": maturity,
            "coverage_gap": "; ".join(gaps) if gaps else None,
        })
    payload = {
        "scope": "Read-only current-base audit. Entity representation is not called tracked coverage.",
        "maturity_levels": {
            "1": "Entity represented", "2": "Discovery configured", "3": "Discovery operational",
            "4": "Readable content acquired", "5": "Current coverage available",
        },
        "roster_count": len(rows),
        "resolved_count": sum(row["resolved"] for row in rows),
        "rows": rows,
    }
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
