from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main
from app.services import company_directory as service, feed_first, map_regions, news_workspace, personal_digest
from app.services.global_explorer import IntelligenceQuery


ENTITIES = {
    "company-a": {"id": "company-a", "name": "Ágro Berries", "entity_type": "company", "status": "active", "berry_ids": ["berry-blueberry"]},
    "company-b": {"id": "company-b", "name": "Beta Berry", "entity_type": "company", "status": "unverified", "berry_ids": []},
    "geography-portugal": {"id": "geography-portugal", "name": "Portugal", "entity_type": "geography", "attributes": {"iso_3166_1_alpha_2": "PT"}},
    "berry-blueberry": {"id": "berry-blueberry", "name": "Blueberry", "entity_type": "berry"},
}


@pytest.fixture(autouse=True)
def no_seed(monkeypatch):
    monkeypatch.setattr(service.seed_roster, "build_roster", lambda existing: [])


def test_catalog_defaults_and_directory_scope_are_not_auto_tiers():
    rows = service.catalog(ENTITIES)
    assert all(row["tier"] == "untiered" and not row["favorite"] for row in rows.values())
    assert service.directory(rows, {}, {"letter": "A"})["rows"][0]["id"] == "company-a"
    assert service.directory(rows, {}, {"berry": "berry-blueberry"})["matching"] == 1
    assert service.directory(rows, {}, {"favorites": "1"})["matching"] == 0
    with pytest.raises(ValueError):
        service.directory(rows, {}, {"letter": "AB"})


def test_marks_lists_subscriptions_and_reading_are_independent(tmp_path):
    allowed = {"company-a", "company-b"}
    group = personal_digest.edit_list(tmp_path, action="create", name="Watch", company_ids=["company-b"], allowed_companies=allowed)
    personal_digest.edit_list(tmp_path, action="subscribe", list_id=group, allowed_companies=allowed)
    service.mark(tmp_path, entity_id="company-a", action="favorite", value="1", allowed=allowed)
    service.mark(tmp_path, entity_id="company-a", action="tier", value="tier1", allowed=allowed)
    service.mark(tmp_path, entity_id="company-a", action="join", value=group, allowed=allowed)
    state = feed_first.load_state(tmp_path)
    assert state["entity_favorites"]["company-a"]
    assert state["entity_tiers"] == {"company-a": "tier1"}
    assert state["company_lists"][group]["company_ids"] == ["company-a", "company-b"]
    assert state["digest_subscriptions"] == [group]
    assert not state["decisions"] and not state["statements"]
    service.mark(tmp_path, entity_id="company-a", action="tier", value="untiered", allowed=allowed)
    service.mark(tmp_path, entity_id="company-a", action="leave", value=group, allowed=allowed)
    state = feed_first.load_state(tmp_path)
    assert state["entity_favorites"]["company-a"] and "company-a" not in state["entity_tiers"]
    assert state["digest_subscriptions"] == [group] and len(state["entity_mark_history"]) == 5
    with pytest.raises(ValueError):
        service.mark(tmp_path, entity_id="missing", action="favorite", value="1", allowed=allowed)


def test_concurrent_membership_keeps_members_and_corrupt_state_is_not_overwritten(tmp_path):
    allowed = {"company-a", "company-b"}
    group = personal_digest.edit_list(tmp_path, action="create", name="Watch", allowed_companies=allowed)
    with ThreadPoolExecutor(2) as pool:
        list(pool.map(lambda key: service.mark(tmp_path, entity_id=key, action="join", value=group, allowed=allowed), sorted(allowed)))
    assert set(feed_first.load_state(tmp_path)["company_lists"][group]["company_ids"]) == allowed
    path = feed_first.state_path(tmp_path)
    path.write_text('{broken', encoding="utf-8")
    with pytest.raises(ValueError):
        service.mark(tmp_path, entity_id="company-a", action="favorite", value="1", allowed=allowed)
    assert path.read_text(encoding="utf-8") == '{broken'


