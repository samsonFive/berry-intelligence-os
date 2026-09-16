"""Publication Review Command Service V1 -- pure domain model (Slice 1).

Implements `design/publication-review-contract-v1`'s `STATE-MACHINE.md`,
`COMMAND-CONTRACTS.md`, and the eligibility content matrix in
`PUBLICATION-REVIEW-CONTRACT-V1.md`. Pure functions and frozen dataclasses
only -- no filesystem, no repository, no HTTP, no clock (a caller-supplied
timestamp is threaded through where one is needed, so this module has no
observable side effect at all and is trivial to test exhaustively).

Reuses existing, already-tested vocabulary rather than inventing a
competing one:
  - `app.services.article_dedup.normalize_canonical_url/normalize_title/
     find_duplicate_article` for deterministic publication identity and
     duplicate detection -- the contract's own "normalized canonical URL
     where available; otherwise exact normalized title + source ID +
     publication date. No fuzzy identity" is exactly what that module
     already does.
  - `app.services.source_body.classify_source_body` and
     `app.services.source_completeness.source_completeness` for content
     classification (`FULL_ARTICLE`/`FULL_TRANSCRIPT`/`STRUCTURED_REGISTRY`/
     `THIN_DESCRIPTION`/`NO_CONTENT`, failure categories, retryability) --
     the exact vocabulary `ReviewPublishService`/`source_body.py` already
     use, not a second classification scheme.

Nothing in this module writes to `data/` or `inbox/`, calls
`ReviewPublishService.publish()`, or creates any canonical record.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from app.services.article_dedup import find_duplicate_article, normalize_canonical_url, normalize_title
from app.services.source_body import classify_source_body

# --------------------------------------------------------------------------
# Review states (STATE-MACHINE.md)
# --------------------------------------------------------------------------

PENDING_REVIEW = "pending_review"
CORRECTION_REQUIRED = "correction_required"
DEFERRED = "deferred"
APPROVED = "approved"
REJECTED = "rejected"
SUPERSEDED_DUPLICATE = "superseded_duplicate"

REVIEW_STATES: tuple[str, ...] = (
    PENDING_REVIEW, CORRECTION_REQUIRED, DEFERRED, APPROVED, REJECTED, SUPERSEDED_DUPLICATE,
)
TERMINAL_STATES = frozenset({APPROVED, REJECTED, SUPERSEDED_DUPLICATE})
REVISITABLE_STATES = frozenset({PENDING_REVIEW, CORRECTION_REQUIRED, DEFERRED})

# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------

CMD_APPROVE = "approve_publication"
CMD_REJECT = "reject_publication"
CMD_DEFER = "defer_publication"
CMD_REQUEST_CORRECTION = "request_publication_correction"
CMD_SUBMIT_CORRECTION = "submit_publication_correction"
CMD_RETURN_TO_REVIEW = "return_publication_to_review"
CMD_SUPERSEDE_DUPLICATE = "supersede_publication_duplicate"
CMD_REVISE = "revise_publication_draft"

DECISION_COMMANDS = frozenset(
    {CMD_APPROVE, CMD_REJECT, CMD_DEFER, CMD_REQUEST_CORRECTION, CMD_SUPERSEDE_DUPLICATE, CMD_RETURN_TO_REVIEW}
)
COMMANDS_REQUIRING_REASON = frozenset({CMD_REJECT, CMD_REQUEST_CORRECTION, CMD_DEFER})

# Permitted transitions: (from_state, command) -> to_state. Exhaustive --
# any (state, command) pair not listed here is an invalid transition.
TRANSITIONS: dict[tuple[str, str], str] = {
    (PENDING_REVIEW, CMD_APPROVE): APPROVED,
    (PENDING_REVIEW, CMD_REJECT): REJECTED,
    (PENDING_REVIEW, CMD_DEFER): DEFERRED,
    (PENDING_REVIEW, CMD_REQUEST_CORRECTION): CORRECTION_REQUIRED,
    (PENDING_REVIEW, CMD_SUPERSEDE_DUPLICATE): SUPERSEDED_DUPLICATE,
    (DEFERRED, CMD_RETURN_TO_REVIEW): PENDING_REVIEW,
    (DEFERRED, CMD_REJECT): REJECTED,
    (CORRECTION_REQUIRED, CMD_SUBMIT_CORRECTION): PENDING_REVIEW,
    (CORRECTION_REQUIRED, CMD_REJECT): REJECTED,
}


def permitted_commands(state: str) -> tuple[str, ...]:
    """Every command permitted from `state`, per the contract's own
    transition table -- used both to validate an incoming command and to
    tell a caller what it may do next."""
    return tuple(sorted({command for (from_state, command) in TRANSITIONS if from_state == state}))


def next_state(state: str, command: str) -> str | None:
    """The resulting state for `command` from `state`, or None if that
    transition is not permitted (an `invalid_transition` case)."""
    return TRANSITIONS.get((state, command))


def is_valid_transition(state: str, command: str) -> bool:
    return (state, command) in TRANSITIONS


# --------------------------------------------------------------------------
# Eligibility (PUBLICATION-REVIEW-CONTRACT-V1.md's content matrix)
# --------------------------------------------------------------------------

ELIGIBLE = "eligible"
ELIGIBLE_WITH_WARNINGS = "eligible_with_warnings"
BLOCKED = "blocked"

BASIS_FULL_ARTICLE = "full_article"
BASIS_PARTIAL_ARTICLE = "partial_article"
BASIS_FULL_TRANSCRIPT = "full_transcript"
BASIS_STRUCTURED_REGISTRY = "structured_registry"
BASIS_LIMITED_CONTENT = "limited_content"
APPROVAL_BASES: tuple[str, ...] = (
    BASIS_FULL_ARTICLE, BASIS_PARTIAL_ARTICLE, BASIS_FULL_TRANSCRIPT, BASIS_STRUCTURED_REGISTRY, BASIS_LIMITED_CONTENT,
)

# Blocker codes -- one per content-matrix "Blocked" row, plus structural
# blockers (state/schema/entity) the contract's approval invariants add.
BLOCKER_NAVIGATION_ONLY_SHELL = "navigation_only_shell"
BLOCKER_RETRYABLE_ACQUISITION = "retryable_acquisition_failure"
BLOCKER_UNSUPPORTED_SOURCE = "unsupported_source"
BLOCKER_MISSING_PROVENANCE = "missing_or_invalid_provenance"
BLOCKER_DETERMINISTIC_DUPLICATE = "deterministic_duplicate"
BLOCKER_AMBIGUOUS_DUPLICATE = "ambiguous_duplicate"
BLOCKER_NOT_PENDING_REVIEW = "not_pending_review"
BLOCKER_UNRESOLVED_ENTITY_LINK = "unresolved_entity_link"
BLOCKER_INVALID_SCHEMA = "invalid_schema"
BLOCKER_RETRYABLE_PENDING = "retryable_attempt_still_pending"

# Warning codes (contract's own "mandatory warnings" list).
WARNING_PARTIAL_CONTENT = "partial_content"
WARNING_UNKNOWN_DATE = "unknown_or_historical_publication_date"
WARNING_LOW_AUTHORITY = "low_source_authority"
WARNING_UNVERIFIED_ENTITY_SUGGESTION = "unverified_entity_suggestion"
WARNING_AI_ENRICHMENT = "ai_generated_enrichment_present"
WARNING_THIN_CONTENT = "thin_content_limited_publication"
WARNING_UNRESOLVED_ATTRIBUTION = "unresolved_optional_attribution"
WARNING_UPGRADE_AVAILABLE = "body_or_transcript_upgrade_available"

# body_state (classify_source_body's own vocabulary) -> (result, allowed bases, warnings)
_BODY_STATE_POLICY: dict[str, tuple[str, tuple[str, ...], tuple[str, ...]]] = {
    "body_available": (ELIGIBLE, (BASIS_FULL_ARTICLE,), ()),
    "body_partial": (ELIGIBLE_WITH_WARNINGS, (BASIS_PARTIAL_ARTICLE,), (WARNING_PARTIAL_CONTENT,)),
    "transcript_available": (ELIGIBLE, (BASIS_FULL_TRANSCRIPT,), ()),
    "description_only": (
        ELIGIBLE_WITH_WARNINGS, (BASIS_LIMITED_CONTENT,),
        (WARNING_THIN_CONTENT, WARNING_UPGRADE_AVAILABLE),
    ),
}


@dataclass(frozen=True)
class EligibilityResult:
    """A pure, side-effect-free judgment: `eligible`, `eligible_with_warnings`,
    or `blocked`, with typed blockers/warnings and the approval bases this
    draft may legitimately be approved under. Never mutates anything."""

    result: str
    content_class: str
    body_state: str
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    permitted_approval_bases: tuple[str, ...] = ()
    duplicate_of: str | None = None
    ambiguous_duplicate_candidates: tuple[str, ...] = ()

    @property
    def approvable(self) -> bool:
        return self.result != BLOCKED and bool(self.permitted_approval_bases)

    def as_dict(self) -> dict[str, Any]:
        return {
            "result": self.result,
            "content_class": self.content_class,
            "body_state": self.body_state,
            "blockers": list(self.blockers),
            "warnings": list(self.warnings),
            "permitted_approval_bases": list(self.permitted_approval_bases),
            "duplicate_of": self.duplicate_of,
            "ambiguous_duplicate_candidates": list(self.ambiguous_duplicate_candidates),
        }


def _structured_registry(record: dict[str, Any]) -> bool:
    from app.services.source_completeness import REGISTRY_SOURCE_TYPES, STRUCTURED_FIELDS

    return (
        str(record.get("source_type") or "").casefold() in REGISTRY_SOURCE_TYPES
        or any(isinstance(record.get(field_name), dict) for field_name in STRUCTURED_FIELDS)
    )


def _required_provenance_present(draft: dict[str, Any]) -> list[str]:
    """Missing/invalid provenance fields the contract requires for every
    approvable draft: resolvable Source id, title, captured date,
    submitted-by, and (for a web_article/podcast draft) a source URL."""
    missing = []
    if not draft.get("id"):
        missing.append("id")
    if not draft.get("title"):
        missing.append("title")
    if not draft.get("captured_date"):
        missing.append("captured_date")
    if not draft.get("submitted_by"):
        missing.append("submitted_by")
    if not draft.get("source_id") and not draft.get("source_url") and not _structured_registry(draft):
        missing.append("source_id_or_source_url_or_structured_locator")
    return missing


def check_eligibility(
    draft: dict[str, Any],
    *,
    existing_trusted_and_pending: list[dict[str, Any]] | None = None,
    resolvable_entity_ids: frozenset[str] = frozenset(),
) -> EligibilityResult:
    """Pure eligibility check over one draft. Never mutates `draft`.

    `existing_trusted_and_pending` should include both trusted publications
    and other pending drafts (the contract's own duplicate check spans
    both) -- reused verbatim via `article_dedup.find_duplicate_article`.
    `resolvable_entity_ids` is the set of canonical entity ids that
    currently exist; any `entity_ids` on the draft not in this set is an
    unresolved link.
    """
    existing = existing_trusted_and_pending or []

    if draft.get("evidence_role") not in (None, "publication_artifact"):
        return EligibilityResult(
            result=BLOCKED, content_class="NOT_APPLICABLE", body_state="not_applicable",
            blockers=(BLOCKER_UNSUPPORTED_SOURCE,),
        )

    missing_provenance = _required_provenance_present(draft)
    body = classify_source_body(draft)
    body_state = body["state"]
    from app.services.source_completeness import source_completeness as _source_completeness

    completeness = _source_completeness(draft)
    content_class = completeness["class"]
    failure_category = completeness.get("failure_category")
    retryable = bool(completeness.get("retryable"))

    blockers: list[str] = []
    warnings: list[str] = []

    if missing_provenance:
        blockers.append(BLOCKER_MISSING_PROVENANCE)

    unresolved_links = [eid for eid in (draft.get("entity_ids") or []) if eid not in resolvable_entity_ids]
    if unresolved_links:
        blockers.append(BLOCKER_UNRESOLVED_ENTITY_LINK)

    # Duplicate identity check -- exact only, never fuzzy.
    duplicate_of = find_duplicate_article(
        {
            "canonical_url": draft.get("source_url"),
            "resolved_canonical_url": (draft.get("article") or {}).get("final_url"),
            "title": draft.get("title"),
            "source_id": draft.get("source_id"),
            "published_date": draft.get("published_date"),
            "raw_metadata": draft.get("raw_metadata") or {},
        },
        existing_records=[r for r in existing if r.get("id") != draft.get("id")],
    )
    if duplicate_of:
        blockers.append(BLOCKER_DETERMINISTIC_DUPLICATE)

    permitted_bases: tuple[str, ...] = ()
    result = BLOCKED

    if _structured_registry(draft) and body_state not in {"interstitial"}:
        result, permitted_bases = ELIGIBLE, (BASIS_STRUCTURED_REGISTRY,)
    elif body_state in _BODY_STATE_POLICY:
        result, permitted_bases, extra_warnings = _BODY_STATE_POLICY[body_state]
        warnings.extend(extra_warnings)
    elif body_state == "interstitial":
        blockers.append(BLOCKER_NAVIGATION_ONLY_SHELL)
    elif retryable:
        # `classify_source_body`'s own `access_limited` state only fires
        # for `discovery_provenance.failure_category` -- real acquisition
        # output stores `acquisition_failure_category` instead (see
        # `source_completeness()`, which checks both keys). Trust
        # `source_completeness`'s already-correct `retryable` flag here
        # rather than depending on that narrower, effectively-dead
        # `access_limited` branch for real drafts.
        blockers.append(BLOCKER_RETRYABLE_ACQUISITION)
    elif body_state in {"access_limited", "body_unavailable"}:
        blockers.append(BLOCKER_NAVIGATION_ONLY_SHELL)
    else:
        blockers.append(BLOCKER_UNSUPPORTED_SOURCE)

    if not draft.get("published_date"):
        warnings.append(WARNING_UNKNOWN_DATE)
    if (draft.get("ai_enrichment") or {}).get("model_provenance", {}).get("status") or draft.get("ai_enrichment"):
        warnings.append(WARNING_AI_ENRICHMENT)
    if draft.get("entity_link_suggestions"):
        warnings.append(WARNING_UNVERIFIED_ENTITY_SUGGESTION)

    if blockers:
        result = BLOCKED
        permitted_bases = ()

    return EligibilityResult(
        result=result,
        content_class=content_class,
        body_state=body_state,
        blockers=tuple(dict.fromkeys(blockers)),
        warnings=tuple(dict.fromkeys(warnings)),
        permitted_approval_bases=permitted_bases,
        duplicate_of=duplicate_of,
    )


# --------------------------------------------------------------------------
# Deterministic identity and review-content digest
# --------------------------------------------------------------------------


def publication_identity_key(draft: dict[str, Any]) -> str:
    """Derived from normalized canonical URL where available; otherwise
    exact normalized title + source ID + publication date. No fuzzy
    identity -- reuses `article_dedup`'s own normalizers verbatim."""
    url = normalize_canonical_url(draft.get("source_url")) or normalize_canonical_url(
        (draft.get("article") or {}).get("final_url")
    )
    if url:
        return f"url:{url}"
    title = normalize_title(draft.get("title"))
    source_id = str(draft.get("source_id") or "")
    published = str(draft.get("published_date") or "")[:10]
    return f"tsd:{title}|{source_id}|{published}"


