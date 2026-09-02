"""Global Week Intelligence V1 -- live, unreviewed weekly industry edition.

Stakeholder question: "What changed in the berry industry this week?"

This is the LIVE RESEARCH PLANE. It reuses Industry Pulse discovery,
qualification, and dedupe unchanged. It does not wait for Publication
Review or Evidence Review. Every displayed item is LIVE / UNREVIEWED.

Never writes Evidence. Never creates a Signal or Assessment. Never
mutates entity truth. The optional Send to review action reuses
`industry_pulse.intake.intake_qualified_hits()` and still enters ordinary
Publication Review -- the only door back into durable trust.
"""

from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Iterable
from urllib.parse import urlparse

from app.services.article_dedup import normalize_title
from app.services.competitor_pulse import (
    _BERRY_PATTERNS,
    _GEOGRAPHY_PATTERNS,
    _normalize_quotes,
    detect_geography,
)
from app.services.industry_pulse.dedup import dedupe_hits, identity_key, unique_hits
from app.services.industry_pulse.matrix import (
    ALL_BERRIES_TERMS,
    BERRIES,
    GEO_EDITIONS,
    WINDOW_DAYS,
    WINDOW_WHEN,
    PulseQuery,
    catch_net_queries,
    generate_pulse_queries,
    regional_language_queries,
    week_retail_query,
)
from app.services.industry_pulse.specialist_feeds import (
    week_specialist_feed_queries,
    week_specialist_site_queries,
)
from app.services.industry_pulse.models import DiscoveryHit
from app.services.industry_pulse.providers import DiscoveryProvider
from app.services.industry_pulse.qualify import (
    EDITORIAL_COMPETITOR,
    EDITORIAL_MARKET,
    EDITORIAL_RESEARCH,
    EDITORIAL_VARIETY,
    SOURCE_BREEDER,
    SOURCE_GOV_AG,
    SOURCE_TRADE,
    SOURCE_UNIVERSITY,
    QualificationIndex,
    qualify_hit,
)
from app.services.industry_pulse.run import names_from_entities

LIVE_WINDOWS = ("24h", "7d", "30d")
DEFAULT_WINDOW = "7d"
TRUST_LABEL = "LIVE / UNREVIEWED"

REGION_ORDER = ("americas", "europe", "africa", "apac")
REGION_LABELS = {
    "americas": "Americas",
    "europe": "Europe",
    "africa": "Africa",
    "apac": "APAC",
    "global": "Global",
}
BERRY_LABELS = {
    "blueberry": "Blueberry",
    "strawberry": "Strawberry",
    "raspberry": "Raspberry",
    "blackberry": "Blackberry",
}
WINDOW_LABELS = {"24h": "24 hours", "7d": "7 days", "30d": "30 days"}

SECTION_WHAT_MATTERS = "what_matters"
SECTION_COMPETITOR = "competitor_moves"
SECTION_VARIETY = "varieties_genetics"
SECTION_REGION = "by_region"
SECTION_BERRY = "by_berry"
SECTION_MARKET = "market_supply_trade"
SECTION_RESEARCH = "research_regulation"
SECTION_EMERGING = "emerging_unreviewed"

WHAT_MATTERS_LIMIT = 8
SECTION_LIMIT = 8
MAX_PER_PUBLISHER_LEAD = 2
MAX_WORKERS = 16
# Provider `when:` is advisory. Retrieve broader, then keep the displayed
# window honest using the article's normalized published_date.
RETRIEVE_WINDOW = {"24h": "7d", "7d": "30d", "30d": "30d"}

_PBR_RE = re.compile(
    r"\b(PBR|PVP|PVPO|CPVO|plant breeders? rights|plant variety protection|"
    r"variety registration|certificate issued)\b",
    re.IGNORECASE,
)
_PATENT_RE = re.compile(r"\b(USPTO|patent|patents|plant patent|WO20|US20)\b", re.IGNORECASE)

SPECIALIST_CONTEXTS = frozenset({SOURCE_TRADE, SOURCE_BREEDER, SOURCE_UNIVERSITY})
OFFICIAL_CONTEXTS = frozenset({SOURCE_GOV_AG})

