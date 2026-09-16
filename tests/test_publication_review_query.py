"""Publication Review Durable Read Model V1 -- read/query seam tests.

Every test uses a `tmp_path`-rooted `DurableReviewRepository` and (where a
real state transition is needed) the real `PublicationReviewCommandService`
to produce it -- never a hand-faked `DraftState` pretending to be
`approved`/`rejected`/etc. without actually going through a real command.
This proves the read model reflects genuine repository content, not a
parallel interpretation of it.
"""

from __future__ import annotations

import hashlib
import json

import pytest

from app.composition import get_repositories
from app.repositories.paths import SCHEMAS_DIR
from app.services import publication_review_domain as domain
from app.services import publication_review_query as query
from app.services.publication_review_command import (
    ActorIdentity, CommandDependencies, InMemoryActorDirectory, PublicationReviewCommandService,
    PERMISSION_PUBLICATION_REVIEW,
)
from app.services.publication_review_migration import import_inbox_draft
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


class Harness:
    def __init__(self, tmp_path):
        self.tmp_path = tmp_path
        self.data_dir = tmp_path / "data"
        (self.data_dir / "evidence").mkdir(parents=True)
        self.inbox_dir = tmp_path / "inbox"
        self.review_root = tmp_path / "review_state"
        self.repository = DurableReviewRepository(self.review_root)
        self.actors = InMemoryActorDirectory()
        self.actors.register(ActorIdentity(actor_id="alice", kind="human", permissions=frozenset({PERMISSION_PUBLICATION_REVIEW})))
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

    def envelope(self, draft_id, *, idempotency_key="k1", version=1, digest=None) -> domain.CommandEnvelope:
        if digest is None:
            digest = self.repository.get_draft_state(draft_id).content_digest
        return domain.CommandEnvelope(
            draft_id=draft_id, actor_id="alice", idempotency_key=idempotency_key, expected_version=version,
            reviewed_content_digest=digest,
        )


@pytest.fixture
def harness(tmp_path):
    return Harness(tmp_path)


def _tree_snapshot(*roots):
    snapshot = {}
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file():
                snapshot[str(path)] = path.read_bytes()
    return snapshot


# ---------------------------------------------------------------------------
# Empty store
# ---------------------------------------------------------------------------


def test_empty_store_queue_is_empty(harness):
    page = query.list_queue(harness.repository)
    assert page.items == ()
    assert page.total_matching == 0
    assert page.next_cursor is None


def test_empty_store_status_summary_is_all_zero(harness):
    summary = query.status_summary(harness.repository)
    assert summary["total"] == 0
    assert all(count == 0 for count in summary["by_state"].values())


def test_empty_store_detail_for_unknown_id_is_none(harness):
    assert query.get_detail(harness.repository, "does-not-exist") is None


# ---------------------------------------------------------------------------
# Pending review
# ---------------------------------------------------------------------------


def test_pending_review_appears_in_queue_and_detail(harness):
    draft = _readable_draft()
    harness.seed(draft)
    page = query.list_queue(harness.repository)
    assert len(page.items) == 1
    assert page.items[0]["review_state"] == domain.PENDING_REVIEW
    assert page.items[0]["draft_id"] == draft["id"]

    detail = query.get_detail(harness.repository, draft["id"])
    assert detail["review_state"] == domain.PENDING_REVIEW
    assert domain.CMD_APPROVE in detail["permitted_commands"]
    assert detail["decision_history"] == []
    assert detail["publication_binding"] is None


# ---------------------------------------------------------------------------
# Approved / rejected / deferred / correction-requested states
# ---------------------------------------------------------------------------


def test_approved_state_reflected_with_publication_binding(harness):
    draft = _readable_draft()
    harness.seed(draft)
    env = harness.envelope(draft["id"])
    harness.service.approve_publication(env, approval_basis=domain.BASIS_FULL_ARTICLE)

    detail = query.get_detail(harness.repository, draft["id"])
    assert detail["review_state"] == domain.APPROVED
    assert detail["publication_binding"]["publication_id"] == draft["id"]
    assert detail["decision_history"][-1]["command"] == domain.CMD_APPROVE
    assert domain.permitted_commands(domain.APPROVED) == tuple(detail["permitted_commands"])


