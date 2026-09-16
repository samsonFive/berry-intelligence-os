"""Publication Review Command Service V1 -- command service tests (Slice 3).

Every test uses `tmp_path`-rooted stores only (durable review repository,
evidence data dir, review-events inbox). Nothing here touches the real
`data/` or `inbox/`, and nothing calls `ReviewPublishService.publish()`.
"""

from __future__ import annotations

import json

import pytest

from app.composition import get_repositories
from app.repositories.paths import SCHEMAS_DIR
from app.services import publication_review_domain as domain
from app.services.publication_review_command import (
    ActorIdentity,
    CommandDependencies,
    InMemoryActorDirectory,
    PublicationReviewCommandService,
    PERMISSION_PUBLICATION_REVIEW,
)
from app.services.publication_review_repository import DraftState, DurableReviewRepository


def _readable_draft(draft_id="ev-media-1", **overrides) -> dict:
    draft = {
        "id": draft_id, "title": "Blueberry acreage grows in Peru", "source_id": "source-1",
        "source_url": "https://example.invalid/peru-blueberries", "captured_date": "2026-09-16",
        "submitted_by": "media-orchestration", "summary": "A short summary.", "published_date": "2026-09-15",
        "article": {
            "word_count": 300, "paragraphs": [{"index": 0, "text": "word " * 300}], "content_sha256": "a" * 64,
        },
    }
    draft.update(overrides)
    return draft


def _shell_draft(draft_id="ev-media-shell") -> dict:
    return {
        "id": draft_id, "title": "Empty shell page", "source_id": "source-2",
        "source_url": "https://example.invalid/empty", "captured_date": "2026-09-16",
        "submitted_by": "media-orchestration", "summary": "Discovered web_article item.",
        "published_date": "2026-09-15",
        "discovery_provenance": {"acquisition_failure_category": "EMPTY_BODY"},
    }


def _transcript_draft(draft_id="ev-media-transcript") -> dict:
    return {
        "id": draft_id, "title": "A podcast episode", "source_id": "source-3", "media_format": "podcast",
        "source_url": "https://example.invalid/pod-1", "captured_date": "2026-09-16",
        "submitted_by": "media-orchestration", "summary": "A podcast summary.", "published_date": "2026-09-15",
        "transcript": {"status": "available", "segments": [{"start": 0, "end": 5, "text": "hello world"}]},
    }


def _thin_draft(draft_id="ev-media-thin") -> dict:
    return {
        "id": draft_id, "title": "A thin metadata-only item", "source_id": "source-4",
        "source_url": "https://example.invalid/thin", "captured_date": "2026-09-16",
        "submitted_by": "media-orchestration", "summary": "", "published_date": "2026-09-15",
        "publisher_description": "A short publisher blurb about a company announcement.",
    }


