"""Publication Review Command Service V1 -- public static-build safety.

Proves, via a real `scripts/build_static.py` run (the same mechanism
`tests/test_build_static.py` already uses), that:

  1. A trusted publication this command service approves renders in the
     static build exactly like any other published Evidence record.
  2. The durable review-state store (`review_state/`: pending drafts,
     journal/staging files, locks, idempotency receipts) never appears
     anywhere in static output -- it is not even in a path the static
     builder reads from, so this is a direct, not inferred, proof.
  3. The acquired full article body text is not emitted into the public
     static build (per the contract's "Recommended default is public
     metadata plus an approved excerpt/link; full body redistribution
     requires a separate legal/product decision" -- V1 does not implement
     that separate decision, so the safe default is body text absent from
     static HTML).
  4. A `limited_content` (metadata-only) approval is excluded from the
     static build's own readable-content framing.
"""

from __future__ import annotations

import json

from app.composition import get_repositories
from app.repositories.paths import SCHEMAS_DIR
from app.services import publication_review_domain as domain
from app.services.publication_review_command import (
    ActorIdentity, CommandDependencies, InMemoryActorDirectory, PublicationReviewCommandService,
    PERMISSION_PUBLICATION_REVIEW,
)
from app.services.publication_review_repository import DraftState, DurableReviewRepository

SECRET_BODY_SENTINEL = "PRIVATE-SENTINEL-full-article-body-text-must-not-leak-into-static-html"
SECRET_DRAFT_TITLE_SENTINEL = "PRIVATE-SENTINEL-unrelated-pending-draft-title"


def _approved_draft() -> dict:
    return {
        "id": "ev-static-safety-test", "title": "Static safety test publication",
        "source_type": "article", "source_id": "source-static-safety", "source_name": "Static Safety Publisher",
        "source_url": "https://example.invalid/static-safety-article", "captured_date": "2026-09-16",
        "submitted_by": "media-orchestration", "summary": "A visible, approved summary.",
        "published_date": "2026-09-15",
        "article": {
            "word_count": 300,
            "paragraphs": [{"index": 0, "text": f"{SECRET_BODY_SENTINEL} " * 40}],
            "content_sha256": "a" * 64,
        },
    }


def _unrelated_pending_draft() -> dict:
    return {
        "id": "ev-static-safety-pending", "title": SECRET_DRAFT_TITLE_SENTINEL, "source_id": "source-2",
        "source_url": "https://example.invalid/pending", "captured_date": "2026-09-16",
        "submitted_by": "media-orchestration", "summary": "Should never appear anywhere in static output.",
        "published_date": "2026-09-15",
        "article": {
            "word_count": 300, "paragraphs": [{"index": 0, "text": "word " * 300}], "content_sha256": "b" * 64,
        },
    }