_EVENT_RE = re.compile(
    r"\b(acquisition|merger|partnership|joint venture|licen[cs]e|unveils|"
    r"launches?|PBR|plant breeders? rights|plant patent|CPVO|USPTO|"
    r"cultivar|new variety|recall|tariff|registration)\b",
    re.IGNORECASE,
)

_SLUG_FROM_BERRY_ID = {f"berry-{slug}": slug for slug in BERRIES}


def retrieve_window_for(display_window: str) -> str:
    if display_window not in RETRIEVE_WINDOW:
        raise ValueError(f"unsupported window: {display_window}")
    return RETRIEVE_WINDOW[display_window]


def week_apac_focus_queries() -> list[PulseQuery]:
    """Bounded current-week APAC discovery. Not a translation platform."""
    au = GEO_EDITIONS["apac"]
    return [
        PulseQuery(
            id="apac:en",
            text=(
                f"({ALL_BERRIES_TERMS} OR berry OR berries) "
                "(Australia OR \"New Zealand\" OR Vietnam OR China OR Japan OR Korea "
                "OR Tasmania OR Indonesia OR Thailand OR \"Hong Kong\") "
                "(harvest OR export OR import OR price OR variety OR cultivar OR "
                '"market access" OR branding OR grower OR volumes)'
            ),
            berry=None,
            geography="apac",
            topic="industry_pulse",
            kind="apac_focus",
            hl=au["hl"],
            gl=au["gl"],
            ceid=au["ceid"],
        ),
        PulseQuery(
            id="apac:zh-focus",
            text="(蓝莓 OR 草莓) (价格 OR 出口 OR 品种 OR 种植 OR 市场)",
            berry=None,
            geography="apac",
            topic="industry_pulse",
            kind="apac_focus",
            hl="zh-CN",
            gl="CN",
            ceid="CN:zh-Hans",
        ),
        PulseQuery(
            id="apac:ja-focus",
            text="(イチゴ OR ブルーベリー) (品種 OR ブランド OR 輸出 OR 産地)",
            berry=None,
            geography="apac",
            topic="industry_pulse",
            kind="apac_focus",
            hl="ja-JP",
            gl="JP",
            ceid="JP:ja",
        ),
    ]


def week_queries() -> list[PulseQuery]:
    """Industry Pulse 32-query matrix plus bounded extras for this edition.

    Does not change `generate_pulse_queries()` -- Industry Pulse stay at 32.
    Extra rows: language editions, retail, specialist site: hosts, APAC focus.
    """
    return [
        *generate_pulse_queries(),
        *regional_language_queries(),
        week_retail_query(),
        *week_specialist_site_queries(),
        *week_apac_focus_queries(),
    ]


def week_catch_net_queries(queries: list[PulseQuery]) -> list[PulseQuery]:
    """Industry Pulse catch-net plus APAC and local-language rows.

    APAC was the known weak region on earlier Pulse tests; routing it to the
    semantic catch-net is a bounded addition, not a doubled matrix.
    """
    selected: dict[str, PulseQuery] = {
        query.id: query for query in catch_net_queries(queries) if query.kind != "specialist_site"
    }
    for query in queries:
        if query.kind == "specialist_site":
            continue
        if query.geography == "apac" or query.kind in {"regional_language", "apac_focus"}:
            selected[query.id] = query
    return list(selected.values())


def berry_slug(value: str | None) -> str | None:
    if not value:
        return None
    text = str(value).strip().lower()
    if text in BERRIES:
        return text
    return _SLUG_FROM_BERRY_ID.get(text)


def berries_mentioned(text: str, *, query_berry: str | None = None) -> tuple[str, ...]:
    """Prefer berries named in the story. Query berry is provenance only --
    used when the title/snippet names none, never to force a second crop."""
    found: list[str] = []
    for berry_id, pattern in _BERRY_PATTERNS.items():
        slug = berry_slug(berry_id)
        if slug and pattern.search(text) and slug not in found:
            found.append(slug)
    if found:
        return tuple(found)
    query_slug = berry_slug(query_berry)
    return (query_slug,) if query_slug else ()


def geographies_mentioned(text: str, *, query_geography: str | None = None) -> tuple[str, ...]:
    """Places named in the story only. Query geography is retrieval provenance,
    not a claim that the article is about that region."""
    del query_geography  # provenance stays on DiscoveryHit.geography
    found: list[str] = []
    for geography, pattern in _GEOGRAPHY_PATTERNS.items():
        if pattern.search(text) and geography not in found:
            found.append(geography)
    return tuple(found)


