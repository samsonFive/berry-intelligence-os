"""Analyst Watchlist + Monitoring Workspace V1 -- private monitoring
interest in existing trusted objects. A Watch is navigation/state only,
never a trust object: it never creates Fact/Evidence/Signal/Assessment
and never mutates any canonical record."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.watchlist import (
    WATCH_TYPES,
    add_watch,
    is_watched,
    load_watches,
    mark_watch_seen,
    present_watch,
    remove_watch,
    watchlist_index,
)


def _entity(**overrides):
    row = {"record_type": "entity", "status": "active", "aliases": [], "berry_ids": [], "attributes": {}}
    row.update(overrides)
    return row


def _entities():
    rows = [
        _entity(id="company-a", entity_type="company", name="Company A", berry_ids=["berry-blueberry"]),
        _entity(id="variety-x", entity_type="variety", name="Variety X", berry_ids=["berry-blueberry"]),
        _entity(id="geography-spain", entity_type="geography", name="Spain"),
    ]
    return {r["id"]: r for r in rows}


def _sq(**overrides):
    row = {
        "id": "sq-test",
        "record_type": "strategic_question",
        "title": "Test question",
        "status": "active",
        "berry_ids": ["berry-blueberry"],
    }
    row.update(overrides)
    return row


def _evidence(**overrides):
    row = {
        "id": "ev-1",
        "title": "Test evidence",
        "source_name": "Some Source",
        "source_type": "trade_press",
        "published_date": "2026-01-01",
        "entity_ids": [],
        "geography_ids": [],
        "strategic_question_ids": [],
    }
    row.update(overrides)
    return row


def _assessment(**overrides):
    row = {
        "id": "assessment-1",
        "title": "Test assessment",
        "confidence": "medium",
        "ai_proposed": False,
        "created_at": "2026-01-01T00:00:00+00:00",
        "entity_ids": [],
        "strategic_question_ids": [],
    }
    row.update(overrides)
    return row


def _signal(**overrides):
    row = {"id": "sig-1", "title": "Test signal", "status": "confirmed", "entity_ids": [], "strategic_question_ids": []}
    row.update(overrides)
    return row


def _index(inbox, **kwargs):
    defaults = dict(
        inbox_dir=inbox,
        entities=_entities(),
        published_evidence=[],
        signals=[],
        assessments=[],
        recommendations=[],
        strategic_questions=[_sq()],
        sources=[],
        berry_labels={"berry-blueberry": "Blueberry"},
    )
    defaults.update(kwargs)
    return watchlist_index(**defaults)


def test_watch_and_unwatch_each_type(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    for watch_type, object_id in (
        ("company", "company-a"),
        ("variety", "variety-x"),
        ("geography", "geography-spain"),
        ("strategic_question", "sq-test"),
    ):
        assert not is_watched(inbox, watch_type, object_id)
        add_watch(inbox, watch_type, object_id)
        assert is_watched(inbox, watch_type, object_id)
        remove_watch(inbox, watch_type, object_id)
        assert not is_watched(inbox, watch_type, object_id)


def test_duplicate_watch_is_idempotent(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    add_watch(inbox, "company", "company-a")
    add_watch(inbox, "company", "company-a")
    watches = load_watches(inbox)
    assert len(watches) == 1


def test_invalid_watch_type_rejected(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    try:
        add_watch(inbox, "not_a_real_type", "x")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_never_viewed_watch_shows_full_count_and_never_seen_flag(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    add_watch(inbox, "company", "company-a")
    watch = load_watches(inbox)[0]
    evidence = [_evidence(id="ev-1", entity_ids=["company-a"], published_date="2026-01-01")]
    card = present_watch(
        watch, entities=_entities(), published_evidence=evidence, signals=[], assessments=[],
        recommendations=[], strategic_questions=[], sources=[], berry_labels={},
    )
    assert card["never_seen"] is True
    assert card["new_evidence_count"] == 1


def test_quiet_watch_after_seen_shows_zero_new(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    add_watch(inbox, "company", "company-a")
    mark_watch_seen(inbox, "company", "company-a")
    watch = load_watches(inbox)[0]
    evidence = [_evidence(id="ev-1", entity_ids=["company-a"], published_date="2020-01-01")]  # old
    card = present_watch(
        watch, entities=_entities(), published_evidence=evidence, signals=[], assessments=[],
        recommendations=[], strategic_questions=[], sources=[], berry_labels={},
    )
    assert card["never_seen"] is False
    assert card["new_evidence_count"] == 0
    assert card["evidence_count"] == 1  # the item itself is still shown, just not "new"


def test_new_evidence_after_last_seen_is_counted(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    add_watch(inbox, "company", "company-a")
    mark_watch_seen(inbox, "company", "company-a")
    watch = load_watches(inbox)[0]
    watch["last_seen_at"] = "2026-01-01T00:00:00+00:00"
    evidence = [
        _evidence(id="ev-old", entity_ids=["company-a"], published_date="2025-12-01"),
        _evidence(id="ev-new", entity_ids=["company-a"], published_date="2026-06-01"),
    ]
    card = present_watch(
        watch, entities=_entities(), published_evidence=evidence, signals=[], assessments=[],
        recommendations=[], strategic_questions=[], sources=[], berry_labels={},
    )
    assert card["new_evidence_count"] == 1
    assert card["evidence_count"] == 2


def test_captured_only_evidence_never_counts_as_new(tmp_path: Path) -> None:
    # No published_date -- a historical reacquisition (captured_date only)
    # must never masquerade as a new competitive development.
    inbox = tmp_path / "inbox"
    add_watch(inbox, "company", "company-a")
    watch = load_watches(inbox)[0]
    watch["last_seen_at"] = "2020-01-01T00:00:00+00:00"
    evidence = [_evidence(id="ev-1", entity_ids=["company-a"], published_date="", captured_date="2026-06-01")]
    card = present_watch(
        watch, entities=_entities(), published_evidence=evidence, signals=[], assessments=[],
        recommendations=[], strategic_questions=[], sources=[], berry_labels={},
    )
    assert card["new_evidence_count"] == 0


def test_new_assessment_counted_via_created_at(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    add_watch(inbox, "company", "company-a")
    watch = load_watches(inbox)[0]
    watch["last_seen_at"] = "2026-01-01T00:00:00+00:00"
    assessments = [_assessment(id="a-1", entity_ids=["company-a"], created_at="2026-06-01T00:00:00+00:00")]
    card = present_watch(
        watch, entities=_entities(), published_evidence=[], signals=[], assessments=assessments,
        recommendations=[], strategic_questions=[], sources=[], berry_labels={},
    )
    assert card["new_assessment_count"] == 1


def test_signal_count_never_claims_new(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    add_watch(inbox, "company", "company-a")
    watch = load_watches(inbox)[0]
    signals = [_signal(id="sig-1", entity_ids=["company-a"])]
    card = present_watch(
        watch, entities=_entities(), published_evidence=[], signals=signals, assessments=[],
        recommendations=[], strategic_questions=[], sources=[], berry_labels={},
    )
    assert card["signal_count"] == 1
    assert "new_signal_count" not in card  # deliberately not claimed -- no reliable Signal date field


def test_rights_vs_commercial_not_conflated_source_mix_only(tmp_path: Path) -> None:
    # Watch cards summarize source mix, never a rights=commercial claim.
    inbox = tmp_path / "inbox"
    add_watch(inbox, "variety", "variety-x")
    watch = load_watches(inbox)[0]
    evidence = [
        _evidence(id="ev-rights", entity_ids=["variety-x"], source_type="plant_breeders_rights_record"),
    ]
    card = present_watch(
        watch, entities=_entities(), published_evidence=evidence, signals=[], assessments=[],
        recommendations=[], strategic_questions=[], sources=[], berry_labels={},
    )
    assert card["evidence_count"] == 1
    assert not any("commercial" in label.casefold() for label, _ in card["source_type_counts"])


def test_monitoring_degraded_only_with_direct_source_link(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    add_watch(inbox, "company", "company-a")
    watch = load_watches(inbox)[0]
    # No sources at all -- must not fabricate a monitoring status.
    card_no_source = present_watch(
        watch, entities=_entities(), published_evidence=[], signals=[], assessments=[],
        recommendations=[], strategic_questions=[], sources=[], berry_labels={}, inbox_dir=inbox,
    )
    assert card_no_source["monitoring"] is None


def test_stale_watch_pointer_returns_none_not_crash(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    add_watch(inbox, "company", "company-does-not-exist")
    watch = load_watches(inbox)[0]
    card = present_watch(
        watch, entities=_entities(), published_evidence=[], signals=[], assessments=[],
        recommendations=[], strategic_questions=[], sources=[], berry_labels={},
    )
    assert card is None


def test_watchlist_index_filters_by_type(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    add_watch(inbox, "company", "company-a")
    add_watch(inbox, "variety", "variety-x")
    all_cards = _index(inbox)
    assert len(all_cards) == 2
    company_only = _index(inbox, watch_type_filter="company")
    assert len(company_only) == 1
    assert company_only[0]["watch_type"] == "company"


def test_watchlist_index_alphabetical_sort(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    add_watch(inbox, "company", "company-a")
    add_watch(inbox, "variety", "variety-x")
    cards = _index(inbox, sort="alphabetical")
    names = [c["name"] for c in cards]
    assert names == sorted(names)


def test_watchlist_index_new_first_sort_puts_new_intelligence_ahead(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    add_watch(inbox, "company", "company-a")
    add_watch(inbox, "variety", "variety-x")
    evidence = [_evidence(id="ev-1", entity_ids=["variety-x"], published_date="2026-01-01")]
    cards = _index(inbox, published_evidence=evidence)
    assert cards[0]["watch_type"] == "variety"  # has new -> first, even though "company" < "variety" alphabetically


def test_has_new_only_filter(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    add_watch(inbox, "company", "company-a")
    add_watch(inbox, "variety", "variety-x")
    evidence = [_evidence(id="ev-1", entity_ids=["variety-x"], published_date="2026-01-01")]
    cards = _index(inbox, published_evidence=evidence, has_new_only=True)
    assert len(cards) == 1
    assert cards[0]["watch_type"] == "variety"


def test_watchlist_state_is_body_free(tmp_path: Path) -> None:
    # The watch record itself only ever stores type/id/timestamps -- there
    # is no field for it to carry a body in, but assert the persisted JSON
    # stays exactly that shape.
    inbox = tmp_path / "inbox"
    add_watch(inbox, "company", "company-a")
    stored = load_watches(inbox)[0]
    assert set(stored.keys()) == {"watch_type", "object_id", "created_at", "last_seen_at"}


# --- Route-level tests against real production data ---


def test_watchlist_route_empty_state():
    client = TestClient(app)
    page = client.get("/watches")
    assert page.status_code == 200
    assert "aren&#39;t watching anything yet" in page.text or "aren't watching anything yet" in page.text


def test_watchlist_toggle_add_remove_route(tmp_path: Path, monkeypatch) -> None:
    from app import main

    monkeypatch.setattr(main, "INBOX_DIR", tmp_path / "inbox")
    client = TestClient(main.app)

    added = client.post(
        "/watches/toggle",
        data={"watch_type": "company", "object_id": "company-planasa", "action": "add", "return_to": "/watches"},
        follow_redirects=False,
    )
    assert added.status_code == 303
    page = client.get("/watches")
    assert "Plantas de Navarra" in page.text or "Planasa" in page.text

    removed = client.post(
        "/watches/toggle",
        data={"watch_type": "company", "object_id": "company-planasa", "action": "remove", "return_to": "/watches"},
        follow_redirects=False,
    )
    assert removed.status_code == 303
    page_after = client.get("/watches")
    assert "watching anything yet" in page_after.text


def test_open_watch_marks_seen_and_redirects(tmp_path: Path, monkeypatch) -> None:
    from app import main

    inbox = tmp_path / "inbox"
    monkeypatch.setattr(main, "INBOX_DIR", inbox)
    client = TestClient(main.app)
    client.post(
        "/watches/toggle",
        data={"watch_type": "company", "object_id": "company-planasa", "action": "add", "return_to": "/watches"},
    )
    resp = client.get(
        "/watches/open",
        params={"watch_type": "company", "object_id": "company-planasa"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/entities/company/company-planasa"
    stored = load_watches(inbox)[0]
    assert stored["last_seen_at"] is not None


def test_watchlist_page_never_rendered_seen_by_itself(tmp_path: Path, monkeypatch) -> None:
    # Loading /watches itself must never mark anything seen.
    from app import main

    inbox = tmp_path / "inbox"
    monkeypatch.setattr(main, "INBOX_DIR", inbox)
    client = TestClient(main.app)
    client.post(
        "/watches/toggle",
        data={"watch_type": "company", "object_id": "company-planasa", "action": "add", "return_to": "/watches"},
    )
    client.get("/watches")
    client.get("/watches")
    stored = load_watches(inbox)[0]
    assert stored["last_seen_at"] is None


def test_company_profile_has_watchlist_toggle():
    client = TestClient(app)
    page = client.get("/entities/company/company-planasa")
    assert page.status_code == 200
    assert "Add to watchlist" in page.text or "Remove from watchlist" in page.text


def test_variety_profile_has_watchlist_toggle():
    client = TestClient(app)
    page = client.get("/entities/variety/variety-blue-manila")
    assert page.status_code == 200
    assert "Add to watchlist" in page.text or "Remove from watchlist" in page.text


def test_company_portfolio_has_watchlist_toggle():
    client = TestClient(app)
    page = client.get("/entities/company/company-planasa/portfolio")
    assert page.status_code == 200
    assert "Add to watchlist" in page.text or "Remove from watchlist" in page.text


def test_geography_detail_has_watchlist_toggle():
    client = TestClient(app)
    page = client.get("/geographies/geography-spain")
    assert page.status_code == 200
    assert "Add to watchlist" in page.text or "Remove from watchlist" in page.text


def test_strategic_question_detail_has_watchlist_toggle():
    client = TestClient(app)
    page = client.get("/strategic-questions/sq-global-genetics-reach")
    assert page.status_code == 200
    assert "Add to watchlist" in page.text or "Remove from watchlist" in page.text


def test_no_trust_action_on_watchlist_page():
    # The page's own honest disclosure sentence ("it never publishes,
    # affirms, approves, or rejects anything") legitimately mentions these
    # words in prose -- what must never exist is an actionable control
    # (button/link text) that performs one of them.
    client = TestClient(app)
    page = client.get("/watches")
    assert page.status_code == 200
    lowered = page.text.casefold()
    for forbidden in (">publish<", ">affirm<", ">approve<", ">reject<", ">confirm signal<"):
        assert forbidden not in lowered


def test_no_score_language_on_watchlist_page():
    client = TestClient(app)
    page = client.get("/watches")
    assert page.status_code == 200
    lowered = page.text.casefold()
    for forbidden in ("importance score", "priority score", "relevance score"):
        assert forbidden not in lowered


def test_watchlist_uses_card_grid_not_wide_table():
    client = TestClient(app)
    page = client.get("/watches")
    assert page.status_code == 200
    assert "<table" not in page.text