def test_approved_publication_binding_can_be_verified_against_evidence_reader(harness):
    draft = _readable_draft()
    harness.seed(draft)
    env = harness.envelope(draft["id"])
    harness.service.approve_publication(env, approval_basis=domain.BASIS_FULL_ARTICLE)

    detail = query.get_detail(harness.repository, draft["id"], evidence_reader=harness.repositories.evidence)
    assert detail["publication_verified"] is True


def test_rejected_state_reflected(harness):
    draft = _readable_draft()
    harness.seed(draft)
    env = harness.envelope(draft["id"])
    harness.service.reject_publication(env, reason_code="not_relevant", comment="no berries mentioned")

    detail = query.get_detail(harness.repository, draft["id"])
    assert detail["review_state"] == domain.REJECTED
    assert detail["decision_history"][-1]["reason_category"] == "not_relevant"
    assert detail["decision_history"][-1]["comment"] == "no berries mentioned"
    assert detail["publication_binding"] is None


def test_deferred_state_reflected(harness):
    draft = _readable_draft()
    harness.seed(draft)
    env = harness.envelope(draft["id"])
    harness.service.defer_publication(env, reason_code="operator_capacity")

    detail = query.get_detail(harness.repository, draft["id"])
    assert detail["review_state"] == domain.DEFERRED
    assert domain.CMD_RETURN_TO_REVIEW in detail["permitted_commands"]


def test_correction_requested_state_reflected(harness):
    draft = _shell_draft()
    harness.seed(draft)
    env = harness.envelope(draft["id"])
    harness.service.request_publication_correction(
        env, blocker_codes=(domain.BLOCKER_MISSING_PROVENANCE,), comment="needs a real source_url",
    )
    detail = query.get_detail(harness.repository, draft["id"])
    assert detail["review_state"] == domain.CORRECTION_REQUIRED
    assert detail["decision_history"][-1]["reason_category"] == domain.BLOCKER_MISSING_PROVENANCE


# ---------------------------------------------------------------------------
# Corrected draft returned to review
# ---------------------------------------------------------------------------


def test_corrected_draft_returns_to_pending_review_with_updated_content(harness):
    draft = _shell_draft()
    harness.seed(draft)
    request_env = harness.envelope(draft["id"])
    requested = harness.service.request_publication_correction(
        request_env, blocker_codes=(domain.BLOCKER_MISSING_PROVENANCE,), comment="fix the url",
    )
    submit_env = harness.envelope(draft["id"], idempotency_key="submit-1", version=requested.resulting_version)
    harness.service.submit_publication_correction(
        submit_env, patch={"source_url": "https://example.invalid/corrected"}, comment="fixed",
    )

    detail = query.get_detail(harness.repository, draft["id"])
    assert detail["review_state"] == domain.PENDING_REVIEW
    assert detail["source_url"] == "https://example.invalid/corrected"
    correction_history = detail["correction_history"]
    assert [row["command"] for row in correction_history] == [domain.CMD_REQUEST_CORRECTION, domain.CMD_SUBMIT_CORRECTION]


def test_returned_to_review_from_deferred(harness):
    draft = _readable_draft()
    harness.seed(draft)
    deferred = harness.service.defer_publication(harness.envelope(draft["id"]), reason_code="operator_capacity")
    return_env = harness.envelope(draft["id"], idempotency_key="return-1", version=deferred.resulting_version)
    harness.service.return_publication_to_review(return_env, comment="ready now")

    detail = query.get_detail(harness.repository, draft["id"])
    assert detail["review_state"] == domain.PENDING_REVIEW
    commands = [row["command"] for row in detail["decision_history"]]
    assert commands == [domain.CMD_DEFER, domain.CMD_RETURN_TO_REVIEW]


# ---------------------------------------------------------------------------
# Superseded duplicate
# ---------------------------------------------------------------------------


def test_superseded_duplicate_exposes_supersession_metadata(harness):
    draft = _readable_draft()
    harness.seed(draft)
    env = harness.envelope(draft["id"])
    harness.service.supersede_publication_duplicate(
        env, survivor_id="ev-real-survivor", identity_basis="canonical_url", comment="same article, different id",
    )
    detail = query.get_detail(harness.repository, draft["id"])
    assert detail["review_state"] == domain.SUPERSEDED_DUPLICATE
    assert detail["supersession"] == {"survivor_id": "ev-real-survivor", "identity_basis": "canonical_url"}


