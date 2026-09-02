"""Live Global Week Intelligence acceptance snapshot.

Read-only. Never writes Evidence, Signals, or Assessments.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.main import all_entities, load_sources  # noqa: E402
from app.services.global_week import LIVE_WINDOWS, run_week_intelligence  # noqa: E402
from app.services.industry_pulse.credentials import has_perplexity  # noqa: E402
from app.services.industry_pulse.perplexity_provider import PerplexitySearchProvider  # noqa: E402
from app.services.industry_pulse.providers import GoogleNewsRssProvider  # noqa: E402
from app.main import PERPLEXITY_PULSE_ENABLED  # noqa: E402


def _stack():
    catch = PerplexitySearchProvider() if (PERPLEXITY_PULSE_ENABLED and has_perplexity()) else None
    return [GoogleNewsRssProvider()], catch


def main() -> int:
    windows = sys.argv[1:] or ["7d"]
    for window in windows:
        if window not in LIVE_WINDOWS:
            print(f"unsupported window: {window}", file=sys.stderr)
            return 2
    entities = all_entities()
    varieties = [row for row in entities if row.get("entity_type") == "variety"]
    sources = load_sources()
    providers, catch_net = _stack()
    reports = []
    for window in windows:
        edition = run_week_intelligence(
            window=window,
            providers=providers,
            catch_net_provider=catch_net,
            entities=entities,
            varieties=varieties,
            sources=sources,
            now=datetime.now(timezone.utc),
        )
        payload = {
                "window": window,
                "stats": edition.stats,
                "latency_seconds": edition.latency_seconds,
                "provider_telemetry": edition.provider_telemetry,
                "source_diversity": {
                    "publisher_count": edition.source_diversity["publisher_count"],
                    "lead_publisher": edition.source_diversity["lead_publisher"],
                    "lead_publisher_count": edition.source_diversity["lead_publisher_count"],
                    "lead_publisher_share": edition.source_diversity["lead_publisher_share"],
                    "provider_counts": edition.source_diversity["provider_counts"],
                },
                "weak_regions": list(edition.weak_regions),
                "weak_berries": list(edition.weak_berries),
                "query_failures": edition.query_failures[:12],
                "what_matters": [
                    {"title": item.title, "publisher": item.publisher, "date": item.published_date, "url": item.url}
                    for item in edition.what_matters
                ],
                "by_region_titles": {
                    geo: [item.title for item in rows[:3]] for geo, rows in edition.by_region.items()
                },
                "by_berry_titles": {
                    berry: [item.title for item in rows[:3]] for berry, rows in edition.by_berry.items()
                },
            }
        reports.append(payload)
        print(json.dumps(payload, indent=2, ensure_ascii=True))
    out = ROOT / "inbox" / "global_week_acceptance.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(reports, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
