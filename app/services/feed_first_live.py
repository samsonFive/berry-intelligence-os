"""Same-day live acquisition for the feed-first Today surface.

Keyless lanes: Google News RSS (when:1d) and specialist / official site RSS.
Keyed request-time lanes when canonical names resolve: Perplexity Search,
Exa, and APITube. Prefer ``EXA_API_KEY`` / ``APITUBE_API_KEY`` /
``PERPLEXITY_API_KEY``. NewsCatcher CatchAll is never request-time on Today.

Hits become LIVE / UNREVIEWED feed records only when ``published_date``
equals the product UTC calendar day. Undated hits are dropped. Stored
published evidence is never a fallback.

Does not write ``data/evidence``. Inbox cache is date-keyed so yesterday
cannot be served as today. Do not poll the 151-row seed one company at a time.
"""

from __future__ import annotations

import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

from app.services.article_dedup import normalize_canonical_url
from app.services.clock import utc_today
from app.services.industry_pulse.dedup import dedupe_hits, unique_hits
from app.services.industry_pulse.apitube import ApiTubeSearchProvider
from app.services.industry_pulse.credentials import has_apitube, has_exa, has_perplexity
from app.services.industry_pulse.exa import ExaSearchProvider
from app.services.industry_pulse.matrix import (
    ALL_BERRIES_TERMS,
    BERRIES,
    BERRY_IDS,
    BERRY_TERMS,
    GEO_EDITIONS,
    PULSE_TOPICS,
    PulseQuery,
)
from app.services.industry_pulse.models import DiscoveryHit
from app.services.industry_pulse.perplexity_provider import PerplexitySearchProvider
from app.services.industry_pulse.providers import DiscoveryProvider, GoogleNewsRssProvider
from app.services.industry_pulse.qualify import QualificationIndex, qualify_hit
from app.services.industry_pulse.run import names_from_entities
from app.services.industry_pulse.specialist_feeds import (
    WEEK_SPECIALIST_FEEDS,
    SpecialistRssProvider,
    week_specialist_feed_queries,
)
from app.services.recall_audit.classify import hostname
from app.services.today_relevance import apply_today_relevance, collapse_story_clusters

CACHE_SUBDIR = "feed_first_live"
CACHE_TTL = timedelta(minutes=15)
LIVE_LANE_GOOGLE = "google_news_rss"
LIVE_LANE_SPECIALIST = "specialist_rss"
LIVE_LANE_PERPLEXITY = "perplexity"
LIVE_LANE_EXA = "exa"
LIVE_LANE_APITUBE = "apitube"
TRUST_LIVE = "LIVE"
REVIEW_UNREVIEWED = "UNREVIEWED"

OFFICIAL_HOSTS = {
    "hortifrut.com",
    "berries.net.au",
    "britishberrygrowers.org.uk",
}

_CROP_MARKERS = (
    ("blueberry", "berry-blueberry"),
    ("blueberries", "berry-blueberry"),
    ("strawberry", "berry-strawberry"),
    ("strawberries", "berry-strawberry"),
    ("raspberry", "berry-raspberry"),
    ("raspberries", "berry-raspberry"),
    ("blackberry", "berry-blackberry"),
    ("blackberries", "berry-blackberry"),
    ("arándano", "berry-blueberry"),
    ("arandano", "berry-blueberry"),
    ("fresa", "berry-strawberry"),
    ("frambuesa", "berry-raspberry"),
    ("zarzamora", "berry-blackberry"),
)

_NAME_MIN = 4
_STOCK_BLACKBERRY = re.compile(
    r"\b(price target|nasdaq|nyse|shares|equity|stock quote|analyst rating)\b",
    re.IGNORECASE,
)
_FRUIT_BLACKBERRY = re.compile(
    r"\b(caneberr\w*|cultivar|grower|harvest|fruit|primocane|nursery|seedless)\b",
    re.IGNORECASE,
)


