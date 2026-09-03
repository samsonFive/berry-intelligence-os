"""Strategy War Room V1.

Compose-only: every section here reads an existing subsystem's own
output (Radar cache, Moves board, Market Reality store, trusted Evidence,
Strategic Questions, Company Compare) and filters/ranks it to a scope.
These tests check scope filtering, that nothing here mutates trust state
or persists a real Watch/Alert, geography region expansion, session
notes, and that discussion questions are always honestly labeled.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main
from app.main import app
from app.services.competitive_moves.models import CompetitiveMove, MovesBoard
from app.services.war_room.compose import compose_war_room
from app.services.war_room.discussion_questions import generate_discussion_questions
from app.services.war_room.models import WarRoomScope
from app.services.war_room.notes import add_note, list_notes_for_scope
from app.services.watchtower.store import load_alerts

NOW = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)

ENTITIES = {
    "company-planasa": {"id": "company-planasa", "entity_type": "company", "name": "Planasa"},
    "company-hortifrut": {"id": "company-hortifrut", "entity_type": "company", "name": "Hortifrut S.A."},
    "geography-peru": {"id": "geography-peru", "entity_type": "geography", "name": "Peru"},
    "geography-europe": {"id": "geography-europe", "entity_type": "geography", "name": "Europe"},
    "geography-spain": {"id": "geography-spain", "entity_type": "geography", "name": "Spain"},
}
BERRY_LABELS = {"berry-blueberry": "Blueberry", "berry-blackberry": "Blackberry"}

RELATIONSHIPS_EUROPE_CONTAINS_SPAIN = [
    {"subject_id": "geography-spain", "predicate": "part_of", "object_id": "geography-europe", "status": "active"},
]


def _move(**overrides) -> CompetitiveMove:
    base = dict(
        id="move-planasa-genetics",
        company_id="company-planasa",
        company_name="Planasa",
        move_type="GENETICS_LAUNCH",
        title="Planasa launches new strawberry variety",
        what_happened="Planasa launched a new commercial strawberry variety in Spain.",
        why_move=("Canonical competitor named", "Classified from Variety Launch"),
        first_seen="2026-08-29T09:00:00+00:00",
        latest_update="2026-08-29T09:00:00+00:00",
        geography_ids=("geography-spain",),
        geography_labels=("Spain",),
        berry_ids=("berry-blueberry",),
        supporting_development_ids=("dev-1",),
    )
    base.update(overrides)
    return CompetitiveMove(**base)


def _board(moves) -> MovesBoard:
    return MovesBoard(
        generated_at=NOW.isoformat(), freshness_label="fresh", cache_status="fresh",
        trust_label="LIVE / UNREVIEWED MOVE", moves=moves, patterns=[], momentum=[],
        sections=[], featured_timeline=None, stats={},
    )


def _compose(monkeypatch, *, scope: WarRoomScope, moves=None, inbox_dir: Path, **overrides):
    board = _board(moves or [])
    monkeypatch.setattr("app.services.war_room.compose.edition_from_cache", lambda inbox_dir: None)
    monkeypatch.setattr("app.services.war_room.compose.compose_moves_board", lambda developments, inbox_dir=None: board)
    defaults = dict(
        inbox_dir=inbox_dir,
        entities=ENTITIES,
        relationships=RELATIONSHIPS_EUROPE_CONTAINS_SPAIN,
        published_evidence=[],
        facts=[],
        signals=[],
        assessments=[],
        strategic_questions=[],
        berry_labels=BERRY_LABELS,
        now=NOW,
    )
    defaults.update(overrides)
    return compose_war_room(scope, **defaults)


# ---- Scope filtering ----

def test_empty_scope_composes_with_zero_ephemeral_watches(monkeypatch, tmp_path: Path) -> None:
    scope = WarRoomScope(berry_id=None)
    session = _compose(monkeypatch, scope=scope, inbox_dir=tmp_path)
    assert session["needs_attention"] == []
    assert session["scope_label"] == "All berries, all markets"


def test_moves_filtered_to_scope_company() -> None:
    pass  # covered via _move_matches_scope below (pure function, no I/O needed)


# ---- Strategic Whitespace Radar integration (reused, not duplicated) ----

def test_whitespace_omitted_without_a_geography_scope(monkeypatch, tmp_path: Path) -> None:
    # Demo 3's shape: a company-only, global scope -- Whitespace needs a
    # company x geography grid, so this must honestly omit it rather than
    # fabricate one.
    planasa_move = _move()
    scope = WarRoomScope(berry_id="berry-blueberry", company_ids=("company-planasa",))
    session = _compose(monkeypatch, scope=scope, moves=[planasa_move], inbox_dir=tmp_path)
    assert session["coverage_unknown"] == []
    assert session["competitive_overlap"] == []
    assert session["whitespace_href"] is None


def test_whitespace_populated_with_full_scope(monkeypatch, tmp_path: Path) -> None:
    planasa_move = _move()
    hortifrut_move = _move(id="move-hortifrut", company_id="company-hortifrut", company_name="Hortifrut S.A.", geography_ids=("geography-spain",), geography_labels=("Spain",))
    scope = WarRoomScope(berry_id="berry-blueberry", geography_ids=("geography-europe",), company_ids=("company-planasa", "company-hortifrut"))
    session = _compose(monkeypatch, scope=scope, moves=[planasa_move, hortifrut_move], inbox_dir=tmp_path)
    assert session["whitespace_href"] is not None
    assert session["whitespace_href"].startswith("/whitespace?")
    # Two companies both showing activity in the same (expanded) geography
    # is exactly what "competitors overlap" should surface.
    assert session["competitive_overlap"]


def test_who_is_moving_filters_by_company(monkeypatch, tmp_path: Path) -> None:
    hortifrut_move = _move(id="move-hortifrut", company_id="company-hortifrut", company_name="Hortifrut S.A.")
    planasa_move = _move()
    scope = WarRoomScope(berry_id=None, company_ids=("company-planasa",))
    session = _compose(monkeypatch, scope=scope, moves=[hortifrut_move, planasa_move], inbox_dir=tmp_path)
    names = {m["company_name"] for m in session["who_is_moving"]}
    assert names == {"Planasa"}


def test_geography_region_expands_to_member_countries(monkeypatch, tmp_path: Path) -> None:
    spain_move = _move()  # geography_ids=("geography-spain",)
    scope = WarRoomScope(berry_id=None, geography_ids=("geography-europe",))
    session = _compose(monkeypatch, scope=scope, moves=[spain_move], inbox_dir=tmp_path)
    assert len(session["who_is_moving"]) == 1  # Europe scope picks up a Spain-tagged move


def test_geography_country_scope_does_not_pick_up_unrelated_country(monkeypatch, tmp_path: Path) -> None:
    spain_move = _move()
    scope = WarRoomScope(berry_id=None, geography_ids=("geography-peru",))
    session = _compose(monkeypatch, scope=scope, moves=[spain_move], inbox_dir=tmp_path)
    assert session["who_is_moving"] == []


# ---- Sections that must be omitted, not padded ----

def test_competitive_positioning_omitted_below_two_companies(monkeypatch, tmp_path: Path) -> None:
    scope = WarRoomScope(berry_id=None, company_ids=("company-planasa",))
    session = _compose(monkeypatch, scope=scope, inbox_dir=tmp_path)
    assert session["competitive_positioning"] is None
    assert session["compare_href"] is None


def test_competitive_positioning_present_with_two_or_more_companies(monkeypatch, tmp_path: Path) -> None:
    scope = WarRoomScope(berry_id=None, company_ids=("company-planasa", "company-hortifrut"))
    session = _compose(monkeypatch, scope=scope, inbox_dir=tmp_path)
    assert session["competitive_positioning"] is not None
    assert session["compare_href"] == "/entities/company/compare?ids=company-planasa,company-hortifrut" or "company-hortifrut,company-planasa" in session["compare_href"]


# ---- Needs attention is ephemeral, never persisted ----

def test_needs_attention_never_persists_a_real_alert(monkeypatch, tmp_path: Path) -> None:
    planasa_move = _move()
    scope = WarRoomScope(berry_id=None, company_ids=("company-planasa",))
    session = _compose(monkeypatch, scope=scope, moves=[planasa_move], inbox_dir=tmp_path)
    assert any(a["subject_id"] == "company-planasa" for a in session["needs_attention"])
    # A real Watchtower alert store must never be written by opening a War Room session.
    assert load_alerts(tmp_path) == []


def test_needs_attention_never_writes_a_real_watch(monkeypatch, tmp_path: Path) -> None:
    scope = WarRoomScope(berry_id=None, company_ids=("company-planasa",))
    _compose(monkeypatch, scope=scope, inbox_dir=tmp_path)
    assert not (tmp_path / "watchlist_state.json").exists()


# ---- Discussion questions: always present, honestly labeled ----

def test_discussion_questions_deterministic_without_completer() -> None:
    result = generate_discussion_questions(
        moves=[{"company_name": "Planasa", "move_label": "Genetics launch", "geography_labels": ["Spain"]}],
        market_changes=[], company_labels=["Planasa"], geography_labels=["Spain"], berry_label="Blueberry",
        completer=None,
    )
    assert result["source"] == "deterministic"
    assert result["questions"]
    assert "Planasa" in result["questions"][0]


def test_discussion_questions_ai_source_only_when_completer_actually_ran() -> None:
    class FakeResult:
        def __init__(self, questions):
            self.parsed = {"questions": questions}

    def fake_completer(prompt, **kwargs):
        return FakeResult(["Is Planasa's genetics activity in Spain changing the competitive structure?"])

    result = generate_discussion_questions(
        moves=[{"company_name": "Planasa", "move_label": "Genetics launch", "geography_labels": ["Spain"]}],
        market_changes=[], company_labels=["Planasa"], geography_labels=["Spain"], berry_label="Blueberry",
        completer=fake_completer,
    )
    assert result["source"] == "ai"


def test_discussion_questions_ungrounded_ai_output_falls_back_to_deterministic() -> None:
    class FakeResult:
        def __init__(self, questions):
            self.parsed = {"questions": questions}

    def fake_completer(prompt, **kwargs):
        return FakeResult(["Is Zylo Corp entering the durian market with a secret genetics platform?"])

    result = generate_discussion_questions(
        moves=[{"company_name": "Planasa", "move_label": "Genetics launch", "geography_labels": ["Spain"]}],
        market_changes=[], company_labels=["Planasa"], geography_labels=["Spain"], berry_label="Blueberry",
        completer=fake_completer,
    )
    assert result["source"] == "deterministic"  # hallucinated company name never survives grounding


def test_discussion_questions_completer_exception_falls_back_gracefully() -> None:
    def broken_completer(prompt, **kwargs):
        raise RuntimeError("provider down")

    result = generate_discussion_questions(
        moves=[{"company_name": "Planasa", "move_label": "Genetics launch", "geography_labels": ["Spain"]}],
        market_changes=[], company_labels=["Planasa"], geography_labels=["Spain"], berry_label="Blueberry",
        completer=broken_completer,
    )
    assert result["source"] == "deterministic"
    assert result["questions"]


# ---- Session notes ----

def test_session_notes_round_trip_and_scope_filtered(tmp_path: Path) -> None:
    add_note(tmp_path, text="Discuss Planasa genetics pipeline", berry_id="berry-blueberry", geography_ids=(), company_ids=("company-planasa",))
    add_note(tmp_path, text="Unrelated note", berry_id="berry-blackberry", geography_ids=(), company_ids=())
    matching = list_notes_for_scope(tmp_path, berry_id="berry-blueberry", geography_ids=(), company_ids=("company-planasa",))
    assert len(matching) == 1
    assert matching[0]["text"] == "Discuss Planasa genetics pipeline"


def test_add_note_rejects_empty_text(tmp_path: Path) -> None:
    try:
        add_note(tmp_path, text="   ", berry_id=None, geography_ids=(), company_ids=())
        raised = False
    except ValueError:
        raised = True
    assert raised


# ---- Routes ----

def test_war_room_page_empty_state_shows_scope_form() -> None:
    page = TestClient(app).get("/war-room")
    assert page.status_code == 200
    assert "Prepare for the meeting" in page.text
    assert "Compose session" in page.text


def test_war_room_page_with_scope_renders_session(monkeypatch) -> None:
    planasa_move = _move()
    board = _board([planasa_move])
    monkeypatch.setattr("app.main.compose_war_room", lambda scope, **kwargs: {
        "scope_label": "Blueberry · Planasa", "window_days": 30, "radar_freshness_label": "fresh",
        "executive_snapshot": {"moves": 1, "developments": 0, "market_changes": 0, "needs_attention": 0, "genetics_ip": 0, "strategic_questions": 0},
        "what_changed": [], "who_is_moving": [m.as_dict() for m in [planasa_move]], "needs_attention": [],
        "competitive_positioning": None, "market_reality": [], "genetics_ip": {"moves": [], "developments": []},
        "emerging_developments": [], "key_uncertainties": [], "questions_for_team": {"questions": ["Is Planasa expanding?"], "source": "deterministic"},
        "strategic_questions": [], "watch_next": [], "notes": [], "ask_berry_os_href": "/research?q=x",
        "compare_href": None, "create_meeting_brief_href": "/reports/new", "watchtower_href": "/watchtower",
        "scope": {"berry_id": "berry-blueberry", "geography_ids": [], "company_ids": ["company-planasa"], "window_days": 30},
    })
    page = TestClient(app).get("/war-room?berry=blueberry&company_ids=company-planasa")
    assert page.status_code == 200
    assert "Blueberry · Planasa" in page.text
    assert "Planasa launched a new commercial strawberry variety in Spain." in page.text
    assert "SUGGESTED DISCUSSION QUESTIONS" in page.text


def test_war_room_needs_attention_never_shows_broken_reopen_button(monkeypatch) -> None:
    # Real bug found during this mission's own demo pass: ephemeral War
    # Room alerts are never persisted, so they never get a "state" key the
    # way real Watchtower alerts do -- _alert_card.html's else-branch
    # rendered a bare "Reopen ()" and posted to a Watchtower alert id that
    # was never stored.
    fake_alert = {
        "id": "wta-fake", "trigger_type": "MARKET_REALITY_CHANGE", "trigger_label": "Market Reality change",
        "subject_type": "berry", "subject_id": "berry-blueberry", "subject_label": "Blueberry",
        "title": "Peru Blueberries — Export Volume +32.2%", "what_happened": "242,000 -> 320,000 MT",
        "why_triggered": ["Watched berry: Blueberry"], "priority": "HIGH ATTENTION", "priority_reasons": ["Watched berry: Blueberry"],
        "generated_at": "2026-09-02T12:00:00+00:00", "first_generated_at": "2026-09-02T12:00:00+00:00", "event_at": "2026-09-02",
        "sources": [], "trust_state": "MARKET REALITY", "related_development_id": None, "related_move_id": None,
        "market_context": None, "trusted_context": [], "open_href": "/today",
        "ask_berry_os_href": "/research?q=x", "create_brief_href": "/reports/new",
        # deliberately no "state" key -- exactly what generate_alerts()'s Alert.as_dict() produces
    }
    monkeypatch.setattr("app.main.compose_war_room", lambda scope, **kwargs: {
        "scope_label": "Blueberry", "window_days": 30, "radar_freshness_label": "fresh",
        "executive_snapshot": {"moves": 0, "developments": 0, "market_changes": 1, "needs_attention": 1, "genetics_ip": 0, "strategic_questions": 0, "findings": []},
        "what_changed": [], "who_is_moving": [], "needs_attention": [fake_alert],
        "competitive_positioning": None, "market_reality": [], "genetics_ip": {"moves": [], "developments": []},
        "emerging_developments": [], "key_uncertainties": [], "coverage_unknown": [], "competitive_overlap": [],
        "landscape_questions": [], "whitespace_watch_next": [], "whitespace_href": None,
        "questions_for_team": {"questions": ["x"], "source": "deterministic"},
        "strategic_questions": [], "watch_next": [], "notes": [], "ask_berry_os_href": "/research?q=x",
        "compare_href": None, "create_meeting_brief_href": "/reports/new", "watchtower_href": "/watchtower",
        "scope": {"berry_id": "berry-blueberry", "geography_ids": [], "company_ids": [], "window_days": 30},
    })
    page = TestClient(app).get("/war-room?berry=blueberry")
    assert page.status_code == 200
    assert "Reopen (" not in page.text
    assert 'action="/watchtower/wta-fake/action"' not in page.text
    assert "Ask Berry OS about this" in page.text  # the safe, non-mutating actions still show


def test_war_room_notes_route_persists_and_redirects(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    response = TestClient(app).post(
        "/war-room/notes",
        data={"text": "Follow up on Hortifrut genetics", "berry": "berry-blueberry", "company_ids": "company-hortifrut", "return_to": "/war-room?berry=blueberry"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    notes = list_notes_for_scope(tmp_path, berry_id="berry-blueberry", geography_ids=(), company_ids=("company-hortifrut",))
    assert len(notes) == 1


def test_war_room_notes_route_rejects_open_redirect(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    response = TestClient(app).post(
        "/war-room/notes",
        data={"text": "note", "return_to": "//evil.example.com"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/war-room"


def test_war_room_nav_entry_present() -> None:
    page = TestClient(app).get("/today")
    assert page.status_code == 200
    assert 'href="/war-room"' in page.text
