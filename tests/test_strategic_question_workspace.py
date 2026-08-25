"""Strategic Question + Decision Workspace V1 -- organizes already-trusted
Facts, Evidence, Signals, Assessments, and Recommendations around a
Strategic Question. Never generates judgment; every gap is a defensible
absence state, never AI-invented."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.services.strategic_question_workspace import (
    strategic_question_detail,
    strategic_question_index,
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
        "description": "A test question.",
        "status": "active",
        "berry_ids": ["berry-blueberry"],
    }
    row.update(overrides)
    return [row]


def _evidence(**overrides):
    row = {
        "id": "ev-1",
        "title": "Test evidence",
        "source_name": "Some Source",
        "source_type": "trade_press",
        "published_date": "2026-01-01",
        "entity_ids": [],
        "strategic_question_ids": [],
    }
    row.update(overrides)
    return row


def _fact(**overrides):
    row = {
        "id": "fact-1",
        "statement": "A statement.",
        "classification": "fact",
        "confidence": "high",
        "created_at": "2026-01-01",
        "evidence_ids": ["ev-1"],
        "entity_ids": [],
    }
    row.update(overrides)
    return row


def _signal(**overrides):
    row = {
        "id": "sig-1",
        "title": "Test signal",
        "status": "confirmed",
        "strength": "moderate",
        "entity_ids": [],
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
        "rationale": "Because of X.",
        "would_change_our_view": "If Y happens.",
        "fact_ids": ["fact-1"],
        "entity_ids": [],
        "strategic_question_ids": [],
    }
    row.update(overrides)
    return row


def _recommendation(**overrides):
    row = {
        "id": "recommendation-1",
        "title": "Test recommendation",
        "status": "open",
        "priority": "medium",
        "action_type": "monitor",
        "rationale": "Do this.",
        "ai_proposed": False,
        "entity_ids": [],
        "strategic_question_ids": [],
    }
    row.update(overrides)
    return row


def _detail(sq_id="sq-test", questions=None, entities=None, **kwargs):
    defaults = dict(
        questions=questions or _sq(),
        entities=entities or _entities(),
        published_evidence=[],
        facts=[],
        signals=[],
        assessments=[],
        recommendations=[],
        berry_labels={"berry-blueberry": "Blueberry"},
    )
    defaults.update(kwargs)
    return strategic_question_detail(sq_id, **defaults)


# --- Presenter unit tests (synthetic fixtures) ---


def test_unknown_question_id_returns_none():
    assert _detail("sq-does-not-exist") is None


def test_fully_sparse_question_shows_all_gaps_honestly():
    result = _detail()
    assert result["coverage"] == {
        "fact_count": 0,
        "evidence_count": 0,
        "signal_count": 0,
        "assessment_count": 0,
        "recommendation_count": 0,
    }
    assert len(result["gaps"]) == 5
    assert "No Fact established for this question yet." in result["gaps"]


def test_fact_appears_only_via_linked_assessment_fact_ids():
    evidence = [_evidence(id="ev-1", strategic_question_ids=["sq-test"])]
    facts = [_fact(id="fact-1", evidence_ids=["ev-1"])]
    assessments = [_assessment(id="assessment-1", fact_ids=["fact-1"], strategic_question_ids=["sq-test"])]
    result = _detail(published_evidence=evidence, facts=facts, assessments=assessments)
    assert result["coverage"]["fact_count"] == 1
    assert result["facts"][0]["id"] == "fact-1"
    assert result["facts"][0]["supporting_evidence"][0]["id"] == "ev-1"


def test_fact_not_linked_to_any_assessment_is_not_pulled_in():
    facts = [_fact(id="fact-orphan")]
    result = _detail(facts=facts)
    assert result["coverage"]["fact_count"] == 0


def test_assessment_preserves_ai_proposed_and_reviewed_distinctly():
    assessments = [
        _assessment(id="a-reviewed", ai_proposed=False, strategic_question_ids=["sq-test"]),
        _assessment(id="a-ai", ai_proposed=True, strategic_question_ids=["sq-test"]),
    ]
    result = _detail(assessments=assessments)
    by_id = {a["id"]: a for a in result["assessments"]}
    assert by_id["a-reviewed"]["ai_proposed"] is False
    assert by_id["a-ai"]["ai_proposed"] is True


def test_signal_distinct_from_fact_and_assessment():
    signals = [_signal(id="sig-1", strategic_question_ids=["sq-test"])]
    result = _detail(signals=signals)
    assert result["coverage"]["signal_count"] == 1
    assert result["coverage"]["fact_count"] == 0
    assert result["signals"][0]["status"] == "confirmed"


def test_would_change_our_view_only_from_real_authored_text():
    assessments = [
        _assessment(id="a-1", would_change_our_view="If independent tests confirm it.", strategic_question_ids=["sq-test"]),
        _assessment(id="a-2", would_change_our_view="", strategic_question_ids=["sq-test"]),
    ]
    result = _detail(assessments=assessments)
    assert result["would_change_our_view"] == ["If independent tests confirm it."]


def test_recommendation_not_auto_generated_from_assessment():
    assessments = [_assessment(id="a-1", strategic_question_ids=["sq-test"])]
    result = _detail(assessments=assessments)
    assert result["recommendations"] == []
    assert "No Recommendation captured for this question yet." in result["gaps"]


def test_recommendation_shown_when_actually_linked():
    recommendations = [_recommendation(id="rec-1", strategic_question_ids=["sq-test"])]
    result = _detail(recommendations=recommendations)
    assert result["coverage"]["recommendation_count"] == 1
    assert result["recommendations"][0]["id"] == "rec-1"


def test_company_variety_geography_scope_derived_from_linked_objects():
    evidence = [
        _evidence(
            id="ev-1",
            strategic_question_ids=["sq-test"],
            entity_ids=["company-a", "variety-x", "geography-spain"],
        )
    ]
    result = _detail(published_evidence=evidence)
    assert [p["id"] for p in result["company_scope"]] == ["company-a"]
    assert [p["id"] for p in result["variety_scope"]] == ["variety-x"]
    assert [p["id"] for p in result["geography_scope"]] == ["geography-spain"]


def test_source_trace_includes_evidence_cited_by_fact_and_signal():
    evidence = [
        _evidence(id="ev-direct", strategic_question_ids=["sq-test"]),
        _evidence(id="ev-via-fact"),
    ]
    facts = [_fact(id="fact-1", evidence_ids=["ev-via-fact"])]
    assessments = [_assessment(id="a-1", fact_ids=["fact-1"], strategic_question_ids=["sq-test"])]
    result = _detail(published_evidence=evidence, facts=facts, assessments=assessments)
    trace_ids = {r["id"] for r in result["source_trace"]}
    assert trace_ids == {"ev-direct", "ev-via-fact"}


def test_no_synthetic_score_fields_in_result():
    result = _detail()
    forbidden_keys = {"score", "readiness_score", "confidence_score", "decision_score"}
    assert not (forbidden_keys & set(result.keys()))
    assert not (forbidden_keys & set(result["coverage"].keys()))


def test_index_sorted_alphabetically_with_real_counts():
    questions = _sq(id="sq-b", title="B question") + _sq(id="sq-a", title="A question")
    rows = strategic_question_index(
        questions=questions,
        published_evidence=[],
        facts=[],
        signals=[],
        assessments=[],
        recommendations=[],
        berry_labels={"berry-blueberry": "Blueberry"},
    )
    assert [r["title"] for r in rows] == ["A question", "B question"]


# --- Route-level tests against real production data ---


def test_list_route_shows_real_question():
    client = TestClient(app)
    page = client.get("/strategic-questions")
    assert page.status_code == 200
    assert "Which breeding programs and genetics owners" in page.text
    assert "/strategic-questions/sq-global-genetics-reach" in page.text


def test_detail_route_data_rich_question():
    client = TestClient(app)
    page = client.get("/strategic-questions/sq-global-genetics-reach")
    assert page.status_code == 200
    assert "What we know" in page.text
    assert "What we think" in page.text
    assert "What we are watching" in page.text
    assert "What we don&#39;t know" in page.text or "What we don't know" in page.text
    assert "What would change our view" in page.text
    assert "Recommendations" in page.text
    assert "Source trace" in page.text


def test_detail_route_sparse_question_honest_gaps():
    client = TestClient(app)
    page = client.get("/strategic-questions/sq-premium-flavor")
    assert page.status_code == 200
    assert "No Fact established for this question yet." in page.text
    assert "No confirmed or proposed Signal captured for this question yet." in page.text


def test_detail_route_invalid_id_is_404():
    client = TestClient(app)
    page = client.get("/strategic-questions/sq-totally-fake-id")
    assert page.status_code == 404


def test_detail_preserves_ai_proposed_vs_reviewed_badge():
    client = TestClient(app)
    page = client.get("/strategic-questions/sq-competitor-expansion")
    assert page.status_code == 200
    assert "AI PROPOSED" in page.text or "REVIEWED" in page.text


def test_no_forbidden_score_language():
    client = TestClient(app)
    page = client.get("/strategic-questions/sq-global-genetics-reach")
    assert page.status_code == 200
    lowered = page.text.casefold()
    for forbidden in ("readiness score", "decision score", "strategic score"):
        assert forbidden not in lowered


def test_does_not_leak_pending_content():
    client = TestClient(app)
    page = client.get("/strategic-questions/sq-global-genetics-reach")
    assert page.status_code == 200
    assert "in_review" not in page.text
    assert "signal_candidate" not in page.text.casefold()


def test_company_portfolio_links_to_strategic_question():
    client = TestClient(app)
    page = client.get("/entities/company/company-costa-group-holdings/portfolio")
    assert page.status_code == 200
    assert "/strategic-questions/" in page.text


def test_variety_profile_links_to_strategic_question():
    client = TestClient(app)
    page = client.get("/entities/variety/variety-blue-manila")
    assert page.status_code == 200
    assert "/strategic-questions/" in page.text


def test_geography_detail_links_to_strategic_question():
    client = TestClient(app)
    page = client.get("/geographies/geography-south-africa")
    assert page.status_code == 200
    assert "/strategic-questions/" in page.text


def test_landscape_explore_links_to_strategic_question():
    client = TestClient(app)
    page = client.get("/landscapes/berries/blueberry")
    assert page.status_code == 200
    assert "/strategic-questions/" in page.text


def test_executive_readout_links_to_strategic_question():
    client = TestClient(app)
    page = client.get("/readout")
    assert page.status_code == 200
    assert "/strategic-questions/" in page.text


def test_brief_pack_links_to_strategic_question():
    # The SQ link lives on the Signals/Assessments sections, not the
    # Companies section -- select a real Assessment known to carry
    # strategic_question_ids so this actually exercises the link.
    client = TestClient(app)
    page = client.get(
        "/brief-pack",
        params={"assessments": "assessment-blueberry-genetics-commercialized-through-platforms"},
    )
    assert page.status_code == 200
    assert "/strategic-questions/" in page.text


def test_global_search_discovers_strategic_questions():
    client = TestClient(app)
    page = client.get("/api/search/global", params={"q": "genetics", "berry": "global"})
    assert page.status_code == 200
    data = page.json()
    sq_group = next((g for g in data.get("groups", []) if g["id"] == "strategic_questions"), None)
    assert sq_group is not None
    assert sq_group["in_context"] or sq_group["also_global"]
