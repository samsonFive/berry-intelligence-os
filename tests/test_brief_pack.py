"""Manager Brief Pack V1 -- a presentation/composition surface over
existing trusted objects, not a new trust object and not AI-generated
narrative. URL-state V1 (no server-side persistence, by explicit design
-- see app/services/brief_pack.py's module docstring)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app import main
from app.main import app
from app.services.brief_pack import (
    assessment_snapshot,
    company_snapshot,
    compose_brief_pack,
    learner_callout,
    signal_snapshot,
    source_trace,
    variety_snapshot,
)


def _entity(**overrides):
    row = {"record_type": "entity", "status": "active", "aliases": [], "berry_ids": [], "attributes": {}}
    row.update(overrides)
    return row


def _entities():
    rows = [
        _entity(id="company-a", entity_type="company", name="Company A", berry_ids=["berry-blueberry"]),
        _entity(id="variety-a", entity_type="variety", name="Variety A", berry_ids=["berry-blueberry"]),
        _entity(id="trait-firmness", entity_type="trait", name="Fruit firmness"),
    ]
    return {row["id"]: row for row in rows}


def _evidence(**overrides):
    row = {
        "id": "ev-1",
        "title": "An article",
        "source_name": "Some Source",
        "source_type": "trade_press",
        "published_date": "2026-01-01",
        "entity_ids": [],
    }
    row.update(overrides)
    return row


# --- company_snapshot / variety_snapshot -----------------------------------


def test_company_snapshot_preserves_role_distinction():
    entities = _entities()
    relationships = [
        {"id": "rel-1", "subject_id": "company-a", "predicate": "develops", "object_id": "variety-a", "status": "active"}
    ]
    row = company_snapshot(
        "company-a", entities=entities, relationships=relationships, published_evidence=[], signals=[]
    )
    assert row["roles"]["breeder"] == [{"id": "variety-a", "name": "Variety A"}]
    assert row["roles"]["marketer"] == []


def test_company_snapshot_recent_evidence_bounded_and_sorted():
    entities = _entities()
    evidence = [
        _evidence(id=f"ev-{i}", entity_ids=["company-a"], published_date=f"2026-01-{i:02d}") for i in range(1, 10)
    ]
    row = company_snapshot("company-a", entities=entities, relationships=[], published_evidence=evidence, signals=[])
    assert len(row["recent_evidence"]) == 3
    dates = [r["date"] for r in row["recent_evidence"]]
    assert dates == sorted(dates, reverse=True)
    assert row["evidence_count"] == 9


def test_company_snapshot_invalid_id_returns_none():
    entities = _entities()
    assert company_snapshot("company-missing", entities=entities, relationships=[], published_evidence=[], signals=[]) is None
    assert company_snapshot("variety-a", entities=entities, relationships=[], published_evidence=[], signals=[]) is None


def test_variety_snapshot_preserves_trust_class_per_row():
    entities = _entities()
    evidence = {"ev-1": _evidence(id="ev-1")}
    facts = [
        {
            "id": "fact-1",
            "statement": "Firm under trial",
            "classification": "fact",
            "entity_ids": ["variety-a", "trait-firmness"],
            "evidence_ids": ["ev-1"],
        }
    ]
    row = variety_snapshot(
        "variety-a",
        entities=entities,
        relationships=[],
        published_evidence=list(evidence.values()),
        signals=[],
        facts=facts,
        evidence_by_id=evidence,
    )
    assert row["top_observations"][0]["classification"] == "fact"
    assert row["top_observations"][0]["trait_names"] == ["Fruit firmness"]


def test_variety_snapshot_invalid_id_returns_none():
    entities = _entities()
    assert variety_snapshot("variety-missing", entities=entities, relationships=[], published_evidence=[], signals=[], facts=[], evidence_by_id={}) is None


# --- learner_callout / signal_snapshot / assessment_snapshot ---------------


def test_learner_callout_real_concept():
    row = learner_callout("firmness")
    assert row is not None
    assert row["name"] == "Firmness"
    assert row["href"] == "/learn/firmness"


def test_learner_callout_invalid_slug_returns_none():
    assert learner_callout("does-not-exist-xyz") is None


def test_signal_snapshot_distinct_from_assessment():
    signals_by_id = {"sig-1": {"id": "sig-1", "title": "A signal", "strength": "moderate", "evidence_ids": ["a", "b"]}}
    row = signal_snapshot("sig-1", signals_by_id)
    assert row["evidence_count"] == 2
    assert signal_snapshot("sig-missing", signals_by_id) is None


def test_assessment_snapshot_links_real_recommendations_only():
    assessments_by_id = {"as-1": {"id": "as-1", "title": "An assessment", "evidence_ids": ["a"], "fact_ids": ["b", "c"]}}
    recommendations = [{"id": "rec-1", "assessment_ids": ["as-1"]}]
    row = assessment_snapshot("as-1", assessments_by_id, recommendations)
    assert row["linked_recommendation_count"] == 1
    assert row["supporting_fact_count"] == 2
    assert assessment_snapshot("as-missing", assessments_by_id, []) is None


# --- source_trace ------------------------------------------------------------


def test_source_trace_dedups_and_sorts_newest_first():
    evidence_by_id = {
        "ev-1": _evidence(id="ev-1", published_date="2026-01-01"),
        "ev-2": _evidence(id="ev-2", published_date="2026-03-01"),
    }
    rows = source_trace({"ev-1", "ev-2", "ev-1"}, evidence_by_id)
    assert len(rows) == 2
    assert rows[0]["id"] == "ev-2"


# --- compose_brief_pack -----------------------------------------------------


def _compose(**overrides):
    entities = _entities()
    defaults = dict(
        title="Test Pack",
        context_note="",
        berry_id=None,
        window_days=14,
        company_ids=[],
        variety_ids=[],
        signal_ids=[],
        assessment_ids=[],
        concept_slugs=[],
        entities=entities,
        relationships=[],
        published_evidence=[],
        facts=[],
        evidence_by_id={},
        signals=[],
        assessments=[],
        recommendations=[],
        landscape_snapshot={"scope": "all", "berry_label": "All berries", "header_stats": {}, "actors_to_watch": [], "href": "/landscapes"},
    )
    defaults.update(overrides)
    return compose_brief_pack(**defaults)


def test_compose_reports_invalid_ids_not_silently_dropped():
    pack = _compose(company_ids=["company-a", "company-missing"], variety_ids=["variety-missing"])
    assert [c["id"] for c in pack["companies"]] == ["company-a"]
    assert pack["invalid_companies"] == ["company-missing"]
    assert pack["invalid_varieties"] == ["variety-missing"]


def test_compose_caps_selection_at_five_and_reports_overflow():
    company_ids = [f"company-{i}" for i in range(7)]
    pack = _compose(company_ids=company_ids)
    assert len(pack["invalid_companies"]) + len(pack["companies"]) == 5
    assert pack["overflow_companies"] == company_ids[5:]


def test_compose_dedups_repeated_ids():
    pack = _compose(company_ids=["company-a", "company-a", "company-a"])
    assert len(pack["companies"]) == 1


def test_compose_honest_empty_states_when_nothing_selected():
    pack = _compose()
    assert pack["companies"] == []
    assert pack["varieties"] == []
    assert pack["signals"] == []
    assert pack["assessments"] == []
    assert pack["concepts"] == []


def test_compose_coverage_caveat_present_and_no_market_activity_claim():
    pack = _compose()
    assert "not market activity" in pack["coverage_caveat"]
    assert "low competitor activity" not in pack["coverage_caveat"].lower()


def test_compose_source_trace_collects_across_sections():
    entities = _entities()
    evidence = {"ev-1": _evidence(id="ev-1", entity_ids=["company-a"])}
    pack = _compose(
        company_ids=["company-a"],
        published_evidence=list(evidence.values()),
        evidence_by_id=evidence,
    )
    trace_ids = {row["id"] for row in pack["source_trace"]}
    assert "ev-1" in trace_ids


def test_compose_no_winner_or_score_language():
    import json

    pack = _compose(company_ids=["company-a"])
    text = json.dumps(pack, default=str).lower()
    for forbidden in ("competitive strength score", "threat score", "momentum score", "winner"):
        assert forbidden not in text


# --- route-level tests against real data ------------------------------------


def test_brief_pack_route_loads():
    client = TestClient(app)
    page = client.get("/brief-pack")
    assert page.status_code == 200
    assert "Manager Brief" in page.text


def test_brief_pack_ordered_sections_present():
    client = TestClient(app)
    page = client.get("/brief-pack")
    ids = [
        "executive-readout-section",
        "landscape-section",
        "companies-section",
        "varieties-section",
        "signals-section",
        "assessments-section",
    ]
    positions = [page.text.index(f'id="{sid}"') for sid in ids]
    assert positions == sorted(positions)


def test_brief_pack_real_company_variety_signal_assessment_concept():
    client = TestClient(app)
    page = client.get(
        "/brief-pack",
        params={
            "title": "Blueberry Genetics Update",
            "berry": "berry-blueberry",
            "companies": "company-planasa",
            "varieties": "variety-sekoya-grande",
            "concepts": "firmness",
        },
    )
    assert page.status_code == 200
    assert "Blueberry Genetics Update" in page.text
    assert "Plantas de Navarra" in page.text
    assert "SEKOYA Grande" in page.text
    assert "EDUCATIONAL KNOWLEDGE" in page.text


def test_brief_pack_trust_classes_stay_distinct():
    client = TestClient(app)
    page = client.get(
        "/brief-pack",
        params={
            "signals": "sig-breeder-and-patent-attribution-drift-in-public-sources",
            "assessments": "assessment-blueberry-genetics-commercialized-through-platforms",
        },
    )
    assert page.status_code == 200
    assert "SIGNAL" in page.text
    assert "ASSESSMENT" in page.text


def test_brief_pack_invalid_ids_reported_not_crashed():
    client = TestClient(app)
    page = client.get("/brief-pack", params={"companies": "company-totally-fake-xyz"})
    assert page.status_code == 200
    assert "company-totally-fake-xyz" in page.text
    assert "Not found" in page.text


def test_brief_pack_context_note_preserved():
    client = TestClient(app)
    page = client.get("/brief-pack", params={"context_note": "Prepared for leadership review"})
    assert page.status_code == 200
    assert "Prepared for leadership review" in page.text


def test_brief_pack_coverage_caveat_present():
    client = TestClient(app)
    page = client.get("/brief-pack")
    assert "Captured intelligence coverage, not market activity" in page.text


def test_brief_pack_no_winner_or_score_language():
    client = TestClient(app)
    page = client.get("/brief-pack", params={"companies": "company-planasa"})
    lowered = page.text.casefold()
    for forbidden in ("winner", "best company", "competitive strength score", "threat score", "momentum score"):
        assert forbidden not in lowered


def test_brief_pack_presentation_mode_toggle():
    client = TestClient(app)
    normal = client.get("/brief-pack")
    presentation = client.get("/brief-pack?present=1")
    assert normal.status_code == presentation.status_code == 200
    assert "v2-presentation-mode" in presentation.text
    assert "Exit presentation mode" in presentation.text


def test_brief_pack_no_pending_leakage():
    client = TestClient(app)
    page = client.get("/brief-pack", params={"companies": "company-planasa"})
    assert "in_review" not in page.text
    assert "signal_candidate" not in page.text.casefold()


def test_brief_pack_deterministic_across_requests():
    client = TestClient(app)
    url = "/brief-pack?companies=company-planasa&varieties=variety-sekoya-grande"
    first = client.get(url).text
    second = client.get(url).text
    assert first == second


def test_brief_pack_deep_link_reload_stable():
    client = TestClient(app)
    url = "/brief-pack?title=Q3+Update&companies=company-planasa,company-costa-group-holdings"
    first = client.get(url)
    second = client.get(url)
    assert first.status_code == second.status_code == 200
    assert "Q3 Update" in first.text and "Q3 Update" in second.text


def test_brief_pack_evidence_trace_links_present():
    client = TestClient(app)
    page = client.get("/brief-pack", params={"companies": "company-planasa"})
    assert "/evidence/" in page.text


def test_brief_pack_nav_link_present():
    client = TestClient(app)
    page = client.get("/brief")
    assert page.status_code == 200
    assert 'href="/brief-pack"' in page.text


def test_brief_pack_warm_request_is_fast():
    import time

    client = TestClient(app)
    url = "/brief-pack?companies=company-planasa&varieties=variety-sekoya-grande"
    client.get(url)  # cold, populates cache
    t0 = time.perf_counter()
    client.get(url)
    warm_ms = (time.perf_counter() - t0) * 1000
    assert warm_ms < 1000


def test_print_css_rules_exist():
    css = (main.BASE_DIR / "app" / "static" / "v2.css").read_text(encoding="utf-8")
    assert "@media print" in css
    assert "page-break-inside: avoid" in css or "break-inside: avoid" in css