class Harness:
    """One self-contained, tmp_path-rooted set of stores plus a ready
    command service, with a small helper to seed a durable draft in
    `pending_review` from a plain draft dict."""

    def __init__(self, tmp_path):
        self.tmp_path = tmp_path
        self.data_dir = tmp_path / "data"
        (self.data_dir / "evidence").mkdir(parents=True)
        self.inbox_dir = tmp_path / "inbox"
        self.review_root = tmp_path / "review_state"
        self.repository = DurableReviewRepository(self.review_root)
        self.actors = InMemoryActorDirectory()
        self.actors.register(ActorIdentity(
            actor_id="alice", kind="human", permissions=frozenset({PERMISSION_PUBLICATION_REVIEW}),
        ))
        self.actors.register(ActorIdentity(
            actor_id="bob", kind="human", permissions=frozenset({PERMISSION_PUBLICATION_REVIEW}),
        ))
        self.actors.register(ActorIdentity(
            actor_id="unpermitted-human", kind="human", permissions=frozenset(),
        ))
        self.actors.register(ActorIdentity(
            actor_id="ai-bot", kind="ai", permissions=frozenset({PERMISSION_PUBLICATION_REVIEW}),
        ))
        self.actors.register(ActorIdentity(
            actor_id="scheduler-service", kind="service", permissions=frozenset({PERMISSION_PUBLICATION_REVIEW}),
        ))
        self.actors.register(ActorIdentity(
            actor_id="expired-actor", kind="human", permissions=frozenset({PERMISSION_PUBLICATION_REVIEW}),
            authenticated=False,
        ))
        self.repositories = get_repositories(self.data_dir, SCHEMAS_DIR)
        self.deps = CommandDependencies(
            repository=self.repository, actor_directory=self.actors, evidence_reader=self.repositories.evidence,
            evidence_schema_path=SCHEMAS_DIR / "evidence.schema.json", evidence_data_dir=self.data_dir,
            review_events_inbox=self.inbox_dir, entity_ids_resolver=lambda: frozenset(),
        )
        self.service = PublicationReviewCommandService(self.deps)

    def seed(self, draft: dict) -> DraftState:
        eligibility = domain.check_eligibility(draft)
        digest = domain.compute_review_content_digest(draft, eligibility=eligibility)
        provenance_digest = domain.compute_provenance_digest(draft)
        state = DraftState(
            id=draft["id"], version=1, state=domain.PENDING_REVIEW, draft=draft, content_digest=digest,
            provenance_digest=provenance_digest, content_class=eligibility.content_class,
            acquisition_classification=eligibility.body_state, created_at="2026-09-16T00:00:00+00:00",
            updated_at="2026-09-16T00:00:00+00:00",
        )
        return self.repository.create_draft_state(state)

    def envelope(self, draft_id, *, actor_id="alice", idempotency_key="k1", version=1, digest=None) -> domain.CommandEnvelope:
        if digest is None:
            digest = self.repository.get_draft_state(draft_id).content_digest
        return domain.CommandEnvelope(
            draft_id=draft_id, actor_id=actor_id, idempotency_key=idempotency_key,
            expected_version=version, reviewed_content_digest=digest,
        )

    def evidence_file(self, draft_id: str):
        return self.data_dir / "evidence" / f"{draft_id}.json"


@pytest.fixture
def harness(tmp_path):
    return Harness(tmp_path)


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------


def test_unauthenticated_actor_is_rejected_with_no_writes(harness):
    draft = _readable_draft()
    harness.seed(draft)
    env = domain.CommandEnvelope(
        draft_id=draft["id"], actor_id="does-not-exist", idempotency_key="k1", expected_version=1,
        reviewed_content_digest=harness.repository.get_draft_state(draft["id"]).content_digest,
    )
    with pytest.raises(domain.CommandError) as exc_info:
        harness.service.approve_publication(env, approval_basis=domain.BASIS_FULL_ARTICLE)
    assert exc_info.value.code == domain.ERROR_UNAUTHENTICATED
    assert not harness.evidence_file(draft["id"]).exists()
    assert harness.repository.get_draft_state(draft["id"]).state == domain.PENDING_REVIEW


def test_expired_actor_session_is_rejected(harness):
    draft = _readable_draft()
    harness.seed(draft)
    env = harness.envelope(draft["id"], actor_id="expired-actor")
    with pytest.raises(domain.CommandError) as exc_info:
        harness.service.approve_publication(env, approval_basis=domain.BASIS_FULL_ARTICLE)
    assert exc_info.value.code == domain.ERROR_UNAUTHENTICATED


def test_human_without_permission_is_forbidden(harness):
    draft = _readable_draft()
    harness.seed(draft)
    env = harness.envelope(draft["id"], actor_id="unpermitted-human")
    with pytest.raises(domain.CommandError) as exc_info:
        harness.service.approve_publication(env, approval_basis=domain.BASIS_FULL_ARTICLE)
    assert exc_info.value.code == domain.ERROR_FORBIDDEN
    assert not harness.evidence_file(draft["id"]).exists()


def test_ai_actor_cannot_approve(harness):
    draft = _readable_draft()
    harness.seed(draft)
    env = harness.envelope(draft["id"], actor_id="ai-bot")
    with pytest.raises(domain.CommandError) as exc_info:
        harness.service.approve_publication(env, approval_basis=domain.BASIS_FULL_ARTICLE)
    assert exc_info.value.code == domain.ERROR_FORBIDDEN
    assert not harness.evidence_file(draft["id"]).exists()


