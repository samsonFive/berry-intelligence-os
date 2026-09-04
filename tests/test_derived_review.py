"""Analyst review of DERIVED intelligence objects -- Analyst Dogfood Loop
Phase 4.

A challenge to a derived object (Radar Development, Competitive Move,
Watchtower Alert, Decision Memo section) is analyst feedback on an
INTERPRETATION, never a mutation of Evidence/Signal/Assessment trust
state. These tests check the four-action vocabulary, review-event
traceability, idempotent-but-notes-aware retry behavior, and that
nothing here touches any other trust store.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main
from app.main import app
from app.services.analyst_queue import apply_action, load_state
from app.services.derived_review import (
    present_derived_review,
    section_review_key,
    source_review_href,
)
from app.services.review_events import load_review_events


def _isolate(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path / "inbox")


# ---- Vocabulary / state machine ----

def test_confirm_dispute_defer_dismiss_are_distinct_states(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    assert apply_action(inbox, dimension="derived_review", item_id="dev-1", action="confirm", object_type="radar_development", reviewer="analyst") == "confirmed"
    assert apply_action(inbox, dimension="derived_review", item_id="move-1", action="dispute", object_type="competitive_move", reviewer="analyst") == "disputed"
    assert apply_action(inbox, dimension="derived_review", item_id="wta-1", action="defer", object_type="watchtower_alert", reviewer="analyst") == "deferred"
    assert apply_action(inbox, dimension="derived_review", item_id="rep-1:genetics_ip", action="dismiss", object_type="decision_memo_section", reviewer="analyst") == "dismissed"


def test_unknown_action_raises() -> None:
    with pytest.raises(ValueError):
        apply_action(Path("unused"), dimension="derived_review", item_id="dev-1", action="approve", object_type="radar_development")


def test_unknown_object_type_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        apply_action(tmp_path / "inbox", dimension="derived_review", item_id="dev-1", action="confirm", object_type="not_a_real_type")


def test_no_edit_action_exists_in_the_vocabulary() -> None:
    """Mission: edit vocabulary is not invented merely for symmetry --
    a Decision Memo section keeps using its own existing Save/Regenerate
    route instead."""
    from app.services.analyst_queue import DERIVED_REVIEW_ACTIONS

    assert "edit" not in DERIVED_REVIEW_ACTIONS
    assert set(DERIVED_REVIEW_ACTIONS) == {"confirm", "dispute", "defer", "dismiss"}


# ---- Traceability: state store + append-only review event ----

def test_notes_and_reason_persist_in_state_and_review_event(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    apply_action(
        inbox, dimension="derived_review", item_id="dev-inka", action="dispute",
        object_type="radar_development", reviewer="analyst-1",
        notes="Geography looks wrong -- this is a Peru story.", reason_category="wrong_scope",
    )
    state = load_state(inbox)
    entry = state["derived_review"]["dev-inka"]
    assert entry["state"] == "disputed"
    assert entry["object_type"] == "radar_development"
    assert entry["review_notes"] == "Geography looks wrong -- this is a Peru story."
    assert entry["reason_category"] == "wrong_scope"
    assert entry["reviewer"] == "analyst-1"

    events = load_review_events(inbox, workflow="derived_object_review")
    assert len(events) == 1
    event = events[0]
    assert event["object_id"] == "dev-inka"
    assert event["object_type"] == "radar_development"
    assert event["action"] == "dispute"
    assert event["prior_state"] == "unreviewed"
    assert event["new_state"] == "disputed"
    assert event["notes"] == "Geography looks wrong -- this is a Peru story."
    assert event["reason_category"] == "wrong_scope"
    # Do not duplicate the full underlying object into the audit event.
    assert "title" not in event and "what_happened" not in event


def test_resubmitting_identical_action_and_notes_is_a_true_no_op(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    apply_action(inbox, dimension="derived_review", item_id="move-1", action="confirm", object_type="competitive_move", reviewer="a", notes="looks right")
    apply_action(inbox, dimension="derived_review", item_id="move-1", action="confirm", object_type="competitive_move", reviewer="a", notes="looks right")
    events = load_review_events(inbox, workflow="derived_object_review")
    assert len(events) == 1


def test_resubmitting_same_action_with_new_notes_updates_current_state_and_appends_event(tmp_path: Path) -> None:
    """Unlike the other six analyst_queue dimensions (no meaningful free
    text), a derived-review re-submission with DIFFERENT notes must not be
    silently swallowed as a no-op -- the analyst is adding real content."""
    inbox = tmp_path / "inbox"
    apply_action(inbox, dimension="derived_review", item_id="wta-1", action="dispute", object_type="watchtower_alert", reviewer="a", notes="first pass, unsure")
    apply_action(inbox, dimension="derived_review", item_id="wta-1", action="dispute", object_type="watchtower_alert", reviewer="a", notes="confirmed: source does not support this")
    state = load_state(inbox)
    assert state["derived_review"]["wta-1"]["review_notes"] == "confirmed: source does not support this"
    events = load_review_events(inbox, workflow="derived_object_review")
    assert len(events) == 2


def test_supporting_ids_and_origin_href_are_recorded_when_available(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    apply_action(
        inbox, dimension="derived_review", item_id="rep-9:plausible_scenarios", action="dispute",
        object_type="decision_memo_section", reviewer="a", notes="overstated",
        reason_category="overstated", supporting_ids=("dev-1", "move-2"), origin_href="/reports/rep-9",
    )
    event = load_review_events(inbox, workflow="derived_object_review")[0]
    assert event["supporting_ids"] == ["dev-1", "move-2"]
    assert event["origin_href"] == "/reports/rep-9"


# ---- Trust boundary ----

def test_derived_review_never_writes_to_any_other_trust_store(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    (inbox / "evidence").mkdir(parents=True)
    (inbox / "evidence" / "ev-1.json").write_text(json.dumps({"id": "ev-1"}), encoding="utf-8")
    before = (inbox / "evidence" / "ev-1.json").read_text(encoding="utf-8")

    apply_action(inbox, dimension="derived_review", item_id="dev-1", action="dispute", object_type="radar_development", reviewer="a", notes="wrong geography")

    after = (inbox / "evidence" / "ev-1.json").read_text(encoding="utf-8")
    assert before == after
    # Only the shared queue-state file and this workflow's own review-event
    # ledger were written -- no signals/assessments directories appeared.
    assert not (inbox / "signals").exists()
    assert not (inbox / "assessments").exists()
    assert (inbox / "analyst_queue_state.json").is_file()
    assert (inbox / "review_events" / "derived_object_review").is_dir()


# ---- Presentation helpers ----

def test_section_review_key_is_composite_since_section_ids_repeat_across_reports() -> None:
    assert section_review_key("rep-1", "genetics_ip") == "rep-1:genetics_ip"
    assert section_review_key("rep-2", "genetics_ip") == "rep-2:genetics_ip"


def test_source_review_href_uses_first_trusted_context_href_when_present() -> None:
    assert source_review_href([{"href": "/evidence/ev-1", "kind": "TRUSTED EVIDENCE"}]) == "/evidence/ev-1"
    assert source_review_href([]) is None
    assert source_review_href(None) is None


def test_present_derived_review_defaults_to_unreviewed(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    payload = present_derived_review(
        "dev-never-touched", object_type="radar_development", state=load_state(inbox), return_to="/radar/dev-never-touched",
    )
    assert payload["state"] == "unreviewed"
    assert payload["label"] == "Unreviewed"
    assert payload["review_notes"] == ""
    assert payload["reviewer"] == ""


def test_present_derived_review_reflects_a_recorded_dispute(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    apply_action(inbox, dimension="derived_review", item_id="dev-2", action="dispute", object_type="radar_development", reviewer="analyst-2", notes="wrong scope", reason_category="wrong_scope")
    payload = present_derived_review("dev-2", object_type="radar_development", state=load_state(inbox), return_to="/radar/dev-2")
    assert payload["state"] == "disputed"
    assert payload["label"] == "Disputed"
    assert payload["review_notes"] == "wrong scope"
    assert payload["reason_category_label"] == "Wrong scope"
    assert payload["reviewer"] == "analyst-2"


# ---- Route ----

def test_route_records_a_review_and_redirects(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    client = TestClient(app)
    response = client.post(
        "/derived-review/watchtower_alert/wta-route-1",
        data={"action": "confirm", "review_notes": "agree", "return_to": "/watchtower"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/watchtower"
    state = load_state(tmp_path / "inbox")
    assert state["derived_review"]["wta-route-1"]["state"] == "confirmed"
    assert state["derived_review"]["wta-route-1"]["review_notes"] == "agree"


def test_route_rejects_unknown_object_type(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    client = TestClient(app)
    response = client.post(
        "/derived-review/not_a_real_type/item-1",
        data={"action": "confirm"},
        follow_redirects=False,
    )
    assert response.status_code == 404
