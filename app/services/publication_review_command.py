"""Publication Review Command Service V1 -- boundary-safe command service
(Slice 3).

Implements `design/publication-review-contract-v1`'s `COMMAND-CONTRACTS.md`
single-item decision commands. This is the ONLY code path in this mission
that may create a trusted publication -- it never calls
`ReviewPublishService.publish()` and never creates an Entity, Fact,
Relationship, Signal, Assessment, Recommendation, or Atomic Evidence
record. Approval stages the strict `publication_artifact` compatibility
profile (`TRUST-BOUNDARIES.md`) with empty `fact_ids`/`relationship_ids`
and exposes it only via one atomic file write, gated behind a durable,
recoverably-staged journal (`FAILURE-AND-RECOVERY.md`).

No HTML, no HTTP, no session -- `AuthorizedActorDirectory` and
`revision-only patch` are the only externally-supplied inputs beyond the
command envelope itself, per the contract's own "HTML forms, JSON routes,
and future operator tools are adapters to the same commands and may not
weaken their checks."
"""

from __future__ import annotations

import hashlib
import json
import uuid
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Callable, Protocol

from jsonschema import Draft202012Validator, FormatChecker

from app.services import publication_review_domain as domain
from app.services.draft_delivery import atomic_write_json
from app.services.publication_review_repository import (
    DraftNotFound,
    DraftState,
    DurableReviewRepository,
    IdempotencyConflict,
    LockUnavailable,
    StaleVersion,
)
from app.services.review_events import append_review_event

ALLOWED_REVISION_FIELDS = frozenset({
    "title", "source_name", "source_url", "published_date", "summary", "why_it_matters",
    "tags", "berry_ids", "geography_ids", "entity_ids", "priority",
})

REJECTION_REASON_CODES = frozenset({
    "not_relevant", "navigation_only_shell", "access_denied", "duplicate", "low_quality",
    "unsupported_source", "other",
})
DEFER_REASON_CODES = frozenset({"needs_manual_acquisition", "awaiting_upgrade", "operator_capacity", "other"})
CORRECTION_BLOCKER_CODES = frozenset(domain.__dict__[name] for name in dir(domain) if name.startswith("BLOCKER_"))

PERMISSION_PUBLICATION_REVIEW = "publication_review"


# --------------------------------------------------------------------------
# Actor authorization -- structured identity, never free text
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ActorIdentity:
    """An authenticated identity resolved by the caller's own session/auth
    layer -- never constructed from raw form text. `kind` distinguishes a
    real human reviewer from AI/bot/service callers; only `kind == "human"`
    with the `publication_review` permission may ever approve/reject/defer/
    request a correction."""

    actor_id: str
    kind: str  # "human" | "ai" | "bot" | "service"
    permissions: frozenset[str] = frozenset()
    authenticated: bool = True


class ActorDirectory(Protocol):
    def resolve(self, actor_id: str) -> ActorIdentity | None:
        """Return the resolved identity for `actor_id`, or None if it does
        not resolve to any known, authenticated identity."""
        ...


class InMemoryActorDirectory:
    """A minimal, explicit actor directory for tests and any future
    adapter -- no session/cookie/JWT parsing lives in this module. A real
    deployment's HTTP layer resolves its own authenticated session to an
    `ActorIdentity` and either implements this Protocol directly or wraps
    another identity provider behind it; this class exists so the command
    service and its tests do not depend on any particular provider."""

    def __init__(self, actors: dict[str, ActorIdentity] | None = None) -> None:
        self._actors = dict(actors or {})

    def register(self, actor: ActorIdentity) -> None:
        self._actors[actor.actor_id] = actor

    def resolve(self, actor_id: str) -> ActorIdentity | None:
        return self._actors.get(actor_id)


def is_authorized_human_reviewer(actor: ActorIdentity | None) -> bool:
    return (
        actor is not None
        and actor.authenticated
        and actor.kind == "human"
        and PERMISSION_PUBLICATION_REVIEW in actor.permissions
    )


# --------------------------------------------------------------------------
# Ports the command service depends on (repository boundary / test seams)
# --------------------------------------------------------------------------


class EvidenceWritePort(Protocol):
    """The narrow slice of `EvidenceRepository` behavior this service
    needs: check an id is free, and validate+write one record. Deliberately
    not the full `RecordRepository` protocol -- approval writes exactly one
    record and never updates/deletes an existing trusted publication."""

    def get(self, record_id: str) -> dict[str, Any] | None: ...


