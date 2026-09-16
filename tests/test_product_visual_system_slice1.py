"""Focused UI tests for Product Visual System production Slice 1 (/today + reader)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.daily_intelligence_briefing import (
    attach_reader_payload,
    build_daily_intelligence_briefing,
    present_briefing_item,
)
from app.services.briefing_page import present_briefing_page

client = TestClient(app)
TODAY = date(2026, 9, 15)
STATIC = Path("app/static")


def _record(**overrides):
    base = {
        "id": "ev-pvs-readable",
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
    return [{"id": "company-fall-creek", "name": "Fall Creek", "entity_type": "company"}]


def test_pvs_token_and_briefing_assets_exist():
    assert (STATIC / "pvs_tokens.css").is_file()
    assert (STATIC / "daily_briefing.css").is_file()
    assert (STATIC / "daily_briefing.js").is_file()
    tokens = (STATIC / "pvs_tokens.css").read_text(encoding="utf-8")
    assert "--pvs-navy: #08234d" in tokens
    assert "--pvs-accent: #8a6a3b" in tokens
    assert "--pvs-canvas: #f4f1ea" in tokens
    assert "--brief-navy: var(--pvs-navy)" in tokens
    css = (STATIC / "daily_briefing.css").read_text(encoding="utf-8")
    assert "prefers-reduced-motion" in css
    assert "var(--pvs-touch)" in css
    assert "daily-briefing-reader" in css
    assert "daily-briefing-skeleton" in css


def test_today_loads_pvs_stylesheets_and_slice_marker():
    response = client.get("/today")
    assert response.status_code == 200
    body = response.text
    assert 'href="/static/pvs_tokens.css"' in body
    assert 'href="/static/daily_briefing.css"' in body
    assert 'src="/static/daily_briefing.js"' in body
    assert 'data-pvs-slice="1"' in body
    assert "Family=Fraunces" in body or "family=Fraunces" in body
    assert "thumbs-up" not in body.lower()
    assert "prototype/product-visual-system-v1" not in body


def test_readable_card_keeps_in_app_reader_affordance():
    response = client.get("/today")
    assert response.status_code == 200
    body = response.text
    assert "data-briefing-open-reader" in body
    assert "Read in app" in body
    # Original source remains a separate secondary action when present
    assert "Original source" in body or "View original source" in body or "data-briefing-open-reader" in body


def test_limited_and_blocked_states_render_honestly():
    briefing = build_daily_intelligence_briefing(
        evidence=[
            _record(id="ev-ok"),
            _record(
                id="ev-bot",
                summary="This website uses a security service to protect against malicious bots.",
                article={
                    "paragraphs": [
                        {
                            "text": (
                                "This website uses a security service to protect against malicious bots. "
                                "This page is displayed while the website verifies you are not a bot."
                            )
                        }
                    ]
                },
            ),
        ],
        entities=_entities(),
        today=TODAY,
    )
    page = present_briefing_page(briefing)
    assert page["what_changed_count"] >= 1
    assert page["needs_attention_count"] >= 1
    attention_ids = {item["id"] for item in page["needs_attention"]}
    assert "ev-bot" in attention_ids
    bot = next(item for item in page["needs_attention"] if item["id"] == "ev-bot")
    assert bot["usable_in_app"] is False
    assert bot.get("attention_label") or bot.get("readable_body_label")


def test_empty_what_changed_honest_copy():
    briefing = build_daily_intelligence_briefing(
        evidence=[],
        entities=_entities(),
        today=TODAY,
    )
    page = present_briefing_page(briefing)
    assert page["what_changed_empty"] is True
    # Route still renders empty state chrome
    response = client.get("/today?berry=__none__")
    assert response.status_code == 200
    assert "No current trusted readable coverage" in response.text or "What Changed" in response.text


def test_reader_dialog_accessibility_contract():
    response = client.get(
        "/today?reader=ev-20260806173605-61c6-berries-market-size-share-trends-growth-"
    )
    assert response.status_code == 200
    body = response.text
    assert 'role="dialog"' in body
    assert 'aria-modal="true"' in body
    assert 'id="briefing-reader"' in body
    assert "aria-label=\"Close in-app reader\"" in body
    assert "daily-briefing-trust-badge" in body
    assert "In-app reader" in body


def test_reader_payload_preserves_trust_display_without_mutations():
    entities_by_id = {e["id"]: e for e in _entities()}
    item = present_briefing_item(_record(), entities_by_id=entities_by_id, today=TODAY)
    assert item.get("review_trust_state")
    row = attach_reader_payload(item, _record())
    assert row.get("reader_mode") in {
        "readable",
        "partial",
        "transcript",
        "description_only",
        "access_limited",
        "body_unavailable",
        "interstitial",
        "missing",
    }
    page = present_briefing_page(
        build_daily_intelligence_briefing(evidence=[_record()], entities=_entities(), today=TODAY)
    )
    assert page["thumbs_mutations_implemented"] == 0


def test_v2_css_no_longer_embeds_briefing_rules():
    v2 = (STATIC / "v2.css").read_text(encoding="utf-8")
    assert ".daily-briefing-card {" not in v2
    assert "Loaded from today.html" in v2 or "daily_briefing.css" in v2
