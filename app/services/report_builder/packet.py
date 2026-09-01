"""AI-Assisted Report Builder V1 -- the intelligence packet.

A deterministic, inspectable composition of already-trusted objects for
one resolved report scope. Every item retained here keeps its canonical
id, trust/state, date + date_basis, and a source href/provenance --
nothing here is prose, and nothing here is generated. This module never
calls an AI provider; app.services.report_builder.synthesis is the only
consumer allowed to turn a packet into report prose, and it only ever
sees the bounded packet this module returns, never the full repository.

Reuses existing composition primitives rather than re-deriving them:
- app.services.brief_pack's company_snapshot/variety_snapshot/source_trace
  for per-entity summaries and citation dedup.
- app.services.chronology's meaningful_stamp/dated_label for the
  captured-vs-published honesty rule (never let ingestion time masquerade
  as publication time -- AGENTS.md, Entity Intelligence Timeline).
- app.services.global_search's GEO_PREDICATES for company<->geography
  linkage.
- app.services.strategic_question_workspace's strategic_question_detail
  for the Strategic Question Brief report type.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.services.brief_pack import company_snapshot, source_trace, variety_snapshot
from app.services.chronology import meaningful_stamp
from app.services.global_search import GEO_PREDICATES
from app.services.report_builder.scope import ResolvedScope
from app.services.strategic_question_workspace import strategic_question_detail

MAX_UNSCOPED_COMPANIES = 10
MAX_UNSCOPED_VARIETIES = 40
RECENT_DEVELOPMENTS_LIMIT = 15


def _evidence_date_row(record: dict[str, Any]) -> dict[str, Any]:
    when, origin = meaningful_stamp(record, mode="timeline_evidence")
    return {
        "id": record.get("id"),
        "title": record.get("title") or record.get("source_name") or record.get("id"),
        "source_name": record.get("source_name") or "",
        "date": when.date().isoformat() if when else "",
        "date_basis": origin or "",
        "is_fallback_date": False,
        "trust": "trusted",
        "href": f"/evidence/{record.get('id')}",
        "reader_href": f"/intelligence/{record.get('id')}",
    }


def _entity_ids_in_scope(scope: ResolvedScope) -> set[str]:
    return set(scope.company_ids) | set(scope.variety_ids) | set(scope.geography_ids)


def _in_berry(record: dict[str, Any], berry_id: str | None) -> bool:
    if not berry_id:
        return True
    berry_ids = record.get("berry_ids") or record.get("market_ids") or []
    return berry_id in berry_ids


def _entity_intersect(record: dict[str, Any], entity_ids: set[str]) -> bool:
    return bool(entity_ids & set(record.get("entity_ids") or []))


def _select_records(
    records: list[dict[str, Any]],
    *,
    entity_ids: set[str],
    berry_id: str | None,
) -> list[dict[str, Any]]:
    """Derived-scope selection (entity-id intersection when a specific
    scope was resolved; berry-only membership for an unscoped landscape
    query), per app.queries.scope's documented default rule."""
    if entity_ids:
        return [r for r in records if _entity_intersect(r, entity_ids) and _in_berry(r, berry_id)]
    return [r for r in records if _in_berry(r, berry_id)]


def _within_window(record: dict[str, Any], window_days: int | None) -> bool:
    """Never drop a record solely because its date is unknown (the same
    honesty rule Search Chronology hardened for search results) -- an
    explicit date window only ever excludes an Evidence record that has a
    published_date outside the window, never one with no reliable date at
    all."""
    if not window_days:
        return True
    when, _origin = meaningful_stamp(record, mode="timeline_evidence")
    if when is None:
        return True
    return when.date() >= date.today() - timedelta(days=window_days)


