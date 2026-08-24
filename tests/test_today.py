"""Today landing: recency-first, not importance-first."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.session_auth import DEFAULT_NEXT_PATH, safe_next_path
from app.services.today import build_today, development_stamp


NOW = datetime(2026, 8, 24, 14, 0, tzinfo=UTC)


def _ev(eid: str, published: str, *, captured: str | None = None, reading: str = "none", **extra) -> dict:
    record = {
        "id": eid,
        "status": "published",
        "title": eid,
        "published_date": published,
        "captured_date": captured or published,
        "source_name": "Planasa Newsroom",
        "source_type": "company_website",
        "berry_ids": ["berry-blueberry"],
        "priority": {"reading": {"level": reading, "rationale": ""}},
    }
    record.update(extra)
    return record


def test_today_item_leads_over_21_day_important() -> None:
    page = build_today(
        published=[
            _ev("old-high", "2026-08-03", reading="high"),
            _ev("new-low", "2026-08-24", reading="none"),
        ],
        signals=[],
        assessments=[],
        sources=[],
        inbox_dir=Path("/tmp"),
        data_dir=Path("/tmp"),
        now=NOW,
    )
    ids = [item["id"] for band in page["latest_bands"] for item in band["rows"]]
    assert ids[0] == "new-low"
    assert "old-high" not in ids
    assert any(item["id"] == "old-high" for item in page["worth_revisiting"])


def test_reacquired_old_article_is_not_today() -> None:
    historic = _ev(
        "historic",
        "2023-03-01",
        captured="2026-08-24",
        reacquired_at="2026-08-24T12:00:00+00:00",
    )
    stamp, origin = development_stamp(historic)
    assert origin == "published"
    assert stamp is not None and stamp.year == 2023
    page = build_today(
        published=[historic],
        signals=[],
        assessments=[],
        sources=[],
        inbox_dir=Path("/tmp"),
        data_dir=Path("/tmp"),
        now=NOW,
    )
    assert page["quiet"] is True
    assert not any(item["id"] == "historic" for band in page["latest_bands"] for item in band["rows"])


def test_captured_fallback_is_labeled() -> None:
    page = build_today(
        published=[_ev("no-pub", "", captured="2026-08-23")],
        signals=[],
        assessments=[],
        sources=[],
        inbox_dir=Path("/tmp"),
        data_dir=Path("/tmp"),
        now=NOW,
    )
    item = page["latest_bands"][0]["rows"][0]
    assert item["when_origin"] == "captured"
    assert item["id"] == "no-pub"


def test_bands_and_quiet_and_signals() -> None:
    page = build_today(
        published=[
            _ev("d0", "2026-08-24"),
            _ev("d2", "2026-08-22"),
            _ev("d6", "2026-08-18"),
            _ev("d12", "2026-08-12"),
        ],
        signals=[{"id": "sig-1", "title": "Emerging", "status": "proposed", "first_seen": "2026-08-23", "berry_ids": ["berry-blueberry"]}],
        assessments=[{"id": "as-1", "title": "View", "created_at": "2026-08-24", "market_ids": ["berry-blueberry"]}],
        sources=[{"id": "source-a", "discovery": {"adapter": "article_rss"}}],
        inbox_dir=Path("/tmp"),
        data_dir=Path("/tmp"),
        now=NOW,
    )
    keys = [band["key"] for band in page["latest_bands"]]
    assert "today" in keys
    assert page["developing_signals"][0]["kind_label"] == "SIGNAL"
    assert any(item["kind_label"] == "ANALYST ASSESSMENT" for band in page["latest_bands"] for item in band["rows"])
    empty = build_today(published=[], signals=[], assessments=[], sources=[], inbox_dir=Path("/tmp"), data_dir=Path("/tmp"), now=NOW)
    assert empty["quiet"] is True


def test_today_uses_authoritative_freshness_contract(monkeypatch) -> None:
    expected = {
        "system_state": "DEGRADED",
        "current_through": "2026-08-24T12:00:00+00:00",
        "last_successful_collection": "2026-08-24T12:00:00+00:00",
        "last_new_intelligence": "2026-08-24T11:58:00+00:00",
        "can_claim_current": False,
        "counts": {"scheduled_sources": 73, "overdue": 2, "failing": 1, "blocked": 0},
    }
    monkeypatch.setattr("app.services.today.build_runtime_freshness", lambda **_kwargs: expected.copy())
    page = build_today(
        published=[], signals=[], assessments=[], sources=[], inbox_dir=Path("/tmp"), data_dir=Path("/tmp"), now=NOW,
    )
    freshness = page["freshness"]
    assert freshness["system_state"] == "DEGRADED"
    assert freshness["can_claim_current"] is False
    assert freshness["last_collection_at"] == expected["last_successful_collection"]
    assert freshness["last_captured_at"] == expected["last_new_intelligence"]
    assert freshness["discoverable_sources"] == 73
    assert freshness["counts"]["overdue"] == 2


def test_login_lands_on_today_and_preserves_deep_link(monkeypatch) -> None:
    from tests.test_remote_auth import OPERATOR, PASSWORD, _client, _enable_remote

    assert DEFAULT_NEXT_PATH == "/today"
    assert safe_next_path("") == "/today"
    assert safe_next_path("/pending") == "/pending"
    _enable_remote(monkeypatch)
    client = _client()
    landed = client.post("/login", data={"username": OPERATOR, "password": PASSWORD})
    assert landed.status_code == 303
    assert landed.headers["location"] == "/today"
    deep = client.post("/login", data={"username": OPERATOR, "password": PASSWORD, "next": "/pending"})
    assert deep.headers["location"] == "/pending"


def test_today_route_reader_and_mobile_css(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path / "inbox")
    monkeypatch.setattr(main, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(main, "published_evidence", lambda: [_ev("new-low", "2026-08-24")])
    monkeypatch.setattr(main, "all_signals", lambda: [])
    monkeypatch.setattr(main, "all_assessments", lambda: [])
    monkeypatch.setattr(main, "load_sources", lambda: [])
    page = TestClient(main.app).get("/today")
    assert page.status_code == 200
    assert "Latest developments" in page.text
    assert "data-open-reader" in page.text
    assert "COMPANY-REPORTED" in page.text
    assert "name=\"decision\"" not in page.text
    css = (Path(main.BASE_DIR) / "app" / "static" / "app.css").read_text(encoding="utf-8")
    assert ".today-age" in css
    assert "@media(max-width:834px)" in css
    blueberry = TestClient(main.app).get("/today?berry=berry-raspberry")
    assert blueberry.status_code == 200
