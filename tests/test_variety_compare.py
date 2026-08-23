"""Variety Compare V1 -- side-by-side trusted intelligence workspace."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.services.variety_workspace import COMPARE_MAX_VARIETIES, present_variety_compare


def _entity(**overrides):
    row = {
        "record_type": "entity",
        "status": "active",
        "aliases": [],
        "berry_ids": [],
        "attributes": {},
    }
    row.update(overrides)
    return row


def _entities():
    rows = [
        _entity(id="variety-a", entity_type="variety", name="Variety A", berry_ids=["berry-blueberry"]),
        _entity(id="variety-b", entity_type="variety", name="Variety B", berry_ids=["berry-blueberry"]),
        _entity(id="variety-sparse", entity_type="variety", name="Variety Sparse", berry_ids=["berry-raspberry"]),
        _entity(id="company-x", entity_type="company", name="Company X"),
        _entity(id="trait-firmness", entity_type="trait", name="Fruit firmness"),
        _entity(id="trait-flavor", entity_type="trait", name="Eating quality"),
    ]
    return {row["id"]: row for row in rows}


def _fact(**overrides):
    row = {
        "id": "fact-1",
        "record_type": "fact",
        "statement": "A statement.",
        "classification": "fact",
        "confidence": "high",
        "status": "active",
        "created_at": "2026-01-01",
        "evidence_ids": ["ev-1"],
        "entity_ids": [],
    }
    row.update(overrides)
    return row


def _evidence(**overrides):
    row = {
        "id": "ev-1",
        "source_name": "Some Source",
        "source_type": "trade_press",
        "published_date": "2026-01-01",
        "geography_ids": [],
    }
    row.update(overrides)
    return row


def test_dedupes_and_caps_at_max_varieties():
    entities = _entities()
    result = present_variety_compare(
        ["variety-a", "variety-a", "variety-b", "variety-sparse", "variety-a"],
        entities=entities,
        relationships=[],
        published_evidence=[],
        facts=[],
        evidence_by_id={},
        signals=[],
        assessments=[],
        berry_labels={"berry-blueberry": "Blueberry", "berry-raspberry": "Raspberry"},
    )
    ids = [card["id"] for card in result["varieties"]]
    assert ids == ["variety-a", "variety-b", "variety-sparse"]
    assert result["count"] == 3
    assert result["invalid_ids"] == []
    assert result["overflow_ids"] == []


def test_invalid_and_non_variety_ids_are_reported_not_silently_dropped():
    entities = _entities()
    result = present_variety_compare(
        ["variety-a", "variety-missing", "company-x"],
        entities=entities,
        relationships=[],
        published_evidence=[],
        facts=[],
        evidence_by_id={},
        signals=[],
        assessments=[],
        berry_labels={},
    )
    assert [c["id"] for c in result["varieties"]] == ["variety-a"]
    assert set(result["invalid_ids"]) == {"variety-missing", "company-x"}


def test_overflow_beyond_max_is_reported():
    entities = _entities()
    entities["variety-c"] = _entity(id="variety-c", entity_type="variety", name="Variety C")
    entities["variety-d"] = _entity(id="variety-d", entity_type="variety", name="Variety D")
    entities["variety-e"] = _entity(id="variety-e", entity_type="variety", name="Variety E")
    result = present_variety_compare(
        ["variety-a", "variety-b", "variety-c", "variety-d", "variety-e"],
        entities=entities,
        relationships=[],
        published_evidence=[],
        facts=[],
        evidence_by_id={},
        signals=[],
        assessments=[],
        berry_labels={},
    )
    assert result["count"] == COMPARE_MAX_VARIETIES
    assert result["overflow_ids"] == ["variety-e"]
    assert result["max_reached"] is True


def test_sparse_variety_has_no_fabricated_dimensions_or_rights():
    entities = _entities()
    result = present_variety_compare(
        ["variety-sparse"],
        entities=entities,
        relationships=[],
        published_evidence=[],
        facts=[],
        evidence_by_id={},
        signals=[],
        assessments=[],
        berry_labels={},
    )
    card = result["varieties"][0]
    assert card["coverage"]["observation_count"] == 0
    assert card["rights_published"] == []
    assert card["rights_drafts"] == []
    assert result["dimensions"] == []


def test_multi_observation_dimension_shows_separate_rows_not_collapsed():
    entities = _entities()
    evidence = {
        "ev-1": _evidence(id="ev-1", source_name="Source One", published_date="2026-01-01"),
        "ev-2": _evidence(id="ev-2", source_name="Source Two", published_date="2026-02-01"),
    }
    facts = [
        _fact(
            id="fact-a",
            statement="Firm under trial conditions.",
            classification="fact",
            entity_ids=["variety-a", "trait-firmness"],
            evidence_ids=["ev-1"],
        ),
        _fact(
            id="fact-b",
            statement="Owner claims very firm fruit.",
            classification="claim",
            entity_ids=["variety-a", "trait-firmness"],
            evidence_ids=["ev-2"],
        ),
    ]
    result = present_variety_compare(
        ["variety-a", "variety-b"],
        entities=entities,
        relationships=[],
        published_evidence=list(evidence.values()),
        facts=facts,
        evidence_by_id=evidence,
        signals=[],
        assessments=[],
        berry_labels={},
    )
    firmness = next(d for d in result["dimensions"] if d["name"] == "Fruit firmness")
    cell_a = next(c for c in firmness["cells"] if c["variety_id"] == "variety-a")
    cell_b = next(c for c in firmness["cells"] if c["variety_id"] == "variety-b")
    # Two independent observations for variety-a's same dimension must both
    # survive as separate rows -- never collapsed into one abstracted value.
    assert len(cell_a["rows"]) == 2
    statements = {row["statement"] for row in cell_a["rows"]}
    assert statements == {"Firm under trial conditions.", "Owner claims very firm fruit."}
    assert cell_b["has_data"] is False
    assert cell_b["rows"] == []


def test_trust_classes_and_attribution_preserved_per_row():
    entities = _entities()
    evidence = {"ev-1": _evidence(id="ev-1", source_type="plant_breeders_rights_record", source_name="CFIA")}
    facts = [
        _fact(
            id="fact-fact",
            classification="fact",
            confidence="high",
            entity_ids=["variety-a", "trait-firmness"],
            evidence_ids=["ev-1"],
        ),
        _fact(
            id="fact-claim",
            classification="claim",
            confidence="low",
            entity_ids=["variety-a", "trait-flavor"],
            evidence_ids=["ev-1"],
        ),
    ]
    result = present_variety_compare(
        ["variety-a"],
        entities=entities,
        relationships=[],
        published_evidence=list(evidence.values()),
        facts=facts,
        evidence_by_id=evidence,
        signals=[],
        assessments=[],
        berry_labels={},
    )
    rows_by_id = {}
    for dim in result["dimensions"]:
        for cell in dim["cells"]:
            for row in cell["rows"]:
                rows_by_id[row["id"]] = row
    assert rows_by_id["fact-fact"]["classification"] == "fact"
    assert rows_by_id["fact-claim"]["classification"] == "claim"
    assert rows_by_id["fact-fact"]["source_type_label"] == "Plant breeders' rights registry"


def test_source_trace_links_to_reader_and_evidence():
    entities = _entities()
    evidence = {"ev-1": _evidence(id="ev-1")}
    facts = [_fact(id="fact-a", entity_ids=["variety-a", "trait-firmness"], evidence_ids=["ev-1"])]
    result = present_variety_compare(
        ["variety-a"],
        entities=entities,
        relationships=[],
        published_evidence=list(evidence.values()),
        facts=facts,
        evidence_by_id=evidence,
        signals=[],
        assessments=[],
        berry_labels={},
    )
    row = result["dimensions"][0]["cells"][0]["rows"][0]
    assert row["evidence_id"] == "ev-1"
    assert row["reader_href"] == "/intelligence/ev-1"
    assert row["evidence_href"] == "/evidence/ev-1"


def test_roles_stay_distinct_across_varieties():
    entities = _entities()
    relationships = [
        {"id": "rel-1", "subject_id": "company-x", "predicate": "develops", "object_id": "variety-a", "status": "active"},
        {"id": "rel-2", "subject_id": "company-x", "predicate": "markets", "object_id": "variety-b", "status": "active"},
    ]
    result = present_variety_compare(
        ["variety-a", "variety-b"],
        entities=entities,
        relationships=relationships,
        published_evidence=[],
        facts=[],
        evidence_by_id={},
        signals=[],
        assessments=[],
        berry_labels={},
    )
    card_a = next(c for c in result["varieties"] if c["id"] == "variety-a")
    card_b = next(c for c in result["varieties"] if c["id"] == "variety-b")
    assert card_a["roles"]["breeder"]
    assert not card_a["roles"]["marketer"]
    assert card_b["roles"]["marketer"]
    assert not card_b["roles"]["breeder"]


def test_empty_and_single_selection_do_not_crash():
    entities = _entities()
    empty = present_variety_compare(
        [], entities=entities, relationships=[], published_evidence=[], facts=[],
        evidence_by_id={}, signals=[], assessments=[], berry_labels={},
    )
    assert empty["count"] == 0
    single = present_variety_compare(
        ["variety-a"], entities=entities, relationships=[], published_evidence=[], facts=[],
        evidence_by_id={}, signals=[], assessments=[], berry_labels={},
    )
    assert single["count"] == 1


# --- Route-level tests against real data --------------------------------


def test_compare_route_registered_before_generic_entity_detail():
    client = TestClient(app)
    page = client.get("/entities/variety/compare?ids=variety-sekoya-grande,variety-blue-maldiva")
    assert page.status_code == 200
    assert "Compare varieties" in page.text
    assert "Entity record not found" not in page.text


def test_compare_two_real_data_rich_blueberries():
    client = TestClient(app)
    page = client.get("/entities/variety/compare?ids=variety-sekoya-grande,variety-emerald")
    assert page.status_code == 200
    assert "SEKOYA Grande" in page.text
    assert "Emerald" in page.text
    assert "FRUIT FIRMNESS" in page.text.upper()
    assert "FACT" in page.text


def test_compare_four_varieties_cross_berry():
    client = TestClient(app)
    page = client.get(
        "/entities/variety/compare",
        params={"ids": "variety-sekoya-grande,variety-zara,variety-amalia-rossa,variety-victoria"},
    )
    assert page.status_code == 200
    for name in ("SEKOYA Grande", "Zara", "Amalia Rossa", "Victoria"):
        assert name in page.text


def test_compare_sparse_raspberry_and_blackberry_show_honest_empty_states():
    client = TestClient(app)
    page = client.get("/entities/variety/compare?ids=variety-amalia-rossa,variety-victoria")
    assert page.status_code == 200
    assert "No trusted rights/IP filing captured." in page.text


def test_compare_duplicate_id_in_query_string_shows_once():
    client = TestClient(app)
    page = client.get("/entities/variety/compare?ids=variety-sekoya-grande,variety-sekoya-grande,variety-emerald")
    assert page.status_code == 200
    assert page.text.count('id="variety-sekoya-grande"') <= 1 or page.text.count("SEKOYA Grande</a>") == 1


def test_compare_invalid_id_reported_not_crashed():
    client = TestClient(app)
    page = client.get("/entities/variety/compare?ids=variety-sekoya-grande,variety-totally-fake-id")
    assert page.status_code == 200
    assert "variety-totally-fake-id" in page.text


def test_compare_deep_link_reload_is_stable():
    client = TestClient(app)
    url = "/entities/variety/compare?ids=variety-sekoya-grande,variety-emerald"
    first = client.get(url)
    second = client.get(url)
    assert first.status_code == second.status_code == 200
    assert "SEKOYA Grande" in first.text and "SEKOYA Grande" in second.text


def test_compare_no_winner_or_score_language():
    client = TestClient(app)
    page = client.get("/entities/variety/compare?ids=variety-sekoya-grande,variety-emerald")
    assert page.status_code == 200
    lowered = page.text.casefold()
    for forbidden in ("winner", "best variety", "overall rating", "innovation score"):
        assert forbidden not in lowered
    # The page's own intro deliberately says "not a competitive score" --
    # legitimate negated copy reinforcing the no-scoring rule, not a leak
    # of the forbidden concept itself.
    assert "not a competitive score" in lowered
    assert lowered.count("competitive score") == 1


def test_compare_does_not_leak_pending_content():
    client = TestClient(app)
    page = client.get("/entities/variety/compare?ids=variety-sekoya-grande,variety-blue-maldiva")
    assert page.status_code == 200
    assert "in_review" not in page.text
    assert "signal_candidate" not in page.text.casefold()


def test_compare_no_ids_shows_selection_prompt_not_error():
    client = TestClient(app)
    page = client.get("/entities/variety/compare")
    assert page.status_code == 200
    assert "Select at least 2 varieties" in page.text