def test_profile_override_precedence_reset_stale_history_and_url_validation(tmp_path):
    payload = {"revision": "0", "website": "https://example.com/company", "linkedin": "https://www.linkedin.com/company/berry/", "socials": "Instagram | @berry | https://www.instagram.com/berry/"}
    saved = service.edit_profile(tmp_path, entity_id="company-a", payload=payload)
    profiles = service.load_profiles(tmp_path)
    rows = service.catalog(ENTITIES, profiles=profiles["profiles"])
    assert rows["company-a"]["website"] == payload["website"] and rows["company-a"]["edited"]
    with pytest.raises(ValueError, match="changed"):
        service.edit_profile(tmp_path, entity_id="company-a", payload=payload)
    with pytest.raises(ValueError):
        service.edit_profile(tmp_path, entity_id="company-a", payload={**payload, "revision": "1", "website": "http://127.0.0.1/private"})
    service.edit_profile(tmp_path, entity_id="company-a", payload={"revision": saved["revision"], "action": "reset"})
    state = service.load_profiles(tmp_path)
    assert "website" not in state["profiles"]["company-a"] and len(state["history"]) == 2
    assert state["history"][1]["before"]["website"] == payload["website"]
    assert not Path(tmp_path / 'analyst_queue_state.json').exists()


def test_people_highlight_hide_restore_and_affiliation_boundaries(tmp_path):
    saved = service.edit_profile(tmp_path, entity_id="company-a", payload={"revision": "0", "action": "person", "name": "Jane Berry", "role": "Research contact", "linkedin": "https://www.linkedin.com/in/jane-berry/", "socials": "X | @jane |", "highlighted": "1"})
    key = next(iter(saved["people"]))
    people = service.people_for("company-a", ENTITIES, [], [], saved)
    assert people[0]["highlighted"] and people[0]["socials"][0]["handle"] == "@jane"
    assert service.people_for("company-b", ENTITIES, [], [], {}) == []
    saved = service.edit_profile(tmp_path, entity_id="company-a", payload={"revision": "1", "action": "hide_person", "person_id": key})
    assert service.people_for("company-a", ENTITIES, [], [], saved)[0]["hidden"]
    saved = service.edit_profile(tmp_path, entity_id="company-a", payload={"revision": "2", "action": "restore_person", "person_id": key})
    assert not saved["people"][key]["hidden"]
    with pytest.raises(ValueError):
        service.edit_profile(tmp_path, entity_id="company-b", payload={"revision": "0", "action": "person", "person_id": key, "name": "Wrong company"})


def test_selected_favorites_are_the_same_in_news_map_and_digest(tmp_path):
    service.mark(tmp_path, entity_id="company-a", action="favorite", value="1", allowed={"company-a"})
    service.mark(tmp_path, entity_id="company-a", action="tier", value="tier1", allowed={"company-a"})
    state = feed_first.load_state(tmp_path)
    records = {"ev-a": {"id": "ev-a", "title": "Agro Berries launches a new blueberry variety", "summary": "New blueberry genetics", "status": "published", "source_type": "trade_press", "source_name": "Trade", "published_date": "2026-09-30", "entity_ids": ["company-a"], "berry_ids": ["berry-blueberry"], "source_url": "https://example.com/a"}}
    personal_digest.set_personal_decision(tmp_path, "ev-a", "save")
    state = feed_first.load_state(tmp_path)
    news = news_workspace.model(records=records, entities=ENTITIES, relationships=[], facts=[], state=state, params={"favorites": "1", "tier": "tier1"}, now=datetime(2026,10,1,tzinfo=UTC))
    assert news["matching"] == 1
    digest = personal_digest.digest_model(records=records, entities=ENTITIES, state=state, reading={}, params={"favorites": "1", "tier": "tier1"})
    assert digest["matching"] == 1
    rows = [{"id": "rel-a", "entity_id": "company-a", "kind": "company", "geography_id": "geography-portugal", "berry_ids": ["berry-blueberry"], "name": "Agro", "country": "Portugal", "status": "active", "activity": "Operations (unspecified)"}]
    assert len(map_regions.scoped(rows, IntelligenceQuery(), [], state, kind="company", favorites="1", tier="tier1")) == 1
    service.mark(tmp_path, entity_id="company-a", action="favorite", value="0", allowed={"company-a"})
    state = feed_first.load_state(tmp_path)
    assert not map_regions.scoped(rows, IntelligenceQuery(), [], state, kind="company", favorites="1")


