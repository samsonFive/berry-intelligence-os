"""Analyst dogfood UX: morning workflow continuity, honest dates, trust labels."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.main import app
from app.services.chronology import dated_label
from app.services.saved_brief_packs import save_pack
from app.services.watchlist import add_watch, load_watches


def _ev(eid: str, published: str, *, captured: str | None = None, **extra) -> dict:
    record = {
        "id": eid,
        "status": "published",
        "title": eid,
        "published_date": published,
        "captured_date": captured or published,
        "source_name": "Planasa Newsroom",
        "source_type": "company_website",
        "berry_ids": ["berry-blueberry"],
        "priority": {"reading": {"level": "none", "rationale": ""}},
    }
    record.update(extra)
    return record


def test_dated_label_does_not_present_captured_as_published() -> None:
    captured_only = {"captured_date": "2026-08-23", "published_date": ""}
    labeled = dated_label(captured_only)
    assert "Captured" in labeled
    assert "Published" not in labeled
    published = dated_label({"published_date": "2026-08-20", "captured_date": "2026-08-24"})
    assert published.startswith("Published")


def test_today_is_a_morning_console_with_source_problems_and_next_work(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path / "inbox")
    monkeypatch.setattr(main, "DATA_DIR", tmp_path / "data")
    (tmp_path / "inbox").mkdir(parents=True, exist_ok=True)
    main._NAV_WORK_CACHE["key"] = None
    main._NAV_WORK_CACHE["value"] = None
    expected = {
        "system_state": "DEGRADED",
        "current_through": "2026-08-24T12:00:00+00:00",
        "last_successful_collection": "2026-08-24T12:00:00+00:00",
        "last_new_intelligence": "2026-08-24T11:58:00+00:00",
        "can_claim_current": False,
        "counts": {"scheduled_sources": 73, "overdue": 2, "failing": 1, "blocked": 0},
    }
    monkeypatch.setattr("app.services.today.build_runtime_freshness", lambda **_kwargs: expected.copy())
    monkeypatch.setattr(main, "published_evidence", lambda: [_ev("new-low", "2026-08-24")])
    monkeypatch.setattr(main, "all_signals", lambda: [])
    monkeypatch.setattr(main, "all_assessments", lambda: [])
    monkeypatch.setattr(main, "load_sources", lambda: [])
    page = TestClient(main.app).get("/today")
    assert page.status_code == 200
    assert "data-today-source-problems" in page.text
    assert "Open Source Health" in page.text
    assert 'href="/sources"' in page.text
    assert 'href="/review-ops"' in page.text
    assert 'href="/pending"' in page.text
    assert 'href="/review?kind=atomic"' in page.text
    assert 'href="/watches"' in page.text
    assert 'href="/strategic-questions"' in page.text
    assert "No last-visit baseline yet" in page.text
    assert "name=\"decision\"" not in page.text


def test_today_get_does_not_mark_watchlist_seen_or_write_review_events(monkeypatch, tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(main, "INBOX_DIR", inbox)
    monkeypatch.setattr(main, "DATA_DIR", tmp_path / "data")
    add_watch(inbox, "company", "company-planasa")
    before = load_watches(inbox)[0]
    assert before["last_seen_at"] is None
    TestClient(main.app).get("/today")
    after = load_watches(inbox)[0]
    assert after["last_seen_at"] is None
    assert not (inbox / "review_events").exists()


def test_sidebar_puts_strategic_questions_in_decide_and_renames_monitoring_queue() -> None:
    page = TestClient(app).get("/today")
    assert page.status_code == 200
    html = page.text
    decide_at = html.find(">Decide<")
    system_at = html.find(">System<")
    sq_at = html.find(">Strategic Questions</span>")
    assert decide_at != -1 and system_at != -1 and sq_at != -1
    assert decide_at < sq_at < system_at
    assert ">Monitoring queue</span>" in html
    assert 'aria-label="Watches' not in html


def test_company_profile_watch_control_is_watchlist_not_monitoring_queue() -> None:
    page = TestClient(app).get("/entities/company/company-planasa")
    assert page.status_code == 200
    assert "Add to watchlist" in page.text or "Remove from watchlist" in page.text
    assert 'href="/queues/monitoring">Watch<' not in page.text
    assert 'href="/queues/monitoring">Watches<' not in page.text


def test_watchlist_filtered_empty_state_is_honest(tmp_path: Path, monkeypatch) -> None:
    inbox = tmp_path / "inbox"
    monkeypatch.setattr(main, "INBOX_DIR", inbox)
    client = TestClient(main.app)
    client.post(
        "/watches/toggle",
        data={"watch_type": "company", "object_id": "company-planasa", "action": "add", "return_to": "/watches"},
    )
    filtered = client.get("/watches?type=variety")
    assert filtered.status_code == 200
    assert "No watches match these filters" in filtered.text
    assert "aren't watching anything yet" not in filtered.text
    assert "aren&#39;t watching anything yet" not in filtered.text


def test_brief_pack_presentation_preserves_pack_id(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    record = save_pack(
        tmp_path,
        title="Q3 Blueberry Update",
        context_note="",
        berry_id="berry-blueberry",
        window_days=14,
        company_ids=["company-planasa"],
        variety_ids=[],
        signal_ids=[],
        assessment_ids=[],
        concept_slugs=[],
    )
    client = TestClient(main.app)
    opened = client.get(f"/brief-pack?pack_id={record['id']}&companies=company-planasa&title=Q3")
    assert opened.status_code == 200
    assert f"pack_id={record['id']}" in opened.text
    assert "present=1" in opened.text
    presented = client.get(
        f"/brief-pack?pack_id={record['id']}&companies=company-planasa&title=Q3&present=1"
    )
    assert presented.status_code == 200
    assert "v2-presentation-mode" in presented.text
    assert f"pack_id={record['id']}" in presented.text
    assert "Exit presentation mode" in presented.text


def test_geography_generic_entity_url_lands_on_geography_workspace() -> None:
    client = TestClient(app)
    redirected = client.get("/entities/geography/geography-spain", follow_redirects=False)
    assert redirected.status_code == 303
    assert redirected.headers["location"] == "/geographies/geography-spain"


def test_geography_workspace_includes_intelligence_timeline() -> None:
    page = TestClient(app).get("/geographies/geography-spain")
    assert page.status_code == 200
    assert "Intelligence timeline" in page.text
    assert "id=\"intelligence-timeline\"" in page.text


def test_ai_proposed_badge_is_visually_distinct_from_reviewed() -> None:
    css = (Path(main.BASE_DIR) / "app" / "static" / "app.css").read_text(encoding="utf-8")
    assert ".badge-ai-proposed" in css
    page = TestClient(app).get("/assessments/assessment-blueberry-genetics-commercialized-through-platforms")
    assert page.status_code == 200
    assert "badge-ai-proposed" in page.text
    assert "AI PROPOSED" in page.text
    reviewed = TestClient(app).get("/assessments/assessment-financial-capital-entering-berry-genetics-ownership")
    assert reviewed.status_code == 200
    assert "REVIEWED" in reviewed.text


def test_pending_and_review_ops_filters_can_be_cleared() -> None:
    client = TestClient(app)
    pending = client.get("/pending")
    assert pending.status_code == 200
    assert 'href="/pending">Clear</a>' in pending.text
    ops = client.get("/review-ops")
    assert ops.status_code == 200
    assert 'href="/review-ops">Clear</a>' in ops.text


def test_review_queue_reset_preserves_kind() -> None:
    page = TestClient(app).get("/review?kind=atomic")
    assert page.status_code == 200
    assert 'href="/review?kind=atomic"' in page.text


def test_evidence_geography_links_to_geography_workspace() -> None:
    page = TestClient(app).get("/geographies/geography-spain")
    assert page.status_code == 200
    assert "GEOGRAPHY INTELLIGENCE" in page.text
    assert "Intelligence timeline" in page.text