def test_bot_or_service_actor_cannot_approve(harness):
    draft = _readable_draft()
    harness.seed(draft)
    env = harness.envelope(draft["id"], actor_id="scheduler-service")
    with pytest.raises(domain.CommandError) as exc_info:
        harness.service.approve_publication(env, approval_basis=domain.BASIS_FULL_ARTICLE)
    assert exc_info.value.code == domain.ERROR_FORBIDDEN
    assert not harness.evidence_file(draft["id"]).exists()


def test_authorized_human_actor_succeeds(harness):
    draft = _readable_draft()
    harness.seed(draft)
    env = harness.envelope(draft["id"])
    result = harness.service.approve_publication(env, approval_basis=domain.BASIS_FULL_ARTICLE)
    assert result.resulting_state == domain.APPROVED
    assert harness.evidence_file(draft["id"]).exists()


def test_every_automated_actor_kind_produces_byte_identical_state_trees(harness):
    """Missing/AI/bot/service actors all fail closed with zero writes --
    the durable draft, evidence directory, and review-events ledger must
    be byte-identical before and after every rejected attempt."""
    draft = _readable_draft()
    harness.seed(draft)

    def _snapshot():
        draft_path = harness.review_root / "drafts" / f"{draft['id']}.json"
        return draft_path.read_text(encoding="utf-8"), list(harness.data_dir.rglob("*")), list(harness.inbox_dir.rglob("*")) if harness.inbox_dir.exists() else []

    before = _snapshot()
    for actor_id in ("does-not-exist", "ai-bot", "scheduler-service", "unpermitted-human", "expired-actor"):
        env = harness.envelope(draft["id"], actor_id=actor_id, idempotency_key=f"k-{actor_id}")
        with pytest.raises(domain.CommandError):
            harness.service.approve_publication(env, approval_basis=domain.BASIS_FULL_ARTICLE)
    after = _snapshot()
    assert before == after


# ---------------------------------------------------------------------------
# Version / digest / provenance staleness
# ---------------------------------------------------------------------------


def test_wrong_expected_version_is_rejected_with_no_mutation(harness):
    draft = _readable_draft()
    harness.seed(draft)
    env = harness.envelope(draft["id"], version=99)
    with pytest.raises(domain.CommandError) as exc_info:
        harness.service.approve_publication(env, approval_basis=domain.BASIS_FULL_ARTICLE)
    assert exc_info.value.code == domain.ERROR_STALE_REVIEW
    assert harness.repository.get_draft_state(draft["id"]).version == 1
    assert not harness.evidence_file(draft["id"]).exists()


def test_stale_content_digest_is_rejected(harness):
    draft = _readable_draft()
    harness.seed(draft)
    env = harness.envelope(draft["id"], digest="stale-digest-value")
    with pytest.raises(domain.CommandError) as exc_info:
        harness.service.approve_publication(env, approval_basis=domain.BASIS_FULL_ARTICLE)
    assert exc_info.value.code == domain.ERROR_STALE_REVIEW


def test_tampered_provenance_after_inspection_is_rejected(harness):
    """Direct storage tampering (or an inconsistent import) that changes
    provenance-relevant fields without recomputing provenance_digest must
    fail closed -- the adversarial 'tampered provenance' case."""
    draft = _readable_draft()
    harness.seed(draft)
    state = harness.repository.get_draft_state(draft["id"])
    state.draft["source_id"] = "source-attacker-controlled"
    from app.services.draft_delivery import atomic_write_json
    atomic_write_json(harness.review_root / "drafts" / f"{draft['id']}.json", state.as_dict())

    env = harness.envelope(draft["id"], digest=state.content_digest)
    with pytest.raises(domain.CommandError) as exc_info:
        harness.service.approve_publication(env, approval_basis=domain.BASIS_FULL_ARTICLE)
    assert exc_info.value.code == domain.ERROR_STALE_REVIEW
    assert not harness.evidence_file(draft["id"]).exists()


def test_revision_bumps_version_and_changes_digest(harness):
    draft = _readable_draft()
    harness.seed(draft)
    env = harness.envelope(draft["id"])
    result = harness.service.revise_publication_draft(env, patch={"title": "A corrected headline"})
    assert result.resulting_version == 2
    assert result.resulting_state == domain.PENDING_REVIEW
    updated = harness.repository.get_draft_state(draft["id"])
    assert updated.draft["title"] == "A corrected headline"


