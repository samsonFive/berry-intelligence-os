from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import pytest
from fastapi.testclient import TestClient

from app import main, map_region_routes
from app.services import map_regions, region_source_research as service
from app.services.ai_gateway.perplexity_deep_research import ResearchError
from tests.test_map_workspace import ENTITIES, RECORDS, REL

ACTOR = "variety-one"
URL = RECORDS[0]["source_url"]


def prepared(actor=ACTOR, records=RECORDS):
    return map_regions.prepare_from_source(actor, source_id=RECORDS[0]["id"], entities=ENTITIES, records=records, relationships=REL)


def item(**kwargs):
    return {"country_code": "PE", "locality": "Lima", "activity": "Trial", "basis": "trial", "observed_on": "", "date_note": "Trial mentioned; effective date not specified",
            "passage": "Example Blue is being trialled at the Lima site.", "explanation": "A trial is not national commercial growing. [web:1]", "source_url": URL, **kwargs}


def response(*items, status="completed", key="fixture-run"):
    return {"provider_id": key, "provider_status": status, "model": "fixture", "usage": {},
            "text": json.dumps({"proposals": list(items or [item()]), "limits": []}),
            "citations": [{"url": URL, "title": "Example source", "reference_ids": ["web:1"]}]}


def ready(tmp_path, *items, actor=ACTOR):
    job, _ = service.reserve(tmp_path, ENTITIES[actor], prepared(actor), "region-token-" + str(len(service.load(tmp_path)["jobs"])) + "-fixture")
    claimed = service.claim(tmp_path, job["id"])
    return service.apply_result(tmp_path, job["id"], response(*items), revision=claimed["revision"])


def get(tmp_path, job, *, actor=ACTOR, records=RECORDS, proposal=None):
    return service.get_proposal(tmp_path, actor, job["id"], proposal or job["proposals"][0]["id"], entities=ENTITIES, records=records, relationships=REL, facts=[])


def test_public_prompt_excludes_internal_summary_statement_notes_ids_and_concurrent_replay(tmp_path):
    source = deepcopy(prepared())
    source["source"]["summary"] = "PRIVATE EDITED SUMMARY"
    source["statement"] = {"statement": "PRIVATE STATEMENT"}
    source["draft"]["notes"] = "PRIVATE NOTE"
    jobs = list(ThreadPoolExecutor(4).map(lambda _: service.reserve(tmp_path, ENTITIES[ACTOR], source, "shared-region-token"), range(4)))
    assert sum(created for _, created in jobs) == 1
    job = jobs[0][0]
    text = service.prompt(job)
    assert URL in text and ENTITIES[ACTOR]["name"] in text
    assert all(private not in text for private in ["PRIVATE EDITED SUMMARY", "PRIVATE STATEMENT", "PRIVATE NOTE", ACTOR, RECORDS[0]["id"]])
    calls = []
    class Client:
        def start(self, prompt):
            calls.append(prompt)
            return response(status="queued")
    list(ThreadPoolExecutor(4).map(lambda _: service.submit(tmp_path, job["id"], Client), range(4)))
    assert len(calls) == 1 and not (tmp_path / map_regions.FILENAME).exists()


def test_proposal_prepares_real_location_activity_unknown_effective_date_without_writes(tmp_path):
    job = ready(tmp_path)
    before = (tmp_path / service.FILENAME).read_bytes()
    _, _, draft = get(tmp_path, job)
    values = draft["draft"]
    assert values["geography_id"] == "geography-peru" and values["activity"] == "Trial"
    assert values["observed_on"] == "" and values["source_date"] == "2026-08-01" and values["status"] == "proposed"
    assert "[web:" not in values["notes"] and "not national" in values["notes"]
    assert (tmp_path / service.FILENAME).read_bytes() == before and not (tmp_path / map_regions.FILENAME).exists()


