"""Geography / Market Intelligence V1 -- captured intelligence about a
place, never a claim about total real-world market activity."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.services.geography_workspace import geography_detail, geography_index


def _entity(**overrides):
    row = {
        "record_type": "entity",
        "status": "active",
        "aliases": [],
        "berry_ids": [],
        "attributes": {},
        "description": "",
    }
    row.update(overrides)
    return row


def _entities():
    rows = [
        _entity(
            id="geography-spain",
            entity_type="geography",
            name="Spain",
            berry_ids=["berry-blueberry"],
            attributes={"iso_3166_1_alpha_2": "ES"},
        ),
        _entity(id="geography-europe", entity_type="geography", name="Europe", berry_ids=["berry-raspberry"]),
        _entity(
            id="geography-sparse",
            entity_type="geography",
            name="Sparseland",
            attributes={"iso_3166_1_alpha_2": "SP"},
        ),
        _entity(id="company-a", entity_type="company", name="Company A", berry_ids=["berry-blueberry"]),
        _entity(id="variety-x", entity_type="variety", name="Variety X", berry_ids=["berry-blueberry"]),
        _entity(id="retailer-r", entity_type="retailer", name="Retailer R"),
    ]
    return {row["id"]: row for row in rows}


def _relationships():
    return [{"subject_id": "company-a", "predicate": "operates_in", "object_id": "geography-spain"}]


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


def _index(entities=None, **kwargs):
    defaults = dict(
        entities=entities or _entities(),
        published_evidence=[],
        relationships=_relationships(),
        signals=[],
        berry_labels={"berry-blueberry": "Blueberry", "berry-raspberry": "Raspberry"},
    )
    defaults.update(kwargs)
    return geography_index(**defaults)


def _detail(geography_id, entities=None, **kwargs):
    defaults = dict(
        entities=entities or _entities(),
        relationships=_relationships(),
        published_evidence=[],
        signals=[],
        assessments=[],
        berry_labels={"berry-blueberry": "Blueberry", "berry-raspberry": "Raspberry"},
    )
    defaults.update(kwargs)
    return geography_detail(geography_id, **defaults)


# --- Presenter unit tests (synthetic fixtures) ---


def test_unknown_geography_id_returns_none():
    assert _detail("geography-does-not-exist") is None


def test_company_id_used_as_geography_id_returns_none():
    assert _detail("company-a") is None


def test_index_lists_all_geographies_sorted_by_name():
    rows = _index()
    names = [r["name"] for r in rows]
    assert names == sorted(names)
    assert "Spain" in names


def test_index_country_vs_region_type_from_iso_code():
    rows = {r["id"]: r for r in _index()}
    assert rows["geography-spain"]["type"] == "Country"
    assert rows["geography-europe"]["type"] == "Region / other"


def test_actor_via_operates_in_relationship_is_counted():
    result = _detail("geography-spain")
    assert result["coverage"]["company_count"] == 1
    assert result["actors"][0]["id"] == "company-a"
    assert result["actors"][0]["has_operates_in_relationship"] is True


def test_actor_via_evidence_entity_ids_is_also_counted():
    evidence = [_evidence(id="ev-1", entity_ids=["geography-europe", "company-a"])]
    result = _detail("geography-europe", published_evidence=evidence)
    assert result["coverage"]["company_count"] == 1
    assert result["actors"][0]["has_operates_in_relationship"] is False


def test_variety_grounding_via_evidence():
    evidence = [_evidence(id="ev-1", entity_ids=["geography-spain", "variety-x"])]
    result = _detail("geography-spain", published_evidence=evidence)
    assert result["coverage"]["variety_count"] == 1
    assert result["varieties"][0]["id"] == "variety-x"


def test_rights_and_commercial_kept_as_separate_lists():
    evidence = [
        _evidence(id="ev-rights", source_type="plant_breeders_rights_record", entity_ids=["geography-spain"]),
        _evidence(
            id="ev-commercial",
            entity_ids=["geography-spain"],
            intake_type="commercial_observation",
            commercial_observation={"retailer_entity_id": "retailer-r", "observed_at": "2026-02-01"},
        ),
    ]
    result = _detail("geography-spain", published_evidence=evidence)
    assert len(result["rights_records"]) == 1
    assert len(result["commercial_records"]) == 1
    assert result["commercial_records"][0]["retailer"]["name"] == "Retailer R"


def test_sparse_geography_has_zero_coverage_not_error():
    result = _detail("geography-sparse")
    assert result["coverage"]["evidence_count"] == 0
    assert result["coverage"]["company_count"] == 0
    assert result["varieties"] == []
    assert result["actors"] == []


def test_recent_moves_bounded_and_sorted_descending():
    evidence = [
        _evidence(id="ev-1", entity_ids=["geography-spain"], published_date="2026-01-01"),
        _evidence(id="ev-2", entity_ids=["geography-spain"], published_date="2026-06-01"),
    ]
    result = _detail("geography-spain", published_evidence=evidence)
    dates = [m["date"] for m in result["recent_moves"]]
    assert dates == sorted(dates, reverse=True)
    assert dates[0] == "2026-06-01"


def test_region_rollup_links_to_matching_region_entity():
    result = _detail("geography-spain")
    # Spain's REGION_LOOKUP-derived region is "Europe", and a Geography
    # entity literally named "Europe" exists in the fixture -- real rollup.
    assert result["region_href"] == "/geographies/geography-europe"
    assert result["region_name"] == "Europe"


def test_no_hierarchy_invented_when_no_matching_entity_exists():
    # Sparseland has no ISO-derivable region and no matching entity.
    result = _detail("geography-sparse")
    assert result["region_href"] == ""


def test_no_market_score_fields_in_result():
    result = _detail("geography-spain")
    forbidden_keys = {"market_attractiveness", "competitive_intensity", "market_score", "opportunity_score"}
    assert not (forbidden_keys & set(result.keys()))
    assert not (forbidden_keys & set(result["coverage"].keys()))


# --- Route-level tests against real production data ---


def test_geography_index_route_real_data():
    client = TestClient(app)
    page = client.get("/geographies")
    assert page.status_code == 200
    assert "Spain" in page.text
    assert "Not complete market reality" in page.text or "not complete market reality" in page.text.casefold()


def test_geography_detail_data_rich_spain():
    client = TestClient(app)
    page = client.get("/geographies/geography-spain")
    assert page.status_code == 200
    assert "Spain" in page.text


def test_geography_detail_data_rich_peru():
    client = TestClient(app)
    page = client.get("/geographies/geography-peru")
    assert page.status_code == 200
    assert "Peru" in page.text


def test_geography_detail_caneberry_relevant_united_kingdom():
    client = TestClient(app)
    page = client.get("/geographies/geography-united-kingdom")
    assert page.status_code == 200
    assert "United Kingdom" in page.text


def test_geography_detail_sparse_geography_honest_copy():
    client = TestClient(app)
    page = client.get("/geographies/geography-zambia")
    assert page.status_code == 200
    assert "Limited trusted intelligence" in page.text or "No trusted" in page.text


def test_geography_detail_invalid_id_is_404():
    client = TestClient(app)
    page = client.get("/geographies/geography-totally-fake-id")
    assert page.status_code == 404


def test_geography_detail_non_geography_id_is_404():
    client = TestClient(app)
    page = client.get("/geographies/company-planasa")
    assert page.status_code == 404


def test_geography_route_registered_before_generic_entity_catchall():
    client = TestClient(app)
    page = client.get("/geographies/geography-spain")
    assert page.status_code == 200
    assert "Entity record not found" not in page.text


def test_geography_no_market_score_language():
    client = TestClient(app)
    page = client.get("/geographies/geography-spain")
    assert page.status_code == 200
    lowered = page.text.casefold()
    for forbidden in (
        "market attractiveness",
        "competitive intensity",
        "market opportunity score",
        "market power score",
        "winner",
        "best market",
        "threat score",
    ):
        assert forbidden not in lowered


def test_geography_does_not_leak_pending_content():
    client = TestClient(app)
    page = client.get("/geographies/geography-spain")
    assert page.status_code == 200
    assert "in_review" not in page.text
    assert "signal_candidate" not in page.text.casefold()


def test_geography_uses_card_grid_not_wide_table():
    client = TestClient(app)
    page = client.get("/geographies/geography-spain")
    assert page.status_code == 200
    assert "<table" not in page.text
    assert "balanced-card-grid" in page.text


def test_geography_actor_links_to_company_portfolio():
    client = TestClient(app)
    page = client.get("/geographies/geography-spain")
    assert page.status_code == 200
    assert "/portfolio" in page.text


def test_company_profile_links_to_geography_intelligence():
    client = TestClient(app)
    page = client.get("/entities/company/company-planasa")
    assert page.status_code == 200
    assert "/geographies/" in page.text


def test_geography_deep_link_reload_is_stable():
    client = TestClient(app)
    url = "/geographies/geography-spain"
    first = client.get(url)
    second = client.get(url)
    assert first.status_code == second.status_code == 200
    assert "Spain" in first.text and "Spain" in second.text