def test_approving_with_a_digest_from_before_a_revision_fails(harness):
    draft = _readable_draft()
    harness.seed(draft)
    stale_digest = harness.repository.get_draft_state(draft["id"]).content_digest
    revise_env = harness.envelope(draft["id"])
    harness.service.revise_publication_draft(revise_env, patch={"title": "Changed after inspection"})

    approve_env = domain.CommandEnvelope(
        draft_id=draft["id"], actor_id="alice", idempotency_key="approve-1", expected_version=1,
        reviewed_content_digest=stale_digest,
    )
    with pytest.raises(domain.CommandError) as exc_info:
        harness.service.approve_publication(approve_env, approval_basis=domain.BASIS_FULL_ARTICLE)
    assert exc_info.value.code == domain.ERROR_STALE_REVIEW


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


def test_identical_retry_returns_the_same_result(harness):
    draft = _readable_draft()
    harness.seed(draft)
    env = harness.envelope(draft["id"], idempotency_key="dup-click")
    first = harness.service.approve_publication(env, approval_basis=domain.BASIS_FULL_ARTICLE)
    second = harness.service.approve_publication(env, approval_basis=domain.BASIS_FULL_ARTICLE)
    assert first.publication_id == second.publication_id
    assert first.event_id == second.event_id
    assert second.idempotent_replay is True
    # Only one evidence file, one event, exactly once.
    assert len(list((harness.data_dir / "evidence").glob("*.json"))) == 1


def test_reusing_idempotency_key_with_different_payload_conflicts(harness):
    draft = _readable_draft()
    harness.seed(draft)
    env = harness.envelope(draft["id"], idempotency_key="reused-key")
    harness.service.reject_publication(
        domain.CommandEnvelope(
            draft_id=draft["id"], actor_id="alice", idempotency_key="reused-key", expected_version=1,
            reviewed_content_digest=env.reviewed_content_digest,
        ),
        reason_code="not_relevant", comment="not relevant to berries",
    )
    # Same key, different draft_id semantics (different command entirely) -> conflict.
    draft2 = _readable_draft(draft_id="ev-media-other")
    harness.seed(draft2)
    env2 = harness.envelope(draft2["id"], idempotency_key="reused-key")
    with pytest.raises(Exception):
        harness.service.reject_publication(env2, reason_code="not_relevant", comment="different draft entirely")


def test_two_simultaneous_identical_commands_produce_one_commit(harness):
    """Simulates a double-click: two calls with the same idempotency key
    in sequence (the lock serializes true concurrency) both succeed with
    identical results and only one trusted publication exists."""
    draft = _readable_draft()
    harness.seed(draft)
    env = harness.envelope(draft["id"], idempotency_key="double-click")
    results = [harness.service.approve_publication(env, approval_basis=domain.BASIS_FULL_ARTICLE) for _ in range(2)]
    assert results[0].publication_id == results[1].publication_id
    assert len(list((harness.data_dir / "evidence").glob("*.json"))) == 1


# ---------------------------------------------------------------------------
# Duplicate prevention / already-reviewed handling
# ---------------------------------------------------------------------------


def test_deterministic_duplicate_blocks_approval(harness):
    existing_path = harness.data_dir / "evidence" / "ev-existing.json"
    existing_path.write_text(json.dumps({
        "id": "ev-existing", "record_type": "evidence", "status": "published", "review_state": "published",
        "source_type": "discovered_media", "title": "x", "captured_date": "2026-09-01", "summary": "s",
        "submitted_by": "m", "source_url": "https://example.invalid/peru-blueberries",
        "priority": {"reading": {"level": "none", "rationale": ""}, "testing": {"level": "none", "rationale": ""},
                     "commercial_position": {"level": "none", "rationale": ""}, "monitoring": {"level": "none", "rationale": ""}},
    }), encoding="utf-8")
    draft = _readable_draft()  # same source_url as the existing trusted record
    harness.seed(draft)
    env = harness.envelope(draft["id"])
    with pytest.raises(domain.CommandError) as exc_info:
        harness.service.approve_publication(env, approval_basis=domain.BASIS_FULL_ARTICLE)
    assert exc_info.value.code == domain.ERROR_INELIGIBLE
    assert domain.BLOCKER_DETERMINISTIC_DUPLICATE in exc_info.value.details["blockers"]