def test_non_superseded_draft_has_no_supersession_metadata(harness):
    draft = _readable_draft()
    harness.seed(draft)
    detail = query.get_detail(harness.repository, draft["id"])
    assert detail["supersession"] is None


# ---------------------------------------------------------------------------
# Multiple revisions and decision-history ordering
# ---------------------------------------------------------------------------


def test_multiple_revisions_preserve_chronological_decision_history_order(harness):
    draft = _readable_draft()
    harness.seed(draft)
    env1 = harness.envelope(draft["id"], idempotency_key="rev-1")
    r1 = harness.service.revise_publication_draft(env1, patch={"title": "First revision"})
    env2 = harness.envelope(draft["id"], idempotency_key="rev-2", version=r1.resulting_version)
    r2 = harness.service.revise_publication_draft(env2, patch={"title": "Second revision"})
    env3 = harness.envelope(draft["id"], idempotency_key="reject-1", version=r2.resulting_version)
    harness.service.reject_publication(env3, reason_code="not_relevant", comment="final decision")

    detail = query.get_detail(harness.repository, draft["id"])
    commands = [row["command"] for row in detail["decision_history"]]
    assert commands == [domain.CMD_REVISE, domain.CMD_REVISE, domain.CMD_REJECT]
    # Chronological, not reverse-chronological.
    occurred = [row["occurred_at"] for row in detail["decision_history"]]
    assert occurred == sorted(occurred)
    assert detail["title"] == "Second revision"


# ---------------------------------------------------------------------------
# Missing or stale referenced state
# ---------------------------------------------------------------------------


def test_publication_binding_referencing_a_deleted_evidence_file_is_reported_unverified(harness):
    draft = _readable_draft()
    harness.seed(draft)
    env = harness.envelope(draft["id"])
    harness.service.approve_publication(env, approval_basis=domain.BASIS_FULL_ARTICLE)

    # Simulate the referenced trusted record having been removed out-of-band.
    (harness.data_dir / "evidence" / f"{draft['id']}.json").unlink()

    detail = query.get_detail(harness.repository, draft["id"], evidence_reader=harness.repositories.evidence)
    assert detail["publication_binding"] is not None  # the binding itself is still honestly reported
    assert detail["publication_verified"] is False  # but it no longer resolves


def test_detail_without_an_evidence_reader_reports_verification_as_unknown_not_false(harness):
    draft = _readable_draft()
    harness.seed(draft)
    env = harness.envelope(draft["id"])
    harness.service.approve_publication(env, approval_basis=domain.BASIS_FULL_ARTICLE)

    detail = query.get_detail(harness.repository, draft["id"])  # no evidence_reader passed
    assert detail["publication_binding"] is not None
    assert detail["publication_verified"] is None


# ---------------------------------------------------------------------------
# Interrupted transaction visibility
# ---------------------------------------------------------------------------


def test_interrupted_transaction_is_visible_but_never_reported_as_approved(harness):
    draft = _readable_draft()
    harness.seed(draft)
    env = harness.envelope(draft["id"])

    class Boom(Exception):
        pass

    # Simplest reliable injection: monkeypatch append_review_event so the
    # transaction gets through every staging phase and the real evidence
    # write, then crashes before the real audit event / draft flip.
    from app.services import publication_review_command as command_module
    original = command_module.append_review_event

    def _crash_once(*args, **kwargs):
        raise Boom("simulated crash before the real audit event")

    command_module.append_review_event = _crash_once
    try:
        with pytest.raises(Boom):
            harness.service.approve_publication(env, approval_basis=domain.BASIS_FULL_ARTICLE)
    finally:
        command_module.append_review_event = original

    # The draft itself still honestly reads pending_review...
    detail = query.get_detail(harness.repository, draft["id"])
    assert detail["review_state"] == domain.PENDING_REVIEW
    assert detail["publication_binding"] is None
    # ...but the read model surfaces the real, uncommitted transaction
    # rather than hiding it or claiming it is approved.
    assert detail["promotion_status"]["has_pending_transaction"] is True
    assert detail["promotion_status"]["pending_transactions"][0]["resumable"] is True
    assert detail["promotion_status"]["pending_transactions"][0]["committed"] is False