@pytest.mark.parametrize("changes", [{"basis": "patent_territory", "activity": "Commercial growing"}, {"basis": "headquarters", "activity": "Commercial growing"},
                                      {"basis": "retail_market", "activity": "Commercial growing"}, {"basis": "trial", "activity": "Commercial growing"}])
def test_sales_rights_offices_and_mismatched_activity_are_visible_but_not_growing(tmp_path, changes):
    job = ready(tmp_path, item(**changes))
    p = job["proposals"][0]
    assert not p["eligible"] and p["warnings"] and p["passage"]
    with pytest.raises(ValueError, match="eligible"):
        get(tmp_path, job)


def test_company_headquarters_is_not_mislabeled_as_growing(tmp_path):
    job = ready(tmp_path, item(basis="headquarters", activity="Headquarters"), actor="company-grower")
    assert job["proposals"][0]["eligible"]
    assert get(tmp_path, job, actor="company-grower")[2]["draft"]["activity"] == "Headquarters"


def test_exact_native_source_required_and_partial_or_invalid_dates_not_fabricated(tmp_path):
    job = ready(tmp_path, item(source_url="https://example.org/other"), item(observed_on="2025", date_note="2025 season"))
    assert len(job["proposals"]) == 1 and job["warnings"]
    p = job["proposals"][0]
    assert p["observed_on"] == "" and "2025" in p["date_note"] and p["warnings"]
    assert "https://example.org/other" in job["text"]


def test_wrong_profile_changed_source_and_unknown_geography_remain_unapplied(tmp_path):
    job = ready(tmp_path)
    with pytest.raises(ValueError, match="another profile"):
        get(tmp_path, job, actor="company-grower")
    with pytest.raises(ValueError, match="source link changed"):
        get(tmp_path, job, records=[{**RECORDS[0], "source_url": "https://example.org/replaced"}])
    unknown = ready(tmp_path, item(country_code="ZZ"))
    with pytest.raises(ValueError, match="not uniquely"):
        get(tmp_path, unknown)
    assert not (tmp_path / map_regions.FILENAME).exists()


def test_save_is_editable_atomic_idempotent_and_removed_suggestion_never_resurrects(tmp_path):
    job = ready(tmp_path)
    form = {**get(tmp_path, job)[2]["draft"], "entity_id": ACTOR, "notes": "Human correction", "activity": "Historical growing", "status": "historical"}
    saved = map_regions.edit(tmp_path, payload=form, entities=ENTITIES, relationships=REL, records=RECORDS)
    assert saved["activity"] == "Historical growing" and saved["notes"] == "Human correction"
    assert saved["research_origin"]["proposal"]["activity"] == "Trial" and saved["research_origin"]["source_url"] == URL
    edited = map_regions.edit(tmp_path, payload={**saved, "notes": "Later edit", "observed_on": "2025-03-04"}, entities=ENTITIES, relationships=REL, records=RECORDS)
    assert edited["research_origin"] == saved["research_origin"]
    assert map_regions.edit(tmp_path, payload=form, entities=ENTITIES, relationships=REL, records=RECORDS) == edited
    assert len(map_regions.load(tmp_path)["history"]) == 2
    map_regions.edit(tmp_path, payload={"id": edited["id"], "revision": 2, "action": "remove"}, entities=ENTITIES, relationships=REL, records=RECORDS)
    with pytest.raises(ValueError, match="already used and removed"):
        map_regions.edit(tmp_path, payload=form, entities=ENTITIES, relationships=REL, records=RECORDS)
    assert len(map_regions.load(tmp_path)["history"]) == 3
    assert not [r for r in map_regions.catalog(ENTITIES, REL, RECORDS, map_regions.load(tmp_path)) if r["entity_id"] == ACTOR]


