"""Corpus freshness baseline for Industry Pulse.

Publication date is `published_date` only. Capture time is reported
separately and is never treated as a publication date.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from app.services.source_lifecycle import is_collection_eligible

BERRY_LABELS = {
    "berry-blueberry": "blueberry",
    "berry-strawberry": "strawberry",
    "berry-raspberry": "raspberry",
    "berry-blackberry": "blackberry",
}
REGION_PREFIXES = {
    "americas": ("geography-united-states", "geography-peru", "geography-chile", "geography-mexico", "geography-canada", "geography-brazil", "geography-argentina", "geography-colombia", "geography-north-america"),
    "europe": ("geography-europe", "geography-spain", "geography-united-kingdom", "geography-netherlands", "geography-germany", "geography-portugal"),
    "africa": ("geography-south-africa", "geography-morocco", "geography-egypt", "geography-kenya", "geography-zimbabwe", "geography-zambia"),
    "apac": ("geography-australia", "geography-china", "geography-japan", "geography-new-zealand", "geography-india"),
}


def _iso_day(value: Any) -> str | None:
    text = str(value or "").strip()
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        return text[:10]
    return None


def _parse_day(value: str | None) -> date | None:
    day = _iso_day(value)
    if not day:
        return None
    try:
        return date.fromisoformat(day)
    except ValueError:
        return None


def _newest(rows: list[dict[str, Any]], field: str) -> dict[str, Any] | None:
    dated = []
    for row in rows:
        day = _parse_day(row.get(field))
        if day:
            dated.append((day, row))
    if not dated:
        return None
    dated.sort(key=lambda pair: pair[0], reverse=True)
    day, row = dated[0]
    return {
        "id": row.get("id"),
        "title": row.get("title") or row.get("name") or row.get("label"),
        "published_date": _iso_day(row.get("published_date")),
        "captured_date": _iso_day(row.get("captured_date") or row.get("discovered_at")),
        field: day.isoformat(),
    }


def _berry_key(row: dict[str, Any]) -> list[str]:
    ids = [str(item) for item in (row.get("berry_ids") or []) if item]
    return [BERRY_LABELS.get(item, item) for item in ids] or ["untagged"]


def _region_keys(row: dict[str, Any]) -> list[str]:
    geos = {str(item) for item in (row.get("geography_ids") or []) if item}
    regions: list[str] = []
    for region, prefixes in REGION_PREFIXES.items():
        if geos & set(prefixes):
            regions.append(region)
    return regions or ["unlinked"]


def audit_freshness(
    *,
    sources: list[dict[str, Any]],
    published_evidence: list[dict[str, Any]],
    publications: list[dict[str, Any]] | None = None,
    discovered_items: list[dict[str, Any]] | None = None,
    today: date | None = None,
    stale_after_days: int = 90,
) -> dict[str, Any]:
    today = today or datetime.now(timezone.utc).date()
    publications = publications or []
    discovered_items = discovered_items or []
    newest_evidence = _newest(published_evidence, "published_date")
    newest_publication = _newest(publications, "published_date")
    newest_discovered = _newest(discovered_items, "published_date")
    newest_captured = _newest(published_evidence, "captured_date")

    per_berry: dict[str, dict[str, Any] | None] = {}
    for berry in ("blueberry", "strawberry", "raspberry", "blackberry"):
        rows = [row for row in published_evidence if berry in _berry_key(row)]
        per_berry[berry] = _newest(rows, "published_date")

    per_region: dict[str, dict[str, Any] | None] = {}
    for region in ("americas", "europe", "africa", "apac"):
        rows = [row for row in published_evidence if region in _region_keys(row)]
        per_region[region] = _newest(rows, "published_date")

    news_queries = []
    for source in sources:
        discovery = source.get("discovery") or {}
        if discovery.get("adapter") != "news_search_rss":
            continue
        news_queries.append(
            {
                "id": source.get("id"),
                "label": source.get("label") or source.get("name"),
                "feed_url": discovery.get("feed_url") or source.get("url"),
                "eligible": is_collection_eligible(source),
            }
        )

    cutoff = today - timedelta(days=stale_after_days)
    evidence_by_source: dict[str, date] = {}
    for row in published_evidence:
        source_id = str(row.get("source_id") or "")
        day = _parse_day(row.get("published_date"))
        if source_id and day:
            evidence_by_source[source_id] = max(day, evidence_by_source.get(source_id, day))
    discovered_by_source: dict[str, date] = {}
    for row in discovered_items:
        source_id = str(row.get("source_id") or "")
        day = _parse_day(row.get("published_date"))
        if source_id and day:
            discovered_by_source[source_id] = max(day, discovered_by_source.get(source_id, day))

    no_recent_yield = []
    for source in sources:
        if not is_collection_eligible(source):
            continue
        source_id = str(source.get("id") or "")
        latest = evidence_by_source.get(source_id) or discovered_by_source.get(source_id)
        if latest is None or latest < cutoff:
            no_recent_yield.append(
                {
                    "id": source_id,
                    "label": source.get("label") or source.get("name"),
                    "newest_published_date": latest.isoformat() if latest else None,
                    "adapter": (source.get("discovery") or {}).get("adapter"),
                }
            )

    return {
        "as_of": today.isoformat(),
        "newest_trusted_evidence": newest_evidence,
        "newest_publication": newest_publication,
        "newest_discovered_item": newest_discovered,
        "newest_captured_date_on_evidence": newest_captured,
        "capture_is_not_publication": True,
        "newest_evidence_per_berry": per_berry,
        "newest_evidence_per_region": per_region,
        "existing_google_news_queries": len(news_queries),
        "google_news_queries": news_queries,
        "sources_with_no_recent_yield": no_recent_yield,
        "sources_with_no_recent_yield_count": len(no_recent_yield),
        "notes": [
            "Unknown published_date stays unknown; captured_date is never used as publication date.",
            "Discovered-item newest date is empty when inbox/discovered_media is absent in this runtime.",
        ],
    }