def _in_selected_window(published_date: str | None, *, today: date, window: str) -> bool:
    """Google News `when:` is advisory. The edition only shows dated items
    whose published_date falls in the selected window, matching run_pulse()."""
    if not published_date:
        return False
    days = WINDOW_DAYS.get(window)
    if days is None:
        return False
    try:
        day = date.fromisoformat(published_date[:10])
    except ValueError:
        return False
    return (today - timedelta(days=days)) <= day <= today


def _is_homepage(url: str) -> bool:
    path = urlparse(url).path
    return path in {"", "/"}


def publisher_of(hit: DiscoveryHit) -> str:
    return str(hit.origin_publisher_name or hit.source_domain or "Unknown publisher")


def _named_entity_count(hit: DiscoveryHit) -> int:
    return sum(
        1
        for reason in (hit.qualify_reasons or [])
        if reason.startswith("named company") or reason.startswith("named cultivar")
    )


def _explicit_event(hit: DiscoveryHit) -> bool:
    if hit.editorial_topic in {EDITORIAL_COMPETITOR, EDITORIAL_VARIETY}:
        return True
    return bool(_EVENT_RE.search(f"{hit.title} {hit.snippet}"))


def _story_cluster_key(title: str) -> str:
    tokens = [token for token in normalize_title(title).split() if len(token) > 2][:6]
    return " ".join(tokens) or normalize_title(title)


def corroboration_by_key(hits: Iterable[DiscoveryHit]) -> dict[str, int]:
    """Distinct publishers per similar-title cluster. Not a score."""
    buckets: dict[str, set[str]] = {}
    keys: dict[str, str] = {}
    for hit in hits:
        cluster = _story_cluster_key(hit.title)
        ident = identity_key(hit)
        keys[ident] = cluster
        buckets.setdefault(cluster, set()).add(publisher_of(hit).lower())
    return {ident: len(buckets.get(cluster, set())) for ident, cluster in keys.items()}


@dataclass
class WeekItem:
    title: str
    url: str
    publisher: str
    published_date: str | None
    captured_at: str
    snippet: str
    berry: str | None
    berries: tuple[str, ...]
    geography: str | None
    geographies: tuple[str, ...]
    provider: str
    providers: tuple[str, ...]
    query_id: str
    qualify_reasons: list[str] = field(default_factory=list)
    editorial_topic: str | None = None
    source_context: str | None = None
    specialist: bool = False
    official: bool = False
    explicit_event: bool = False
    named_entity_count: int = 0
    corroboration: int = 1
    in_window: bool = True
    rank_reasons: tuple[str, ...] = ()
    trust_label: str = TRUST_LABEL

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["berries"] = list(self.berries)
        payload["geographies"] = list(self.geographies)
        payload["providers"] = list(self.providers)
        payload["rank_reasons"] = list(self.rank_reasons)
        return payload


def _rank_reasons(item: WeekItem) -> tuple[str, ...]:
    reasons: list[str] = []
    if item.explicit_event:
        reasons.append("Named competitor, cultivar, or regulatory event")
    if item.official:
        reasons.append("Official source")
    if item.specialist:
        reasons.append("Specialist source")
    if item.corroboration > 1:
        reasons.append(f"Corroborated across {item.corroboration} publishers")
    if item.named_entity_count:
        reasons.append(f"{item.named_entity_count} known companies/cultivars named")
    if item.in_window:
        reasons.append("Dated in the selected window")
    elif item.published_date:
        reasons.append(f"Article date {item.published_date} is older than this window")
    else:
        reasons.append("Publication date unknown")
    return tuple(reasons)


def _rank_tuple(item: WeekItem) -> tuple[Any, ...]:
    """Deterministic lexicographic order. Not a weighted importance score.

    Event and source class outrank volume. Recency is the last dated
    tie-break, then title for stability.
    """
    return (
        1 if item.in_window else 0,
        1 if item.explicit_event else 0,
        1 if item.official else 0,
        1 if item.specialist else 0,
        item.corroboration,
        item.named_entity_count,
        item.published_date or "",
        item.title.lower(),
    )


