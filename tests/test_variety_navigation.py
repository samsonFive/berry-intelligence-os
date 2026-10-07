import re

import pytest
from fastapi.testclient import TestClient

from app import main
from app.services import feed_first, feed_first_reader, map_regions, variety_navigation as navigation


def cards():
    return [{"id": "variety-a", "name": "Ária"}, {"id": "variety-b", "name": "Beta"}, {"id": "variety-c", "name": "7 Blue"}]


ENTITIES = {"company-a": {"id": "company-a", "name": "Alpha", "entity_type": "company"},
            "person-a": {"id": "person-a", "name": "Person", "entity_type": "person"}}
RELATIONSHIPS = [
    {"subject_id": "company-a", "object_id": "variety-a", "predicate": "develops", "status": "active"},
    {"subject_id": "company-a", "object_id": "variety-b", "predicate": "owns", "status": "historical"},
    {"subject_id": "person-a", "object_id": "variety-c", "predicate": "develops", "status": "active"},
]
STATE = {"entity_favorites": {"company-a": True}, "entity_tiers": {"company-a": "tier1"},
         "company_lists": {"watch": {"name": "Watch", "company_ids": ["company-a"]}}}


def directory(params, regions=(), state=STATE):
    return navigation.directory(cards(), params=params, state=state, entities=ENTITIES, relationships=RELATIONSHIPS, regions=regions)


@pytest.mark.parametrize("params", [{"favorites": "1"}, {"tier": "tier1"}, {"list": "watch"}, {"favorites": "1", "tier": "tier1", "list": "watch"}])
def test_marks_use_active_organization_roles(params):
    assert [row["id"] for row in directory(params)["variety_rows"]] == ["variety-a"]


def test_unassigned_role_company_is_untiered_not_a_seed_tier():
    assert [row["id"] for row in directory({"tier": "untiered"}, state={})["variety_rows"]] == ["variety-a"]
    assert navigation.company_actors("variety-b", RELATIONSHIPS, ENTITIES) == set()


def test_alphabet_preserves_scope_and_empty_letters():
    model = directory({"letter": "a", "favorites": "1", "q": "A&B", "berry": "berry-blueberry"})
    assert model["letters"] == {"A"}
    assert model["variety_rows"][0]["name"] == "Ária"
    assert "favorites=1" in model["letter_urls"]["A"] and "q=A%26B" in model["letter_urls"]["A"]
    assert directory({"letter": "#"})["variety_rows"][0]["id"] == "variety-c"


def test_growing_filter_does_not_infer_from_retail_market_or_company_role():
    regions = [{"entity_id": "variety-b", "kind": "variety", "geography_id": "geo-pt", "country": "Portugal", "basis": "User annotation · not reviewed"}]
    model = directory({"growing_country": "geo-pt"}, regions)
    assert [row["id"] for row in model["variety_rows"]] == ["variety-b"]
    assert model["variety_rows"][0]["growing_regions"][0]["basis"].startswith("User annotation")


@pytest.mark.parametrize("params", [{"letter": "AB"}, {"favorites": "yes"}, {"tier": "auto"}, {"list": "missing"}])
def test_invalid_scope_fails_visibly(params):
    with pytest.raises(ValueError):
        directory(params)


def test_candidates_filter_photo_company_without_becoming_roles():
    candidates = [{"id": "vcand-a", "candidate_name": "Ária", "berry_id": "berry-blueberry", "identity_state": "possible_alias", "knowledge": {"company_associations": [{"entity_id": "company-a", "name": "Alpha"}]}},
                  {"id": "vcand-b", "candidate_name": "Beta", "berry_id": "berry-strawberry", "identity_state": "unknown", "knowledge": {}}]
    result = navigation.candidate_queue(candidates, {"company": "company-a", "q": "Alpha", "berry": "berry-blueberry", "status": "possible_alias", "letter": "A"})
    assert result["candidates"] == [candidates[0]]
    assert result["candidate_total"] == 2
    assert candidates[0]["identity_state"] == "possible_alias"
    assert navigation.company_actors("vcand-a", RELATIONSHIPS, ENTITIES) == set()


def test_candidate_letter_links_land_in_queue_and_preserve_every_filter():
    from urllib.parse import parse_qs, urlsplit
    params = {"company": "company-a", "q": "Alpha & Blue", "berry": "berry-blueberry",
              "status": "unknown", "source": "source-with-#", "letter": "A"}
    row = {"id": "vcand-a", "candidate_name": "Alpha & Blue", "berry_id": "berry-blueberry",
           "identity_state": "unknown", "source_id": params["source"],
           "knowledge": {"source_companies": [{"entity_id": "company-a", "name": "Alpha"}]}}
    model = navigation.candidate_queue([row], params)
    for letter in ("B", "", "#"):
        target = urlsplit(model["letter_urls"][letter])
        assert target.fragment == "candidate-results"
        assert {key: values[0] for key, values in parse_qs(target.query, keep_blank_values=True).items()} == {**params, "letter": letter}
    assert row["identity_state"] == "unknown"


@pytest.mark.parametrize("tier,expected", [("tier_1_patent_pvr", "Open patent / rights record"),
                                          ("tier_1_registry", "Open registry record"),
                                          ("tier_1_breeder_catalog", None)])