_DIGEST_FIELDS = (
    "title", "source_id", "source_name", "source_url", "published_date", "captured_date",
    "summary", "evidence_role", "entity_ids", "berry_ids", "geography_ids", "warnings",
)


def _content_hashes(draft: dict[str, Any]) -> dict[str, str | None]:
    article = draft.get("article") if isinstance(draft.get("article"), dict) else {}
    transcript = draft.get("transcript") if isinstance(draft.get("transcript"), dict) else {}
    source_artifact = draft.get("source_artifact") if isinstance(draft.get("source_artifact"), dict) else {}
    return {
        "article_content_sha256": article.get("content_sha256"),
        "transcript_content_sha256": transcript.get("content_sha256"),
        "source_artifact_content_sha256": source_artifact.get("content_sha256"),
    }


def compute_review_content_digest(
    draft: dict[str, Any], *, eligibility: EligibilityResult | None = None,
) -> str:
    """SHA-256 over a canonical (sorted-key, compact) serialization of
    every review-relevant field named by the contract: title, source
    identity/URL, publication/capture dates, summary, body/transcript
    hashes, content class, acquisition outcome, entity links, warnings,
    and source provenance. Any edit to a review-relevant field changes
    this digest -- callers must recompute after every revision."""
    payload: dict[str, Any] = {field_name: draft.get(field_name) for field_name in _DIGEST_FIELDS}
    payload.update(_content_hashes(draft))
    payload["discovery_provenance"] = draft.get("discovery_provenance") or {}
    payload["source_completeness_class"] = (draft.get("source_completeness") or {}).get("class")
    payload["acquisition_failure_category"] = (draft.get("discovery_provenance") or {}).get(
        "acquisition_failure_category"
    )
    if eligibility is not None:
        payload["eligibility_content_class"] = eligibility.content_class
        payload["eligibility_warnings"] = sorted(eligibility.warnings)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