def display_url(hit: DiscoveryHit) -> str:
    origin = hit.origin_publisher_url or hit.url
    if _is_homepage(origin) and hit.wrapper_url:
        return hit.wrapper_url
    return origin


def _to_item(
    hit: DiscoveryHit,
    *,
    captured_at: str,
    providers: Iterable[str],
    corroboration: int,
    window: str,
    today: date,
) -> WeekItem:
    text = f"{hit.title} {hit.snippet}"
    berries = berries_mentioned(text, query_berry=hit.berry)
    geos = geographies_mentioned(text, query_geography=hit.geography)
    context = hit.source_context
    item = WeekItem(
        title=hit.title,
        url=display_url(hit),
        publisher=publisher_of(hit),
        published_date=hit.published_date,
        captured_at=captured_at,
        snippet=hit.snippet,
        berry=berries[0] if berries else berry_slug(hit.berry),
        berries=berries,
        geography=geos[0] if geos else None,
        geographies=geos,
        provider=hit.provider,
        providers=tuple(sorted({*(providers or []), hit.provider})),
        query_id=hit.query_id,
        qualify_reasons=list(hit.qualify_reasons or []),
        editorial_topic=hit.editorial_topic,
        source_context=context,
        specialist=context in SPECIALIST_CONTEXTS,
        official=context in OFFICIAL_CONTEXTS,
        explicit_event=_explicit_event(hit),
        named_entity_count=_named_entity_count(hit),
        corroboration=corroboration,
        in_window=_in_selected_window(hit.published_date, today=today, window=window),
    )
    item.rank_reasons = _rank_reasons(item)
    return item


def diverse_take(
    items: list[WeekItem],
    *,
    limit: int = WHAT_MATTERS_LIMIT,
    max_per_publisher: int = MAX_PER_PUBLISHER_LEAD,
) -> list[WeekItem]:
    """Keep one publisher from dominating a lead section. No score."""
    chosen: list[WeekItem] = []
    counts: dict[str, int] = {}
    for item in items:
        key = item.publisher.strip().lower()
        if counts.get(key, 0) >= max_per_publisher:
            continue
        chosen.append(item)
        counts[key] = counts.get(key, 0) + 1
        if len(chosen) >= limit:
            break
    return chosen


def _discover_one(provider: DiscoveryProvider, query: PulseQuery) -> tuple[str, PulseQuery, list[DiscoveryHit], str | None]:
    try:
        hits = provider.discover(query)
        for hit in hits:
            hit.title = _normalize_quotes(hit.title)
            hit.snippet = _normalize_quotes(hit.snippet)
        return provider.name, query, hits, None
    except Exception as exc:  # noqa: BLE001 -- one query/provider must not abort the edition
        return provider.name, query, [], f"{type(exc).__name__}: {exc}"


def _run_provider_queries(
    provider: DiscoveryProvider,
    queries: list[PulseQuery],
    *,
    raw: list[DiscoveryHit],
    found_by: dict[str, set[str]],
    telemetry: dict[str, dict[str, int]],
    failures: list[dict[str, str]],
) -> None:
    stats = telemetry.setdefault(provider.name, {"queries_issued": 0, "hits_returned": 0, "errors": 0})
    if not queries:
        return
    workers = min(MAX_WORKERS, len(queries))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_discover_one, provider, query) for query in queries]
        for future in as_completed(futures):
            name, query, hits, error = future.result()
            stats["queries_issued"] += 1
            if error:
                stats["errors"] += 1
                failures.append({"query_id": query.id, "provider": name, "error": error})
                continue
            stats["hits_returned"] += len(hits)
            raw.extend(hits)
            for hit in hits:
                found_by.setdefault(identity_key(hit), set()).add(name)


def _qualify_corpus(
    *,
    entities: Iterable[dict[str, Any]],
    varieties: Iterable[dict[str, Any]],
    sources: Iterable[dict[str, Any]],
) -> QualificationIndex:
    company_names = names_from_entities(entities, prefix="company-")
    variety_names = {str(row.get("name") or "") for row in varieties if row.get("name")}
    for row in varieties:
        for alias in row.get("aliases") or []:
            if alias:
                variety_names.add(str(alias))
    for entity in entities:
        if str(entity.get("entity_type") or "") != "variety":
            continue
        if entity.get("name"):
            variety_names.add(str(entity["name"]))
        for alias in entity.get("aliases") or []:
            if alias:
                variety_names.add(str(alias))
    return QualificationIndex.compile(
        company_names=company_names,
        variety_names=variety_names,
        sources=sources,
    )


