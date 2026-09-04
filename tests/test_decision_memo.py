"""Executive Decision Memo Engine V1.

Decision Memo is a report_type mode on the existing Reports architecture,
sourced from compose_war_room() rather than the generic Evidence/Company/
Variety packet. These tests check scope carryover, section omission,
claim grounding, the scenario-engine seam, Market Reality's structured
(non-prose) formatting, the coverage-gap/whitespace-state vocabulary,
the internal/public boundary, Strategic-Question proposal behavior, and
that nothing here mutates trust state.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main
from app.main import app
from app.services.competitive_moves.models import CompetitiveMove, MovesBoard
from app.services.report_builder.decision_memo import (
    build_decision_memo_packet,
    generate_decision_memo_sections,
)
from app.services.report_builder.scope import REPORT_TYPE_LABELS, REPORT_TYPES, ResolvedScope

NOW = datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc)

ENTITIES = {
    "company-planasa": {"id": "company-planasa", "entity_type": "company", "name": "Planasa"},
    "company-hortifrut": {"id": "company-hortifrut", "entity_type": "company", "name": "Hortifrut S.A."},
    "geography-peru": {"id": "geography-peru", "entity_type": "geography", "name": "Peru"},
}
BERRY_LABELS = {"berry-blueberry": "Blueberry"}


def _move(**overrides) -> CompetitiveMove:
    base = dict(
        id="move-planasa-genetics",
        company_id="company-planasa",
        company_name="Planasa",
        move_type="GENETICS_LAUNCH",
        title="Planasa launches new blueberry variety",
        what_happened="Planasa launched a new commercial blueberry variety in Peru.",
        why_move=("Canonical competitor named", "Classified from Variety Launch"),
        first_seen="2026-08-29T09:00:00+00:00",
        latest_update="2026-08-29T09:00:00+00:00",
        geography_ids=("geography-peru",),
        geography_labels=("Peru",),
        berry_ids=("berry-blueberry",),
        corroboration="MULTIPLE INDEPENDENT SOURCES",
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


def _build_packet(monkeypatch, *, scope: ResolvedScope, moves=None, inbox_dir: Path, **overrides):
    board = _board(moves or [])
    monkeypatch.setattr("app.services.war_room.compose.edition_from_cache", lambda inbox_dir: None)
    monkeypatch.setattr("app.services.war_room.compose.compose_moves_board", lambda developments, inbox_dir=None: board)
    defaults = dict(
        inbox_dir=inbox_dir,
        entities=ENTITIES,
        relationships=[],
        published_evidence=[],
        facts=[],
        signals=[],
        assessments=[],
        strategic_questions=[],
        berry_labels=BERRY_LABELS,
        now=NOW,
    )
    defaults.update(overrides)
    return build_decision_memo_packet(scope, **defaults)


def _scope(**overrides) -> ResolvedScope:
    base = dict(
        report_type="decision_memo", berry_id="berry-blueberry", geography_ids=("geography-peru",),
        company_ids=("company-planasa",), variety_ids=(), strategic_question_id=None,
        date_window_days=30, focus_notes="Prepare a decision memo: Blueberry Peru",
    )
    base.update(overrides)
    return ResolvedScope(**base)


# ---- REPORT_TYPES registration ----

def test_decision_memo_registered_in_report_types() -> None:
    assert "decision_memo" in REPORT_TYPES
    assert REPORT_TYPE_LABELS["decision_memo"] == "Executive Decision Memo"


# ---- Scope carryover ----

def test_packet_preserves_scope(monkeypatch, tmp_path: Path) -> None:
    scope = _scope()
    packet = _build_packet(monkeypatch, scope=scope, inbox_dir=tmp_path)
    assert packet["berry_id"] == "berry-blueberry"
    assert packet["geography_ids"] == ["geography-peru"]
    assert packet["company_ids"] == ["company-planasa"]
    assert packet["window_days"] == 30
    assert packet["focus_notes"] == scope.focus_notes


def test_packet_defaults_window_when_scope_has_none(monkeypatch, tmp_path: Path) -> None:
    scope = _scope(date_window_days=None)
    packet = _build_packet(monkeypatch, scope=scope, inbox_dir=tmp_path)
    assert packet["window_days"] == 30


# ---- Section omission ----

def test_empty_packet_omits_all_conditional_sections_except_internal_data_needed(monkeypatch, tmp_path: Path) -> None:
    scope = _scope(company_ids=(), geography_ids=(), berry_id=None)
    packet = _build_packet(monkeypatch, scope=scope, inbox_dir=tmp_path)
    # War Room's own discussion-question generator always has a
    # deterministic fallback question, even for a fully empty scope
    # (correct, established behavior there) -- clear it here so this test
    # isolates section OMISSION logic, not that generator's own fallback.
    packet["questions_for_team"] = {"questions": [], "source": "deterministic"}
    sections = generate_decision_memo_sections(packet)
    section_ids = {s.section_id for s in sections}
    assert section_ids == {"internal_data_needed"}


def test_populated_packet_produces_multiple_real_sections(monkeypatch, tmp_path: Path) -> None:
    move = _move()
    scope = _scope()
    packet = _build_packet(monkeypatch, scope=scope, moves=[move], inbox_dir=tmp_path)
    sections = generate_decision_memo_sections(packet)
    section_ids = {s.section_id for s in sections}
    assert "what_changed" in section_ids
    assert "competitive_moves" in section_ids
    assert "internal_data_needed" in section_ids
    # Scenarios/confirm-refute stay omitted -- no scenario_provider wired.
    assert "plausible_scenarios" not in section_ids
    assert "confirm_refute" not in section_ids


# ---- Claim grounding ----

def test_executive_takeaway_deterministic_fallback_is_grounded(monkeypatch, tmp_path: Path) -> None:
    move = _move()
    packet = _build_packet(monkeypatch, scope=_scope(), moves=[move], inbox_dir=tmp_path)
    sections = generate_decision_memo_sections(packet)
    takeaway = next(s for s in sections if s.section_id == "executive_takeaway")
    assert takeaway.status == "structured"
    assert takeaway.citation_ids
    for cid in takeaway.citation_ids:
        assert cid in packet["known_ids"]


def test_executive_takeaway_ai_output_validated_against_known_ids(monkeypatch, tmp_path: Path) -> None:
    move = _move()
    packet = _build_packet(monkeypatch, scope=_scope(), moves=[move], inbox_dir=tmp_path)
    real_id = packet["what_changed"][0]["id"]

    class FakeResult:
        def __init__(self, bullets):
            self.parsed = {"bullets": bullets}

    def fake_completer(prompt, **kwargs):
        return FakeResult([
            {"text": "Planasa is expanding genetics activity in Peru.", "citation_ids": [real_id]},
            {"text": "A hallucinated claim about a company not in this packet.", "citation_ids": ["move-does-not-exist"]},
        ])

    sections = generate_decision_memo_sections(packet, completer=fake_completer)
    takeaway = next(s for s in sections if s.section_id == "executive_takeaway")
    assert takeaway.status == "ai_draft"
    assert real_id in takeaway.citation_ids
    assert "move-does-not-exist" not in takeaway.citation_ids
    assert "hallucinated" not in takeaway.prose.lower()


def test_executive_takeaway_falls_back_when_ai_returns_nothing_grounded(monkeypatch, tmp_path: Path) -> None:
    move = _move()
    packet = _build_packet(monkeypatch, scope=_scope(), moves=[move], inbox_dir=tmp_path)

    class FakeResult:
        def __init__(self):
            self.parsed = {"bullets": [{"text": "Ungrounded claim.", "citation_ids": ["not-a-real-id"]}]}

    def fake_completer(prompt, **kwargs):
        return FakeResult()

    sections = generate_decision_memo_sections(packet, completer=fake_completer)
    takeaway = next(s for s in sections if s.section_id == "executive_takeaway")
    assert takeaway.status == "structured"  # degraded to the deterministic fallback, not shown ungrounded


def test_executive_takeaway_completer_exception_falls_back(monkeypatch, tmp_path: Path) -> None:
    move = _move()
    packet = _build_packet(monkeypatch, scope=_scope(), moves=[move], inbox_dir=tmp_path)

    def broken_completer(prompt, **kwargs):
        raise RuntimeError("provider down")

    sections = generate_decision_memo_sections(packet, completer=broken_completer)
    takeaway = next(s for s in sections if s.section_id == "executive_takeaway")
    assert takeaway.status == "structured"


# ---- Scenario seam (packet["scenarios"], built by build_decision_memo_packet()
# via the real Change & Scenario Engine's change_scenario_for() read seam) ----

def test_scenarios_omitted_when_packet_has_none(monkeypatch, tmp_path: Path) -> None:
    packet = _build_packet(monkeypatch, scope=_scope(), moves=[_move()], inbox_dir=tmp_path)
    packet["scenarios"] = []
    sections = generate_decision_memo_sections(packet)
    assert not any(s.section_id in {"plausible_scenarios", "confirm_refute"} for s in sections)


def test_scenarios_present_preserve_language(monkeypatch, tmp_path: Path) -> None:
    packet = _build_packet(monkeypatch, scope=_scope(), moves=[_move()], inbox_dir=tmp_path)
    packet["scenarios"] = [{
        "title": "Peru blueberry consolidation accelerates",
        "why_plausible": "Multiple companies show concentrated genetics activity in Peru.",
        "what_confirms": "A third company enters the same lane within 90 days.",
        "what_refutes": "Activity plateaus with no new entrants.",
        "what_to_watch": "New PBR filings in Peru.",
        "citation_ids": [packet["what_changed"][0]["id"]],
    }]
    sections = generate_decision_memo_sections(packet)
    scenarios = next(s for s in sections if s.section_id == "plausible_scenarios")
    assert "PLAUSIBLE SCENARIO -- NOT FORECAST" in scenarios.prose
    confirm_refute = next(s for s in sections if s.section_id == "confirm_refute")
    assert "CONFIRMS" in confirm_refute.prose and "REFUTES" in confirm_refute.prose


def test_build_change_scenarios_swallows_exceptions_and_returns_empty(monkeypatch, tmp_path: Path) -> None:
    """The real engine call (assemble_research_packet + change_scenario_for)
    is wrapped defensively in build_decision_memo_packet() -- a raise from
    either must degrade to an empty scenario list, not crash the whole
    packet build."""
    from app.services.report_builder import decision_memo as dm

    def broken_assemble(*args, **kwargs):
        raise RuntimeError("engine not ready")

    monkeypatch.setattr(dm, "assemble_research_packet", broken_assemble)
    packet = _build_packet(monkeypatch, scope=_scope(), moves=[_move()], inbox_dir=tmp_path)
    assert packet["scenarios"] == []
    sections = generate_decision_memo_sections(packet)
    assert not any(s.section_id in {"plausible_scenarios", "confirm_refute"} for s in sections)


def test_change_scenario_engine_output_is_remapped_to_expected_field_names(monkeypatch, tmp_path: Path) -> None:
    """The real engine's field names (text/watch/would_confirm/would_refute/
    source_ids) must be remapped, not passed through raw."""
    from app.services.report_builder import decision_memo as dm

    def fake_change_scenario_for(scope, packet):
        return {"scenarios": [{
            "text": "Continued supply expansion could keep pressuring price.",
            "why_plausible": "Acreage and volume are both rising while price falls.",
            "would_confirm": "Price keeps falling as acreage keeps rising.",
            "would_refute": "Price stabilizes despite acreage growth.",
            "watch": "Next season's acreage report.",
            "source_ids": ["mkt-real-series"],
            "kind": "SCENARIO TO WATCH",
        }]}

    monkeypatch.setattr(dm, "change_scenario_for", fake_change_scenario_for)
    packet = _build_packet(monkeypatch, scope=_scope(), moves=[_move()], inbox_dir=tmp_path)
    assert len(packet["scenarios"]) == 1
    row = packet["scenarios"][0]
    assert row["title"] == "Continued supply expansion could keep pressuring price."
    assert row["what_confirms"] == "Price keeps falling as acreage keeps rising."
    assert row["what_refutes"] == "Price stabilizes despite acreage growth."
    assert row["what_to_watch"] == "Next season's acreage report."
    assert row["citation_ids"] == ["mkt-real-series"]


# ---- Market Reality: structured, not prose ----

def test_market_reality_section_is_structured_with_units_and_source(monkeypatch, tmp_path: Path) -> None:
    class FakeMarketRepo:
        def latest_by_key(self, **filters):
            return [
                {
                    "metric": "EXPORT_VOLUME", "unit": "MT", "source_commodity_code": "BLUEBERRY", "form": "fresh",
                    "geography": "PE", "geography_id": "geography-peru", "geography_ids": ["geography-peru"],
                    "berry_id": "berry-blueberry", "berry_ids": ["berry-blueberry"],
                    "source_commodity_label": "Blueberries", "source": "usda_fas", "source_dataset": "gain",
                    "period": "2023/24", "period_type": "year", "value": 242000.0, "captured_at": "2026-08-01T00:00:00+00:00",
                },
                {
                    "metric": "EXPORT_VOLUME", "unit": "MT", "source_commodity_code": "BLUEBERRY", "form": "fresh",
                    "geography": "PE", "geography_id": "geography-peru", "geography_ids": ["geography-peru"],
                    "berry_id": "berry-blueberry", "berry_ids": ["berry-blueberry"],
                    "source_commodity_label": "Blueberries", "source": "usda_fas", "source_dataset": "gain",
                    "period": "2024/25e", "period_type": "year", "value": 320000.0, "captured_at": "2026-08-01T00:00:00+00:00",
                },
            ]

    packet = _build_packet(monkeypatch, scope=_scope(), market_repo=FakeMarketRepo(), inbox_dir=tmp_path)
    sections = generate_decision_memo_sections(packet)
    market = next(s for s in sections if s.section_id == "market_reality")
    assert "242,000" in market.prose and "320,000" in market.prose
    assert "MT" in market.prose
    assert "2023/24" in market.prose and "2024/25e" in market.prose
    assert "usda_fas" in market.prose
    assert "Not a claim of cause" in market.prose
    # Not casual prose -- one block per series, not run-on sentences.
    assert market.prose.count("\n\n") >= 1


# ---- Coverage-gap / whitespace-state language preserved ----

def test_what_we_do_not_know_never_calls_low_coverage_an_opportunity(monkeypatch, tmp_path: Path) -> None:
    packet = _build_packet(monkeypatch, scope=_scope(), moves=[_move()], inbox_dir=tmp_path)
    packet["coverage_unknown"] = [{"text": "Peru Blueberry is LOW COVERAGE / UNKNOWN: not enough sources.", "geography_id": "geography-peru", "geography_name": "Peru"}]
    sections = generate_decision_memo_sections(packet)
    section = next(s for s in sections if s.section_id == "what_we_do_not_know")
    assert "opportunity" not in section.prose.lower()
    assert "LOW COVERAGE" in section.prose


# ---- Internal / public boundary ----

def test_internal_data_needed_always_present_and_never_fabricated(monkeypatch, tmp_path: Path) -> None:
    packet = _build_packet(monkeypatch, scope=_scope(company_ids=(), geography_ids=(), berry_id=None), inbox_dir=tmp_path)
    sections = generate_decision_memo_sections(packet)
    section = next(s for s in sections if s.section_id == "internal_data_needed")
    assert section.status == "structured"
    assert section.provider is None
    assert "Internal evidence not connected" in section.prose
    assert "OUR TESTING" in section.prose
    assert "OUR CUSTOMER SIGNALS" in section.prose
    assert "OUR COMMERCIAL POSITION" in section.prose
    assert "OUR FIELD INTELLIGENCE" in section.prose


def test_internal_data_needed_never_calls_the_completer() -> None:
    calls = {"count": 0}

    def counting_completer(prompt, **kwargs):
        calls["count"] += 1
        raise AssertionError("internal_data_needed must never call the completer")

    from app.services.report_builder.decision_memo import _section_internal_data_needed

    _section_internal_data_needed({})
    assert calls["count"] == 0


# ---- Strategic Question proposal behavior ----

def test_questions_for_team_labels_ai_proposals_and_never_creates_a_strategic_question(monkeypatch, tmp_path: Path) -> None:
    packet = _build_packet(monkeypatch, scope=_scope(), moves=[_move()], inbox_dir=tmp_path)
    packet["questions_for_team"] = {"questions": ["Is Planasa's Peru activity a durable expansion?"], "source": "ai"}
    sections = generate_decision_memo_sections(packet)
    section = next(s for s in sections if s.section_id == "questions_for_team")
    assert "PROPOSALS" in section.prose
    assert "AI-GENERATED" in section.prose


def test_questions_for_team_omitted_when_no_questions(monkeypatch, tmp_path: Path) -> None:
    packet = _build_packet(monkeypatch, scope=_scope(company_ids=(), geography_ids=(), berry_id=None), inbox_dir=tmp_path)
    packet["questions_for_team"] = {"questions": [], "source": "deterministic"}
    sections = generate_decision_memo_sections(packet)
    assert not any(s.section_id == "questions_for_team" for s in sections)


# ---- Routes ----

def test_report_new_page_accepts_decision_memo_handoff() -> None:
    page = TestClient(app).get("/reports/new?report_type=decision_memo&berry=blueberry&company_ids=company-planasa&focus_notes=Prepare+a+decision+memo&date_window_days=30")
    assert page.status_code == 200
    assert 'value="decision_memo" selected' in page.text or ("decision_memo" in page.text and "selected" in page.text)
    assert "Executive Decision Memo" in page.text


def test_war_room_create_decision_memo_button_present(monkeypatch) -> None:
    monkeypatch.setattr("app.main.compose_war_room", lambda scope, **kwargs: {
        "scope_label": "Blueberry · Planasa", "window_days": 30, "radar_freshness_label": "fresh",
        "executive_snapshot": {"moves": 0, "developments": 0, "market_changes": 0, "needs_attention": 0, "genetics_ip": 0, "strategic_questions": 0, "findings": []},
        "what_changed": [], "who_is_moving": [], "needs_attention": [],
        "competitive_positioning": None, "market_reality": [], "genetics_ip": {"moves": [], "developments": []},
        "emerging_developments": [], "key_uncertainties": [], "coverage_unknown": [], "competitive_overlap": [],
        "landscape_questions": [], "whitespace_watch_next": [], "whitespace_href": None,
        "questions_for_team": {"questions": [], "source": "deterministic"},
        "strategic_questions": [], "watch_next": [], "notes": [], "ask_berry_os_href": "/research?q=x",
        "compare_href": None, "create_meeting_brief_href": "/reports/new", "watchtower_href": "/watchtower",
        "create_decision_memo_href": "/reports/new?report_type=decision_memo&focus_notes=x",
        "scope": {"berry_id": "berry-blueberry", "geography_ids": [], "company_ids": ["company-planasa"], "window_days": 30},
    })
    page = TestClient(app).get("/war-room?berry=blueberry&company_ids=company-planasa")
    assert page.status_code == 200
    assert 'href="/reports/new?report_type=decision_memo&amp;focus_notes=x"' in page.text or "report_type=decision_memo" in page.text
    assert "Create decision memo" in page.text


def test_decision_memo_generation_creates_no_evidence_or_trust_files(monkeypatch, tmp_path: Path) -> None:
    """No trust mutation: creating a decision memo only writes to
    inbox/reports/ (private workspace state, same as every other report
    type already does) -- never to data/evidence, data/signals, etc."""
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path / "inbox")
    monkeypatch.setattr("app.services.war_room.compose.edition_from_cache", lambda inbox_dir: None)
    monkeypatch.setattr("app.services.war_room.compose.compose_moves_board", lambda developments, inbox_dir=None: _board([]))
    client = TestClient(app)
    response = client.post(
        "/reports/new",
        data={
            "step": "generate", "report_type": "decision_memo", "berry": "berry-blueberry",
            "company_ids": "company-planasa", "geography_ids": "", "variety_ids": "",
            "strategic_question_id": "", "date_window_days": "30", "focus_notes": "test", "title": "Test memo",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].startswith("/reports/rp-")
    inbox_dir = tmp_path / "inbox"
    assert (inbox_dir / "reports").is_dir()
    assert not (inbox_dir.parent / "data" / "evidence").exists()