@dataclass(frozen=True)
class CommandDependencies:
    repository: DurableReviewRepository
    actor_directory: ActorDirectory
    evidence_reader: EvidenceWritePort
    evidence_schema_path: Path
    evidence_data_dir: Path
    review_events_inbox: Path
    entity_ids_resolver: Callable[[], frozenset[str]]
    clock: Callable[[], datetime] = lambda: datetime.now(UTC)
    command_id_generator: Callable[[], str] = lambda: f"cmd-{uuid.uuid4().hex}"
    transaction_id_generator: Callable[[], str] = lambda: f"txn-{uuid.uuid4().hex}"


def _payload_hash(command: str, envelope: domain.CommandEnvelope, extra: dict[str, Any]) -> str:
    payload = {
        "command": command, "draft_id": envelope.draft_id, "expected_version": envelope.expected_version,
        "reviewed_content_digest": envelope.reviewed_content_digest, "comment": envelope.comment, **extra,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="microseconds")


class PublicationReviewCommandService:
    """The single boundary-safe command surface. Every public method takes
    a `CommandEnvelope` and returns a `domain.CommandResult`, or raises
    `domain.CommandError`."""

    def __init__(self, deps: CommandDependencies) -> None:
        self._deps = deps

    # -- read operations ----------------------------------------------------

    def get_publication_review(self, draft_id: str) -> dict[str, Any]:
        """Read-only inspection. Never mutates state; inspecting a draft
        never implies a human decision."""
        state = self._deps.repository.get_draft_state(draft_id)
        if state is None:
            raise domain.CommandError(domain.ERROR_DRAFT_NOT_FOUND, f"no draft {draft_id!r}")
        eligibility = domain.check_eligibility(
            state.draft, resolvable_entity_ids=self._deps.entity_ids_resolver(),
        )
        return {
            **state.as_dict(),
            "eligibility": eligibility.as_dict(),
            "permitted_commands": list(domain.permitted_commands(state.state)),
        }

    def list_publication_reviews(self, *, state: str | None = None) -> list[dict[str, Any]]:
        """Queue/list with a stable filter on review state. Reads only
        complete states -- `DraftState` snapshots on disk are only ever
        replaced atomically, so this can never observe a torn write."""
        return [row.as_dict() for row in self._deps.repository.list_draft_states(state=state)]

    def status_summary(self) -> dict[str, Any]:
        rows = self._deps.repository.list_draft_states()
        counts: dict[str, int] = {name: 0 for name in domain.REVIEW_STATES}
        for row in rows:
            counts[row.state] = counts.get(row.state, 0) + 1
        return {"total": len(rows), "by_state": counts}

    def decision_history(self, draft_id: str) -> list[dict[str, Any]]:
        state = self._deps.repository.get_draft_state(draft_id)
        if state is None:
            raise domain.CommandError(domain.ERROR_DRAFT_NOT_FOUND, f"no draft {draft_id!r}")
        return list(state.decision_history)

    # -- authorization / idempotency plumbing shared by every command -------

    def _authorize(self, envelope: domain.CommandEnvelope) -> ActorIdentity:
        actor = self._deps.actor_directory.resolve(envelope.actor_id)
        if actor is None or not actor.authenticated:
            raise domain.CommandError(domain.ERROR_UNAUTHENTICATED, "no authenticated actor")
        if not is_authorized_human_reviewer(actor):
            raise domain.CommandError(
                domain.ERROR_FORBIDDEN,
                f"actor {envelope.actor_id!r} (kind={actor.kind!r}) is not an authorized human reviewer",
            )
        return actor

    def _check_idempotency(
        self, command: str, envelope: domain.CommandEnvelope, extra: dict[str, Any],
    ) -> domain.CommandResult | None:
        receipt = self._deps.repository.get_idempotency_receipt(envelope.actor_id, envelope.idempotency_key)
        if receipt is None:
            return None
        current_hash = _payload_hash(command, envelope, extra)
        if receipt["payload_hash"] != current_hash:
            raise IdempotencyConflict(envelope.actor_id, envelope.idempotency_key)
        result_dict = receipt["result"]
        return domain.CommandResult(
            command_id=result_dict["command_id"], prior_state=result_dict["prior_state"],
            resulting_state=result_dict["resulting_state"], resulting_version=result_dict["resulting_version"],
            event_id=result_dict["event_id"], publication_id=result_dict["publication_id"],
            warnings=tuple(result_dict["warnings"]), idempotent_replay=True,
        )

    def _store_idempotency(
        self, command: str, envelope: domain.CommandEnvelope, extra: dict[str, Any], result: domain.CommandResult,
    ) -> None:
        payload_hash = _payload_hash(command, envelope, extra)
        self._deps.repository.put_idempotency_receipt(
            envelope.actor_id, envelope.idempotency_key, payload_hash=payload_hash, result=result.as_dict(),
        )

    def _load_and_validate(self, envelope: domain.CommandEnvelope, command: str) -> DraftState:
        state = self._deps.repository.get_draft_state(envelope.draft_id)
        if state is None:
            raise domain.CommandError(domain.ERROR_DRAFT_NOT_FOUND, f"no draft {envelope.draft_id!r}")
        if state.version != envelope.expected_version:
            raise domain.CommandError(
                domain.ERROR_STALE_REVIEW,
                f"expected version {envelope.expected_version}, current {state.version}",
                details={"current_version": state.version, "current_digest": state.content_digest},
            )
        if state.content_digest != envelope.reviewed_content_digest:
            raise domain.CommandError(
                domain.ERROR_STALE_REVIEW,
                "reviewed_content_digest does not match the current draft content",
                details={"current_version": state.version, "current_digest": state.content_digest},
            )
        recomputed_provenance_digest = domain.compute_provenance_digest(state.draft)
        if state.provenance_digest != recomputed_provenance_digest:
            # The stored provenance_digest no longer matches what the
            # currently-stored draft content would hash to -- source_id/
            # source_url/discovery/extraction/transcript provenance drifted
            # without going through revise_publication_draft(), which is
            # the only path that keeps both digests in lockstep. This is
            # the "tampered/altered provenance after acquisition" adversarial
            # case Luna's safety audit named explicitly: fail closed rather
            # than trust content whose origin no longer verifies.
            raise domain.CommandError(
                domain.ERROR_STALE_REVIEW,
                "provenance_digest does not match the current draft's provenance fields",
                details={"current_version": state.version, "current_provenance_digest": state.provenance_digest},
            )
        if state.state in domain.TERMINAL_STATES and command in domain.DECISION_COMMANDS:
            raise domain.CommandError(domain.ERROR_ALREADY_DECIDED, f"draft {envelope.draft_id!r} already decided")
        if not domain.is_valid_transition(state.state, command):
            raise domain.CommandError(
                domain.ERROR_INVALID_TRANSITION, f"{command} is not permitted from {state.state!r}",
            )
        return state

    def _append_decision_event(
        self, *, state: DraftState, command: str, actor: ActorIdentity, new_state: str,
        reason_category: str | None, comment: str | None, envelope: domain.CommandEnvelope,
    ) -> str:
        result = append_review_event(
            self._deps.review_events_inbox, workflow="publication_review_command_v1",
            object_id=state.id, object_type="publication_review_draft", action=command,
            prior_state=state.state, new_state=new_state, actor=actor.actor_id, subject=state.draft,
            reason_category=reason_category, notes=comment, idempotency_key=envelope.idempotency_key,
            expected_version=envelope.expected_version, state_version=state.version + 1,
            source_surface=envelope.source_surface,
        )
        return result.event["id"]

    # -- simple (non-promoting) decision commands ---------------------------

    def _simple_transition(
        self, envelope: domain.CommandEnvelope, command: str, *, reason_category: str | None,
        comment: str | None, require_reason: bool,
    ) -> domain.CommandResult:
        actor = self._authorize(envelope)
        extra = {"reason_category": reason_category}
        replay = self._check_idempotency(command, envelope, extra)
        if replay is not None:
            return replay
        if require_reason and not (comment or "").strip():
            raise domain.CommandError(domain.ERROR_INVALID_COMMAND, f"{command} requires a nonblank reason/comment")
        with self._deps.repository.lock_draft(envelope.draft_id):
            state = self._load_and_validate(envelope, command)
            new_review_state = domain.next_state(state.state, command)
            assert new_review_state is not None
            event_id = self._append_decision_event(
                state=state, command=command, actor=actor, new_state=new_review_state,
                reason_category=reason_category, comment=comment, envelope=envelope,
            )

            def _mutate(current: DraftState) -> DraftState:
                updated = deepcopy(current)
                updated.state = new_review_state
                updated.version = current.version + 1
                updated.updated_at = _iso(self._deps.clock())
                updated.decision_history = [*updated.decision_history, {
                    "command": command, "actor_id": actor.actor_id, "occurred_at": updated.updated_at,
                    "reason_category": reason_category, "comment": comment,
                    "resulting_state": new_review_state, "resulting_version": updated.version,
                    "event_id": event_id, "idempotency_key": envelope.idempotency_key,
                }]
                return updated

            updated_state = self._deps.repository.compare_and_set(envelope.draft_id, state.version, _mutate)
        result = domain.CommandResult(
            command_id=self._deps.command_id_generator(), prior_state=state.state,
            resulting_state=updated_state.state, resulting_version=updated_state.version,
            event_id=event_id, publication_id=None,
        )
        self._store_idempotency(command, envelope, extra, result)
        return result

    def reject_publication(self, envelope: domain.CommandEnvelope, *, reason_code: str, comment: str) -> domain.CommandResult:
        if reason_code not in REJECTION_REASON_CODES:
            raise domain.CommandError(domain.ERROR_INVALID_COMMAND, f"unknown rejection reason_code {reason_code!r}")
        return self._simple_transition(
            envelope, domain.CMD_REJECT, reason_category=reason_code, comment=comment, require_reason=True,
        )

    def defer_publication(
        self, envelope: domain.CommandEnvelope, *, reason_code: str, review_after: str | None = None,
    ) -> domain.CommandResult:
        if reason_code not in DEFER_REASON_CODES:
            raise domain.CommandError(domain.ERROR_INVALID_COMMAND, f"unknown defer reason_code {reason_code!r}")
        comment = f"review_after={review_after}" if review_after else None
        return self._simple_transition(
            envelope, domain.CMD_DEFER, reason_category=reason_code, comment=comment or reason_code,
            require_reason=False,
        )

    def request_publication_correction(
        self, envelope: domain.CommandEnvelope, *, blocker_codes: tuple[str, ...], comment: str,
    ) -> domain.CommandResult:
        if not blocker_codes:
            raise domain.CommandError(domain.ERROR_INVALID_COMMAND, "at least one blocker_code is required")
        unknown = [code for code in blocker_codes if code not in CORRECTION_BLOCKER_CODES]
        if unknown:
            raise domain.CommandError(domain.ERROR_INVALID_COMMAND, f"unknown blocker_codes: {unknown}")
        return self._simple_transition(
            envelope, domain.CMD_REQUEST_CORRECTION, reason_category=",".join(sorted(blocker_codes)),
            comment=comment, require_reason=True,
        )

    def return_publication_to_review(self, envelope: domain.CommandEnvelope, *, comment: str) -> domain.CommandResult:
        return self._simple_transition(
            envelope, domain.CMD_RETURN_TO_REVIEW, reason_category="ready_for_review", comment=comment,
            require_reason=False,
        )

    def supersede_publication_duplicate(
        self, envelope: domain.CommandEnvelope, *, survivor_id: str, identity_basis: str, comment: str,
    ) -> domain.CommandResult:
        if not survivor_id.strip():
            raise domain.CommandError(domain.ERROR_INVALID_COMMAND, "survivor_id is required")
        if identity_basis not in {"canonical_url", "title_source_date"}:
            raise domain.CommandError(domain.ERROR_INVALID_COMMAND, f"unsupported identity_basis {identity_basis!r}")
        return self._simple_transition(
            envelope, domain.CMD_SUPERSEDE_DUPLICATE, reason_category=f"survivor={survivor_id}:{identity_basis}",
            comment=comment, require_reason=True,
        )

    # -- content revision (not a trust decision) -----------------------------

    def revise_publication_draft(self, envelope: domain.CommandEnvelope, *, patch: dict[str, Any]) -> domain.CommandResult:
        actor = self._authorize(envelope)
        disallowed = set(patch) - ALLOWED_REVISION_FIELDS
        if disallowed:
            raise domain.CommandError(domain.ERROR_INVALID_COMMAND, f"disallowed revision fields: {sorted(disallowed)}")
        extra = {"patch": patch}
        replay = self._check_idempotency(domain.CMD_REVISE, envelope, extra)
        if replay is not None:
            return replay
        with self._deps.repository.lock_draft(envelope.draft_id):
            state = self._load_and_validate_revision(envelope)
            new_draft = {**state.draft, **patch}
            eligibility = domain.check_eligibility(new_draft, resolvable_entity_ids=self._deps.entity_ids_resolver())
            new_digest = domain.compute_review_content_digest(new_draft, eligibility=eligibility)
            new_provenance_digest = domain.compute_provenance_digest(new_draft)
            event_id = self._append_decision_event(
                state=state, command=domain.CMD_REVISE, actor=actor, new_state=state.state,
                reason_category="content_revision", comment=None, envelope=envelope,
            )

            def _mutate(current: DraftState) -> DraftState:
                updated = deepcopy(current)
                updated.draft = new_draft
                updated.version = current.version + 1
                updated.content_digest = new_digest
                updated.provenance_digest = new_provenance_digest
                updated.content_class = eligibility.content_class
                updated.acquisition_classification = eligibility.body_state
                updated.updated_at = _iso(self._deps.clock())
                updated.decision_history = [*updated.decision_history, {
                    "command": domain.CMD_REVISE, "actor_id": actor.actor_id, "occurred_at": updated.updated_at,
                    "reason_category": "content_revision", "comment": None,
                    "resulting_state": updated.state, "resulting_version": updated.version,
                    "event_id": event_id, "idempotency_key": envelope.idempotency_key,
                }]
                return updated

            updated_state = self._deps.repository.compare_and_set(envelope.draft_id, state.version, _mutate)
        result = domain.CommandResult(
            command_id=self._deps.command_id_generator(), prior_state=state.state,
            resulting_state=updated_state.state, resulting_version=updated_state.version,
            event_id=event_id, publication_id=None,
        )
        self._store_idempotency(domain.CMD_REVISE, envelope, extra, result)
        return result

    def submit_publication_correction(
        self, envelope: domain.CommandEnvelope, *, patch: dict[str, Any], comment: str,
    ) -> domain.CommandResult:
        actor = self._authorize(envelope)
        disallowed = set(patch) - ALLOWED_REVISION_FIELDS
        if disallowed:
            raise domain.CommandError(domain.ERROR_INVALID_COMMAND, f"disallowed revision fields: {sorted(disallowed)}")
        extra = {"patch": patch, "comment": comment}
        replay = self._check_idempotency(domain.CMD_SUBMIT_CORRECTION, envelope, extra)
        if replay is not None:
            return replay
        with self._deps.repository.lock_draft(envelope.draft_id):
            state = self._load_and_validate(envelope, domain.CMD_SUBMIT_CORRECTION)
            new_draft = {**state.draft, **patch}
            eligibility = domain.check_eligibility(new_draft, resolvable_entity_ids=self._deps.entity_ids_resolver())
            new_digest = domain.compute_review_content_digest(new_draft, eligibility=eligibility)
            new_provenance_digest = domain.compute_provenance_digest(new_draft)
            new_review_state = domain.next_state(state.state, domain.CMD_SUBMIT_CORRECTION)
            assert new_review_state is not None
            event_id = self._append_decision_event(
                state=state, command=domain.CMD_SUBMIT_CORRECTION, actor=actor, new_state=new_review_state,
                reason_category="correction_submitted", comment=comment, envelope=envelope,
            )

            def _mutate(current: DraftState) -> DraftState:
                updated = deepcopy(current)
                updated.draft = new_draft
                updated.state = new_review_state
                updated.version = current.version + 1
                updated.content_digest = new_digest
                updated.provenance_digest = new_provenance_digest
                updated.content_class = eligibility.content_class
                updated.acquisition_classification = eligibility.body_state
                updated.updated_at = _iso(self._deps.clock())
                updated.decision_history = [*updated.decision_history, {
                    "command": domain.CMD_SUBMIT_CORRECTION, "actor_id": actor.actor_id,
                    "occurred_at": updated.updated_at, "reason_category": "correction_submitted",
                    "comment": comment, "resulting_state": new_review_state, "resulting_version": updated.version,
                    "event_id": event_id, "idempotency_key": envelope.idempotency_key,
                }]
                return updated

            updated_state = self._deps.repository.compare_and_set(envelope.draft_id, state.version, _mutate)
        result = domain.CommandResult(
            command_id=self._deps.command_id_generator(), prior_state=state.state,
            resulting_state=updated_state.state, resulting_version=updated_state.version,
            event_id=event_id, publication_id=None,
        )
        self._store_idempotency(domain.CMD_SUBMIT_CORRECTION, envelope, extra, result)
        return result

    def _load_and_validate_revision(self, envelope: domain.CommandEnvelope) -> DraftState:
        """Revision is not itself a transition (`pending_review` stays
        `pending_review`), so it is checked against the domain rules
        directly rather than via `_load_and_validate`'s transition table."""
        state = self._deps.repository.get_draft_state(envelope.draft_id)
        if state is None:
            raise domain.CommandError(domain.ERROR_DRAFT_NOT_FOUND, f"no draft {envelope.draft_id!r}")
        if state.version != envelope.expected_version or state.content_digest != envelope.reviewed_content_digest:
            raise domain.CommandError(
                domain.ERROR_STALE_REVIEW, "stale version or digest",
                details={"current_version": state.version, "current_digest": state.content_digest},
            )
        if state.state != domain.PENDING_REVIEW:
            raise domain.CommandError(domain.ERROR_INVALID_TRANSITION, "revision is only permitted while pending_review")
        return state

    # -- approval: the only command that promotes a trusted publication -----

    def approve_publication(
        self, envelope: domain.CommandEnvelope, *, approval_basis: str,
        warning_acknowledgments: tuple[str, ...] = (),
    ) -> domain.CommandResult:
        actor = self._authorize(envelope)
        if approval_basis not in domain.APPROVAL_BASES:
            raise domain.CommandError(domain.ERROR_INVALID_COMMAND, f"unknown approval_basis {approval_basis!r}")
        extra = {"approval_basis": approval_basis, "warning_acknowledgments": sorted(warning_acknowledgments)}
        replay = self._check_idempotency(domain.CMD_APPROVE, envelope, extra)
        if replay is not None:
            return replay

        with self._deps.repository.lock_draft(envelope.draft_id):
            state = self._load_and_validate(envelope, domain.CMD_APPROVE)
            existing_records = self._existing_records_for_duplicate_check()
            eligibility = domain.check_eligibility(
                state.draft, existing_trusted_and_pending=existing_records,
                resolvable_entity_ids=self._deps.entity_ids_resolver(),
            )
            if not eligibility.approvable:
                raise domain.CommandError(
                    domain.ERROR_INELIGIBLE, f"draft {envelope.draft_id!r} is not eligible for approval",
                    details=eligibility.as_dict(),
                )
            if approval_basis not in eligibility.permitted_approval_bases:
                raise domain.CommandError(
                    domain.ERROR_INELIGIBLE,
                    f"approval_basis {approval_basis!r} is not permitted for this draft's content "
                    f"(permitted: {eligibility.permitted_approval_bases})",
                    details=eligibility.as_dict(),
                )
            unacknowledged = set(eligibility.warnings) - set(warning_acknowledgments)
            if unacknowledged:
                raise domain.CommandError(
                    domain.ERROR_INVALID_COMMAND, f"unacknowledged warnings: {sorted(unacknowledged)}",
                    details={"warnings": list(eligibility.warnings)},
                )
            publication_id = state.draft.get("id") or envelope.draft_id
            if self._deps.evidence_reader.get(publication_id) is not None:
                raise domain.CommandError(
                    domain.ERROR_IDENTITY_CONFLICT, f"a trusted publication already exists at id {publication_id!r}",
                )

            transaction_id = self._deps.transaction_id_generator()
            event_id, updated_state = self._promote(
                state=state, envelope=envelope, actor=actor, approval_basis=approval_basis,
                eligibility=eligibility, transaction_id=transaction_id, publication_id=publication_id,
            )

        result = domain.CommandResult(
            command_id=self._deps.command_id_generator(), prior_state=state.state,
            resulting_state=updated_state.state, resulting_version=updated_state.version,
            event_id=event_id, publication_id=publication_id, warnings=eligibility.warnings,
        )
        self._store_idempotency(domain.CMD_APPROVE, envelope, extra, result)
        return result

    def _existing_records_for_duplicate_check(self) -> list[dict[str, Any]]:
        trusted = getattr(self._deps.evidence_reader, "list", lambda: [])()
        pending = [row.draft for row in self._deps.repository.list_draft_states(state=domain.PENDING_REVIEW)]
        return [*trusted, *pending]

    def _build_trusted_publication_record(
        self, *, draft: dict[str, Any], publication_id: str, actor: ActorIdentity, approval_basis: str,
        envelope: domain.CommandEnvelope, resulting_version: int, command_id: str, decided_at: str,
    ) -> dict[str, Any]:
        """The strict `publication_artifact` compatibility profile
        `PUBLICATION-REVIEW-CONTRACT-V1.md`'s "Compatibility storage
        profile" section names exactly: `fact_ids: []`,
        `relationship_ids: []` for anything this command creates, existing
        canonical entity ids may be linked but never created, and a
        `publication_review` snapshot with actor/timestamp/reason/digest/
        command id/resulting version."""
        record: dict[str, Any] = {
            "id": publication_id,
            "record_type": "evidence",
            "evidence_role": "publication_artifact",
            "status": "published",
            "review_state": "published",
            "source_type": draft.get("source_type") or "discovered_media",
            "title": draft.get("title") or "",
            "source_name": draft.get("source_name") or "",
            "source_url": draft.get("source_url") or "",
            "published_date": draft.get("published_date"),
            "captured_date": draft.get("captured_date") or date.today().isoformat(),
            "summary": draft.get("summary") or "",
            "why_it_matters": draft.get("why_it_matters") or "",
            "submitted_by": draft.get("submitted_by") or "publication_review_command_service",
            "berry_ids": list(draft.get("berry_ids") or []),
            "geography_ids": list(draft.get("geography_ids") or []),
            "entity_ids": list(draft.get("entity_ids") or []),
            "fact_ids": [],
            "relationship_ids": [],
            "strategic_question_ids": list(draft.get("strategic_question_ids") or []),
            "tags": list(draft.get("tags") or []),
            "attachments": [],
            "priority": draft.get("priority") or {
                "reading": {"level": "none", "rationale": ""}, "testing": {"level": "none", "rationale": ""},
                "commercial_position": {"level": "none", "rationale": ""}, "monitoring": {"level": "none", "rationale": ""},
            },
            "reviewed_by": actor.actor_id,
            "reviewed_at": decided_at[:10],
            "publication_content_basis": approval_basis,
            "limited_content": approval_basis == domain.BASIS_LIMITED_CONTENT,
            "publication_review": {
                "actor_id": actor.actor_id,
                "decision_timestamp": decided_at,
                "reason_code": approval_basis,
                "reviewed_content_digest": envelope.reviewed_content_digest,
                "command_id": command_id,
                "resulting_state_version": resulting_version,
            },
        }
        for field_name in (
            "source_id", "media_format", "transcript", "parent_evidence_id", "artifact_locator",
            "extraction_provenance", "transcript_provenance", "transcript_excerpt", "discovered_item_id",
            "discovery_provenance", "publisher_description", "article", "relevance_tier", "does_not_prove",
            "source_artifact", "source_completeness",
        ):
            if field_name in draft:
                record[field_name] = deepcopy(draft[field_name])
        return record

    def _promote(
        self, *, state: DraftState, envelope: domain.CommandEnvelope, actor: ActorIdentity, approval_basis: str,
        eligibility: domain.EligibilityResult, transaction_id: str, publication_id: str,
    ) -> tuple[str, DraftState]:
        """The staged promotion protocol from `FAILURE-AND-RECOVERY.md`,
        steps 2-9 (step 1, validate+lock, already happened in the caller)."""
        repo = self._deps.repository
        decided_at = _iso(self._deps.clock())
        command_id = self._deps.command_id_generator()

        # Step 2: durably write the command intent/receipt.
        repo.write_journal_phase(state.id, transaction_id, "intent", {
            "draft_id": state.id, "expected_version": envelope.expected_version,
            "reviewed_content_digest": envelope.reviewed_content_digest, "actor_id": actor.actor_id,
            "target_publication_id": publication_id, "approval_basis": approval_basis,
            "command_id": command_id, "idempotency_key": envelope.idempotency_key, "started_at": decided_at,
        })

        publication_record = self._build_trusted_publication_record(
            draft=state.draft, publication_id=publication_id, actor=actor, approval_basis=approval_basis,
            envelope=envelope, resulting_version=state.version + 1, command_id=command_id, decided_at=decided_at,
        )
        publication_hash = hashlib.sha256(
            json.dumps(publication_record, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()

        # Step 3: stage the trusted publication under the transaction id --
        # NOT written to the real evidence store yet, so it is not
        # queryable as trusted.
        repo.write_journal_phase(state.id, transaction_id, "staged_publication", {
            "publication_id": publication_id, "record": publication_record, "record_hash": publication_hash,
        })

        # Step 4: stage the immutable decision binding draft/version/
        # provenance to the publication hash.
        decision_payload = {
            "draft_id": state.id, "version": state.version, "content_digest": envelope.reviewed_content_digest,
            "provenance_digest": state.provenance_digest, "actor_id": actor.actor_id,
            "publication_id": publication_id, "publication_record_hash": publication_hash,
            "approval_basis": approval_basis, "decided_at": decided_at, "command_id": command_id,
        }
        repo.write_journal_phase(state.id, transaction_id, "staged_decision", decision_payload)

        # Step 5: append the audit event -- while pre-commit this is staged
        # only, an operational pending event, not yet a completed decision.
        staged_event_payload = {
            "workflow": "publication_review_command_v1", "object_id": state.id, "action": domain.CMD_APPROVE,
            "prior_state": state.state, "new_state": domain.APPROVED, "actor_id": actor.actor_id,
            "reason_category": approval_basis, "idempotency_key": envelope.idempotency_key,
            "expected_version": envelope.expected_version, "state_version": state.version + 1,
            "source_surface": envelope.source_surface,
        }
        repo.write_journal_phase(state.id, transaction_id, "staged_event", staged_event_payload)

        # Step 6: verify staged content, then commit.
        return self._finish_promotion(state, transaction_id, publication_id)

    def _finish_promotion(
        self, state: DraftState, transaction_id: str, publication_id: str,
    ) -> tuple[str, DraftState]:
        """Steps 6-9: verify -> one atomic evidence write (the real
        visibility boundary external readers observe) -> real audit event
        -> draft compare-and-set -> commit marker. Idempotent: safe to call
        again during recovery for a transaction that reached any point up
        to (but not including) a published commit marker."""
        repo = self._deps.repository
        staged_publication = repo.read_journal_phase(state.id, transaction_id, "staged_publication")
        staged_decision = repo.read_journal_phase(state.id, transaction_id, "staged_decision")
        staged_event = repo.read_journal_phase(state.id, transaction_id, "staged_event")
        if not (staged_publication and staged_decision and staged_event):
            raise domain.CommandError(
                domain.ERROR_PROMOTION_INCOMPLETE, f"transaction {transaction_id!r} is missing staged phases",
            )
        publication_record = staged_publication["record"]
        expected_hash = staged_publication["record_hash"]
        recomputed_hash = hashlib.sha256(
            json.dumps(publication_record, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        if recomputed_hash != expected_hash or staged_decision["publication_record_hash"] != expected_hash:
            raise domain.CommandError(
                domain.ERROR_PROMOTION_INCOMPLETE, "staged publication hash mismatch; refusing to commit",
            )

        # Step 6 (real visibility boundary): one atomic file write. Never
        # re-written if it already exists from a prior, interrupted attempt
        # at this exact transaction -- idempotent by construction.
        evidence_path = self._deps.evidence_data_dir / "evidence" / f"{publication_id}.json"
        if not evidence_path.is_file():
            self._validate_against_evidence_schema(publication_record)
            atomic_write_json(evidence_path, publication_record)

        # Step 7: the real, shared review-event ledger. append_review_event
        # is itself idempotent on identical retry (see review_events.py).
        event_result = append_review_event(
            self._deps.review_events_inbox, workflow=staged_event["workflow"], object_id=staged_event["object_id"],
            object_type="publication_review_draft", action=staged_event["action"],
            prior_state=staged_event["prior_state"], new_state=staged_event["new_state"],
            actor=staged_event["actor_id"], subject=state.draft, reason_category=staged_event["reason_category"],
            idempotency_key=staged_event["idempotency_key"], expected_version=staged_event["expected_version"],
            state_version=staged_event["state_version"], source_surface=staged_event["source_surface"],
        )
        event_id = event_result.event["id"]

        # Step 8: draft compare-and-set to the terminal `approved` state.
        current = repo.get_draft_state(state.id)
        if current is None:
            raise domain.CommandError(domain.ERROR_PROMOTION_INCOMPLETE, "draft vanished during promotion")
        if current.state != domain.APPROVED:
            def _mutate(existing: DraftState) -> DraftState:
                updated = deepcopy(existing)
                updated.state = domain.APPROVED
                updated.version = existing.version + 1
                updated.updated_at = staged_decision["decided_at"]
                updated.publication_binding = {
                    "publication_id": publication_id, "committed_at": staged_decision["decided_at"],
                    "transaction_id": transaction_id,
                }
                updated.decision_history = [*updated.decision_history, {
                    "command": domain.CMD_APPROVE, "actor_id": staged_decision["actor_id"],
                    "occurred_at": staged_decision["decided_at"], "reason_category": staged_decision["approval_basis"],
                    "comment": None, "resulting_state": domain.APPROVED, "resulting_version": updated.version,
                    "event_id": event_id, "idempotency_key": None,
                }]
                return updated
            updated_state = repo.compare_and_set(state.id, current.version, _mutate)
        else:
            updated_state = current

        # Step 9: the single visibility commit marker -- last write of the
        # transaction. A reconciler treats its presence as proof steps 6-8
        # are complete and verified.
        repo.write_journal_phase(state.id, transaction_id, "commit_marker", {
            "publication_id": publication_id, "publication_record_hash": expected_hash, "event_id": event_id,
            "committed_at": staged_decision["decided_at"], "draft_version": updated_state.version,
        })
        return event_id, updated_state

    def _validate_against_evidence_schema(self, record: dict[str, Any]) -> None:
        schema = json.loads(self._deps.evidence_schema_path.read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        errors = [error.message for error in validator.iter_errors(record)]
        if errors:
            raise domain.CommandError(domain.ERROR_INVALID_COMMAND, f"trusted publication failed schema: {errors}")

    # -- crash recovery / reconciliation -------------------------------------

    def reconcile_pending_transactions(self) -> list[dict[str, Any]]:
        """Resume or safely abandon every transaction whose journal has no
        `commit_marker` yet. Called at startup (or on demand by an
        operator tool) -- never automatically mid-request. Recovery never
        rolls back a published commit marker; it only finishes or safely
        abandons work that never became visible."""
        reports: list[dict[str, Any]] = []
        for draft_id, transaction_id in self._deps.repository.pending_transactions():
            report = {"draft_id": draft_id, "transaction_id": transaction_id}
            phases = self._deps.repository.journal_phases_present(draft_id, transaction_id)
            state = self._deps.repository.get_draft_state(draft_id)
            if state is None:
                report["outcome"] = "abandoned_draft_missing"
                reports.append(report)
                continue
            if {"staged_publication", "staged_decision", "staged_event"} <= phases:
                publication_id = self._deps.repository.read_journal_phase(
                    draft_id, transaction_id, "staged_publication"
                )["publication_id"]
                try:
                    event_id, updated_state = self._finish_promotion(state, transaction_id, publication_id)
                    report["outcome"] = "resumed_and_committed"
                    report["event_id"] = event_id
                    report["resulting_version"] = updated_state.version
                except domain.CommandError as exc:
                    report["outcome"] = f"resume_failed:{exc.code}"
            else:
                report["outcome"] = "abandoned_incomplete_stage"
            reports.append(report)
        return reports
