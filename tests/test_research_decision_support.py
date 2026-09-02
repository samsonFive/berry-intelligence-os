"""Strategic comparison and decision-support contracts for Ask Berry OS."""

from __future__ import annotations

from copy import deepcopy

from app.services.research_decision_support import build_research_decision_support
from app.services.research_desk import (
    ResearchScope,
    assemble_research_packet,
    comparison_candidate_ids,
    interpret_research_scope,
)


def _scope(**overrides) -> ResearchScope:
    values = {
        "question": "Compare Company A, Company B, and Company C in blueberries.",
        "berry_id": "berry-blueberry",
        "geography_ids": (),
        "company_ids": ("company-a", "company-b", "company-c"),
        "variety_ids": (),
        "window_days": 30,
        "topics": (),
        "intelligence_type": "company_comparison",
        "comparison": True,
    }
    values.update(overrides)
    return ResearchScope(**values)


def _comparison() -> dict:
    def card(company_id: str, name: str, *, geographies=(), varieties=(), rights=()):
        return {
            "id": company_id,
            "name": name,
            "href": f"/entities/company/{company_id}",
            "roles": {"breeder": [{"id": value, "name": value, "href": f"/entities/variety/{value}"} for value in varieties]},
            "rights_published": list(rights),
            "geographies": [{"id": value, "name": value, "href": f"/entities/geography/{value}"} for value in geographies],
        }
    return {"companies": [
        card("company-a", "Company A", geographies=("Peru",), varieties=("Alpha",)),
        card("company-b", "Company B", varieties=("Beta",)),
        card("company-c", "Company C"),
    ]}


def _packet() -> dict:
    evidence = [
        {"id": "ev-a1", "title": "A expands", "entity_ids": ["company-a"], "trust_class": "TRUSTED EVIDENCE", "href": "/evidence/ev-a1"},
        {"id": "ev-a2", "title": "A genetics", "entity_ids": ["company-a"], "trust_class": "TRUSTED EVIDENCE", "href": "/evidence/ev-a2"},
        {"id": "ev-b1", "title": "B genetics", "entity_ids": ["company-b"], "trust_class": "TRUSTED EVIDENCE", "href": "/evidence/ev-b1"},
    ]
    market = [{
        "id": "market-1", "title": "Peru production moved", "trust_class": "STRUCTURED MARKET OBSERVATION",
        "structured_kind": "MARKET REALITY", "href": "https://example.test/market",
    }]
    radar = [{
        "id": "radar-a", "title": "A opens a new program", "company_ids": ["company-a"],
        "event_type": "PRODUCTION_EXPANSION", "trust_class": "LIVE / UNREVIEWED DEVELOPMENT",
        "url": "https://example.test/a", "source_count": 2,
    }]
    relationships = [{
        "id": "rel-a", "subject_id": "company-a", "object_id": "company-partner", "predicate": "partners_with",
        "subject_name": "Company A", "object_name": "Partner", "evidence_ids": ["ev-a1"],
    }]
    source_rows = [*evidence, *market, *radar]
    return {
        "scope": _scope().as_dict(),
        "evidence": evidence,
        "rights_ip": [],
        "relationships": relationships,
        "market_context": market,
        "radar_developments": radar,
        "competitive_moves": [],
        "signals": [],
        "source_index": {row["id"]: row for row in source_rows},
        "geographies": [{"id": "geography-peru", "name": "Peru"}],
    }


def test_comparison_emits_only_populated_dimensions_and_no_score() -> None:
    model = build_research_decision_support(_scope(), packet=_packet(), company_compare=_comparison())
    assert model is not None
    assert model["mode"] == "comparison"
    keys = {row["key"] for row in model["dimensions"]}
    assert {"current", "moves", "geographies", "varieties", "partnerships", "trusted"}.issubset(keys)
    assert "signals" not in keys
    assert "score" not in str(model).casefold()


def test_differences_are_coverage_cautious_and_cited() -> None:
    model = build_research_decision_support(_scope(), packet=_packet(), company_compare=_comparison())
    assert model and model["key_differences"]
    known = set(_packet()["source_index"])
    for row in [*model["key_differences"], *model["interpretation"], *model["watch_next"]]:
        assert row["source_ids"]
        assert set(row["source_ids"]).issubset(known)
    text = " ".join(row["text"] for row in model["key_differences"])
    assert "visible" in text
    assert "not underlying company performance" in text
    assert model["coverage_difference"]["different"] is True
    assert "must not be interpreted" in model["coverage_difference"]["note"]
    assert "Observed activity" in model["coverage_difference"]["note"]


