"""Strategic Watchtower + Actionable Alerts V1.

An alert is a notification wrapper, never a truth promotion -- these tests
check deterministic trigger matching, idempotent/restart-safe persistence,
read/dismiss/snooze state independent of trust state, and that nothing
here ever mutates Evidence/Signal/Assessment.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main
from app.main import app
from app.services.competitive_moves.models import CompanyPattern, CompetitiveMove, MovesBoard
from app.services.emerging_radar.models import Development, SourceRef
from app.services.watchtower.digest import build_digest
from app.services.watchtower.generate import MARKET_CHANGE_THRESHOLD_PCT, generate_alerts
from app.services.watchtower.present import present_watchtower
from app.services.watchtower.store import apply_alert_action, load_alert_state, load_alerts, persist_alerts

NOW = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)

ENTITIES = {
    "company-planasa": {"id": "company-planasa", "entity_type": "company", "name": "Planasa"},
    "company-hortifrut": {"id": "company-hortifrut", "entity_type": "company", "name": "Hortifrut S.A."},
}
BERRY_LABELS = {"berry-blueberry": "Blueberry", "berry-strawberry": "Strawberry"}


def _source(url="https://example.com/a", official=False, registry=False) -> SourceRef:
    return SourceRef(
        url=url, title="A story", publisher="Example News", domain="example.com",
        published_date="2026-08-28", provider="google_news_rss", query_id="q1",
        official=official, registry=registry,
    )


def _development(**overrides) -> Development:
    base = dict(
        id="dev-planasa-leadership",
        title="Planasa appoints new global innovation leader",
        event_type="LEADERSHIP",
        what_happened="Planasa named a new global head of innovation.",
        first_seen="2026-08-28T09:00:00+00:00",
        latest_update="2026-08-28T09:00:00+00:00",
        event_date="2026-08-28",
        company_ids=("company-planasa",),
        company_names=("Planasa",),
        geography_ids=(),
        berry_ids=("berry-strawberry",),
        sources=[_source()],
        status="emerging",
        corroboration="ONE SOURCE",
    )
    base.update(overrides)
    return Development(**base)


def _empty_board(**overrides) -> MovesBoard:
    base = dict(
        generated_at=NOW.isoformat(), freshness_label="fresh", cache_status="fresh",
        trust_label="LIVE / UNREVIEWED MOVE", moves=[], patterns=[], momentum=[],
        sections=[], featured_timeline=None, stats={},
    )
    base.update(overrides)
    return MovesBoard(**base)


def _move(**overrides) -> CompetitiveMove:
    base = dict(
        id="move-planasa-genetics",
        company_id="company-planasa",
        company_name="Planasa",
        move_type="GENETICS_LAUNCH",
        title="Planasa launches new strawberry variety",
        what_happened="Planasa launched a new commercial strawberry variety in Spain.",
        why_move=("Canonical competitor named", "Classified from VARIETY_LAUNCH", "Geography named: Spain"),
        first_seen="2026-08-29T09:00:00+00:00",
        latest_update="2026-08-29T09:00:00+00:00",
        geography_ids=("geography-spain",),
        geography_labels=("Spain",),
        berry_ids=("berry-strawberry",),
    )
    base.update(overrides)
    return CompetitiveMove(**base)


class FakeMarketRepo:
    def __init__(self, rows) -> None:
        self.rows = rows

    def latest_by_key(self, **filters):
        out = list(self.rows)
        if filters.get("berry_id"):
            out = [row for row in out if row.get("berry_id") == filters["berry_id"]]
        if filters.get("geography_id"):
            out = [row for row in out if row.get("geography_id") == filters["geography_id"]]
        return out


def _market_rows(pct_change_setup=True):
    if pct_change_setup:
        return [
            {
                "metric": "EXPORT_VOLUME", "unit": "t", "source_commodity_code": "BLUEBERRY", "form": "fresh",
                "geography": "PE", "geography_id": "geography-peru", "geography_ids": ["geography-peru"],
                "berry_id": "berry-blueberry", "berry_ids": ["berry-blueberry"],
                "source_commodity_label": "Blueberries", "source": "usda-fas", "source_dataset": "gain",
                "period": "2023/24", "period_type": "year", "value": 100.0, "captured_at": "2026-08-01T00:00:00+00:00",
            },
            {
                "metric": "EXPORT_VOLUME", "unit": "t", "source_commodity_code": "BLUEBERRY", "form": "fresh",
                "geography": "PE", "geography_id": "geography-peru", "geography_ids": ["geography-peru"],
                "berry_id": "berry-blueberry", "berry_ids": ["berry-blueberry"],
                "source_commodity_label": "Blueberries", "source": "usda-fas", "source_dataset": "gain",
                "period": "2024/25", "period_type": "year", "value": 132.2, "captured_at": "2026-08-01T00:00:00+00:00",
            },
        ]
    return []


def _generate(**kwargs):
    defaults = dict(
        watches=[], developments=[], board=_empty_board(), market_repo=None,
        published_evidence=[], strategic_questions=[], entities=ENTITIES, berry_labels=BERRY_LABELS, now=NOW,
    )
    defaults.update(kwargs)
    return generate_alerts(**defaults)


# ---- Watch matching / trigger families ----

def test_new_development_requires_a_watch_match() -> None:
    dev = _development()
    unwatched = _generate(developments=[dev], watches=[{"watch_type": "company", "object_id": "company-hortifrut"}])
    assert unwatched == []
    watched = _generate(developments=[dev], watches=[{"watch_type": "company", "object_id": "company-planasa"}])
    assert any(a.trigger_type == "NEW_DEVELOPMENT" for a in watched)


def test_new_development_matches_berry_watch() -> None:
    dev = _development(berry_ids=("berry-blueberry",))
    alerts = _generate(developments=[dev], watches=[{"watch_type": "berry", "object_id": "berry-blueberry"}])
    assert any(a.trigger_type == "NEW_DEVELOPMENT" and a.subject_type == "berry" for a in alerts)


def test_weak_signal_without_corroboration_does_not_alert() -> None:
    dev = _development(status="weak_signal", independent_source_count=0)
    alerts = _generate(developments=[dev], watches=[{"watch_type": "company", "object_id": "company-planasa"}])
    assert alerts == []


def test_development_outside_recency_window_does_not_alert() -> None:
    dev = _development(event_date="2025-01-01", latest_update="2025-01-01T00:00:00+00:00", first_seen="2025-01-01T00:00:00+00:00")
    alerts = _generate(developments=[dev], watches=[{"watch_type": "company", "object_id": "company-planasa"}])
    assert alerts == []


def test_development_updated_upserts_same_id_as_new_development_alert_but_distinct_row() -> None:
    from app.services.emerging_radar.models import EvolutionEvent

    dev = _development(evolution=[EvolutionEvent(at="2026-08-28", kind="FIRST_SEEN", detail="x"), EvolutionEvent(at="2026-08-29", kind="NEW_SOURCE", detail="A second outlet covered this.")])
    alerts = _generate(developments=[dev], watches=[{"watch_type": "company", "object_id": "company-planasa"}])
    triggers = {a.trigger_type for a in alerts}
    assert "NEW_DEVELOPMENT" in triggers
    assert "DEVELOPMENT_UPDATED" in triggers
    ids = {a.id for a in alerts}
    assert len(ids) == len(alerts)  # distinct rows, not collapsed


def test_pbr_and_patent_event_types_produce_distinct_trigger_alerts() -> None:
    pbr = _development(id="dev-pbr", event_type="PBR")
    patent = _development(id="dev-patent", event_type="PATENT")
    alerts = _generate(developments=[pbr, patent], watches=[{"watch_type": "company", "object_id": "company-planasa"}])
    triggers = {a.trigger_type for a in alerts}
    assert "NEW_PBR_RIGHTS_EVENT" in triggers
    assert "NEW_PATENT_IP_EVENT" in triggers


def test_new_competitive_move_requires_watch_match() -> None:
    move = _move()
    board = _empty_board(moves=[move])
    unwatched = _generate(board=board, watches=[{"watch_type": "company", "object_id": "company-hortifrut"}])
    assert unwatched == []
    watched = _generate(board=board, watches=[{"watch_type": "company", "object_id": "company-planasa"}])
    assert any(a.trigger_type == "NEW_COMPETITIVE_MOVE" for a in watched)


def test_move_type_watch_matches_moves_of_that_type() -> None:
    move = _move(move_type="GENETICS_LAUNCH")
    board = _empty_board(moves=[move])
    alerts = _generate(board=board, watches=[{"watch_type": "move_type", "object_id": "GENETICS_LAUNCH"}])
    assert any(a.trigger_type == "NEW_COMPETITIVE_MOVE" and a.subject_type == "move_type" for a in alerts)
    none = _generate(board=board, watches=[{"watch_type": "move_type", "object_id": "LEADERSHIP"}])
    assert none == []


def test_new_competitive_move_reasons_include_moves_own_why_move() -> None:
    move = _move()
    board = _empty_board(moves=[move])
    alerts = _generate(board=board, watches=[{"watch_type": "company", "object_id": "company-planasa"}])
    alert = next(a for a in alerts if a.trigger_type == "NEW_COMPETITIVE_MOVE")
    assert any(reason in alert.why_triggered for reason in move.why_move)


def test_repeated_move_pattern_requires_company_watch() -> None:
    pattern = CompanyPattern(
        company_id="company-planasa", company_name="Planasa", theme="GENETICS / COMMERCIALIZATION",
        label="REPEATED MOVE PATTERN", supporting_move_types=("GENETICS_LAUNCH", "LICENSING"),
        supporting_move_ids=("move-1", "move-2"), why="Planasa has 2 supporting moves.",
        latest_update="2026-08-29T09:00:00+00:00", move_count=2,
    )
    board = _empty_board(patterns=[pattern])
    alerts = _generate(board=board, watches=[{"watch_type": "company", "object_id": "company-planasa"}])
    assert any(a.trigger_type == "REPEATED_MOVE_PATTERN" for a in alerts)


def test_market_reality_change_below_threshold_does_not_alert() -> None:
    repo = FakeMarketRepo(_market_rows())
    alerts = _generate(market_repo=repo, watches=[{"watch_type": "geography", "object_id": "geography-peru"}], market_threshold_pct=100.0)
    assert alerts == []


def test_market_reality_change_above_threshold_alerts_matching_geography() -> None:
    repo = FakeMarketRepo(_market_rows())
    alerts = _generate(market_repo=repo, watches=[{"watch_type": "geography", "object_id": "geography-peru"}], market_threshold_pct=MARKET_CHANGE_THRESHOLD_PCT)
    assert any(a.trigger_type == "MARKET_REALITY_CHANGE" for a in alerts)
    # a different geography watch must not pick up Peru's numbers
    other = _generate(market_repo=repo, watches=[{"watch_type": "geography", "object_id": "geography-spain"}], market_threshold_pct=MARKET_CHANGE_THRESHOLD_PCT)
    assert other == []


def test_market_reality_change_never_claims_statistical_significance() -> None:
    repo = FakeMarketRepo(_market_rows())
    alerts = _generate(market_repo=repo, watches=[{"watch_type": "berry", "object_id": "berry-blueberry"}])
    alert = next(a for a in alerts if a.trigger_type == "MARKET_REALITY_CHANGE")
    combined = " ".join(alert.why_triggered).lower() + alert.title.lower()
    assert "significant" not in combined and "statistically" not in combined


def test_new_trusted_evidence_matches_watched_entity() -> None:
    evidence = [{"id": "ev-1", "title": "Planasa expands nursery capacity", "entity_ids": ["company-planasa"], "geography_ids": [], "berry_ids": [], "published_date": "2026-08-30"}]
    alerts = _generate(published_evidence=evidence, watches=[{"watch_type": "company", "object_id": "company-planasa"}])
    assert any(a.trigger_type == "NEW_TRUSTED_EVIDENCE" and a.trust_state == "REVIEWED EVIDENCE" for a in alerts)


def test_watched_strategic_question_match_from_evidence() -> None:
    evidence = [{"id": "ev-2", "title": "Peru blueberry exports rise", "entity_ids": [], "geography_ids": [], "berry_ids": [], "strategic_question_ids": ["sq-peru-expansion"], "published_date": "2026-08-30"}]
    questions = [{"id": "sq-peru-expansion", "title": "Is Peru blueberry expansion accelerating?"}]
    alerts = _generate(published_evidence=evidence, strategic_questions=questions, watches=[{"watch_type": "strategic_question", "object_id": "sq-peru-expansion"}])
    assert any(a.trigger_type == "WATCHED_STRATEGIC_QUESTION_MATCH" for a in alerts)


def test_watched_strategic_question_match_from_move() -> None:
    move = _move(strategic_questions=({"id": "sq-planasa-genetics", "title": "Is Planasa leading genetics?", "href": "/strategic-questions/sq-planasa-genetics"},))
    board = _empty_board(moves=[move])
    alerts = _generate(board=board, watches=[{"watch_type": "strategic_question", "object_id": "sq-planasa-genetics"}])
    assert any(a.trigger_type == "WATCHED_STRATEGIC_QUESTION_MATCH" and a.related_move_id == move.id for a in alerts)


def test_priority_is_transparent_reasons_not_a_score() -> None:
    dev = _development(corroboration="MULTIPLE INDEPENDENT SOURCES", sources=[_source(official=True)], geography_ids=("geography-spain",))
    alerts = _generate(developments=[dev], watches=[{"watch_type": "company", "object_id": "company-planasa"}])
    alert = next(a for a in alerts if a.trigger_type == "NEW_DEVELOPMENT")
    assert alert.priority in {"HIGH ATTENTION", "ATTENTION", "FYI"}
    assert len(alert.priority_reasons) >= 1
    assert all(isinstance(r, str) and r for r in alert.priority_reasons)


def test_ask_berry_os_href_never_carries_raw_body_text() -> None:
    dev = _development(what_happened="CONFIDENTIAL BODY TEXT SHOULD NOT LEAK")
    alerts = _generate(developments=[dev], watches=[{"watch_type": "company", "object_id": "company-planasa"}])
    alert = next(a for a in alerts if a.trigger_type == "NEW_DEVELOPMENT")
    assert "CONFIDENTIAL BODY TEXT" not in alert.ask_berry_os_href
    assert alert.ask_berry_os_href.startswith("/research?q=")


# ---- Idempotency / persistence / restart-safety ----

def test_generate_alerts_is_idempotent_across_repeated_calls() -> None:
    dev = _development()
    watches = [{"watch_type": "company", "object_id": "company-planasa"}]
    first = {a.id for a in _generate(developments=[dev], watches=watches)}
    second = {a.id for a in _generate(developments=[dev], watches=watches)}
    assert first == second


def test_persist_alerts_preserves_first_generated_at_across_regeneration(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    dev = _development()
    watches = [{"watch_type": "company", "object_id": "company-planasa"}]
    first_alerts = _generate(developments=[dev], watches=watches, now=NOW)
    stored_first = persist_alerts(inbox, first_alerts)
    assert len(stored_first) == 1
    original_first_seen = stored_first[0]["first_generated_at"]

    later = datetime(2026, 9, 2, 13, 0, tzinfo=timezone.utc)
    second_alerts = _generate(developments=[dev], watches=watches, now=later)
    stored_second = persist_alerts(inbox, second_alerts)
    assert len(stored_second) == 1
    assert stored_second[0]["id"] == stored_first[0]["id"]
    assert stored_second[0]["first_generated_at"] == original_first_seen
    assert stored_second[0]["generated_at"] != stored_first[0]["generated_at"]


def test_persisted_alerts_survive_a_simulated_restart(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    dev = _development()
    watches = [{"watch_type": "company", "object_id": "company-planasa"}]
    persist_alerts(inbox, _generate(developments=[dev], watches=watches))
    # Simulate a process restart: a fresh read from disk, no in-memory state.
    reloaded = load_alerts(inbox)
    assert len(reloaded) == 1
    assert reloaded[0]["trigger_type"] == "NEW_DEVELOPMENT"


def test_regeneration_drops_alerts_whose_underlying_thing_left_the_cache(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    dev = _development()
    watches = [{"watch_type": "company", "object_id": "company-planasa"}]
    persist_alerts(inbox, _generate(developments=[dev], watches=watches))
    assert len(load_alerts(inbox)) == 1
    persist_alerts(inbox, _generate(developments=[], watches=watches))
    assert load_alerts(inbox) == []


# ---- Read / dismiss / snooze state, independent of trust ----

def test_alert_action_state_survives_restart_and_is_explicit_only(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    dev = _development()
    watches = [{"watch_type": "company", "object_id": "company-planasa"}]
    stored = persist_alerts(inbox, _generate(developments=[dev], watches=watches))
    alert_id = stored[0]["id"]
    assert load_alert_state(inbox) == {}  # never marked read by generation alone

    apply_alert_action(inbox, alert_id, "dismiss")
    state = load_alert_state(inbox)
    assert state[alert_id]["state"] == "dismissed"

    # A regeneration must not clear or reset the dismissal.
    persist_alerts(inbox, _generate(developments=[dev], watches=watches))
    assert load_alert_state(inbox)[alert_id]["state"] == "dismissed"


def test_alert_action_never_touches_evidence_or_trust_state(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    evidence = [{"id": "ev-3", "title": "Planasa update", "entity_ids": ["company-planasa"], "geography_ids": [], "berry_ids": [], "published_date": "2026-08-30"}]
    stored = persist_alerts(inbox, _generate(published_evidence=evidence, watches=[{"watch_type": "company", "object_id": "company-planasa"}]))
    alert_id = stored[0]["id"]
    apply_alert_action(inbox, alert_id, "dismiss")
    # The alert's own trust_state field (copied from the underlying record)
    # is untouched by the action -- dismissing an alert never rewrites the
    # thing it points at.
    reloaded = load_alerts(inbox)[0]
    assert reloaded["trust_state"] == "REVIEWED EVIDENCE"
    assert evidence[0].get("state") is None  # the source record was never mutated


def test_unsupported_alert_action_raises(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    try:
        apply_alert_action(inbox, "wta-doesnotexist", "delete_forever")
        raised = False
    except ValueError:
        raised = True
    assert raised


# ---- Digest / presenter ----

def test_digest_omits_dismissed_and_read_alerts_from_needs_attention() -> None:
    dev = _development()
    alerts = [a.as_dict() for a in _generate(developments=[dev], watches=[{"watch_type": "company", "object_id": "company-planasa"}])]
    for a in alerts:
        a["state"] = "dismissed"
    digest = build_digest(alerts)
    assert digest["total_open"] == 0
    assert digest["top_alerts"] == []


def test_present_watchtower_groups_by_trigger_family() -> None:
    dev = _development(event_type="PBR")
    alerts = [a.as_dict() for a in _generate(developments=[dev], watches=[{"watch_type": "company", "object_id": "company-planasa"}])]
    for a in alerts:
        a["state"] = "open"
    page = present_watchtower({"alerts": alerts, "digest": build_digest(alerts), "cache_status": "fresh", "radar_freshness_label": "fresh", "watch_count": 1, "watches": []})
    assert page["genetics_ip"]
    assert all(a["trigger_type"] == "NEW_PBR_RIGHTS_EVENT" for a in page["genetics_ip"])


# ---- Route rendering ----

def test_watchtower_page_renders_empty_state_with_no_watches(monkeypatch) -> None:
    monkeypatch.setattr(main, "_watchtower_cached", lambda: {
        "alerts": [], "digest": build_digest([]), "cache_status": "empty",
        "radar_freshness_label": "No Radar cache yet.", "watch_count": 0, "watches": [],
    })
    page = TestClient(app).get("/watchtower")
    assert page.status_code == 200
    assert "watching anything yet" in page.text


def test_watchtower_page_renders_alert_cards(monkeypatch) -> None:
    dev = _development()
    alerts = [a.as_dict() for a in _generate(developments=[dev], watches=[{"watch_type": "company", "object_id": "company-planasa"}])]
    for a in alerts:
        a["state"] = "open"
    monkeypatch.setattr(main, "_watchtower_cached", lambda: {
        "alerts": alerts, "digest": build_digest(alerts), "cache_status": "fresh",
        "radar_freshness_label": "fresh", "watch_count": 1, "watches": [],
    })
    page = TestClient(app).get("/watchtower")
    assert page.status_code == 200
    assert "Needs your attention" in page.text
    assert "Planasa appoints new global innovation leader" in page.text
    assert "Ask Berry OS about this" in page.text


def test_watchtower_alert_action_route_is_explicit_and_redirects(monkeypatch, tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    monkeypatch.setattr(main, "INBOX_DIR", inbox)
    dev = _development()
    stored = persist_alerts(inbox, _generate(developments=[dev], watches=[{"watch_type": "company", "object_id": "company-planasa"}]))
    alert_id = stored[0]["id"]
    response = TestClient(app).post(f"/watchtower/{alert_id}/action", data={"action": "mark_read", "return_to": "/watchtower"}, follow_redirects=False)
    assert response.status_code == 303
    assert load_alert_state(inbox)[alert_id]["state"] == "read"


def test_watchtower_alert_action_rejects_open_redirect(monkeypatch, tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    monkeypatch.setattr(main, "INBOX_DIR", inbox)
    dev = _development()
    stored = persist_alerts(inbox, _generate(developments=[dev], watches=[{"watch_type": "company", "object_id": "company-planasa"}]))
    alert_id = stored[0]["id"]
    response = TestClient(app).post(f"/watchtower/{alert_id}/action", data={"action": "mark_read", "return_to": "//evil.example.com"}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/watchtower"


def test_today_page_omits_needs_attention_section_when_no_open_alerts(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path / "inbox")
    main._WATCHTOWER_CACHE["value"] = None
    main._WATCHTOWER_CACHE["computed_at"] = 0.0
    page = TestClient(app).get("/today")
    assert page.status_code == 200
    assert "needs-your-attention" not in page.text


def test_today_page_shows_needs_attention_when_watchtower_has_open_alerts(monkeypatch) -> None:
    dev = _development()
    alerts = [a.as_dict() for a in _generate(developments=[dev], watches=[{"watch_type": "company", "object_id": "company-planasa"}])]
    for a in alerts:
        a["state"] = "open"
    monkeypatch.setattr(main, "load_watches", lambda inbox_dir: [{"watch_type": "company", "object_id": "company-planasa"}])
    monkeypatch.setattr(main, "_watchtower_cached", lambda: {
        "alerts": alerts, "digest": build_digest(alerts), "cache_status": "fresh",
        "radar_freshness_label": "fresh", "watch_count": 1, "watches": [],
    })
    page = TestClient(app).get("/today")
    assert page.status_code == 200
    assert "needs-your-attention" in page.text
    assert "Open Watchtower" in page.text


def test_watchtower_nav_entry_present() -> None:
    page = TestClient(app).get("/watches")
    assert page.status_code == 200
    assert 'href="/watchtower"' in page.text


def test_new_watch_types_are_accepted_end_to_end(monkeypatch, tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    monkeypatch.setattr(main, "INBOX_DIR", inbox)
    client = TestClient(app)
    berry_response = client.post("/watches/toggle", data={"watch_type": "berry", "object_id": "berry-blueberry", "action": "add", "return_to": "/watches"}, follow_redirects=False)
    assert berry_response.status_code == 303
    move_type_response = client.post("/watches/toggle", data={"watch_type": "move_type", "object_id": "GENETICS_LAUNCH", "action": "add", "return_to": "/watches"}, follow_redirects=False)
    assert move_type_response.status_code == 303
    from app.services.watchlist import load_watches

    watches = load_watches(inbox)
    types = {w["watch_type"] for w in watches}
    assert {"berry", "move_type"} <= types
