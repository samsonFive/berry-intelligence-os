"""Real filter boundaries and durable selector-only views, without trust changes."""
from copy import deepcopy
from datetime import date
import json
from html import unescape
import re

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.services import landscape_workspace as workspace


@pytest.fixture
def world():
    entities = {
        "company-a": {"id": "company-a", "name": "Alpha", "entity_type": "company", "berry_ids": ["berry-blueberry"]},
        "company-b": {"id": "company-b", "name": "Beta", "entity_type": "company", "berry_ids": ["berry-blueberry"]},
        "variety-a": {"id": "variety-a", "name": "Azure", "entity_type": "variety", "berry_ids": ["berry-blueberry"]},
        "geography-peru": {"id": "geography-peru", "name": "Peru", "entity_type": "geography"},
        "geography-china": {"id": "geography-china", "name": "China", "entity_type": "geography"},
    }
    companies = {key: row for key, row in entities.items() if row["entity_type"] == "company"}
    evidence = [
        {"id": "ev-latest", "status": "published", "title": "Latest", "published_date": "2026-10-01", "berry_ids": ["berry-blueberry"], "entity_ids": ["company-a", "variety-a"], "geography_ids": ["geography-peru"]},
        {"id": "ev-old", "status": "published", "title": "Older", "published_date": "2025-01-01", "berry_ids": ["berry-blueberry"], "entity_ids": ["company-a"], "geography_ids": ["geography-peru"]},
        {"id": "ev-undated", "status": "published", "title": "Undated", "captured_date": "2026-10-01", "berry_ids": ["berry-blueberry"], "entity_ids": ["company-a"], "geography_ids": ["geography-peru"]},
        {"id": "ev-pending", "status": "in_review", "title": "Pending", "published_date": "2026-10-01", "berry_ids": ["berry-blueberry"], "entity_ids": ["company-a"]},
        {"id": "ev-future", "status": "published", "title": "Future", "published_date": "2026-10-05", "berry_ids": ["berry-blueberry"], "entity_ids": ["company-a"]},
    ]
    contexts = {"berry-blueberry": {"competitive_field": [{"entity": row} for row in companies.values()],
        "variety_rollup": [{"entity": entities["variety-a"]}],
        "signals": [{"id": "sig-explicit", "title": "China scoped", "berry_ids": ["berry-blueberry"], "geography_ids": ["geography-china"], "entity_ids": ["company-a"], "evidence_ids": ["ev-latest"]},
                    {"id": "sig-derived", "title": "Source linked", "berry_ids": ["berry-blueberry"], "entity_ids": ["company-a"], "evidence_ids": ["ev-latest"]}],
        "assessments": [{"id": "assessment-other-berry", "title": "Different explicit scope", "market_ids": ["berry-raspberry"], "entity_ids": ["company-a"]}]}}
    return {"contexts": contexts, "entities": entities, "companies": companies,
            "relationships": [{"subject_id": "company-a", "object_id": "variety-a", "predicate": "licenses", "status": "active"}],
            "evidence": evidence, "region_rows": [{"entity_id": "company-a", "geography_id": "geography-peru", "status": "active", "basis": "Existing relationship"}],
            "state": {}, "berries": {"berry-blueberry": "Blueberry"}, "today": date(2026, 10, 1)}


def test_dates_are_publication_only_and_do_not_erase_portfolios(world):
    before = deepcopy(world)
    result = workspace.model(**world, params={"window": "7d"})
    assert [row["id"] for row in result["panels"]["sources"]] == ["ev-latest"]
    assert [row["id"] for row in result["undated_sources"]] == ["ev-undated"]
    assert len(result["panels"]["companies"]) == 2
    assert len(result["panels"]["varieties"]) == 1
    assert world == before


def test_geography_does_not_infer_growing_from_article_mention_or_user_note(world):
    world["region_rows"].append({"entity_id": "variety-a", "geography_id": "geography-peru", "status": "active", "basis": "User annotation · not reviewed"})
    result = workspace.model(**world, params={"countries": "geography-peru"})
    assert [row["id"] for row in result["panels"]["companies"]] == ["company-a"]
    assert result["panels"]["varieties"] == []
    assert len(result["panels"]["sources"]) == 2
    assert [row["id"] for row in result["panels"]["signals"]] == ["sig-derived"]
    assert result["panels"]["assessments"] == []


