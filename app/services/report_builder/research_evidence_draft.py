"""Report Quality & Public Gap Research V1 -- promoting one reviewed
external research finding into the existing Evidence draft/review queue.

Mirrors app.services.cpvo_registry.build_cpvo_review_draft's shape and
epistemic discipline: an unreviewed public web-search citation proves
only that a page exists saying something, nothing about its accuracy.
The resulting dict is written through the same generic mechanism every
other public-source draft uses (app.main.save_draft -> inbox/evidence/),
so it appears in the existing /review queue unmodified -- no new review
queue, no new trust-promotion plumbing. A human analyst still makes the
actual trust decision at /review/{draft_id}/publish, exactly as for a
CPVO filing or a patent record.

This module never calls a network provider and never mutates canonical
Evidence directly -- it only shapes a `status: "draft"` dict."""

from __future__ import annotations

import secrets
from typing import Any

from app.services.transcript_evidence import PRIORITY_NONE

RESEARCH_DOES_NOT_PROVE = (
    "that this claim is accurate -- it is an unreviewed web-search citation, not a verified fact",
    "that the cited page is an authoritative or primary source",
    "market scale, commercial success, or that any figure cited is current",
    "that this finding was independently corroborated by a second source",
)


def build_perplexity_research_draft(
    finding: dict[str, Any],
    *,
    berry_id: str | None,
    geography_ids: tuple[str, ...],
    entity_ids: tuple[str, ...],
    captured_date: str,
) -> dict[str, Any]:
    """`finding` is one entry from a report's `external_research_appendix`
    (title/url/snippet/gap_label/provider/retrieved_at). The caller is
    responsible for having the analyst mark it reviewed in the report
    workspace before calling this -- promotion itself performs no trust
    check beyond what the schema requires."""
    draft_id = "ev-perplexity-" + secrets.token_hex(8)
    gap_label = finding.get("gap_label") or "a research gap identified in a report"
    title = finding.get("title") or finding.get("url") or "External public research finding"
    summary = (
        f"Public web-search finding for {gap_label!r}, retrieved via Perplexity public gap research: "
        f"{(finding.get('snippet') or '').strip()[:600]}"
    )
    why = (
        "An analyst selected this finding from unreviewed public research and chose to propose it for "
        "Evidence review. It is a web-search citation, not this system's own trusted source capture -- "
        "verify against the source URL before publishing."
    )
    return {
        "id": draft_id,
        "record_type": "evidence",
        "status": "draft",
        "review_state": "in_review",
        "source_authority": "low",
        "verification_state": "unverified",
        "does_not_prove": list(RESEARCH_DOES_NOT_PROVE),
        "relevance_tier": "adjacent",
        "intake_type": "perplexity_public_research",
        "source_type": "perplexity_public_research",
        "title": title,
        "source_name": finding.get("provider") or "Perplexity public research",
        "source_url": finding.get("url") or "",
        "published_date": finding.get("publication_date"),
        "event_date": None,
        "captured_date": captured_date,
        "summary": summary,
        "why_it_matters": why,
        "submitted_by": "report-builder-public-research",
        "berry_ids": [berry_id] if berry_id else [],
        "geography_ids": list(geography_ids),
        "entity_ids": list(entity_ids),
        "fact_ids": [],
        "relationship_ids": [],
        "strategic_question_ids": [],
        "tags": [t for t in ("external-research", "perplexity", finding.get("gap_key")) if t],
        "auto_captured": False,
        "validated": False,
        "source_id": None,
        "evidence_role": "publication_artifact",
        "priority": dict(PRIORITY_NONE),
    }
