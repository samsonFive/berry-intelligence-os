"""Company Compare V1 -- side-by-side trusted intelligence workspace."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.services.company_workspace import COMPARE_MAX_COMPANIES, present_company_compare


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
        _entity(id="company-a", entity_type="company", name="Company A", berry_ids=["berry-blueberry"]),
        _entity(id="company-b", entity_type="company", name="Company B", berry_ids=["berry-blueberry"]),
        _entity(id="company-sparse", entity_type="company", name="Company Sparse", berry_ids=["berry-raspberry"]),
        _entity(id="variety-x", entity_type="variety", name="Variety X", berry_ids=["berry-blueberry"]),
        _entity(id="variety-y", entity_type="variety", name="Variety Y", berry_ids=["berry-blueberry"]),
        _entity(id="trait-firmness", entity_type="trait", name="Fruit firmness"),
        _entity(id="geo-spain", entity_type="geography", name="Spain"),
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
        "entity_ids": [],
    }
    row.update(overrides)
    return row


def _compare(ids, entities=None, **kwargs):
    defaults = dict(
        entities=entities or _entities(),
        relationships=[],
        published_evidence=[],
        facts=[],
        evidence_by_id={},
        signals=[],
        assessments=[],
        berry_labels={"berry-blueberry": "Blueberry", "berry-raspberry": "Raspberry"},
    )
    defaults.update(kwargs)
    return present_company_compare(ids, **defaults)


def test_dedupes_and_caps_at_max_companies():
    result = _compare(["company-a", "company-a", "company-b", "company-sparse", "company-a"])
    ids = [card["id"] for card in result["companies"]]
    assert ids == ["company-a", "company-b", "company-sparse"]
    assert result["count"] == 3
    assert result["invalid_ids"] == []
    assert result["overflow_ids"] == []


def test_invalid_and_non_company_ids_are_reported_not_silently_dropped():
    result = _compare(["company-a", "company-missing", "variety-x"])
    assert [c["id"] for c in result["companies"]] == ["company-a"]
    assert set(result["invalid_ids"]) == {"company-missing", "variety-x"}


def test_overflow_beyond_max_is_reported():
    entities = _entities()
    entities["company-c"] = _entity(id="company-c", entity_type="company", name="Company C")
    entities["company-d"] = _entity(id="company-d", entity_type="company", name="Company D")
    entities["company-e"] = _entity(id="company-e", entity_type="company", name="Company E")
    result = _compare(
        ["company-a", "company-b", "company-c", "company-d", "company-e"], entities=entities
    )
    assert result["count"] == COMPARE_MAX_COMPANIES
    assert result["overflow_ids"] == ["company-e"]
    assert result["max_reached"] is True


def test_sparse_company_has_no_fabricated_portfolio_or_rights():
    result = _compare(["company-sparse"])
    card = result["companies"][0]
    assert card["coverage"]["evidence_count"] == 0
    assert card["coverage"]["variety_count"] == 0
    assert card["portfolio_variety_ids"] == []
    assert card["rights_published"] == []
    assert card["geographies"] == []
    assert result["role_matrix"] == []


def test_empty_and_single_selection_do_not_crash():
    empty = _compare([])
    assert empty["count"] == 0
    single = _compare(["company-a"])
    assert single["count"] == 1


def test_roles_stay_distinct_never_collapsed():
    relationships = [
        {"id": "rel-1", "subject_id": "company-a", "predicate": "develops", "object_id": "variety-x", "status": "active"},
        {"id": "rel-2", "subject_id": "company-b", "predicate": "markets", "object_id": "variety-y", "status": "active"},
    ]
    result = _compare(["company-a", "company-b"], relationships=relationships)
    card_a = next(c for c in result["companies"] if c["id"] == "company-a")
    card_b = next(c for c in result["companies"] if c["id"] == "company-b")
    assert card_a["roles"]["breeder"]
    assert not card_a["roles"]["marketer"]
    assert card_b["roles"]["marketer"]
    assert not card_b["roles"]["breeder"]
    # Role matrix only lists roles actually represented -- breeder and
    # marketer, never a generic "has variety" bucket.
    buckets = {row["bucket"] for row in result["role_matrix"]}
    assert buckets == {"breeder", "marketer"}


def test_variety_links_navigate_to_own_variety_profile():
    relationships = [
        {"id": "rel-1", "subject_id": "company-a", "predicate": "develops", "object_id": "variety-x", "status": "active"},
    ]
    result = _compare(["company-a"], relationships=relationships)
    card = result["companies"][0]
    party = card["roles"]["breeder"][0]
    assert party["id"] == "variety-x"
    assert party["href"] == "/entities/variety/variety-x"


def test_rights_and_geography_and_signals_and_assessments_preserved_per_kind():
    evidence = {
        "ev-1": _evidence(id="ev-1", source_type="plant_breeders_rights_record", entity_ids=["company-a"]),
    }
    relationships = [
        {"id": "rel-1", "subject_id": "company-a", "predicate": "operates_in", "object_id": "geo-spain", "status": "active"},
    ]
    signals = [{"id": "sig-1", "title": "A signal", "status": "open", "entity_ids": ["company-a"]}]
    assessments = [{"id": "as-1", "title": "An assessment", "confidence": "medium", "entity_ids": ["company-a"]}]
    result = _compare(
        ["company-a"],
        relationships=relationships,
        published_evidence=list(evidence.values()),
        evidence_by_id=evidence,
        signals=signals,
        assessments=assessments,
    )
    card = result["companies"][0]
    assert card["geographies"][0]["id"] == "geo-spain"
    assert card["signals"][0]["id"] == "sig-1"
    assert card["assessments"][0]["id"] == "as-1"
    assert card["coverage"]["signal_count"] == 1
    assert card["coverage"]["assessment_count"] == 1


def test_coverage_is_not_a_performance_score():
    result = _compare(["company-a", "company-sparse"])
    card_a = next(c for c in result["companies"] if c["id"] == "company-a")
    card_sparse = next(c for c in result["companies"] if c["id"] == "company-sparse")
    # Coverage is a plain dict of counts -- no "score" field of any kind.
    assert "score" not in card_a["coverage"]
    assert "score" not in card_sparse["coverage"]


# --- Route-level tests against real data --------------------------------


def test_compare_route_registered_before_generic_entity_detail():
    client = TestClient(app)
    page = client.get("/entities/company/compare?ids=company-planasa,company-costa-group-holdings")
    assert page.status_code == 200
    assert "Compare companies" in page.text
    assert "Entity record not found" not in page.text


def test_compare_two_real_data_rich_companies_planasa_vs_costa():
    client = TestClient(app)
    page = client.get("/entities/company/compare?ids=company-planasa,company-costa-group-holdings")
    assert page.status_code == 200
    assert "Plantas de Navarra" in page.text
    assert "Costa Group Holdings" in page.text
    assert "Breeder" in page.text
    assert "Blue Manila" in page.text or "Blue Maldiva" in page.text


def test_compare_four_companies_including_data_rich_and_sparse():
    client = TestClient(app)
    page = client.get(
        "/entities/company/compare",
        params={
            "ids": "company-planasa,company-costa-group-holdings,"
            "company-fall-creek-farm-and-nursery,company-sanlucar"
        },
    )
    assert page.status_code == 200
    for name in ("Plantas de Navarra", "Costa Group Holdings", "Fall Creek Farm", "SanLucar"):
        assert name in page.text
    assert "No trusted Variety relationship captured." in page.text


def test_compare_sparse_company_shows_honest_empty_states():
    client = TestClient(app)
    page = client.get("/entities/company/compare?ids=company-sanlucar,company-planasa")
    assert page.status_code == 200
    assert "No trusted Variety relationship captured." in page.text
    assert "No trusted rights/IP filing captured." in page.text


def test_compare_duplicate_id_shows_once():
    client = TestClient(app)
    page = client.get(
        "/entities/company/compare?ids=company-planasa,company-planasa,company-costa-group-holdings"
    )
    assert page.status_code == 200
    assert page.text.count("Plantas de Navarra, S.A.</a>") == 1


def test_compare_invalid_id_reported_not_crashed():
    client = TestClient(app)
    page = client.get("/entities/company/compare?ids=company-planasa,company-totally-fake-id")
    assert page.status_code == 200
    assert "company-totally-fake-id" in page.text
    assert "Not found or not a Company" in page.text


def test_compare_overflow_beyond_four_reported():
    client = TestClient(app)
    page = client.get(
        "/entities/company/compare",
        params={
            "ids": "company-planasa,company-costa-group-holdings,"
            "company-fall-creek-farm-and-nursery,company-sanlucar,company-driscolls"
        },
    )
    assert page.status_code == 200
    assert "Only the first 4 selected ids are compared" in page.text
    assert "company-driscolls" in page.text


def test_compare_deep_link_reload_is_stable():
    client = TestClient(app)
    url = "/entities/company/compare?ids=company-planasa,company-costa-group-holdings"
    first = client.get(url)
    second = client.get(url)
    assert first.status_code == second.status_code == 200
    assert "Plantas de Navarra" in first.text and "Plantas de Navarra" in second.text


def test_compare_deep_link_into_variety_compare_uses_real_ids():
    client = TestClient(app)
    page = client.get("/entities/company/compare?ids=company-planasa,company-costa-group-holdings")
    assert page.status_code == 200
    assert "/entities/variety/compare?ids=" in page.text
    assert "Compare Plantas de Navarra" in page.text


def test_compare_geography_and_rights_copy_is_honest():
    client = TestClient(app)
    page = client.get("/entities/company/compare?ids=company-planasa,company-costa-group-holdings")
    assert page.status_code == 200
    assert "Geographies represented in trusted intelligence" in page.text
    assert "Filing counts, not innovation quality" in page.text
    assert "captured coverage, not total real-world portfolio size" in page.text


def test_compare_no_winner_or_score_language():
    client = TestClient(app)
    page = client.get("/entities/company/compare?ids=company-planasa,company-costa-group-holdings")
    assert page.status_code == 200
    lowered = page.text.casefold()
    for forbidden in (
        "winner",
        "best company",
        "competitive strength",
        "innovation score",
        "portfolio score",
        "threat score",
        "momentum score",
        "overall rating",
    ):
        assert forbidden not in lowered
    # The page's own intro deliberately says "not a competitive score" --
    # legitimate negated copy reinforcing the no-scoring rule, not a leak.
    assert "not a competitive score" in lowered
    assert lowered.count("competitive score") == 1


def test_compare_does_not_leak_pending_content():
    client = TestClient(app)
    page = client.get("/entities/company/compare?ids=company-planasa,company-costa-group-holdings")
    assert page.status_code == 200
    assert "in_review" not in page.text
    assert "signal_candidate" not in page.text.casefold()


def test_compare_no_ids_shows_selection_prompt_not_error():
    client = TestClient(app)
    page = client.get("/entities/company/compare")
    assert page.status_code == 200
    assert "Select at least 2 companies" in page.text


def test_company_profile_has_compare_link():
    client = TestClient(app)
    page = client.get("/entities/company/company-planasa")
    assert page.status_code == 200
    assert "/entities/company/compare?ids=company-planasa" in page.text


def test_company_index_has_compare_links():
    client = TestClient(app)
    page = client.get("/entities/company")
    assert page.status_code == 200
    assert "/entities/company/compare?ids=" in page.text