@dataclass
class WeekEdition:
    window: str
    searched_at: str
    latency_seconds: float
    items: list[WeekItem]
    what_matters: list[WeekItem]
    competitor_moves: list[WeekItem]
    varieties_genetics: list[WeekItem]
    by_region: dict[str, list[WeekItem]]
    by_berry: dict[str, list[WeekItem]]
    market_supply_trade: list[WeekItem]
    research_regulation: list[WeekItem]
    pbr_regulatory: list[WeekItem]
    patents_genetics: list[WeekItem]
    emerging_unreviewed: list[WeekItem]
    older_circulating: list[WeekItem]
    stats: dict[str, Any]
    provider_telemetry: dict[str, dict[str, int]]
    query_failures: list[dict[str, str]]
    weak_regions: tuple[str, ...]
    weak_berries: tuple[str, ...]
    source_diversity: dict[str, Any]
    trust_label: str = TRUST_LABEL

    def as_dict(self) -> dict[str, Any]:
        return {
            "window": self.window,
            "searched_at": self.searched_at,
            "latency_seconds": self.latency_seconds,
            "items": [item.as_dict() for item in self.items],
            "what_matters": [item.as_dict() for item in self.what_matters],
            "competitor_moves": [item.as_dict() for item in self.competitor_moves],
            "varieties_genetics": [item.as_dict() for item in self.varieties_genetics],
            "by_region": {key: [item.as_dict() for item in rows] for key, rows in self.by_region.items()},
            "by_berry": {key: [item.as_dict() for item in rows] for key, rows in self.by_berry.items()},
            "market_supply_trade": [item.as_dict() for item in self.market_supply_trade],
            "research_regulation": [item.as_dict() for item in self.research_regulation],
            "pbr_regulatory": [item.as_dict() for item in self.pbr_regulatory],
            "patents_genetics": [item.as_dict() for item in self.patents_genetics],
            "emerging_unreviewed": [item.as_dict() for item in self.emerging_unreviewed],
            "older_circulating": [item.as_dict() for item in self.older_circulating],
            "stats": self.stats,
            "provider_telemetry": self.provider_telemetry,
            "query_failures": self.query_failures,
            "weak_regions": list(self.weak_regions),
            "weak_berries": list(self.weak_berries),
            "source_diversity": self.source_diversity,
            "trust_label": self.trust_label,
        }


def _compose_items(
    hits: list[DiscoveryHit],
    *,
    captured_at: str,
    found_by: dict[str, set[str]],
    window: str,
    today: date,
) -> list[WeekItem]:
    unique = [hit for hit in unique_hits(hits) if hit.qualifying]
    corroboration = corroboration_by_key(unique)
    items = [
        _to_item(
            hit,
            captured_at=captured_at,
            providers=found_by.get(identity_key(hit) or "", set()),
            corroboration=corroboration.get(identity_key(hit), 1),
            window=window,
            today=today,
        )
        for hit in unique
    ]
    items.sort(key=_rank_tuple, reverse=True)
    return items


def _in_topic(item: WeekItem, *topics: str) -> bool:
    return item.editorial_topic in topics


