"""Resolved catalog membership survives older News/Digest presentation adapters."""
from datetime import UTC, datetime
import json

import pytest
from fastapi.testclient import TestClient

from app import main
from app.services.feed_first_live import save_bundle


def source(key, **changes):
    stamp = datetime.now(UTC).date().isoformat()
    return {
        "id": key, "record_type": "evidence", "status": "draft", "review_state": "draft",
        "evidence_role": "publication_artifact", "source_type": "trade_press",
        "source_name": "Berry Journal", "source_url": "https://example.invalid/" + key,
        "title": "Current blueberry greenhouse expansion", "summary": "A blueberry nursery expands production.",
        "published_date": stamp, "captured_date": stamp, "submitted_by": "test",
        "berry_ids": ["berry-blueberry"], "entity_ids": ["company-nursery"], "geography_ids": [],
        "priority": {key: {"level": "none", "rationale": ""} for key in ("reading", "testing", "monitoring", "commercial_position")},
        **changes,
    }


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path / "inbox")
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    monkeypatch.setattr("app.services.seed_roster.build_roster", lambda existing, **kwargs: [])
    repos = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    repos.entities.create({"id": "company-nursery", "record_type": "entity", "entity_type": "company",
                           "name": "Berry Nursery", "status": "active", "berry_ids": ["berry-blueberry"]})
    active = source("ev-current", article={"paragraphs": [{"text": "The blueberry nursery tested waxseal in the greenhouse."}]})
    folder = main.INBOX_DIR / "evidence"
    folder.mkdir(parents=True)
    (folder / "ev-current.json").write_text(json.dumps(active), encoding="utf-8")
    rejected = source("ev-excluded", status="rejected", review_state="rejected", title="Excluded old cached headline")
    repos.evidence.create(rejected)
    save_bundle(main.INBOX_DIR, {"today": datetime.now(UTC).date().isoformat(), "records": [
        {**rejected, "status": "published", "review_state": "published"},
    ]})
    return active, rejected


def test_digest_news_and_packet_do_not_reintroduce_rejected_cached_record(runtime):
    from app.personal_digest_routes import world
    from app.news_packet_routes import world as packet_world
    active, rejected = runtime
    records = world()[2]
    assert active["id"] in records
    assert rejected["id"] not in records
    packet_records = packet_world()[2]
    assert {row["id"] for row in packet_records} == {active["id"]}
    page = TestClient(main.app).get("/today")
    assert page.status_code == 200
    assert active["title"] in page.text
    assert rejected["title"] not in page.text


def test_company_news_and_region_views_include_current_intake_record(runtime):
    from app.map_region_routes import context
    active, _ = runtime
    assert {row["id"] for row in context("company-nursery")[3]} == {active["id"]}
    page = TestClient(main.app).get("/entities/company/company-nursery?tab=news")
    assert page.status_code == 200
    assert active["title"] in page.text


def test_body_lookup_and_background_classification_use_resolved_catalog(runtime, monkeypatch):
    from app import news_workspace_routes
    active, rejected = runtime
    body_for = news_workspace_routes.stored_body_lookup(main, {"q": "waxseal"})
    assert "waxseal" in body_for(active)
    assert body_for(rejected) == ""
    captured = {}
    monkeypatch.setattr("app.services.news_tag_semantics.enabled", lambda: False)
    monkeypatch.setattr("app.services.news_tags.backfill", lambda inbox, records: captured.update(records))
    result = news_workspace_routes._classify_stored_tags()
    assert set(captured) == {active["id"]}
    assert "article" in captured[active["id"]]
    assert result["sources"] == 1 and result["with_stored_body"] == 1
