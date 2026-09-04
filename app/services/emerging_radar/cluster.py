"""Explainable Development clustering. Machinery, not the product.

Merge when canonical entities, event type, date proximity, and headline
concepts agree. Semantic similarity may propose a cluster; it must not
silently merge ambiguous developments. Syndicated copies stay on the
Development but do not count as independent corroboration.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date, datetime, timezone
from typing import Any, Iterable
from urllib.parse import urlparse

from app.services.article_dedup import normalize_title
from app.services.emerging_radar.models import (
    WEAK_SIGNAL_LABEL,
    Development,
    EvolutionEvent,
    SourceRef,
)
from app.services.industry_pulse.matrix import BERRY_IDS
from app.services.industry_pulse.models import DiscoveryHit
from app.services.industry_pulse.qualify import SOURCE_BREEDER, SOURCE_COMPANY, SOURCE_GOV_AG
from app.services.recall_audit.classify import hostname
from app.services.source_independence import _jaccard, _tokens

EVENT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("LEADERSHIP", re.compile(r"\b(ceo|appoints?|appointed|resigns?|chairman|managing director)\b", re.I)),
    ("LICENSING", re.compile(r"\b(licen[cs]e[ds]?|licensing|royalt(?:y|ies)|managed variet)\b", re.I)),
    ("PARTNERSHIP", re.compile(r"\b(partnership|joint venture|collaborat\w+|alliance|mou)\b", re.I)),
    ("VARIETY_LAUNCH", re.compile(r"\b(launches?|unveils?|introduces?|debuts?|new (?:variety|cultivar)|releases? a)\b", re.I)),
    ("GENETICS_INNOVATION", re.compile(r"\b(seedless|crispr|gene-?edit\w*|shelf[- ]life|disease resist\w*|breeding program|genetics)\b", re.I)),
    ("PRODUCTION_EXPANSION", re.compile(r"\b(expansion|new farm|hectares?|acres?|packing (?:plant|facility)|greenhouse|glasshouse|controlled[- ]environment)\b", re.I)),
    ("MARKET_ACCESS", re.compile(r"\b(market access|phytosanitary|protocol|export approval|opens? .*market)\b", re.I)),
    ("PBR", re.compile(r"\b(PBR|PVP|PVPO|CPVO|plant breeders? rights|plant variety protection)\b", re.I)),
    ("PATENT", re.compile(r"\b(USPTO|plant patent|patent(?:s|ed)?|WO20|US20)\b", re.I)),
    ("REGULATORY", re.compile(r"\b(regulat\w+|mrl|residue|recall|tariff|duty)\b", re.I)),
    ("LEGAL", re.compile(r"\b(lawsuit|litigation|injunct\w+|settlement|court)\b", re.I)),
    ("SUPPLY_CHANGE", re.compile(r"\b(shortage|oversupply|shortfall|frost|crop loss|volumes? (?:up|down)|harvest delay)\b", re.I)),
    ("RETAIL_PROGRAM", re.compile(r"\b(retail(?:er)?|supermarket|tesco|walmart|costco|exclusive program|private label)\b", re.I)),
    ("RESEARCH", re.compile(r"\b(university|trial|extension|journal|doi:|research station)\b", re.I)),
)

COUNTRY_GEOGRAPHY: tuple[tuple[re.Pattern[str], str, str], ...] = (
    (re.compile(r"\bPeru(?:vian)?\b", re.I), "geography-peru", "Peru"),
    (re.compile(r"\bChile(?:an)?\b", re.I), "geography-chile", "Chile"),
    (re.compile(r"\bMexico|Mexican\b", re.I), "geography-mexico", "Mexico"),
    (re.compile(r"\bSpain|Spanish\b", re.I), "geography-spain", "Spain"),
    (re.compile(r"\bChina|Chinese\b", re.I), "geography-china", "China"),
    (re.compile(r"\bUnited States|\bUSA\b|\bU\.S\.A?\.?\b|\bCalifornia\b|\bFlorida\b", re.I), "geography-united-states", "United States"),
    (re.compile(r"\bNetherlands|Dutch\b", re.I), "geography-netherlands", "Netherlands"),
    (re.compile(r"\bMorocco|Maroc\b", re.I), "geography-morocco", "Morocco"),
    (re.compile(r"\bSouth Africa|South African\b", re.I), "geography-south-africa", "South Africa"),
    (re.compile(r"\bAustralia|Tasmania\b", re.I), "geography-australia", "Australia"),
    (re.compile(r"\bUnited Kingdom|\bBritain\b|\bEngland\b|\bUK\b", re.I), "geography-united-kingdom", "United Kingdom"),
    (re.compile(r"\bUkraine|Ukrainian\b", re.I), "geography-ukraine", "Ukraine"),
    (re.compile(r"\bPoland|Polish\b", re.I), "geography-poland", "Poland"),
    (re.compile(r"\bPortugal|Portuguese\b", re.I), "geography-portugal", "Portugal"),
    (re.compile(r"\bGermany|German\b", re.I), "geography-germany", "Germany"),
    (re.compile(r"\bJapan|Japanese\b", re.I), "geography-japan", "Japan"),
    (re.compile(r"\bIndia|Indian\b", re.I), "geography-india", "India"),
    (re.compile(r"\bCanada|Canadian\b", re.I), "geography-canada", "Canada"),
    (re.compile(r"\bBrazil|Brazilian\b", re.I), "geography-brazil", "Brazil"),
    (re.compile(r"\bNew Zealand\b", re.I), "geography-new-zealand", "New Zealand"),
)

BERRY_LABELS = {
    "berry-blueberry": "Blueberry",
    "berry-strawberry": "Strawberry",
    "berry-raspberry": "Raspberry",
    "berry-blackberry": "Blackberry",
}

SOCIAL_HOSTS = frozenset({"linkedin.com", "www.linkedin.com", "x.com", "twitter.com", "www.twitter.com", "facebook.com", "www.facebook.com"})
AGGREGATOR_HOSTS = frozenset(
    {
        "news.google.com",
        "msn.com",
        "www.msn.com",
        "news.yahoo.com",
        "apple.news",
        "flipboard.com",
        "news.bing.com",
    }
)
REGISTRY_HOSTS = frozenset(
    {
        "cpvo.europa.eu",
        "www.cpvo.europa.eu",
        "uspto.gov",
        "patents.google.com",
        "ams.usda.gov",
        "www.ams.usda.gov",
    }
)
DATE_WINDOW_DAYS = 21
MERGE_TITLE_JACCARD = 0.45
SYNDICATION_TITLE_JACCARD = 0.75
PROPOSE_TITLE_JACCARD = 0.32
STOP_CONCEPT = {
    "with", "from", "that", "this", "have", "will", "their", "about", "into",
    "over", "after", "berry", "berries", "new", "says", "said",
}


def classify_event_type(text: str) -> str:
    for event_type, pattern in EVENT_PATTERNS:
        if pattern.search(text or ""):
            return event_type
    return "OTHER"


def _registrable(host: str) -> str:
    folded = (host or "").lower().removeprefix("www.")
    parts = folded.split(".")
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return folded


def is_social_profile_url(url: str) -> bool:
    folded = (url or "").lower()
    if "linkedin.com/posts/" in folded or "linkedin.com/feed/" in folded:
        return False
    return any(marker in folded for marker in ("linkedin.com/in/", "linkedin.com/company/", "linkedin.com/school/"))


def is_social_host(host: str) -> bool:
    folded = (host or "").lower().removeprefix("www.")
    return folded in SOCIAL_HOSTS or folded.endswith(".linkedin.com")


def is_aggregator_host(host: str) -> bool:
    folded = (host or "").lower().removeprefix("www.")
    return folded in AGGREGATOR_HOSTS or _registrable(folded) in {"msn.com", "yahoo.com"}


def is_registry_host(host: str) -> bool:
    folded = (host or "").lower().removeprefix("www.")
    return folded in REGISTRY_HOSTS or folded.endswith(".gov") and any(
        marker in folded for marker in ("usda", "uspto", "cpvo")
    )


def concept_key(title: str) -> str:
    tokens = [token for token in sorted(_tokens(title)) if token not in STOP_CONCEPT][:6]
    return " ".join(tokens) or normalize_title(title)


def _parse_day(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _dates_close(left: str | None, right: str | None, *, days: int = DATE_WINDOW_DAYS) -> bool:
    a, b = _parse_day(left), _parse_day(right)
    if a is None or b is None:
        return True
    return abs((a - b).days) <= days


def _stable_id(parts: Iterable[str]) -> str:
    key = "|".join(part for part in parts if part)
    return "dev-" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


def is_publisher_home_url(url: str) -> bool:
    """RSS items sometimes carry the publisher homepage instead of the article."""
    path = (urlparse(url or "").path or "").strip("/")
    return not path


def _prior_matches_cluster(
    prior: Development,
    *,
    event_type: str,
    company_ids: tuple[str, ...],
    variety_ids: tuple[str, ...],
    concept: str,
) -> bool:
    if prior.event_type != event_type:
        return False
    if set(prior.company_ids) & set(company_ids):
        return True
    if set(prior.variety_ids) & set(variety_ids):
        return True
    return bool(concept) and concept_key(prior.title) == concept


# A geography name inside a parenthetical aside is disproportionately
# likely to describe a THIRD PARTY's nationality ("...together with Bloom
# Fresh (a Spanish firm that acquired 66% of the genetics business)...")
# rather than the development's own location -- a real, live production
# defect: "Inka's Berries operates a new blueberry packing plant in Ica"
# (a Peru story) was tagged geography-spain purely because its snippet
# named an unrelated Spanish co-investor parenthetically. An actual event
# location is overwhelmingly stated in the main clause ("expanding to
# Chile"), not parenthetically, so geography matching -- and only
# geography matching, not company/variety/berry -- runs against text with
# parenthetical content removed.
_PARENTHETICAL = re.compile(r"\([^()]*\)")


class EntityResolver:
    """Name → canonical IDs. Does not create entities."""

    def __init__(self, entities: Iterable[dict[str, Any]] = ()) -> None:
        self.companies: list[tuple[re.Pattern[str], str, str]] = []
        self.varieties: list[tuple[re.Pattern[str], str, str]] = []
        self.by_id: dict[str, dict[str, Any]] = {}
        for row in entities:
            row_id = str(row.get("id") or "")
            if row_id:
                self.by_id[row_id] = row
            names = [str(row.get("name") or "")]
            names.extend(str(alias) for alias in (row.get("aliases") or []) if alias)
            names = [name.strip() for name in names if len(str(name).strip()) >= 5]
            if not names:
                continue
            pattern = re.compile(r"\b(" + "|".join(re.escape(name) for name in sorted(set(names), key=len, reverse=True)) + r")\b", re.I)
            label = str(row.get("name") or row_id)
            entity_type = str(row.get("entity_type") or "")
            if row_id.startswith("company-") or entity_type == "company":
                self.companies.append((pattern, row_id, label))
            elif row_id.startswith("variety-") or entity_type == "variety":
                self.varieties.append((pattern, row_id, label))

    def resolve(self, text: str) -> dict[str, tuple[str, ...]]:
        company_ids: list[str] = []
        company_names: list[str] = []
        for pattern, row_id, label in self.companies:
            if pattern.search(text) and row_id not in company_ids:
                company_ids.append(row_id)
                company_names.append(label)
        variety_ids: list[str] = []
        variety_names: list[str] = []
        for pattern, row_id, label in self.varieties:
            if pattern.search(text) and row_id not in variety_ids:
                variety_ids.append(row_id)
                variety_names.append(label)
        geography_ids: list[str] = []
        geography_labels: list[str] = []
        geography_text = _PARENTHETICAL.sub(" ", text)
        for pattern, row_id, label in COUNTRY_GEOGRAPHY:
            if pattern.search(geography_text) and row_id not in geography_ids:
                geography_ids.append(row_id)
                geography_labels.append(label)
        berry_ids: list[str] = []
        berry_labels: list[str] = []
        folded = text.casefold()
        for slug, berry_id in BERRY_IDS.items():
            if slug in folded and berry_id not in berry_ids:
                berry_ids.append(berry_id)
                berry_labels.append(BERRY_LABELS[berry_id])
        return {
            "company_ids": tuple(company_ids),
            "company_names": tuple(company_names),
            "variety_ids": tuple(variety_ids),
            "variety_names": tuple(variety_names),
            "geography_ids": tuple(geography_ids),
            "geography_labels": tuple(geography_labels),
            "berry_ids": tuple(berry_ids),
            "berry_labels": tuple(berry_labels),
        }


def source_from_hit(hit: DiscoveryHit) -> SourceRef:
    host = hostname(hit.origin_publisher_url or hit.url) or (hit.source_domain or "")
    official = hit.source_context == SOURCE_GOV_AG
    company_claim = hit.source_context in {SOURCE_COMPANY, SOURCE_BREEDER}
    return SourceRef(
        url=hit.origin_publisher_url or hit.url,
        title=hit.title,
        publisher=str(hit.origin_publisher_name or host or "Unknown publisher"),
        domain=host,
        published_date=hit.published_date,
        provider=hit.provider,
        query_id=hit.query_id,
        snippet=hit.snippet or "",
        official=official,
        registry=is_registry_host(host),
        social=is_social_host(host),
        company_claim=company_claim,
        syndicated=is_aggregator_host(host),
    )


def _hit_day(hit: DiscoveryHit) -> str | None:
    return (hit.published_date or "")[:10] or None


def _should_merge(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if not _dates_close(left.get("event_date"), right.get("event_date")):
        return False
    shared_company = set(left["company_ids"]) & set(right["company_ids"])
    shared_variety = set(left["variety_ids"]) & set(right["variety_ids"])
    title_sim = _jaccard(_tokens(left["title"]), _tokens(right["title"]))
    same_concept = bool(left["concept"] and left["concept"] == right["concept"])
    overlap = _tokens(left["title"]) & _tokens(right["title"])
    if title_sim >= SYNDICATION_TITLE_JACCARD:
        return True
    # Same real-world thing: canonical actor + overlapping headline facts.
    # Event-type labels may differ (license vs seedless innovation).
    if (shared_company or shared_variety) and (len(overlap) >= 3 or same_concept or title_sim >= 0.30):
        return True
    if left["event_type"] != right["event_type"]:
        return False
    if shared_variety and (title_sim >= 0.30 or same_concept):
        return True
    if shared_company and (title_sim >= 0.30 or same_concept):
        return True
    if shared_company and shared_variety:
        return True
    return False


def _should_propose(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if left["event_type"] != right["event_type"]:
        return False
    if _should_merge(left, right):
        return False
    if not _dates_close(left.get("event_date"), right.get("event_date"), days=14):
        return False
    title_sim = _jaccard(_tokens(left["title"]), _tokens(right["title"]))
    return PROPOSE_TITLE_JACCARD <= title_sim < MERGE_TITLE_JACCARD


def _union_find_merge(rows: list[dict[str, Any]]) -> list[list[int]]:
    parent = list(range(len(rows)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for i, left in enumerate(rows):
        for j in range(i + 1, len(rows)):
            if _should_merge(left, rows[j]):
                union(i, j)
    groups: dict[int, list[int]] = {}
    for i in range(len(rows)):
        groups.setdefault(find(i), []).append(i)
    return list(groups.values())


def corroboration_shape(sources: list[SourceRef]) -> tuple[str, int]:
    independent: list[SourceRef] = []
    seen_reg: set[str] = set()
    for source in sources:
        if source.syndicated or is_aggregator_host(source.domain) or source.social:
            continue
        key = _registrable(source.domain)
        if not key or key in seen_reg:
            continue
        seen_reg.add(key)
        independent.append(source)
    if not independent:
        if sources and all(source.social or source.syndicated for source in sources):
            return WEAK_SIGNAL_LABEL, 0
        return "ONE SOURCE", 1 if sources else 0
    has_official = any(source.official for source in independent)
    has_registry = any(source.registry for source in independent)
    has_claim = any(source.company_claim for source in independent)
    has_press = any(
        not source.official and not source.registry and not source.social and not source.company_claim
        for source in independent
    )
    has_independent_report = any(not source.company_claim and not source.social for source in independent)
    if has_registry and has_press:
        return "REGISTRY + PRESS", len(independent)
    if has_official and has_press:
        return "OFFICIAL + PRESS", len(independent)
    if has_claim and has_independent_report and len(independent) >= 2:
        return "COMPANY CLAIM + INDEPENDENT REPORT", len(independent)
    if len(independent) >= 2:
        return "MULTIPLE INDEPENDENT SOURCES", len(independent)
    return "ONE SOURCE", max(len(independent), 1 if sources else 0)


def _what_happened(title: str, event_type: str, names: tuple[str, ...]) -> str:
    who = ", ".join(names[:3])
    if who:
        return f"{who}: {title}".strip()
    label = event_type.replace("_", " ").title()
    return f"{label}: {title}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def cluster_hits(
    hits: Iterable[DiscoveryHit],
    *,
    entities: Iterable[dict[str, Any]] = (),
    previous: Iterable[Development] = (),
    now: datetime | None = None,
) -> list[Development]:
    """Cluster qualifying hits into Developments. Conservative merge."""
    now = now or datetime.now(timezone.utc)
    captured = now.isoformat(timespec="seconds")
    resolver = EntityResolver(entities)
    rows: list[dict[str, Any]] = []
    for hit in hits:
        if hit.duplicate_of or not hit.qualifying:
            continue
        if is_social_profile_url(hit.origin_publisher_url or hit.url):
            continue
        text = f"{hit.title} {hit.snippet}"
        resolved = resolver.resolve(text)
        event_type = classify_event_type(text)
        rows.append(
            {
                "hit": hit,
                "title": hit.title,
                "event_type": event_type,
                "event_date": _hit_day(hit),
                "concept": concept_key(hit.title),
                **resolved,
            }
        )
    if not rows:
        return []

    groups = _union_find_merge(rows)
    proposed: dict[int, set[int]] = {i: set() for i in range(len(groups))}
    for i, group in enumerate(groups):
        sample_i = rows[group[0]]
        for j in range(i + 1, len(groups)):
            sample_j = rows[groups[j][0]]
            if _should_propose(sample_i, sample_j):
                proposed[i].add(j)
                proposed[j].add(i)

    previous_by_url: dict[str, Development] = {}
    previous_by_id: dict[str, Development] = {}
    for item in previous:
        previous_by_id[item.id] = item
        for url in item.live_hit_urls:
            if url and not is_publisher_home_url(url):
                previous_by_url[url] = item

    developments: list[Development] = []
    pending_ids: list[str] = []
    used_ids: set[str] = set()
    for index, members in enumerate(groups):
        clustered = [rows[i] for i in members]
        hits_in = [row["hit"] for row in clustered]
        sources = [source_from_hit(hit) for hit in hits_in]
        urls = tuple(dict.fromkeys(source.url for source in sources))
        event_type = clustered[0]["event_type"]
        company_ids = tuple(dict.fromkeys(cid for row in clustered for cid in row["company_ids"]))
        variety_ids = tuple(dict.fromkeys(vid for row in clustered for vid in row["variety_ids"]))
        geography_ids = tuple(dict.fromkeys(gid for row in clustered for gid in row["geography_ids"]))
        berry_ids = tuple(dict.fromkeys(bid for row in clustered for bid in row["berry_ids"]))
        company_names = tuple(dict.fromkeys(name for row in clustered for name in row["company_names"]))
        variety_names = tuple(dict.fromkeys(name for row in clustered for name in row["variety_names"]))
        geography_labels = tuple(dict.fromkeys(name for row in clustered for name in row["geography_labels"]))
        berry_labels = tuple(dict.fromkeys(name for row in clustered for name in row["berry_labels"]))
        concept = clustered[0]["concept"]
        new_id = _stable_id((event_type, ",".join(company_ids), ",".join(variety_ids), concept))
        prior = previous_by_id.get(new_id)
        if prior is None:
            for url in urls:
                if is_publisher_home_url(url):
                    continue
                candidate = previous_by_url.get(url)
                if candidate is None:
                    continue
                if _prior_matches_cluster(
                    candidate,
                    event_type=event_type,
                    company_ids=company_ids,
                    variety_ids=variety_ids,
                    concept=concept,
                ):
                    prior = candidate
                    new_id = prior.id
                    break
        dates = [day for day in (_hit_day(hit) for hit in hits_in) if day]
        event_date = min(dates) if dates else None
        lead = max(
            hits_in,
            key=lambda hit: (
                0 if is_social_host(hostname(hit.origin_publisher_url or hit.url) or hit.source_domain) else 1,
                0 if is_aggregator_host(hostname(hit.origin_publisher_url or hit.url) or hit.source_domain) else 1,
                len(hit.title or ""),
                hit.published_date or "",
            ),
        )
        if new_id in used_ids:
            new_id = _stable_id((new_id, lead.title, urls[0] if urls else str(index)))
            prior = None
        used_ids.add(new_id)
        shape, independent_count = corroboration_shape(sources)
        social_only = shape == WEAK_SIGNAL_LABEL or (sources and all(source.social for source in sources))
        providers = tuple(dict.fromkeys(hit.provider for hit in hits_in))
        google_stack = any(hit.provider in {"google_news_rss", "specialist_rss"} for hit in hits_in)
        status = "weak_signal" if social_only else ("corroborated" if independent_count >= 2 else "emerging")
        first_seen = prior.first_seen if prior else (event_date or captured[:10])
        latest_update = max([*(dates or []), captured[:10]])
        evolution = list(prior.evolution) if prior else [EvolutionEvent(at=first_seen, kind="FIRST_SEEN", detail=lead.title)]
        if prior:
            prior_urls = set(prior.live_hit_urls)
            for source in sources:
                if source.url not in prior_urls and not source.syndicated:
                    evolution.append(
                        EvolutionEvent(at=captured, kind="NEW_SOURCE", detail=f"{source.publisher}: {source.title}")
                    )
            if prior.corroboration != shape:
                evolution.append(
                    EvolutionEvent(at=captured, kind="STATUS_CHANGE", detail=f"{prior.corroboration} → {shape}")
                )
            if prior.what_happened and lead.snippet and lead.snippet[:80] not in (prior.what_happened or ""):
                if lead.snippet and lead.snippet not in " ".join(ev.detail for ev in prior.evolution):
                    evolution.append(EvolutionEvent(at=captured, kind="NEW_FACT", detail=lead.snippet[:240]))
            if latest_update != prior.latest_update:
                evolution.append(EvolutionEvent(at=captured, kind="LATEST_UPDATE", detail=lead.title))
        publishers = {source.publisher.lower() for source in sources if not source.syndicated}
        developments.append(
            Development(
                id=new_id,
                title=lead.title,
                event_type=event_type,
                what_happened=_what_happened(lead.title, event_type, company_names or variety_names),
                first_seen=first_seen,
                latest_update=latest_update,
                event_date=event_date,
                company_ids=company_ids,
                variety_ids=variety_ids,
                geography_ids=geography_ids,
                berry_ids=berry_ids,
                company_names=company_names,
                variety_names=variety_names,
                geography_labels=geography_labels,
                berry_labels=berry_labels,
                sources=sources,
                live_hit_urls=urls,
                corroboration=shape,
                status=status,
                provenance=providers,
                trust_state="LIVE / UNREVIEWED DEVELOPMENT",
                weak_signal_label=WEAK_SIGNAL_LABEL if social_only else None,
                google_stack_would_find=google_stack,
                evolution=evolution,
                source_count=len(sources),
                independent_source_count=independent_count,
                publisher_diversity=len(publishers),
            )
        )
        pending_ids.append(new_id)

    id_by_group = {i: pending_ids[i] for i in range(len(pending_ids))}
    for i, development in enumerate(developments):
        related = tuple(id_by_group[j] for j in sorted(proposed.get(i, ())) if j in id_by_group)
        development.proposed_related_ids = related
    return developments