def test_existing_region_and_edited_notes_never_overwritten_and_conflicts_are_visible(tmp_path):
    map_regions.edit(tmp_path, payload={"entity_id": ACTOR, "geography_id": "geography-lima", "activity": "Historical growing", "status": "disputed", "notes": "Existing correction"}, entities=ENTITIES, relationships=REL, records=RECORDS)
    before = (tmp_path / map_regions.FILENAME).read_bytes()
    job = ready(tmp_path)
    rows = [r for r in map_regions.catalog(ENTITIES, REL, RECORDS, map_regions.load(tmp_path)) if r["entity_id"] == ACTOR]
    view = service.views(tmp_path, ACTOR, ENTITIES, rows, REL)[0]
    assert len(view["proposals"][0]["existing"]) == 1
    assert view["proposals"][0]["existing"][0]["notes"] == "Existing correction"
    assert "[web:" not in view["proposals"][0]["explanation_display"]
    assert (tmp_path / map_regions.FILENAME).read_bytes() == before


def test_uncertain_submission_retrieval_failure_and_stale_results_preserve_run(tmp_path):
    job, _ = service.reserve(tmp_path, ENTITIES[ACTOR], prepared(), "uncertain-source-token")
    claimed = service.claim(tmp_path, job["id"])
    service.failure(tmp_path, job["id"], ResearchError("Uncertain", uncertain=True), revision=claimed["revision"], submitting=True)
    assert not service.reserve(tmp_path, ENTITIES[ACTOR], prepared(), "new-source-token")[1]
    current = service.load(tmp_path)["jobs"][job["id"]]
    running = service.apply_result(tmp_path, job["id"], response(status="queued"), revision=current["revision"])
    service.failure(tmp_path, job["id"], ResearchError("Try again"), revision=running["revision"])
    current = service.load(tmp_path)["jobs"][job["id"]]
    assert current["status"] == "running" and current["provider_id"]
    service.apply_result(tmp_path, job["id"], response(), revision=running["revision"])
    assert service.load(tmp_path)["jobs"][job["id"]]["status"] == "running"
    assert service.apply_result(tmp_path, job["id"], response(), revision=current["revision"])["status"] == "ready"