def test_promotion_status_is_empty_for_a_draft_with_no_transaction(harness):
    draft = _readable_draft()
    harness.seed(draft)
    status = query.promotion_status(harness.repository, draft["id"])
    assert status == {"has_pending_transaction": False, "pending_transactions": []}


def test_committed_approval_shows_no_pending_transaction(harness):
    draft = _readable_draft()
    harness.seed(draft)
    env = harness.envelope(draft["id"])
    harness.service.approve_publication(env, approval_basis=domain.BASIS_FULL_ARTICLE)
    status = query.promotion_status(harness.repository, draft["id"])
    assert status["has_pending_transaction"] is False


# ---------------------------------------------------------------------------
# Actor redaction / serialization boundaries
# ---------------------------------------------------------------------------


def test_decision_event_serialization_only_exposes_the_whitelisted_fields(harness):
    draft = _readable_draft()
    harness.seed(draft)
    env = harness.envelope(draft["id"])
    harness.service.reject_publication(env, reason_code="not_relevant", comment="no")

    detail = query.get_detail(harness.repository, draft["id"])
    event = detail["decision_history"][0]
    assert set(event.keys()) == {
        "command", "actor_id", "occurred_at", "reason_category", "comment",
        "resulting_state", "resulting_version", "event_id",
    }
    assert event["actor_id"] == "alice"
    assert "idempotency_key" not in event


def test_raw_repository_event_has_more_fields_than_the_serialized_view(harness):
    """Confirms the whitelist is actually doing something -- the raw
    stored event carries strictly more fields than the redacted view."""
    draft = _readable_draft()
    harness.seed(draft)
    env = harness.envelope(draft["id"])
    harness.service.reject_publication(env, reason_code="not_relevant", comment="no")

    raw_state = harness.repository.get_draft_state(draft["id"])
    raw_event = raw_state.decision_history[0]
    serialized = query.decision_history_view(raw_state)[0]
    assert set(serialized.keys()) < set(raw_event.keys())
    assert "idempotency_key" in raw_event


# ---------------------------------------------------------------------------
# Stable results across repeated reads
# ---------------------------------------------------------------------------


def test_repeated_queue_reads_are_identical(harness):
    harness.seed(_readable_draft(draft_id="a"))
    harness.seed(_readable_draft(draft_id="b"))
    first = query.list_queue(harness.repository).as_dict()
    second = query.list_queue(harness.repository).as_dict()
    assert first == second


def test_repeated_detail_reads_are_identical(harness):
    draft = _readable_draft()
    harness.seed(draft)
    first = query.get_detail(harness.repository, draft["id"])
    second = query.get_detail(harness.repository, draft["id"])
    assert first == second


def test_pagination_cursor_resumes_deterministically(harness):
    for i in range(5):
        harness.seed(_readable_draft(draft_id=f"item-{i}"))
    page1 = query.list_queue(harness.repository, page_size=2)
    assert len(page1.items) == 2
    assert page1.next_cursor is not None
    page2 = query.list_queue(harness.repository, page_size=2, cursor=page1.next_cursor)
    assert len(page2.items) == 2
    ids_page1 = {row["draft_id"] for row in page1.items}
    ids_page2 = {row["draft_id"] for row in page2.items}
    assert ids_page1.isdisjoint(ids_page2)


# ---------------------------------------------------------------------------
# Byte-identical repository/canonical state before and after all reads
# ---------------------------------------------------------------------------


def test_reads_never_mutate_the_durable_repository_or_data_dir(harness):
    harness.seed(_readable_draft(
        draft_id="ev-media-a", title="Article A", source_id="source-a",
        source_url="https://example.invalid/article-a",
    ))
    harness.seed(_readable_draft(
        draft_id="ev-media-b", title="Article B", source_id="source-b",
        source_url="https://example.invalid/article-b",
    ))
    env = harness.envelope("ev-media-a")
    harness.service.approve_publication(env, approval_basis=domain.BASIS_FULL_ARTICLE)

    before = _tree_snapshot(harness.review_root, harness.data_dir, harness.inbox_dir)

    query.list_queue(harness.repository)
    query.get_detail(harness.repository, "ev-media-a")
    query.get_detail(harness.repository, "ev-media-b")
    query.status_summary(harness.repository)
    query.promotion_status(harness.repository, "ev-media-a")
    query.hydrated_excerpt(harness.repository.get_draft_state("ev-media-a"))

    after = _tree_snapshot(harness.review_root, harness.data_dir, harness.inbox_dir)
    assert before == after


