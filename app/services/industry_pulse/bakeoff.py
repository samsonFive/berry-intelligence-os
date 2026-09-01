"""Evaluate bake-off hits into raw, explainable metrics. No composite score."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Callable

from app.services.coverage_assurance.universe import load_universe
from app.services.industry_pulse.authority import (
    authority_tier,
    class_by_host,
    evidence_hosts,
    is_cultivar_dense,
    is_unknown_unknown,
    source_hosts,
    universe_hosts,
)
from app.services.industry_pulse.brightdata import BrightDataSearchProvider
from app.services.industry_pulse.brightdata import available as brightdata_available
from app.services.industry_pulse.dedup import dedupe_hits, identity_key, unique_hits
from app.services.industry_pulse.exa import ExaSearchProvider
from app.services.industry_pulse.exa import available as exa_available
from app.services.industry_pulse.firecrawl import FirecrawlSearchProvider
from app.services.industry_pulse.firecrawl import available as firecrawl_available
from app.services.industry_pulse.matrix import WINDOWS, PulseQuery
from app.services.industry_pulse.models import DiscoveryHit
from app.services.industry_pulse.novelty import classify_hit
from app.services.industry_pulse.perplexity_provider import PerplexitySearchProvider
from app.services.industry_pulse.perplexity_provider import available as perplexity_available
from app.services.industry_pulse.providers import DiscoveryProvider, GoogleNewsRssProvider
from app.services.industry_pulse.qualify import (
    QualificationIndex,
    qualify_hit,
    rejection_reason_counts,
)
from app.services.industry_pulse.run import names_from_entities
from app.services.industry_pulse.slices import ACQUISITION_PROBE_URLS, BAKEOFF_SLICES, slice_query
from app.services.industry_pulse.union import union_hits
from app.services.recall_audit.classify import SOURCE_COLLECTED_ITEM_MISSED, SOURCE_UNKNOWN

# Documented list prices as of 2026-09-01. Not used at product runtime.
PRICING_AS_OF = "2026-09-01"
UNIT_COST_USD = {
    "google_news_rss": 0.0,
    "perplexity": 0.005,
    "exa": 0.007,
    "firecrawl": 0.0,  # credit-based; estimated in the written cost model only
    "brightdata": 0.0015,
}

PROPRIETARY_TOKENS = (
    "Assessment",
    "Signal review",
    "Fact statement",
    "analyst notes",
    "private report",
)


@dataclass
class ProviderMetrics:
    provider: str
    live: bool
    unavailable_reason: str | None
    total_results: int = 0
    unique_urls: int = 0
    qualifying: int = 0
    novel_qualifying: int = 0
    known_source_new_item: int = 0
    unknown_source: int = 0
    unknown_unknown: int = 0
    tier1: int = 0
    tier2: int = 0
    duplicates: int = 0
    non_qualifying: int = 0
    false_positive_rate: float | None = None
    reliable_published_dates: int = 0
    cultivar_dense: int = 0
    latency_seconds_total: float = 0.0
    latency_seconds_mean: float | None = None
    api_calls: int = 0
    estimated_cost_usd: float | None = None
    query_failures: int = 0
    by_geography: dict[str, int] = field(default_factory=dict)
    by_berry: dict[str, int] = field(default_factory=dict)
    unknown_unknown_hosts: list[str] = field(default_factory=list)
    tier1_hosts: list[str] = field(default_factory=list)
    qualifying_examples: list[dict[str, str | None]] = field(default_factory=list)
    by_window: dict[str, dict[str, int]] = field(default_factory=dict)
    rejection_reasons: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_hits(
    hits: list[DiscoveryHit],
    *,
    provider: str,
    live: bool,
    sources: list[dict[str, Any]],
    published_evidence: list[dict[str, Any]],
    universe_entries: list[dict[str, Any]],
    varieties: list[dict[str, Any]] | None = None,
    entities: list[dict[str, Any]] | None = None,
    latency_seconds_total: float = 0.0,
    api_calls: int = 0,
    query_failures: int = 0,
    unavailable_reason: str | None = None,
) -> ProviderMetrics:
    known = source_hosts(sources)
    universe = universe_hosts(universe_entries)
    cited = evidence_hosts(published_evidence)
    class_map = class_by_host(sources, universe_entries)
    variety_names: set[str] = set()
    for row in varieties or []:
        if row.get("name"):
            variety_names.add(str(row["name"]))
        for alias in row.get("aliases") or []:
            if alias:
                variety_names.add(str(alias))
    index = QualificationIndex.compile(
        company_names=names_from_entities(entities or [], prefix="company-"),
        variety_names=variety_names,
        sources=sources,
        universe_entries=universe_entries,
    )
    qualified = [qualify_hit(hit, index=index) for hit in hits]
    deduped = dedupe_hits(qualified)
    classified = [
        classify_hit(hit, sources=sources, published_evidence=published_evidence, varieties=varieties)
        for hit in deduped
    ]
    unique = unique_hits(classified)
    qualifying = [hit for hit in unique if hit.qualifying]
    unknown_hosts = sorted(
        {
            hit.source_domain
            for hit in qualifying
            if is_unknown_unknown(hit.source_domain, known_sources=known, universe=universe, cited=cited)
        }
    )
    tier1_hosts = sorted(
        {hit.source_domain for hit in unique if authority_tier(hit.source_domain, class_map=class_map) == "tier1"}
    )
    non_qualifying = len(unique) - len(qualifying)
    unit = UNIT_COST_USD.get(provider)
    cost = round(unit * api_calls, 4) if unit is not None and live else None
    mean_latency = round(latency_seconds_total / api_calls, 3) if api_calls else None
    return ProviderMetrics(
        provider=provider,
        live=live,
        unavailable_reason=unavailable_reason,
        total_results=len(hits),
        unique_urls=len(unique),
        qualifying=len(qualifying),
        novel_qualifying=sum(1 for hit in qualifying if hit.novel_domain or hit.miss_classification == SOURCE_UNKNOWN),
        known_source_new_item=sum(
            1 for hit in qualifying if hit.miss_classification == SOURCE_COLLECTED_ITEM_MISSED
        ),
        unknown_source=sum(1 for hit in qualifying if hit.miss_classification == SOURCE_UNKNOWN),
        unknown_unknown=len(unknown_hosts),
        tier1=sum(1 for hit in unique if authority_tier(hit.source_domain, class_map=class_map) == "tier1"),
        tier2=sum(1 for hit in unique if authority_tier(hit.source_domain, class_map=class_map) == "tier2"),
        duplicates=sum(1 for hit in classified if hit.duplicate_of),
        non_qualifying=non_qualifying,
        false_positive_rate=round(non_qualifying / len(unique), 3) if unique else None,
        reliable_published_dates=sum(1 for hit in unique if hit.published_date),
        cultivar_dense=sum(1 for hit in unique if is_cultivar_dense(hit)),
        latency_seconds_total=round(latency_seconds_total, 3),
        latency_seconds_mean=mean_latency,
        api_calls=api_calls,
        estimated_cost_usd=cost,
        query_failures=query_failures,
        by_geography=_count_unique(unique, "geography"),
        by_berry=_count_unique(unique, "berry"),
        unknown_unknown_hosts=unknown_hosts[:40],
        tier1_hosts=tier1_hosts[:40],
        qualifying_examples=[
            {
                "title": hit.title,
                "url": hit.origin_publisher_url or hit.url,
                "source_domain": hit.source_domain,
                "published_date": hit.published_date,
                "miss_classification": hit.miss_classification,
                "qualify_reason": hit.qualify_reason,
            }
            for hit in qualifying[:15]
        ],
        by_window=_window_counts(classified),
        rejection_reasons=rejection_reason_counts(unique),
    )


def _window_counts(hits: list[DiscoveryHit]) -> dict[str, dict[str, int]]:
    """Per-window unique identity. Does not collapse across windows."""
    counts = {window: {"unique": 0, "qualifying": 0} for window in WINDOWS}
    seen: dict[str, set[str]] = {window: set() for window in WINDOWS}
    for hit in hits:
        window = None
        for candidate in WINDOWS:
            if hit.query_id.endswith(f":{candidate}"):
                window = candidate
                break
        if window is None:
            continue
        key = identity_key(hit)
        if key in seen[window]:
            continue
        seen[window].add(key)
        counts[window]["unique"] += 1
        if hit.qualifying:
            counts[window]["qualifying"] += 1
    return counts


def _count_unique(hits: list[DiscoveryHit], field_name: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for hit in hits:
        value = getattr(hit, field_name) or "none"
        counts[str(value)] = counts.get(str(value), 0) + 1
    return counts


def bakeoff_queries(*, google_when: bool) -> list[PulseQuery]:
    queries: list[PulseQuery] = []
    for row in BAKEOFF_SLICES:
        for window in WINDOWS:
            queries.append(slice_query(row, window, google_when=google_when))
    return queries


def assert_public_queries(queries: list[PulseQuery]) -> None:
    for query in queries:
        lowered = query.text.lower()
        for token in PROPRIETARY_TOKENS:
            if token.lower() in lowered:
                raise ValueError(f"proprietary token leaked into bake-off query: {token}")


def discover_timed(provider: DiscoveryProvider, query: PulseQuery) -> tuple[list[DiscoveryHit], float]:
    started = time.monotonic()
    hits = provider.discover(query)
    return hits, time.monotonic() - started


def run_provider_slice(
    provider: DiscoveryProvider,
    *,
    live: bool,
    sources: list[dict[str, Any]],
    published_evidence: list[dict[str, Any]],
    universe_entries: list[dict[str, Any]],
    varieties: list[dict[str, Any]] | None = None,
    entities: list[dict[str, Any]] | None = None,
    google_when: bool = False,
    unavailable_reason: str | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> tuple[ProviderMetrics, list[DiscoveryHit]]:
    if not live:
        return (
            evaluate_hits(
                [],
                provider=provider.name,
                live=False,
                sources=sources,
                published_evidence=published_evidence,
                universe_entries=universe_entries,
                varieties=varieties,
                entities=entities,
                unavailable_reason=unavailable_reason or "credentials absent",
            ),
            [],
        )
    queries = bakeoff_queries(google_when=google_when)
    assert_public_queries(queries)
    raw: list[DiscoveryHit] = []
    latency = 0.0
    failures = 0
    calls = 0
    for query in queries:
        started = clock()
        try:
            raw.extend(provider.discover(query))
            calls += 1
        except Exception:  # noqa: BLE001 — one query must not abort the bake-off
            failures += 1
        latency += clock() - started
    metrics = evaluate_hits(
        raw,
        provider=provider.name,
        live=True,
        sources=sources,
        published_evidence=published_evidence,
        universe_entries=universe_entries,
        varieties=varieties,
        entities=entities,
        latency_seconds_total=latency,
        api_calls=calls,
        query_failures=failures,
    )
    return metrics, unique_hits(dedupe_hits(raw))


def credential_status() -> dict[str, dict[str, Any]]:
    return {
        "google_news_rss": {"live": True, "reason": None},
        "exa": {"live": exa_available(), "reason": None if exa_available() else "EXA_API_KEY absent"},
        "firecrawl": {
            "live": firecrawl_available(),
            "reason": None if firecrawl_available() else "FIRECRAWL_API_KEY absent",
        },
        "perplexity": {
            "live": perplexity_available(),
            "reason": None if perplexity_available() else "PERPLEXITY_API_KEY absent",
        },
        "brightdata": {
            "live": brightdata_available(),
            "reason": None if brightdata_available() else "BRIGHTDATA_API_KEY / BRIGHTDATA_SERP_ZONE absent",
        },
    }


def run_bakeoff(
    *,
    sources: list[dict[str, Any]],
    published_evidence: list[dict[str, Any]],
    data_dir: Any | None = None,
    varieties: list[dict[str, Any]] | None = None,
    entities: list[dict[str, Any]] | None = None,
    today: date | None = None,
    include_live: bool = True,
) -> dict[str, Any]:
    today = today or datetime.now(timezone.utc).date()
    universe_entries = []
    if data_dir is not None:
        universe_entries = load_universe(data_dir).get("entries") or []
    status = credential_status()
    providers: list[tuple[DiscoveryProvider, bool, bool, str | None]] = [
        (GoogleNewsRssProvider(), True, True, None),
        (ExaSearchProvider(today=today), False, status["exa"]["live"], status["exa"]["reason"]),
        (FirecrawlSearchProvider(today=today), False, status["firecrawl"]["live"], status["firecrawl"]["reason"]),
        (PerplexitySearchProvider(today=today), False, status["perplexity"]["live"], status["perplexity"]["reason"]),
        (BrightDataSearchProvider(), False, status["brightdata"]["live"], status["brightdata"]["reason"]),
    ]
    metrics_rows: list[dict[str, Any]] = []
    unique_by_provider: dict[str, list[DiscoveryHit]] = {}
    for provider, google_when, live_flag, reason in providers:
        live = bool(include_live and live_flag)
        if not include_live and live_flag:
            run_reason = "live fetch disabled"
        elif live:
            run_reason = None
        else:
            run_reason = reason
        metrics, unique = run_provider_slice(
            provider,
            live=live,
            sources=sources,
            published_evidence=published_evidence,
            universe_entries=universe_entries,
            varieties=varieties,
            entities=entities,
            google_when=google_when,
            unavailable_reason=run_reason,
        )
        metrics_rows.append(metrics.as_dict())
        unique_by_provider[provider.name] = unique

    unions: list[dict[str, Any]] = []
    live_names = [row["provider"] for row in metrics_rows if row["live"]]
    if len(live_names) >= 2:
        left, right = live_names[0], live_names[1]
        unions.append(
            union_hits(
                unique_by_provider[left],
                unique_by_provider[right],
                left_name=left,
                right_name=right,
            )
        )

    acquisition = {
        "tested": False,
        "reason": "FIRECRAWL_API_KEY absent" if not firecrawl_available() else None,
        "probe_urls": [{"kind": kind, "url": url} for kind, url in ACQUISITION_PROBE_URLS],
        "results": [],
    }
    if include_live and firecrawl_available():
        scraper = FirecrawlSearchProvider()
        results = []
        for kind, url in ACQUISITION_PROBE_URLS:
            started = time.monotonic()
            try:
                row = scraper.scrape(url)
                row["kind"] = kind
                row["latency_seconds"] = round(time.monotonic() - started, 3)
                results.append(row)
            except Exception as exc:  # noqa: BLE001
                results.append(
                    {
                        "kind": kind,
                        "url": url,
                        "success": False,
                        "error": type(exc).__name__,
                        "latency_seconds": round(time.monotonic() - started, 3),
                    }
                )
        acquisition = {
            "tested": True,
            "reason": None,
            "probe_urls": [{"kind": kind, "url": url} for kind, url in ACQUISITION_PROBE_URLS],
            "results": results,
        }

    return {
        "as_of": today.isoformat(),
        "pricing_as_of": PRICING_AS_OF,
        "auto_trust": False,
        "production_provider_unchanged": True,
        "production_provider": "google_news_rss",
        "slice_count": len(BAKEOFF_SLICES),
        "windows": list(WINDOWS),
        "queries_per_live_provider": len(BAKEOFF_SLICES) * len(WINDOWS),
        "credential_status": status,
        "providers": metrics_rows,
        "unions": unions,
        "firecrawl_acquisition": acquisition,
        "notes": [
            "No composite score. Compare raw columns only.",
            "Unknown-unknown hosts are not onboarded.",
            "Paid adapters are not the production Industry Pulse default.",
            "Query strings are public berry-industry search terms only.",
        ],
    }