def test_route_permissions_pure_get_preparation_and_corrected_annotation_save(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    monkeypatch.setattr(main, "entity_index", lambda: ENTITIES)
    monkeypatch.setattr(main, "published_evidence", lambda: RECORDS)
    monkeypatch.setattr(main, "all_relationships", lambda: REL)
    monkeypatch.setattr(main, "all_facts", lambda: [])
    calls = []
    class Client:
        def start(self, prompt):
            calls.append(prompt)
            return response()
    monkeypatch.setattr(map_region_routes, "research_client", Client)
    client = TestClient(main.app)
    base = "/profiles/variety-one/regions"
    form = {"source_id": RECORDS[0]["id"], "token": "route-source-token"}
    assert client.post(base + "/research", data=form, headers={"sec-fetch-site": "cross-site"}).status_code == 403
    assert not calls and not (tmp_path / service.FILENAME).exists()
    assert client.get(base + "?from_source=" + RECORDS[0]["id"]).status_code == 200 and not calls
    assert client.post(base + "/research", data=form, follow_redirects=False).status_code == 303
    job = next(iter(service.load(tmp_path)["jobs"].values()))
    assert len(calls) == 1
    page = client.get(base).text
    assert "Locations suggested by sources" in page and "Check and edit new entry" in page
    before = (tmp_path / service.FILENAME).read_bytes()
    target = base + f'?research_job={job["id"]}&proposal={job["proposals"][0]["id"]}'
    assert client.get(target).status_code == 200 and (tmp_path / service.FILENAME).read_bytes() == before
    assert client.get(target + "&edit=unknown").status_code == 409
    values = {**get(tmp_path, job)[2]["draft"], "notes": "My corrected note"}
    assert client.post(base, data=values, follow_redirects=False).status_code == 303
    saved = next(iter(map_regions.load(tmp_path)["entries"].values()))
    assert saved["notes"] == "My corrected note" and saved["research_origin"]
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    monkeypatch.setattr(service, "load", lambda *_: pytest.fail("Readonly must not read private source research"))
    assert client.get(target).status_code == 403
    assert "Locations suggested by sources" not in client.get(base).text
    assert client.post(base + "/research", data=form).status_code == 403


@pytest.mark.parametrize("field,value", [("scope", {}), ("revision", True), ("citations", []),
                                         ("history", [{"action": "dismiss", "proposal_id": "unknown"}])])
def test_corrupt_private_research_is_preserved_and_cannot_be_replaced(tmp_path, field, value):
    job = ready(tmp_path)
    state = service.load(tmp_path)
    state["jobs"][job["id"]][field] = value
    path = tmp_path / service.FILENAME
    path.write_text(json.dumps(state), encoding="utf-8")
    before = path.read_bytes()
    with pytest.raises(ValueError, match="restore it"):
        service.reserve(tmp_path, ENTITIES[ACTOR], prepared(), "replacement-token-fixture")
    assert path.read_bytes() == before and not (tmp_path / map_regions.FILENAME).exists()


@pytest.mark.parametrize("changes", [{"eligible": False}, {"passage": "x" * 1601},
                                      {"observed_on": "2026"}, {"source_url": "https://example.org/other"}])
def test_corrupt_persisted_proposal_cannot_bypass_source_date_or_eligibility_gates(tmp_path, changes):
    job = ready(tmp_path)
    state = service.load(tmp_path)
    state["jobs"][job["id"]]["proposals"][0].update(changes)
    path = tmp_path / service.FILENAME
    path.write_text(json.dumps(state), encoding="utf-8")
    before = path.read_bytes()
    with pytest.raises(ValueError, match="restore it"):
        get(tmp_path, job)
    assert path.read_bytes() == before


def test_long_source_qualifications_and_rejected_partial_date_are_not_silently_cut(tmp_path):
    date_note = "Source qualification: " + "q" * (600 - len("Source qualification: "))
    job = ready(tmp_path, item(passage="p" * 1600, explanation="e" * 600, date_note=date_note, observed_on="2025 season"))
    proposal = service.load(tmp_path)["jobs"][job["id"]]["proposals"][0]
    assert proposal["date_note"] == date_note + " · 2025 season" and proposal["observed_on"] == ""
    draft = get(tmp_path, job)[2]["draft"]
    assert len(draft["notes"]) > 2000
    saved = map_regions.edit(tmp_path, payload={**draft, "entity_id": ACTOR}, entities=ENTITIES, relationships=REL, records=RECORDS)
    assert saved["notes"] == draft["notes"].strip()
    before = (tmp_path / map_regions.FILENAME).read_bytes()
    with pytest.raises(ValueError, match="nothing has been saved"):
        map_regions.edit(tmp_path, payload={**saved, "notes": "x" * 4001}, entities=ENTITIES, relationships=REL, records=RECORDS)
    assert (tmp_path / map_regions.FILENAME).read_bytes() == before


def test_partial_native_citation_result_and_duplicate_country_need_human_resolution(tmp_path):
    job, _ = service.reserve(tmp_path, ENTITIES[ACTOR], prepared(), "partial-result-token")
    claimed = service.claim(tmp_path, job["id"])
    partial = service.apply_result(tmp_path, job["id"], response(status="incomplete"), revision=claimed["revision"])
    assert partial["status"] == "partial" and get(tmp_path, partial)[2]["draft"]["status"] == "proposed"
    duplicate = {**ENTITIES, "duplicate-peru": {**ENTITIES["geography-peru"], "id": "duplicate-peru"}}
    with pytest.raises(ValueError, match="not uniquely"):
        service.get_proposal(tmp_path, ACTOR, job["id"], partial["proposals"][0]["id"], entities=duplicate,
                             records=RECORDS, relationships=REL, facts=[])
    assert not (tmp_path / map_regions.FILENAME).exists()


def test_response_prose_cannot_replace_native_citation_and_wrong_provider_is_rejected(tmp_path):
    job, _ = service.reserve(tmp_path, ENTITIES[ACTOR], prepared(), "native-citation-token")
    claimed = service.claim(tmp_path, job["id"])
    running = service.apply_result(tmp_path, job["id"], response(status="queued"), revision=claimed["revision"])
    before = (tmp_path / service.FILENAME).read_bytes()
    with pytest.raises(ValueError, match="another location check"):
        service.apply_result(tmp_path, job["id"], response(key="other-provider"), revision=running["revision"])
    assert (tmp_path / service.FILENAME).read_bytes() == before
    result = response()
    result["citations"] = []
    completed = service.apply_result(tmp_path, job["id"], result, revision=running["revision"])
    assert not completed["proposals"] and completed["warnings"] and URL in completed["text"]


def test_saved_removed_entry_is_visible_in_source_history_without_a_broken_edit_link(tmp_path):
    job = ready(tmp_path)
    saved = map_regions.edit(tmp_path, payload={**get(tmp_path, job)[2]["draft"], "entity_id": ACTOR}, entities=ENTITIES, relationships=REL, records=RECORDS)
    p = service.views(tmp_path, ACTOR, ENTITIES, [], REL)[0]["proposals"][0]
    assert p["used"] and p["entry_id"] == saved["id"] and not p["entry_removed"]
    map_regions.edit(tmp_path, payload={"id": saved["id"], "revision": saved["revision"], "action": "remove"}, entities=ENTITIES, relationships=REL, records=RECORDS)
    assert service.views(tmp_path, ACTOR, ENTITIES, [], REL)[0]["proposals"][0]["entry_removed"]


def test_http_recovery_error_resume_cancel_and_wrong_profile_do_not_duplicate_requests(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    monkeypatch.setattr(main, "entity_index", lambda: ENTITIES)
    monkeypatch.setattr(main, "published_evidence", lambda: RECORDS)
    monkeypatch.setattr(main, "all_relationships", lambda: REL)
    monkeypatch.setattr(main, "all_facts", lambda: [])
    calls = []
    class Client:
        def start(self, prompt):
            calls.append(prompt)
            raise ResearchError("Reconnect the existing run", uncertain=True)
        def check(self, key):
            raise ResearchError("Existing run is temporarily unavailable")
    monkeypatch.setattr(map_region_routes, "research_client", Client)
    client = TestClient(main.app)
    job, _ = service.reserve(tmp_path, ENTITIES[ACTOR], prepared(), "resume-request-token")
    root = f'/profiles/{ACTOR}/regions/research/{job["id"]}'
    assert client.post(root.replace(ACTOR, "company-grower") + "/resume").status_code == 404 and not calls
    assert client.post(root + "/resume", follow_redirects=False).status_code == 303 and len(calls) == 1
    assert client.post(root + "/resume").status_code == 422 and len(calls) == 1
    assert client.post(root + "/recover", data={"provider_id": "existing-run", "confirm_run": "yes"}, follow_redirects=False).status_code == 303
    current = service.load(tmp_path)["jobs"][job["id"]]
    assert current["status"] == "submission_uncertain" and current["error"] == "Existing run is temporarily unavailable"
    assert not service.reserve(tmp_path, ENTITIES[ACTOR], prepared(), "duplicate-request-token")[1]
    # A separate reserved request can be stopped without any provider call.
    source = deepcopy(prepared())
    source["source"]["source_url"] = "https://example.org/another-source"
    stopped, _ = service.reserve(tmp_path, ENTITIES[ACTOR], source, "stop-request-token")
    stop_url = f'/profiles/{ACTOR}/regions/research/{stopped["id"]}/cancel'
    assert client.post(stop_url, data={"revision": 99}).status_code == 409
    assert client.post(stop_url, data={"revision": stopped["revision"]}, follow_redirects=False).status_code == 303
    assert service.load(tmp_path)["jobs"][stopped["id"]]["status"] == "cancelled" and len(calls) == 1
