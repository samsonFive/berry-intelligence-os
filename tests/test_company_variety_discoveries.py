"""Source recall reaches company context without inventing trusted portfolios."""
from copy import deepcopy
from urllib.parse import parse_qs, urlsplit

from fastapi.testclient import TestClient

from app import main
from app.services.company_variety_discoveries import company_variety_discoveries
from app.services.variety_portfolio_coverage import reconcile_portfolios, load_portfolio_observations


def source(identifier, names, company="company-a", **changes):
    return {"id": identifier, "title": identifier, "url": "https://example.com/" + identifier,
            "checked_on": "2026-10-07", "capture_status": "names_enumerated",
            "source_type": "breeder_catalog", "company_ids": [company],
            "berry_ids": ["berry-blueberry"], "names": names, **changes}


def observation(name, **changes):
    return {"candidate_name": name, "berry_id": "berry-blueberry", **changes}


def model(sources, *, varieties=(), candidates=(), linked=()):
    reconciled, _ = reconcile_portfolios(sources=sources, varieties=list(varieties), candidates=list(candidates),
        entities=[{"id": "company-a", "name": "Company A", "entity_type": "company"}])
    return company_variety_discoveries(entity_id="company-a", sources=reconciled, linked_variety_ids=linked)


def test_repeated_sources_deduplicate_but_codes_and_crops_stay_separate():
    rows = [observation("Pink Star", breeder_code="MAR502", trade_name="Pink Star"),
            observation("Pink Star", breeder_code="MAR506", trade_name="Pink Star"),
            observation("Pink Star", berry_id="berry-raspberry")]
    sources = [source("a", rows), source("b", [rows[0]]), source("unrelated", [observation("Elsewhere")], company="company-b")]
    before = deepcopy(sources)
    result = model(sources)
    assert len(result["rows"]) == 3
    assert result["source_count"] == 2
    coded = {row["code"]: row for row in result["rows"] if row["code"]}
    assert set(coded) == {"MAR502", "MAR506"}
    assert len(coded["MAR502"]["sources"]) == 2
    assert all(row["notes"] for row in coded.values())
    assert all(row["label"] == "Name / code conflict" for row in coded.values())
    params = parse_qs(urlsplit(coded["MAR502"]["href"]).query)
    assert params["company"] == ["company-a"] and params["source"] == ["b"]
    assert urlsplit(coded["MAR502"]["href"]).fragment.startswith("vcand-")
    assert sources == before


def test_catalog_match_does_not_become_reviewed_company_link():
    variety = {"id": "variety-known", "name": "Known", "entity_type": "variety", "berry_ids": ["berry-blueberry"], "aliases": []}
    result = model([source("a", [observation("Known")])], varieties=[variety])
    assert result["rows"][0]["label"] == "Company link needs review"
    assert result["rows"][0]["href"] == "/entities/variety/variety-known"
    reviewed = model([source("a", [observation("Known")])], varieties=[variety], linked={"variety-known"})
    assert reviewed["rows"] == [] and reviewed["linked_count"] == 1


def test_human_rejection_remains_closed_and_unreadable_is_a_gap():
    candidates = [{"id": "vcand-rejected", "candidate_name": "Closed", "berry_id": "berry-blueberry",
                   "status": "rejected", "identity_state": "rejected", "human_gated": True, "notes": "Keep my decision"}]
    before = deepcopy(candidates)
    result = model([source("a", [observation("Closed")]), source("failed", [], capture_status="unreadable")], candidates=candidates)
    assert result["rows"] == [] and result["rejected_count"] == 1
    assert result["follow_up_count"] == 1 and result["source_count"] == 2
    assert candidates == before


def test_recommendation_is_labelled_and_invalid_product_link_falls_back():
    result = model([source("extension", [observation("Von", product_url="javascript:alert(1)")], source_type="extension_recommendation")])
    assert result["rows"][0]["sources"][0]["context"] == "Recommendation list"
    assert result["rows"][0]["sources"][0]["href"] == "https://example.com/extension"


def test_company_views_surface_hortifrut_source_names_without_writes(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    client = TestClient(main.app)
    for url in ("/entities/company/company-hortifrut?tab=varieties", "/entities/company/company-hortifrut/portfolio"):
        page = client.get(url)
        assert page.status_code == 200
        assert "Varieties named in sources" in page.text and "Daybreak" in page.text
        assert "Being named here does not confirm" in page.text
        assert "data-source-letter=" in page.text and "data-source-search" in page.text
    assert not list(tmp_path.iterdir())


def test_public_company_views_never_read_private_candidate_universe(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    def forbidden():
        raise AssertionError("Public company views must not load private discoveries")
    monkeypatch.setattr(main, "variety_candidate_universe", forbidden)
    client = TestClient(main.app)
    for url in ("/entities/company/company-hortifrut?tab=varieties", "/entities/company/company-hortifrut/portfolio"):
        page = client.get(url)
        assert page.status_code == 200
        assert "data-company-source-varieties" not in page.text and "company_variety_discoveries.js" not in page.text
        assert "Check the source discoveries below" not in page.text
    assert not list(tmp_path.iterdir())


def test_loading_failure_is_not_a_false_empty_portfolio(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    monkeypatch.setattr(main, "variety_candidate_universe", lambda: ([], [], {"portfolio_error": "internal file details"}))
    page = TestClient(main.app).get("/entities/company/company-hortifrut?tab=varieties")
    assert page.status_code == 200 and "source-name list could not be loaded" in page.text
    assert "internal file details" not in page.text


def test_actual_fnm_sources_include_licensed_and_extension_boundaries(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    sources = load_portfolio_observations(main.DATA_DIR)
    fnm = next(row for row in sources if row["id"] == "portfolio-fnm-current-variety-index")
    result = main.company_source_varieties(fnm["company_ids"][0], None)
    assert any(row["name"] == "Divine" for row in result["rows"])
    assert any("exclusiv" in note.casefold() for row in result["rows"] for note in row["notes"])
    assert not list(tmp_path.iterdir())


def test_static_template_hides_private_projection_even_if_supplied():
    html = main.templates.env.get_template("_company_variety_discoveries.html").render(
        authoring_mode=True, static_build=True, company_source_varieties={"rows": [{"name": "Private fixture"}]})
    assert "Private fixture" not in html and "data-company-source-varieties" not in html
