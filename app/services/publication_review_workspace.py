"""Publication Review V2 dossier: source evidence vs proposed record vs decision.

Review aids are never Evidence. This module does not create entities.
"""

from __future__ import annotations

import re
from typing import Any

from app.services.deterministic_tagging import infer_berry_ids_from_text
from app.services.draft_attribution import attribute_draft
from app.services.html_text import decode_html_text
from app.services.source_body import classify_source_body, atomic_extraction_source_text

_SPANISH_HINTS = (" se publicó", " frambuesa", " fresa ", " las variedades", " los principales")
_FRENCH_HINTS = (" les variétés", " fraise ", " framboise")
_ITALIAN_HINTS = (" le varietà", " fragola ", " lampone")

VARIETY_BERRY = (
    ("redsayra", "RedSayra", "Strawberry"),
    ("red samantha", "Red Samantha", "Strawberry"),
    ("blue maldiva", "Blue Maldiva", "Blueberry"),
    ("blue madeira", "Blue Madeira", "Blueberry"),
    ("blue manila", "Blue Manila", "Blueberry"),
    ("pink hudson", "Pink Hudson", "Raspberry"),
    ("black sultana", "Black Sultana", "Blackberry"),
)

TRAIT_PATTERNS = (
    ("precocity", "Precocity"),
    ("firmness", "Firmness"),
    ("flavour", "Flavor"),
    ("flavor", "Flavor"),
    ("calibre", "Fruit size"),
    ("caliber", "Fruit size"),
    ("size", "Size"),
    ("texture", "Texture"),
    ("bloom", "Bloom"),
    ("shelf life", "Shelf life"),
    ("bright colour", "Bright color"),
    ("bright color", "Bright color"),
    ("winter", "Winter production"),
    ("double crop", "Double cropping"),
    ("remarkable quality", "Fruit quality across production cycle"),
    ("quality of the fruit", "Fruit quality across production cycle"),
)

RETAILER_NAMES = (
    "Tesco",
    "Marks & Spencer",
    "ASDA",
    "Waitrose",
    "Chambers",
    "Bakker",
    "Berrie's Pride",
)

BERRY_UNLOCK = {
    "berry-raspberry": "Raspberry",
    "berry-blackberry": "Blackberry",
    "berry-strawberry": "Strawberry",
    "berry-blueberry": "Blueberry",
}


def _language_label(record: dict[str, Any], source_text: str) -> str:
    explicit = str(record.get("language") or record.get("source_language") or "").strip()
    if explicit:
        return explicit
    sample = f" {source_text.casefold()} "
    if any(hint in sample or hint in source_text for hint in _SPANISH_HINTS):
        return "Spanish"
    if any(hint in sample for hint in _FRENCH_HINTS):
        return "French"
    if any(hint in sample for hint in _ITALIAN_HINTS):
        return "Italian"
    return "English"


def _named_variety_candidates(text: str, known_names: set[str]) -> list[str]:
    found: list[str] = []
    haystack = decode_html_text(text)
    for match in re.finditer(
        r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\s+(raspberry|blackberry|strawberry|blueberry)\b",
        haystack,
        re.IGNORECASE,
    ):
        name = match.group(1).strip()
        if name.casefold() in {"the", "new", "our"}:
            continue
        if name.casefold() not in known_names and name not in found:
            found.append(name)
    return found[:8]


def detect_variety_observations(source_text: str) -> list[dict[str, Any]]:
    """Compact source-derived preview. Not Atomic Evidence."""

    rows: list[dict[str, Any]] = []
    paragraphs = [p.strip() for p in re.split(r"\n\n+", decode_html_text(source_text)) if p.strip()]
    if not paragraphs:
        paragraphs = [decode_html_text(source_text)]
    for key, name, berry in VARIETY_BERRY:
        traits: list[str] = []
        mentioned = False
        for paragraph in paragraphs:
            folded = paragraph.casefold()
            if key not in folded:
                continue
            mentioned = True
            for needle, label in TRAIT_PATTERNS:
                if needle in folded and label not in traits:
                    traits.append(label)
        if mentioned:
            rows.append({"name": name, "berry": berry, "traits": traits, "kind": "review_aid"})
    return rows


