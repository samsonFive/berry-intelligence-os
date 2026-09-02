"""Trusted Evidence Semantics Repair V1.

Restores a clean distinction the trust model already intends but did not
enforce for ordinary Publications:

    SOURCE DECISION      -- "is this source item worth retaining as an
                             approved Publication?"
    EVIDENCE CLAIM DECISION -- "which explicit factual claim from this
                             source should enter trusted Evidence?"

Publication Promote (`/review/{id}/publish`, unchanged) still creates the
Evidence record -- that part of the trust model is not being redesigned.
What changes is what that record's presence *means*: a published
`evidence_role: "publication_artifact"` record with no linked Fact is an
APPROVED SOURCE, not yet TRUSTED EVIDENCE in the fuller sense. It becomes
TRUSTED EVIDENCE only once at least one Fact is explicitly analyst-
approved against it (`review_publish.ReviewPublishService.approve_claim`).

This module holds the two small, pure pieces of that repair:
`evidence_trust_tier()` (classification, used by presentation code) and
`prepare_candidate_proposition()` (deterministic, no-LLM claim-statement
drafting so the analyst never has to retype the article -- see the
module docstring's FAST PATH section in the mission brief this
implements).

SCOPE, DELIBERATELY NARROW (legacy audit, not a system redesign):
`evidence_trust_tier()` only ever returns something other than
"reviewed_evidence" for `evidence_role == "publication_artifact"`
records -- the ~17-record population this session's own work created,
100% still lacking a Fact today. The 1,268 legacy `evidence_role: None`
records (only 119 of which happen to carry `fact_ids` themselves) are
NOT reclassified by this change and are NOT touched by it: grandfathered
as "reviewed_evidence" unconditionally, exactly the same as before this
mission. Retroactively re-auditing that much larger population is a
separate, larger decision this mission does not make -- see
docs/v2/TRUSTED-EVIDENCE-SEMANTICS-REPAIR-V1.md's legacy section.
"""

from __future__ import annotations

from typing import Any

TIER_APPROVED_SOURCE = "approved_source"
TIER_TRUSTED_EVIDENCE = "trusted_evidence"
TIER_REVIEWED_EVIDENCE = "reviewed_evidence"  # legacy / atomic_evidence, unconditional, untouched

TRUST_TIER_LABELS: dict[str, str] = {
    TIER_APPROVED_SOURCE: "APPROVED SOURCE",
    TIER_TRUSTED_EVIDENCE: "TRUSTED EVIDENCE",
    TIER_REVIEWED_EVIDENCE: "REVIEWED EVIDENCE",
}

ORIGIN_PUBLICATION_PROSE = "publication_claim_review"
ORIGIN_STRUCTURED_REGISTRY = "structured_registry_claim_review"

STRUCTURED_REGISTRY_INTAKE_TYPES = frozenset({"pvr_filing", "patent_filing"})


def evidence_trust_tier(record: dict[str, Any]) -> str:
    """Deterministic, presentation-layer only -- never mutates data.
    Publication-derived records (the population this mission's repair
    concerns) need a Fact to count as TRUSTED EVIDENCE; every other
    existing record type is grandfathered unchanged."""
    if record.get("evidence_role") != "publication_artifact":
        return TIER_REVIEWED_EVIDENCE
    if record.get("fact_ids"):
        return TIER_TRUSTED_EVIDENCE
    return TIER_APPROVED_SOURCE


def trust_tier_label(record: dict[str, Any]) -> str:
    return TRUST_TIER_LABELS[evidence_trust_tier(record)]


def _clean(text: str) -> str:
    return " ".join(str(text or "").strip().split())


def _structured_registry_proposition(draft: dict[str, Any]) -> str | None:
    """Build a single deterministic sentence from already-extracted
    structured fields (never free prose) for CPVO/patent-style filings.
    Registry authority does not mean automatic trust -- this only
    prepares the candidate text an analyst still explicitly approves."""
    intake_type = draft.get("intake_type")
    if intake_type == "pvr_filing":
        filing = draft.get("cpvo_filing") or {}
        denomination = filing.get("denomination") or filing.get("cultivar_name") or draft.get("title") or "This variety"
        species = filing.get("species_name")
        applicants = filing.get("applicants") or []
        applicant_text = ", ".join(str(a) for a in applicants) if applicants else "an unstated applicant"
        status = filing.get("title_status") or "an unstated"
        granting_date = filing.get("granting_date")
        parts = [f"{denomination}"]
        if species:
            parts[0] += f" ({species})"
        parts.append(f"was filed for Community Plant Variety Right by {applicant_text}")
        if granting_date:
            parts.append(f"with title status '{status}' as of {granting_date}")
        else:
            parts.append(f"with title status '{status}'")
        return _clean(". ".join([" ".join(parts)]) + ".")
    if intake_type == "patent_filing":
        filing = draft.get("patent_filing") or {}
        cultivar = filing.get("cultivar_name") or draft.get("title") or "This variety"
        assignees = filing.get("assignees") or []
        assignee_text = ", ".join(str(a) for a in assignees) if assignees else "an unstated assignee"
        pub_number = filing.get("publication_number")
        grant_date = filing.get("grant_date") or filing.get("publication_date")
        sentence = f"{cultivar} is the subject of plant patent {pub_number or '(number unstated)'}, assigned to {assignee_text}"
        if grant_date:
            sentence += f", granted/published {grant_date}"
        return _clean(sentence + ".")
    return None


def prepare_candidate_proposition(draft: dict[str, Any]) -> tuple[str, str]:
    """Returns (candidate_statement, origin). Never invents facts not
    already present on the draft: structured filings build a sentence
    strictly from their own already-extracted fields; ordinary prose
    Publications use the draft's own `why_it_matters` (falling back to
    `summary`) as the starting candidate -- text the analyst already saw
    and is now being asked to explicitly stand behind, edit, or reject,
    not text this function is authoring itself."""
    structured = _structured_registry_proposition(draft)
    if structured:
        return structured, ORIGIN_STRUCTURED_REGISTRY
    candidate = _clean(draft.get("why_it_matters") or draft.get("summary") or draft.get("title") or "")
    return candidate, ORIGIN_PUBLICATION_PROSE
