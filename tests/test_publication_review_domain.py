"""Publication Review Command Service V1 -- pure domain tests (Slice 1).

No filesystem, no repository, no HTTP -- every test here is a plain
function call against `app.services.publication_review_domain`.
"""

from __future__ import annotations

import pytest

from app.services import publication_review_domain as domain


# ---------------------------------------------------------------------------
# State machine: every valid transition, table-driven
# ---------------------------------------------------------------------------

VALID_TRANSITIONS = [
    (domain.PENDING_REVIEW, domain.CMD_APPROVE, domain.APPROVED),
    (domain.PENDING_REVIEW, domain.CMD_REJECT, domain.REJECTED),
    (domain.PENDING_REVIEW, domain.CMD_DEFER, domain.DEFERRED),
    (domain.PENDING_REVIEW, domain.CMD_REQUEST_CORRECTION, domain.CORRECTION_REQUIRED),
    (domain.PENDING_REVIEW, domain.CMD_SUPERSEDE_DUPLICATE, domain.SUPERSEDED_DUPLICATE),
    (domain.DEFERRED, domain.CMD_RETURN_TO_REVIEW, domain.PENDING_REVIEW),
    (domain.DEFERRED, domain.CMD_REJECT, domain.REJECTED),
    (domain.CORRECTION_REQUIRED, domain.CMD_SUBMIT_CORRECTION, domain.PENDING_REVIEW),
    (domain.CORRECTION_REQUIRED, domain.CMD_REJECT, domain.REJECTED),
]


@pytest.mark.parametrize("from_state,command,to_state", VALID_TRANSITIONS)
def test_every_valid_transition(from_state, command, to_state):
    assert domain.is_valid_transition(from_state, command)
    assert domain.next_state(from_state, command) == to_state
    assert command in domain.permitted_commands(from_state)


# Every (state, command) pair NOT in VALID_TRANSITIONS is invalid -- build
# the full cross product and assert everything not explicitly valid fails.
ALL_STATES = domain.REVIEW_STATES
ALL_COMMANDS = (
    domain.CMD_APPROVE, domain.CMD_REJECT, domain.CMD_DEFER, domain.CMD_REQUEST_CORRECTION,
    domain.CMD_SUBMIT_CORRECTION, domain.CMD_RETURN_TO_REVIEW, domain.CMD_SUPERSEDE_DUPLICATE,
)
VALID_PAIRS = {(f, c) for f, c, _ in VALID_TRANSITIONS}


@pytest.mark.parametrize("state", ALL_STATES)
@pytest.mark.parametrize("command", ALL_COMMANDS)
def test_every_invalid_transition_is_rejected(state, command):
    if (state, command) in VALID_PAIRS:
        pytest.skip("valid transition, covered above")
    assert not domain.is_valid_transition(state, command)
    assert domain.next_state(state, command) is None


def test_terminal_states_have_no_permitted_decision_commands():
    for state in domain.TERMINAL_STATES:
        permitted = domain.permitted_commands(state)
        # A terminal state may still be inspected/listed but no decision
        # command should be able to fire again from it.
        assert set(permitted).isdisjoint(domain.DECISION_COMMANDS - {domain.CMD_RETURN_TO_REVIEW})


def test_revisitable_and_terminal_states_partition_all_states():
    assert domain.REVISITABLE_STATES | domain.TERMINAL_STATES == set(domain.REVIEW_STATES)
    assert domain.REVISITABLE_STATES & domain.TERMINAL_STATES == set()


# ---------------------------------------------------------------------------
# Eligibility content matrix -- every row from PUBLICATION-REVIEW-CONTRACT-V1.md
# ---------------------------------------------------------------------------


def _base_draft(**overrides) -> dict:
    draft = {
        "id": "ev-media-1", "title": "A real headline", "source_id": "source-1",
        "source_url": "https://example.invalid/a", "captured_date": "2026-09-16",
        "submitted_by": "media-orchestration", "summary": "", "published_date": "2026-09-15",
        "evidence_role": "publication_artifact",
    }
    draft.update(overrides)
    return draft


