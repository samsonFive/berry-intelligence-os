"""Live specialist-feed and HortiDaily path audit. Read-only. No Evidence writes."""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.industry_pulse.specialist_feeds import WEEK_SPECIALIST_FEEDS  # noqa: E402
from app.services.media_discovery import (  # noqa: E402
    MEDIA_DISCOVERY_FETCH_TIMEOUT_SECONDS,
    MEDIA_DISCOVERY_USER_AGENT,
    _fetch_paginated_rss,
    _normalize_article_rss_entry,
    _normalize_news_search_entry,
    _podcast_rss_entries,
)

EXTRA_PATHS = {
    "hortidaily.com": [
        "https://www.hortidaily.com/robots.txt",
        "https://www.hortidaily.com/sitemap.xml",
        "https://www.hortidaily.com/rss.xml",
        "https://www.hortidaily.com/rss.xml?section=berries",
    ],
    "fruitnet.com": [
        "https://www.fruitnet.com/robots.txt",
        "https://www.fruitnet.com/45.rss",
        "https://www.fruitnet.com/fresh-produce-journal.rss",
    ],
    "east-fruit.com": [
        "https://east-fruit.com/en/feed/",
        "https://east-fruit.com/feed/",
    ],
    "thepacker.com": [
        "https://www.thepacker.com/rss.xml",
        "https://www.thepacker.com/feed",
    ],
}


def _get(url: str) -> httpx.Response:
    return httpx.get(
        url,
        timeout=MEDIA_DISCOVERY_FETCH_TIMEOUT_SECONDS,
        headers={"User-Agent": MEDIA_DISCOVERY_USER_AGENT},
        follow_redirects=True,
    )


def audit_feed(row: dict[str, str]) -> dict[str, object]:
    report: dict[str, object] = {
        "id": row["id"],
        "label": row["label"],
        "source_id": row["source_id"],
        "host": row["host"],
        "feed_url": row["feed_url"],
        "adapter": row["adapter"],
        "source_exists": True,
        "collector_type": row["adapter"],
        "active_for_live_week": True,
        "http_status": None,
        "item_count": 0,
        "newest_published_date": None,
        "sample_titles": [],
        "error": None,
        "can_feed_live_research": True,
        "can_feed_publication_review": True,
    }
    try:
        response = _get(row["feed_url"])
        report["http_status"] = response.status_code
        if response.status_code >= 400:
            report["error"] = f"HTTP {response.status_code}"
            return report
        parsed, _raw = _fetch_paginated_rss(row["feed_url"], max_pages=1)
        entries = _podcast_rss_entries(parsed)
        normalize = (
            _normalize_news_search_entry if row["adapter"] == "news_search_rss" else _normalize_article_rss_entry
        )
        dates: list[str] = []
        titles: list[str] = []
        for entry in entries[:25]:
            item = normalize(entry)
            if item.published_date:
                dates.append(str(item.published_date)[:10])
            if item.title:
                titles.append(item.title[:120])
        report["item_count"] = len(entries)
        report["newest_published_date"] = max(dates) if dates else None
        report["sample_titles"] = titles[:5]
    except Exception as exc:  # noqa: BLE001 -- audit must continue
        report["error"] = f"{type(exc).__name__}: {exc}"
    return report


def main() -> int:
    today = date.today().isoformat()
    feeds = [audit_feed(row) for row in WEEK_SPECIALIST_FEEDS]
    extras: dict[str, list[dict[str, object]]] = {}
    for host, urls in EXTRA_PATHS.items():
        extras[host] = []
        for url in urls:
            row: dict[str, object] = {"url": url, "status": None, "content_type": None, "error": None}
            try:
                response = _get(url)
                row["status"] = response.status_code
                row["content_type"] = response.headers.get("content-type")
                if "robots" in url:
                    row["body_head"] = response.text[:800]
            except Exception as exc:  # noqa: BLE001
                row["error"] = f"{type(exc).__name__}: {exc}"
            extras[host].append(row)
    payload = {
        "audited_at": datetime.now(timezone.utc).isoformat(),
        "today": today,
        "feeds": feeds,
        "extra_paths": extras,
    }
    out = ROOT / "inbox" / "week_source_audit.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=True))
    print(f"wrote {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
