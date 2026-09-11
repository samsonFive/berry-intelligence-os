"""Read-only company coverage audit; never acquires or publishes source items."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.services.company_news_coverage import company_news_coverage
from app.services.entity_alias_recall import linked_evidence_for_entity
from app.services.source_body import reader_content


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("company_id")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.days < 1:
        parser.error("--days must be positive")
    companies = [json.loads(p.read_text(encoding="utf-8")) for p in (args.data_dir / "entities" / "companies").glob("*.json")]
    company = next((r for r in companies if r.get("id") == args.company_id), None)
    if company is None:
        parser.error("Company ID not found in the selected data directory")
    evidence = [json.loads(p.read_text(encoding="utf-8")) for p in (args.data_dir / "evidence").glob("*.json")]
    published = [r for r in evidence if r.get("status") == "published"]
    linked = linked_evidence_for_entity(company, published)
    current = company_news_coverage(company, published=linked, days=args.days, today=args.as_of)
    result = {
        "company_id": args.company_id, "as_of": args.as_of.isoformat(),
        "scope": "Selected data directory, published records only. Inbox and production runtime were not inspected.",
        "matching_records_all_time": len(linked),
        "access_screen_records_all_time": sum(reader_content(r)["contaminated"] for r in linked),
        "current": current,
        "limitation": "Captured coverage is not web recall. Zero captured articles does not establish zero company activity.",
    }
    text = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text)


if __name__ == "__main__":
    main()
