"""Learner Mode V1 -- a bounded, deterministic educational layer connected
to (but never masquerading as) trusted Competitive Intelligence.

Governance: docs/v2/feature-requests/LEARNER-MODE.md and
INTELLIGENCE-EXPANSION-BUILD-GUIDE.md section 12a are the authoritative
requirements this module deliberately stays within. Concept content is
data, not code -- structured JSON records under data/learn/concepts/,
mirroring the existing data/entities/traits/ pattern, not hardcoded
template strings. Educational content carries its own knowledge_class
and source list and is never presented as Fact, Atomic Evidence, Signal,
or Assessment. "Related intelligence" reuses only already-trusted Fact/
Evidence objects, matched by the same real trait-* entity ids Variety
Intelligence V2 already uses -- no NLP, no new trust object, no fake
competitive knowledge."""

from __future__ import annotations

import json
import re
from datetime import date
from functools import lru_cache
from typing import Any

from app.runtime_config import resolve_data_dir

# resolve_data_dir() -- not a path relative to this file -- so this
# correctly follows BIOS_DATA_DIR/BIOS_RUNTIME_DIR in the remote-demo
# deployment (data/ lives under the synced runtime tree there, not next
# to the application code) the same way every other data reader in this
# codebase already does.
CONCEPTS_DIR = resolve_data_dir() / "learn" / "concepts"

PILLAR_LABELS: dict[str, str] = {
    "plant_biology_agronomy": "Plant Biology & Agronomy",
    "pest_disease_process": "Pest, Disease & Cross-Cutting Process",
    "harvest_technology_agtech": "Harvest Technology & AgTech",
    "taste_consumer_science": "Taste & Consumer Science",
    "visual_content_sourcing": "Visual Content Sourcing",
}

PILLAR_ORDER = list(PILLAR_LABELS.keys())

KNOWLEDGE_CLASS_LABELS: dict[str, str] = {
    "foundational_knowledge": "Foundational knowledge",
    "regional_production_practice": "Regional production practice",
    "current_technical_guidance": "Current technical guidance",
    "consumer_sensory_observations": "Consumer / sensory observations",
}

KNOWLEDGE_CLASS_NOTES: dict[str, str] = {
    "foundational_knowledge": "Relatively stable crop biology / attribute concept -- slow review cadence.",
    "regional_production_practice": "Must be read with geography/production-system context -- never universal across regions.",
    "current_technical_guidance": "Needs freshness/review; can change with new technique or research.",
    "consumer_sensory_observations": "Dated research/panel output -- read as a trended data point, not a timeless fact.",
}

RELATED_INTELLIGENCE_LIMIT = 8
GLOSSARY_HIT_LIMIT = 6
GROWING_PROFILE_LIMIT = 12
# Short distinctive tokens that are safe glossary triggers. Generic
# single words (bloom, flavor, color) only match in a title, never in a
# summary/body excerpt -- that is the whole precision rule; there is no
# NLP pass over article text.
GLOSSARY_SHORT_OK = {"ipm", "voc", "ssc", "brix", "swd"}
GLOSSARY_WEAK_SINGLE = {
    "bloom",
    "color",
    "flavor",
    "taste",
    "texture",
    "firmness",
    "precocity",
}
FRESHNESS_CLASSES = {
    "current_technical_guidance",
    "consumer_sensory_observations",
}


@lru_cache(maxsize=1)
def _load_all() -> tuple[dict[str, Any], ...]:
    if not CONCEPTS_DIR.exists():
        return ()
    rows: list[dict[str, Any]] = []
    for path in sorted(CONCEPTS_DIR.glob("concept-*.json")):
        with path.open(encoding="utf-8") as fh:
            row = json.load(fh)
        pillar = str(row.get("pillar") or "")
        row["pillar_label"] = PILLAR_LABELS.get(pillar, pillar.replace("_", " ").title())
        knowledge_class = str(row.get("knowledge_class") or "")
        row["knowledge_class_label"] = KNOWLEDGE_CLASS_LABELS.get(
            knowledge_class, knowledge_class.replace("_", " ").title()
        )
        row["knowledge_class_note"] = KNOWLEDGE_CLASS_NOTES.get(knowledge_class, "")
        row["berry_ids"] = tuple(
            dict.fromkeys(
                str(note.get("berry_id") or "")
                for note in (row.get("berry_notes") or [])
                if note.get("berry_id")
            )
        )
        figure = next(
            (
                item
                for item in (row.get("media") or [])
                if item.get("image_url")
            ),
            None,
        )
        row["teaching_figure"] = figure
        review_by = str(row.get("review_by") or "").strip()
        reviewed_at = str(row.get("reviewed_at") or "").strip()
        row["reviewed_at"] = reviewed_at
        row["review_by"] = review_by
        row["needs_review_cadence"] = knowledge_class in FRESHNESS_CLASSES
        row["is_stale"] = bool(review_by) and review_by < date.today().isoformat()
        rows.append(row)
    rows.sort(key=lambda row: str(row.get("name") or ""))
    return tuple(rows)