def _readable_article(word_count=300) -> dict:
    text = "word " * word_count
    return _base_draft(article={
        "word_count": word_count, "paragraphs": [{"index": 0, "text": text}], "content_sha256": "a" * 64,
    })


def _partial_article() -> dict:
    return _base_draft(article={
        "word_count": 40, "paragraphs": [{"index": 0, "text": "short body text here, forty words is still less than the four hundred char floor for a body available state so this remains partial only"}],
        "content_sha256": "b" * 64,
    })


def _full_transcript() -> dict:
    return _base_draft(media_format="podcast", transcript={
        "status": "available", "segments": [{"start": 0, "end": 5, "text": "hello world this is a transcript segment"}],
    })


def _structured_registry() -> dict:
    return _base_draft(source_type="patent", patent_filing={"filing_number": "US123", "status": "granted"})


def _thin_description() -> dict:
    return _base_draft(publisher_description="A short publisher blurb about the article.")


def _navigation_only_shell() -> dict:
    return _base_draft(discovery_provenance={"acquisition_failure_category": "EMPTY_BODY"})


def _retryable_failure() -> dict:
    return _base_draft(discovery_provenance={"acquisition_failure_category": "TIMEOUT"})


def _missing_provenance() -> dict:
    draft = _base_draft()
    del draft["source_id"]
    del draft["source_url"]
    return draft


def test_full_readable_article_is_eligible():
    result = domain.check_eligibility(_readable_article())
    assert result.result == domain.ELIGIBLE
    assert result.approvable
    assert result.permitted_approval_bases == (domain.BASIS_FULL_ARTICLE,)
    assert result.content_class == "FULL_ARTICLE"


def test_partial_readable_article_is_eligible_with_warnings():
    result = domain.check_eligibility(_partial_article())
    assert result.result == domain.ELIGIBLE_WITH_WARNINGS
    assert result.approvable
    assert result.permitted_approval_bases == (domain.BASIS_PARTIAL_ARTICLE,)
    assert domain.WARNING_PARTIAL_CONTENT in result.warnings


def test_full_transcript_is_eligible():
    result = domain.check_eligibility(_full_transcript())
    assert result.result == domain.ELIGIBLE
    assert result.permitted_approval_bases == (domain.BASIS_FULL_TRANSCRIPT,)


def test_structured_registry_is_eligible():
    result = domain.check_eligibility(_structured_registry())
    assert result.result == domain.ELIGIBLE
    assert result.permitted_approval_bases == (domain.BASIS_STRUCTURED_REGISTRY,)


def test_generic_thin_description_is_eligible_with_warnings_as_limited_content_only():
    result = domain.check_eligibility(_thin_description())
    assert result.result == domain.ELIGIBLE_WITH_WARNINGS
    assert result.permitted_approval_bases == (domain.BASIS_LIMITED_CONTENT,)
    assert domain.WARNING_THIN_CONTENT in result.warnings
    assert domain.WARNING_UPGRADE_AVAILABLE in result.warnings


def test_navigation_only_shell_is_blocked_never_approvable():
    result = domain.check_eligibility(_navigation_only_shell())
    assert result.result == domain.BLOCKED
    assert not result.approvable
    assert result.permitted_approval_bases == ()
    assert domain.BLOCKER_NAVIGATION_ONLY_SHELL in result.blockers


def test_retryable_failure_is_blocked_not_permanent_metadata_trust():
    result = domain.check_eligibility(_retryable_failure())
    assert result.result == domain.BLOCKED
    assert domain.BLOCKER_RETRYABLE_ACQUISITION in result.blockers


def test_unsupported_source_kind_is_blocked():
    draft = _base_draft(evidence_role="atomic_evidence")
    result = domain.check_eligibility(draft)
    assert result.result == domain.BLOCKED
    assert domain.BLOCKER_UNSUPPORTED_SOURCE in result.blockers