def compose_edition(
    items: list[WeekItem],
    *,
    window: str,
    searched_at: str,
    latency_seconds: float,
    raw_hit_count: int,
    unique_count: int,
    provider_telemetry: dict[str, dict[str, int]],
    query_failures: list[dict[str, str]],
    query_count: int,
    retrieve_window: str | None = None,
) -> WeekEdition:
    ranked = sorted(items, key=_rank_tuple, reverse=True)
    current = [item for item in ranked if item.in_window]
    older = [item for item in ranked if not item.in_window]
    what_matters = diverse_take(current, limit=WHAT_MATTERS_LIMIT)
    competitor = [item for item in current if _in_topic(item, EDITORIAL_COMPETITOR) or "named company" in " ".join(item.qualify_reasons)][:SECTION_LIMIT]
    varieties = [item for item in current if _in_topic(item, EDITORIAL_VARIETY) or any("cultivar" in reason for reason in item.qualify_reasons)][:SECTION_LIMIT]
    market = [item for item in current if _in_topic(item, EDITORIAL_MARKET)][:SECTION_LIMIT]
    research = [item for item in current if _in_topic(item, EDITORIAL_RESEARCH) or item.official][:SECTION_LIMIT]
    pbr = [item for item in current if _PBR_RE.search(f"{item.title} {item.snippet}")][:SECTION_LIMIT]
    patents = [
        item
        for item in current
        if _PATENT_RE.search(f"{item.title} {item.snippet}") and item not in pbr
    ][:SECTION_LIMIT]
    emerging = [
        item
        for item in current
        if not item.official and not item.specialist and item.corroboration <= 1
    ][:SECTION_LIMIT]

    by_region_all: dict[str, list[WeekItem]] = {
        geography: [item for item in current if geography in item.geographies] for geography in REGION_ORDER
    }
    by_berry_all: dict[str, list[WeekItem]] = {
        berry: [item for item in current if berry in item.berries] for berry in BERRIES
    }
    by_region = {geography: rows[:SECTION_LIMIT] for geography, rows in by_region_all.items()}
    by_berry = {berry: rows[:SECTION_LIMIT] for berry, rows in by_berry_all.items()}

    weak_regions = tuple(geo for geo, rows in by_region_all.items() if not rows)
    weak_berries = tuple(berry for berry, rows in by_berry_all.items() if not rows)

    publisher_counts: dict[str, int] = {}
    provider_counts: dict[str, int] = {}
    specialist_publishers: set[str] = set()
    official_publishers: set[str] = set()
    for item in ranked:
        publisher_counts[item.publisher] = publisher_counts.get(item.publisher, 0) + 1
        for provider in item.providers:
            provider_counts[provider] = provider_counts.get(provider, 0) + 1
        if item.specialist:
            specialist_publishers.add(item.publisher)
        if item.official:
            official_publishers.add(item.publisher)
    total = len(ranked) or 1
    top_publisher, top_count = max(publisher_counts.items(), key=lambda row: row[1]) if publisher_counts else ("", 0)

    provider_unique = {name: 0 for name in provider_telemetry}
    overlap = 0
    for item in ranked:
        if len(item.providers) > 1:
            overlap += 1
        elif len(item.providers) == 1:
            only = item.providers[0]
            if only in provider_unique:
                provider_unique[only] += 1

    newest = max((item.published_date or "" for item in current), default="") or None
    telemetry = {
        name: {**stats, "unique_qualifying": provider_unique.get(name, 0)}
        for name, stats in provider_telemetry.items()
    }
    stats = {
        "raw_discovered": raw_hit_count,
        "qualifying": len(ranked),
        "in_window_qualifying": len(current),
        "older_qualifying": len(older),
        "unique": unique_count,
        "provider_unique": provider_unique,
        "overlap_qualifying": overlap,
        "publishers": len(publisher_counts),
        "specialist_sources": len(specialist_publishers),
        "official_sources": len(official_publishers),
        "regions": {geo: len(rows) for geo, rows in by_region_all.items()},
        "berries": {berry: len(rows) for berry, rows in by_berry_all.items()},
        "newest_item": newest,
        "query_count": query_count,
        "window": window,
        "retrieve_window": retrieve_window or RETRIEVE_WINDOW.get(window, window),
        "display_window": window,
    }
    diversity = {
        "publisher_count": len(publisher_counts),
        "publisher_counts": dict(sorted(publisher_counts.items(), key=lambda row: (-row[1], row[0]))),
        "provider_counts": provider_counts,
        "lead_publisher": top_publisher,
        "lead_publisher_count": top_count,
        "lead_publisher_share": round(top_count / total, 3),
        "max_per_publisher_in_what_matters": MAX_PER_PUBLISHER_LEAD,
    }
    return WeekEdition(
        window=window,
        searched_at=searched_at,
        latency_seconds=latency_seconds,
        items=ranked,
        what_matters=what_matters,
        competitor_moves=competitor,
        varieties_genetics=varieties,
        by_region=by_region,
        by_berry=by_berry,
        market_supply_trade=market,
        research_regulation=research,
        pbr_regulatory=pbr,
        patents_genetics=patents,
        emerging_unreviewed=emerging,
        older_circulating=older[:SECTION_LIMIT],
        stats=stats,
        provider_telemetry=telemetry,
        query_failures=query_failures,
        weak_regions=weak_regions,
        weak_berries=weak_berries,
        source_diversity=diversity,
    )