def test_active_role_required_for_company_variety_scope(world):
    result = workspace.model(**world, params={"company": "company-a", "variety": "variety-a"})
    assert len(result["panels"]["varieties"]) == 1
    assert result["panels"]["varieties"][0]["roles"][0]["label"] == "Licensee"
    world["relationships"][0]["status"] = "historical"
    assert workspace.model(**world, params={"company": "company-a"})["panels"]["varieties"] == []


def test_combined_personal_marks_must_match_same_company(world):
    world["state"] = {"entity_favorites": {"company-a": True}, "entity_tiers": {"company-b": "tier1"}}
    world["evidence"][0]["entity_ids"].append("company-b")
    result = workspace.model(**world, params={"favorites": "1", "tier": "tier1"})
    assert result["panels"]["companies"] == []
    assert result["panels"]["sources"] == []


def test_native_repeat_csv_dedup_and_deliberate_empty_sections(world):
    from starlette.datastructures import QueryParams
    result = workspace.model(**world, params=QueryParams("company=company-a,company-b&company=company-a&berry_choice=berry-blueberry&configured=1"))
    assert result["filters"]["company"] == "company-a,company-b"
    assert result["sections"] == []


@pytest.mark.parametrize("params", [{"company": "missing"}, {"variety": "missing"}, {"berry": "fake"}, {"section": "fake"}, {"list": "missing"}, {"tier": "fake"}, {"window": "custom", "start": "2026-10-02", "end": "2026-10-01"}])
def test_invalid_saved_scope_is_not_silently_dropped(world, params):
    with pytest.raises(ValueError):
        workspace.model(**world, params=params)


def test_saved_views_preserve_selector_history_and_conflict(tmp_path):
    row = workspace.save_view(tmp_path, name="Blue watch", filters={"berry": "berry-blueberry", "private_article": "must not persist"})
    stored = json.loads((tmp_path / workspace.VIEW_FILE).read_text())
    assert "private_article" not in str(stored)
    assert "source_rows" not in str(stored)
    row = workspace.save_view(tmp_path, name="Updated watch", filters={"company": "company-a"}, view_id=row["id"], revision="1")
    before = (tmp_path / workspace.VIEW_FILE).read_bytes()
    with pytest.raises(ValueError, match="another window"):
        workspace.save_view(tmp_path, name="Lost update", filters={}, view_id=row["id"], revision="1")
    assert (tmp_path / workspace.VIEW_FILE).read_bytes() == before
    archived = workspace.save_view(tmp_path, name=row["name"], filters=row["filters"], view_id=row["id"], revision="2", archive=True)
    restored = workspace.save_view(tmp_path, name=archived["name"], filters=archived["filters"], view_id=archived["id"], revision="3")
    assert restored["filters"] == row["filters"]
    assert not restored["archived"]
    assert len(workspace.load_views(tmp_path)["history"]) == 4


def test_corrupt_saved_view_file_fails_without_overwrite(tmp_path):
    path = tmp_path / workspace.VIEW_FILE
    path.write_text('{"version":1,"views":[],"history":[]}')
    before = path.read_bytes()
    with pytest.raises(ValueError):
        workspace.save_view(tmp_path, name="New", filters={})
    assert path.read_bytes() == before


def test_browsing_landscape_is_readonly_and_has_no_provider(monkeypatch, tmp_path):
    def fail(*args, **kwargs):
        raise AssertionError("Landscape browsing cannot collect, generate or read pending nav bodies")
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "maybe_untrusted_completer", fail)
    monkeypatch.setattr(main, "_feed_first_world", fail)
    monkeypatch.setattr(main, "_compute_nav_work_counts", fail)
    client = TestClient(main.app)
    response = client.get("/landscapes?berry=berry-blueberry&section=companies")
    assert response.status_code == 200
    assert "Competitive Landscape" in response.text
    assert "Include sections" in response.text
    assert not list(tmp_path.rglob("*.json"))


def test_published_only_view_never_reads_saved_views_or_personal_marks(monkeypatch, tmp_path):
    from app.services import feed_first
    def fail(*args, **kwargs):
        raise AssertionError("Private state must not be read")
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(workspace, "load_views", fail)
    monkeypatch.setattr(feed_first, "load_state", fail)
    client = TestClient(main.app)
    page = client.get("/landscapes?berry=berry-blueberry")
    assert page.status_code == 200
    assert "Save this view" not in page.text
    assert client.post("/landscapes/views", data={"name": "Private"}).status_code == 403


