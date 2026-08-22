"""General parent-artifact and atomic-Evidence architecture tests."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.main import app


PRIORITY = {
    dimension: {"level": "none", "rationale": ""}
    for dimension in ("reading", "testing", "commercial_position", "monitoring")
}


def _evidence(record_id: str, **overrides) -> dict:
    record = {
        "id": record_id,
        "record_type": "evidence",
        "status": "published",
        "source_type": "trade_press",
        "title": f"Fixture {record_id}",
        "captured_date": "2026-08-15",
        "summary": "Synthetic fixture only.",
        "submitted_by": "test",
        "priority": deepcopy(PRIORITY),
    }
    record.update(overrides)
    return record


def test_legacy_article_parent_and_multiple_atomic_points_validate(tmp_path: Path) -> None:
    repos = main.get_repositories(tmp_path, main.SCHEMAS_DIR)
    legacy = repos.evidence.create(_evidence("ev-legacy-article"))
    parent = repos.evidence.create(
        _evidence(
            "ev-parent-media",
            evidence_role="publication_artifact",
            media_format="podcast",
            source_id="source-fixture",
            transcript={"status": "available", "source": "publisher_provided", "url": "https://example.invalid/t"},
        )
    )
    child_a = repos.evidence.create(
        _evidence(
            "ev-atomic-a",
            evidence_role="atomic_evidence",
            parent_evidence_id=parent["id"],
            artifact_locator={"start_seconds": 61, "end_seconds": 78, "speaker_label": "Speaker A"},
            extraction_provenance={"method": "ai_assisted", "extracted_by": "fixture extractor", "extracted_at": "2026-08-15"},
            entity_ids=["company-fixture-a"],
            geography_ids=["geography-fixture-a"],
            review_state="published",
            reviewed_by="reviewer-a",
            reviewed_at="2026-08-15",
        )
    )
    child_b = repos.evidence.create(
        _evidence(
            "ev-atomic-b",
            status="in_review",
            evidence_role="atomic_evidence",
            parent_evidence_id=parent["id"],
            artifact_locator={"start_seconds": 305, "end_seconds": 332, "section": "Market discussion"},
            extraction_provenance={"method": "human", "extracted_by": "fixture analyst", "extracted_at": "2026-08-15"},
            entity_ids=["company-fixture-b"],
            geography_ids=["geography-fixture-b"],
            review_state="in_review",
        )
    )

    assert "evidence_role" not in legacy
    assert child_a["parent_evidence_id"] == child_b["parent_evidence_id"] == parent["id"]
    assert child_a["artifact_locator"] != child_b["artifact_locator"]
    assert child_a["entity_ids"] != child_b["entity_ids"]
    assert child_a["geography_ids"] != child_b["geography_ids"]
    assert child_a["review_state"] == "published"
    assert child_b["review_state"] == "in_review"


def test_atomic_evidence_requires_parent_locator_and_extraction_provenance(tmp_path: Path) -> None:
    from app.repositories.base import InvalidRecord

    repos = main.get_repositories(tmp_path, main.SCHEMAS_DIR)
    try:
        repos.evidence.create(_evidence("ev-incomplete-atomic", evidence_role="atomic_evidence"))
    except InvalidRecord as exc:
        message = str(exc)
    else:
        raise AssertionError("incomplete atomic Evidence unexpectedly validated")
    assert "parent_evidence_id" in message
    assert "artifact_locator" in message
    assert "extraction_provenance" in message


def test_independent_publish_and_reject_preserve_parent_and_lineage(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(main, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path / "inbox")
    repos = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    repos.sources.create({"id": "source-fixture", "name": "Fixture Publisher"})
    repos.evidence.create(
        _evidence(
            "ev-parent-media",
            evidence_role="publication_artifact",
            media_format="podcast",
            source_id="source-fixture",
        )
    )
    for entity in (
        {"id": "company-fixture", "record_type": "entity", "entity_type": "company", "name": "Fixture Company", "status": "active"},
        {"id": "geography-fixture", "record_type": "entity", "entity_type": "geography", "name": "Fixture Geography", "status": "active"},
    ):
        repos.entities.create(entity)

    base_draft = {
        "record_type": "evidence",
        "status": "draft",
        "intake_type": "article_or_url",
        "source_type": "industry_podcast",
        "source_name": "Fixture Publisher",
        "source_url": "https://example.invalid/episode",
        "captured_date": "2026-08-15",
        "summary": "Synthetic atomic proposal.",
        "why_it_matters": "",
        "submitted_by": "fixture extractor",
        "source_id": "source-fixture",
        "evidence_role": "atomic_evidence",
        "parent_evidence_id": "ev-parent-media",
        "extraction_provenance": {"method": "ai_assisted", "extracted_by": "fixture extractor", "extracted_at": "2026-08-15"},
        "suggested_competitors": [],
        "suggested_varieties": [],
        "attachments": [],
    }
    draft_a = {**base_draft, "id": "ev-proposal-a", "title": "Proposal A", "artifact_locator": {"start_seconds": 10, "end_seconds": 20}}
    draft_b = {**base_draft, "id": "ev-proposal-b", "title": "Proposal B", "artifact_locator": {"start_seconds": 40, "end_seconds": 55}}
    main.save_draft(draft_a)
    main.save_draft(draft_b)
    client = TestClient(app)

    approved = client.post(
        "/review/ev-proposal-a/publish",
        data={
            "title": "Edited proposal A",
            "source_type": "industry_podcast",
            "source_name": "Fixture Publisher",
            "source_url": "https://example.invalid/episode",
            "captured_date": "2026-08-15",
            "summary": "Human-edited synthetic fixture.",
            "companies": "Fixture Company",
            "geographies": "Fixture Geography",
            "berries": ["berry-blueberry"],
            "fact_statement_1": "Synthetic fact fixture.",
            "fact_classification_1": "fact",
            "fact_confidence_1": "medium",
            "reviewer": "reviewer-a",
        },
        follow_redirects=False,
    )
    rejected = client.post(
        "/review/ev-proposal-b/reject",
        data={"reviewer": "reviewer-b", "rejection_reason": "Unsupported synthetic fixture."},
        follow_redirects=False,
    )

    assert approved.status_code == rejected.status_code == 303
    parent = repos.evidence.get("ev-parent-media")
    child = repos.evidence.get("ev-proposal-a")
    rejected_draft = main.get_draft("ev-proposal-b")
    assert parent["status"] == "published"
    assert child["parent_evidence_id"] == parent["id"]
    assert child["review_state"] == "published"
    assert child["reviewed_by"] == "reviewer-a"
    assert rejected_draft["review_state"] == "rejected"
    assert rejected_draft["reviewed_by"] == "reviewer-b"
    assert repos.evidence.get("ev-proposal-b") is None
    assert "ev-proposal-b" in {draft["id"] for draft in main.list_drafts()}
    assert "ev-proposal-b" not in {draft["id"] for draft in main.list_pending_drafts()}

    fact = repos.facts.get("fact-proposal-a-1")
    assert fact["evidence_ids"] == [child["id"]]
    assessment = repos.assessments.create(
        {
            "id": "assessment-atomic-fixture",
            "record_type": "assessment",
            "title": "Synthetic assessment fixture",
            "rationale": "Fixture only.",
            "status": "active",
            "confidence": "medium",
            "fact_ids": [fact["id"]],
            "evidence_ids": [child["id"]],
            "reviewer": "reviewer-a",
            "created_at": "2026-08-15",
        }
    )
    lineage = main.get_query_services(main.DATA_DIR, main.SCHEMAS_DIR).lineage
    assert lineage.resolve_linked_facts(assessment["fact_ids"])[0]["id"] == fact["id"]
    assert lineage.resolve_linked_evidence(fact["evidence_ids"])[0]["id"] == child["id"]
    assert repos.sources.get(parent["source_id"])["name"] == "Fixture Publisher"


def test_fact_can_cite_multiple_atomic_evidence_records(tmp_path: Path) -> None:
    repos = main.get_repositories(tmp_path, main.SCHEMAS_DIR)
    fact = repos.facts.create(
        {
            "id": "fact-multi-atomic",
            "record_type": "fact",
            "statement": "Synthetic fixture.",
            "classification": "fact",
            "confidence": "medium",
            "status": "active",
            "reviewer": "fixture reviewer",
            "created_at": "2026-08-15",
            "evidence_ids": ["ev-atomic-a", "ev-atomic-b"],
        }
    )
    assert fact["evidence_ids"] == ["ev-atomic-a", "ev-atomic-b"]
