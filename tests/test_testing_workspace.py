"""Claim Testing V2 workspace: tagged Evidence, not Facts or Learner Mode."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.main import app
from app.services.global_search import search_global
from app.services.intelligence_feed import annotate_feed_semantics
from app.services.media_discovery import list_discovered_items
from app.services.morning_brief import build_morning_brief
from app.services.testing_workspace import testing_page_model as build_testing_page
from app.services.variety_footprint import variety_footprint


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
    (tmp_path / "inbox").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "evidence").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "facts").mkdir(parents=True, exist_ok=True)


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
        "summary": "Exact source wording for the fixture claim.",
        "why_it_matters": "Stored rationale, not generated importance.",
        "submitted_by": "reviewer",
        "reviewed_by": "reviewer",
        "reviewed_at": "2026-08-10",
        "priority": deepcopy(PRIORITY),
        "berry_ids": ["berry-blueberry"],
        "entity_ids": ["company-hortifrut", "variety-example-blue", "geography-chile"],
        "evidence_links": [],
        "fact_ids": [],
        "does_not_prove": ["Does not prove a universal trait."],
    }
    record.update(overrides)
    return record


def _seed(repos, records: list[dict]) -> None:
    for payload in (
        {"id": "company-hortifrut", "record_type": "entity", "entity_type": "company", "name": "Hortifrut", "status": "active"},
        {"id": "variety-example-blue", "record_type": "entity", "entity_type": "variety", "name": "Example Blue", "status": "active"},
        {"id": "geography-chile", "record_type": "entity", "entity_type": "geography", "name": "Chile", "status": "active"},
    ):
        repos.entities.create(payload)
    for record in records:
        repos.evidence.create(record)


def test_testing_queue_v2_card_and_detail_preserve_trust(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    repos = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    priority = deepcopy(PRIORITY)
    priority["testing"] = {"level": "high", "rationale": "Florida trial yield claim needs local confirmation."}
    support = _published(
        "ev-support-1",
        title="Independent trial notes lower yield",
        priority=deepcopy(PRIORITY),
    )
    claim = _published(
        "ev-claim-1",
        title="Primocane cultivar X produces better yields under condition Y",
        priority=priority,
        evidence_links=[
            {
                "predicate": "corroborates",
                "target_evidence_id": "ev-support-1",
                "status": "accepted",
                "notes": "Same trial family",
                "proposed_by": "analyst",
                "proposed_at": "2026-08-10",
            }
        ],
    )
    _seed(repos, [support, claim])
    client = TestClient(app)
    page = client.get("/queues/testing")
    assert page.status_code == 200
    html = page.text
    assert "v2-claim-card" in html
    assert "Source claim" in html
    assert "Primocane cultivar X" in html
    assert "Hortifrut" in html
    assert "Example Blue" in html
    assert "Chile" in html
    assert "Supports 1" in html
    assert "not a Fact" in html
    assert "Learner Mode" in html
    assert "data-open-reader" in html
    assert "queue-table" not in html
    detail = client.get("/queues/testing/ev-claim-1")
    assert detail.status_code == 200
    body = detail.text
    assert "Exact wording" in body
    assert "Exact source wording" in body
    assert "Supporting evidence" in body
    assert "Contradicting evidence" in body
    assert "Independent trial notes lower yield" in body
    assert "/entities/company/company-hortifrut" in body
    assert "/entities/variety/variety-example-blue" in body
    assert "/entities/geography/geography-chile" in body
    assert "Does not prove a universal trait" in body
    assert "never writes a Fact" in body
    assert "does not author a Fact" in body
    passed = client.post(
        "/queues/testing/ev-claim-1",
        data={"action": "pass", "reviewer": "analyst-fixture", "return_to": "/queues/testing/ev-claim-1"},
        follow_redirects=False,
    )
    assert passed.status_code == 303
    assert repos.evidence.get("ev-claim-1")["status"] == "published"
    after = client.get("/queues/testing")
    assert "Primocane cultivar X" not in after.text
    audit = client.get("/queues/testing?show_completed=1")
    assert "Primocane cultivar X" in audit.text
    assert "Pass" in audit.text


def test_testing_queue_does_not_run_forbidden_work(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    repos = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    priority = deepcopy(PRIORITY)
    priority["testing"] = {"level": "medium", "rationale": "Check the claim."}
    _seed(repos, [_published("ev-claim-2", priority=priority)])
    calls: list[str] = []

    def wrap(name, original):
        def inner(*args, **kwargs):
            calls.append(name)
            return original(*args, **kwargs)

        return inner

    monkeypatch.setattr(main, "build_morning_brief", wrap("brief", build_morning_brief))
    monkeypatch.setattr("app.services.media_discovery.list_discovered_items", wrap("discover", list_discovered_items))
    monkeypatch.setattr("app.services.variety_footprint.variety_footprint", wrap("footprint", variety_footprint))
    monkeypatch.setattr("app.services.intelligence_feed.annotate_feed_semantics", wrap("story", annotate_feed_semantics))
    monkeypatch.setattr("app.services.global_search.search_global", wrap("search", search_global))
    page = TestClient(app).get("/queues/testing")
    assert page.status_code == 200
    assert calls == []


def test_static_testing_page_hides_disposition(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    repos = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    priority = deepcopy(PRIORITY)
    priority["testing"] = {"level": "high", "rationale": "Need a test."}
    _seed(repos, [_published("ev-claim-static", title="Yield claim fixture", priority=priority)])
    _write(
        tmp_path / "inbox" / "analyst_queue_state.json",
        {
            "testing": {
                "ev-claim-static": {
                    "state": "pass",
                    "updated_at": "2026-08-22T12:00:00",
                    "reviewer": "private-analyst",
                    "action": "pass",
                }
            }
        },
    )
    model = build_testing_page(
        records=repos.evidence.list(),
        inbox_dir=main.INBOX_DIR,
        entities={row["id"]: row for row in repos.entities.list()},
        berry_labels=main.BERRIES,
        static_build=True,
    )
    dumped = json.dumps(model)
    assert "private-analyst" not in dumped
    assert model["testing_groups"][0]["key"] == "tagged"
    assert model["items"][0]["workflow_label"] == "Tagged evidence"
    assert not model["items"][0]["reviewer"]
