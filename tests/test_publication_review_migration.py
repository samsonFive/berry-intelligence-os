"""Publication Review Command Service V1 -- development inbox import adapter tests.

Every test passes an explicit, hand-built dict as `inbox_draft` -- never a
real path under `inbox/`, and never a directory scan. This proves the
adapter is a deliberate, single-item action, not a bulk/automatic import
path that could be mistaken for treating local inbox files as
authoritative shared state.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.services import publication_review_domain as domain
from app.services.publication_review_migration import import_inbox_draft
from app.services.publication_review_repository import DurableReviewRepository


def _inbox_shaped_draft(draft_id="ev-media-imported") -> dict:
    """Matches the real shape a gitignored inbox/evidence/<id>.json draft
    has -- built by hand here, never read from a real inbox path."""
    return {
        "id": draft_id, "record_type": "evidence", "status": "draft", "review_state": "in_review",
        "source_type": "discovered_media", "title": "Imported from a development inbox",
        "source_name": "Example Source", "source_url": "https://example.invalid/imported-item",
        "published_date": "2026-09-10", "captured_date": "2026-09-16",
        "summary": "A short summary.", "submitted_by": "media-orchestration",
        "article": {
            "word_count": 250, "paragraphs": [{"index": 0, "text": "word " * 250}], "content_sha256": "c" * 64,
        },
    }


def test_import_creates_a_pending_review_durable_draft(tmp_path):
    repo = DurableReviewRepository(tmp_path / "review_state")
    outcome = import_inbox_draft(repo, _inbox_shaped_draft())
    assert outcome.created is True
    assert outcome.provenance_drifted is False
    state = repo.get_draft_state("ev-media-imported")
    assert state is not None
    assert state.state == domain.PENDING_REVIEW
    assert state.version == 1
    assert state.content_class == "FULL_ARTICLE"


def test_import_is_a_single_explicit_item_never_a_directory_scan(tmp_path):
    """The function signature itself proves this: it takes one dict, not a
    directory path. This test additionally confirms importing one draft
    never creates or touches any other draft id."""
    repo = DurableReviewRepository(tmp_path / "review_state")
    import_inbox_draft(repo, _inbox_shaped_draft("ev-media-a"))
    assert repo.get_draft_state("ev-media-b") is None
    assert len(repo.list_draft_states()) == 1


def test_reimporting_an_unchanged_draft_does_not_create_a_second_version(tmp_path):
    repo = DurableReviewRepository(tmp_path / "review_state")
    draft = _inbox_shaped_draft()
    import_inbox_draft(repo, draft)
    outcome = import_inbox_draft(repo, draft)
    assert outcome.created is False
    assert outcome.provenance_drifted is False
    assert repo.get_draft_state(draft["id"]).version == 1


def test_reimporting_a_draft_with_drifted_provenance_is_reported_not_silently_applied(tmp_path):
    """If the same draft id is re-imported with different provenance
    (e.g. a corrected source_id upstream), the import adapter must never
    silently overwrite the durable, possibly-already-reviewed state -- it
    reports the drift for a deliberate revise/correction command instead."""
    repo = DurableReviewRepository(tmp_path / "review_state")
    draft = _inbox_shaped_draft()
    import_inbox_draft(repo, draft)

    drifted_draft = dict(draft)
    drifted_draft["source_id"] = "source-corrected"
    outcome = import_inbox_draft(repo, drifted_draft)
    assert outcome.created is False
    assert outcome.provenance_drifted is True
    # The durable draft itself is unchanged -- import never silently mutated it.
    stored = repo.get_draft_state(draft["id"])
    assert stored.version == 1
    assert stored.draft.get("source_id") != "source-corrected"


def test_import_computes_real_digests_matching_the_domain_module(tmp_path):
    repo = DurableReviewRepository(tmp_path / "review_state")
    draft = _inbox_shaped_draft()
    import_inbox_draft(repo, draft)
    state = repo.get_draft_state(draft["id"])
    eligibility = domain.check_eligibility(draft)
    assert state.content_digest == domain.compute_review_content_digest(draft, eligibility=eligibility)
    assert state.provenance_digest == domain.compute_provenance_digest(draft)


def test_import_accepts_an_explicit_clock_for_determinism(tmp_path):
    repo = DurableReviewRepository(tmp_path / "review_state")
    fixed = datetime(2026, 1, 1, tzinfo=UTC)
    import_inbox_draft(repo, _inbox_shaped_draft(), now=fixed)
    state = repo.get_draft_state("ev-media-imported")
    assert state.created_at.startswith("2026-01-01")
