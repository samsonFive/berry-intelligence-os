"""Review Operations Console: three-queue cockpit without trust actions."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.queries.pending_review import JsonPendingDraftSnapshotProvider, PendingReviewQueryService
from app.services.review_events import append_review_event
from app.services.review_operations import build_review_operations

PRIORITY = {
    dimension: {"level": "none", "rationale": ""}
    for dimension in ("reading", "testing", "commercial_position", "monitoring")
}
ENTITIES = {
    "company-planasa": {
        "id": "company-planasa",
        "entity_type": "company",
        "name": "Planasa",
    }
}
SOURCES = {
    "source-planasa": {
        "id": "source-planasa",
        "label": "Planasa Newsroom",
        "linked_competitor_ids": ["company-planasa"],
    }
}


def _pub(index: int, **overrides) -> dict:
    record = {
        "id": f"pending-{index:04d}",
        "record_type": "evidence",
        "evidence_role": "publication_artifact",
        "status": "pending",
        "source_id": "source-planasa",
        "source_name": "Planasa Newsroom",
        "source_type": "company_website",
        "title": f"Planasa blueberry production update {index}",
        "published_date": "2026-08-20",
        "captured_date": "2026-08-20",
        "summary": "Untrusted pending summary.",
        "berry_ids": ["berry-blueberry"],
        "entity_ids": [],
        "relevance_tier": "direct",
        "media_format": "web_article",
        "priority": deepcopy(PRIORITY),
        "article": {"paragraphs": [{"text": "Blue Maldiva appears in the full private article body."}]},
    }
    record.update(overrides)
    return record


def _write(folder: Path, record: dict) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{record['id']}.json").write_text(json.dumps(record), encoding="utf-8")


def _artifact(evidence_id: str, status: str = "pending") -> dict:
    return {
        "source_fidelity_artifact_schema_version": 1,
        "evidence_id": evidence_id,
        "match_class": "EXACT_IDENTITY_MATCH",
        "identity_proof": ["EXACT_IDENTITY_MATCH"],
        "review": {"status": status},
        "reacquired_at": "2026-08-10T00:00:00+00:00",
        "source_name": "Planasa Newsroom",
    }


def _atomic(index: int, parent: str, **overrides) -> dict:
    record = {
        "id": f"atomic-{index:04d}",
        "record_type": "evidence",
        "evidence_role": "atomic_evidence",
        "status": "draft",
        "parent_evidence_id": parent,
        "captured_date": "2026-08-01",
        "summary": "Proposed statement",
        "transcript_excerpt": "SECRET ATOMIC EXCERPT SHOULD NOT RENDER",
        "berry_ids": ["berry-blueberry"],
        "priority": deepcopy(PRIORITY),
    }
    record.update(overrides)
    return record


def test_three_queue_counts_age_and_next_links(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    _write(inbox / "evidence", _pub(0, captured_date="2026-07-01"))
    trusted = {
        "id": "ev-trusted",
        "status": "published",
        "title": "Trusted",
        "berry_ids": ["berry-raspberry"],
        "entity_ids": ["company-planasa"],
        "source_id": "source-planasa",
        "source_name": "Planasa Newsroom",
    }
    ops = build_review_operations(
        inbox_dir=inbox,
        pending_service=PendingReviewQueryService(JsonPendingDraftSnapshotProvider(inbox)),
        entities=ENTITIES,
        sources=SOURCES,
        published=[trusted],
        atomic_drafts=[_atomic(0, "ev-parent-a"), _atomic(1, "ev-parent-a")],
        fidelity_artifacts=[_artifact("ev-trusted")],
        review_events=[],
        extraction_gate={"enabled": False, "runnable": False},
        today=date(2026, 8, 24),
    )
    assert ops["publication"]["pending"] == 1
    assert ops["publication"]["oldest"]["age_days"] >= 30
    assert ops["publication"]["next_href"].startswith("/review/")
    encoded = json.dumps(ops)
    assert "full private article body" not in encoded
    assert "SECRET ATOMIC EXCERPT" not in encoded
    assert ops["source_fidelity"]["pending"] == 1
    assert ops["source_fidelity"]["next_href"] == "/source-fidelity/ev-trusted"
    assert "EXACT SOURCE MATCH" in ops["source_fidelity"]["reasons"] or "Raspberry undercoverage" in ops["source_fidelity"]["reasons"]
    assert ops["atomic"]["pending"] == 2
    assert ops["atomic"]["batches"] == 1
    assert "SOURCE BATCH WITH 2 PROPOSALS" in ops["atomic"]["reasons"]
    assert ops["atomic"]["next_href"] == "/review?kind=atomic&parent=ev-parent-a"
    assert ops["atomic"]["extraction_disabled"] is True
    assert any(row["code"] == "ATOMIC_EXTRACTION_DISABLED" for row in ops["blocked"])
    labels = {row["label"] for row in ops["publication"]["age_buckets"]}
    assert labels == {"Today", "1–3 days", "4–7 days", "8–30 days", "30+ days"}


def test_review_events_and_empty_fidelity(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    append_review_event(
        inbox,
        workflow="publication_review",
        object_id="pending-0000",
        object_type="publication_draft",
        action="publish",
        prior_state="pending",
        new_state="published",
        actor="johnny",
    )
    append_review_event(
        inbox,
        workflow="source_fidelity_review",
        object_id="ev-trusted",
        object_type="source_fidelity_artifact",
        action="rejected",
        prior_state="pending",
        new_state="rejected",
        actor="johnny",
    )
    append_review_event(
        inbox,
        workflow="atomic_evidence_review",
        object_id="atomic-0000",
        object_type="atomic_evidence_draft",
        action="approve",
        prior_state="draft",
        new_state="published",
        actor="johnny",
    )
    ops = build_review_operations(
        inbox_dir=inbox,
        pending_service=PendingReviewQueryService(JsonPendingDraftSnapshotProvider(inbox)),
        entities=ENTITIES,
        sources=SOURCES,
        published=[],
        atomic_drafts=[],
        fidelity_artifacts=[],
        extraction_gate={"enabled": False, "runnable": False},
        today=date(2026, 8, 24),
    )
    labels = [row["label"] for row in ops["activity"]]
    assert "Published" in labels
    assert "Source artifact rejected" in labels
    assert "Atomic approved" in labels
    assert ops["source_fidelity"]["pending"] == 0
    assert any(row["code"] == "SOURCE_FIDELITY_EMPTY" for row in ops["blocked"])
    assert "johnny" not in json.dumps(ops["activity"])


def test_review_ops_route_has_no_trust_actions(monkeypatch, tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    data = tmp_path / "data"
    _write(inbox / "evidence", _pub(0))
    monkeypatch.setattr(main, "INBOX_DIR", inbox)
    monkeypatch.setattr(main, "DATA_DIR", data)
    monkeypatch.setattr(main, "entity_index", lambda: ENTITIES)
    monkeypatch.setattr(main, "load_sources", lambda: list(SOURCES.values()))
    monkeypatch.setattr(main, "published_evidence", lambda: [])
    monkeypatch.setattr(main, "list_drafts", lambda: [])
    page = TestClient(main.app).get("/review-ops")
    assert page.status_code == 200
    assert "PUBLICATION REVIEW" in page.text
    assert "SOURCE FIDELITY REVIEW" in page.text
    assert "ATOMIC EVIDENCE REVIEW" in page.text
    assert "Review next publication" in page.text
    assert "Review next source fidelity item" in page.text
    assert "Review next atomic batch" in page.text
    assert 'name="decision"' not in page.text
    assert "confirm_affirm" not in page.text
    assert 'action="/review/' not in page.text
    assert 'action="/source-fidelity/' not in page.text
    assert "review-ops-grid" in page.text
    css = (Path(main.BASE_DIR) / "app" / "static" / "app.css").read_text(encoding="utf-8")
    assert ".review-ops-grid" in css
    assert "@media(max-width:834px)" in css