def _qualify_raw(
    raw: list[DiscoveryHit],
    *,
    index: QualificationIndex,
    window: str,
    today: date,
) -> None:
    del window, today
    for hit in raw:
        qualify_hit(hit, index=index)
    dedupe_hits(raw)


def _provider_available(provider: DiscoveryProvider) -> bool:
    available = getattr(provider, "available", None)
    if callable(available):
        try:
            return bool(available())
        except Exception:  # noqa: BLE001 -- missing credential is a skip, not a crash
            return False
    return True


def run_week_intelligence(
    *,
    window: str = DEFAULT_WINDOW,
    providers: Iterable[DiscoveryProvider] = (),
    catch_net_provider: DiscoveryProvider | None = None,
    specialist_provider: DiscoveryProvider | None = None,
    entities: Iterable[dict[str, Any]] = (),
    varieties: Iterable[dict[str, Any]] = (),
    sources: Iterable[dict[str, Any]] = (),
    now: datetime | None = None,
    query_filter: Callable[[list[PulseQuery]], list[PulseQuery]] | None = None,
) -> WeekEdition:
    """Live, read-only. Writes nothing. Qualifying hits stay LIVE / UNREVIEWED."""
    if window not in LIVE_WINDOWS:
        raise ValueError(f"unsupported window: {window}")
    if window not in WINDOW_WHEN:
        raise ValueError(f"unsupported window: {window}")
    now = now or datetime.now(timezone.utc)
    started = time.monotonic()
    provider_list = list(providers)
    retrieve = retrieve_window_for(window)
    queries = [row.with_window(retrieve) for row in week_queries()]
    if query_filter is not None:
        queries = query_filter(queries)

    raw: list[DiscoveryHit] = []
    found_by: dict[str, set[str]] = {}
    telemetry: dict[str, dict[str, int]] = {}
    failures: list[dict[str, str]] = []
    jobs: list[tuple[DiscoveryProvider, PulseQuery]] = [
        (provider, query) for provider in provider_list for query in queries
    ]

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
            jobs.extend((catch_net_provider, query) for query in week_catch_net_queries(queries))

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
                for hit in hits:
                    found_by.setdefault(identity_key(hit), set()).add(name)

    index = _qualify_corpus(entities=entities, varieties=varieties, sources=sources)
    _qualify_raw(raw, index=index, window=window, today=now.date())
    captured_at = now.isoformat()
    items = _compose_items(raw, captured_at=captured_at, found_by=found_by, window=window, today=now.date())
    unique_count = len(unique_hits(raw))
    latency = round(time.monotonic() - started, 3)
    return compose_edition(
        items,
        window=window,
        searched_at=captured_at,
        latency_seconds=latency,
        raw_hit_count=len(raw),
        unique_count=unique_count,
        provider_telemetry=telemetry,
        query_failures=failures,
        query_count=len(queries),
        retrieve_window=retrieve,
    )