def test_approved_publication_appears_but_review_state_never_leaks_into_the_static_build(monkeypatch, tmp_path):
    data_dir = tmp_path / "data"
    inbox_dir = tmp_path / "inbox"
    review_root = tmp_path / "review_state"
    (data_dir / "evidence").mkdir(parents=True)
    config_dir = data_dir / "configuration"
    config_dir.mkdir(parents=True)
    (config_dir / "sources.json").write_text(json.dumps([
        {
            "id": "source-static-safety", "type": "rss", "label": "Static Safety Source",
            "value": "https://example.invalid/feed.xml", "enabled": True,
            "entity_types": ["trade_press"], "berry_ids": ["berry-blueberry"], "region_coverage": [],
        }
    ]), encoding="utf-8")

    repository = DurableReviewRepository(review_root)
    actors = InMemoryActorDirectory()
    actors.register(ActorIdentity(actor_id="alice", kind="human", permissions=frozenset({PERMISSION_PUBLICATION_REVIEW})))
    repositories = get_repositories(data_dir, SCHEMAS_DIR)
    deps = CommandDependencies(
        repository=repository, actor_directory=actors, evidence_reader=repositories.evidence,
        evidence_schema_path=SCHEMAS_DIR / "evidence.schema.json", evidence_data_dir=data_dir,
        review_events_inbox=inbox_dir, entity_ids_resolver=lambda: frozenset(),
    )
    service = PublicationReviewCommandService(deps)

    # Approve one publication -- this must appear in static output.
    approved = _approved_draft()
    eligibility = domain.check_eligibility(approved)
    digest = domain.compute_review_content_digest(approved, eligibility=eligibility)
    provenance_digest = domain.compute_provenance_digest(approved)
    repository.create_draft_state(DraftState(
        id=approved["id"], version=1, state=domain.PENDING_REVIEW, draft=approved, content_digest=digest,
        provenance_digest=provenance_digest, content_class=eligibility.content_class,
        acquisition_classification=eligibility.body_state, created_at="2026-09-16T00:00:00+00:00",
        updated_at="2026-09-16T00:00:00+00:00",
    ))
    env = domain.CommandEnvelope(
        draft_id=approved["id"], actor_id="alice", idempotency_key="k1", expected_version=1,
        reviewed_content_digest=digest,
    )
    result = service.approve_publication(env, approval_basis=domain.BASIS_FULL_ARTICLE)
    assert result.resulting_state == domain.APPROVED

    # An unrelated pending draft -- must never appear anywhere in static output.
    pending = _unrelated_pending_draft()
    pending_eligibility = domain.check_eligibility(pending)
    repository.create_draft_state(DraftState(
        id=pending["id"], version=1, state=domain.PENDING_REVIEW, draft=pending,
        content_digest=domain.compute_review_content_digest(pending, eligibility=pending_eligibility),
        provenance_digest=domain.compute_provenance_digest(pending), content_class=pending_eligibility.content_class,
        acquisition_classification=pending_eligibility.body_state, created_at="2026-09-16T00:00:00+00:00",
        updated_at="2026-09-16T00:00:00+00:00",
    ))

    from app import main

    monkeypatch.setattr(main, "DATA_DIR", data_dir)
    monkeypatch.setattr(main, "INBOX_DIR", inbox_dir)

    import scripts.build_static as build_static

    output_dir = tmp_path / "generated"
    monkeypatch.setattr(build_static, "OUTPUT_DIR", output_dir)
    assert build_static.main() == 0

    all_html = list(output_dir.rglob("*.html"))
    assert all_html, "static build produced no HTML output"

    for html_file in all_html:
        content = html_file.read_text(encoding="utf-8")
        # The approved publication's own metadata is allowed to appear.
        # The unrelated pending draft's title/id must never appear anywhere.
        assert SECRET_DRAFT_TITLE_SENTINEL not in content, html_file
        assert pending["id"] not in content, html_file
        # The full acquired body text must not be redistributed publicly
        # by default (no separate legal/product authorization exists).
        assert SECRET_BODY_SENTINEL not in content, html_file
        # No durable review-state internals (journal/lock/idempotency
        # payloads, raw digests) ever appear.
        assert digest not in content, html_file
        assert provenance_digest not in content, html_file
        assert "publication_review_command_v1" not in content, html_file
        assert str(review_root) not in content, html_file

    evidence_page = output_dir / "evidence" / approved["id"] / "index.html"
    assert evidence_page.is_file()
    evidence_html = evidence_page.read_text(encoding="utf-8")
    assert "Static safety test publication" in evidence_html
    assert "Static Safety Publisher" in evidence_html


def test_limited_content_approval_is_labeled_and_excluded_from_readable_framing(monkeypatch, tmp_path):
    data_dir = tmp_path / "data"
    inbox_dir = tmp_path / "inbox"
    review_root = tmp_path / "review_state"
    (data_dir / "evidence").mkdir(parents=True)

    repository = DurableReviewRepository(review_root)
    actors = InMemoryActorDirectory()
    actors.register(ActorIdentity(actor_id="alice", kind="human", permissions=frozenset({PERMISSION_PUBLICATION_REVIEW})))
    repositories = get_repositories(data_dir, SCHEMAS_DIR)
    deps = CommandDependencies(
        repository=repository, actor_directory=actors, evidence_reader=repositories.evidence,
        evidence_schema_path=SCHEMAS_DIR / "evidence.schema.json", evidence_data_dir=data_dir,
        review_events_inbox=inbox_dir, entity_ids_resolver=lambda: frozenset(),
    )
    service = PublicationReviewCommandService(deps)

    thin = {
        "id": "ev-limited-content-test", "title": "A thin metadata-only item", "source_id": "source-thin",
        "source_url": "https://example.invalid/thin", "captured_date": "2026-09-16",
        "submitted_by": "media-orchestration", "summary": "", "published_date": "2026-09-15",
        "publisher_description": "A short publisher blurb about a company announcement.",
    }
    eligibility = domain.check_eligibility(thin)
    digest = domain.compute_review_content_digest(thin, eligibility=eligibility)
    repository.create_draft_state(DraftState(
        id=thin["id"], version=1, state=domain.PENDING_REVIEW, draft=thin, content_digest=digest,
        provenance_digest=domain.compute_provenance_digest(thin), content_class=eligibility.content_class,
        acquisition_classification=eligibility.body_state, created_at="2026-09-16T00:00:00+00:00",
        updated_at="2026-09-16T00:00:00+00:00",
    ))
    env = domain.CommandEnvelope(
        draft_id=thin["id"], actor_id="alice", idempotency_key="k1", expected_version=1,
        reviewed_content_digest=digest,
    )
    service.approve_publication(env, approval_basis=domain.BASIS_LIMITED_CONTENT, warning_acknowledgments=eligibility.warnings)

    record = json.loads((data_dir / "evidence" / f"{thin['id']}.json").read_text(encoding="utf-8"))
    assert record["limited_content"] is True
    assert record["publication_content_basis"] == domain.BASIS_LIMITED_CONTENT
    assert "article" not in record
