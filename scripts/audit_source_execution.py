"""Read-only inventory of configured Source execution capability and history."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.composition import get_repositories
from app.repositories.paths import SCHEMAS_DIR
from app.runtime_config import resolve_data_dir, resolve_inbox_dir
from app.services.media_discovery import read_source_discovery_state
from app.services.article_acquisition_outcomes import source_acquisition_summary
from app.services.monitor_workspace import retry_hints_by_source
from app.services.source_freshness import aggregate_source_execution, source_execution_status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--inbox-dir", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--season-pilot", action="store_true", help="Include the blackberry comparison source coverage")
    parser.add_argument("--all-seasons", action="store_true", help="Include source coverage for all four 2027 crop comparisons")
    args = parser.parse_args(argv)
    data_dir = args.data_dir or resolve_data_dir(ROOT)
    inbox_dir = args.inbox_dir or resolve_inbox_dir(ROOT)
    repositories = get_repositories(data_dir, SCHEMAS_DIR)
    sources = repositories.sources.list()
    retries = retry_hints_by_source(inbox_dir)
    rows = []
    for source in sorted(sources, key=lambda row: str(row.get("id") or "")):
        source_id = str(source.get("id") or "")
        if not source_id:
            continue
        status = source_execution_status(
            source,
            discovery_state=read_source_discovery_state(inbox_dir, source_id),
            retry_hint=retries.get(source_id),
        )
        acquisition = source_acquisition_summary(inbox_dir, source_id)
        rows.append({
            "source_id": source_id,
            "label": source.get("label") or source_id,
            **status,
            "article_body_acquisition": acquisition,
        })
    payload = {
        "scope": "Configured Sources plus local per-source discovery state; no network calls or writes.",
        "counts": aggregate_source_execution({row["source_id"]: row for row in rows}),
        "sources": rows,
    }
    if args.season_pilot or args.all_seasons:
        from urllib.parse import urlsplit
        from app.services.article_dedup import normalize_canonical_url, research_capture_url_key
        from app.services.research_source_cache import cached_source_urls
        from app.services.variety_season import SEASON_CROPS, comparison_path
        configured_hosts = {urlsplit(source.get("url") or "").hostname for source in sources}
        published = {
            normalize_canonical_url(evidence.get("source_url") or "")
            for evidence in repositories.evidence.list(status="published")
        }
        captured, cache_status = cached_source_urls(inbox_dir)
        crops = SEASON_CROPS if args.all_seasons else ("berry-blackberry",)
        for berry in crops:
            pilot = json.loads((data_dir / comparison_path(berry)).read_text(encoding="utf-8"))
            references = [
                {
                    "source_id": key, "title": title, "url": url,
                    "configured_host": urlsplit(url).hostname in configured_hosts,
                    "captured_for_research": research_capture_url_key(url) in captured if cache_status != "unavailable" else None,
                    "published_evidence": normalize_canonical_url(url) in published,
                }
                for key, (title, url, _) in pilot["sources"].items()
            ]
            payload[f"{berry.removeprefix('berry-')}_season"] = {
                "season": pilot["season"],
                "research_cache_status": cache_status,
                "references": references,
            }
    rendered = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