def test_identity_conflict_when_publication_id_already_exists(harness):
    draft = _readable_draft(draft_id="ev-collide")
    existing_path = harness.data_dir / "evidence" / "ev-collide.json"
    existing_path.parent.mkdir(parents=True, exist_ok=True)
    existing_path.write_text(json.dumps({"id": "ev-collide", "status": "published"}), encoding="utf-8")
    harness.seed(draft)
    env = harness.envelope(draft["id"])
    with pytest.raises(domain.CommandError) as exc_info:
        harness.service.approve_publication(env, approval_basis=domain.BASIS_FULL_ARTICLE)
    assert exc_info.value.code == domain.ERROR_IDENTITY_CONFLICT


def test_already_decided_draft_rejects_a_second_new_decision(harness):
    draft = _readable_draft()
    harness.seed(draft)
    env = harness.envelope(draft["id"], idempotency_key="first-approval")
    harness.service.approve_publication(env, approval_basis=domain.BASIS_FULL_ARTICLE)

    second_env = domain.CommandEnvelope(
        draft_id=draft["id"], actor_id="bob", idempotency_key="second-attempt", expected_version=2,
        reviewed_content_digest=env.reviewed_content_digest,
    )
    with pytest.raises(domain.CommandError) as exc_info:
        harness.service.reject_publication(second_env, reason_code="not_relevant", comment="too late")
    assert exc_info.value.code == domain.ERROR_ALREADY_DECIDED


# ---------------------------------------------------------------------------
# Every valid state transition via the real command service
# ---------------------------------------------------------------------------


def test_reject_requires_a_reason(harness):
    draft = _readable_draft()
    harness.seed(draft)
    env = harness.envelope(draft["id"])
    with pytest.raises(domain.CommandError) as exc_info:
        harness.service.reject_publication(env, reason_code="not_relevant", comment="")
    assert exc_info.value.code == domain.ERROR_INVALID_COMMAND


def test_reject_with_reason_transitions_to_rejected(harness):
    draft = _readable_draft()
    harness.seed(draft)
    env = harness.envelope(draft["id"])
    result = harness.service.reject_publication(env, reason_code="navigation_only_shell", comment="empty page")
    assert result.resulting_state == domain.REJECTED
    assert not harness.evidence_file(draft["id"]).exists()


def test_defer_transitions_to_deferred_and_return_to_review_works(harness):
    draft = _readable_draft()
    harness.seed(draft)
    env = harness.envelope(draft["id"])
    deferred = harness.service.defer_publication(env, reason_code="operator_capacity")
    assert deferred.resulting_state == domain.DEFERRED

    return_env = harness.envelope(draft["id"], idempotency_key="return-1", version=deferred.resulting_version)
    returned = harness.service.return_publication_to_review(return_env, comment="ready now")
    assert returned.resulting_state == domain.PENDING_REVIEW


def test_request_correction_then_submit_correction_returns_to_pending_review(harness):
    draft = _shell_draft()
    harness.seed(draft)
    env = harness.envelope(draft["id"])
    corrected_request = harness.service.request_publication_correction(
        env, blocker_codes=(domain.BLOCKER_MISSING_PROVENANCE,), comment="need a real source_url",
    )
    assert corrected_request.resulting_state == domain.CORRECTION_REQUIRED

    submit_env = harness.envelope(draft["id"], idempotency_key="submit-1", version=corrected_request.resulting_version)
    submitted = harness.service.submit_publication_correction(
        submit_env, patch={"source_url": "https://example.invalid/corrected"}, comment="fixed",
    )
    assert submitted.resulting_state == domain.PENDING_REVIEW


def test_supersede_duplicate_transitions_to_superseded_duplicate(harness):
    draft = _readable_draft()
    harness.seed(draft)
    env = harness.envelope(draft["id"])
    result = harness.service.supersede_publication_duplicate(
        env, survivor_id="ev-existing-survivor", identity_basis="canonical_url", comment="same article",
    )
    assert result.resulting_state == domain.SUPERSEDED_DUPLICATE
    assert not harness.evidence_file(draft["id"]).exists()


