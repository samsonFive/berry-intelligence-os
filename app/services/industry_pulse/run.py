"""Run the Industry Pulse catch-net and slice live windows.

Live-first: fetch the 7-day matrix once, then slice by published_date into
24h / 3d / 7d. Unknown dates stay unknown and are not counted as in-window.
Never writes Evidence, Sources, or page bodies.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from app.services.industry_pulse.dedup import dedupe_hits, identity_key, unique_hits
from app.services.industry_pulse.freshness import audit_freshness
from app.services.industry_pulse.matrix import (
    BERRIES,
    GEOGRAPHIES,
    WINDOW_DAYS,
    WINDOWS,
    generate_pulse_queries,
    query_count,
)
from app.services.industry_pulse.models import DiscoveryHit, WindowSlice
from app.services.industry_pulse.novelty import classify_hit, empty_miss_counts
from app.services.industry_pulse.providers import DiscoveryProvider, GoogleNewsRssProvider
from app.services.industry_pulse.qualify import (
    QualificationIndex,
    editorial_topic_counts,
    qualify_hit,
    rejection_reason_counts,
)
from app.services.recall_audit.classify import (
    SOURCE_COLLECTED_ITEM_MISSED,
    SOURCE_KNOWN_NOT_COLLECTED,
    SOURCE_UNKNOWN,
)

INBOX_SUBDIR = "industry_pulse"
SNAPSHOT_NAME = "latest.json"


def _in_window(published_date: str | None, *, today: date, days: int) -> bool:
    if not published_date:
        return False
    try:
        day = date.fromisoformat(published_date[:10])
    except ValueError:
        return False
    return (today - timedelta(days=days)) <= day <= today


def _dimension_yield(hits: list[DiscoveryHit]) -> tuple[dict[str, dict[str, int]], dict[str, dict[str, int]]]:
    """Unique URL counts per query geography/berry before cross-query collapse."""
    by_geo = {geo: {"discovered": 0, "qualifying": 0} for geo in GEOGRAPHIES}
    by_berry = {berry: {"discovered": 0, "qualifying": 0} for berry in BERRIES}
    seen_geo: dict[str, set[str]] = {geo: set() for geo in GEOGRAPHIES}
    seen_berry: dict[str, set[str]] = {berry: set() for berry in BERRIES}
    for hit in hits:
        key = identity_key(hit)
        geo = hit.geography
        if geo in seen_geo and key not in seen_geo[geo]:
            seen_geo[geo].add(key)
            by_geo[geo]["discovered"] += 1
            if hit.qualifying:
                by_geo[geo]["qualifying"] += 1
        berry = hit.berry
        if berry in seen_berry and key not in seen_berry[berry]:
            seen_berry[berry].add(key)
            by_berry[berry]["discovered"] += 1
            if hit.qualifying:
                by_berry[berry]["qualifying"] += 1
    return by_geo, by_berry


def _tally(hits: list[DiscoveryHit], *, window: str, today: date) -> WindowSlice:
    days = WINDOW_DAYS[window]
    in_window = [hit for hit in hits if _in_window(hit.published_date, today=today, days=days)]
    unique = unique_hits(in_window)
    qualifying = [hit for hit in unique if hit.qualifying]
    unknown_date = sum(1 for hit in unique_hits(hits) if not hit.published_date)
    by_geo: dict[str, dict[str, int]] = {}
    for geo in GEOGRAPHIES:
        geo_hits = [hit for hit in unique if hit.geography == geo]
        by_geo[geo] = {
            "discovered": len(geo_hits),
            "qualifying": sum(1 for hit in geo_hits if hit.qualifying),
        }
    by_berry: dict[str, dict[str, int]] = {}
    for berry in BERRIES:
        berry_hits = [hit for hit in unique if hit.berry == berry]
        by_berry[berry] = {
            "discovered": len(berry_hits),
            "qualifying": sum(1 for hit in berry_hits if hit.qualifying),
        }
    query_geo, query_berry = _dimension_yield(in_window)
    miss_counts = empty_miss_counts()
    for hit in qualifying:
        if hit.miss_classification in miss_counts:
            miss_counts[hit.miss_classification] += 1
    return WindowSlice(
        window=window,
        discovered=len(unique),
        qualifying=len(qualifying),
        novel=sum(1 for hit in qualifying if hit.novel_domain or hit.miss_classification == SOURCE_UNKNOWN),
        known=sum(1 for hit in qualifying if hit.known_source),
        duplicates=sum(1 for hit in in_window if hit.duplicate_of),
        unknown_date=unknown_date,
        by_geography=by_geo,
        by_berry=by_berry,
        query_yield_by_geography=query_geo,
        query_yield_by_berry=query_berry,
        miss_counts=miss_counts,
    )


def names_from_entities(entities: Iterable[dict[str, Any]], *, prefix: str) -> frozenset[str]:
    names: set[str] = set()
    for entity in entities:
        entity_id = str(entity.get("id") or "")
        entity_type = str(entity.get("entity_type") or entity.get("type") or "")
        if not (entity_id.startswith(prefix) or entity_type == prefix.rstrip("-")):
            continue
        if entity.get("name"):
            names.add(str(entity["name"]))
        for alias in entity.get("aliases") or []:
            if alias:
                names.add(str(alias))
    return frozenset(names)


def run_pulse(
    *,
    provider: DiscoveryProvider | None = None,
    sources: list[dict[str, Any]],
    published_evidence: list[dict[str, Any]],
    varieties: list[dict[str, Any]] | None = None,
    entities: list[dict[str, Any]] | None = None,
    publications: list[dict[str, Any]] | None = None,
    discovered_items: list[dict[str, Any]] | None = None,
    today: date | None = None,
    persist_dir: Path | None = None,
) -> dict[str, Any]:
    today = today or datetime.now(timezone.utc).date()
    provider = provider or GoogleNewsRssProvider()
    varieties = varieties or []
    queries = [row.with_window("7d") for row in generate_pulse_queries()]
    raw: list[DiscoveryHit] = []
    failures: list[dict[str, str]] = []
    for query in queries:
        try:
            raw.extend(provider.discover(query))
        except Exception as exc:  # noqa: BLE001 — one query must not abort the matrix
            failures.append({"query_id": query.id, "error": f"{type(exc).__name__}: {exc}"})
    company_names = names_from_entities(entities or [], prefix="company-")
    variety_names = {str(row.get("name") or "") for row in varieties if row.get("name")}
    for alias_row in varieties:
        for alias in alias_row.get("aliases") or []:
            if alias:
                variety_names.add(str(alias))
    index = QualificationIndex.compile(
        company_names=company_names,
        variety_names=variety_names,
        sources=sources,
    )
    qualified = [qualify_hit(hit, index=index) for hit in raw]
    deduped = dedupe_hits(qualified)
    classified = [
        classify_hit(
            hit,
            sources=sources,
            published_evidence=published_evidence,
            varieties=varieties,
        )
        for hit in deduped
    ]
    windows = {
        window: _tally(classified, window=window, today=today).as_dict()
        for window in WINDOWS
    }
    unique_7d = unique_hits(
        [hit for hit in classified if _in_window(hit.published_date, today=today, days=7)]
    )
    qualifying_7d = [hit for hit in unique_7d if hit.qualifying]
    unique_24h = unique_hits(
        [hit for hit in classified if _in_window(hit.published_date, today=today, days=1)]
    )
    rejected_7d = [hit for hit in unique_7d if not hit.qualifying]

    def _examples(rows: list[DiscoveryHit]) -> list[dict[str, Any]]:
        return [
            {
                "title": hit.title,
                "source_domain": hit.source_domain,
                "published_date": hit.published_date,
                "berry": hit.berry,
                "geography": hit.geography,
                "qualifying": hit.qualifying,
                "qualify_reason": hit.qualify_reason,
                "editorial_topic": hit.editorial_topic,
                "miss_classification": hit.miss_classification,
            }
            for hit in rows[:25]
        ]

    novel_hosts = sorted(
        {
            hit.source_domain
            for hit in qualifying_7d
            if hit.novel_domain and hit.source_domain
        }
    )
    item_missed = [
        hit.as_dict()
        for hit in qualifying_7d
        if hit.miss_classification == SOURCE_COLLECTED_ITEM_MISSED
    ]
    known_not_collected = [
        hit.as_dict()
        for hit in qualifying_7d
        if hit.miss_classification == SOURCE_KNOWN_NOT_COLLECTED
    ]
    report = {
        "as_of": today.isoformat(),
        "provider": provider.name,
        "live_query_count": query_count(),
        "queries_attempted": len(queries),
        "query_failures": failures,
        "windows": windows,
        "novel_source_count": len(novel_hosts),
        "novel_source_hosts": novel_hosts,
        "rejected_7d": len(rejected_7d),
        "rejection_reason_counts": rejection_reason_counts(unique_7d),
        "editorial_topic_counts": editorial_topic_counts(qualifying_7d),
        "known_source_item_missed_count": len(item_missed),
        "known_source_not_collected_count": len(known_not_collected),
        "auto_trust": False,
        "persisted_bodies": False,
        "freshness": audit_freshness(
            sources=sources,
            published_evidence=published_evidence,
            publications=publications,
            discovered_items=discovered_items,
            today=today,
        ),
        "hits": [hit.as_dict() for hit in qualifying_7d][:200],
        "window_examples": {
            "24h": _examples(unique_24h),
            "7d_qualifying": _examples(qualifying_7d),
        },
        "notes": [
            "Catch-net output is discovery material only and is not trusted Evidence.",
            "Unknown published_date is excluded from 24h/3d/7d window counts.",
            "GET /industry-pulse never publishes Evidence or onboards Sources.",
            "novel_source_count and stored hits are the 7d published_date window only.",
        ],
    }
    if persist_dir is not None:
        persist_snapshot(persist_dir, report)
    return report


def persist_snapshot(inbox_dir: Path, report: dict[str, Any]) -> Path:
    """Metadata only: titles, URLs, dates, provenance. No page bodies."""
    folder = inbox_dir / INBOX_SUBDIR
    folder.mkdir(parents=True, exist_ok=True)
    safe = dict(report)
    for hit in safe.get("hits") or []:
        hit.pop("body", None)
        hit.pop("html", None)
        hit.pop("article_body", None)
    path = folder / SNAPSHOT_NAME
    path.write_text(json.dumps(safe, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def load_snapshot(inbox_dir: Path) -> dict[str, Any] | None:
    path = inbox_dir / INBOX_SUBDIR / SNAPSHOT_NAME
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