def live_disclosure(bundle: dict[str, Any]) -> str:
    lanes = ", ".join(bundle.get("lanes") or []) or "none"
    fetched = bundle.get("fetched_at") or "not fetched"
    errors = bundle.get("lane_errors") or []
    err = f" Lane errors: {len(errors)}." if errors else ""
    unused: list[str] = []
    present = set(bundle.get("lanes") or [])
    if LIVE_LANE_EXA not in present:
        unused.append("Exa")
    if LIVE_LANE_APITUBE not in present:
        unused.append("APITube")
    if LIVE_LANE_PERPLEXITY not in present:
        unused.append("Perplexity")
    unused_note = ""
    if unused:
        unused_note = f" {', '.join(unused)} stay unused until those keys exist."
    return (
        f"LIVE / UNREVIEWED same-day acquisition ({lanes}). "
        f"Only items whose published_date equals {bundle.get('today')} "
        f"(product UTC clock). Fetched {fetched}. "
        f"The stored August corpus is unused here.{err} "
        "Social platforms are not collected. "
        "NewsCatcher CatchAll is not request-time on Today."
        f"{unused_note}"
    )


def cache_path(inbox_dir: Path, today: date) -> Path:
    return Path(inbox_dir) / CACHE_SUBDIR / f"{today.isoformat()}.json"


def is_same_calendar_day(published: str | None, today: date) -> bool:
    if not published:
        return False
    try:
        when = date.fromisoformat(str(published).strip()[:10])
    except ValueError:
        return False
    return when == today


def today_google_queries() -> list[PulseQuery]:
    """Four berry × global Google News rows with when:1d. Not the Pulse 32."""
    edition = GEO_EDITIONS["global"]
    rows: list[PulseQuery] = []
    for berry in BERRIES:
        rows.append(
            PulseQuery(
                id=f"today:{berry}:global",
                text=f"{BERRY_TERMS[berry]} ({PULSE_TOPICS})",
                berry=berry,
                geography="global",
                topic="industry_pulse",
                kind="today_berry",
                hl=edition["hl"],
                gl=edition["gl"],
                ceid=edition["ceid"],
            ).with_window("24h")
        )
    return rows


def today_keyed_queries() -> list[PulseQuery]:
    """Bounded same-day catch-net for Exa / APITube. Not a 151-entity loop."""
    return today_perplexity_queries()[:2]


def today_perplexity_queries() -> list[PulseQuery]:
    """Bounded same-day catch-net. Not the Pulse 20 and not a doubled matrix."""
    global_edition = GEO_EDITIONS["global"]
    americas = GEO_EDITIONS["americas"]
    rows = [
        PulseQuery(
            id="today:perplexity:all:global",
            text=f"({ALL_BERRIES_TERMS}) ({PULSE_TOPICS})",
            berry=None,
            geography="global",
            topic="industry_pulse",
            kind="today_catch_net",
            hl=global_edition["hl"],
            gl=global_edition["gl"],
            ceid=global_edition["ceid"],
        ).with_window("24h")
    ]
    for berry in ("blueberry", "strawberry"):
        rows.append(
            PulseQuery(
                id=f"today:perplexity:{berry}:americas",
                text=f"{BERRY_TERMS[berry]} {americas['terms']} ({PULSE_TOPICS})",
                berry=berry,
                geography="americas",
                topic="industry_pulse",
                kind="today_catch_net",
                hl=americas["hl"],
                gl=americas["gl"],
                ceid=americas["ceid"],
            ).with_window("24h")
        )
    return rows


def live_item_id(url: str) -> str:
    key = normalize_canonical_url(url) or url.strip()
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    return f"live-{digest}"


def match_entity_ids(text: str, entities: Iterable[dict[str, Any]]) -> list[str]:
    hay = (text or "").casefold()
    found: list[str] = []
    for entity in entities:
        entity_id = str(entity.get("id") or "")
        if not entity_id or entity_id in found:
            continue
        names = [entity.get("name"), *(entity.get("aliases") or [])]
        for raw in names:
            name = str(raw or "").strip()
            if len(name) < _NAME_MIN:
                continue
            if name.casefold() in hay:
                found.append(entity_id)
                break
    return found


def berry_ids_for(hit: DiscoveryHit) -> list[str]:
    found: list[str] = []
    if hit.berry and hit.berry in BERRY_IDS:
        found.append(BERRY_IDS[hit.berry])
    hay = f"{hit.title} {hit.snippet}".casefold()
    for marker, berry_id in _CROP_MARKERS:
        if marker in hay and berry_id not in found:
            found.append(berry_id)
    return found


