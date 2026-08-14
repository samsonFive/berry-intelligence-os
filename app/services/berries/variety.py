"""Berries variety trait/patent interpretation (V2 Phase 2B.2, moved from
app/main.py -- V2 Phase 1.5B's BERRIES DOMAIN PACK PROTOTYPE LOGIC block).

Reads free-form conventions that exist only inside the Berries dataset's
`attributes` dict (attributes.traits[], attributes.patent_number) -- none
of it is a core schema guarantee, and no other entity type in this
dataset uses these keys. Moved verbatim; behavior is unchanged. Pure
functions -- no repository or DATA_DIR access.
"""

from __future__ import annotations

from typing import Any


def variety_trait_profile(variety: dict[str, Any], entities: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Resolve a variety's attributes.traits[] entries (already real,
    structured data -- see data/entities/varieties/*.json) into rows a
    template can render, honestly distinguishing an owner/marketer CLAIM
    from an independently-sourced measurement."""
    rows = []
    for entry in (variety.get("attributes") or {}).get("traits") or []:
        trait_entity = entities.get(entry.get("trait"))
        provenance = entry.get("provenance")
        rows.append(
            {
                "trait_name": trait_entity["name"] if trait_entity else entry.get("trait"),
                "value": entry.get("value"),
                "provenance": provenance,
                "is_claim": provenance == "owner_or_marketer_claim",
                "is_unresolved": provenance == "unresolved",
                "asserted_by": entry.get("asserted_by"),
                "conditions": entry.get("conditions"),
                "evidence_ids": entry.get("evidence_ids") or [],
            }
        )
    return rows


def _normalize_patent_number(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


def variety_patent_link(variety: dict[str, Any], patents: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Best-effort match of a variety's free-text attributes.patent_number
    (e.g. "US PP28,358") against a live patent entity's id/aliases -- no
    'protects' relationship (patent -> variety) has any live usage yet, so
    this is the only real linkage path available today. Returns None,
    rather than a guess, when no confident match exists."""
    patent_number = (variety.get("attributes") or {}).get("patent_number")
    if not patent_number:
        return None
    needle = _normalize_patent_number(patent_number)
    for patent in patents:
        candidates = [patent.get("id", ""), *(patent.get("aliases") or [])]
        if any(_normalize_patent_number(c) == needle for c in candidates):
            return patent
    return None


class BerriesVarietyService:
    """Thin composition-registry wrapper around the module-level functions
    above, for callers that reach it via get_domain_services() rather than
    importing directly. app/main.py itself re-exports the module functions
    under their original names -- both paths call the same code."""

    def __init__(self, repos: Any) -> None:
        self._repos = repos

    def variety_trait_profile(self, variety: dict[str, Any], entities: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        return variety_trait_profile(variety, entities)

    def variety_patent_link(self, variety: dict[str, Any], patents: list[dict[str, Any]]) -> dict[str, Any] | None:
        return variety_patent_link(variety, patents)