def _companies_in_scope(
    scope: ResolvedScope,
    *,
    entities: dict[str, dict[str, Any]],
    relationships: list[dict[str, Any]],
    scoped_evidence: list[dict[str, Any]],
) -> list[str]:
    if scope.company_ids:
        return list(scope.company_ids)
    if scope.geography_ids:
        geo_set = set(scope.geography_ids)
        company_ids = {
            rel["subject_id"]
            for rel in relationships
            if rel.get("predicate") in GEO_PREDICATES and rel.get("object_id") in geo_set
            and (entities.get(rel.get("subject_id")) or {}).get("entity_type") == "company"
        }
        if company_ids:
            return sorted(company_ids)
    # Unscoped landscape query: rank companies by how much in-scope
    # evidence names them -- a plain, defensible count, never a score.
    counts: dict[str, int] = {}
    for record in scoped_evidence:
        for eid in record.get("entity_ids") or []:
            if (entities.get(eid) or {}).get("entity_type") == "company":
                counts[eid] = counts.get(eid, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [cid for cid, _count in ranked[:MAX_UNSCOPED_COMPANIES]]


def _varieties_in_scope(
    scope: ResolvedScope,
    *,
    entities: dict[str, dict[str, Any]],
    relationships: list[dict[str, Any]],
    company_ids: list[str],
) -> list[str]:
    if scope.variety_ids:
        return list(scope.variety_ids)
    if company_ids:
        company_set = set(company_ids)
        variety_ids = {
            rel["object_id"]
            for rel in relationships
            if rel.get("subject_id") in company_set
            and (entities.get(rel.get("object_id")) or {}).get("entity_type") == "variety"
        }
        if variety_ids:
            return sorted(variety_ids)
    if scope.berry_id:
        return [
            eid
            for eid, e in entities.items()
            if e.get("entity_type") == "variety" and scope.berry_id in (e.get("berry_ids") or [])
        ][:MAX_UNSCOPED_VARIETIES]
    return []


def build_report_packet(
    scope: ResolvedScope,
    *,
    entities: dict[str, dict[str, Any]],
    relationships: list[dict[str, Any]],
    published_evidence: list[dict[str, Any]],
    facts: list[dict[str, Any]],
    signals: list[dict[str, Any]],
    assessments: list[dict[str, Any]],
    strategic_questions: list[dict[str, Any]],
    recommendations: list[dict[str, Any]],
    variety_candidates: list[dict[str, Any]],
    berry_labels: dict[str, str],
) -> dict[str, Any]:
    """Deterministic packet assembly for one resolved scope. Safe to call
    repeatedly with the same scope against the same trusted data -- it
    always produces the same packet (no randomness, no model call)."""
    entity_ids = _entity_ids_in_scope(scope)
    evidence_by_id = {r["id"]: r for r in published_evidence if r.get("id")}

    if scope.report_type == "strategic_question_brief" and scope.strategic_question_id:
        sq = strategic_question_detail(
            scope.strategic_question_id,
            questions=strategic_questions,
            entities=entities,
            published_evidence=published_evidence,
            facts=facts,
            signals=signals,
            assessments=assessments,
            recommendations=recommendations,
            berry_labels=berry_labels,
        )
        return {
            "report_type": scope.report_type,
            "berry_id": scope.berry_id,
            "strategic_question": sq,
            "companies": [],
            "varieties": [],
            "variety_candidates": [],
            "recent_developments": [],
            "signals": sq.get("signals") if sq else [],
            "assessments": sq.get("assessments") if sq else [],
            "source_trace": sq.get("source_trace") if sq else [],
            "known_ids": _known_ids_from_sq(sq) if sq else set(),
        }

    scoped_evidence = [
        r
        for r in _select_records(published_evidence, entity_ids=entity_ids, berry_id=scope.berry_id)
        if _within_window(r, scope.date_window_days)
    ]
    scoped_signals = _select_records(signals, entity_ids=entity_ids, berry_id=scope.berry_id)
    scoped_assessments = _select_records(assessments, entity_ids=entity_ids, berry_id=scope.berry_id)

    company_ids = _companies_in_scope(scope, entities=entities, relationships=relationships, scoped_evidence=scoped_evidence)
    variety_ids = _varieties_in_scope(scope, entities=entities, relationships=relationships, company_ids=company_ids)

    companies = []
    for cid in company_ids:
        row = company_snapshot(cid, entities=entities, relationships=relationships, published_evidence=published_evidence, signals=signals)
        if row:
            companies.append(row)

    varieties = []
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
        if row:
            varieties.append(row)

    candidate_rows = [
        c
        for c in variety_candidates
        if not scope.berry_id or scope.berry_id == c.get("berry_id") or scope.berry_id in (c.get("berry_ids") or [])
    ]

    recent = sorted(
        (r for r in scoped_evidence if meaningful_stamp(r, mode="timeline_evidence")[0] is not None),
        key=lambda r: meaningful_stamp(r, mode="timeline_evidence")[0],
        reverse=True,
    )[:RECENT_DEVELOPMENTS_LIMIT]

    signal_rows = [
        {
            "id": s.get("id"),
            "title": s.get("title") or s.get("id"),
            "status": s.get("status") or "",
            "strength": s.get("strength") or "",
            "observation": s.get("observation") or "",
            "trust": "confirmed_signal" if s.get("status") == "confirmed" else "emerging_signal",
            "href": f"/signals/{s.get('id')}",
        }
        for s in scoped_signals
    ]
    assessment_rows = [
        {
            "id": a.get("id"),
            "title": a.get("title") or a.get("id"),
            "confidence": a.get("confidence") or "",
            "ai_proposed": bool(a.get("ai_proposed")),
            "rationale": a.get("rationale") or "",
            "trust": "assessment",
            "date": a.get("created_at") or "",
            "date_basis": "created_at",
            "href": f"/assessments/{a.get('id')}",
        }
        for a in scoped_assessments
    ]

    trace_evidence_ids: set[str] = {r["id"] for r in scoped_evidence if r.get("id")}
    for s in scoped_signals:
        trace_evidence_ids.update(s.get("evidence_ids") or [])
    for a in scoped_assessments:
        trace_evidence_ids.update(a.get("evidence_ids") or [])

    known_ids = (
        {row["id"] for row in scoped_evidence if row.get("id")}
        | {row["id"] for row in scoped_signals if row.get("id")}
        | {row["id"] for row in scoped_assessments if row.get("id")}
        | set(company_ids)
        | set(variety_ids)
        | {c["id"] for c in candidate_rows if c.get("id")}
    )

    return {
        "report_type": scope.report_type,
        "berry_id": scope.berry_id,
        "strategic_question": None,
        "companies": companies,
        "varieties": varieties,
        "variety_candidates": candidate_rows,
        "recent_developments": [_evidence_date_row(r) for r in recent],
        "signals": signal_rows,
        "assessments": assessment_rows,
        "source_trace": source_trace(trace_evidence_ids, evidence_by_id),
        "known_ids": known_ids,
    }


def _known_ids_from_sq(sq: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for group in ("facts", "assessments", "signals", "recommendations"):
        ids.update(row["id"] for row in sq.get(group) or [] if row.get("id"))
    ids.update(row["id"] for row in sq.get("source_trace") or [] if row.get("id"))
    return ids
