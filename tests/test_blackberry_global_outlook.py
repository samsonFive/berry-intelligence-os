"""Leadership research remains sourced, scoped and separate from canonical data."""
from copy import deepcopy
from datetime import date
import json

from fastapi import HTTPException, Request
import pytest

from app.services import blackberry_global_outlook as outlook


@pytest.fixture
def research():
    return {"schema_version": 1, "as_of": "2026-11-16", "season": "2027",
            "title": "Global blackberry outlook 2027",
            "sources": [{"id": "source-a", "title": "Primary license announcement", "url": "https://example.org/license",
                         "publisher": "Example breeder", "published_date": "2026-09-01"},
                        {"id": "source-b", "title": "Grower supply account", "url": "https://example.org/supply", "publisher": "Example grower"}],
            "executive_findings": [{"title": "Access and planting differ", "text": "A license is an access commitment.",
                                    "implication": "Compare the stated scope.", "source_ids": ["source-a"]}],
            "companies": [{"id": "example", "entity_id": "company-example", "name": "Example Berries", "roles": ["Licensor"],
                           "summary": "License holder", "source_ids": ["source-a"]}],
            "varieties": [{"id": "first", "entity_id": "variety-first", "name": "First", "aliases": ["NC 999"],
                           "habit": "floricane", "regions": ["europe"], "company_ids": ["example"],
                           "notable_reason": "International licensing", "outlook_2027": "Stock remains unconfirmed.", "source_ids": ["source-a"]},
                          {"id": "second", "entity_id": "variety-second", "name": "Second", "habit": "primocane",
                           "regions": ["latin-america"], "company_ids": ["example"], "source_ids": ["source-b"]}],
            "commitments": [{"id": "license", "title": "European development license", "category": "license",
                             "date": "2026-09-01", "variety_ids": ["first"], "company_ids": ["example"], "regions": ["europe"],
                             "countries": ["Development outside the US"], "summary": "Development rights announced.",
                             "scale": "", "scope_limit": "No planted hectares disclosed.", "implication": "Access is distinct from planting.", "source_ids": ["source-a"]},
                            {"id": "supply", "title": "Existing supply", "category": "commercial_supply", "variety_ids": ["second"],
                             "company_ids": ["example"], "regions": ["latin-america"], "source_ids": ["source-b"]}],
            "developments": [{"id": "license-news", "title": "License announced", "date": "2026-09-01", "variety_ids": ["first"],
                              "company_ids": ["example"], "regions": ["europe"], "source_ids": ["source-a"]}],
            "regions": [{"id": "europe", "name": "Europe", "summary": "Development access", "source_ids": ["source-a"]},
                        {"id": "latin-america", "name": "Latin America", "summary": "Supply context", "source_ids": ["source-b"]}],
            "report": {"id": "global-blackberry-outlook-2027"}, "limitations": ["2027 stock is not confirmed."]}


@pytest.fixture
def entities():
    return {"company-example": {"id": "company-example", "entity_type": "company", "name": "Example Berries"},
            "variety-first": {"id": "variety-first", "entity_type": "variety", "name": "First", "berry_ids": ["berry-blackberry"]},
            "variety-second": {"id": "variety-second", "entity_type": "variety", "name": "Second", "berry_ids": ["berry-raspberry"]}}


def test_combined_filters_preserve_commitment_scope_without_inventing_planting(research, entities):
    before = deepcopy(research)
    view = outlook.model(research, {"habit": "floricane", "region": "europe", "category": "license"}, entities)
    assert [row["id"] for row in view["varieties"]] == ["first"]
    assert [row["id"] for row in view["commitments"]] == ["license"]
    assert view["commitments"][0]["scale"] == ""
    assert view["commitments"][0]["scope_limit"] == "No planted hectares disclosed."
    assert research == before
    assert not outlook.model(research, {"habit": "primocane", "category": "license"}, entities)["commitments"]


def test_code_search_and_company_focus_are_reusable_and_crop_safe(research, entities):
    view = outlook.model(research, {"q": "NC 999"}, entities)
    assert [row["id"] for row in view["varieties"]] == ["first"]
    assert view["varieties"][0]["profile_href"] == "/entities/variety/variety-first"
    assert outlook.model(research, {}, entities)["varieties"][1]["profile_href"] == ""
    focus = outlook.model(research, {"company": "example"}, entities)
    assert focus["selected_company"]["name"] == "Example Berries"
    assert "company=example" in focus["clear_focus_href"] or focus["clear_focus_href"] == outlook.PATH


def test_specific_variety_focus_retains_its_local_detail_and_sources(research, entities):
    view = outlook.model(research, {"variety": "second"}, entities)
    assert view["selected_variety"]["name"] == "Second"
    assert view["selected_variety"]["profile_href"] == ""
    assert [row["id"] for row in view["commitments"]] == ["supply"]
    assert view["selected_variety"]["sources"][0]["url"] == "https://example.org/supply"


@pytest.mark.parametrize("filters", [{"habit": "mixed-up"}, {"category": "market-share"}, {"region": "mars"}, {"company": "missing"}, {"variety": "missing"}])
def test_unsupported_scope_is_not_silently_broadened(research, entities, filters):
    with pytest.raises(ValueError):
        outlook.model(research, filters, entities)


