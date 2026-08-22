"""Commercial Positions V2: tagged Evidence inventory, not a Position schema."""

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
    for folder in ("evidence", "facts", "signals", "assessments", "entities"):
        (tmp_path / "data" / folder).mkdir(parents=True, exist_ok=True)


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
        "summary": "Stored source summary.",
        "why_it_matters": "Stored rationale, not generated importance.",
        "submitted_by": "reviewer",
        "reviewed_by": "reviewer",
        "reviewed_at": "2026-08-10",
        "priority": deepcopy(PRIORITY),
        "berry_ids": ["berry-blueberry"],
        "entity_ids": ["company-hortifrut", "variety-example-blue", "geography-chile"],
        "evidence_links": [],
        "fact_ids": [],
        "does_not_prove": ["Does not prove a universal competitive ranking."],
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


def test_commercial_positions_v2_cards_are_inventory_not_scores(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    repos = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    priority = deepcopy(PRIORITY)
    priority["commercial_position"] = {
        "level": "high",
        "rationale": "Willingness to litigate changes the licensing risk.",
    }
    priority["testing"] = {"level": "medium", "rationale": "Verify the litigated claim."}
    record = _published(
        "ev-pos-1",
        title="Commercial fixture one",
        priority=priority,
        fact_ids=["fact-pos-1"],
        commercial_observation={"observed_at": "2026-08-10"},
        trade_observation={"berry_code_purity": "multi_berry_combined"},
    )
    _seed(repos, [record])
    repos.facts.create(
        {
            "id": "fact-pos-1",
            "record_type": "fact",
            "statement": "Hortifrut litigated a licensing dispute.",
            "classification": "fact",
            "confidence": "medium",
            "status": "active",
            "reviewer": "analyst-fixture",
            "created_at": "2026-08-10",
            "evidence_ids": ["ev-pos-1"],
        }
    )
    repos.signals.create(
        {
            "id": "signal-pos-1",
            "record_type": "signal",
            "title": "Licensing enforcement is tightening",
            "status": "active",
            "strength": "medium",
            "reviewer": "analyst-fixture",
            "evidence_ids": ["ev-pos-1", "ev-placeholder"],
        }
    )
    repos.assessments.create(
        {
            "id": "assessment-pos-1",
            "record_type": "assessment",
            "title": "Licensing risk is material for Chile blueberry programs",
            "rationale": "The stored fact is a legal action, not market share.",
            "status": "active",
            "confidence": "medium",
            "fact_ids": ["fact-pos-1"],
            "reviewer": "analyst-fixture",
            "created_at": "2026-08-10",
            "would_change_our_view": "A dismissed case with no remaining claims.",
        }
    )
    client = TestClient(app)
    page = client.get("/queues/commercial_position")
    assert page.status_code == 200
    html = page.text
    assert "not a queue of tasks" in html
    assert "not a Position object" in html
    assert "not a competitive score" in html
    assert "Hortifrut" in html
    assert "Commercial fixture one" in html
    assert "Facts" in html
    assert "Signals" in html
    assert "Assessments" in html
    assert "tag priority high" in html
    assert "competitive score" in html
    assert "Position object" in html
    assert "/entities/variety/variety-example-blue" in html
    assert "/search?q=" in html
    assert "data-open-reader" in html
    assert not Path("schemas/position.schema.json").exists()
    assert "Hortifrut litigated a licensing dispute." in html
    assert "Licensing enforcement is tightening" in html
    assert "Licensing risk is material" in html
    assert "would change our view" in html
    assert "multi_berry_combined" in html
    assert "Does not prove a universal competitive ranking" in html
    assert "Claim Testing" in html
    assert "Clear" not in html
    assert ">Pass<" not in html
    assert "queue-table" not in html
    assert "v2-claim-card" in html
    assert "/entities/company/company-hortifrut" in html
    private = client.get("/queues/commercial_position")
    assert "ai_proposed" not in private.text


def test_commercial_positions_hide_private_rows_on_static_model(monkeypatch, tmp_path: Path) -> None:
    from app.services.commercial_positions import commercial_page_model

    _isolate(monkeypatch, tmp_path)
    repos = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    priority = deepcopy(PRIORITY)
    priority["commercial_position"] = {"level": "medium", "rationale": "Tagged for position thinking."}
    record = _published("ev-pos-static", title="Static fixture", priority=priority)
    _seed(repos, [record])
    proposed = {
        "id": "signal-proposed-pos",
        "record_type": "signal",
        "title": "Should not leak",
        "status": "proposed",
        "strength": "low",
        "reviewer": "analyst-fixture",
        "evidence_ids": ["ev-pos-static", "ev-other"],
    }
    draft_assessment = {
        "id": "assessment-draft-pos",
        "record_type": "assessment",
        "title": "Private AI proposal",
        "rationale": "Not approved.",
        "status": "active",
        "confidence": "low",
        "fact_ids": ["fact-missing"],
        "evidence_ids": ["ev-pos-static"],
        "reviewer": "analyst-fixture",
        "created_at": "2026-08-10",
        "ai_proposed": True,
    }
    model = commercial_page_model(
        records=[record],
        inbox_dir=None,
        entities=main.entity_index(),
        berry_labels=main.BERRIES,
        facts=[],
        signals=[proposed],
        assessments=[draft_assessment],
        static_build=True,
    )
    html_bits = str(model["position_items"])
    assert "Should not leak" not in html_bits
    assert "Private AI proposal" not in html_bits


def test_commercial_positions_does_not_run_forbidden_work(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    repos = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    priority = deepcopy(PRIORITY)
    priority["commercial_position"] = {"level": "low", "rationale": "Inventory only."}
    _seed(repos, [_published("ev-pos-2", priority=priority)])
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
    client = TestClient(app)
    page = client.get("/queues/commercial_position")
    assert page.status_code == 200
    assert calls == []
