"""Presentation-time entity attribution for untrusted pending content.

Deterministic matching only: canonical names, aliases, legal names, company
newsroom identity, and strong title/body hits. This module never writes
Evidence, never mutates trusted records, and never uses an opaque AI score.

Callers may *expose* suggestions on pending cards. They must not silently
stuff ``entity_ids`` as if a human had tagged the draft.
"""

from __future__ import annotations

import re
from typing import Any

from app.services.deterministic_tagging import BERRY_TERMS, matchers_from_entities
from app.services.intelligence_feed import MARKET_TAGS

WATCH_ENTITY_TYPES = {"company", "variety", "geography", "person"}
MIN_NEEDLE = 4
LEGAL_SUFFIX_RE = re.compile(
    r",?\s+(s\.?a\.?|pty ltd|llc|b\.v\.|inc\.?|ltd\.?|gmbh|holdings.*|group.*)$",
    re.IGNORECASE,
)


def _folded(value: Any) -> str:
    return str(value or "").casefold()


def _title_text(record: dict[str, Any]) -> str:
    return " ".join(
        part for part in (record.get("title"), record.get("headline")) if isinstance(part, str) and part.strip()
    )


def _body_text(record: dict[str, Any]) -> str:
    parts = []
    for key in ("summary", "excerpt", "why_it_matters", "publisher_description"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(value)
    enrichment = record.get("ai_enrichment") or {}
    for key in ("concise_summary", "why_it_matters"):
        value = enrichment.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(value)
    return " ".join(parts)


def _needles(entity: dict[str, Any]) -> list[tuple[str, str]]:
    """(folded needle, method) longest first. Legal names keep a distinct method."""

    rows: list[tuple[str, str]] = []
    seen: set[str] = set()
    name = str(entity.get("name") or "").strip()
    if name:
        method = "legal_name" if LEGAL_SUFFIX_RE.search(name) else "canonical_name"
        folded = name.casefold()
        if len(folded) >= MIN_NEEDLE and folded not in seen:
            rows.append((folded, method))
            seen.add(folded)
        compact = LEGAL_SUFFIX_RE.sub("", name).strip()
        if compact:
            folded = compact.casefold()
            if len(folded) >= MIN_NEEDLE and folded not in seen:
                rows.append((folded, "canonical_name"))
                seen.add(folded)
    for alias in list(entity.get("aliases") or []) + list(entity.get("also_known_as") or []):
        text = str(alias or "").strip()
        folded = text.casefold()
        if len(folded) < MIN_NEEDLE or folded in seen:
            continue
        rows.append((folded, "alias"))
        seen.add(folded)
    rows.sort(key=lambda row: len(row[0]), reverse=True)
    return rows


def _boundary_search(haystack: str, needle: str) -> bool:
    if not haystack or not needle:
        return False
    return re.search(r"\b" + re.escape(needle) + r"\b", haystack, re.IGNORECASE) is not None


def _first_method(haystack: str, entity: dict[str, Any]) -> str | None:
    for needle, method in _needles(entity):
        if _boundary_search(haystack, needle):
            return method
    return None


def _hit(
    entity: dict[str, Any],
    *,
    method: str,
    location: str,
    strength: str,
) -> dict[str, Any]:
    return {
        "id": str(entity.get("id") or ""),
        "name": str(entity.get("name") or entity.get("id") or ""),
        "entity_type": str(entity.get("entity_type") or "company"),
        "method": method,
        "location": location,
        "strength": strength,
    }


def _newsroom_company_ids(
    record: dict[str, Any],
    entities: dict[str, dict[str, Any]],
    sources: dict[str, dict[str, Any]] | None,
) -> list[str]:
    ids: list[str] = []
    source = (sources or {}).get(str(record.get("source_id") or "")) or {}
    ids.extend(str(entity_id) for entity_id in (source.get("linked_competitor_ids") or []) if entity_id)
    label = " ".join(
        part
        for part in (source.get("label"), record.get("source_name"), record.get("publisher"))
        if isinstance(part, str) and part.strip()
    )
    if label:
        for entity in entities.values():
            if entity.get("entity_type") != "company":
                continue
            if _first_method(label, entity):
                ids.append(str(entity.get("id") or ""))
    return list(dict.fromkeys(id_ for id_ in ids if id_))


def _market_subject(record: dict[str, Any]) -> dict[str, Any] | None:
    tags = {str(tag).casefold() for tag in (record.get("tags") or [])}
    if tags & MARKET_TAGS:
        return {
            "id": "",
            "name": "Markets / supply",
            "entity_type": "market",
            "method": "market_tag",
            "location": "tags",
            "strength": "primary",
        }
    return None


def attribute_draft(
    record: dict[str, Any],
    entities: dict[str, dict[str, Any]],
    *,
    sources: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return suggestions and a single primary subject. Non-mutating."""

    title = _title_text(record)
    body = _body_text(record)
    hits: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add_hit(entity: dict[str, Any], *, method: str, location: str, strength: str) -> None:
        entity_id = str(entity.get("id") or "")
        if not entity_id:
            return
        existing = next((row for row in hits if row["id"] == entity_id), None)
        rank = {"primary": 2, "mention": 1}
        loc_rank = {"title": 3, "source": 2, "stored": 2, "body": 1}
        if existing:
            if rank.get(strength, 0) > rank.get(existing["strength"], 0) or (
                strength == existing["strength"] and loc_rank.get(location, 0) > loc_rank.get(existing["location"], 0)
            ):
                existing.update(_hit(entity, method=method, location=location, strength=strength))
            return
        hits.append(_hit(entity, method=method, location=location, strength=strength))
        seen.add(entity_id)

    for entity in entities.values():
        if entity.get("entity_type") not in WATCH_ENTITY_TYPES:
            continue
        entity_id = str(entity.get("id") or "")
        if not entity_id:
            continue
        title_method = _first_method(title, entity)
        if title_method:
            add_hit(entity, method=title_method, location="title", strength="primary")
            continue
        body_method = _first_method(body, entity)
        if body_method:
            add_hit(entity, method=body_method, location="body", strength="mention")

    for entity_id in record.get("entity_ids") or []:
        entity = entities.get(str(entity_id))
        if not entity or entity.get("entity_type") not in WATCH_ENTITY_TYPES:
            continue
        if str(entity.get("id") or "") in seen:
            continue
        add_hit(entity, method="stored_entity_id", location="stored", strength="mention")

    title_company_ids = {
        hit["id"] for hit in hits if hit["entity_type"] == "company" and hit["location"] == "title"
    }
    for entity_id in _newsroom_company_ids(record, entities, sources):
        entity = entities.get(entity_id)
        if not entity:
            continue
        title_method = _first_method(title, entity)
        competing_title = bool(title_company_ids - {entity_id})
        if title_method:
            add_hit(entity, method="newsroom_identity", location="title", strength="primary")
        elif not competing_title:
            add_hit(entity, method="newsroom_identity", location="source", strength="primary")
        else:
            add_hit(entity, method="newsroom_identity", location="source", strength="mention")

    title_companies = [
        hit for hit in hits if hit["entity_type"] == "company" and hit["location"] == "title"
    ]
    newsroom_primary = [
        hit
        for hit in hits
        if hit["method"] == "newsroom_identity" and hit["entity_type"] == "company" and hit["strength"] == "primary"
    ]
    title_varieties = [hit for hit in hits if hit["entity_type"] == "variety" and hit["location"] == "title"]
    title_geographies = [hit for hit in hits if hit["entity_type"] == "geography" and hit["location"] == "title"]

    primary: dict[str, Any] | None = None
    if len(title_companies) == 1:
        primary = dict(title_companies[0])
        primary["strength"] = "primary"
    elif len(title_companies) > 1:
        primary = dict(max(title_companies, key=lambda hit: len(str(hit.get("name") or ""))))
        primary["strength"] = "primary"
    elif newsroom_primary:
        primary = dict(newsroom_primary[0])
        primary["strength"] = "primary"
    elif title_varieties:
        primary = dict(title_varieties[0])
        primary["strength"] = "primary"
    elif title_geographies and not title_companies:
        primary = dict(title_geographies[0])
        primary["strength"] = "primary"
    else:
        primary = _market_subject(record)

    if primary and primary.get("id"):
        for hit in hits:
            if hit["id"] == primary["id"]:
                hit["strength"] = "primary"
            elif hit["location"] != "title" or hit["entity_type"] != primary.get("entity_type"):
                if hit["id"] != primary["id"]:
                    hit["strength"] = "mention"

    display = [
        hit
        for hit in hits
        if hit["strength"] == "primary" or hit["location"] in {"title", "source"} or hit["method"] == "newsroom_identity"
    ]
    mentions = [hit for hit in hits if hit["strength"] == "mention" and hit not in display]

    return {
        "primary": primary,
        "suggested": display,
        "mentions": mentions,
        "hits": hits,
    }


def watch_match_quality(
    attribution: dict[str, Any],
    watch_entities: set[str],
) -> tuple[str, str | None]:
    """Return (primary|mention|none, matched entity id)."""

    primary = attribution.get("primary") or {}
    primary_id = str(primary.get("id") or "")
    if primary_id and primary_id in watch_entities:
        return "primary", primary_id
    for hit in attribution.get("hits") or []:
        hit_id = str(hit.get("id") or "")
        if hit_id and hit_id in watch_entities:
            return "mention", hit_id
    return "none", None


def draft_matches_entity(
    record: dict[str, Any],
    entity: dict[str, Any],
    entities: dict[str, dict[str, Any]],
    *,
    sources: dict[str, dict[str, Any]] | None = None,
) -> bool:
    """True when the draft is *about* this entity, not merely co-mentioning it."""

    entity_id = str(entity.get("id") or "")
    if not entity_id:
        return False
    if entity_id in (record.get("entity_ids") or []):
        if _first_method(_title_text(record), entity) or not _body_text(record):
            return True
        # Stored id with only a body mention: still a stored link the analyst
        # or capture path already made. Keep it for recall of tagged drafts.
        return True
    attribution = attribute_draft(record, entities, sources=sources)
    primary = attribution.get("primary") or {}
    if str(primary.get("id") or "") == entity_id:
        return True
    return any(
        hit.get("id") == entity_id and hit.get("location") in {"title", "source"}
        for hit in attribution.get("suggested") or []
    )


def company_matchers(entities: dict[str, dict[str, Any]]) -> list[tuple[str, re.Pattern[str]]]:
    """Expose the same word-boundary company matchers used at capture time."""

    return matchers_from_entities(entities, "company")


def berry_terms() -> tuple[tuple[str, tuple[str, ...]], ...]:
    return BERRY_TERMS