def test_candidate_rights_reference_keeps_unreviewed_dates_and_scope(monkeypatch, tmp_path, tier, expected):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    candidate = {"id": "vcand-rights", "candidate_name": "Sample", "identity_label": "Unresolved",
                 "identity_state": "unknown", "berry_id": "berry-blueberry", "knowledge": {},
                 "source_tier": tier, "source_url": "https://example.test/original-rights-record",
                 "registration": {"application_number": "123", "grant_number": "456", "jurisdiction": "UK",
                                  "application_date": "2020-01-02", "grant_date": "2021-02-03",
                                  "expiry": "2030-04-05", "status": "expired"}}
    monkeypatch.setattr(main, "variety_candidate_universe", lambda: ([], [candidate], {}))
    page = TestClient(main.app).get("/varieties/candidates")
    assert page.status_code == 200
    assert "Candidate (untrusted)" in page.text and "expired" in page.text
    for value in ("Applied", "Granted", "Recorded expiry", "2020-01-02", "2021-02-03", "2030-04-05"):
        assert value in page.text
    if expected:
        assert expected in page.text and "identity and rights still need review" in page.text
    else:
        assert "Open registry record" not in page.text and "Open patent / rights record" not in page.text
    assert not list(tmp_path.iterdir())


def test_directory_preserves_catalog_ids_and_get_has_no_personal_writes(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    def forbidden(*args, **kwargs):
        raise AssertionError("Directory must not load full pending records, fetch or write personal state")
    monkeypatch.setattr(main, "list_pending_drafts", forbidden)
    monkeypatch.setattr(feed_first, "save_state", forbidden)
    monkeypatch.setattr(feed_first_reader, "load_capture", forbidden)
    monkeypatch.setattr(feed_first_reader, "fetch_public_article", forbidden)
    monkeypatch.setattr(map_regions, "edit", forbidden)
    page = TestClient(main.app).get("/entities/variety?berry=")
    assert page.status_code == 200
    ids = set(re.findall(r'<tr id="variety-([^"]+)"', page.text))
    expected = {row["id"] for row in main.living_catalog() if row.get("entity_type") == "variety"}
    assert ids == expected
    assert page.text.count('id="v2ReaderOffcanvas"') == 1
    assert not list(tmp_path.iterdir())


def test_profile_keeps_all_evidence_sections_and_shared_reader():
    page = TestClient(main.app).get("/entities/variety/variety-sekoya-grande")
    assert page.status_code == 200
    for key in ("growing-regions", "roles", "rights", "commercial-footprint", "variety-intelligence", "traits", "network", "intelligence-timeline", "recent-intelligence"):
        assert f'id="{key}"' in page.text, key
    assert re.search(r'id="rights">\s*<details class="variety-section">', page.text)
    assert re.search(r'id="roles">\s*<details class="variety-section" open>', page.text)
    assert page.text.count('id="v2ReaderOffcanvas"') == 1
    assert "data-open-reader" in page.text
    assert TestClient(main.app).get("/entities/variety/variety-sekoya-grande?view=legacy").status_code == 200
    assert TestClient(main.app).get("/entities/variety?view=legacy").status_code == 200


def test_readonly_excludes_private_growing_locations_and_candidates(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    (tmp_path / map_regions.FILENAME).write_text('not valid JSON', encoding="utf-8")
    def forbidden(*args, **kwargs):
        raise AssertionError("Read-only Varieties must not hydrate private inputs")
    monkeypatch.setattr(main, "list_drafts_metadata", forbidden)
    monkeypatch.setattr(main, "load_candidates", forbidden)
    monkeypatch.setattr(main, "present_candidates", forbidden)
    monkeypatch.setattr(main, "pending_publication_drafts", forbidden)
    monkeypatch.setattr(map_regions, "load", forbidden)
    client = TestClient(main.app)
    assert client.get("/entities/variety").status_code == 200
    assert client.get("/entities/variety/variety-sekoya-grande").status_code == 200
    assert client.get("/varieties/candidates").status_code == 403


def test_candidate_decision_controls_remain_protected_and_collapsed(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    candidate = {"id": "vcand-sample", "candidate_name": "Sample", "identity_label": "Possible alias", "identity_state": "possible_alias", "berry_id": "berry-blueberry", "knowledge": {}, "registration": {}, "candidate_canonical_match": "variety-sekoya-grande"}
    monkeypatch.setattr(main, "variety_candidate_universe", lambda: ([], [candidate], {}))
    page = TestClient(main.app).get("/varieties/candidates")
    assert page.status_code == 200
    assert '<details class="variety-candidate" id="vcand-sample">' in page.text
    assert set(re.findall(r'name="decision" value="([^"]+)"', page.text)) == {"possible_alias", "unknown", "distinct", "confirmed_same", "rejected"}
    assert not list(tmp_path.iterdir())


def test_one_region_edit_is_shared_by_directory_profile_and_map(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    client = TestClient(main.app)
    response = client.post("/profiles/variety-sekoya-grande/regions", data={
        "geography_id": "geography-portugal", "activity": "Trial", "status": "proposed",
        "locality": "Isolated test location", "observed_on": "2026-10-01",
        "notes": "Test annotation; not a researched growing location",
    }, follow_redirects=False)
    assert response.status_code == 303
    before = (tmp_path / map_regions.FILENAME).read_bytes()
    profile = client.get("/entities/variety/variety-sekoya-grande")
    assert "Isolated test location" in profile.text
    assert "User annotation · not reviewed" in profile.text
    directory_page = client.get("/entities/variety?growing_country=geography-portugal")
    assert 'id="variety-variety-sekoya-grande"' in directory_page.text
    assert 'id="variety-variety-zara"' not in directory_page.text
    map_page = client.get("/explorer?layer=varieties&region_entity=variety-sekoya-grande")
    assert "Isolated test location" in map_page.text
    assert "User annotation · not reviewed" in map_page.text
    assert (tmp_path / map_regions.FILENAME).read_bytes() == before
