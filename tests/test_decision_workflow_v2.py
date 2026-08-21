"""Pending Review, Reading Queue, and Assessment V2 decision-workspace contracts."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.main import app
from app.services.analyst_queue import load_state, pending_workflow_state


PRIORITY = {
    dimension: {"level": "none", "rationale": ""}
    for dimension in ("reading", "testing", "commercial_position", "monitoring")
}


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _isolate(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path / "inbox")
    monkeypatch.setattr(main, "DATA_DIR", tmp_path / "data")
    (tmp_path / "inbox" / "evidence").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "configuration").mkdir(parents=True, exist_ok=True)
    _write(tmp_path / "data" / "configuration" / "sources.json", [])
    main._NAV_WORK_CACHE["key"] = None
    main._NAV_WORK_CACHE["value"] = None


def _draft(record_id: str, **overrides) -> dict:
    record = {
        "id": record_id,
        "record_type": "evidence",
        "evidence_role": "publication_artifact",
        "status": "pending",
        "review_state": "pending_review",
        "source_type": "patent_record",
        "source_name": "USPTO",
        "source_url": "https://example.invalid/" + record_id,
        "title": f"Pending {record_id}",
        "published_date": date.today().isoformat(),
        "captured_date": date.today().isoformat(),
        "summary": "Untrusted pending article.",
        "berry_ids": ["berry-blueberry"],
        "entity_ids": [],
        "relevance_tier": "direct",
        "media_format": "web_article",
        "priority": deepcopy(PRIORITY),
    }
    record.update(overrides)
    return record


def _published(record_id: str, **overrides) -> dict:
    record = {
        "id": record_id,
        "record_type": "evidence",
        "status": "published",
        "review_state": "published",
        "source_type": "news_search",
        "source_name": "FreshPlaza",
        "source_url": "https://example.invalid/" + record_id,
        "title": f"Trusted {record_id}",
        "published_date": "2026-08-10",
        "captured_date": "2026-08-10",
        "summary": "Trusted published article fixture.",
        "why_it_matters": "Analyst-facing rationale.",
        "submitted_by": "reviewer",
        "reviewed_by": "reviewer",
        "reviewed_at": "2026-08-10",
        "priority": deepcopy(PRIORITY),
        "berry_ids": ["berry-blueberry"],
        "entity_ids": [],
        "tags": ["tier-1"],
    }
    record.update(overrides)
    return record


def test_pending_v2_is_decision_workspace_not_feed_clone(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    _write(tmp_path / "inbox" / "evidence" / "draft-now.json", _draft("draft-now", title="Direct blueberry patent draft"))
    client = TestClient(app)
    page = client.get("/pending")
    assert page.status_code == 200
    html = page.text
    assert "Pending review" in html
    assert "This is not Live Intelligence" in html
    assert "Bulk dismiss never publishes" in html
    assert "Review now" in html
    assert "Review soon" in html
    assert "Adjacent" in html
    assert "Likely ignore" in html
    assert "Older backlog" in html
    assert "v2-decision-row" in html
    assert "v2-decision-bar" in html
    assert "data-open-reader" in html
    assert 'id="v2ReaderOffcanvas"' in html
    assert "Direct blueberry patent draft" in html
    assert "v2-feed-grid" not in html
    assert "Bulk publish" not in html.casefold()
    nav = client.get("/brief")
    assert 'href="/pending"' in nav.text


def test_pending_bulk_dismiss_never_publishes(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    draft = _draft("draft-ignore", title="Tomato greenhouse construction", berry_ids=[], relevance_tier=None)
    _write(tmp_path / "inbox" / "evidence" / "draft-ignore.json", draft)
    client = TestClient(app)
    page = client.get("/pending")
    assert "Tomato greenhouse" in page.text
    response = client.post(
        "/queues/pending/bulk-dismiss",
        data={"item_id": "draft-ignore", "reviewer": "analyst", "return_to": "/pending"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/pending"
    stored = json.loads((tmp_path / "inbox" / "evidence" / "draft-ignore.json").read_text(encoding="utf-8"))
    assert stored["status"] == "pending"
    assert stored.get("review_state") != "published"
    assert pending_workflow_state("draft-ignore", load_state(main.INBOX_DIR)) == "dismissed"
    after = client.get("/pending")
    assert "Tomato greenhouse" not in after.text


def test_reading_v2_uses_cards_and_keeps_independent_state(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    repos = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    priority = deepcopy(PRIORITY)
    priority["reading"] = {"level": "high", "rationale": "Need to finish this brief."}
    repos.evidence.create(_published("ev-read-v2", title="Reading V2 fixture", priority=priority))
    client = TestClient(app)
    page = client.get("/queues/reading")
    assert page.status_code == 200
    assert "v2-reading-list" in page.text
    assert "data-open-reader" in page.text
    assert "Reading V2 fixture" in page.text
    assert "Mark read" in page.text
    assert "Keep" in page.text
    marked = client.post(
        "/queues/reading/ev-read-v2",
        data={"action": "mark_read", "reviewer": "analyst-fixture"},
        follow_redirects=False,
    )
    assert marked.status_code == 303
    after = client.get("/queues/reading")
    assert "Reading V2 fixture" not in after.text
    assert repos.evidence.get("ev-read-v2")["status"] == "published"
    completed = client.get("/queues/reading?show_completed=1")
    assert "Reading V2 fixture" in completed.text


def test_assessment_authoring_form_still_requires_facts() -> None:
    client = TestClient(app)
    form = client.get("/assessments/new")
    assert form.status_code == 200
    assert "Supporting fact ids" in form.text
    assert 'name="market_ids"' not in form.text