def test_routes_pure_get_authoring_origin_and_private_read_only(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "living_catalog", lambda: list(ENTITIES.values()))
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    client = TestClient(main.app)
    assert client.get('/entities/company').status_code == 200
    assert not list(tmp_path.iterdir())
    assert client.post('/companies/company-a/marks', data={"action": "favorite", "value": "1"}, headers={"origin": "https://other.example"}).status_code == 403
    result = client.post('/companies/company-a/marks', data={"action": "favorite", "value": "1", "return_to": "https://other.example"}, follow_redirects=False)
    assert result.status_code == 303 and result.headers['location'] == '/entities/company'
    service.edit_profile(tmp_path, entity_id="company-a", payload={"revision": "0", "website": "https://private-note.example/company", "socials": ""})
    assert 'private-note.example' in client.get('/entities/company').text
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    assert client.post('/companies/company-a/marks', data={"action": "favorite", "value": "0"}).status_code == 403
    assert 'private-note.example' not in client.get('/entities/company').text
    assert client.get('/entity-logos/company-a/logo-1234567890abcdef.png').status_code == 404


def test_logo_writes_require_authoring_and_same_origin(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    client = TestClient(main.app)
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    assert client.post('/entities/company/company-a/logo', data={"logo_url": "https://example.com/logo.png"}).status_code == 403
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    assert client.post('/entities/company/company-a/logo', data={"logo_url": "https://example.com/logo.png"}, headers={"sec-fetch-site": "cross-site"}).status_code == 403


def test_profile_tabs_preserve_backbone_and_shared_reader(tmp_path, monkeypatch):
    # Use real canonical data/seed matching for this integration proof.
    monkeypatch.undo()
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    client = TestClient(main.app)
    base = '/entities/company/company-planasa'
    overview = client.get(base)
    assert overview.status_code == 200 and 'company_workspace.css' in overview.text
    assert 'Company sections' in overview.text and 'Profile &amp; links' in overview.text
    intelligence = client.get(base+'?tab=intelligence')
    assert 'Canonical portfolio' in intelligence.text and 'Canonical corporate relationships' in intelligence.text
    assert 'Blue Manila' in client.get(base+'?tab=varieties').text
    assert 'Map Explorer' in client.get(base+'?tab=regions').text
    assert 'Add a person' in client.get(base+'?tab=people').text
    assert 'Save logo' in client.get(base+'?tab=details').text
    assert 'v2ReaderOffcanvas' in client.get(base+'?tab=news').text
    assert not list(tmp_path.iterdir())


def test_directory_list_rename_retains_existing_person_member(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "living_catalog", lambda: list(ENTITIES.values()))
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    group = personal_digest.edit_list(tmp_path, action="create", name="Registry", company_ids=["company-a", "person-a"], allowed_companies={"company-a", "person-a"})
    result = TestClient(main.app).post("/companies/lists", data={"action": "edit", "list_id": group, "name": "Renamed registry", "company_ids": ["company-a", "person-a"]}, follow_redirects=False)
    assert result.status_code == 303
    assert feed_first.load_state(tmp_path)["company_lists"][group]["company_ids"] == ["company-a", "person-a"]
    assert TestClient(main.app).post("/companies/lists", data={"action": "edit", "list_id": group, "name": "Other", "company_ids": ["unknown-person"]}, follow_redirects=False).status_code == 400


def test_digest_marks_filter_each_story_not_last_source(tmp_path):
    records = {key: {"id": key, "title": key, "entity_ids": [company], "published_date": "2026-09-30"} for key, company in [("ev-a", "company-a"), ("ev-b", "company-b")]}
    group = personal_digest.edit_list(tmp_path, action="create", name="A only", company_ids=["company-a"], allowed_companies={"company-a"})
    personal_digest.edit_list(tmp_path, action="subscribe", list_id=group, allowed_companies=set())
    personal_digest.set_personal_decision(tmp_path, "ev-b", "save")
    service.mark(tmp_path, entity_id="company-a", action="favorite", value="1", allowed={"company-a"})
    state = feed_first.load_state(tmp_path)
    for filters in ({"list": group}, {"favorites": "1"}):
        result = personal_digest.digest_model(records=records, entities=ENTITIES, state=state, reading={}, params=filters)
        assert [r["id"] for r in result["cards"]] == ["ev-a"]