def _is_blackberry_stock(hit: DiscoveryHit) -> bool:
    text = f"{hit.title} {hit.snippet}"
    if "blackberry" not in text.casefold():
        return False
    return bool(_STOCK_BLACKBERRY.search(text) and not _FRUIT_BLACKBERRY.search(text))


def source_type_for(hit: DiscoveryHit, *, official: set[str] | None = None) -> str:
    host = (hit.source_domain or hostname(hit.origin_publisher_url or hit.url) or "").lower().removeprefix("www.")
    known = OFFICIAL_HOSTS | (official or set())
    if host in known:
        return "company_website"
    if hit.provider == LIVE_LANE_SPECIALIST:
        return "trade_press"
    return "news_search"


def hit_to_record(
    hit: DiscoveryHit,
    *,
    entities: Iterable[dict[str, Any]],
    today: date,
    official_hosts: set[str] | None = None,
    people: Iterable[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    url = hit.origin_publisher_url or hit.url
    text = f"{hit.title} {hit.snippet}"
    entity_ids = match_entity_ids(text, entities)
    from app.services.people_watchlist import match_people

    person_ids = [row["id"] for row in match_people(text, people or [])]
    snippet = (hit.snippet or "").strip()
    return {
        "id": live_item_id(url),
        "status": "published",
        "trust_state": TRUST_LIVE,
        "review_state": REVIEW_UNREVIEWED,
        "acquisition_lane": hit.provider,
        "live": True,
        "title": hit.title,
        "summary": snippet,
        "source_name": hit.origin_publisher_name or hit.source_domain or "Unknown source",
        "source_type": source_type_for(hit, official=official_hosts),
        "source_url": url,
        "published_date": str(hit.published_date or "")[:10],
        "captured_date": today.isoformat(),
        "berry_ids": berry_ids_for(hit),
        "entity_ids": entity_ids,
        "person_ids": person_ids,
        "geography_ids": [],
        "tags": ["live", "unreviewed"],
        "publisher_description": snippet,
        "qualify_reason": hit.qualify_reason,
        "editorial_topic": hit.editorial_topic,
        "discovery_provenance": {
            "provider": hit.provider,
            "query_id": hit.query_id,
            "wrapper_url": hit.wrapper_url,
        },
    }


def empty_bundle(today: date, *, fetched_at: str | None = None) -> dict[str, Any]:
    return {
        "today": today.isoformat(),
        "fetched_at": fetched_at,
        "lanes": [LIVE_LANE_GOOGLE, LIVE_LANE_SPECIALIST],
        "lane_errors": [],
        "stats": {
            "discovered": 0,
            "qualified": 0,
            "same_day": 0,
            "dropped_not_today": 0,
            "dropped_undated": 0,
            "dropped_unqualified": 0,
        },
        "records": [],
    }


def _discover_one(provider: DiscoveryProvider, query: PulseQuery) -> tuple[list[DiscoveryHit], dict[str, str] | None]:
    try:
        return list(provider.discover(query)), None
    except Exception as exc:  # noqa: BLE001 — one query must not abort Today
        return [], {
            "query_id": query.id,
            "provider": getattr(provider, "name", "unknown"),
            "error": f"{type(exc).__name__}: {exc}",
        }


def _run_lane(
    provider: DiscoveryProvider,
    queries: list[PulseQuery],
    *,
    workers: int = 8,
) -> tuple[list[DiscoveryHit], list[dict[str, str]]]:
    if not queries:
        return [], []
    hits: list[DiscoveryHit] = []
    errors: list[dict[str, str]] = []
    max_workers = min(workers, len(queries))
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(_discover_one, provider, query) for query in queries]
        for future in as_completed(futures):
            batch, error = future.result()
            hits.extend(batch)
            if error:
                errors.append(error)
    return hits, errors


def _resolve_keyed_provider(
    provider: DiscoveryProvider | None,
    *,
    enable: bool | None,
    available: bool,
    factory,
) -> DiscoveryProvider | None:
    if provider is not None:
        return provider
    if enable is False:
        return None
    if enable is True or available:
        return factory()
    return None


def _resolve_perplexity(
    provider: DiscoveryProvider | None,
    *,
    today: date,
    enable: bool | None,
) -> DiscoveryProvider | None:
    return _resolve_keyed_provider(
        provider,
        enable=enable,
        available=has_perplexity(),
        factory=lambda: PerplexitySearchProvider(today=today),
    )


def collect_same_day_hits(
    *,
    google_provider: DiscoveryProvider | None = None,
    specialist_provider: DiscoveryProvider | None = None,
    perplexity_provider: DiscoveryProvider | None = None,
    exa_provider: DiscoveryProvider | None = None,
    apitube_provider: DiscoveryProvider | None = None,
    enable_perplexity: bool | None = None,
    enable_exa: bool | None = None,
    enable_apitube: bool | None = None,
    entities: list[dict[str, Any]] | None = None,
    sources: list[dict[str, Any]] | None = None,
    today: date | None = None,
) -> tuple[list[DiscoveryHit], dict[str, Any]]:
    today = today or utc_today()
    google_provider = google_provider or GoogleNewsRssProvider()
    specialist_provider = specialist_provider or SpecialistRssProvider()
    perplexity_provider = _resolve_perplexity(
        perplexity_provider, today=today, enable=enable_perplexity
    )
    exa_provider = _resolve_keyed_provider(
        exa_provider,
        enable=enable_exa,
        available=has_exa(),
        factory=lambda: ExaSearchProvider(today=today),
    )
    apitube_provider = _resolve_keyed_provider(
        apitube_provider,
        enable=enable_apitube,
        available=has_apitube(),
        factory=lambda: ApiTubeSearchProvider(today=today),
    )
    entities = entities or []
    sources = sources or []

    google_hits, google_errors = _run_lane(google_provider, today_google_queries())
    specialist_hits, specialist_errors = _run_lane(
        specialist_provider,
        week_specialist_feed_queries(),
    )
    perplexity_hits, perplexity_errors = ([], [])
    if perplexity_provider is not None:
        perplexity_hits, perplexity_errors = _run_lane(
            perplexity_provider,
            today_perplexity_queries(),
            workers=3,
        )
    exa_hits, exa_errors = ([], [])
    if exa_provider is not None:
        exa_hits, exa_errors = _run_lane(exa_provider, today_keyed_queries(), workers=2)
    apitube_hits, apitube_errors = ([], [])
    if apitube_provider is not None:
        apitube_hits, apitube_errors = _run_lane(
            apitube_provider, today_keyed_queries(), workers=2
        )
    raw = [*google_hits, *specialist_hits, *perplexity_hits, *exa_hits, *apitube_hits]
    company_names = names_from_entities(entities, prefix="company-")
    variety_names = names_from_entities(entities, prefix="variety-")
    index = QualificationIndex.compile(
        company_names=company_names,
        variety_names=variety_names,
        sources=sources,
    )
    qualified_rows = [qualify_hit(hit, index=index) for hit in raw]
    relevant, dropped_today_noise = apply_today_relevance(qualified_rows, entities=entities)
    deduped = unique_hits(dedupe_hits(relevant))

    same_day: list[DiscoveryHit] = []
    dropped_not_today = 0
    dropped_undated = 0
    dropped_unqualified = 0
    for hit in deduped:
        if not hit.qualifying or _is_blackberry_stock(hit):
            dropped_unqualified += 1
            continue
        if not hit.published_date:
            dropped_undated += 1
            continue
        if not is_same_calendar_day(hit.published_date, today):
            dropped_not_today += 1
            continue
        same_day.append(hit)

    stats = {
        "discovered": len(raw),
        "qualified": sum(1 for hit in deduped if hit.qualifying),
        "same_day": len(same_day),
        "dropped_not_today": dropped_not_today,
        "dropped_undated": dropped_undated,
        "dropped_unqualified": dropped_unqualified + dropped_today_noise,
        "dropped_today_noise": dropped_today_noise,
    }
    lanes = [
        getattr(google_provider, "name", LIVE_LANE_GOOGLE),
        getattr(specialist_provider, "name", LIVE_LANE_SPECIALIST),
    ]
    if perplexity_provider is not None:
        lanes.append(getattr(perplexity_provider, "name", LIVE_LANE_PERPLEXITY))
    if exa_provider is not None:
        lanes.append(getattr(exa_provider, "name", LIVE_LANE_EXA))
    if apitube_provider is not None:
        lanes.append(getattr(apitube_provider, "name", LIVE_LANE_APITUBE))
    meta = {
        "today": today.isoformat(),
        "lanes": lanes,
        "lane_errors": [
            *google_errors,
            *specialist_errors,
            *perplexity_errors,
            *exa_errors,
            *apitube_errors,
        ],
        "stats": stats,
        "specialist_feed_count": len(WEEK_SPECIALIST_FEEDS),
        "perplexity_enabled": perplexity_provider is not None,
        "exa_enabled": exa_provider is not None,
        "apitube_enabled": apitube_provider is not None,
    }
    return same_day, meta


def _cache_fresh(payload: dict[str, Any], *, today: date, now: datetime) -> bool:
    if str(payload.get("today") or "") != today.isoformat():
        return False
    fetched = str(payload.get("fetched_at") or "")
    if not fetched:
        return False
    try:
        stamp = datetime.fromisoformat(fetched)
    except ValueError:
        return False
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=UTC)
    return now - stamp <= CACHE_TTL