def test_source_and_report_links_cannot_become_script_or_arbitrary_paths(research, entities):
    research["sources"][0]["url"] = "javascript:alert(1)"
    research["report"]["id"] = "../private"
    research["varieties"][0]["report_url"] = "javascript:alert(2)"
    view = outlook.model(research, {}, entities)
    assert not view["sources"][0]["url"]
    assert not view["report"]
    assert not view["varieties"][0]["report_href"]


def test_news_uses_unreviewed_information_and_original_dates_without_cross_crop_leak(research, entities):
    view = outlook.model(research, {"variety": "first"}, entities)
    records = [{"id": "old", "title": "Older", "published_date": "2026-01-01", "captured_date": "2026-11-16",
                "entity_ids": ["variety-first"], "berry_ids": ["berry-blackberry"], "status": "published"},
               {"id": "new", "title": "Unreviewed latest", "published_date": "2026-11-15", "entity_ids": ["variety-first"],
                "berry_ids": ["berry-blackberry"], "status": "unreviewed"},
               {"id": "other-genetics", "published_date": "2026-11-16", "entity_ids": ["company-example"], "berry_ids": ["berry-blackberry"]},
               {"id": "other-crop", "published_date": "2026-11-16", "entity_ids": ["variety-first"], "berry_ids": ["berry-raspberry"]},
               {"id": "future", "published_date": "2027-01-01", "entity_ids": ["variety-first"]},
               {"id": "rejected", "published_date": "2026-11-16", "entity_ids": ["variety-first"], "status": "rejected"},
               {"id": "exact-primary", "source_url": "https://example.org/license", "published_date": "2026-09-01"},
               {"id": "undated", "captured_date": "2026-11-16", "entity_ids": ["variety-first"]}]
    selected, total = outlook.related_news(records, view, today=date(2026, 11, 16))
    assert [row["id"] for row in selected] == ["new", "exact-primary", "old", "undated"]
    assert total == 4


def test_package_is_read_only_and_duplicate_ids_fail_closed(tmp_path, research):
    assert outlook.load(tmp_path) is None
    target = tmp_path / outlook.PACKAGE
    target.parent.mkdir()
    target.write_text(json.dumps(research), encoding="utf-8")
    before = target.read_bytes()
    assert outlook.load(tmp_path)["season"] == "2027"
    assert target.read_bytes() == before
    research["sources"].append(research["sources"][0])
    target.write_text(json.dumps(research), encoding="utf-8")
    with pytest.raises(ValueError, match="ambiguous"):
        outlook.load(tmp_path)


def test_package_preserves_uppercase_citation_keys_and_rejects_unresolved_sources(tmp_path, research):
    research["sources"].append({"id": "P01", "title": "Primary source", "url": "https://example.org/primary#section"})
    target = tmp_path / outlook.PACKAGE
    target.parent.mkdir()
    target.write_text(json.dumps(research), encoding="utf-8")
    assert outlook.load(tmp_path)["sources"][-1]["id"] == "P01"
    research["varieties"][0]["source_ids"] = ["missing"]
    target.write_text(json.dumps(research), encoding="utf-8")
    with pytest.raises(ValueError, match="unresolved reference"):
        outlook.load(tmp_path)


def test_route_uses_private_runtime_and_shared_cards_without_fetch_or_trust_write(tmp_path, research, entities, monkeypatch):
    from app import main
    from app.blackberry_outlook_routes import blackberry_outlook
    target = tmp_path / outlook.PACKAGE
    target.parent.mkdir()
    target.write_text(json.dumps(research), encoding="utf-8")
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "entity_index", lambda: entities)
    monkeypatch.setattr(main, "unified_information", lambda: [{"id": "live-story", "title": "Current blackberry news",
                        "status": "unreviewed", "published_date": "2026-11-15", "berry_ids": ["berry-blackberry"],
                        "entity_ids": ["variety-first"], "source_name": "Example news", "source_url": "https://example.org/current"}])
    before = {str(path): path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    request = Request({"type": "http", "method": "GET", "path": outlook.PATH,
                       "query_string": b"variety=first", "headers": [], "app": main.app})
    response = blackberry_outlook(request)
    body = response.body.decode()
    assert "Global blackberry outlook 2027" in body
    assert "Current blackberry news" in body
    assert "data-open-reader" in body and "/intelligence/live-story?personal=1" in body
    assert "No planted hectares disclosed." in body
    assert "Explore a country" not in body
    assert "global-blackberry-outlook-2027/download.pdf" in body
    assert response.headers["cache-control"] == "private, no-store"
    assert {str(path): path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()} == before
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    with pytest.raises(HTTPException) as exc:
        blackberry_outlook(request)
    assert exc.value.status_code == 404


def test_route_retains_existing_inventory_adapter_before_unified_release(tmp_path, research, entities, monkeypatch):
    from app import main
    from app.blackberry_outlook_routes import blackberry_outlook
    target = tmp_path / outlook.PACKAGE
    target.parent.mkdir()
    target.write_text(json.dumps(research), encoding="utf-8")
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "entity_index", lambda: entities)
    monkeypatch.delattr(main, "unified_information")
    calls = []
    monkeypatch.setattr(main, "published_evidence", lambda: calls.append("existing-adapter") or [])
    request = Request({"type": "http", "method": "GET", "path": outlook.PATH,
                       "query_string": b"", "headers": [], "app": main.app})
    response = blackberry_outlook(request)
    assert calls == ["existing-adapter"]
    assert response.status_code == 200
    assert "No news matches this scope" in response.body.decode()
