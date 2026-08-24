"""Manager Brief Pack V1 -- a presentation/composition surface, NOT a new
trust object and NOT a new intelligence-generation feature. It assembles
already-trusted objects (Executive Readout, Landscape, Company/Variety
snapshots, Signals, Assessments, Learner concepts) that the operator
selects by real canonical ID into one presentation-ready, screen-shareable
briefing. No AI-written narrative, no competitor score, no fabricated
"so what" -- every section either shows a real object with its real trust
badge, or an honest "not selected" / "no trusted X captured" state.

V1 persistence model: URL-state only (the query string IS the pack) --
no server-side pack storage. This is a deliberate, documented scope cut
(see docs/v2/MANAGER-BRIEF-PACK-V1.md and the TD register); the mission
brief itself explicitly permits it: "If persistence introduces
unnecessary scope: a URL-state V1 is acceptable." A pack is deep-linkable
today because the URL already fully encodes it -- reopening the same URL
reproduces the same pack live, resolved against current trusted data.

Real object ids are read from the query string only; never a temporary
or hardcoded id baked into this module -- the default demo pack lives in
the manager-demo doc, not here."""

from __future__ import annotations

from typing import Any

from app.services.executive_readout import what_changed as readout_what_changed

# Same caveat text Executive Readout and Landscape V2 both use verbatim --
# a brief pack's selection is too small/specific for a meaningful
# disputed-fact/unresolved-question count of its own, so only the
# qualitative caveat is carried forward here, never a fabricated "0".
COVERAGE_CAVEAT = (
    "Captured intelligence coverage, not market activity. Most trusted evidence "
    "today is a thin description rather than full article or transcript text -- "
    "a thinly covered berry, company, or geography may simply be under-captured, "
    "not inactive."
)
from app.services.learner import concept_by_slug, concept_href
from app.services.variety_workspace import (
    ROLE_BUCKETS,
    ROLE_LABEL,
    SOURCE_TYPE_LABEL,
    present_variety_intelligence,
    variety_footprint,
)

COMPANY_LIMIT = 5
VARIETY_LIMIT = 5
SIGNAL_LIMIT = 5
ASSESSMENT_LIMIT = 5
CONCEPT_LIMIT = 5
RECENT_EVIDENCE_PER_COMPANY = 3


def _humanize_source_type(source_type: str) -> str:
    if not source_type:
        return "Unspecified source"
    return SOURCE_TYPE_LABEL.get(source_type, source_type.replace("_", " ").title())


def _dedup_cap(ids: list[str], limit: int) -> tuple[list[str], list[str]]:
    seen: set[str] = set()
    kept: list[str] = []
    for value in ids:
        if value and value not in seen:
            seen.add(value)
            kept.append(value)
    return kept[:limit], kept[limit:]