# ---------------------------------------------------------------------------
# No leakage of full acquired article bodies
# ---------------------------------------------------------------------------


def test_queue_item_never_contains_article_paragraphs_or_transcript_segments(harness):
    draft = _readable_draft()
    harness.seed(draft)
    item = query.queue_item_view(harness.repository.get_draft_state(draft["id"]), repository=harness.repository)
    serialized = json.dumps(item)
    assert "word word word" not in serialized  # the actual body text
    assert "paragraphs" not in item
    assert "article" not in item


def test_detail_view_never_contains_the_full_article_text(harness):
    draft = _readable_draft()
    harness.seed(draft)
    detail = query.get_detail(harness.repository, draft["id"])
    full_body = "word " * 300
    serialized = json.dumps(detail)
    assert full_body not in serialized
    assert detail["excerpt"]["truncated"] is True
    assert len(detail["excerpt"]["excerpt"]) <= query.EXCERPT_MAX_CHARS


def test_hydrated_excerpt_is_bounded_and_never_the_full_body(harness):
    draft = _readable_draft()
    harness.seed(draft)
    excerpt = query.hydrated_excerpt(harness.repository.get_draft_state(draft["id"]))
    assert excerpt["full_body_available"] is True
    assert excerpt["truncated"] is True
    assert len(excerpt["excerpt"]) == query.EXCERPT_MAX_CHARS


def test_short_body_excerpt_is_not_marked_truncated(harness):
    draft = _readable_draft(article={
        "word_count": 5, "paragraphs": [{"index": 0, "text": "short body text"}], "content_sha256": "b" * 64,
    })
    harness.seed(draft)
    excerpt = query.hydrated_excerpt(harness.repository.get_draft_state(draft["id"]))
    assert excerpt["excerpt"] == "short body text"
    assert excerpt["truncated"] is False


def test_readonly_ui_compatible_projection_also_never_leaks_full_body(harness):
    draft = _readable_draft()
    harness.seed(draft)
    item = query.queue_item_view(harness.repository.get_draft_state(draft["id"]), repository=harness.repository)
    compatible = query.to_readonly_ui_compatible(item)
    serialized = json.dumps(compatible)
    assert "word word word" not in serialized


# ---------------------------------------------------------------------------
# Compatibility with imported legacy review records
# ---------------------------------------------------------------------------


def _inbox_shaped_draft(draft_id="ev-media-legacy") -> dict:
    return {
        "id": draft_id, "record_type": "evidence", "status": "draft", "review_state": "in_review",
        "source_type": "discovered_media", "title": "A legacy imported draft",
        "source_name": "Example Source", "source_url": "https://example.invalid/legacy-item",
        "published_date": "2026-09-01", "captured_date": "2026-09-16",
        "summary": "A short summary.", "submitted_by": "media-orchestration",
        "article": {
            "word_count": 250, "paragraphs": [{"index": 0, "text": "word " * 250}], "content_sha256": "c" * 64,
        },
    }


def test_imported_legacy_draft_is_readable_and_flagged(harness):
    outcome = import_inbox_draft(harness.repository, _inbox_shaped_draft())
    assert outcome.created is True
    detail = query.get_detail(harness.repository, "ev-media-legacy")
    assert detail is not None
    assert detail["review_state"] == domain.PENDING_REVIEW
    assert detail["is_legacy_import"] is True
    assert detail["decision_history"] == []


def test_legacy_draft_stops_being_flagged_once_it_has_a_real_decision(harness):
    import_inbox_draft(harness.repository, _inbox_shaped_draft())
    env = harness.envelope("ev-media-legacy")
    harness.service.reject_publication(env, reason_code="not_relevant", comment="no")
    detail = query.get_detail(harness.repository, "ev-media-legacy")
    assert detail["is_legacy_import"] is False


def test_natively_seeded_draft_is_not_flagged_as_legacy_import(harness):
    draft = _readable_draft()
    harness.seed(draft)
    detail = query.get_detail(harness.repository, draft["id"])
    assert detail["is_legacy_import"] is False
