"""Strategic Question + Decision Workspace V1 -- organizes already-trusted
Facts, Evidence, Signals, Assessments, and Recommendations around a
Strategic Question. Does not generate judgment: every "what we think" row
is a real Assessment, every "what we are watching" row is a real Signal,
every gap is a defensible absence state, never an AI-invented one. No
runtime LLM dependency, no synthetic "so what," no readiness/confidence
composite score.

Reuses the existing strategic_question_ids linkage already authored on
Evidence/Signal/Assessment/Recommendation (proven live: every Signal,
Assessment, and Recommendation in the current corpus already carries it)
rather than inventing a competing Decision schema. Facts link indirectly,
through the fact_ids already authored on linked Assessments -- Facts
themselves carry no strategic_question_ids field."""

from __future__ import annotations

from typing import Any

from app.services.variety_workspace import _party

GAP_MESSAGES = (
    ("fact_count", "No Fact established for this question yet."),
    ("evidence_count", "No trusted Evidence captured for this question yet."),
    ("signal_count", "No confirmed or proposed Signal captured for this question yet."),
    ("assessment_count", "No analyst Assessment captured for this question yet."),
    ("recommendation_count", "No Recommendation captured for this question yet."),
)


def _linked(records: list[dict[str, Any]], sq_id: str) -> list[dict[str, Any]]:
    return [r for r in records if sq_id in (r.get("strategic_question_ids") or [])]


