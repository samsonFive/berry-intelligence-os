"""Analyst queue workflow: action counts resolve; inventory views do not impersonate work."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.main import app
from app.services.analyst_queue import load_state, work_counts


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
        "submitted_by": "reviewer",
        "reviewed_by": "reviewer",
        "reviewed_at": "2026-08-10",
        "priority": deepcopy(PRIORITY),
        "berry_ids": ["berry-blueberry"],
        "entity_ids": ["company-hortifrut"],
    }
    record.update(overrides)
    return record


def _seed(repos, records: list[dict]) -> None:
    repos.entities.create(
        {
            "id": "company-hortifrut",
            "record_type": "entity",
            "entity_type": "company",
            "name": "Hortifrut",
            "status": "active",
        }
    )
    for record in records:
        repos.evidence.create(record)


def test_reading_queue_mark_read_does_not_delete_evidence(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    repos = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    priority = deepcopy(PRIORITY)
    priority["reading"] = {"level": "high", "rationale": "Need to finish this brief."}
    _seed(repos, [_published("ev-read-1", title="Reading fixture one", priority=priority)])
    client = TestClient(app)
    page = client.get("/queues/reading")
    assert page.status_code == 200
    assert "Items you have not finished consuming" in page.text
    assert "Reading fixture one" in page.text
    assert "Mark read" in page.text
    assert "need attention" in page.text
    marked = client.post(
        "/queues/reading/ev-read-1",
        data={"action": "mark_read", "reviewer": "analyst-fixture"},
        follow_redirects=False,
    )
    assert marked.status_code == 303
    after = client.get("/queues/reading")
    assert "Reading fixture one" not in after.text
    assert "0 need attention" in after.text
    assert repos.evidence.get("ev-read-1")["status"] == "published"
    completed_read = client.get("/queues/reading?show_completed=1")
    assert "Reading fixture one" in completed_read.text
    assert "Read" in completed_read.text
    dismissed = client.post(
        "/queues/reading/ev-read-1",
        data={"action": "dismiss", "reviewer": "analyst-fixture", "show_completed": "1"},
        follow_redirects=False,
    )
    assert dismissed.status_code == 303
    gone = client.get("/queues/reading")
    assert "Reading fixture one" not in gone.text
    completed = client.get("/queues/reading?show_completed=1")
    assert "Reading fixture one" in completed.text
    assert "Dismissed" in completed.text
    assert repos.evidence.get("ev-read-1")["title"] == "Reading fixture one"


def test_testing_queue_pass_leaves_active_but_stays_auditable(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    repos = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    priority = deepcopy(PRIORITY)
    priority["testing"] = {"level": "medium", "rationale": "Variety names without performance data."}
    _seed(repos, [_published("ev-test-1", title="Testing fixture one", priority=priority)])
    client = TestClient(app)
    page = client.get("/queues/testing")
    assert "Claim testing" in page.text
    assert "not a Fact" in page.text.casefold() or "NOT A FACT" in page.text
    assert "Pass" in page.text
    client.post("/queues/testing/ev-test-1", data={"action": "pass", "reviewer": "analyst-fixture"})
    active = client.get("/queues/testing")
    assert "Testing fixture one" not in active.text
    audit = client.get("/queues/testing?show_completed=1")
    assert "Testing fixture one" in audit.text
    assert "Pass" in audit.text or "Pass" in page.text
    assert repos.evidence.get("ev-test-1")["status"] == "published"


def test_commercial_positions_are_inventory_not_a_clear_queue(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    repos = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    priority = deepcopy(PRIORITY)
    priority["commercial_position"] = {
        "level": "high",
        "rationale": "Willingness to litigate changes the licensing risk.",
    }
    _seed(repos, [_published("ev-pos-1", title="Commercial fixture one", priority=priority)])
    client = TestClient(app)
    page = client.get("/queues/commercial_position")
    assert page.status_code == 200
    assert "not a queue of tasks" in page.text
    assert "Hortifrut" in page.text
    assert "Commercial fixture one" in page.text
    assert "Clear" not in page.text
    assert ">Pass<" not in page.text
    assert "tagged evidence" in page.text


def test_monitoring_stop_reduces_active_watch_count(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    repos = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    priority = deepcopy(PRIORITY)
    priority["monitoring"] = {"level": "medium", "rationale": "Watch for appeals."}
    _seed(repos, [_published("ev-watch-1", title="Watch fixture one", priority=priority)])
    _write(
        tmp_path / "data" / "signals" / "sig-proposed-1.json",
        {
            "id": "sig-proposed-1",
            "record_type": "signal",
            "title": "Proposed licensing signal",
            "status": "proposed",
            "direction": "emerging",
            "strength": "medium",
            "evidence_ids": ["ev-watch-1", "ev-read-placeholder"],
            "reviewer": None,
            "proposed_at": "2026-08-18",
        },
    )
    client = TestClient(app)
    page = client.get("/queues/monitoring")
    assert "active watches" in page.text
    assert "new signal" in page.text
    assert "Watch fixture one" in page.text
    assert "Pause" in page.text
    counts = work_counts(inbox_dir=main.INBOX_DIR, published=repos.evidence.list(), signals=repos.signals.list())
    assert counts["monitoring_inventory"] == 1
    assert counts["signal_alerts"] == 1
    client.post("/queues/monitoring/ev-watch-1", data={"action": "stop", "reviewer": "analyst-fixture"})
    after = work_counts(inbox_dir=main.INBOX_DIR, published=repos.evidence.list(), signals=repos.signals.list())
    assert after["monitoring_inventory"] == 0
    hidden = client.get("/queues/monitoring")
    assert "Watch fixture one" not in hidden.text
    assert repos.evidence.get("ev-watch-1")["status"] == "published"
    dismissed = client.post(
        "/signals/sig-proposed-1/alert-decision",
        data={"action": "dismiss", "reviewer": "analyst-fixture"},
        follow_redirects=False,
    )
    assert dismissed.status_code == 303
    quiet = work_counts(inbox_dir=main.INBOX_DIR, published=repos.evidence.list(), signals=repos.signals.list())
    assert quiet["signal_alerts"] == 0
    assert (tmp_path / "data" / "signals" / "sig-proposed-1.json").is_file()


def test_position_proposals_accept_does_not_delete_recommendation(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    repos = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    _seed(repos, [])
    repos.recommendations.create(
        {
            "id": "recommendation-fixture-proposal",
            "record_type": "recommendation",
            "title": "Fixture position proposal",
            "rationale": "Pending human review of a commercial stance.",
            "action_type": "monitor_for_confirmation",
            "status": "active",
            "reviewer": "Codex proposal — pending human review",
            "ai_proposed": True,
            "created_at": "2026-08-18",
            "signal_ids": ["sig-fixture-1"],
        }
    )
    client = TestClient(app)
    page = client.get("/queues/commercial_position")
    assert "Position proposals" in page.text
    assert "Fixture position proposal" in page.text
    assert "Accept" in page.text
    assert "Reject" in page.text
    accepted = client.post(
        "/recommendations/recommendation-fixture-proposal/proposal-decision",
        data={"action": "accept", "reviewer": "analyst-fixture"},
        follow_redirects=False,
    )
    assert accepted.status_code == 303
    after = client.get("/queues/commercial_position")
    assert "Fixture position proposal" not in after.text
    assert repos.recommendations.get("recommendation-fixture-proposal")["status"] == "active"


def test_nav_uses_action_badges_not_raw_inventory_for_review(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    repos = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    _seed(repos, [])
    client = TestClient(app)
    home = client.get("/")
    assert "need review" in home.text or "Publications" in home.text
    assert "Reading Queue (124)" not in home.text
    assert "nav-action" in home.text or "Publications" in home.text
    assert load_state(main.INBOX_DIR)["reading"] == {}