def test_unknown_source_ids_cannot_create_generated_difference() -> None:
    packet = _packet()
    packet["source_index"] = {}
    model = build_research_decision_support(_scope(), packet=packet, company_compare=_comparison())
    assert model is not None
    assert model["key_differences"] == []
    assert model["interpretation"] == []
    assert model["watch_next"] == []


def test_market_context_is_shared_and_never_allocates_company_share() -> None:
    model = build_research_decision_support(_scope(), packet=_packet(), company_compare=_comparison())
    assert model and model["market_context"]
    market_claim = next(row for row in model["interpretation"] if "market movement" in row["text"])
    assert market_claim["source_ids"] == ["market-1"]
    assert "does not allocate market share" in market_claim["text"]


def test_company_deep_dive_reuses_same_model_without_fabricating_comparison() -> None:
    comparison = _comparison()
    comparison["companies"] = comparison["companies"][:1]
    model = build_research_decision_support(
        _scope(company_ids=("company-a",), comparison=False, intelligence_type="competitor"),
        packet=_packet(), company_compare=comparison,
    )
    assert model and model["mode"] == "company_deep_dive"
    assert model["companies"][0]["varieties"]
    assert model["companies"][0]["geographies"]


def test_decision_support_never_mutates_packet_or_company_cards() -> None:
    packet = _packet()
    comparison = _comparison()
    before_packet = deepcopy(packet)
    before_comparison = deepcopy(comparison)
    build_research_decision_support(_scope(), packet=packet, company_compare=comparison)
    assert packet == before_packet
    assert comparison == before_comparison


def test_comparative_intent_and_smart_apostrophe_resolve_without_silent_guessing() -> None:
    entities = [
        {"id": "company-driscolls", "entity_type": "company", "name": "Driscoll's", "aliases": []},
        {"id": "company-hortifrut", "entity_type": "company", "name": "Hortifrut", "aliases": []},
        {"id": "geography-europe", "entity_type": "geography", "name": "Europe", "aliases": []},
    ]
    scope = interpret_research_scope(
        "Who appears most active in European berry genetics?",
        berries={"berry-blueberry": "Blueberry"}, entities=entities, questions=[], relationships=[],
    )
    assert scope.comparison is True
    assert scope.geography_ids == ("geography-europe",)
    assert scope.topics == ("genetics",)

    named = interpret_research_scope(
        "What are the most important differences between Hortifrut and Driscoll’s right now?",
        berries={"berry-blueberry": "Blueberry"}, entities=entities, questions=[], relationships=[],
    )
    assert named.company_ids == ("company-hortifrut", "company-driscolls")
    assert named.comparison is True
    assert named.window_days == 7

    plural = interpret_research_scope(
        "Compare Hortifrut and Driscoll's in blueberries.",
        berries={"berry-blueberry": "Blueberry"}, entities=entities, questions=[], relationships=[],
    )
    assert plural.berry_id == "berry-blueberry"


def test_packet_consumes_market_radar_and_competitive_move_seams() -> None:
    scope = _scope(company_ids=("company-a",))
    entities = {
        "company-a": {"id": "company-a", "entity_type": "company", "name": "Company A", "berry_ids": ["berry-blueberry"]},
    }
    packet = assemble_research_packet(
        scope,
        entities=entities,
        relationships=[], published_evidence=[], facts=[], signals=[], assessments=[],
        market_context_provider=lambda _scope: [{"id": "market-1", "title": "Market", "structured_kind": "MARKET REALITY"}],
        radar_provider=lambda _scope: [{"id": "radar-1", "title": "Radar", "company_ids": ["company-a"], "sources": []}],
        competitive_moves_provider=lambda _scope: [{"id": "move-1", "title": "Move", "company_ids": ["company-a"], "sources": []}],
    )
    assert packet["market_context"][0]["id"] == "market-1"
    assert packet["radar_developments"][0]["id"] == "radar-1"
    assert packet["competitive_moves"][0]["id"] == "move-1"
    assert {"MARKET_REALITY", "RADAR_DEVELOPMENTS", "COMPETITIVE_MOVES"}.issubset(packet["requested_layers"])