_PROVENANCE_FIELDS = ("source_id", "source_url", "source_name", "media_format")


def compute_provenance_digest(draft: dict[str, Any]) -> str:
    """A digest over acquisition/source provenance specifically -- kept
    separate from `compute_review_content_digest` per the contract's own
    distinct "content digest" vs "provenance digest" fields, so a caller
    can tell "the reviewed material changed" apart from "where it came
    from changed" (e.g. a corrected `source_id` after a mis-attributed
    draft) even when one happens without the other."""
    payload: dict[str, Any] = {field_name: draft.get(field_name) for field_name in _PROVENANCE_FIELDS}
    payload["discovery_provenance"] = draft.get("discovery_provenance") or {}
    payload["extraction_provenance"] = draft.get("extraction_provenance") or {}
    payload["transcript_provenance"] = draft.get("transcript_provenance") or {}
    payload["artifact_locator"] = draft.get("artifact_locator") or {}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# Command envelope / results (COMMAND-CONTRACTS.md)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class CommandEnvelope:
    """Every state-changing command's common fields. The service derives
    timestamps, command IDs, permissions, current state, and repository
    locations -- callers cannot supply or override them."""

    draft_id: str
    actor_id: str
    idempotency_key: str
    expected_version: int
    reviewed_content_digest: str
    source_surface: str = "review_command_service"
    comment: str | None = None