def test_view_save_reopen_and_update_conflict(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    client = TestClient(main.app)
    response = client.post("/landscapes/views", data={"name": "Pilot scope", "berry": "berry-blueberry", "company": "company-planasa", "section": "sources", "configured": "1"}, follow_redirects=False)
    assert response.status_code == 303
    reopened = client.get(response.headers["location"])
    assert reopened.status_code == 200
    assert "Pilot scope" in reopened.text
    row = next(iter(workspace.load_views(tmp_path)["views"].values()))
    assert row["filters"]["company"] == "company-planasa"
    conflict = client.post("/landscapes/views", data={"name": "Stale", "view_id": row["id"], "revision": "0", "berry": "berry-blueberry"})
    assert conflict.status_code == 409
    assert len(workspace.load_views(tmp_path)["views"]) == 1


def test_access_screen_summary_is_hidden_without_changing_source(world):
    world["evidence"][0]["summary"] = "Verify you are a human. Enable cookies to continue."
    before = deepcopy(world["evidence"])
    result = workspace.model(**world, params={})
    latest = next(row for row in result["panels"]["sources"] if row["id"] == "ev-latest")
    assert latest["summary"] == ""
    assert latest["summary_blocked"]
    assert world["evidence"] == before


def test_malformed_saved_row_cannot_be_overwritten(tmp_path):
    path = tmp_path / workspace.VIEW_FILE
    path.write_text(json.dumps({"version": 1, "views": {"bad": {"id": "bad"}}, "history": []}))
    before = path.read_bytes()
    with pytest.raises(ValueError, match="cannot be read"):
        workspace.save_view(tmp_path, name="New", filters={})
    assert path.read_bytes() == before


def test_rename_cannot_collide_with_another_active_saved_view(tmp_path):
    first = workspace.save_view(tmp_path, name="First", filters={})
    workspace.save_view(tmp_path, name="Second", filters={})
    before = (tmp_path / workspace.VIEW_FILE).read_bytes()
    with pytest.raises(ValueError, match="already exists"):
        workspace.save_view(tmp_path, name="Second", filters={}, view_id=first["id"], revision="1")
    assert (tmp_path / workspace.VIEW_FILE).read_bytes() == before


def test_region_scope_uses_active_containment_relationships(world):
    world["entities"]["geography-south-america"] = {"id": "geography-south-america", "name": "South America", "entity_type": "geography"}
    world["relationships"].append({"subject_id": "geography-peru", "object_id": "geography-south-america", "predicate": "part_of", "status": "active"})
    result = workspace.model(**world, params={"countries": "geography-south-america"})
    assert [row["id"] for row in result["panels"]["companies"]] == ["company-a"]
    assert len(result["panels"]["sources"]) == 2


def test_saved_view_pagination_and_report_handoff_keep_scope(monkeypatch, tmp_path):
    from urllib.parse import parse_qs, urlsplit

    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    row = workspace.save_view(tmp_path, name="Genetics view", filters={
        "company": "company-fall-creek-farm-and-nursery,company-planasa",
        "berry": "berry-blueberry,berry-raspberry", "section": "companies,sources"})
    client = TestClient(main.app)
    page = client.get(workspace.view_href(row))
    assert page.status_code == 200
    next_href = unescape(re.search(r'<a href="([^"]+)">Next sources</a>', page.text)[1])
    assert parse_qs(urlsplit(next_href).query)["saved_view"] == [row["id"]]
    second_page = client.get(next_href)
    assert 'name="saved_view" value="' + row["id"] + '"' in second_page.text
    brief_href = unescape(re.search(r'href="(/brief-pack\?[^"]+)"', page.text)[1])
    assert parse_qs(urlsplit(brief_href).query).get("varieties") is None
    report_href = unescape(re.search(r'href="(/reports/new\?[^"]+)"', page.text)[1])
    report_query = parse_qs(urlsplit(report_href).query)
    assert report_query["origin"] == ["landscape"]
    assert "Companies, Latest sources" in report_query["focus_notes"][0]
    report_page = client.get(report_href).text
    assert "Prefilled from your Landscape" in report_page
    assert "Prefilled from Today's top stories" not in report_page
    notes = unescape(re.search(r'<textarea[^>]+name="focus_notes"[^>]*>(.*?)</textarea>', report_page, re.S)[1])
    assert "Blueberry, Raspberry" in notes
    assert "confirm the report's berry scope" in notes


def test_empty_personal_scope_does_not_generate_unscoped_report(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    page = TestClient(main.app).get("/landscapes?favorites=1")
    assert page.status_code == 200
    assert not re.search(r'href="/reports/new\?', page.text)