def find_week_hit_by_url(
    *,
    url: str,
    window: str,
    providers: Iterable[DiscoveryProvider],
    catch_net_provider: DiscoveryProvider | None = None,
    specialist_provider: DiscoveryProvider | None = None,
    entities: Iterable[dict[str, Any]] = (),
    varieties: Iterable[dict[str, Any]] = (),
    sources: Iterable[dict[str, Any]] = (),
    query_id: str | None = None,
) -> DiscoveryHit | None:
    """Re-run live discovery and return the qualifying hit for `url`.

    If `query_id` is supplied, only that query is re-issued -- still live,
    still qualified -- so Send to review does not replay the full matrix.
    """

    def only_query(rows: list[PulseQuery]) -> list[PulseQuery]:
        if not query_id:
            return rows
        matched = [row for row in rows if row.id == query_id or row.id.startswith(f"{query_id}:")]
        return matched or rows

    edition_queries_run: list[DiscoveryHit] = []
    # Run the same stack, then search unique qualifying hits.
    if window not in LIVE_WINDOWS:
        return None
    provider_list = list(providers)
    retrieve = retrieve_window_for(window)
    queries = only_query([row.with_window(retrieve) for row in week_queries()])
    raw: list[DiscoveryHit] = []
    found_by: dict[str, set[str]] = {}
    telemetry: dict[str, dict[str, int]] = {}
    failures: list[dict[str, str]] = []
    for provider in provider_list:
        _run_provider_queries(provider, queries, raw=raw, found_by=found_by, telemetry=telemetry, failures=failures)
    if specialist_provider is not None and (not query_id or str(query_id).startswith("feed:")):
        feed_rows = week_specialist_feed_queries()
        if query_id:
            feed_rows = [row for row in feed_rows if row.id == query_id or query_id.startswith(row.id)]
        _run_provider_queries(
            specialist_provider, feed_rows, raw=raw, found_by=found_by, telemetry=telemetry, failures=failures
        )
    if catch_net_provider is not None and not query_id:
        selected = week_catch_net_queries(queries)
        _run_provider_queries(
            catch_net_provider, selected, raw=raw, found_by=found_by, telemetry=telemetry, failures=failures
        )
    index = _qualify_corpus(entities=entities, varieties=varieties, sources=sources)
    _qualify_raw(raw, index=index, window=window, today=datetime.now(timezone.utc).date())
    edition_queries_run = [hit for hit in unique_hits(raw) if hit.qualifying]
    for hit in edition_queries_run:
        if (hit.origin_publisher_url or hit.url) == url:
            return hit
    return None


# --- "What should I know this week?" from displayed public results only ---

_BRIEF_SCHEMA = {
    "type": "object",
    "properties": {
        "statements": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "source_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["text", "source_ids"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["statements"],
    "additionalProperties": False,
}

_BRIEF_INSTRUCTIONS = (
    "You are drafting a short weekly intelligence briefing on the global berry industry "
    "(blueberry, strawberry, raspberry, blackberry) for an internal strategy team. "
    "You may state ONLY what is directly supported by the numbered public news items below -- "
    "never add outside knowledge, never speculate, never invent a fact, date, or figure not "
    "present in them. Cover the biggest developments, regional movement, competitor moves, "
    "and genetics/variety news only when the items support it. Every statement's source_ids "
    "must reference one or more of the ids listed below. If the items do not support a "
    "substantive briefing, return an empty statements array."
)


@dataclass(frozen=True)
class BriefStatement:
    text: str
    source_ids: tuple[str, ...]


def _digest_line(item_id: str, item: WeekItem) -> str:
    parts = [item_id, item.title, item.publisher, item.published_date or "date unknown"]
    if item.snippet:
        parts.append(item.snippet[:200])
    return " | ".join(str(part) for part in parts if part)[:320]


def generate_week_brief(
    items: list[WeekItem],
    *,
    completer: Callable[..., Any] | None,
    model: str = "anthropic/claude-haiku-4-5",
) -> tuple[BriefStatement, ...]:
    """`items` must be the display-ready result set already shown on the page."""
    if completer is None or not items:
        return ()
    indexed = {f"live-{i}": item for i, item in enumerate(items[:25])}
    digest = [_digest_line(item_id, item) for item_id, item in indexed.items()]
    prompt = (
        f"{_BRIEF_INSTRUCTIONS}\n\nNumbered public items (id | title | publisher | date | snippet):\n"
        + "\n".join(f"- {line}" for line in digest)
    )
    try:
        result = completer(prompt, schema=_BRIEF_SCHEMA, model=model, max_output_tokens=700)
    except Exception:  # noqa: BLE001 -- synthesis failure must not break the live page
        return ()
    statements: list[BriefStatement] = []
    for row in result.parsed.get("statements") or []:
        text = str(row.get("text") or "").strip()
        raw_ids = [str(source_id) for source_id in (row.get("source_ids") or [])]
        valid_ids = tuple(source_id for source_id in raw_ids if source_id in indexed)
        if text and valid_ids:
            statements.append(BriefStatement(text=text, source_ids=valid_ids))
    return tuple(statements)
