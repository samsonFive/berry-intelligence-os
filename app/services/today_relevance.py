"""Same-day Today relevance — drop hobby/consumer noise after Pulse qualify.

Pulse qualification is recall-oriented. Today is a manager brief: keep
industry moves, drop garden how-tos, cherry tomatoes, and forex pages.
Does not invent entities. Does not write Evidence.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Iterable

from app.services.article_dedup import normalize_canonical_url
from app.services.industry_pulse.models import DiscoveryHit

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
    r"\b(recipe|smoothie|muffin|calories|superfood|dessert)\b",
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


def today_noise_reason(hit: DiscoveryHit, *, named_entity: bool) -> str | None:
    text = f"{hit.title} {hit.snippet}"
    if _TOMATO.search(text):
        return "cherry-tomato / non-berry produce"
    if _FOREX.search(text):
        return "forex/equity noise"
    if _CONSUMER.search(text):
        return "recipe/consumer food"
    if _HOBBY.search(text) and not named_entity and not _STRONG.search(text):
        return "home-garden how-to"
    if not named_entity and not _STRONG.search(text):
        return "berry mention without industry signal"
    return None


def hit_has_named_entity(hit: DiscoveryHit, entities: Iterable[dict[str, Any]]) -> bool:
    hay = f"{hit.title} {hit.snippet}".casefold()
    for entity in entities:
        names = [entity.get("name"), *(entity.get("aliases") or [])]
        for raw in names:
            name = str(raw or "").strip()
            if len(name) >= 4 and name.casefold() in hay:
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


def cluster_key(record: dict[str, Any]) -> str:
    title = str(record.get("title") or "")
    words = [w for w in re.findall(r"[a-z0-9]+", title.casefold()) if w not in _STOP]
    stem = " ".join(words[:8])
    published = str(record.get("published_date") or "")[:10]
    if stem:
        return f"title:{published}:{stem}"
    url = normalize_canonical_url(str(record.get("source_url") or ""))
    if url:
        return f"url:{url}"
    return f"id:{record.get('id') or title}"


def collapse_story_clusters(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One story once. Extra lanes become cluster sources on the lead."""
    groups: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for record in records:
        key = cluster_key(record)
        if key not in groups:
            order.append(key)
            groups[key] = []
        groups[key].append(record)
    collapsed: list[dict[str, Any]] = []
    for key in order:
        rows = groups[key]
        lead = dict(rows[0])
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]
        lead["story_cluster_id"] = f"cluster-{digest}"
        lead["cluster_size"] = len(rows)
        lead["cluster_sources"] = [
            str(row.get("source_name") or row.get("acquisition_lane") or "")
            for row in rows[1:]
        ]
        lead["discovery_urls"] = [str(row.get("source_url") or "") for row in rows if row.get("source_url")]
        collapsed.append(lead)
    return collapsed