def all_concepts() -> list[dict[str, Any]]:
    return list(_load_all())


@lru_cache(maxsize=1)
def _by_slug() -> dict[str, dict[str, Any]]:
    return {str(row["slug"]): row for row in _load_all() if row.get("slug")}


@lru_cache(maxsize=1)
def _trait_id_to_slug() -> dict[str, str]:
    index: dict[str, str] = {}
    for row in _load_all():
        for trait_id in row.get("trait_ids") or []:
            index.setdefault(str(trait_id), str(row["slug"]))
    return index


def concept_by_slug(slug: str) -> dict[str, Any] | None:
    return _by_slug().get(slug)


def concept_href(slug: str) -> str:
    return f"/learn/{slug}"


def learn_href_for_trait_id(trait_id: str) -> str | None:
    """Used by Variety Intelligence's "Explain this" links -- a trait chip
    whose id matches a Learner concept's own trait_ids gets a deep link
    into that concept page. Returns None (no link rendered) when no
    concept covers that trait -- never fabricates a connection."""
    slug = _trait_id_to_slug().get(str(trait_id))
    return concept_href(slug) if slug else None


def concepts_by_pillar() -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for concept in _load_all():
        pillar = str(concept.get("pillar") or "")
        grouped.setdefault(pillar, []).append(concept)
    ordered_keys = [p for p in PILLAR_ORDER if p in grouped] + [
        p for p in grouped if p not in PILLAR_ORDER
    ]
    return [
        {
            "pillar": pillar,
            "label": PILLAR_LABELS.get(pillar, pillar.replace("_", " ").title()),
            "concepts": grouped[pillar],
        }
        for pillar in ordered_keys
    ]


def search_concepts(query: str) -> list[dict[str, Any]]:
    """Deterministic name/alias/keyword/pillar substring match -- no
    semantic search, no ranking model. Fast over a small finite set is the
    entire performance requirement here."""
    q = (query or "").strip().lower()
    if not q:
        return all_concepts()
    results = []
    for concept in _load_all():
        haystack = " ".join(
            [
                str(concept.get("name") or ""),
                " ".join(concept.get("aliases") or []),
                PILLAR_LABELS.get(str(concept.get("pillar") or ""), ""),
                str(concept.get("summary") or ""),
            ]
        ).lower()
        if q in haystack:
            results.append(concept)
    return results


def related_concepts(concept: dict[str, Any]) -> list[dict[str, Any]]:
    by_slug = _by_slug()
    related = []
    for related_id in concept.get("related_concept_ids") or []:
        # related_concept_ids store the concept id (e.g. "concept-texture");
        # resolve via slug for the href, tolerating either form.
        slug = str(related_id).removeprefix("concept-")
        row = by_slug.get(slug)
        if row:
            related.append({"slug": row["slug"], "name": row["name"], "href": concept_href(row["slug"])})
    return related


