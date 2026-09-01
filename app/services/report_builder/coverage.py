"""AI-Assisted Report Builder V1 -- structural coverage and gaps.

Plain counts over the packet, plus a small set of defensible zero-count
gap messages -- the same idiom as strategic_question_workspace.py's
GAP_MESSAGES. No LLM is involved anywhere in this module: coverage and
gaps must never be invented or estimated by a model, only counted.

Report Quality & Public Gap Research V1 additionally returns
`dimensions`: an ordered list of AVAILABLE/PARTIAL/MISSING states (see
report_builder.coverage_dimensions) built from the same counts plus a
few packet-derived signals -- `counts`/`gaps` are unchanged and remain
the contract synthesis.py already depends on for its narrative-section
gating.
"""

from __future__ import annotations

from typing import Any

from app.services.report_builder.coverage_dimensions import report_coverage_dimensions

GAP_MESSAGES = (
    ("evidence_count", "No trusted Evidence captured for this scope yet."),
    ("company_count", "No Companies resolved for this scope."),
    ("trusted_variety_count", "No trusted Varieties captured for this scope yet."),
    ("signal_count", "No Signals captured for this scope yet."),
    ("assessment_count", "No analyst Assessment captured for this scope yet."),
)


def report_coverage(
    packet: dict[str, Any],
    *,
    berry_label: str = "",
    geography_labels: tuple[str, ...] = (),
) -> dict[str, Any]:
    if packet.get("strategic_question") is not None:
        sq = packet["strategic_question"]
        counts = {
            "fact_count": len(sq.get("facts") or []),
            "evidence_count": len(sq.get("source_trace") or []),
            "signal_count": len(sq.get("signals") or []),
            "assessment_count": len(sq.get("assessments") or []),
            "recommendation_count": len(sq.get("recommendations") or []),
        }
        gaps = list(sq.get("gaps") or [])
        dimensions = report_coverage_dimensions(
            packet,
            report_type="strategic_question_brief",
            counts=counts,
            berry_label=berry_label,
            geography_labels=geography_labels,
        )
        return {"counts": counts, "gaps": gaps, "dimensions": dimensions}

    counts = {
        "evidence_count": len(packet.get("source_trace") or []),
        "company_count": len(packet.get("companies") or []),
        "trusted_variety_count": len(packet.get("varieties") or []),
        "variety_candidate_count": len(packet.get("variety_candidates") or []),
        "signal_count": len(packet.get("signals") or []),
        "assessment_count": len(packet.get("assessments") or []),
    }
    gaps = [message for key, message in GAP_MESSAGES if counts.get(key, 0) == 0]
    dimensions = report_coverage_dimensions(
        packet,
        report_type=str(packet.get("report_type") or ""),
        counts=counts,
        berry_label=berry_label,
        geography_labels=geography_labels,
    )
    return {"counts": counts, "gaps": gaps, "dimensions": dimensions}
