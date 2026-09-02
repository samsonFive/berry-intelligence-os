"""Presentation helpers for the stakeholder shell. No trust/write side effects."""

from __future__ import annotations

from typing import Any

ROLE_LABELS = {
    "genetics_licensor": "Genetics licensor",
    "rights_holder": "Rights holder",
    "owner_rights_holder": "Owner / rights holder",
    "plant_breeder": "Plant breeder",
    "breeder": "Breeder",
    "licensee": "Licensee",
    "marketer": "Marketer",
    "grower": "Grower",
    "distributor": "Distributor",
    "nursery": "Nursery",
    "retailer": "Retailer",
    "exporter": "Exporter",
    "importer": "Importer",
}

IDENTITY_LABELS = {
    "no_canonical_identity_match": "Needs a human name decision",
    "unresolved_identity": "Identity not confirmed",
    "ambiguous_identity": "More than one possible match",
    "canonical_match": "Matched to a known variety",
    "alias_match": "Matched as an alias",
}

REPORT_EXAMPLE_PROMPTS = [
    {
        "label": "Blueberry genetics in Europe",
        "text": "Give me a competitive landscape for blueberry genetics in Europe.",
    },
    {
        "label": "Planasa now",
        "text": "What is Planasa doing in blueberries, and which varieties matter?",
    },
    {
        "label": "SEKOYA Grande",
        "text": "Write a variety brief for SEKOYA Grande: identity, rights, and recent intelligence.",
    },
]


def humanize_label(value: Any) -> str:
    """Turn internal slugs into stakeholder-readable labels."""
    text = str(value or "").strip()
    if not text:
        return ""
    mapped = ROLE_LABELS.get(text) or IDENTITY_LABELS.get(text)
    if mapped:
        return mapped
    cleaned = text.replace("-", " ").replace("_", " ").strip()
    if cleaned.lower().startswith("no canonical"):
        return "Needs a human name decision"
    return cleaned[:1].upper() + cleaned[1:] if cleaned else ""


def _section_rows(front_page: dict[str, Any], key: str) -> list[dict[str, Any]]:
    for section in front_page.get("sections") or []:
        if section.get("key") == key:
            return list(section.get("rows") or [])
    return []


def compose_stakeholder_front(
    front_page: dict[str, Any],
    worth_revisiting: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Pick a lead story without inventing freshness.

    When the current window has no top story, surface the strongest trusted
    or strategically important item and label it as current — not today's news.
    """
    top = list(front_page.get("top_stories") or [])
    trusted = _section_rows(front_page, "trusted_intelligence")
    worth = list(worth_revisiting or front_page.get("worth_revisiting") or [])
    using_fallback = False
    if top:
        lead, supporting = top[0], top[1:5]
    elif trusted:
        lead, supporting, using_fallback = trusted[0], trusted[1:5], True
    elif worth:
        lead, supporting, using_fallback = worth[0], worth[1:5], True
    else:
        lead, supporting, using_fallback = None, [], True
    return {
        "lead": lead,
        "supporting": supporting,
        "using_fallback": using_fallback,
        "freshness_note": (
            "These items are the strongest current trusted material. "
            "Dates are publication dates, not a claim that they happened today."
            if using_fallback and lead
            else None
        ),
        "stale_reason": front_page.get("stale_reason") or "",
    }