def related_intelligence_for_concept(
    concept: dict[str, Any],
    *,
    facts: list[dict[str, Any]],
    entities: dict[str, dict[str, Any]],
    evidence_by_id: dict[str, dict[str, Any]],
    limit: int = RELATED_INTELLIGENCE_LIMIT,
) -> dict[str, Any]:
    """Trusted-only, bounded lookup: Facts whose entity_ids co-occur with
    both a real trait-* entity this concept declares and a real Variety --
    the exact same recall mechanism present_variety_intelligence() already
    uses. A single pass over the already-loaded facts list; no corpus
    re-scan. Concepts with no trait_ids honestly return no rows rather
    than fabricating a text-keyword match."""
    trait_ids = set(concept.get("trait_ids") or [])
    if not trait_ids:
        return {"rows": [], "has_any": False}

    rows: list[dict[str, Any]] = []
    for fact in facts:
        fact_entity_ids = set(fact.get("entity_ids") or [])
        if not (fact_entity_ids & trait_ids):
            continue
        variety_id = next(
            (
                eid
                for eid in fact_entity_ids
                if entities.get(eid, {}).get("entity_type") == "variety"
            ),
            None,
        )
        if not variety_id:
            continue
        variety = entities.get(variety_id)
        evidence_ids = [str(eid) for eid in (fact.get("evidence_ids") or []) if eid]
        primary = evidence_by_id.get(evidence_ids[0]) if evidence_ids else None
        rows.append(
            {
                "id": fact.get("id"),
                "statement": fact.get("statement") or "",
                "classification": fact.get("classification") or "",
                "variety_name": variety.get("name") if variety else variety_id,
                "variety_href": f"/entities/variety/{variety_id}",
                "source_name": (primary or {}).get("source_name") or "",
                "published_date": (primary or {}).get("published_date") or (primary or {}).get("captured_date") or "",
                "evidence_id": (primary or {}).get("id") or "",
                "evidence_href": f"/evidence/{primary['id']}" if primary else "",
                "reader_href": f"/intelligence/{primary['id']}" if primary else "",
            }
        )

    rows.sort(key=lambda r: str(r.get("published_date") or ""), reverse=True)
    rows = rows[:limit]
    return {"rows": rows, "has_any": bool(rows)}


def berry_notes_for_display(concept: dict[str, Any], berry_id: str) -> dict[str, Any]:
    """Split crop notes into in-context vs also-global. A concept with no
    berry_notes is crop-general, not a claim that it applies to every berry."""
    berry_id = str(berry_id or "")
    notes = []
    for raw in concept.get("berry_notes") or []:
        bid = str(raw.get("berry_id") or "")
        text = str(raw.get("note") or "").strip()
        if not bid or not text:
            continue
        notes.append(
            {
                "berry_id": bid,
                "berry_label": bid.removeprefix("berry-").replace("-", " ").title(),
                "note": text,
            }
        )
    if berry_id in {"", "global"}:
        return {"in_context": notes, "also_global": [], "has_any": bool(notes)}
    in_context = [row for row in notes if row["berry_id"] == berry_id]
    also_global = [row for row in notes if row["berry_id"] != berry_id]
    return {"in_context": in_context, "also_global": also_global, "has_any": bool(notes)}


@lru_cache(maxsize=1)
def _glossary_terms() -> tuple[dict[str, Any], ...]:
    terms: list[dict[str, Any]] = []
    for row in _load_all():
        seen_phrase: set[str] = set()
        for raw in [row.get("name"), *(row.get("aliases") or [])]:
            phrase = str(raw or "").strip()
            folded = phrase.casefold()
            if not phrase or folded in seen_phrase:
                continue
            seen_phrase.add(folded)
            tokens = folded.split()
            strong = len(tokens) > 1 or len(folded) >= 8 or folded in GLOSSARY_SHORT_OK
            weak = (not strong) and (len(folded) >= 4 or folded in GLOSSARY_WEAK_SINGLE)
            if not strong and not weak:
                continue
            terms.append(
                {
                    "phrase": phrase,
                    "folded": folded,
                    "pattern": re.compile(r"(?<!\w)" + re.escape(folded) + r"(?!\w)", re.IGNORECASE),
                    "slug": row["slug"],
                    "name": row["name"],
                    "href": concept_href(str(row["slug"])),
                    "pillar_label": row.get("pillar_label") or "",
                    "strong": strong,
                }
            )
    terms.sort(key=lambda term: (-len(term["folded"]), term["folded"]))
    return tuple(terms)


def glossary_hits_for_text(*parts: Any, limit: int = GLOSSARY_HIT_LIMIT) -> list[dict[str, Any]]:
    """Deterministic alias/name match against title + optional excerpts.

    Does not scan full article or transcript bodies. Weak single-token
    names only match the first part (title). Never returns a trust badge."""
    texts = [str(part or "") for part in parts]
    title = texts[0] if texts else ""
    rest = " ".join(texts[1:])
    if not title.strip() and not rest.strip():
        return []
    hits: list[dict[str, Any]] = []
    seen: set[str] = set()
    for term in _glossary_terms():
        slug = str(term["slug"])
        if slug in seen:
            continue
        in_title = bool(term["pattern"].search(title))
        in_rest = bool(term["pattern"].search(rest)) if rest else False
        matched = in_title or (term["strong"] and in_rest)
        if not matched:
            continue
        seen.add(slug)
        hits.append(
            {
                "slug": slug,
                "name": term["name"],
                "href": term["href"],
                "pillar_label": term["pillar_label"],
                "matched_term": term["phrase"],
            }
        )
        if len(hits) >= limit:
            break
    return hits


