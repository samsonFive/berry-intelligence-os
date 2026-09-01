"""Guided analyst experience + Today modernization V1."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.services.guided_analyst import (
    build_attention_queues,
    count_phrase,
    nav_count_labels,
    variety_identity_waiting_count,
    watch_monitoring_snapshot,
)
from app.services.today import build_today
from app.services.watchlist import add_watch, load_watches


NOW = datetime(2026, 8, 24, 14, 0, tzinfo=UTC)


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


def test_today_recent_items_newest_first_with_honest_dates() -> None:
    page = build_today(
        published=[
            _ev("older", "2026-08-22"),
            _ev("newer", "2026-08-24"),
            _ev("captured-only", "", captured="2026-08-23"),
        ],
        signals=[],
        assessments=[],
        sources=[],
        inbox_dir=Path("/tmp"),
        data_dir=Path("/tmp"),
        now=NOW,
    )
    items = [item for band in page["latest_bands"] for item in band["rows"]]
    assert [item["id"] for item in items][:2] == ["newer", "captured-only"]
    by_id = {item["id"]: item for item in items}
    assert by_id["newer"]["date_basis_label"] == "Published"
    assert by_id["captured-only"]["date_basis_label"] == "Captured"
    assert by_id["captured-only"]["when_origin"] == "captured"
    assert all(item.get("date_basis_label") for item in items)


def test_attention_queues_do_not_invent_new_since_last_visit() -> None:
    queues = build_attention_queues(
        publication_waiting=12,
        publication_since_brief=None,
        atomic_waiting=0,
        variety_waiting=3,
        source_failing=1,
        source_overdue=2,
        source_blocked=0,
        retrying=0,
        authoring_mode=True,
    )
    by_key = {row["key"]: row for row in queues}
    assert by_key["publication"]["waiting_label"] == "12 Publications awaiting review"
    assert by_key["publication"]["recent_label"] == ""
    assert "new since last visit" not in by_key["publication"]["recent_label"].lower()
    assert "does not erase the original Source record" in by_key["publication"]["after"]
    assert "does not invent a new trusted Variety" in by_key["variety"]["after"]
    labeled = nav_count_labels({"review_now": 1693, "atomic_pending": 1})
    assert labeled["review_now"] == "1,693 Publications awaiting review"
    assert "Reviews 1693" not in labeled["review_now"]
    assert count_phrase(0, "Publication awaiting review", "Publications awaiting review") == (
        "0 Publications awaiting review"
    )


def test_today_route_console_help_and_no_trust_mutation(monkeypatch, tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(main, "INBOX_DIR", inbox)
    monkeypatch.setattr(main, "DATA_DIR", tmp_path / "data")
    main._NAV_WORK_CACHE["key"] = None
    main._NAV_WORK_CACHE["value"] = None
    add_watch(inbox, "company", "company-planasa")
    expected = {
        "system_state": "DEGRADED",
        "current_through": "2026-08-24T12:00:00+00:00",
        "last_successful_collection": "2026-08-24T12:00:00+00:00",
        "last_collection_attempt": "2026-08-24T12:05:00+00:00",
        "last_new_intelligence": "2026-08-24T11:58:00+00:00",
        "can_claim_current": False,
        "retrying_count": 1,
        "counts": {"scheduled_sources": 73, "overdue": 2, "failing": 1, "blocked": 0, "retrying": 1},
    }
    monkeypatch.setattr("app.services.today.build_runtime_freshness", lambda **_kwargs: expected.copy())
    monkeypatch.setattr(main, "published_evidence", lambda: [_ev("new-low", "2026-08-24")])
    monkeypatch.setattr(main, "all_signals", lambda: [])
    monkeypatch.setattr(main, "all_assessments", lambda: [])
    monkeypatch.setattr(main, "load_sources", lambda: [])
    before = load_watches(inbox)[0]
    assert before["last_seen_at"] is None
    page = TestClient(main.app).get("/today")
    assert page.status_code == 200
    html = page.text
    assert "Recent intelligence" in html
    assert "Needs your attention" in html
    assert "Publications awaiting review" in html
    assert "data-workspace-help" in html
    assert "How Berry Intelligence Works" in html
    assert 'href="/guide"' in html
    assert "new since last visit" not in html.lower()
    assert "Open Source Health" in html
    assert 'href="/collection-ops"' in html
    assert "name=\"decision\"" not in html
    assert "Create Report" not in html
    after = load_watches(inbox)[0]
    assert after["last_seen_at"] is None
    assert not (inbox / "review_events").exists()


def test_today_sparse_empty_states(monkeypatch, tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(main, "INBOX_DIR", inbox)
    monkeypatch.setattr(main, "DATA_DIR", tmp_path / "data")
    main._NAV_WORK_CACHE["key"] = None
    main._NAV_WORK_CACHE["value"] = None
    monkeypatch.setattr(
        "app.services.today.build_runtime_freshness",
        lambda **_kwargs: {
            "system_state": "CURRENT",
            "current_through": None,
            "last_successful_collection": None,
            "last_new_intelligence": None,
            "can_claim_current": False,
            "counts": {"scheduled_sources": 0, "overdue": 0, "failing": 0, "blocked": 0},
        },
    )
    monkeypatch.setattr(main, "published_evidence", lambda: [])
    monkeypatch.setattr(main, "all_signals", lambda: [])
    monkeypatch.setattr(main, "all_assessments", lambda: [])
    monkeypatch.setattr(main, "load_sources", lambda: [])
    page = TestClient(main.app).get("/today")
    assert page.status_code == 200
    assert "No new trusted developments captured in the last 14 days" in page.text
    assert "You are not monitoring anything yet" in page.text
    assert "No Publications are waiting for review" in page.text
    snapshot = watch_monitoring_snapshot(inbox_dir=inbox)
    assert snapshot["watch_count"] == 0
    assert snapshot["has_watches"] is False


def test_guide_is_read_only_orientation(monkeypatch, tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(main, "INBOX_DIR", inbox)
    page = TestClient(main.app).get("/guide")
    assert page.status_code == 200
    html = page.text
    assert "How Berry Intelligence Works" in html
    assert "Trusted intelligence lifecycle" in html
    assert "Variety identity" in html
    assert "DISCOVERED" in html
    assert "REVIEW REQUIRED" in html
    assert "TRUSTED" in html
    assert "CANDIDATE" in html
    assert "POSSIBLE ALIAS" in html
    assert "OPERATOR ACTION" in html
    assert "name=\"decision\"" not in html
    assert "<form" not in html or 'action="/login"' not in html
    assert list(inbox.iterdir()) == []


def test_publication_and_atomic_and_variety_explanations() -> None:
    client = TestClient(main.app)
    pending = client.get("/pending")
    assert pending.status_code == 200
    assert "Newly discovered Publications that have not yet been accepted" in pending.text
    assert "does not erase the original Source record" in pending.text
    assert "data-workspace-help" in pending.text
    atomic = client.get("/review?kind=atomic")
    assert atomic.status_code == 200
    assert "Proposed individual intelligence statements" in atomic.text
    assert "does not delete the parent Publication" in atomic.text
    assert "Automated extraction remains disabled or unqualified" in atomic.text
    assert 'href="/collection-ops"' in atomic.text
    variety = client.get("/varieties/candidates")
    assert variety.status_code == 200
    assert "CANDIDATE, not a trusted Variety" in variety.text
    assert "does not create a new trusted Variety" in variety.text
    assert 'href="/varieties/coverage"' in variety.text


def test_collection_ops_and_source_degradation_next_action() -> None:
    client = TestClient(main.app)
    ops = client.get("/collection-ops")
    assert ops.status_code == 200
    assert "data-workspace-help" in ops.text
    assert "Viewing this page does not publish" in ops.text
    sources = client.get("/sources")
    assert sources.status_code == 200
    assert "data-workspace-help" in sources.text
    assert "OPERATOR ACTION" in sources.text


def test_contextual_help_on_major_pages() -> None:
    client = TestClient(main.app)
    for path in (
        "/today",
        "/sources",
        "/collection-ops",
        "/pending",
        "/review?kind=atomic",
        "/signals",
        "/assessments",
        "/strategic-questions",
        "/watches",
        "/varieties/coverage",
        "/varieties/candidates",
        "/brief-packs",
    ):
        page = client.get(path)
        assert page.status_code == 200, path
        assert "data-workspace-help" in page.text, path
        assert "About this workspace" in page.text, path


def test_queue_count_semantics_in_sidebar() -> None:
    html = TestClient(main.app).get("/today").text
    assert "Publications awaiting review" in html
    assert "How it works" in html
    assert 'href="/guide"' in html


def test_variety_waiting_count_ignores_distinct_and_rejected(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    target = inbox / "variety_candidates"
    target.mkdir(parents=True)
    (target / "a.json").write_text(
        '{"id":"a","identity_state":"possible_alias","status":"proposed"}\n', encoding="utf-8"
    )
    (target / "b.json").write_text(
        '{"id":"b","identity_state":"distinct","status":"reviewed"}\n', encoding="utf-8"
    )
    (target / "c.json").write_text(
        '{"id":"c","identity_state":"unknown","status":"rejected"}\n', encoding="utf-8"
    )
    assert variety_identity_waiting_count(inbox) == 1


def test_workspace_help_is_collapsed_details() -> None:
    css = (Path(main.BASE_DIR) / "app" / "static" / "app.css").read_text(encoding="utf-8")
    assert ".workspace-help" in css
    page = TestClient(main.app).get("/signals")
    assert "<details class=\"workspace-help\"" in page.text
    assert "A Signal is a pattern that may be emerging" in page.text
    assessments = TestClient(main.app).get("/assessments")
    assert "analyst interpretation of Facts" in assessments.text
    questions = TestClient(main.app).get("/strategic-questions")
    assert "enduring questions" in questions.text.lower()
    assert 'href="/brief-pack"' in questions.text or "Brief Pack" in questions.text
