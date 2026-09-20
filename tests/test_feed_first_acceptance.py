"""P0 acceptance matrix for the feed-first path. Not a Gate 5 release."""

from datetime import date

from fastapi.testclient import TestClient

from app.main import app
from app.services.feed_first import (
    apply_decision,
    build_feed,
    empty_state,
    extract_statements,
    load_state,
    parse_filters,
    set_entity_tier,
)
from app.services.seed_roster import build_roster, roster_counts


def _record(**overrides):
    base = {
        "id": "ev-accept",
        "status": "published",
        "title": "Fall Creek Spain reaches 14 million blueberry plants after 10 years",
        "summary": "Fall Creek marked 10 years in Spain and reports 14 million plants.",
        "source_name": "FreshPlaza",
        "source_type": "trade_press",
        "source_url": "https://example.test/fall-creek-spain",
        "published_date": "2026-05-26",
        "berry_ids": ["berry-blueberry"],
        "entity_ids": ["company-fall-creek-farm-and-nursery"],
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


def test_p0_today_is_front_door_and_not_review_ops():
    page = TestClient(app).get("/today")
    assert page.status_code == 200
    assert "data-feed-first-today" in page.text
    assert "Publication Review" not in page.text


def test_p0_thumbs_persist_undo_idempotent_and_do_not_mute(tmp_path):
    inbox = tmp_path / "inbox"
    record = _record()
    first = apply_decision(inbox, item_id=record["id"], action="thumbs_up", evidence=[record])
    retry = apply_decision(inbox, item_id=record["id"], action="thumbs_up", evidence=[record])
    assert [row["id"] for row in retry["statements"]] == [row["id"] for row in first["statements"]]
    down = apply_decision(inbox, item_id=record["id"], action="thumbs_down", evidence=[record])
    assert down["muted_world"] is False
    assert down["statements"] == []
    undo = apply_decision(inbox, item_id=record["id"], action="clear_reaction", evidence=[record])
    assert undo["decision"]["reaction"] is None


def test_p0_save_does_not_imply_trust(tmp_path):
    inbox = tmp_path / "inbox"
    record = _record()
    saved = apply_decision(inbox, item_id=record["id"], action="save", evidence=[record])
    assert saved["decision"]["saved"] is True
    assert saved["statements"] == []


def test_p0_statement_has_exact_support_and_keeps_original(tmp_path):
    from app.services.feed_first import mutate_statement

    inbox = tmp_path / "inbox"
    record = _record()
    applied = apply_decision(inbox, item_id=record["id"], action="thumbs_up", evidence=[record])
    statement = applied["statements"][0]
    assert statement["supporting_passages"]
    assert statement["supporting_passages"][0]
    original = statement["original_extraction_text"]
    edited = mutate_statement(
        inbox, statement_id=statement["id"], action="edit", text="Spain nursery now reports 14 million plants."
    )
    assert edited["original_extraction_text"] == original
    assert edited["statement_text"] != original


def test_p0_tier_does_not_change_verification(tmp_path):
    inbox = tmp_path / "inbox"
    set_entity_tier(inbox, entity_id="company-fall-creek-farm-and-nursery", tier="tier1")
    feed = build_feed(
        evidence=[_record()],
        entities=[
            {
                "id": "company-fall-creek-farm-and-nursery",
                "name": "Fall Creek",
                "status": "active",
                "verification_status": "verified-secondary",
            }
        ],
        state=load_state(inbox),
        filters=parse_filters({"tier": "tier1", "window": "30d"}),
        today=date(2026, 6, 1),
    )
    assert feed["cards"][0]["entities"][0]["verification_status"] == "verified-secondary"
    assert feed["cards"][0]["entities"][0]["tier"] == "tier1"


def test_p0_blocked_body_yields_no_statements():
    blocked = _record(
        summary="Please log in to continue. Subscribe to continue reading.",
        article={"paragraphs": [{"text": "Please log in to continue. Subscribe to continue reading."}]},
    )
    assert extract_statements(blocked) == []


def test_p0_seed_not_bulk_trusted_and_registries_excluded():
    counts = roster_counts(build_roster([]))
    assert counts["tracked_companies"] == 145
    assert counts["registries"] == 6
    assert counts["candidates"] == 61
    roster = build_roster([])
    assert all(row["status"] == "unverified" for row in roster if row["candidate"])
    assert all(row["competitor"] is False for row in roster if row["is_registry"])


def test_p0_reader_keyboard_help_and_research_ops_are_not_home():
    today = TestClient(app).get("/today")
    assert "data-keyboard-help" in today.text
    ops = TestClient(app).get("/research-ops")
    assert ops.status_code == 200
    assert "data-feed-first-ops" in ops.text
    assert "CatchAll" in ops.text


def test_p1_feed_first_company_profile_is_berry_os():
    page = TestClient(app).get("/entities/company/company-fall-creek-farm-and-nursery?view=feed")
    assert page.status_code == 200
    assert "data-feed-first-company" in page.text
    assert "From Today thumbs-up" in page.text
    assert "Create 90-day report" not in page.text
    legacy = TestClient(app).get("/entities/company/company-fall-creek-farm-and-nursery?view=legacy")
    assert legacy.status_code == 200
    assert "data-feed-first-company" not in legacy.text