def load_cached_bundle(inbox_dir: Path, *, today: date | None = None) -> dict[str, Any] | None:
    today = today or utc_today()
    path = cache_path(inbox_dir, today)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if str(payload.get("today") or "") != today.isoformat():
        return None
    return payload


def save_bundle(inbox_dir: Path, bundle: dict[str, Any]) -> Path:
    today = date.fromisoformat(str(bundle["today"]))
    path = cache_path(inbox_dir, today)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(bundle, indent=2) + "\n", encoding="utf-8")
    return path


def cached_live_records(inbox_dir: Path, *, today: date | None = None) -> list[dict[str, Any]]:
    bundle = load_cached_bundle(inbox_dir, today=today)
    if not bundle:
        return []
    rows = bundle.get("records") or []
    return [row for row in rows if isinstance(row, dict)]


def merge_decision_records(
    stored: list[dict[str, Any]],
    live: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Live ids win. Used only for thumbs/extract lookup, not the Today corpus."""
    by_id = {str(row.get("id")): row for row in stored if row.get("id")}
    for row in live:
        item_id = str(row.get("id") or "")
        if item_id:
            by_id[item_id] = row
    return list(by_id.values())


def live_feed_bundle(
    *,
    inbox_dir: Path,
    entities: list[dict[str, Any]] | None = None,
    sources: list[dict[str, Any]] | None = None,
    refresh: bool = False,
    today: date | None = None,
    now: datetime | None = None,
    google_provider: DiscoveryProvider | None = None,
    specialist_provider: DiscoveryProvider | None = None,
    perplexity_provider: DiscoveryProvider | None = None,
    exa_provider: DiscoveryProvider | None = None,
    apitube_provider: DiscoveryProvider | None = None,
    enable_perplexity: bool | None = None,
    enable_exa: bool | None = None,
    enable_apitube: bool | None = None,
    official_hosts: set[str] | None = None,
    people: list[dict[str, Any]] | None = None,
    enrich_lead: bool = False,
) -> dict[str, Any]:
    today = today or utc_today()
    now = now or datetime.now(UTC)
    if not refresh:
        cached = load_cached_bundle(inbox_dir, today=today)
        if cached and _cache_fresh(cached, today=today, now=now):
            return cached

    hits, meta = collect_same_day_hits(
        google_provider=google_provider,
        specialist_provider=specialist_provider,
        perplexity_provider=perplexity_provider,
        exa_provider=exa_provider,
        apitube_provider=apitube_provider,
        enable_perplexity=enable_perplexity,
        enable_exa=enable_exa,
        enable_apitube=enable_apitube,
        entities=entities,
        sources=sources,
        today=today,
    )
    records = collapse_story_clusters(
        [
            hit_to_record(
                hit,
                entities=entities or [],
                today=today,
                official_hosts=official_hosts,
                people=people,
            )
            for hit in hits
        ]
    )
    if enrich_lead and records:
        from app.services.feed_first_reader import capture_item, merge_capture

        lead = merge_capture(records[0], capture_item(inbox_dir, records[0]))
        records[0] = lead
    bundle = {
        **empty_bundle(today, fetched_at=now.isoformat(timespec="seconds")),
        **meta,
        "fetched_at": now.isoformat(timespec="seconds"),
        "records": records,
    }
    save_bundle(inbox_dir, bundle)
    return bundle