@pytest.mark.parametrize("command_name,kwargs", [
    ("reject_publication", {"reason_code": "not_relevant", "comment": "no"}),
    ("defer_publication", {"reason_code": "operator_capacity"}),
    ("request_publication_correction", {"blocker_codes": (domain.BLOCKER_MISSING_PROVENANCE,), "comment": "fix"}),
])
def test_invalid_transition_from_a_terminal_state_is_rejected(harness, command_name, kwargs):
    draft = _readable_draft()
    harness.seed(draft)
    env = harness.envelope(draft["id"], idempotency_key="terminal-1")
    harness.service.approve_publication(env, approval_basis=domain.BASIS_FULL_ARTICLE)

    second_env = domain.CommandEnvelope(
        draft_id=draft["id"], actor_id="alice", idempotency_key="terminal-2", expected_version=2,
        reviewed_content_digest=env.reviewed_content_digest,
    )
    method = getattr(harness.service, command_name)
    with pytest.raises(domain.CommandError) as exc_info:
        method(second_env, **kwargs)
    assert exc_info.value.code == domain.ERROR_ALREADY_DECIDED


# ---------------------------------------------------------------------------
# Approval content-basis coverage: readable / transcript / metadata-only /
# navigation-only blocking
# ---------------------------------------------------------------------------


def test_readable_article_approval_creates_a_trusted_publication_with_full_article_basis(harness):
    draft = _readable_draft()
    harness.seed(draft)
    env = harness.envelope(draft["id"])
    result = harness.service.approve_publication(env, approval_basis=domain.BASIS_FULL_ARTICLE)
    assert result.resulting_state == domain.APPROVED
    record = json.loads(harness.evidence_file(draft["id"]).read_text(encoding="utf-8"))
    assert record["publication_content_basis"] == domain.BASIS_FULL_ARTICLE
    assert record["limited_content"] is False
    assert record["fact_ids"] == []
    assert record["relationship_ids"] == []


def test_transcript_backed_approval_creates_a_trusted_publication_with_transcript_basis(harness):
    draft = _transcript_draft()
    harness.seed(draft)
    env = harness.envelope(draft["id"])
    result = harness.service.approve_publication(env, approval_basis=domain.BASIS_FULL_TRANSCRIPT)
    assert result.resulting_state == domain.APPROVED
    record = json.loads(harness.evidence_file(draft["id"]).read_text(encoding="utf-8"))
    assert record["publication_content_basis"] == domain.BASIS_FULL_TRANSCRIPT
    assert record["transcript"]["status"] == "available"


def test_metadata_only_approval_requires_limited_content_basis_and_warning_acknowledgment(harness):
    draft = _thin_draft()
    harness.seed(draft)
    env = harness.envelope(draft["id"])
    # Wrong basis for this content is rejected.
    with pytest.raises(domain.CommandError) as exc_info:
        harness.service.approve_publication(env, approval_basis=domain.BASIS_FULL_ARTICLE)
    assert exc_info.value.code == domain.ERROR_INELIGIBLE

    # Correct basis without acknowledging warnings is rejected.
    with pytest.raises(domain.CommandError) as exc_info:
        harness.service.approve_publication(env, approval_basis=domain.BASIS_LIMITED_CONTENT)
    assert exc_info.value.code == domain.ERROR_INVALID_COMMAND

    # Correct basis with explicit acknowledgment succeeds and is labeled.
    eligibility = domain.check_eligibility(draft)
    result = harness.service.approve_publication(
        env, approval_basis=domain.BASIS_LIMITED_CONTENT, warning_acknowledgments=eligibility.warnings,
    )
    assert result.resulting_state == domain.APPROVED
    record = json.loads(harness.evidence_file(draft["id"]).read_text(encoding="utf-8"))
    assert record["limited_content"] is True
    assert record["publication_content_basis"] == domain.BASIS_LIMITED_CONTENT


def test_navigation_only_shell_can_never_be_approved(harness):
    draft = _shell_draft()
    harness.seed(draft)
    env = harness.envelope(draft["id"])
    for basis in domain.APPROVAL_BASES:
        with pytest.raises(domain.CommandError) as exc_info:
            harness.service.approve_publication(env, approval_basis=basis)
        assert exc_info.value.code == domain.ERROR_INELIGIBLE
    assert not harness.evidence_file(draft["id"]).exists()