def company_snapshot(
    company_id: str,
    *,
    entities: dict[str, dict[str, Any]],
    relationships: list[dict[str, Any]],
    published_evidence: list[dict[str, Any]],
    signals: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Compact, bounded Company snapshot -- built from the same cheap
    primitives Company Intelligence already uses (grouped relationships,
    berry_ids, entity-linked evidence filter), never the full profile
    page's heavier synthesis. Role-bucketed varieties are never collapsed
    to a generic "has variety."."""
    company = entities.get(company_id)
    if not company or company.get("entity_type") != "company":
        return None

    predicate_to_bucket = {predicate: bucket for bucket, predicate, _label in ROLE_BUCKETS}
    roles: dict[str, list[dict[str, str]]] = {bucket: [] for bucket, _p, _l in ROLE_BUCKETS}
    for rel in relationships:
        if rel.get("subject_id") != company_id:
            continue
        bucket = predicate_to_bucket.get(rel.get("predicate"))
        if not bucket:
            continue
        variety = entities.get(str(rel.get("object_id") or ""))
        if variety and variety.get("entity_type") == "variety":
            roles[bucket].append({"id": variety["id"], "name": variety.get("name") or variety["id"]})

    berry_ids = [str(b) for b in (company.get("berry_ids") or []) if b]
    linked_evidence = [r for r in published_evidence if company_id in (r.get("entity_ids") or [])]
    linked_evidence.sort(key=lambda r: str(r.get("published_date") or r.get("captured_date") or ""), reverse=True)
    company_signals = [s for s in signals if company_id in (s.get("entity_ids") or [])]
    rights_count = sum(
        1 for r in linked_evidence if r.get("source_type") in ("patent_record", "plant_breeders_rights_record")
    )

    return {
        "id": company_id,
        "name": company.get("name") or company_id,
        "href": f"/entities/company/{company_id}",
        "timeline_href": f"/entities/company/{company_id}#intelligence-timeline",
        "berry_ids": berry_ids,
        "roles": roles,
        "role_labels": ROLE_LABEL,
        "recent_evidence": [
            {
                "id": r["id"],
                "title": r.get("title") or r.get("source_name") or r["id"],
                "source_name": r.get("source_name") or "",
                "date": r.get("published_date") or r.get("captured_date") or "",
                "href": f"/evidence/{r['id']}",
                "reader_href": f"/intelligence/{r['id']}",
            }
            for r in linked_evidence[:RECENT_EVIDENCE_PER_COMPANY]
        ],
        "signal_count": len(company_signals),
        "evidence_count": len(linked_evidence),
        "rights_count": rights_count,
    }


def variety_snapshot(
    variety_id: str,
    *,
    entities: dict[str, dict[str, Any]],
    relationships: list[dict[str, Any]],
    published_evidence: list[dict[str, Any]],
    signals: list[dict[str, Any]],
    facts: list[dict[str, Any]],
    evidence_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    """Compact Variety snapshot -- reuses variety_footprint() and
    present_variety_intelligence() exactly as Variety Compare V1 already
    proved fast and correct for a single variety; V1 shows the coverage
    counts and top observation, not the full profile page."""
    variety = entities.get(variety_id)
    if not variety or variety.get("entity_type") != "variety":
        return None

    entity_list = list(entities.values())
    footprint = variety_footprint(
        variety_id,
        entities=entity_list,
        relationships=relationships,
        published_evidence=published_evidence,
        signals=signals,
    )
    variety_facts = [f for f in facts if variety_id in (f.get("entity_ids") or [])]
    intelligence = present_variety_intelligence(
        variety, entities=entities, facts=variety_facts, evidence_by_id=evidence_by_id
    )
    top_rows = [row for group in intelligence["groups"] for row in group["rows"]][:3]

    return {
        "id": variety_id,
        "name": variety.get("name") or variety_id,
        "href": f"/entities/variety/{variety_id}",
        "berry_ids": [str(b) for b in (variety.get("berry_ids") or []) if b],
        "rights_count": len(footprint.get("rights_filings", {}).get("published") or []),
        "commercial_observation_count": len(footprint.get("commercial_observations") or []),
        "top_observations": [
            {
                "id": row["id"],
                "statement": row["statement"],
                "classification": row["classification"],
                "trait_names": row["trait_names"],
                "source_name": row["source_name"],
                "evidence_href": row["evidence_href"],
                "reader_href": row["reader_href"],
                "evidence_id": row["evidence_id"],
            }
            for row in top_rows
        ],
        "has_any_intelligence": bool(intelligence.get("has_any")),
    }


def learner_callout(slug: str) -> dict[str, Any] | None:
    concept = concept_by_slug(slug)
    if not concept:
        return None
    return {
        "slug": concept["slug"],
        "name": concept["name"],
        "summary": concept["summary"],
        "why_it_matters": concept["why_it_matters"],
        "href": concept_href(concept["slug"]),
    }


def signal_snapshot(signal_id: str, signals_by_id: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    signal = signals_by_id.get(signal_id)
    if not signal:
        return None
    return {
        "id": signal["id"],
        "title": signal.get("title") or signal["id"],
        "strength": signal.get("strength") or "",
        "evidence_count": len(signal.get("evidence_ids") or []),
        "href": f"/signals/{signal['id']}",
    }


def assessment_snapshot(
    assessment_id: str,
    assessments_by_id: dict[str, dict[str, Any]],
    recommendations: list[dict[str, Any]],
) -> dict[str, Any] | None:
    assessment = assessments_by_id.get(assessment_id)
    if not assessment:
        return None
    linked = [r for r in recommendations if assessment_id in (r.get("assessment_ids") or [])]
    return {
        "id": assessment["id"],
        "title": assessment.get("title") or assessment["id"],
        "confidence": assessment.get("confidence") or "",
        "ai_proposed": bool(assessment.get("ai_proposed")),
        "rationale": assessment.get("rationale") or "",
        "would_change_our_view": assessment.get("would_change_our_view") or "",
        "supporting_evidence_count": len(assessment.get("evidence_ids") or []),
        "supporting_fact_count": len(assessment.get("fact_ids") or []),
        "linked_recommendation_count": len(linked),
        "href": f"/assessments/{assessment['id']}",
    }


def source_trace(evidence_ids: set[str], evidence_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Every Evidence record referenced anywhere else in the pack,
    deduplicated, so the presentation stays defensible without
    re-embedding full source bodies."""
    rows = []
    for evidence_id in evidence_ids:
        record = evidence_by_id.get(evidence_id)
        if not record:
            continue
        rows.append(
            {
                "id": record["id"],
                "title": record.get("title") or record.get("source_name") or record["id"],
                "source_name": record.get("source_name") or "",
                "source_type_label": _humanize_source_type(str(record.get("source_type") or "")),
                "date": record.get("published_date") or record.get("captured_date") or "",
                "href": f"/evidence/{record['id']}",
            }
        )
    rows.sort(key=lambda r: str(r.get("date") or ""), reverse=True)
    return rows


def compose_brief_pack(
    *,
    title: str,
    context_note: str,
    berry_id: str | None,
    window_days: int,
    company_ids: list[str],
    variety_ids: list[str],
    signal_ids: list[str],
    assessment_ids: list[str],
    concept_slugs: list[str],
    entities: dict[str, dict[str, Any]],
    relationships: list[dict[str, Any]],
    published_evidence: list[dict[str, Any]],
    facts: list[dict[str, Any]],
    evidence_by_id: dict[str, dict[str, Any]],
    signals: list[dict[str, Any]],
    assessments: list[dict[str, Any]],
    recommendations: list[dict[str, Any]],
    landscape_snapshot: dict[str, Any],
) -> dict[str, Any]:
    """Top-level orchestrator. Every list here is already bounded by the
    caller (query-string selections, capped) and every underlying data
    source is a list the route already loaded once -- no corpus re-scan
    per section."""
    company_ids, overflow_companies = _dedup_cap(company_ids, COMPANY_LIMIT)
    variety_ids, overflow_varieties = _dedup_cap(variety_ids, VARIETY_LIMIT)
    signal_ids, overflow_signals = _dedup_cap(signal_ids, SIGNAL_LIMIT)
    assessment_ids, overflow_assessments = _dedup_cap(assessment_ids, ASSESSMENT_LIMIT)
    concept_slugs, overflow_concepts = _dedup_cap(concept_slugs, CONCEPT_LIMIT)

    signals_by_id = {s["id"]: s for s in signals if s.get("id")}
    assessments_by_id = {a["id"]: a for a in assessments if a.get("id")}

    companies = []
    invalid_companies = []
    for cid in company_ids:
        row = company_snapshot(cid, entities=entities, relationships=relationships, published_evidence=published_evidence, signals=signals)
        (companies if row else invalid_companies).append(row or cid)

    varieties = []
    invalid_varieties = []
    for vid in variety_ids:
        row = variety_snapshot(
            vid,
            entities=entities,
            relationships=relationships,
            published_evidence=published_evidence,
            signals=signals,
            facts=facts,
            evidence_by_id=evidence_by_id,
        )
        (varieties if row else invalid_varieties).append(row or vid)

    selected_signals = []
    invalid_signals = []
    for sid in signal_ids:
        row = signal_snapshot(sid, signals_by_id)
        (selected_signals if row else invalid_signals).append(row or sid)

    selected_assessments = []
    invalid_assessments = []
    for aid in assessment_ids:
        row = assessment_snapshot(aid, assessments_by_id, recommendations)
        (selected_assessments if row else invalid_assessments).append(row or aid)

    concepts = []
    invalid_concepts = []
    for slug in concept_slugs:
        row = learner_callout(slug)
        (concepts if row else invalid_concepts).append(row or slug)

    evidence_ids: set[str] = set()
    for company in companies:
        evidence_ids.update(row["id"] for row in company["recent_evidence"])
    for variety in varieties:
        evidence_ids.update(row["evidence_id"] for row in variety["top_observations"] if row.get("evidence_id"))
    for signal in selected_signals:
        record = signals_by_id.get(signal["id"])
        if record:
            evidence_ids.update(record.get("evidence_ids") or [])
    for assessment in selected_assessments:
        record = assessments_by_id.get(assessment["id"])
        if record:
            evidence_ids.update(record.get("evidence_ids") or [])

    key_developments = readout_what_changed(
        published_evidence=published_evidence,
        signals=signals,
        assessments=assessments,
        window_days=window_days,
        limit=5,
    )

    return {
        "title": title,
        "context_note": context_note,
        "berry_id": berry_id,
        "window_days": window_days,
        "key_developments": key_developments,
        "coverage_caveat": COVERAGE_CAVEAT,
        "landscape_snapshot": landscape_snapshot,
        "companies": companies,
        "invalid_companies": invalid_companies,
        "overflow_companies": overflow_companies,
        "varieties": varieties,
        "invalid_varieties": invalid_varieties,
        "overflow_varieties": overflow_varieties,
        "signals": selected_signals,
        "invalid_signals": invalid_signals,
        "assessments": selected_assessments,
        "invalid_assessments": invalid_assessments,
        "concepts": concepts,
        "invalid_concepts": invalid_concepts,
        "source_trace": source_trace(evidence_ids, evidence_by_id),
    }
