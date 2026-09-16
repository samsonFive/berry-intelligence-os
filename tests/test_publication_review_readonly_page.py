"""Publication Review read-only page (`GET /review-ops/publications`) --
a thin HTML view over the already-tested `publication_review_query` read
model. This route issues only read calls and renders no decision control
of any kind; these tests prove that directly rather than trusting the
route's own docstring."""

from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services import publication_review_domain as domain
from app.services.publication_review_repository import DraftState, DurableReviewRepository

client = TestClient(app)


def _page_body(html: str) -> str:
    """Isolate this route's own markup from the shared `base.html` chrome
    (nav, berry/feed-view context-switcher form) so decision-control
    checks aren't tripped up by controls this page did not introduce."""
    match = re.search(r'<div class="v2-page">.*?\n</div>', html, re.DOTALL)
    assert match, "expected the page's own <div class=\"v2-page\"> wrapper to be present"
    return match.group(0)


def _draft(draft_id: str, **overrides) -> dict:
    draft = {
        "id": draft_id, "title": f"Blueberry acreage grows in Peru ({draft_id})", "source_id": f"source-{draft_id}",
        "source_url": f"https://example.invalid/{draft_id}", "captured_date": "2026-09-16",
        "submitted_by": "media-orchestration", "summary": "A short summary.", "published_date": "2026-09-15",
        "article": {
            "word_count": 300, "paragraphs": [{"index": 0, "text": "the full acquired body text " * 60}],
            "content_sha256": "a" * 64,
        },
    }
    draft.update(overrides)
    return draft


def _seed(repository: DurableReviewRepository, draft_id: str, **overrides) -> DraftState:
    draft = _draft(draft_id, **overrides)
    eligibility = domain.check_eligibility(draft)
    state = DraftState(
        id=draft["id"], version=1, state=domain.PENDING_REVIEW, draft=draft,
        content_digest=domain.compute_review_content_digest(draft, eligibility=eligibility),
        provenance_digest=domain.compute_provenance_digest(draft), content_class=eligibility.content_class,
        acquisition_classification=eligibility.body_state, created_at="2026-09-16T00:00:00+00:00",
        updated_at="2026-09-16T00:00:00+00:00",
    )
    return repository.create_draft_state(state)


def test_page_renders_with_empty_durable_store(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BIOS_REVIEW_STATE_DIR", str(tmp_path / "review_state"))

    resp = client.get("/review-ops/publications")

    assert resp.status_code == 200
    assert "read-only" in resp.text.lower() or "read only" in resp.text.lower()
    assert "never invents backlog" in resp.text


def test_page_renders_queue_and_detail_for_a_seeded_draft(tmp_path: Path, monkeypatch) -> None:
    review_root = tmp_path / "review_state"
    monkeypatch.setenv("BIOS_REVIEW_STATE_DIR", str(review_root))
    repository = DurableReviewRepository(review_root)
    _seed(repository, "ev-media-a")

    resp = client.get("/review-ops/publications")

    assert resp.status_code == 200
    assert "Blueberry acreage grows in Peru (ev-media-a)" in resp.text
    assert "pending review" in resp.text.lower()


def test_page_never_renders_a_decision_control(tmp_path: Path, monkeypatch) -> None:
    review_root = tmp_path / "review_state"
    monkeypatch.setenv("BIOS_REVIEW_STATE_DIR", str(review_root))
    repository = DurableReviewRepository(review_root)
    _seed(repository, "ev-media-b")

    resp = client.get("/review-ops/publications?selected=ev-media-b")
    body = _page_body(resp.text)

    assert resp.status_code == 200
    assert "<form" not in body
    assert "<button" not in body
    for verb in ("approve_publication", "reject_publication", "defer_publication", "request_publication_correction"):
        assert f'action="{verb}' not in body
        assert f"/{verb}" not in body


def test_page_never_leaks_the_full_acquired_body(tmp_path: Path, monkeypatch) -> None:
    review_root = tmp_path / "review_state"
    monkeypatch.setenv("BIOS_REVIEW_STATE_DIR", str(review_root))
    repository = DurableReviewRepository(review_root)
    tail_marker = "END-OF-FULL-ACQUIRED-BODY-MARKER"
    _seed(repository, "ev-media-c", article={
        "word_count": 300,
        "paragraphs": [{"index": 0, "text": ("filler word " * 300) + tail_marker}],
        "content_sha256": "a" * 64,
    })

    resp = client.get("/review-ops/publications?selected=ev-media-c")

    assert resp.status_code == 200
    assert tail_marker not in resp.text


def test_page_get_never_mutates_the_durable_repository(tmp_path: Path, monkeypatch) -> None:
    review_root = tmp_path / "review_state"
    monkeypatch.setenv("BIOS_REVIEW_STATE_DIR", str(review_root))
    repository = DurableReviewRepository(review_root)
    _seed(repository, "ev-media-d")
    before = repository.get_draft_state("ev-media-d")

    client.get("/review-ops/publications?selected=ev-media-d")
    client.get("/review-ops/publications?state=pending_review")

    after = repository.get_draft_state("ev-media-d")
    assert after.version == before.version
    assert after.updated_at == before.updated_at


def test_page_filters_by_state(tmp_path: Path, monkeypatch) -> None:
    review_root = tmp_path / "review_state"
    monkeypatch.setenv("BIOS_REVIEW_STATE_DIR", str(review_root))
    repository = DurableReviewRepository(review_root)
    _seed(repository, "ev-media-e")

    resp = client.get("/review-ops/publications?state=rejected")

    assert resp.status_code == 200
    assert "Blueberry acreage grows in Peru (ev-media-e)" not in resp.text