def test_navigation_only_shell_can_be_rejected(harness):
    draft = _shell_draft()
    harness.seed(draft)
    env = harness.envelope(draft["id"])
    result = harness.service.reject_publication(env, reason_code="navigation_only_shell", comment="empty page, no body")
    assert result.resulting_state == domain.REJECTED


# ---------------------------------------------------------------------------
# Prohibited side effects: approval creates ONLY the trusted publication
# ---------------------------------------------------------------------------


def test_approval_creates_no_entities_facts_relationships_signals_assessments_recommendations(harness):
    draft = _readable_draft()
    harness.seed(draft)
    env = harness.envelope(draft["id"])
    harness.service.approve_publication(env, approval_basis=domain.BASIS_FULL_ARTICLE)

    for folder in ("entities", "facts", "relationships", "signals", "assessments", "recommendations"):
        directory = harness.data_dir / folder
        files = list(directory.rglob("*.json")) if directory.exists() else []
        assert files == [], f"unexpected writes under data/{folder}: {files}"


def test_approval_creates_no_atomic_evidence(harness):
    draft = _readable_draft()
    harness.seed(draft)
    env = harness.envelope(draft["id"])
    harness.service.approve_publication(env, approval_basis=domain.BASIS_FULL_ARTICLE)

    for path in (harness.data_dir / "evidence").glob("*.json"):
        record = json.loads(path.read_text(encoding="utf-8"))
        assert record.get("evidence_role") != "atomic_evidence"


def test_approval_never_calls_review_publish_service(harness, monkeypatch):
    """A direct proof, not just an absence-of-import check: patch
    ReviewPublishService.publish to explode, and confirm a normal approval
    still succeeds -- the command service never reaches that code path."""
    from app.services.review_publish import ReviewPublishService

    def _explode(self, request):
        raise AssertionError("ReviewPublishService.publish() must never be called by the command service")

    monkeypatch.setattr(ReviewPublishService, "publish", _explode)
    draft = _readable_draft()
    harness.seed(draft)
    env = harness.envelope(draft["id"])
    result = harness.service.approve_publication(env, approval_basis=domain.BASIS_FULL_ARTICLE)
    assert result.resulting_state == domain.APPROVED


def test_only_one_trusted_publication_and_one_decision_event_created(harness):
    draft = _readable_draft()
    harness.seed(draft)
    env = harness.envelope(draft["id"])
    harness.service.approve_publication(env, approval_basis=domain.BASIS_FULL_ARTICLE)
    assert len(list((harness.data_dir / "evidence").glob("*.json"))) == 1
    events = list(harness.inbox_dir.rglob("*.json"))
    assert len(events) == 1


# ---------------------------------------------------------------------------
# Read operations expose only complete states
# ---------------------------------------------------------------------------


def test_get_publication_review_includes_eligibility_and_permitted_commands(harness):
    draft = _readable_draft()
    harness.seed(draft)
    view = harness.service.get_publication_review(draft["id"])
    assert view["state"] == domain.PENDING_REVIEW
    assert view["eligibility"]["result"] == domain.ELIGIBLE
    assert domain.CMD_APPROVE in view["permitted_commands"]


def test_status_summary_counts_by_state(harness):
    harness.seed(_readable_draft(draft_id="a"))
    harness.seed(_readable_draft(draft_id="b"))
    env = harness.envelope("a")
    harness.service.reject_publication(env, reason_code="not_relevant", comment="no")
    summary = harness.service.status_summary()
    assert summary["total"] == 2
    assert summary["by_state"][domain.REJECTED] == 1
    assert summary["by_state"][domain.PENDING_REVIEW] == 1


def test_decision_history_is_recorded_and_append_only_shaped(harness):
    draft = _readable_draft()
    harness.seed(draft)
    env = harness.envelope(draft["id"])
    harness.service.reject_publication(env, reason_code="not_relevant", comment="no")
    history = harness.service.decision_history(draft["id"])
    assert len(history) == 1
    assert history[0]["command"] == domain.CMD_REJECT
