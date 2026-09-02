"""Run the bounded Emerging Developments Radar.

Request-time core: Google News RSS, specialist RSS, Exa semantic radar.
Optional: Perplexity catch-net (3 queries). Never APITube. Never a live
CatchAll submit. Does not write Evidence.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from app.services.competitor_pulse import _normalize_quotes
from app.services.emerging_radar.cache import (
    append_watch_events,
    previous_developments,
    write_cache,
)
from app.services.emerging_radar.cluster import cluster_hits
from app.services.emerging_radar.compose import (
    apply_watchlist,
    attach_market_context,
    attach_trusted_context,
    compose_edition,
    load_watchlist,
)
from app.services.emerging_radar.models import CACHE_TTL_SECONDS, RADAR_WINDOW, RadarEdition
from app.services.emerging_radar.queries import (
    radar_catchnet_queries,
    radar_google_queries,
    radar_query_budget,
    radar_semantic_queries,
)
from app.services.industry_pulse.dedup import dedupe_hits, unique_hits
from app.services.industry_pulse.matrix import PulseQuery
from app.services.industry_pulse.models import DiscoveryHit
from app.services.industry_pulse.providers import DiscoveryProvider
from app.services.industry_pulse.qualify import QualificationIndex, qualify_hit
from app.services.industry_pulse.run import names_from_entities
from app.services.industry_pulse.specialist_feeds import week_specialist_feed_queries

MAX_WORKERS = 12


def _discover_one(provider: DiscoveryProvider, query: PulseQuery) -> tuple[str, PulseQuery, list[DiscoveryHit], str | None]:
    try:
        hits = provider.discover(query)
        for hit in hits:
            hit.title = _normalize_quotes(hit.title)
            hit.snippet = _normalize_quotes(hit.snippet)
        return provider.name, query, hits, None
    except Exception as exc:  # noqa: BLE001 -- one query must not abort the radar
        return provider.name, query, [], f"{type(exc).__name__}: {exc}"


def _provider_available(provider: DiscoveryProvider) -> bool:
    available = getattr(provider, "available", None)
    if callable(available):
        try:
            return bool(available())
        except Exception:  # noqa: BLE001
            return False
    return True


def run_radar_intelligence(
    *,
    providers: Iterable[DiscoveryProvider] = (),
    catch_net_provider: DiscoveryProvider | None = None,
    specialist_provider: DiscoveryProvider | None = None,
    entities: Iterable[dict[str, Any]] = (),
    sources: Iterable[dict[str, Any]] = (),
    evidence: Iterable[dict[str, Any]] = (),
    assessments: Iterable[dict[str, Any]] = (),
    background_hits: Iterable[DiscoveryHit] = (),
    market_repo: Any | None = None,
    inbox_dir: Path | None = None,
    persist: bool = True,
    now: datetime | None = None,
    seed_hits: Iterable[DiscoveryHit] | None = None,
) -> RadarEdition:
    """Live, read-only aside from the Radar inbox cache and watchlist events."""
    now = now or datetime.now(timezone.utc)
    started = time.monotonic()
    entity_list = list(entities)
    companies = names_from_entities(entity_list, prefix="company-")
    varieties = names_from_entities(entity_list, prefix="variety-")
    index = QualificationIndex.compile(
        company_names=companies,
        variety_names=varieties,
        sources=sources,
    )

    raw: list[DiscoveryHit] = list(seed_hits or [])
    telemetry: dict[str, dict[str, int]] = {}
    failures: list[dict[str, str]] = []
    jobs: list[tuple[DiscoveryProvider, PulseQuery]] = []

    google_queries = [row.with_window(RADAR_WINDOW) for row in radar_google_queries()]
    semantic = radar_semantic_queries()
    for provider in providers:
        name = getattr(provider, "name", "")
        if name == "exa":
            jobs.extend((provider, query) for query in semantic)
        elif name == "apitube":
            continue
        else:
            jobs.extend((provider, query) for query in google_queries)

    if specialist_provider is not None:
        jobs.extend((specialist_provider, query) for query in week_specialist_feed_queries())

    if catch_net_provider is not None:
        if not _provider_available(catch_net_provider):
            telemetry.setdefault(catch_net_provider.name, {"queries_issued": 0, "hits_returned": 0, "errors": 0})
            failures.append(
                {
                    "query_id": "",
                    "provider": catch_net_provider.name,
                    "error": "ProviderUnavailable: credential not configured, catch-net skipped",
                }
            )
        else:
            jobs.extend((catch_net_provider, query) for query in radar_catchnet_queries())

    if jobs:
        workers = min(MAX_WORKERS, len(jobs))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(_discover_one, provider, query) for provider, query in jobs]
            for future in as_completed(futures):
                name, query, hits, error = future.result()
                stats = telemetry.setdefault(name, {"queries_issued": 0, "hits_returned": 0, "errors": 0})
                stats["queries_issued"] += 1
                if error:
                    stats["errors"] += 1
                    failures.append({"query_id": query.id, "provider": name, "error": error})
                    continue
                stats["hits_returned"] += len(hits)
                raw.extend(hits)

    raw.extend(background_hits)
    for hit in raw:
        qualify_hit(hit, index=index)
    dedupe_hits(raw)
    qualifying = [hit for hit in unique_hits(raw) if hit.qualifying]

    previous = previous_developments(inbox_dir) if inbox_dir is not None else []
    developments = cluster_hits(qualifying, entities=entity_list, previous=previous, now=now)
    watches = load_watchlist(inbox_dir) if inbox_dir is not None else []
    watch_events = apply_watchlist(developments, watches)
    attach_market_context(developments, repo=market_repo)
    attach_trusted_context(developments, evidence=evidence, assessments=assessments)

    latency = round(time.monotonic() - started, 3)
    generated = now.isoformat(timespec="seconds")
    budget = radar_query_budget()
    google_stack = {"google_news_rss", "specialist_rss"}
    stats = {
        "raw_discovered": len(raw),
        "qualifying": len(qualifying),
        "developments": len(developments),
        "board": 0,
        "exa_only": sum(
            1
            for row in developments
            if "exa" in row.provenance and not any(name in google_stack for name in row.provenance)
        ),
        "weak_signals": sum(1 for row in developments if row.weak_signal_label),
        "watch_matches": len(watch_events),
        "query_budget": budget,
        "window": RADAR_WINDOW,
        "ttl_seconds": CACHE_TTL_SECONDS,
    }
    edition = compose_edition(
        developments,
        generated_at=generated,
        window=RADAR_WINDOW,
        latency_seconds=latency,
        cache_status="live",
        expires_at=None,
        stats=stats,
        query_failures=failures,
        provider_telemetry=telemetry,
        today=now.date(),
    )
    if persist and inbox_dir is not None:
        write_cache(edition, inbox_dir=inbox_dir)
        append_watch_events(watch_events, inbox_dir=inbox_dir)
        for event in watch_events:
            event.setdefault("emitted_at", generated)
    edition.stats["watch_events"] = watch_events
    return edition
