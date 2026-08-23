"""Executive Intelligence Readout V1 -- a synthesis surface distinct from
both Morning Brief and Landscape:

- Morning Brief (`/brief`) = "what should I inspect today?" -- per-analyst
  triage state, ranked by `rank_item()`'s work-queue heuristics.
- Landscape (`/landscapes`) = "what does the captured competitive
  environment look like?" -- coverage/actors/moves per berry.
- Executive Readout (`/readout`, this module) = "what are the most
  important trusted developments and analyst interpretations I would
  communicate upward?" -- a corpus-wide, not per-analyst, not per-berry,
  read-only synthesis.

Deliberately absent: any invented "so what." If no real Assessment or
Signal exists for something, the honest empty state is shown -- never a
fabricated interpretation. Every surfaced item stays traceable to its
real trust class (Assessment / Signal / Evidence / Source) and is never
flattened into one generic "event" type."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any

WHAT_CHANGED_WINDOW_DAYS = 14
WHAT_CHANGED_LIMIT = 15
SIGNALS_LIMIT = 8
ASSESSMENTS_LIMIT = 8

NO_ASSESSMENT_MESSAGE = "No analyst assessment captured."
NO_SIGNAL_MESSAGE = "No confirmed or proposed Signal captured."


def _confidence_rank(value: str | None) -> int:
    return {"high": 0, "medium": 1, "low": 2}.get(value, 3)


def _strength_rank(value: str | None) -> int:
    return {"strong": 0, "moderate": 1, "weak": 2}.get(value, 3)


def what_changed(
    *,
    published_evidence: list[dict[str, Any]],
    signals: list[dict[str, Any]],
    assessments: list[dict[str, Any]],
    window_days: int = WHAT_CHANGED_WINDOW_DAYS,
    limit: int = WHAT_CHANGED_LIMIT,
) -> dict[str, Any]:
    """Corpus-wide "what changed" -- not per-analyst (Morning Brief's own
    `last_seen_at` state is a different, complementary concept) and not
    berry-scoped (Landscape's `recent_movement` is explicitly per-berry
    and "important-linked" rather than simply recent). Each row keeps its
    real record type; classification is never flattened."""
    cutoff = (date.today() - timedelta(days=window_days)).isoformat()
    rows: list[dict[str, Any]] = []
    for record in published_evidence:
        record_date = record.get("published_date") or record.get("captured_date")
        if record_date and record_date >= cutoff:
            rows.append(
                {
                    "kind": "evidence",
                    "kind_label": "EVIDENCE",
                    "id": record["id"],
                    "title": record.get("title") or record.get("source_name") or record["id"],
                    "date": record_date,
                    "href": f"/evidence/{record['id']}",
                    "reader_href": f"/intelligence/{record['id']}",
                }
            )
    for record in signals:
        record_date = record.get("first_seen") or record.get("last_updated")
        if record_date and record_date >= cutoff:
            rows.append(
                {
                    "kind": "signal",
                    "kind_label": "SIGNAL",
                    "id": record["id"],
                    "title": record.get("title") or record["id"],
                    "date": record_date,
                    "href": f"/signals/{record['id']}",
                }
            )
    for record in assessments:
        record_date = record.get("created_at")
        if record_date and record_date >= cutoff:
            rows.append(
                {
                    "kind": "assessment",
                    "kind_label": "ASSESSMENT",
                    "id": record["id"],
                    "title": record.get("title") or record["id"],
                    "date": record_date,
                    "href": f"/assessments/{record['id']}",
                }
            )
    rows.sort(key=lambda r: r["date"], reverse=True)
    return {"rows": rows[:limit], "window_days": window_days, "has_any": bool(rows), "total_in_window": len(rows)}


def top_signals(signals: list[dict[str, Any]], *, limit: int = SIGNALS_LIMIT) -> list[dict[str, Any]]:
    """Cross-berry equivalent of Landscape's own per-berry `priority_signals`
    -- same sort discipline (strength, then supporting-evidence count),
    just not filtered to one berry."""
    enriched = [
        {**signal, "supporting_evidence_count": len(signal.get("evidence_ids") or [])} for signal in signals
    ]
    enriched.sort(
        key=lambda s: (_strength_rank(s.get("strength")), -s["supporting_evidence_count"], s.get("title") or "")
    )
    return enriched[:limit]


def top_assessments(
    assessments: list[dict[str, Any]],
    recommendations: list[dict[str, Any]],
    *,
    limit: int = ASSESSMENTS_LIMIT,
) -> list[dict[str, Any]]:
    """Cross-berry equivalent of Landscape's own per-berry
    `executive_assessments` -- identical prioritization (non-AI-proposed
    first, then confidence). `why_it_matters`/`would_change_our_view` are
    read as-authored from the Assessment record; an absent field is never
    backfilled with invented text."""
    recommendation_by_assessment: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for recommendation in recommendations:
        for assessment_id in recommendation.get("assessment_ids") or []:
            recommendation_by_assessment[assessment_id].append(recommendation)
    prioritized = sorted(
        assessments,
        key=lambda a: (bool(a.get("ai_proposed")), _confidence_rank(a.get("confidence")), a.get("title") or ""),
    )
    result = []
    for assessment in prioritized[:limit]:
        result.append(
            {
                **assessment,
                "supporting_evidence_count": len(assessment.get("evidence_ids") or []),
                "supporting_fact_count": len(assessment.get("fact_ids") or []),
                "linked_recommendations": recommendation_by_assessment[assessment["id"]],
            }
        )
    return result


def what_we_know(
    *,
    published_evidence: list[dict[str, Any]],
    facts: list[dict[str, Any]],
    coverage_service: Any,
    primary_source_types: set[str],
) -> dict[str, Any]:
    """Cheap, already-proven CoverageQueryService primitives (the same
    ones Landscape's own evidence_coverage uses) applied corpus-wide
    instead of per-berry -- never the expensive extraction-readiness
    classifier (see TD-093/TD-094), which is not safe to run per-request."""
    entity_ids = {eid for fact in facts for eid in (fact.get("entity_ids") or [])}
    source_type_counts, primary_count = coverage_service.evidence_source_breakdown(
        published_evidence, primary_source_types
    )
    confidence_counts, disputed_facts = coverage_service.fact_confidence_and_disputes(entity_ids)
    return {
        "evidence_count": len(published_evidence),
        "fact_count": len(facts),
        "primary_source_count": primary_count,
        "source_type_breakdown": source_type_counts.most_common(6),
        "confidence_distribution": confidence_counts,
        "disputed_fact_count": len(disputed_facts),
    }


def caution(*, disputed_relationship_count: int, unresolved_strategic_question_count: int) -> dict[str, Any]:
    """Explicit, non-inferred caution framing -- carries Landscape V2's
    "coverage is not market activity" discipline into Readout. Never
    written as "low evidence = low competitive activity."."""
    return {
        "disputed_relationship_count": disputed_relationship_count,
        "unresolved_strategic_question_count": unresolved_strategic_question_count,
        "coverage_caveat": (
            "Captured intelligence coverage, not market activity. Most trusted evidence "
            "today is a thin description rather than full article or transcript text -- "
            "a thinly covered berry, company, or geography may simply be under-captured, "
            "not inactive."
        ),
    }
