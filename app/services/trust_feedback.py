"""Private, auditable analyst feedback over existing intelligence records.

This service adds a projection to the existing analyst queue state and appends
events through the existing review-event ledger. It never rewrites or deletes
Evidence, discoveries, Source records, or acquisition outcomes. Governed
promotion is dependency-injected so callers must use the existing publication
approval architecture rather than gaining a second path into trusted data.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Mapping

from app.services.analyst_queue import load_state, save_state
from app.services.evidence_claim_review import (
    TIER_APPROVED_SOURCE,
    evidence_trust_tier,
)
from app.services.review_events import (
    EventAppendResult,
    append_review_event,
    load_review_events,
    remove_created_event,
)
from app.services.source_body import classify_source_body

WORKFLOW = "trust_feedback"
STATE_BUCKET = "trust_feedback"
STATE_UNREVIEWED = "unreviewed"
STATE_RETAINED = "retained"
STATE_PENDING_PROMOTION = "pending_promotion"
STATE_APPROVED_SOURCE = "approved_source"
STATE_TRUSTED = "trusted_intelligence"
STATE_EXCLUDED = "excluded"
STATE_DEFERRED = "deferred"

ACTIONS = frozenset({"promote", "exclude", "defer", "undo"})
OBJECT_TYPES = frozenset(
    {"evidence", "publication_draft", "discovered_media", "signal", "assessment"}
)
PROMOTION_INTENTS = frozenset(
    {"relevant", "retain_for_review", "monitor", "governed_promotion"}
)
EXCLUSION_REASONS = frozenset(
    {
        "irrelevant",
        "duplicate",
        "wrong_entity",
        "wrong_berry",
        "wrong_region",
        "wrong_berry_or_region",
        "weak_source",
        "unreadable",
        "outdated",
        "misleading_extraction",
        "other",
    }
)
UNUSABLE_OUTCOMES = frozenset(
    {
        "cookie_or_consent_page",
        "access_denied",
        "bot_wall",
        "empty_page",
        "navigation_only_shell",
        "http_failure",
        "network_failure",
        "parser_failure",
        "unsupported_source",
        "retryable_failure",
        "manual_acquisition_required",
    }
)
TERMINAL_PROMOTION_STATES = frozenset({STATE_APPROVED_SOURCE, STATE_TRUSTED})


class FeedbackError(ValueError):
    """Base class for safe, caller-visible feedback rejections."""


class StaleFeedbackVersion(FeedbackError):
    pass


class IdempotencyConflict(FeedbackError):
    pass


class InvalidUndo(FeedbackError):
    pass


@dataclass(frozen=True)
class FeedbackActor:
    actor_id: str
    permissions: frozenset[str] = field(default_factory=lambda: frozenset({"submit_feedback"}))


@dataclass(frozen=True)
class FeedbackRequest:
    action: str
    object_id: str
    object_type: str
    actor: FeedbackActor
    idempotency_key: str
    expected_version: int | None
    source_surface: str
    intent: str | None = None
    reason: str | None = None
    original_event_id: str | None = None


@dataclass(frozen=True)
class PromotionOutcome:
    ok: bool
    resulting_trust_state: str | None = None
    trusted_record_id: str | None = None
    blockers: tuple[str, ...] = ()


@dataclass(frozen=True)
class EligibilityResult:
    eligible: bool
    blockers: tuple[str, ...]
    limitations: tuple[str, ...]
    content_state: str
    date_class: str
    current_news_eligible: bool


@dataclass(frozen=True)
class FeedbackResult:
    state: str
    version: int
    blockers: tuple[str, ...]
    event: Mapping[str, Any]
    event_created: bool
    idempotent_replay: bool
    trusted_record_id: str | None
    projection: Mapping[str, Any]


PromotionHandler = Callable[[Mapping[str, Any], FeedbackActor], PromotionOutcome]


def _state_key(actor_id: str, object_type: str, object_id: str) -> str:
    raw = f"{actor_id}\x1f{object_type}\x1f{object_id}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _date_class(record: Mapping[str, Any], *, today: date, current_window_days: int) -> str:
    value = record.get("published_date")
    if not value:
        return "unknown"
    try:
        published = date.fromisoformat(str(value)[:10])
    except ValueError:
        return "unknown"
    return "current" if published >= today - timedelta(days=current_window_days) else "historical"


def check_eligibility(
    record: Mapping[str, Any],
    *,
    acquisition_outcome: Mapping[str, Any] | None = None,
    today: date | None = None,
    current_window_days: int = 90,
) -> EligibilityResult:
    """Explain whether a record may enter the governed trust workflow."""

    blockers: list[str] = []
    limitations: list[str] = []
    outcome = acquisition_outcome or (
        record.get("acquisition_outcome")
        if isinstance(record.get("acquisition_outcome"), Mapping)
        else {}
    )
    outcome_category = str(outcome.get("outcome_category") or "")
    body = classify_source_body(dict(record))
    if outcome_category in UNUSABLE_OUTCOMES:
        blockers.append(f"unusable_acquisition:{outcome_category}")
    if outcome.get("manual_acquisition_required"):
        blockers.append("unusable_acquisition:manual_acquisition_required")
    if str(outcome.get("content_quality") or "").startswith("UNUSABLE"):
        blockers.append("unusable_acquisition:content_quality")
    if not body["usable_in_app"]:
        blockers.append(f"content_not_readable:{body['state']}")
    elif body["state"] == "body_partial":
        limitations.append("partial_body")

    if not record.get("source_url"):
        blockers.append("missing_provenance:source_url")
    if not (record.get("source_id") or record.get("source_name")):
        blockers.append("missing_provenance:source_identity")
    if not record.get("captured_date"):
        blockers.append("missing_provenance:captured_date")

    date_class = _date_class(
        record,
        today=today or datetime.now(UTC).date(),
        current_window_days=current_window_days,
    )
    if date_class == "historical":
        limitations.append("historical_context_only")
    elif date_class == "unknown":
        limitations.append("publication_date_unknown")
    blockers = list(dict.fromkeys(blockers))
    limitations = list(dict.fromkeys(limitations))
    return EligibilityResult(
        eligible=not blockers,
        blockers=tuple(blockers),
        limitations=tuple(limitations),
        content_state=str(body["state"]),
        date_class=date_class,
        current_news_eligible=not blockers and date_class == "current",
    )


def _base_trust_state(record: Mapping[str, Any]) -> str:
    if record.get("status") != "published" and record.get("review_state") != "published":
        return STATE_UNREVIEWED
    tier = evidence_trust_tier(dict(record))
    return STATE_APPROVED_SOURCE if tier == TIER_APPROVED_SOURCE else STATE_TRUSTED


def feedback_projection(
    record: Mapping[str, Any],
    *,
    entry: Mapping[str, Any] | None = None,
    acquisition_outcome: Mapping[str, Any] | None = None,
    today: date | None = None,
    current_window_days: int = 90,
) -> dict[str, Any]:
    """Return the deterministic query seam for Today/reports/coverage/packets."""

    entry = entry or {}
    state = str(entry.get("state") or _base_trust_state(record))
    eligibility = check_eligibility(
        record,
        acquisition_outcome=acquisition_outcome,
        today=today,
        current_window_days=current_window_days,
    )
    trusted = state == STATE_TRUSTED
    excluded = state == STATE_EXCLUDED
    stored_blockers = list(entry.get("review_blockers") or [])
    return {
        "state": state,
        "version": int(entry.get("version") or 0),
        "eligible_for_trusted_feed": trusted and eligibility.eligible and not excluded,
        "excluded_from_trusted_feed": excluded,
        "pending_promotion": state == STATE_PENDING_PROMOTION,
        "approved": state in TERMINAL_PROMOTION_STATES,
        "trusted": trusted,
        "deferred": state == STATE_DEFERRED,
        "last_feedback_action": entry.get("action"),
        "exclusion_reason": entry.get("reason") if excluded else None,
        "undo_available": (
            bool(entry.get("last_event_id"))
            and entry.get("action") != "undo"
            and state not in TERMINAL_PROMOTION_STATES
        ),
        "current_news_eligible": trusted and eligibility.current_news_eligible and not excluded,
        "date_class": eligibility.date_class,
        "content_state": eligibility.content_state,
        "review_blockers": list(dict.fromkeys([*stored_blockers, *eligibility.blockers])),
        "limitations": list(eligibility.limitations),
    }


class TrustFeedbackService:
    def __init__(self, inbox_dir: Path, *, promotion_handler: PromotionHandler | None = None) -> None:
        self._inbox_dir = Path(inbox_dir)
        self._promotion_handler = promotion_handler

    def eligibility(
        self,
        record: Mapping[str, Any],
        *,
        acquisition_outcome: Mapping[str, Any] | None = None,
        today: date | None = None,
    ) -> EligibilityResult:
        return check_eligibility(record, acquisition_outcome=acquisition_outcome, today=today)

    def projection(
        self,
        record: Mapping[str, Any],
        *,
        actor_id: str,
        object_type: str = "evidence",
        acquisition_outcome: Mapping[str, Any] | None = None,
        today: date | None = None,
    ) -> dict[str, Any]:
        state = load_state(self._inbox_dir)
        key = _state_key(actor_id, object_type, str(record.get("id") or ""))
        return feedback_projection(
            record,
            entry=(state.get(STATE_BUCKET) or {}).get(key),
            acquisition_outcome=acquisition_outcome,
            today=today,
        )

    def apply(
        self,
        request: FeedbackRequest,
        record: Mapping[str, Any],
        *,
        acquisition_outcome: Mapping[str, Any] | None = None,
    ) -> FeedbackResult:
        self._validate_request(request, record)
        existing = self._idempotent_event(request)
        if existing is not None:
            return self._replay_result(existing, record, request, acquisition_outcome)

        state = load_state(self._inbox_dir)
        bucket = state.setdefault(STATE_BUCKET, {})
        key = _state_key(request.actor.actor_id, request.object_type, request.object_id)
        current = bucket.get(key) or {}
        current_version = int(current.get("version") or 0)
        if request.expected_version is not None and request.expected_version != current_version:
            raise StaleFeedbackVersion(
                f"expected version {request.expected_version}, current version is {current_version}"
            )
        prior_state = str(current.get("state") or _base_trust_state(record))
        blockers: tuple[str, ...] = ()
        trusted_record_id: str | None = None

        if request.action == "undo":
            resulting_state = self._undo_state(request, current, prior_state)
        elif request.action == "exclude":
            resulting_state = STATE_EXCLUDED
        elif request.action == "defer":
            resulting_state = STATE_DEFERRED
        else:
            resulting_state, blockers, trusted_record_id = self._promote(
                request, record, acquisition_outcome
            )

        next_version = current_version + 1
        event_result = append_review_event(
            self._inbox_dir,
            workflow=WORKFLOW,
            object_id=request.object_id,
            object_type=request.object_type,
            action=request.action,
            prior_state=prior_state,
            new_state=resulting_state,
            actor=request.actor.actor_id,
            subject=dict(record),
            reason_category=request.reason,
            feedback_intent=request.intent,
            idempotency_key=request.idempotency_key,
            expected_version=request.expected_version,
            state_version=next_version,
            source_surface=request.source_surface,
            review_blockers=list(blockers),
            undoes_event_id=request.original_event_id,
            occurred_at=datetime.now(UTC).isoformat(timespec="microseconds"),
        )
        bucket[key] = {
            "object_id": request.object_id,
            "object_type": request.object_type,
            "actor_id": request.actor.actor_id,
            "state": resulting_state,
            "version": next_version,
            "action": request.action,
            "intent": request.intent,
            "reason": request.reason,
            "last_event_id": event_result.event["id"],
            "updated_at": event_result.event["occurred_at"],
            "review_blockers": list(blockers),
            "trusted_record_id": trusted_record_id,
        }
        try:
            save_state(self._inbox_dir, state)
        except Exception:
            remove_created_event(event_result)
            raise
        projection = feedback_projection(
            record, entry=bucket[key], acquisition_outcome=acquisition_outcome
        )
        return FeedbackResult(
            state=resulting_state,
            version=next_version,
            blockers=blockers,
            event=event_result.event,
            event_created=event_result.created,
            idempotent_replay=False,
            trusted_record_id=trusted_record_id,
            projection=projection,
        )

    def _validate_request(self, request: FeedbackRequest, record: Mapping[str, Any]) -> None:
        if request.action not in ACTIONS:
            raise FeedbackError(f"unsupported feedback action: {request.action}")
        if request.object_type not in OBJECT_TYPES:
            raise FeedbackError(f"unsupported feedback object_type: {request.object_type}")
        if not request.actor.actor_id.strip():
            raise FeedbackError("actor_id is required")
        if "submit_feedback" not in request.actor.permissions:
            raise FeedbackError("actor is not authorized to submit feedback")
        if not request.idempotency_key.strip() or len(request.idempotency_key) > 200:
            raise FeedbackError("a bounded idempotency_key is required")
        if not request.source_surface.strip():
            raise FeedbackError("source_surface is required")
        if not request.object_id or request.object_id != str(record.get("id") or ""):
            raise FeedbackError("linked record ID does not match the feedback request")
        if request.action == "promote" and request.intent not in PROMOTION_INTENTS:
            raise FeedbackError("promote requires a supported typed intent")
        if request.reason and request.reason not in EXCLUSION_REASONS:
            raise FeedbackError("unsupported feedback reason")
        if request.action == "undo" and not request.original_event_id:
            raise InvalidUndo("undo requires original_event_id")

    def _idempotent_event(self, request: FeedbackRequest) -> Mapping[str, Any] | None:
        for event in load_review_events(
            self._inbox_dir, workflow=WORKFLOW, object_id=request.object_id
        ):
            if event.get("idempotency_key") != request.idempotency_key:
                continue
            same = (
                event.get("actor") == request.actor.actor_id
                and event.get("object_type") == request.object_type
                and event.get("action") == request.action
                and event.get("feedback_intent") == request.intent
                and event.get("reason_category") == request.reason
                and event.get("undoes_event_id") == request.original_event_id
            )
            if not same:
                raise IdempotencyConflict("idempotency key was already used for a different action")
            return event
        return None

    def _replay_result(
        self,
        event: Mapping[str, Any],
        record: Mapping[str, Any],
        request: FeedbackRequest,
        acquisition_outcome: Mapping[str, Any] | None,
    ) -> FeedbackResult:
        state = load_state(self._inbox_dir)
        key = _state_key(request.actor.actor_id, request.object_type, request.object_id)
        entry = (state.get(STATE_BUCKET) or {}).get(key) or {}
        resulting = str(event.get("resulting_state") or event.get("new_state") or STATE_UNREVIEWED)
        return FeedbackResult(
            state=resulting,
            version=int(event.get("state_version") or 0),
            blockers=tuple(event.get("review_blockers") or ()),
            event=event,
            event_created=False,
            idempotent_replay=True,
            trusted_record_id=entry.get("trusted_record_id"),
            projection=feedback_projection(
                record, entry=entry, acquisition_outcome=acquisition_outcome
            ),
        )

    def _promote(
        self,
        request: FeedbackRequest,
        record: Mapping[str, Any],
        acquisition_outcome: Mapping[str, Any] | None,
    ) -> tuple[str, tuple[str, ...], str | None]:
        if request.intent != "governed_promotion":
            return STATE_RETAINED, (), None
        if request.object_type not in {"evidence", "publication_draft"}:
            return (
                STATE_PENDING_PROMOTION,
                ("governed_promotion_not_supported_for_object_type",),
                None,
            )
        eligibility = check_eligibility(record, acquisition_outcome=acquisition_outcome)
        blockers = list(eligibility.blockers)
        if "promote_evidence" not in request.actor.permissions:
            blockers.append("review_authority_required")
        if blockers:
            return STATE_PENDING_PROMOTION, tuple(dict.fromkeys(blockers)), None

        base_state = _base_trust_state(record)
        if base_state in TERMINAL_PROMOTION_STATES:
            return base_state, (), request.object_id
        if self._promotion_handler is None:
            return STATE_PENDING_PROMOTION, ("governed_promotion_handler_required",), None
        outcome = self._promotion_handler(record, request.actor)
        if not outcome.ok:
            return STATE_PENDING_PROMOTION, tuple(outcome.blockers or ("approval_gate_rejected",)), None
        if outcome.resulting_trust_state not in TERMINAL_PROMOTION_STATES:
            return STATE_PENDING_PROMOTION, ("approval_result_did_not_establish_trust_state",), None
        return outcome.resulting_trust_state, (), outcome.trusted_record_id

    def _undo_state(
        self,
        request: FeedbackRequest,
        current: Mapping[str, Any],
        prior_state: str,
    ) -> str:
        events = load_review_events(
            self._inbox_dir, workflow=WORKFLOW, object_id=request.object_id
        )
        target = next(
            (event for event in events if event.get("id") == request.original_event_id),
            None,
        )
        if target is None:
            raise InvalidUndo("original feedback event was not found")
        if target.get("actor") != request.actor.actor_id:
            raise InvalidUndo("only the original actor may undo this feedback event")
        if target.get("object_type") != request.object_type:
            raise InvalidUndo("feedback event belongs to a different object type")
        if current.get("last_event_id") != request.original_event_id:
            raise InvalidUndo("feedback event has been superseded and cannot be undone")
        if target.get("action") == "undo":
            raise InvalidUndo("an undo event cannot itself be undone through this operation")
        if prior_state in TERMINAL_PROMOTION_STATES:
            raise InvalidUndo("governed publication requires its existing reversal workflow")
        return str(target.get("prior_state") or STATE_UNREVIEWED)
