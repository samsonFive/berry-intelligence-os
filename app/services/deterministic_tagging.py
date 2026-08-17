"""Deterministic known-name tagging for untrusted drafts.

This is pattern matching against already-registered geography and company
names/aliases. It never verifies a claim and never writes trusted records.
Publication drafts and auto-captured newsfeed cards share the matcher;
callers decide the trust/review gate (auto-captured-only vs. draft enrichment).
"""

from __future__ import annotations

import re
from typing import Any

BERRY_TERMS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("berry-blueberry", ("blueberries", "blueberry", "arándanos", "arandanos", "arándano", "arandano")),
    ("berry-strawberry", ("strawberries", "strawberry", "frutilla", "frutillas", "fresa", "fresas")),
    ("berry-raspberry", ("raspberries", "raspberry", "frambuesa", "frambuesas")),
    ("berry-blackberry", ("blackberries", "blackberry", "mora", "moras")),
)


def matchers_from_entities(
    entities: list[dict[str, Any]] | dict[str, dict[str, Any]],
    entity_type: str,
) -> list[tuple[str, re.Pattern[str]]]:
    """(entity_id, word-boundary regex) for names/aliases at least 4 characters."""

    records = entities.values() if isinstance(entities, dict) else entities
    matchers: list[tuple[str, re.Pattern[str]]] = []
    for entity in records:
        if entity.get("entity_type") != entity_type:
            continue
        entity_id = str(entity.get("id") or "").strip()
        if not entity_id:
            continue
        for name in [entity.get("name", "")] + list(entity.get("aliases") or []):
            text = str(name or "").strip()
            if len(text) < 4:
                continue
            matchers.append((entity_id, re.compile(r"\b" + re.escape(text) + r"\b", re.IGNORECASE)))
    return matchers


def apply_known_name_matches(
    record: dict[str, Any],
    haystack: str,
    *,
    geo_matchers: list[tuple[str, re.Pattern[str]]],
    company_matchers: list[tuple[str, re.Pattern[str]]],
) -> dict[str, Any]:
    matched_geo = {eid for eid, pattern in geo_matchers if pattern.search(haystack)}
    matched_ent = {eid for eid, pattern in company_matchers if pattern.search(haystack)}
    if matched_geo:
        record["geography_ids"] = sorted(set(record.get("geography_ids") or []) | matched_geo)
    if matched_ent:
        record["entity_ids"] = sorted(set(record.get("entity_ids") or []) | matched_ent)
    if matched_geo or matched_ent:
        record["auto_tagged"] = True
    return record


def infer_berry_ids_from_text(text: str) -> list[str]:
    lowered = text.casefold()
    found: list[str] = []
    for berry_id, terms in BERRY_TERMS:
        if any(term in lowered for term in terms) and berry_id not in found:
            found.append(berry_id)
    return found
