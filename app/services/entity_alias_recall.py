"""Derived, non-mutating alias-based evidence recall for entities.

Real gap found auditing company coverage (Intelligence Acquisition mission,
2026-08-19): SanLucar and USHBC were added as tracked entities after some
evidence that genuinely mentions them by name had already been reviewed and
published. That evidence's entity_ids never got backfilled to include them,
and it never will by the existing pipeline -- app/main.py's
auto_tag_geography_and_entities() deliberately skips any record with
validated=True, precisely so an automated process never rewrites a human's
already-reviewed trusted record. A bulk backfill script would violate that
same invariant.

This module never writes to evidence. It computes a read-only, in-memory
match from the entity's own canonical name/aliases against already-published
evidence, letting company pages recall these older mentions without ever
touching the trusted file on disk. Matches are returned as shallow copies
tagged with link_mechanism="alias_recall" so callers/templates can label
them distinctly from a reviewed entity_ids link (link_mechanism="entity_id")
-- this is a recall aid, not a claim that the match was human-verified.
"""

from __future__ import annotations

import re
from typing import Any

MIN_ALIAS_LENGTH = 4


def _alias_pattern(entity: dict[str, Any]) -> "re.Pattern[str] | None":
    aliases = [a for a in (entity.get("aliases") or []) if isinstance(a, str) and len(a) >= MIN_ALIAS_LENGTH]
    name = entity.get("name")
    if isinstance(name, str) and len(name) >= MIN_ALIAS_LENGTH:
        aliases.append(name)
    unique_aliases = sorted(set(aliases), key=len, reverse=True)
    if not unique_aliases:
        return None
    return re.compile("|".join(re.escape(a) for a in unique_aliases), re.IGNORECASE)


def _text_of(record: dict[str, Any]) -> str:
    parts = []
    for key in ("title", "headline", "summary", "excerpt", "why_it_matters"):
        value = record.get(key)
        if isinstance(value, str):
            parts.append(value)
    return " ".join(parts)


def alias_linked_evidence(
    entity: dict[str, Any],
    records: list[dict[str, Any]],
    *,
    already_linked_ids: set[str],
) -> list[dict[str, Any]]:
    """Published evidence that mentions `entity`'s canonical name/aliases by
    text but is not already linked via entity_ids. Skips entities with no
    usable alias (too short/ambiguous to match safely, e.g. bare acronyms
    under MIN_ALIAS_LENGTH). Returns shallow copies -- the original record
    objects are never modified."""
    pattern = _alias_pattern(entity)
    if pattern is None:
        return []
    matches = []
    for record in records:
        record_id = record.get("id")
        if not record_id or record_id in already_linked_ids:
            continue
        if pattern.search(_text_of(record)):
            matches.append({**record, "link_mechanism": "alias_recall"})
    return matches


def linked_evidence_for_entity(
    entity: dict[str, Any], published: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """The full recall set for one entity: reviewed entity_ids links first
    (link_mechanism="entity_id"), then alias-derived recall for anything
    the tagging pipeline missed. Both are shallow copies; published's own
    records are never mutated."""
    entity_id = entity["id"]
    direct = [{**r, "link_mechanism": "entity_id"} for r in published if entity_id in (r.get("entity_ids") or [])]
    direct_ids = {r["id"] for r in direct if r.get("id")}
    recalled = alias_linked_evidence(entity, published, already_linked_ids=direct_ids)
    return direct + recalled