def build_publication_review_dossier(
    draft: dict[str, Any],
    *,
    entities: dict[str, dict[str, Any]] | list[dict[str, Any]],
    berry_labels: dict[str, str],
    sources: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    entity_list = list(entities.values()) if isinstance(entities, dict) else list(entities)
    entity_index = {str(row.get("id")): row for row in entity_list if row.get("id")}
    source_index = {str(row.get("id")): row for row in (sources or []) if row.get("id")}
    body = classify_source_body(draft)
    source_text = atomic_extraction_source_text(draft)
    attribution = attribute_draft(draft, entity_index, sources=source_index)
    known_variety_names = {
        str(row.get("name") or "").casefold()
        for row in entity_list
        if row.get("entity_type") == "variety"
    }
    detected = detect_variety_observations(source_text)
    proposed_varieties = _named_variety_candidates(
        f"{draft.get('title') or ''} {source_text}",
        known_variety_names,
    )
    for row in detected:
        if row["name"] not in proposed_varieties and row["name"].casefold() not in known_variety_names:
            proposed_varieties.append(row["name"])
    retailers = [name for name in RETAILER_NAMES if name.casefold() in source_text.casefold()]
    berry_ids = list(draft.get("berry_ids") or [])
    for berry_id in infer_berry_ids_from_text(f"{draft.get('title') or ''} {source_text}"):
        if berry_id not in berry_ids:
            berry_ids.append(berry_id)
    companies = [
        hit for hit in (attribution.get("suggested") or []) if hit.get("entity_type") == "company"
    ]
    varieties = [
        hit for hit in (attribution.get("suggested") or []) if hit.get("entity_type") == "variety"
    ]
    geographies = [
        hit for hit in (attribution.get("suggested") or []) if hit.get("entity_type") == "geography"
    ]
    source_derived = []
    if berry_ids:
        source_derived.append(
            "Berry: " + ", ".join(berry_labels.get(bid, bid) for bid in berry_ids)
        )
    for hit in companies[:4]:
        source_derived.append(f"Company named: {hit.get('name')} (resolved to existing entity).")
    for hit in varieties[:4]:
        source_derived.append(f"Variety named: {hit.get('name')} (resolved to existing entity).")
    for name in proposed_varieties:
        source_derived.append(f"Variety named in source, not yet a tracked entity: {name}.")
    if draft.get("source_name"):
        source_derived.append(f"Publisher: {draft.get('source_name')}.")
    if draft.get("source_url"):
        source_derived.append("Source URL is recorded on the draft.")
    if draft.get("published_date"):
        source_derived.append(f"Published date: {draft.get('published_date')}.")

    unlocks: list[str] = []
    if proposed_varieties or varieties:
        unlocks.append("Variety identity")
    if companies and (proposed_varieties or varieties):
        unlocks.append("Company ↔ Variety relationship")
    if draft.get("source_type") in {"cpvo_record", "plant_patent", "patent_record"}:
        unlocks.append("CPVO/PVR linkage")
        unlocks.append("applicant / rights-holder identity")
    if any("retail" in (draft.get("title") or "").casefold() or "retailer" in source_text.casefold() for _ in [0]):
        unlocks.append("commercial observation")
    if companies:
        unlocks.append("entity grounding")

    limitations: list[str] = []
    if body["state"] == "description_only":
        limitations.append("Description only — full article body was not persisted.")
    if body["state"] == "body_partial":
        limitations.append("Body partial — persisted text may be incomplete.")
    if body["state"] in {"body_unavailable", "access_limited", "interstitial"}:
        limitations.append("Full body unavailable in-app.")
    if "planasa" in (draft.get("source_name") or "").casefold() or "newsroom" in (draft.get("source_name") or "").casefold():
        limitations.append("Primary/company source. No independent corroboration from this record alone.")
    limitations.append("Translation is a review aid, never Evidence.")
    if "award" in (draft.get("title") or "").casefold() or "taste" in source_text.casefold():
        limitations.append("Award does not establish broad consumer preference or commercial acreage.")
    if draft.get("source_type") in {"cpvo_record", "plant_patent", "patent_record"}:
        limitations.append("Registry grant/application does not establish commercial success.")
    for item in draft.get("does_not_prove") or []:
        if item and str(item) not in limitations:
            limitations.append(str(item))

    why = decode_html_text(draft.get("why_it_matters") or "")
    if not why:
        bits = []
        if proposed_varieties:
            bits.append("names " + ", ".join(proposed_varieties[:3]))
        if berry_ids:
            bits.append("as " + "/".join(berry_labels.get(bid, bid) for bid in berry_ids[:2]))
        if companies:
            bits.append("tied to " + str(companies[0].get("name")))
        if bits:
            why = (
                "If trusted, this publication could support "
                + "; ".join(unlocks[:3] or ["entity grounding"])
                + ". "
                + "Source " + " ".join(bits) + "."
            )
            why = why[0].upper() + why[1:] if why else why

    review_summary = decode_html_text(draft.get("summary") or "")
    publisher = body["publisher_description"]
    if body["body"] and (not review_summary or review_summary == publisher):
        review_summary = body["body"][:480].rsplit(" ", 1)[0] + "…" if len(body["body"]) > 480 else body["body"]

    prefill = {
        "title": decode_html_text(draft.get("title") or ""),
        "source_name": draft.get("source_name") or "",
        "source_url": draft.get("source_url") or "",
        "published_date": draft.get("published_date") or "",
        "source_type": draft.get("source_type") or "",
        "berries": berry_ids,
        "companies": ", ".join(hit.get("name") or "" for hit in companies if hit.get("name")),
        "varieties": ", ".join(
            list(dict.fromkeys([*(hit.get("name") or "" for hit in varieties if hit.get("name")), *proposed_varieties]))
        ),
        "retailers": ", ".join(retailers),
        "geographies": ", ".join(hit.get("name") or "" for hit in geographies if hit.get("name")),
        "summary": review_summary,
        "why_it_matters": why,
        "field_classes": {
            "title": "A",
            "source_name": "A",
            "source_url": "A",
            "published_date": "A" if draft.get("published_date") else "D",
            "berries": "A" if berry_ids else "D",
            "companies": "A" if companies else "D",
            "varieties": "A" if (varieties or proposed_varieties) else "D",
            "geographies": "A" if geographies else "D",
            "summary": "B",
            "why_it_matters": "B",
            "unlocks": "B",
            "decision": "C",
        },
    }
    language = _language_label(draft, body["body"] or publisher)
    return {
        "body": body,
        "language": language,
        "language_label": f"ORIGINAL — {language}",
        "translation_available": False,
        "translation_note": "Translation unavailable.",
        "source_derived": source_derived,
        "review_aids": [
            item
            for item in (
                why and f"Why it matters (review aid): {why}",
                unlocks and "If trusted, this publication could support: " + "; ".join(unlocks) + ".",
            )
            if item
        ],
        "unlocks": unlocks,
        "limitations": limitations,
        "proposed_variety_candidates": proposed_varieties,
        "matched_entities": companies + varieties + geographies,
        "prefill": prefill,
        "extraction_text": source_text,
        "extraction_uses_summary_only": not bool(body["body"] or body["transcript_text"] or body["excerpt"]),
        "read_original_primary": not body["usable_in_app"],
        "detected_intelligence": detected,
    }


def apply_dossier_prefill(values: dict[str, Any], dossier: dict[str, Any]) -> dict[str, Any]:
    prefill = dossier.get("prefill") or {}
    updated = dict(values)
    if not (updated.get("companies") or "").strip() and prefill.get("companies"):
        updated["companies"] = prefill["companies"]
    if not (updated.get("varieties") or "").strip() and prefill.get("varieties"):
        updated["varieties"] = prefill["varieties"]
    if not (updated.get("geographies") or "").strip() and prefill.get("geographies"):
        updated["geographies"] = prefill["geographies"]
    if not (updated.get("retailers") or "").strip() and prefill.get("retailers"):
        updated["retailers"] = prefill["retailers"]
    if prefill.get("berries"):
        berries = list(updated.get("berries") or [])
        for berry_id in prefill["berries"]:
            if berry_id not in berries:
                berries.append(berry_id)
        updated["berries"] = berries
    if not (updated.get("why_it_matters") or "").strip() and prefill.get("why_it_matters"):
        updated["why_it_matters"] = prefill["why_it_matters"]
    if prefill.get("summary"):
        current = (updated.get("summary") or "").strip()
        publisher = (dossier.get("body") or {}).get("publisher_description") or ""
        if not current or current == publisher:
            updated["summary"] = prefill["summary"]
    if prefill.get("title"):
        updated["title"] = prefill["title"]
    return updated
