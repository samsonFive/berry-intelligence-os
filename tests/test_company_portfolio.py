"""Company Variety Portfolio Intelligence V1 -- one Company's derived
Variety/genetics portfolio."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.services.company_workspace import present_company_portfolio


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
        _entity(id="company-sparse", entity_type="company", name="Company Sparse", berry_ids=["berry-raspberry"]),
        _entity(
            id="variety-multi",
            entity_type="variety",
            name="Variety Multi-Role",
            berry_ids=["berry-blueberry"],
        ),
        _entity(id="variety-second", entity_type="variety", name="Variety Second", berry_ids=["berry-strawberry"]),
        _entity(id="geo-spain", entity_type="geography", name="Spain"),
    ]
    return {row["id"]: row for row in rows}


def _relationships():
    return [
        {"subject_id": "company-a", "predicate": "develops", "object_id": "variety-multi"},
        {"subject_id": "company-a", "predicate": "owns", "object_id": "variety-multi"},
        {"subject_id": "company-a", "predicate": "markets", "object_id": "variety-second"},
    ]


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


def _portfolio(company_id, entities=None, **kwargs):
    defaults = dict(
        entities=entities or _entities(),
        relationships=_relationships(),
        published_evidence=[],
        facts=[],
        evidence_by_id={},
        signals=[],
        assessments=[],
        berry_labels={"berry-blueberry": "Blueberry", "berry-strawberry": "Strawberry", "berry-raspberry": "Raspberry"},
    )
    defaults.update(kwargs)
    return present_company_portfolio(company_id, **defaults)


def test_unknown_company_id_returns_none():
    assert _portfolio("company-does-not-exist") is None


def test_variety_id_used_as_company_id_returns_none():
    assert _portfolio("variety-multi") is None


def test_variety_with_multiple_roles_shows_both_distinctly():
    result = _portfolio("company-a")
    row = next(r for r in result["variety_rows"] if r["id"] == "variety-multi")
    assert set(row["roles"]) == {"Breeder", "Owner / rights holder"}


def test_single_role_variety_shows_one_role():
    result = _portfolio("company-a")
    row = next(r for r in result["variety_rows"] if r["id"] == "variety-second")
    assert row["roles"] == ["Marketer"]


def test_berry_grouping_separates_varieties_by_berry():
    result = _portfolio("company-a")
    ids_by_berry = {g["id"]: [r["id"] for r in g["rows"]] for g in result["berry_groups"]}
    assert ids_by_berry["berry-blueberry"] == ["variety-multi"]
    assert ids_by_berry["berry-strawberry"] == ["variety-second"]


def test_sparse_company_has_zero_coverage_not_error():
    result = _portfolio("company-sparse")
    assert result["coverage"]["total_varieties"] == 0
    assert result["coverage"]["varieties_sparse"] == 0
    assert result["variety_rows"] == []


def test_rights_and_commercial_are_tracked_separately():
    evidence = [
        _evidence(id="ev-rights", source_type="plant_breeders_rights_record", entity_ids=["variety-multi"]),
    ]
    result = _portfolio("company-a", published_evidence=evidence)
    row = next(r for r in result["variety_rows"] if r["id"] == "variety-multi")
    assert row["rights_count"] == 1
    assert row["commercial_observation_count"] == 0


def test_coverage_counts_varieties_with_evidence_and_sparse_separately():
    evidence = [_evidence(id="ev-1", entity_ids=["variety-multi"])]
    result = _portfolio("company-a", published_evidence=evidence)
    assert result["coverage"]["varieties_with_evidence"] == 1
    assert result["coverage"]["varieties_sparse"] == 1  # variety-second has nothing captured


def test_recent_moves_bounded_and_sorted_descending():
    evidence = [
        _evidence(id="ev-rights-1", source_type="plant_breeders_rights_record", entity_ids=["variety-multi"], published_date="2026-01-01"),
        _evidence(id="ev-rights-2", source_type="plant_breeders_rights_record", entity_ids=["variety-second"], published_date="2026-06-01"),
    ]
    result = _portfolio("company-a", published_evidence=evidence)
    dates = [m["date"] for m in result["recent_moves"]]
    assert dates == sorted(dates, reverse=True)
    assert dates[0] == "2026-06-01"


def test_source_mix_humanizes_source_types():
    evidence = [_evidence(id="ev-1", source_type="trade_press", entity_ids=["variety-multi"])]
    result = _portfolio("company-a", published_evidence=evidence)
    labels = dict(result["source_type_counts"])
    assert any("Trade" in label or "trade" in label for label in labels)


def test_no_forbidden_scoring_fields_in_result():
    result = _portfolio("company-a")
    forbidden_keys = {"score", "rank", "strength", "threat_score", "innovation_score"}
    assert not (forbidden_keys & set(result.keys()))
    for row in result["variety_rows"]:
        assert not (forbidden_keys & set(row.keys()))


# --- Route-level tests against real production data ---


def test_portfolio_route_registered_before_generic_entity_detail():
    client = TestClient(app)
    page = client.get("/entities/company/company-planasa/portfolio")
    assert page.status_code == 200
    assert "Entity record not found" not in page.text
    assert "VARIETY PORTFOLIO" in page.text


def test_portfolio_data_rich_company_planasa_shows_real_varieties():
    client = TestClient(app)
    page = client.get("/entities/company/company-planasa/portfolio")
    assert page.status_code == 200
    assert "Plantas de Navarra" in page.text
    assert "BREEDER" in page.text


def test_portfolio_driscolls_shows_multi_role_variety_distinctly():
    client = TestClient(app)
    page = client.get("/entities/company/company-driscolls/portfolio")
    assert page.status_code == 200
    assert "BREEDER" in page.text
    assert "OWNER / RIGHTS HOLDER" in page.text


def test_portfolio_sparse_company_shows_honest_empty_state():
    client = TestClient(app)
    page = client.get("/entities/company/company-sanlucar/portfolio")
    assert page.status_code == 200
    assert "No trusted Variety relationship captured" in page.text


def test_portfolio_invalid_company_id_is_404():
    client = TestClient(app)
    page = client.get("/entities/company/company-totally-fake-id/portfolio")
    assert page.status_code == 404


def test_portfolio_variety_id_as_company_id_is_404():
    client = TestClient(app)
    page = client.get("/entities/company/variety-drisblueseventeen/portfolio")
    assert page.status_code == 404


def test_portfolio_no_winner_or_score_language():
    client = TestClient(app)
    page = client.get("/entities/company/company-planasa/portfolio")
    assert page.status_code == 200
    lowered = page.text.casefold()
    for forbidden in (
        "winner",
        "best company",
        "competitive strength",
        "innovation score",
        "portfolio score",
        "portfolio strength",
        "threat score",
        "momentum score",
        "genetics score",
        "market power",
        "overall rating",
    ):
        assert forbidden not in lowered


def test_portfolio_does_not_leak_pending_content():
    client = TestClient(app)
    page = client.get("/entities/company/company-planasa/portfolio")
    assert page.status_code == 200
    assert "in_review" not in page.text
    assert "signal_candidate" not in page.text.casefold()


def test_portfolio_uses_card_grid_not_wide_table():
    client = TestClient(app)
    page = client.get("/entities/company/company-planasa/portfolio")
    assert page.status_code == 200
    assert "<table" not in page.text
    assert "balanced-card-grid" in page.text


def test_portfolio_deep_link_reload_is_stable():
    client = TestClient(app)
    url = "/entities/company/company-planasa/portfolio"
    first = client.get(url)
    second = client.get(url)
    assert first.status_code == second.status_code == 200
    assert "Plantas de Navarra" in first.text and "Plantas de Navarra" in second.text


def test_portfolio_links_to_company_profile_and_compare():
    client = TestClient(app)
    page = client.get("/entities/company/company-planasa/portfolio")
    assert page.status_code == 200
    assert "/entities/company/company-planasa\"" in page.text
    assert "/entities/company/compare?ids=company-planasa" in page.text


def test_company_profile_has_portfolio_link():
    client = TestClient(app)
    page = client.get("/entities/company/company-planasa")
    assert page.status_code == 200
    assert "/entities/company/company-planasa/portfolio" in page.text


def test_company_compare_has_portfolio_links():
    client = TestClient(app)
    page = client.get("/entities/company/compare?ids=company-planasa,company-costa-group-holdings")
    assert page.status_code == 200
    assert "/entities/company/company-planasa/portfolio" in page.text


def test_company_index_has_portfolio_links():
    client = TestClient(app)
    page = client.get("/entities/company")
    assert page.status_code == 200
    assert "/portfolio" in page.text


def test_landscape_all_links_to_company_portfolio():
    client = TestClient(app)
    page = client.get("/landscapes")
    assert page.status_code == 200
    assert "View portfolio" in page.text or "/portfolio" in page.text


def test_brief_pack_links_to_company_portfolio():
    client = TestClient(app)
    page = client.get(
        "/brief-pack",
        params={"companies": "company-planasa,company-costa-group-holdings"},
    )
    assert page.status_code == 200
    assert "/entities/company/company-planasa/portfolio" in page.text
