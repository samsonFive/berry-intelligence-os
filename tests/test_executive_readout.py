"""Executive Intelligence Readout V1 -- distinct from Morning Brief
(per-analyst triage) and Landscape (captured-competitive-environment
coverage): the most important trusted developments and analyst
interpretations to communicate upward. No fabricated interpretation --
absent Assessments/Signals render an honest empty state."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app import main
from app.main import app
from app.services.executive_readout import (
    NO_ASSESSMENT_MESSAGE,
    NO_SIGNAL_MESSAGE,
    caution,
    top_assessments,
    top_signals,
    what_changed,
    what_we_know,
)


def _evidence(**overrides):
    row = {
        "id": "ev-1",
        "title": "An article",
        "source_name": "Some Source",
        "source_type": "trade_press",
        "published_date": "2026-01-01",
    }
    row.update(overrides)
    return row


def _signal(**overrides):
    row = {"id": "sig-1", "title": "A signal", "strength": "moderate", "evidence_ids": ["ev-1"]}
    row.update(overrides)
    return row


def _assessment(**overrides):
    row = {"id": "as-1", "title": "An assessment", "confidence": "medium", "evidence_ids": [], "fact_ids": []}
    row.update(overrides)
    return row


# --- what_changed ---------------------------------------------------------


def test_what_changed_includes_records_in_window_excludes_older():
    from datetime import date, timedelta

    recent = (date.today() - timedelta(days=3)).isoformat()
    old = (date.today() - timedelta(days=90)).isoformat()
    evidence = [_evidence(id="ev-recent", published_date=recent), _evidence(id="ev-old", published_date=old)]
    result = what_changed(published_evidence=evidence, signals=[], assessments=[], window_days=14)
    ids = {row["id"] for row in result["rows"]}
    assert "ev-recent" in ids
    assert "ev-old" not in ids


def test_what_changed_preserves_distinct_kinds():
    from datetime import date

    today = date.today().isoformat()
    evidence = [_evidence(published_date=today)]
    signals = [_signal(first_seen=today)]
    assessments = [_assessment(created_at=today)]
    result = what_changed(published_evidence=evidence, signals=signals, assessments=assessments)
    kinds = {row["kind"] for row in result["rows"]}
    assert kinds == {"evidence", "signal", "assessment"}


def test_what_changed_sorted_newest_first_and_bounded():
    from datetime import date, timedelta

    evidence = [
        _evidence(id=f"ev-{i}", published_date=(date.today() - timedelta(days=i)).isoformat()) for i in range(20)
    ]
    result = what_changed(published_evidence=evidence, signals=[], assessments=[], limit=15)
    assert len(result["rows"]) == 15
    dates = [row["date"] for row in result["rows"]]
    assert dates == sorted(dates, reverse=True)


def test_what_changed_honest_empty_state():
    result = what_changed(published_evidence=[], signals=[], assessments=[])
    assert result["has_any"] is False
    assert result["rows"] == []


# --- top_signals / top_assessments -----------------------------------------


def test_top_signals_sorted_by_strength_then_evidence_count():
    signals = [
        _signal(id="weak", strength="weak", evidence_ids=["a", "b", "c"]),
        _signal(id="strong", strength="strong", evidence_ids=["a"]),
        _signal(id="moderate", strength="moderate", evidence_ids=["a", "b"]),
    ]
    result = top_signals(signals)
    assert [s["id"] for s in result] == ["strong", "moderate", "weak"]


def test_top_assessments_reviewed_before_ai_proposed():
    assessments = [
        _assessment(id="ai", ai_proposed=True, confidence="high"),
        _assessment(id="reviewed", ai_proposed=False, confidence="low"),
    ]
    result = top_assessments(assessments, [])
    assert [a["id"] for a in result] == ["reviewed", "ai"]


def test_top_assessments_links_real_recommendations_not_invented():
    assessments = [_assessment(id="as-1")]
    recommendations = [{"id": "rec-1", "assessment_ids": ["as-1"], "title": "Do X"}]
    result = top_assessments(assessments, recommendations)
    assert len(result[0]["linked_recommendations"]) == 1
    assert result[0]["linked_recommendations"][0]["id"] == "rec-1"

    result_no_recs = top_assessments(assessments, [])
    assert result_no_recs[0]["linked_recommendations"] == []


def test_assessment_absent_why_it_matters_not_fabricated():
    assessments = [_assessment(id="as-1")]
    result = top_assessments(assessments, [])
    assert "why_it_matters" not in result[0] or result[0].get("why_it_matters") is None


# --- caution ----------------------------------------------------------------


def test_honest_empty_state_messages_match_required_phrasing():
    assert NO_ASSESSMENT_MESSAGE == "No analyst assessment captured."
    assert NO_SIGNAL_MESSAGE == "No confirmed or proposed Signal captured."


def test_caution_never_infers_low_activity_from_low_evidence():
    result = caution(disputed_relationship_count=2, unresolved_strategic_question_count=9)
    assert "not market activity" in result["coverage_caveat"]
    assert "low competitor activity" not in result["coverage_caveat"].lower()
    assert "low competitive activity" not in result["coverage_caveat"].lower()


# --- route-level tests against real data ------------------------------------


def test_readout_route_loads():
    client = TestClient(app)
    page = client.get("/readout")
    assert page.status_code == 200
    assert "Executive Intelligence Readout" in page.text


def test_readout_distinguishes_from_brief_and_landscape():
    client = TestClient(app)
    page = client.get("/readout")
    assert "distinct from Morning Brief" in page.text
    assert "Landscape" in page.text


def test_readout_shows_real_sections():
    client = TestClient(app)
    page = client.get("/readout")
    for heading in (
        "What changed",
        "Who / what matters",
        "What do we actually know",
        "What do our analyst assessments say",
        "Signals",
        "What to be cautious about",
    ):
        assert heading in page.text


def test_readout_trust_classes_stay_distinct():
    client = TestClient(app)
    page = client.get("/readout")
    # Real production data has both Assessments and Signals -- both marks
    # must appear, never merged into one generic "event" badge. Assert on
    # the always-rendered top_assessments/top_signals sections (badge
    # classes, not the literal "ASSESSMENT" string) rather than the
    # key_developments digest: that digest is windowed by
    # what_changed()'s fixed 14-day cutoff against the real wall clock
    # (/readout has no days= override, unlike /brief-pack), so a fixture
    # assessment's created_at ages out of it over time even though the
    # assessment itself is still present and correctly badged elsewhere.
    assert "badge-assessment" in page.text or "AI PROPOSED" in page.text or "REVIEWED" in page.text
    assert "SIGNAL" in page.text


def test_readout_reuses_landscape_actors_to_watch_no_duplicate_logic():
    client = TestClient(app)
    page = client.get("/readout")
    assert "not a competitive-strength ranking" in page.text


def test_readout_coverage_caveat_present():
    client = TestClient(app)
    page = client.get("/readout")
    assert "Captured intelligence coverage, not market activity" in page.text


def test_readout_no_winner_or_score_language():
    client = TestClient(app)
    page = client.get("/readout")
    lowered = page.text.casefold()
    for forbidden in ("winner", "best company", "competitive strength score", "threat score", "momentum score"):
        assert forbidden not in lowered


def test_readout_presentation_mode_toggle():
    client = TestClient(app)
    normal = client.get("/readout")
    presentation = client.get("/readout?present=1")
    assert normal.status_code == presentation.status_code == 200
    assert "v2-presentation-mode" in presentation.text
    assert "Exit presentation mode" in presentation.text
    assert "Presentation mode" in normal.text


def test_readout_no_pending_leakage():
    client = TestClient(app)
    page = client.get("/readout")
    assert "in_review" not in page.text
    assert "signal_candidate" not in page.text.casefold()


def test_readout_deterministic_across_requests():
    client = TestClient(app)
    first = client.get("/readout").text
    second = client.get("/readout").text
    assert first == second


def test_readout_nav_link_present():
    client = TestClient(app)
    page = client.get("/brief")
    assert page.status_code == 200
    assert 'href="/readout"' in page.text


def test_readout_warm_request_is_fast():
    import time

    client = TestClient(app)
    client.get("/readout")  # cold, populates cache
    t0 = time.perf_counter()
    client.get("/readout")
    warm_ms = (time.perf_counter() - t0) * 1000
    assert warm_ms < 2000
