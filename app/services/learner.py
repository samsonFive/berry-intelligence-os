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
    semantic search, no ranking model. Fast over ~10 records is the
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
    re-scan. Concepts with no trait_ids (Bloom, Texture, Precocity, Double
    cropping, Winter production as of this mission) honestly return no
    rows rather than fabricating a text-keyword match."""
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