def _counterevidence_rows(
    assessments: list[dict[str, Any]],
    *,
    fact_by_id: dict[str, dict[str, Any]],
    evidence_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Tensions, part 1: an Assessment's own counterevidence_ids -- the one
    explicit, schema-supported "this judgment has a known complication"
    mechanism already proven on assessment_detail.html. counterevidence_ids
    may reference either a Fact or a piece of Evidence (assessment_detail's
    own established dual-reference convention, preserved exactly here, not
    reinvented). Only assessments with real, non-empty counterevidence are
    included -- never an inferred or semantic-similarity "disagreement.\""""
    rows: list[dict[str, Any]] = []
    for a in assessments:
        items: list[dict[str, Any]] = []
        for cid in a.get("counterevidence_ids") or []:
            if cid in fact_by_id:
                fact = fact_by_id[cid]
                items.append(
                    {"id": cid, "kind": "fact", "statement": fact.get("statement") or "", "href": None}
                )
            elif cid in evidence_by_id:
                record = evidence_by_id[cid]
                items.append(
                    {
                        "id": cid,
                        "kind": "evidence",
                        "statement": record.get("title") or record.get("source_name") or cid,
                        "href": f"/evidence/{cid}",
                    }
                )
        if items:
            rows.append(
                {
                    "assessment_id": a["id"],
                    "assessment_title": a.get("title") or "",
                    "assessment_href": f"/assessments/{a['id']}",
                    # Deliberately not named "items" -- a dict key of that
                    # name is shadowed by dict.items() under Jinja's
                    # attribute-then-item dot-access resolution.
                    "counterevidence_items": items,
                }
            )
    return rows


def _evidence_contradiction_rows(
    sq_evidence: list[dict[str, Any]],
    *,
    evidence_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Tensions, part 2: explicit, accepted Evidence-to-Evidence
    "contradicts" links (Evidence.evidence_links, an existing schema
    field) among Evidence actually scoped to this question. Only
    status == "accepted" counts -- a merely proposed or contested link is
    not yet an established tension. Never semantic-similarity inference."""
    rows: list[dict[str, Any]] = []
    for record in sq_evidence:
        for link in record.get("evidence_links") or []:
            if link.get("predicate") != "contradicts" or link.get("status") != "accepted":
                continue
            target_id = str(link.get("target_evidence_id") or "")
            target = evidence_by_id.get(target_id)
            rows.append(
                {
                    "evidence_id": record["id"],
                    "evidence_title": record.get("title") or record.get("source_name") or record["id"],
                    "evidence_href": f"/evidence/{record['id']}",
                    "target_id": target_id,
                    "target_title": (target.get("title") or target.get("source_name") or target_id) if target else target_id,
                    "target_href": f"/evidence/{target_id}" if target else None,
                }
            )
    return rows


def _coverage_counts(
    *,
    fact_count: int,
    evidence_count: int,
    signal_count: int,
    assessment_count: int,
    recommendation_count: int,
) -> dict[str, int]:
    return {
        "fact_count": fact_count,
        "evidence_count": evidence_count,
        "signal_count": signal_count,
        "assessment_count": assessment_count,
        "recommendation_count": recommendation_count,
    }


def strategic_question_index(
    *,
    questions: list[dict[str, Any]],
    published_evidence: list[dict[str, Any]],
    facts: list[dict[str, Any]],
    signals: list[dict[str, Any]],
    assessments: list[dict[str, Any]],
    recommendations: list[dict[str, Any]],
    berry_labels: dict[str, str],
) -> list[dict[str, Any]]:
    """Analyst browse surface -- one row per Strategic Question with real
    linked-object counts, never a synthesized "readiness" or confidence
    score. Sorted alphabetically, not by any implied importance."""
    fact_by_id = {f["id"]: f for f in facts if f.get("id")}
    rows: list[dict[str, Any]] = []
    for sq in questions:
        sq_id = sq.get("id")
        if not sq_id:
            continue
        sq_evidence = _linked(published_evidence, sq_id)
        sq_signals = _linked(signals, sq_id)
        sq_assessments = _linked(assessments, sq_id)
        sq_recommendations = _linked(recommendations, sq_id)
        fact_ids: set[str] = set()
        for a in sq_assessments:
            fact_ids.update(a.get("fact_ids") or [])
        sq_facts = [fact_by_id[fid] for fid in fact_ids if fid in fact_by_id]

        coverage = _coverage_counts(
            fact_count=len(sq_facts),
            evidence_count=len(sq_evidence),
            signal_count=len(sq_signals),
            assessment_count=len(sq_assessments),
            recommendation_count=len(sq_recommendations),
        )
        gaps = [message for key, message in GAP_MESSAGES if coverage[key] == 0]

        berry_ids = [str(b) for b in (sq.get("berry_ids") or []) if b]
        dates = [str(e.get("published_date") or e.get("captured_date") or "") for e in sq_evidence]
        dates = [d for d in dates if d]

        rows.append(
            {
                "id": sq_id,
                "title": sq.get("title") or sq_id,
                "status": sq.get("status") or "",
                "href": f"/strategic-questions/{sq_id}",
                "berry_ids": berry_ids,
                "berries": [berry_labels.get(b, b) for b in berry_ids],
                "coverage": coverage,
                "gap_count": len(gaps),
                "latest_activity": max(dates) if dates else "",
            }
        )
    rows.sort(key=lambda r: r["title"])
    return rows


def strategic_question_detail(
    sq_id: str,
    *,
    questions: list[dict[str, Any]],
    entities: dict[str, dict[str, Any]],
    published_evidence: list[dict[str, Any]],
    facts: list[dict[str, Any]],
    signals: list[dict[str, Any]],
    assessments: list[dict[str, Any]],
    recommendations: list[dict[str, Any]],
    berry_labels: dict[str, str],
) -> dict[str, Any] | None:
    """One Strategic Question's full decision-support workspace: what we
    know (Facts + supporting Evidence), what we think (Assessments, real
    rationale/would_change_our_view fields, REVIEWED vs AI PROPOSED
    preserved), what we are watching (Signals, status/strength preserved
    distinct from Fact/Assessment), what we don't know (defensible
    zero-count gaps only), and real linked Recommendations. Returns None
    for an unknown id (the route turns that into a 404)."""
    sq = next((q for q in questions if q.get("id") == sq_id), None)
    if sq is None:
        return None

    evidence_by_id = {e["id"]: e for e in published_evidence if e.get("id")}
    fact_by_id = {f["id"]: f for f in facts if f.get("id")}

    sq_evidence = _linked(published_evidence, sq_id)
    sq_signals = _linked(signals, sq_id)
    sq_assessments = _linked(assessments, sq_id)
    sq_recommendations = _linked(recommendations, sq_id)

    fact_ids: set[str] = set()
    for a in sq_assessments:
        fact_ids.update(a.get("fact_ids") or [])
    sq_facts = [fact_by_id[fid] for fid in fact_ids if fid in fact_by_id]

    fact_rows = []
    for f in sq_facts:
        supporting = [
            {
                "id": evidence_by_id[eid]["id"],
                "title": evidence_by_id[eid].get("title"),
                "source_name": evidence_by_id[eid].get("source_name"),
                "href": f"/evidence/{eid}",
            }
            for eid in (f.get("evidence_ids") or [])
            if eid in evidence_by_id
        ]
        fact_rows.append(
            {
                "id": f["id"],
                "statement": f.get("statement") or "",
                "classification": f.get("classification") or "",
                "confidence": f.get("confidence") or "",
                "event_date": f.get("event_date") or f.get("created_at") or "",
                "supporting_evidence": supporting,
            }
        )
    fact_rows.sort(key=lambda r: str(r["event_date"]), reverse=True)

    assessment_rows = [
        {
            "id": a["id"],
            "title": a.get("title") or "",
            "confidence": a.get("confidence") or "",
            "ai_proposed": bool(a.get("ai_proposed")),
            "rationale": a.get("rationale") or "",
            "why_it_matters": a.get("why_it_matters") or "",
            "would_change_our_view": a.get("would_change_our_view") or "",
            "href": f"/assessments/{a['id']}",
        }
        for a in sq_assessments
    ]

    signal_rows = [
        {
            "id": s["id"],
            "title": s.get("title") or "",
            "status": s.get("status") or "",
            "strength": s.get("strength") or "",
            "observation": s.get("observation") or "",
            "why_it_might_matter": s.get("why_it_might_matter") or "",
            "what_would_confirm_it": s.get("what_would_confirm_it") or "",
            "what_would_falsify_it": s.get("what_would_falsify_it") or "",
            "evidence_count": len(s.get("evidence_ids") or []),
            "href": f"/signals/{s['id']}",
        }
        for s in sq_signals
    ]

    recommendation_rows = [
        {
            "id": r["id"],
            "title": r.get("title") or "",
            "status": r.get("status") or "",
            "priority": r.get("priority") or "",
            "action_type": r.get("action_type") or "",
            "rationale": r.get("rationale") or "",
            "ai_proposed": bool(r.get("ai_proposed")),
            "href": f"/recommendations/{r['id']}",
        }
        for r in sq_recommendations
    ]

    assessment_counterevidence = _counterevidence_rows(
        sq_assessments, fact_by_id=fact_by_id, evidence_by_id=evidence_by_id
    )
    evidence_contradictions = _evidence_contradiction_rows(sq_evidence, evidence_by_id=evidence_by_id)

    # Only real authored text -- never a fabricated counterfactual.
    would_change_our_view = sorted(
        {a.get("would_change_our_view") for a in sq_assessments if a.get("would_change_our_view")}
    )

    entity_ids: set[str] = set()
    for group in (sq_evidence, sq_signals, sq_assessments, sq_recommendations, sq_facts):
        for record in group:
            entity_ids.update(record.get("entity_ids") or [])

    company_scope = [
        _party(entities.get(eid))
        for eid in sorted(entity_ids)
        if entities.get(eid, {}).get("entity_type") == "company"
    ]
    variety_scope = [
        _party(entities.get(eid))
        for eid in sorted(entity_ids)
        if entities.get(eid, {}).get("entity_type") == "variety"
    ]
    geography_scope = [
        _party(entities.get(eid))
        for eid in sorted(entity_ids)
        if entities.get(eid, {}).get("entity_type") == "geography"
    ]

    coverage = _coverage_counts(
        fact_count=len(sq_facts),
        evidence_count=len(sq_evidence),
        signal_count=len(sq_signals),
        assessment_count=len(sq_assessments),
        recommendation_count=len(sq_recommendations),
    )
    gaps = [message for key, message in GAP_MESSAGES if coverage[key] == 0]

    # Source trace: every Evidence id any linked Fact/Signal/Assessment/
    # Recommendation actually cites, plus Evidence directly scoped to this
    # question -- never an orphaned executive claim.
    source_evidence_ids: set[str] = {e["id"] for e in sq_evidence if e.get("id")}
    for group in (sq_facts, sq_signals, sq_assessments, sq_recommendations):
        for record in group:
            source_evidence_ids.update(record.get("evidence_ids") or [])
    source_trace = [
        {
            "id": eid,
            "title": evidence_by_id[eid].get("title"),
            "source_name": evidence_by_id[eid].get("source_name"),
            "published_date": evidence_by_id[eid].get("published_date") or evidence_by_id[eid].get("captured_date"),
            "href": f"/evidence/{eid}",
        }
        for eid in source_evidence_ids
        if eid in evidence_by_id
    ]
    source_trace.sort(key=lambda r: str(r.get("published_date") or ""), reverse=True)

    recent_evidence = sorted(
        sq_evidence,
        key=lambda e: str(e.get("published_date") or e.get("captured_date") or ""),
        reverse=True,
    )
    recent_rows = [
        {
            "id": e["id"],
            "title": e.get("title"),
            "date": e.get("published_date") or e.get("captured_date"),
            "source_name": e.get("source_name"),
            "reader_href": f"/intelligence/{e['id']}",
            "href": f"/evidence/{e['id']}",
        }
        for e in recent_evidence
        if e.get("id")
    ][:10]

    berry_ids = [str(b) for b in (sq.get("berry_ids") or []) if b]

    return {
        "id": sq_id,
        "title": sq.get("title") or sq_id,
        "description": sq.get("description") or "",
        "status": sq.get("status") or "",
        "berry_ids": berry_ids,
        "berries": [berry_labels.get(b, b) for b in berry_ids],
        "company_scope": [p for p in company_scope if p],
        "variety_scope": [p for p in variety_scope if p],
        "geography_scope": [p for p in geography_scope if p],
        "facts": fact_rows,
        "assessments": assessment_rows,
        "signals": signal_rows,
        "recommendations": recommendation_rows,
        "would_change_our_view": would_change_our_view,
        "assessment_counterevidence": assessment_counterevidence,
        "evidence_contradictions": evidence_contradictions,
        "gaps": gaps,
        "source_trace": source_trace,
        "recent_evidence": recent_rows,
        "coverage": coverage,
    }