def stale_concepts(*, as_of: str | None = None) -> list[dict[str, Any]]:
    """Pages that declared a review-by date and are past it. Foundational
    biology with no review_by is not stale — it was never on a cadence."""
    cutoff = as_of or date.today().isoformat()
    rows = []
    for concept in _load_all():
        review_by = str(concept.get("review_by") or "")
        if review_by and review_by < cutoff:
            rows.append(concept)
    rows.sort(key=lambda row: str(row.get("review_by") or ""))
    return rows


def freshness_summary(*, as_of: str | None = None) -> dict[str, Any]:
    cadence = [row for row in _load_all() if row.get("needs_review_cadence")]
    stale = stale_concepts(as_of=as_of)
    return {
        "cadence_count": len(cadence),
        "stale_count": len(stale),
        "stale": stale,
        "as_of": as_of or date.today().isoformat(),
    }


def growing_profile_for_varieties(
    variety_ids: list[str],
    *,
    facts: list[dict[str, Any]],
    entities: dict[str, dict[str, Any]],
    limit: int = GROWING_PROFILE_LIMIT,
) -> dict[str, Any]:
    """Map captured trait-* Facts on the given varieties onto Learner
    concepts. Educational assembly only — not a performance score, not a
    farm Growing Guide, and not a new Fact."""
    wanted = {str(vid) for vid in variety_ids if vid}
    if not wanted:
        return {"rows": [], "has_any": False, "variety_count": 0}
    trait_to_slug = _trait_id_to_slug()
    by_slug: dict[str, dict[str, Any]] = {}
    for fact in facts:
        fact_ids = {str(eid) for eid in (fact.get("entity_ids") or []) if eid}
        matched_varieties = fact_ids & wanted
        if not matched_varieties:
            continue
        for trait_id in fact_ids:
            slug = trait_to_slug.get(trait_id)
            if not slug:
                continue
            trait = entities.get(trait_id) or {}
            if trait.get("entity_type") != "trait":
                continue
            concept = concept_by_slug(slug)
            if not concept:
                continue
            row = by_slug.setdefault(
                slug,
                {
                    "slug": slug,
                    "name": concept.get("name") or slug,
                    "href": concept_href(slug),
                    "pillar_label": concept.get("pillar_label") or "",
                    "summary": concept.get("summary") or "",
                    "trait_names": [],
                    "variety_ids": set(),
                },
            )
            trait_name = str(trait.get("name") or trait_id)
            if trait_name not in row["trait_names"]:
                row["trait_names"].append(trait_name)
            row["variety_ids"].update(matched_varieties)
    rows = []
    for row in by_slug.values():
        variety_names = []
        for vid in sorted(row["variety_ids"]):
            entity = entities.get(vid) or {}
            variety_names.append(
                {
                    "id": vid,
                    "name": entity.get("name") or vid,
                    "href": f"/entities/variety/{vid}",
                }
            )
        rows.append({**row, "variety_ids": sorted(row["variety_ids"]), "varieties": variety_names})
    rows.sort(key=lambda row: str(row.get("name") or ""))
    rows = rows[:limit]
    return {"rows": rows, "has_any": bool(rows), "variety_count": len(wanted)}


def growing_profile_for_company(
    company_id: str,
    *,
    relationships: list[dict[str, Any]],
    entities: dict[str, dict[str, Any]],
    facts: list[dict[str, Any]],
    limit: int = GROWING_PROFILE_LIMIT,
) -> dict[str, Any]:
    """Educational context from a Company's ROLE_BUCKETS portfolio varieties.

    Reuses `_company_portfolio_roles` so breeder/owner/licensee stay distinct
    at the id-collection layer, then maps captured trait Facts the same way
    a Variety Growing Profile does. Not a farm guide and not a score.
    """
    from app.services.company_workspace import _company_portfolio_roles, _portfolio_variety_ids

    vids = _portfolio_variety_ids(
        _company_portfolio_roles(company_id, relationships=relationships, entities=entities)
    )
    return growing_profile_for_varieties(vids, facts=facts, entities=entities, limit=limit)
