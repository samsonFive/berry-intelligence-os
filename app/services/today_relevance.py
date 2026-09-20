"""Same-day Today relevance — drop hobby/consumer noise after Pulse qualify.

Pulse qualification is recall-oriented. Today is a manager brief: keep
industry moves, drop garden how-tos, cherry tomatoes, and forex pages.
Does not invent entities. Does not write Evidence.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Iterable

from urllib.parse import urlparse

from app.services.article_dedup import normalize_canonical_url, normalize_title
from app.services.industry_pulse.models import DiscoveryHit

_STOP = {
    "the",
    "a",
    "an",
    "of",
    "in",
    "for",
    "and",
    "to",
    "on",
    "with",
    "from",
    "after",
    "this",
    "that",
}
_SUFFIX_RE = re.compile(r"\s+[-|–—]\s+[^-|–—]{2,40}$")
_BYLINE_RE = re.compile(r"\s+by\s+.+$", re.IGNORECASE)
_STEM_WORDS = 8

_HOBBY = re.compile(
    r"\b("
    r"how to plant|how to grow|growing guide|special care in the fall|"
    r"what to do right now|backyard|home garden|in pots|"
    r"need special care|our wild garden|better harvest"
    r")\b",
    re.IGNORECASE,
)
_TOMATO = re.compile(
    r"\b(cherry tomato|cherry tomatoes|solanum lycopersicum|indigo blue berries)\b",
    re.IGNORECASE,
)
_FOREX = re.compile(
    r"(外汇|forex|\bprice target\b|\bstock quote\b|蓝莓外汇)",
    re.IGNORECASE,
)
_CONSUMER = re.compile(
    r"\b("
    r"recipe|smoothie|muffin|calories|superfood|superfruit|dessert|"
    r"juicy secret|where to buy|best blueberries to buy|amazon|walmart|"
    r"weight loss|antioxidant snack|grocery haul|from bog to bottle|"
    r"in spanish translation"
    r")\b",
    re.IGNORECASE,
)
_PYO = re.compile(
    r"\b(pick your own|pick-your-own|u-pick|blueberry picking|strawberry picking)\b",
    re.IGNORECASE,
)
_BERRY_TERM = re.compile(
    r"\b(blueberr\w*|strawberr\w*|raspberr\w*|blackberr\w*|cranberr\w*|berries|berry|莓果|蓝莓)\b",
    re.IGNORECASE,
)
_NON_BERRY = re.compile(
    r"\b(mangoes|mango|avocados?|avocado|bananas?|banana|cucumbers?|cucumber)\b",
    re.IGNORECASE,
)
_NEWS_PATH = re.compile(r"/(news|article|press|blog|story)/", re.IGNORECASE)
_JUNK_HOSTS = {
    "test.mydesignation.com",
    "mydesignation.com",
    "mysheen.com",
}
_DIRECTORY_HOSTS = {
    "internationalblueberry.org",
}
_GENERIC = re.compile(
    r"\b(top \d+|things to do|weekend getaway|horoscope|astrology)\b",
    re.IGNORECASE,
)
_STRONG = re.compile(
    r"\b("
    r"cultivar|breeder|breeding|nursery|grower-marketer|growers?|"
    r"pbr|plant patent|plant variety|licensing|acreage|hectares|"
    r"export|imports?|variety launch|genetics|commercial production|"
    r"berry production|breeding program|managed variety|sekoya|"
    r"plant breeders|field trial"
    r")\b",
    re.IGNORECASE,
)


def _hostname(*values: str) -> str:
    for raw in values:
        text = str(raw or "").strip()
        if not text:
            continue
        host = text.split("/")[0] if "://" not in text else (urlparse(text).hostname or "")
        host = host.casefold().removeprefix("www.")
        if host:
            return host
    return ""


def noise_reason(
    *,
    title: str,
    snippet: str = "",
    url: str = "",
    source_domain: str = "",
    named_entity: bool = False,
    include_soft: bool = True,
) -> str | None:
    text = f"{title} {snippet}"
    host = _hostname(source_domain, url)
    path = urlparse(str(url or "")).path if url else ""
    if host in _JUNK_HOSTS:
        return "content-mill / SEO host"
    if host in _DIRECTORY_HOSTS and not _NEWS_PATH.search(path or "/"):
        return "directory / member profile"
    if _PYO.search(text):
        return "pick-your-own consumer"
    if _TOMATO.search(text):
        return "cherry-tomato / non-berry produce"
    if _NON_BERRY.search(text) and not _BERRY_TERM.search(text):
        return "non-berry produce"
    if _FOREX.search(text):
        return "forex/equity noise"
    if _CONSUMER.search(text):
        return "recipe/consumer food"
    if not include_soft:
        return None
    if _GENERIC.search(text) and not named_entity:
        return "generic listicle"
    if _HOBBY.search(text) and not named_entity and not _STRONG.search(text):
        return "home-garden how-to"
    if not named_entity and not _STRONG.search(text):
        return "berry mention without industry signal"
    snippet_text = (snippet or "").strip()
    if not named_entity and len(snippet_text) < 40:
        return "thin industry mention without a company"
    return None


def today_noise_reason(hit: DiscoveryHit, *, named_entity: bool) -> str | None:
    return noise_reason(
        title=hit.title,
        snippet=hit.snippet,
        url=hit.origin_publisher_url or hit.url or "",
        source_domain=hit.source_domain or "",
        named_entity=named_entity,
    )


def _name_hits(hay: str, name: str) -> bool:
    token = name.strip()
    if len(token) < 5:
        return False
    folded = token.casefold()
    if len(token) >= 10 and folded in hay:
        return True
    return bool(re.search(rf"\b{re.escape(folded)}\b", hay))


def hit_has_named_entity(hit: DiscoveryHit, entities: Iterable[dict[str, Any]]) -> bool:
    hay = f"{hit.title} {hit.snippet}".casefold()
    for entity in entities:
        names = [entity.get("name"), *(entity.get("aliases") or [])]
        for raw in names:
            if _name_hits(hay, str(raw or "")):
                return True
    return False


def apply_today_relevance(
    hits: list[DiscoveryHit],
    *,
    entities: Iterable[dict[str, Any]],
) -> tuple[list[DiscoveryHit], int]:
    kept: list[DiscoveryHit] = []
    dropped = 0
    for hit in hits:
        if not hit.qualifying:
            continue
        named = hit_has_named_entity(hit, entities)
        reason = today_noise_reason(hit, named_entity=named)
        if reason:
            hit.qualifying = False
            hit.qualify_reason = f"REJECT: {reason}"
            hit.qualify_reasons = [reason]
            dropped += 1
            continue
        kept.append(hit)
    return kept, dropped


def filter_today_records(
    records: list[dict[str, Any]],
    *,
    entities: Iterable[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    """Drop SEO/directory junk from cached Today records without a refetch."""
    kept: list[dict[str, Any]] = []
    dropped = 0
    for row in records:
        hay = f"{row.get('title') or ''} {row.get('summary') or ''}"
        named = False
        for entity in entities:
            names = [entity.get("name"), *(entity.get("aliases") or [])]
            for raw in names:
                if _name_hits(hay.casefold(), str(raw or "")):
                    named = True
                    break
            if named:
                break
        reason = noise_reason(
            title=str(row.get("title") or ""),
            snippet=str(row.get("summary") or row.get("publisher_description") or ""),
            url=str(row.get("source_url") or ""),
            source_domain="",
            named_entity=named,
            include_soft=False,
        )
        if reason:
            dropped += 1
            continue
        kept.append(row)
    return kept, dropped


def story_stem(title: str) -> str:
    """First eight content words after publisher suffix and trailing byline."""
    text = str(title or "").strip()
    text = _SUFFIX_RE.sub("", text)
    text = _BYLINE_RE.sub("", text)
    text = _SUFFIX_RE.sub("", text)
    words = [w for w in re.findall(r"[a-z0-9]+", text.casefold()) if w not in _STOP]
    if len(words) < _STEM_WORDS:
        return ""
    return " ".join(words[:_STEM_WORDS])


def cluster_key(record: dict[str, Any]) -> str:
    title = str(record.get("title") or "")
    title_id = normalize_title(title)
    published = str(record.get("published_date") or "")[:10]
    if title_id:
        return f"title:{published}:{title_id}"
    url = normalize_canonical_url(str(record.get("source_url") or ""))
    if url:
        return f"url:{url}"
    return f"id:{record.get('id') or title}"


def _cluster_label(row: dict[str, Any]) -> str:
    name = str(row.get("source_name") or "").strip()
    host = ""
    url = str(row.get("source_url") or "")
    if "://" in url:
        host = url.split("://", 1)[1].split("/", 1)[0].casefold().removeprefix("www.")
    if name and (" " in name or "." in name):
        return name
    if host:
        return host
    return name or str(row.get("acquisition_lane") or "").strip()


def collapse_story_clusters(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One story once. Extra lanes become cluster sources on the lead.

    Title+date groups already collapse syndicated headlines. A second pass
    unions groups that share a tracking-stripped canonical URL so UTM
    variants do not reopen the same page.
    """
    groups: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for record in records:
        key = cluster_key(record)
        if key not in groups:
            order.append(key)
            groups[key] = []
        groups[key].append(record)

    parent = {key: key for key in order}

    def find(key: str) -> str:
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    def union(left: str, right: str) -> None:
        root_left, root_right = find(left), find(right)
        if root_left == root_right:
            return
        if order.index(root_left) <= order.index(root_right):
            parent[root_right] = root_left
        else:
            parent[root_left] = root_right

    url_keys: dict[str, str] = {}
    stem_keys: dict[str, str] = {}
    for key, rows in groups.items():
        for row in rows:
            url = normalize_canonical_url(str(row.get("source_url") or ""))
            if url:
                seen = url_keys.get(url)
                if seen is None:
                    url_keys[url] = key
                else:
                    union(seen, key)
            stem = story_stem(str(row.get("title") or ""))
            if stem:
                seen_stem = stem_keys.get(stem)
                if seen_stem is None:
                    stem_keys[stem] = key
                else:
                    union(seen_stem, key)

    merged: dict[str, list[dict[str, Any]]] = {}
    merged_order: list[str] = []
    for key in order:
        root = find(key)
        if root not in merged:
            merged_order.append(root)
            merged[root] = []
        merged[root].extend(groups[key])

    collapsed: list[dict[str, Any]] = []
    for key in merged_order:
        rows = merged[key]
        lead = dict(rows[0])
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]
        extra: list[str] = []
        seen_extra: set[str] = set()
        for row in rows[1:]:
            label = _cluster_label(row)
            if label and label not in seen_extra:
                seen_extra.add(label)
                extra.append(label)
        lead["story_cluster_id"] = f"cluster-{digest}"
        lead["cluster_size"] = len(rows)
        lead["cluster_sources"] = extra
        lead["discovery_urls"] = [str(row.get("source_url") or "") for row in rows if row.get("source_url")]
        collapsed.append(lead)
    return collapsed