def test_malformed_missing_provenance_is_blocked():
    result = domain.check_eligibility(_missing_provenance())
    assert result.result == domain.BLOCKED
    assert domain.BLOCKER_MISSING_PROVENANCE in result.blockers


def test_deterministic_duplicate_is_blocked():
    existing = [{"id": "ev-existing", "source_url": "https://example.invalid/a", "status": "published"}]
    result = domain.check_eligibility(_readable_article(), existing_trusted_and_pending=existing)
    assert result.result == domain.BLOCKED
    assert domain.BLOCKER_DETERMINISTIC_DUPLICATE in result.blockers
    assert result.duplicate_of == "ev-existing"


def test_unresolved_entity_link_is_blocked():
    draft = _readable_article()
    draft["entity_ids"] = ["company-does-not-exist"]
    result = domain.check_eligibility(draft, resolvable_entity_ids=frozenset())
    assert result.result == domain.BLOCKED
    assert domain.BLOCKER_UNRESOLVED_ENTITY_LINK in result.blockers


def test_resolved_entity_link_does_not_block():
    draft = _readable_article()
    draft["entity_ids"] = ["company-real"]
    result = domain.check_eligibility(draft, resolvable_entity_ids=frozenset({"company-real"}))
    assert result.approvable


def test_unknown_publication_date_produces_a_warning_not_a_blocker():
    draft = _readable_article()
    draft["published_date"] = None
    result = domain.check_eligibility(draft)
    assert result.approvable
    assert domain.WARNING_UNKNOWN_DATE in result.warnings


def test_ai_enrichment_present_produces_a_visible_warning():
    draft = _readable_article()
    draft["ai_enrichment"] = {"model_provenance": {"status": "ok"}}
    result = domain.check_eligibility(draft)
    assert domain.WARNING_AI_ENRICHMENT in result.warnings


# ---------------------------------------------------------------------------
# Deterministic identity
# ---------------------------------------------------------------------------


def test_identity_key_prefers_canonical_url():
    draft = _readable_article()
    key = domain.publication_identity_key(draft)
    assert key.startswith("url:")
    assert "example.invalid/a" in key


def test_identity_key_falls_back_to_title_source_date_when_no_url():
    draft = _readable_article()
    draft["source_url"] = ""
    key = domain.publication_identity_key(draft)
    assert key.startswith("tsd:")


def test_identity_key_is_stable_for_the_same_logical_item():
    a = domain.publication_identity_key(_readable_article())
    b = domain.publication_identity_key(_readable_article())
    assert a == b


# ---------------------------------------------------------------------------
# Content and provenance digests
# ---------------------------------------------------------------------------


def test_content_digest_is_deterministic_for_identical_input():
    draft = _readable_article()
    assert domain.compute_review_content_digest(draft) == domain.compute_review_content_digest(draft)


def test_content_digest_changes_when_a_review_relevant_field_changes():
    draft = _readable_article()
    digest_before = domain.compute_review_content_digest(draft)
    draft["title"] = "A different headline"
    digest_after = domain.compute_review_content_digest(draft)
    assert digest_before != digest_after


def test_content_digest_changes_when_body_hash_changes():
    draft = _readable_article()
    digest_before = domain.compute_review_content_digest(draft)
    draft["article"]["content_sha256"] = "f" * 64
    digest_after = domain.compute_review_content_digest(draft)
    assert digest_before != digest_after


def test_provenance_digest_is_independent_of_summary_text():
    draft = _readable_article()
    before = domain.compute_provenance_digest(draft)
    draft["summary"] = "a completely rewritten summary"
    after = domain.compute_provenance_digest(draft)
    assert before == after


def test_provenance_digest_changes_when_source_id_changes():
    draft = _readable_article()
    before = domain.compute_provenance_digest(draft)
    draft["source_id"] = "source-different"
    after = domain.compute_provenance_digest(draft)
    assert before != after