ERROR_INVALID_COMMAND = "invalid_command"
ERROR_UNAUTHENTICATED = "unauthenticated"
ERROR_FORBIDDEN = "forbidden"
ERROR_DRAFT_NOT_FOUND = "draft_not_found"
ERROR_STALE_REVIEW = "stale_review"
ERROR_INVALID_TRANSITION = "invalid_transition"
ERROR_IDEMPOTENCY_CONFLICT = "idempotency_conflict"
ERROR_IDENTITY_CONFLICT = "identity_conflict"
ERROR_INELIGIBLE = "ineligible_for_approval"
ERROR_ALREADY_DECIDED = "already_decided"
ERROR_PROMOTION_INCOMPLETE = "promotion_incomplete"


class CommandError(Exception):
    """A structured, typed command failure -- one of COMMAND-CONTRACTS.md's
    own error codes. Never raised for a successful idempotent replay."""

    def __init__(self, code: str, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


@dataclass(frozen=True)
class CommandResult:
    command_id: str
    prior_state: str
    resulting_state: str
    resulting_version: int
    event_id: str | None
    publication_id: str | None = None
    warnings: tuple[str, ...] = ()
    idempotent_replay: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "command_id": self.command_id,
            "prior_state": self.prior_state,
            "resulting_state": self.resulting_state,
            "resulting_version": self.resulting_version,
            "event_id": self.event_id,
            "publication_id": self.publication_id,
            "warnings": list(self.warnings),
            "idempotent_replay": self.idempotent_replay,
        }
