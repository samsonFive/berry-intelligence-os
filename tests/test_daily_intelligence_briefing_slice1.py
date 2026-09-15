"""Focused tests for Daily Intelligence Briefing production Slice 1."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.daily_intelligence_briefing import (
    attach_attention_metadata,
    attach_reader_payload,
    build_daily_intelligence_briefing,
    classify_briefing_bucket,
    is_safe_record_id,
    landscape_handoff_url,
    parse_briefing_filters,
    present_briefing_item,
    recency_band_for,
)
from app.services.briefing_page import present_briefing_page

client = TestClient(app)
TODAY = date(2026, 9, 15)
FIXTURE = Path("prototypes/daily-intelligence-briefing-v2/fixtures/briefing-v2.json")


def _record(**overrides):
    base = {
        "id": "ev-test-1",
        "status": "published",
        "title": "Blueberry packing expansion",
        "summary": "A grower expanded cold storage for the coming season.",
        "why_it_matters": "",
        "source_name": "Trade Press",
        "source_url": "https://example.test/story",
        "published_date": "2026-09-01",
        "captured_date": "2026-09-10",
        "berry_ids": ["berry-blueberry"],
        "entity_ids": ["company-fall-creek"],
        "tags": ["supply"],
        "article": {
            "paragraphs": [
                {
                    "text": (
                        "The company opened a new packing line serving export customers across the southern hemisphere. "
                        "Managers said cold-storage capacity will rise ahead of the next harvest window. "
                        "No varieties were named in the release and investment totals were withheld."
                    )
                }
            ]
        },
    }
    base.update(overrides)
    return base


def _entities():
    return [
        {"id": "company-fall-creek", "name": "Fall Creek", "entity_type": "company"},
        {"id": "brand-ozblu", "name": "OZblu", "entity_type": "brand"},
        {
            "id": "breeding_program-uc-davis-strawberry",
            "name": "UC Davis Strawberry Breeding Program",
            "entity_type": "breeding_program",
        },
    ]


def test_adapter_never_loads_prototype_fixture(monkeypatch):
    opened = []
    real_open = open

    def guarded_open(path, *args, **kwargs):
        text = str(path)
        opened.append(text)
        if "briefing-v2.json" in text or "daily-intelligence-briefing-v2/fixtures" in text:
            raise AssertionError(f"prototype fixture read attempted: {text}")
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr("builtins.open", guarded_open)
    briefing = build_daily_intelligence_briefing(
        evidence=[_record()],
        entities=_entities(),
        sources=[],
        today=TODAY,
    )
    assert briefing["prototype_fixture_used"] is False
    assert briefing["fixture_dependency"] is None
    assert briefing["what_changed_count"] == 1
    assert not any("briefing-v2.json" in path for path in opened)


def test_only_readable_trusted_current_items_enter_what_changed():
    readable = _record(id="ev-readable")
    blocked = _record(
        id="ev-bot",
        summary="This website uses a security service to protect against malicious bots.",
        article={"paragraphs": [{"text": "This website uses a security service to protect against malicious bots. This page is displayed while the website verifies you are not a bot."}]},
        why_it_matters="Should never surface",
    )
    old = _record(id="ev-old", published_date="2024-01-01", captured_date="2026-09-14")
    undated = _record(id="ev-undated", published_date="", captured_date="2026-09-14")
    briefing = build_daily_intelligence_briefing(
        evidence=[readable, blocked, old, undated],
        entities=_entities(),
        today=TODAY,
    )
    changed_ids = [item["id"] for band in briefing["what_changed_bands"] for item in band["entries"]]
    assert changed_ids == ["ev-readable"]
    assert all(item["usable_in_app"] for band in briefing["what_changed_bands"] for item in band["entries"])
    attention_ids = {item["id"] for item in briefing["needs_attention"]}
    assert "ev-bot" in attention_ids
    assert "ev-old" not in changed_ids
    assert any(item["id"] == "ev-old" for item in briefing["historical_context"])
    assert any(item["id"] == "ev-undated" for item in briefing["unknown_publication_dates"])


def test_bot_wall_and_consent_get_no_invented_summary():
    bot = _record(
        id="ev-bot",
        summary="This website uses a security service to protect against malicious bots.",
        article={"paragraphs": [{"text": "This website uses a security service to protect against malicious bots. This page is displayed while the website verifies you are not a bot."}]},
        why_it_matters="Fabricated implication",
    )
    ents = {e["id"]: e for e in _entities()}
    item = present_briefing_item(bot, entities_by_id=ents, today=TODAY)
    item = attach_attention_metadata(item)
    item = attach_reader_payload(item, bot)
    assert item["observed_change"] is None
    assert item["analyst_implication"] is None
    assert item["implication_available"] is False
    assert item["attention_reason"] == "bot_wall"
    assert item["reader_paragraphs"] == []


def test_publication_date_drives_recency_not_capture_date():
    assert recency_band_for(date(2024, 1, 1), today=TODAY) == "older"
    record = _record(published_date="2024-01-01", captured_date="2026-09-14")
    item = present_briefing_item(record, entities_by_id={e["id"]: e for e in _entities()}, today=TODAY)
    assert item["recency_band"] == "older"
    assert classify_briefing_bucket(item) == "historical"


def test_missing_implication_is_not_generated():
    record = _record(why_it_matters="")
    briefing = build_daily_intelligence_briefing(evidence=[record], entities=_entities(), today=TODAY)
    item = briefing["what_changed_bands"][0]["entries"][0]
    assert item["implication_available"] is False
    assert item.get("implication_placeholder")


def test_explicit_implication_stays_distinct():
    record = _record(why_it_matters="Capacity expansion may tighten nursery supply.")
    item = present_briefing_item(record, entities_by_id={e["id"]: e for e in _entities()}, today=TODAY)
    assert item["observed_change"]
    assert item["analyst_implication"] == "Capacity expansion may tighten nursery supply."
    assert item["observed_change"] != item["analyst_implication"]


def test_query_params_restore_filters_and_reader_state():
    filters = parse_briefing_filters(
        {"berry": "blueberry", "region": "Americas", "reader": "ev-test-1", "attention": "bot_wall"}
    )
    assert filters.berry == "blueberry"
    assert filters.region == "Americas"
    assert filters.reader == "ev-test-1"
    assert filters.attention == "bot_wall"
    assert "berry=blueberry" in filters.to_query()
    assert "reader=ev-test-1" in filters.to_query(include_reader=True)


def test_reader_rejects_unsafe_record_ids():
    assert is_safe_record_id("ev-ok-1")
    assert not is_safe_record_id("../etc/passwd")
    assert not is_safe_record_id("ev/../../x")
    filters = parse_briefing_filters({"reader": "../secret"})
    assert filters.reader == ""


def test_landscape_handoff_uses_competitors_contract():
    url = landscape_handoff_url(berry="blueberry", entity_id="company-fall-creek")
    assert url.startswith("/competitors?")
    assert "berry=blueberry" in url
    assert "company=company-fall-creek" in url
    assert "from=today" in url


def test_non_company_entities_keep_valid_profile_urls():
    record = _record(entity_ids=["brand-ozblu", "breeding_program-uc-davis-strawberry"])
    item = present_briefing_item(record, entities_by_id={e["id"]: e for e in _entities()}, today=TODAY)
    urls = {e["id"]: e["profile_url"] for e in item["entities"]}
    assert urls["brand-ozblu"] == "/entities/brand/brand-ozblu"
    assert (
        urls["breeding_program-uc-davis-strawberry"]
        == "/entities/breeding_program/breeding_program-uc-davis-strawberry"
    )


def test_today_route_renders_briefing_without_fixture_file_dependency():
    assert FIXTURE.exists()  # prototype package remains available as design evidence
    response = client.get("/today")
    assert response.status_code == 200
    body = response.text
    assert "Daily Intelligence Briefing" in body
    assert "What Changed" in body
    assert "Needs Attention" in body
    assert "Coverage Pulse" in body
    assert "briefing-v2.json" not in body
    assert "thumbs-up" not in body.lower()
    assert 'name="thumbs"' not in body


def test_reader_query_preserves_filters_and_stays_in_app():
    response = client.get("/today?berry=blueberry&reader=ev-20260806173605-61c6-berries-market-size-share-trends-growth-")
    assert response.status_code == 200
    assert "In-app reader" in response.text
    assert "Published" in response.text
    assert "Captured" in response.text
    assert "View original source" in response.text or "original source" in response.text.lower()


def test_page_adapter_marks_no_fixture_dependency():
    briefing = build_daily_intelligence_briefing(evidence=[_record()], entities=_entities(), today=TODAY)
    page = present_briefing_page(briefing)
    assert page["prototype_fixture_used"] is False
    assert page["fixture_dependency"] is None
    assert page["thumbs_mutations_implemented"] == 0
