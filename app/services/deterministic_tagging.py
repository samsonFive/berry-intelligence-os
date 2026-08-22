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
    # French "myrtille(s)" and Italian "mirtillo"/"mirtilli" added for
    # Evidence Berry Tagging Backfill V1 (2026-08-22) -- mirrors the species
    # vocabulary already proven safe in relevance_screen.py's berry_identity
    # gate (TD-072: this module previously had zero French/Italian terms for
    # any berry despite relevance_screen.py recognizing them).
    ("berry-blueberry", ("blueberries", "blueberry", "arándanos", "arandanos", "arándano", "arandano", "myrtille", "myrtilles", "mirtillo", "mirtilli")),
    # French "fraise(s)" and Italian "fragola"/"fragole" added, same reason.
    ("berry-strawberry", ("strawberries", "strawberry", "frutilla", "frutillas", "fresa", "fresas", "fraise", "fraises", "fragola", "fragole")),
    # "caneberry"/"caneberries" appears on both raspberry and blackberry --
    # it is the real, unambiguous US/UK trade-press collective term for the
    # two species together (Blackberry/Raspberry Vertical V1, 2026-08-22),
    # not a third species. An item naming only "caneberry" tags both.
    # French "framboise(s)" and Italian "lampone"/"lamponi" added, same
    # reason as blueberry/strawberry above.
    ("berry-raspberry", ("raspberries", "raspberry", "frambuesa", "frambuesas", "caneberry", "caneberries", "framboise", "framboises", "lampone", "lamponi")),
    # "zarzamora"/"zarzamoras" -- the real term Mexican trade press uses
    # for blackberry (Blackberry/Raspberry Vertical V1, 2026-08-22),
    # distinct from and lower collision-risk than the existing "mora".
    # French "mûre"/"mûres" and Italian "more" are deliberately NOT added
    # here, mirroring relevance_screen.py's own documented exclusions:
    # "mûre" is the ordinary French adjective for "ripe", and "more" is an
    # extremely common English word -- word-boundary matching (this
    # module's own infer_berry_ids_from_text, fixed this mission) protects
    # against a *substring* collision like "morado", but a standalone
    # French/English sentence can legitimately contain the standalone word
    # "mûre"/"more" with zero connection to blackberries, so word-boundary
    # matching alone does not make either term safe to add.
    ("berry-blackberry", ("blackberries", "blackberry", "mora", "moras", "zarzamora", "zarzamoras", "caneberry", "caneberries")),
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


def _word_present(text: str, term: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text) is not None


def infer_berry_ids_from_text(text: str) -> list[str]:
    """Word-boundary matched -- a plain substring check here would false-positive
    on real, common non-berry Spanish words that merely contain "mora" (e.g.
    "morado"/purple, "enamorado"/in love, "memorable"). Found and fixed during
    Evidence Berry Tagging Backfill V1 (2026-08-22) before it could inject
    false blackberry tags at backfill scale; mirrors relevance_screen.py's
    own already-word-boundary-safe `_word_present`."""
    lowered = text.casefold()
    found: list[str] = []
    for berry_id, terms in BERRY_TERMS:
        if any(_word_present(lowered, term) for term in terms) and berry_id not in found:
            found.append(berry_id)
    return found