def test_ambient_genetics_comparison_prefers_operating_company_over_financial_comention() -> None:
    scope = _scope(company_ids=(), topics=("genetics",))
    entities = {
        "company-breeder": {"id": "company-breeder", "entity_type": "company"},
        "company-investor": {"id": "company-investor", "entity_type": "company"},
        "variety-a": {"id": "variety-a", "entity_type": "variety", "berry_ids": ["berry-blueberry"]},
    }
    packet = {
        "evidence": [{"id": "ev-1", "entity_ids": ["company-breeder", "company-investor"]}],
        "rights_ip": [], "radar_developments": [], "competitive_moves": [],
    }
    ids = comparison_candidate_ids(
        scope,
        packet=packet,
        entities=entities,
        relationships=[{"subject_id": "company-breeder", "predicate": "develops", "object_id": "variety-a"}],
    )
    assert ids == ["company-breeder"]


def test_blueberry_scope_drops_other_berry_varieties_from_packet() -> None:
    scope = _scope(company_ids=("company-a",))
    entities = {
        "company-a": {"id": "company-a", "entity_type": "company", "name": "Company A"},
        "variety-blue": {"id": "variety-blue", "entity_type": "variety", "name": "Blue", "berry_ids": ["berry-blueberry"]},
        "variety-rasp": {"id": "variety-rasp", "entity_type": "variety", "name": "Rasp", "berry_ids": ["berry-raspberry"]},
    }
    packet = assemble_research_packet(
        scope,
        entities=entities,
        relationships=[],
        published_evidence=[{
            "id": "ev-mix",
            "title": "Mixed",
            "entity_ids": ["company-a", "variety-blue", "variety-rasp"],
            "published_date": "2026-08-20",
        }],
        facts=[], signals=[], assessments=[],
    )
    variety_ids = {row["id"] for row in packet["varieties"]}
    assert "variety-blue" in variety_ids
    assert "variety-rasp" not in variety_ids


def test_watch_prefers_question_geography_over_move_geography() -> None:
    packet = _packet()
    packet["geographies"] = [{"id": "geography-europe", "name": "Europe"}]
    packet["competitive_moves"] = [{
        "id": "move-a",
        "title": "Company A genetics launch",
        "company_id": "company-a",
        "move_type": "GENETICS_LAUNCH",
        "layer": "COMPETITIVE MOVE",
        "source_count": 2,
        "variety_names": ["Sekoya Nova"],
        "geography_labels": ["Peru"],
    }]
    packet["source_index"]["move-a"] = packet["competitive_moves"][0]
    model = build_research_decision_support(_scope(), packet=packet, company_compare=_comparison())
    watch = " ".join(row["text"] for row in model["watch_next"])
    assert "Europe" in watch
    assert " in Peru" not in watch


def test_official_competitive_move_dicts_are_company_scoped() -> None:
    packet = _packet()
    packet["competitive_moves"] = [{
        "id": "move-a",
        "title": "Company A genetics launch",
        "company_id": "company-a",
        "move_type": "GENETICS_LAUNCH",
        "layer": "COMPETITIVE MOVE",
        "source_count": 2,
        "variety_names": ["Sekoya Nova"],
        "geography_labels": ["Peru"],
    }]
    packet["source_index"]["move-a"] = packet["competitive_moves"][0]
    model = build_research_decision_support(_scope(), packet=packet, company_compare=_comparison())
    assert model is not None
    a_moves = next(row["moves"] for row in model["companies"] if row["id"] == "company-a")
    assert a_moves[0]["id"] == "move-a"
    watch = " ".join(row["text"] for row in model["watch_next"])
    assert "Sekoya Nova" in watch or "Peru" in watch
    snapshot = next(row for row in model["positioning"] if row["id"] == "company-a")
    assert snapshot["visible_current_moves"]["lead"]
    assert model["coverage_difference"]["observed_activity"]["Company A"] >= 1
    assert "More sources" not in model["coverage_difference"]["coverage_note"] or "not more activity" in model["coverage_difference"]["coverage_note"]
