"""Gate A / Gate 1 feed-first golden path."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.feed_first import (
    EXTRACTION_MODEL,
    apply_decision,
    build_feed,
    empty_state,
    extract_statements,
    load_state,
    parse_filters,
    playground_fixtures,
    set_entity_tier,
    statements_for_entity,
)


def _record(**overrides):
    base = {
        "id": "ev-gate1-readable",
        "status": "published",
        "title": "Fall Creek Spain reaches 14 million blueberry plants after 10 years",
        "summary": "Fall Creek marked 10 years in Spain and reports 14 million plants.",
        "source_name": "FreshPlaza",
        "source_type": "trade_press",
        "source_url": "https://example.test/fall-creek-spain",
        "published_date": "2026-05-26",
        "captured_date": "2026-08-06",
        "berry_ids": ["berry-blueberry"],
        "entity_ids": ["company-fall-creek-farm-and-nursery"],
        "geography_ids": ["geography-spain"],
        "article": {
            "paragraphs": [
                {
                    "text": (
                        "Fall Creek Farm & Nursery marked 10 years of operations in Spain. "
                        "Established in 2016 with a two-hectare harvest using plug material from the U.S., "
                        "the operation has expanded to 14 million blueberry plants."
                    )
                }
            ]
        },
    }
    base.update(overrides)
    return base


def _entities():
    return [
        {
            "id": "company-fall-creek-farm-and-nursery",
            "name": "Fall Creek Farm & Nursery",
            "entity_type": "company",
            "status": "active",
        }
    ]


def test_tokens_and_playground_exist():
    css = Path("app/static/berry_os.css").read_text(encoding="utf-8")
    assert "--bos-ink: #0b1020" in css
    assert "--bos-strawberry: #f43f5e" in css
    assert "prefers-reduced-motion" in css
    page = TestClient(app).get("/design-system")
    assert page.status_code == 200
    assert "data-design-system" in page.text
    assert "Playground fixtures only" in page.text
    assert "Card families" in page.text
    assert "Berry Growth Loader" in page.text


def test_today_is_feed_first_front_door():
    page = TestClient(app).get("/")
    assert page.status_code in {200, 307}
    today = TestClient(app).get("/today")
    assert today.status_code == 200
    assert "data-feed-first-today" in today.text
    assert "thumbs_up" in today.text
    assert "berry_os.css" in today.text
    assert "Stored published evidence" in today.text
    assert 'name="tier"' in today.text
    assert 'name="crop"' in today.text
    assert 'name="source"' in today.text
    assert 'name="window"' in today.text
    assert 'name="state"' in today.text


def test_legacy_briefing_still_available():
    page = TestClient(app).get("/today?view=briefing")
    assert page.status_code == 200
    assert "Daily Intelligence Briefing" in page.text
    assert "thumbs-up" not in page.text.lower()


def test_filters_and_card_families():
    official = _record(
        id="ev-official",
        source_type="company_website",
        source_name="Fall Creek",
        title="Our history",
    )
    social = _record(
        id="ev-catalog",
        source_type="company_catalog",
        title="Sekoya catalog",
    )
    registry = _record(
        id="ev-patent",
        source_type="patent_record",
        source_name="USPTO",
        title="Plant patent",
        berry_ids=["berry-blueberry"],
        entity_ids=["company-fall-creek-farm-and-nursery"],
    )
    blocked = _record(
        id="ev-blocked",
        title="Paywalled note",
        summary="Please log in to continue. Subscribe to continue reading.",
        article={"paragraphs": [{"text": "Please log in to continue. Subscribe to continue reading."}]},
    )
    feed = build_feed(
        evidence=[_record(), official, social, registry, blocked],
        entities=_entities(),
        state=empty_state(),
        filters=parse_filters({"crop": "blueberry", "window": "30d"}),
        today=date(2026, 6, 1),
    )
    kinds = {item["source_kind"] for item in feed["items"]}
    families = {item["family"] for item in feed["items"]}
    assert "article" in kinds
    assert "official" in kinds
    assert "registry" in kinds
    assert "social" in families or "social" in kinds
    assert feed["has_fallback"]
    blueberry = build_feed(
        evidence=[_record(), _record(id="ev-berry", berry_ids=["berry-strawberry"], title="Strawberry only")],
        entities=_entities(),
        state=empty_state(),
        filters=parse_filters({"crop": "blueberry"}),
        today=date(2026, 6, 1),
    )
    assert all("blueberry" in item["crops"] for item in blueberry["items"])


def test_thumbs_persist_undo_and_do_not_mute(tmp_path: Path):
    inbox = tmp_path / "inbox"
    record = _record()
    first = apply_decision(inbox, item_id=record["id"], action="thumbs_up", evidence=[record])
    assert first["decision"]["reaction"] == "up"
    assert first["statements"]
    assert first["statements"][0]["extraction_model"] == EXTRACTION_MODEL
    retry = apply_decision(inbox, item_id=record["id"], action="thumbs_up", evidence=[record])
    assert len(retry["statements"]) == len(first["statements"])
    assert {row["id"] for row in retry["statements"]} == {row["id"] for row in first["statements"]}
    down = apply_decision(inbox, item_id=record["id"], action="thumbs_down", evidence=[record])
    assert down["decision"]["reaction"] == "down"
    assert down["statements"] == []
    assert down["muted_world"] is False
    state = load_state(inbox)
    assert state["entity_tiers"] == {}
    undo = apply_decision(inbox, item_id=record["id"], action="clear_reaction", evidence=[record])
    assert undo["decision"]["reaction"] is None


def test_thumbs_down_hides_from_default_feed(tmp_path: Path):
    inbox = tmp_path / "inbox"
    record = _record()
    apply_decision(inbox, item_id=record["id"], action="thumbs_down", evidence=[record])
    hidden = build_feed(
        evidence=[record],
        entities=_entities(),
        state=load_state(inbox),
        filters=parse_filters({}),
        today=date(2026, 6, 1),
    )
    assert hidden["items"] == []
    judged = build_feed(
        evidence=[record],
        entities=_entities(),
        state=load_state(inbox),
        filters=parse_filters({"state": "judged"}),
        today=date(2026, 6, 1),
    )
    assert judged["items"][0]["id"] == record["id"]


def test_blocked_body_yields_no_statements():
    blocked = _record(
        id="ev-blocked-extract",
        summary="Please log in to continue. Subscribe to continue reading.",
        article={"paragraphs": [{"text": "Please log in to continue. Subscribe to continue reading."}]},
    )
    assert extract_statements(blocked) == []


def test_statement_edit_keeps_original(tmp_path: Path):
    from app.services.feed_first import mutate_statement

    inbox = tmp_path / "inbox"
    record = _record()
    applied = apply_decision(inbox, item_id=record["id"], action="thumbs_up", evidence=[record])
    statement_id = applied["statements"][0]["id"]
    original = applied["statements"][0]["original_extraction_text"]
    edited = mutate_statement(inbox, statement_id=statement_id, action="edit", text="Spain nursery now at 14 million plants.")
    assert edited is not None
    assert edited["statement_text"] == "Spain nursery now at 14 million plants."
    assert edited["original_extraction_text"] == original
    assert edited["supporting_passages"]


def test_tier_does_not_change_verification(tmp_path: Path):
    inbox = tmp_path / "inbox"
    set_entity_tier(inbox, entity_id="company-fall-creek-farm-and-nursery", tier="tier1")
    feed = build_feed(
        evidence=[_record()],
        entities=_entities(),
        state=load_state(inbox),
        filters=parse_filters({"tier": "tier1"}),
        today=date(2026, 6, 1),
    )
    assert feed["items"]
    assert feed["items"][0]["entities"][0]["verification_status"] == "active"
    assert feed["items"][0]["entities"][0]["tier"] == "tier1"


def test_react_http_and_entity_reflection(tmp_path, monkeypatch):
    from app import main

    inbox = tmp_path / "inbox"
    monkeypatch.setattr(main, "INBOX_DIR", inbox)
    record = _record()
    monkeypatch.setattr(main, "published_evidence", lambda: [record])
    client = TestClient(main.app)
    up = client.post("/api/feed-first/react", json={"item_id": record["id"], "action": "thumbs_up"})
    assert up.status_code == 200
    assert up.json()["decision"]["reaction"] == "up"
    retry = client.post("/api/feed-first/react", json={"item_id": record["id"], "action": "thumbs_up"})
    assert [row["id"] for row in retry.json()["statements"]] == [row["id"] for row in up.json()["statements"]]
    state = load_state(inbox)
    reflected = statements_for_entity(state, "company-fall-creek-farm-and-nursery")
    assert reflected
    down = client.post("/api/feed-first/react", json={"item_id": record["id"], "action": "thumbs_down"})
    assert down.json()["muted_world"] is False


def test_people_watchlist_is_honest():
    page = TestClient(app).get("/people")
    assert page.status_code == 200
    assert "provider-unavailable" in page.text
    assert "Empty watchlist" in page.text


def test_playground_fixtures_are_not_the_today_corpus():
    ids = {row["id"] for row in playground_fixtures()}
    assert all(item_id.startswith("fixture-") for item_id in ids)
    today = TestClient(app).get("/today")
    assert "fixture-lead-article" not in today.text
