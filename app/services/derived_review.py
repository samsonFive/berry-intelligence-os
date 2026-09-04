"""Analyst review of DERIVED intelligence objects -- Analyst Dogfood Loop
Phase 4, deliberately narrow.

A challenge to a derived object is not necessarily a challenge to its
source Evidence: Evidence may be correct while a Radar Development's
geography interpretation is wrong, a Competitive Move is supported but
overstated, a Scenario is grounded but analytically unhelpful, or a
Decision Memo section frames real evidence poorly. Confirm/dispute/
defer/dismiss recorded here is the analyst's judgment on that
INTERPRETATION -- it never mutates Evidence/Signal/Assessment trust
state, never rewrites a source record, and never suppresses future
source ingestion. If the analyst believes the underlying SOURCE is bad,
that belongs in the existing evidence-side review flow instead (see
source_review_href below).

This reuses app.services.analyst_queue's existing dimension/state-store/
review-event mechanism exactly as every other analyst workflow does (a
"derived_review" dimension alongside reading/testing/monitoring/
proposals/signals/pending) -- not a second review subsystem.
"""

from __future__ import annotations

from typing import Any, Mapping

OBJECT_TYPES = ("radar_development", "competitive_move", "watchtower_alert", "decision_memo_section")

OBJECT_TYPE_LABELS: dict[str, str] = {
    "radar_development": "Development",
    "competitive_move": "Competitive Move",
    "watchtower_alert": "Watchtower Alert",
    "decision_memo_section": "Decision Memo section",
}

# Mission-specified reasons for disputing a derived object (Scenario
# sections named explicitly, but the same generic reasons apply to any
# supported object type -- one shared vocabulary, not a scenario-specific
# review subsystem).
DISPUTE_REASONS: tuple[tuple[str, str], ...] = (
    ("not_useful", "Not useful"),
    ("overstated", "Overstated"),
    ("missing_counterevidence", "Missing counterevidence"),
    ("wrong_scope", "Wrong scope"),
    ("source_does_not_support_interpretation", "Source does not support this interpretation"),
)
_DISPUTE_REASON_LABELS = dict(DISPUTE_REASONS)


def section_review_key(report_id: str, section_id: str) -> str:
    """Decision Memo sections are reviewed as a whole section (mission:
    "review the SECTION as the derived object, not every sentence/bullet
    independently"), and a section_id alone is only unique within one
    report -- so the review-queue item_id is the composite of both."""
    return f"{report_id}:{section_id}"


def source_review_href(trusted_context: list[Mapping[str, Any]] | Mapping[str, Any] | None) -> str | None:
    """A link into the EXISTING evidence-side review flow -- only when
    this object already carries one via its own trusted_context (already
    populated from published Evidence at compose time by Radar/Moves/
    Watchtower), never a fabricated linkage."""
    rows = trusted_context or []
    if isinstance(rows, Mapping):
        rows = [rows]
    for row in rows:
        href = row.get("href") if isinstance(row, Mapping) else None
        if href:
            return str(href)
    return None


def present_derived_review(
    item_id: str,
    *,
    object_type: str,
    state: Mapping[str, Mapping[str, Mapping[str, Any]]],
    return_to: str,
    trusted_context: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Template-ready context for the shared _derived_review.html partial."""
    from app.services.analyst_queue import DERIVED_REVIEW_LABELS, derived_review_entry, derived_review_state

    entry = derived_review_entry(item_id, dict(state))
    status = derived_review_state(item_id, dict(state))
    reason = entry.get("reason_category")
    return {
        "object_type": object_type,
        "object_type_label": OBJECT_TYPE_LABELS.get(object_type, object_type),
        "item_id": item_id,
        "state": status,
        "label": DERIVED_REVIEW_LABELS.get(status, status),
        "reviewer": str(entry.get("reviewer") or ""),
        "updated_at": str(entry.get("updated_at") or ""),
        "review_notes": str(entry.get("review_notes") or ""),
        "reason_category": reason,
        "reason_category_label": _DISPUTE_REASON_LABELS.get(str(reason or ""), ""),
        "dispute_reasons": DISPUTE_REASONS,
        "source_review_href": source_review_href(trusted_context),
        "return_to": return_to,
    }
