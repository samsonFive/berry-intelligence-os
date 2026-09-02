"""Dump the current Radar cache as an inspection worksheet.

Does not fetch providers. Run scripts/emerging_radar_refresh.py first.
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
from app.services.emerging_radar.cache import edition_from_cache


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inbox-dir", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    inbox = args.inbox_dir or resolve_inbox_dir(ROOT)
    edition = edition_from_cache(inbox_dir=inbox)
    if edition is None:
        print("No radar cache. Run scripts/emerging_radar_refresh.py first.")
        return 1
    rows = []
    for index, row in enumerate(edition.developments[:20], start=1):
        rows.append(
            {
                "rank": index,
                "id": row.id,
                "title": row.title,
                "what_happened": row.what_happened,
                "event_type": row.event_type,
                "section": row.section,
                "why": list(row.radar_reasons),
                "sources": [
                    {
                        "publisher": source.publisher,
                        "domain": source.domain,
                        "url": source.url,
                        "provider": source.provider,
                        "social": source.social,
                        "syndicated": source.syndicated,
                    }
                    for source in row.sources
                ],
                "providers": list(row.provenance),
                "companies": list(row.company_names),
                "varieties": list(row.variety_names),
                "geographies": list(row.geography_labels),
                "berries": list(row.berry_labels),
                "corroboration": row.corroboration,
                "google_stack_would_find": row.google_stack_would_find,
                "market_context": row.market_context,
                "trusted_context": row.trusted_context,
                "weak_signal": row.weak_signal_label,
                "first_seen": row.first_seen,
                "latest_update": row.latest_update,
            }
        )
    payload = {
        "generated_at": edition.generated_at,
        "freshness_label": edition.freshness_label,
        "latency_seconds": edition.latency_seconds,
        "stats": edition.stats,
        "top_20": rows,
        "section_counts": {section["key"]: len(section.get("developments") or []) for section in edition.sections},
    }
    out = args.out or (inbox / "operations" / "radar" / "inspection.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {out} ({len(rows)} developments)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
