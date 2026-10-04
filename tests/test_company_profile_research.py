from concurrent.futures import ThreadPoolExecutor
import json

from fastapi.testclient import TestClient
import pytest

from app import main, company_routes
from app.services import company_directory as directory, company_profile_research as research
from app.services.ai_gateway.perplexity_deep_research import ResearchError

COMPANY = {"id": "company-planasa", "name": "Planasa", "website": "https://planasa.com/", "aliases": []}
SOURCE = "https://planasa.com/about/"


def result(*items, status="completed", provider_id="research-fixture"):
    return {"provider_id": provider_id, "provider_status": status, "text": json.dumps({"proposals": list(items)}),
            "citations": [{"url": SOURCE, "title": "Company team and official profiles"}], "model": "fixture-model", "usage": {}}


def proposal(kind="website", **fields):
    return {"kind": kind, "source_url": SOURCE, "source_note": "Listed on the company's public page; review the original context.",
            **({"value": "https://planasa.com/new/"} if kind == "website" else {}), **fields}


def ready(inbox, *items):
    job, _ = research.reserve(inbox, COMPANY, "token-" + str(len(research.load(inbox)["jobs"])) + "-fixture-long")
    claimed = research.claim(inbox, job["id"])
    return research.apply_result(inbox, job["id"], result(*(items or [proposal()])), revision=claimed["revision"])


def test_public_request_excludes_private_fields_and_only_submits_once(tmp_path):
    sent = []
    company = {**COMPANY, "people": [{"name": "PRIVATE CONTACT"}], "notes": "PRIVATE NOTES", "description": "PRIVATE BODY"}
    jobs = list(ThreadPoolExecutor(4).map(lambda _: research.reserve(tmp_path, company, "fixture-token-long"), range(4)))
    assert sum(created for _, created in jobs) == 1
    key = jobs[0][0]["id"]
    class Client:
        def start(self, prompt):
            sent.append(prompt)
            return result(status="queued")
    list(ThreadPoolExecutor(4).map(lambda _: research.submit(tmp_path, key, Client), range(4)))
    assert len(sent) == 1 and "Planasa" in sent[0]
    assert all(text not in sent[0] for text in ["PRIVATE CONTACT", "PRIVATE NOTES", "PRIVATE BODY"])
    assert research.load(tmp_path)["jobs"][key]["config"]["prompt_version"] == "company-profile-proposals-v1"
    assert not (tmp_path / directory.PROFILE_FILE).exists()
    assert not research.reserve(tmp_path, COMPANY, "different-token-long")[1]


@pytest.mark.parametrize("item", [proposal(source_url="https://invented.example/"), proposal(value="http://127.0.0.1/private"),
    proposal(value="javascript:alert(1)"), proposal("social", platform="X|bad", handle="@x", url="https://x.com/example"),
    proposal("person", name="", role="CEO"), proposal("person", name="Ada", linkedin="https://user:password@example.com"),
    proposal("person", name="Ada", socials="bad"), proposal("unsupported")])
def test_unsafe_uncited_incomplete_proposals_are_retained_as_warnings_not_applied(tmp_path, item):
    job = ready(tmp_path, item)
    assert not job["proposals"] and job["warnings"]
    assert item["kind"] in job["text"] and not (tmp_path / directory.PROFILE_FILE).exists()


def test_malformed_partial_and_unsafe_native_citations_are_honest(tmp_path):
    job, _ = research.reserve(tmp_path, COMPANY, "malformed-token-long")
    response = result(proposal(), status="incomplete")
    response["text"] = "No structured results today"
    response["citations"].append({"url": "http://localhost/private", "title": "Private URL"})
    saved = research.apply_result(tmp_path, job["id"], response, revision=1)
    assert saved["status"] == "partial" and not saved["proposals"] and saved["warnings"]
    assert len(saved["citations"]) == 1 and len(saved["original_citations"]) == 2
    assert saved["text"] == response["text"]


def test_stale_result_wrong_run_and_terminal_results_never_replace(tmp_path):
    job, _ = research.reserve(tmp_path, COMPANY, "stale-token-fixture")
    first = research.apply_result(tmp_path, job["id"], result(status="queued"), revision=1)
    with pytest.raises(ValueError, match="another run"):
        research.apply_result(tmp_path, job["id"], result(provider_id="wrong"), revision=first["revision"])
    research.apply_result(tmp_path, job["id"], result(), revision=1)
    assert research.load(tmp_path)["jobs"][job["id"]]["status"] == "running"
    done = research.apply_result(tmp_path, job["id"], result(proposal()), revision=first["revision"])
    before = (tmp_path / research.FILENAME).read_bytes()
    research.apply_result(tmp_path, job["id"], result(proposal(value="https://example.org/changed")), revision=done["revision"])
    assert (tmp_path / research.FILENAME).read_bytes() == before


def test_network_failure_keeps_run_retrievable_and_uncertain_submission_blocks_duplicate(tmp_path):
    job, _ = research.reserve(tmp_path, COMPANY, "uncertain-token-long")
    class Client:
        def start(self, prompt):
            raise ResearchError("Could not confirm submission", uncertain=True)
    research.submit(tmp_path, job["id"], Client)
    uncertain = research.load(tmp_path)["jobs"][job["id"]]
    assert uncertain["status"] == "submission_uncertain"
    assert not research.reserve(tmp_path, COMPANY, "second-token-fixture")[1]
    running = research.apply_result(tmp_path, job["id"], result(status="queued"), revision=uncertain["revision"])
    failed_check = research.failure(tmp_path, job["id"], ResearchError("Try checking again"), revision=running["revision"])
    assert failed_check["status"] == "running" and failed_check["provider_id"] == "research-fixture"
    assert research.apply_result(tmp_path, job["id"], result(proposal()), revision=failed_check["revision"])["status"] == "ready"


def test_unsubmitted_stop_and_resume_cannot_resubmit_claimed_job(tmp_path):
    job, _ = research.reserve(tmp_path, COMPANY, "stop-token-fixture")
    research.stop_unsubmitted(tmp_path, job["id"], revision=1)
    assert research.claim(tmp_path, job["id"]) is None
    assert research.reserve(tmp_path, COMPANY, "new-request-fixture")[1]
    with pytest.raises(ValueError, match="changed"):
        research.stop_unsubmitted(tmp_path, job["id"], revision=1)


def test_saved_blank_and_stale_edits_are_protected_selective_acceptance_is_idempotent(tmp_path):
    manual = directory.edit_profile(tmp_path, entity_id=COMPANY["id"], payload={"revision": 0, "website": "", "linkedin": "https://example.org/manual", "socials": ""})
    job = ready(tmp_path)
    p = job["proposals"][0]
    before = (tmp_path / directory.PROFILE_FILE).read_bytes()
    with pytest.raises(ValueError, match="blank"):
        research.accept(tmp_path, job["id"], p["id"], profile_revision=1)
    with pytest.raises(ValueError, match="changed"):
        research.accept(tmp_path, job["id"], p["id"], profile_revision=0, replace=True)
    assert (tmp_path / directory.PROFILE_FILE).read_bytes() == before
    accepted = research.accept(tmp_path, job["id"], p["id"], profile_revision=1, replace=True, reviewer="Analyst")
    assert accepted["website"] == p["value"] and accepted["linkedin"] == manual["linkedin"]
    assert accepted["socials"] == [] and accepted["people"] == {}
    assert research.accept(tmp_path, job["id"], p["id"], profile_revision=1) == accepted
    assert len(directory.load_profiles(tmp_path)["history"]) == 2
    assert next(iter(accepted["research_acceptances"].values()))["source_url"] == SOURCE
    directory.edit_profile(tmp_path, entity_id=COMPANY["id"], payload={"revision": 2, "action": "reset"})
    assert research.accept(tmp_path, job["id"], p["id"], profile_revision=3)["revision"] == 3


def test_new_contact_preserves_people_and_source_history_without_canonical_identity(tmp_path):
    directory.edit_profile(tmp_path, entity_id=COMPANY["id"], payload={"revision": 0, "action": "person", "name": "Existing Person"})
    job = ready(tmp_path, proposal("person", name="Ada Berry", role="Listed as breeder in a 2024 team page", linkedin="https://www.linkedin.com/in/ada-berry/"))
    p = job["proposals"][0]
    saved = research.accept(tmp_path, job["id"], p["id"], profile_revision=1)
    assert len(saved["people"]) == 2
    person_id = "contact-research-" + p["id"]
    assert saved["people"][person_id]["research_source"]["source_url"] == SOURCE
    edited = directory.edit_profile(tmp_path, entity_id=COMPANY["id"], payload={"revision": 2, "action": "person", "person_id": person_id, "name": "Ada Corrected", "role": "Updated by analyst"})
    assert edited["people"][person_id]["research_source"] == saved["people"][person_id]["research_source"]
    assert directory.people_for(COMPANY["id"], {}, [], [], edited)[0]["basis"] == "User-edited contact · not reviewed"
    assert {f.name for f in tmp_path.iterdir()} == {research.FILENAME, directory.PROFILE_FILE}


def test_duplicate_people_dismissal_and_social_append_preserve_saved_data(tmp_path):
    job = ready(tmp_path, proposal("person", name="Ada", role="Breeder"), proposal("social", platform="Instagram", handle="@planasa", url="https://www.instagram.com/planasa/"))
    person, social = job["proposals"]
    with pytest.raises(ValueError, match="already exists"):
        research.accept(tmp_path, job["id"], person["id"], profile_revision=0, known_people=[{"name": "ADA"}])
    research.dismiss(tmp_path, job["id"], person["id"], revision=job["revision"])
    with pytest.raises(ValueError, match="dismissed"):
        research.accept(tmp_path, job["id"], person["id"], profile_revision=0)
    old_social = {"platform": "YouTube", "handle": "", "url": "https://www.youtube.com/@company"}
    accepted = research.accept(tmp_path, job["id"], social["id"], profile_revision=0, current_socials=[old_social])
    assert accepted["socials"] == [old_social, social["value"]]


def test_damaged_history_fails_without_overwrite(tmp_path):
    file = tmp_path / research.FILENAME
    file.write_text('{"version":1,"jobs":[]}', encoding="utf-8")
    before = file.read_bytes()
    with pytest.raises(ValueError, match="cannot be read"):
        research.reserve(tmp_path, COMPANY, "fixture-token-long")
    assert file.read_bytes() == before


def test_background_capacity_is_bounded_and_unknown_token_cannot_cross_company(tmp_path):
    research.reserve(tmp_path, COMPANY, "capacity-token-first")
    with pytest.raises(ValueError, match="another company"):
        research.reserve(tmp_path, {**COMPANY, "id": "company-second"}, "capacity-token-first")
    research.reserve(tmp_path, {**COMPANY, "id": "company-second"}, "capacity-token-second")
    with pytest.raises(ValueError, match="Finish or stop"):
        research.reserve(tmp_path, {**COMPANY, "id": "company-third"}, "capacity-token-third")


def test_cited_code_fence_deduplication_and_escaped_ui_are_untrusted():
    response = result(proposal(source_note="<script>never execute this</script>"), proposal())
    parsed, warnings = research.proposals("```json\n" + response["text"] + "\n```", response["citations"], "fixture")
    assert len(parsed) == 1 and not warnings
    job = {"id": "fixture", "created_at": "2026-10-04", "updated_at": "2026-10-04", "provider_id": "", "status": "ready",
           "status_label": "Suggestions ready to review", "error": "", "warnings": [], "config": {"provider": "fixture"},
           "proposals": [{**parsed[0], "accepted": False, "dismissed": False}], "citations": response["citations"], "text": response["text"]}
    from starlette.requests import Request
    rendered = main.templates.env.get_template("_company_research.html").render(authoring_mode=True, profile_research_jobs=[job],
        profile_override={"revision": 0}, company={"name": "Example", "website": ""}, request=Request({"type": "http", "query_string": b""}))
    assert "<script>never execute this</script>" not in rendered and "&lt;script&gt;never execute this&lt;/script&gt;" in rendered


def test_recovery_checks_existing_id_never_resubmits_and_failed_checks_keep_history(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    job, _ = research.reserve(tmp_path, COMPANY, "recovery-fixture-token")
    claimed = research.claim(tmp_path, job["id"])
    research.failure(tmp_path, job["id"], ResearchError("Submission uncertain", uncertain=True), revision=claimed["revision"], submitting=True)
    calls = []
    class Client:
        def start(self, prompt):
            pytest.fail("Recovery cannot submit another paid request")
        def check(self, key):
            calls.append(key)
            return result(status="queued", provider_id=key)
        def cancel(self, key):
            calls.append("cancel:" + key)
            return result(status="cancelled", provider_id=key)
    monkeypatch.setattr(company_routes, "profile_research_client", Client)
    client = TestClient(main.app)
    path = f'/companies/company-planasa/research/{job["id"]}'
    assert client.post(path + "/recover", data={"provider_id": "existing-id"}).status_code == 422 and not calls
    assert client.post(path + "/recover", data={"provider_id": "existing-id", "confirm_run": "yes"}, follow_redirects=False).status_code == 303
    assert calls == ["existing-id"]
    assert client.post(path + "/resume").status_code == 422
    assert client.post(path + "/cancel", follow_redirects=False).status_code == 303
    assert research.load(tmp_path)["jobs"][job["id"]]["status"] == "cancelled"


def test_company_routes_use_public_identity_private_guards_sources_and_review(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    calls = []
    class Client:
        def start(self, prompt):
            calls.append(prompt)
            return result(proposal(), proposal("person", name="Fixture Contact", role="Historical breeder"))
    monkeypatch.setattr(company_routes, "profile_research_client", Client)
    directory.edit_profile(tmp_path, entity_id=COMPANY["id"], payload={"revision": 0, "website": "https://example.org/PRIVATE-EDIT"})
    client = TestClient(main.app)
    endpoint = "/companies/company-planasa/research/start"
    payload = {"token": "browser-fixture-token", "tab": "details"}
    assert client.post(endpoint, data=payload, headers={"sec-fetch-site": "cross-site"}).status_code == 403
    assert not calls and not (tmp_path / research.FILENAME).exists()
    assert client.post(endpoint, data=payload, follow_redirects=False).status_code == 303
    assert len(calls) == 1 and "PRIVATE-EDIT" not in calls[0]
    job = next(iter(research.load(tmp_path)["jobs"].values()))
    assert client.get("/entities/company/company-planasa?tab=details").status_code == 200
    page = client.get("/entities/company/company-planasa?tab=people").text
    assert "Find company details" in page and "Fixture Contact" in page and "Replace my saved website" in page
    assert "Find company details" not in client.get("/entities/company/company-planasa?tab=news").text
    path = f'/companies/company-planasa/research/{job["id"]}'
    accept = {"proposal_id": job["proposals"][0]["id"], "revision": 1}
    assert client.post(path + "/accept", data=accept, follow_redirects=False).status_code == 422
    assert client.post(path + "/accept", data={**accept, "replace": "yes"}, follow_redirects=False).status_code == 303
    assert client.post(path.replace("company-planasa", "company-costa") + "/accept", data=accept).status_code == 404
    assert client.post(endpoint, data=payload, follow_redirects=False).status_code == 303 and len(calls) == 1
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    def forbidden(*args, **kwargs):
        pytest.fail("Read-only view must not read private company research")
    monkeypatch.setattr(research, "load", forbidden)
    assert "Fixture Contact" not in client.get("/entities/company/company-planasa?tab=people").text
    assert client.post(path + "/check").status_code == 403
    assert client.post(endpoint, data=payload).status_code == 403


def test_provider_reference_tags_are_plain_language_in_view_without_changing_original(tmp_path):
    job, _ = research.reserve(tmp_path, COMPANY, "source-tags-fixture")
    response = result(proposal(source_note="Public company page [web:35]. The role may be historical [web:999]."))
    response["citations"][0]["reference_ids"] = ["web:35"]
    job = research.apply_result(tmp_path, job["id"], response, revision=1)
    view = research.view(job, {})
    assert view["proposals"][0]["source_note_display"] == "Public company page. The role may be historical."
    assert view["proposals"][0]["unresolved_reference"]
    assert "[web:35]" in research.load(tmp_path)["jobs"][job["id"]]["proposals"][0]["source_note"]
    assert research.readable_note("Literal [limited scope] stays [web:35]", response["citations"]) == ("Literal [limited scope] stays", False)


def test_accepted_contact_sources_hide_provider_tags_but_keep_later_literal_edits(tmp_path):
    job, _ = research.reserve(tmp_path, COMPANY, "contact-source-tags")
    response = result(proposal("person", name="Ada", role="Historical breeder [web:1]", source_note="Named in the 2024 source [web:1]."))
    response["citations"][0]["reference_ids"] = ["web:1"]
    job = research.apply_result(tmp_path, job["id"], response, revision=1)
    saved = research.accept(tmp_path, job["id"], job["proposals"][0]["id"], profile_revision=0)
    row = directory.people_for(COMPANY["id"], {}, [], [], saved)[0]
    assert row["role"] == "Historical breeder" and "[web:" not in row["research_source"]["source_note_display"]
    key = row["id"]
    edited = directory.edit_profile(tmp_path, entity_id=COMPANY["id"], payload={"revision": 1, "action": "person", "person_id": key, "name": "Ada", "role": "Literal analyst edit [limited scope]"})
    assert directory.people_for(COMPANY["id"], {}, [], [], edited)[0]["role"] == "Literal analyst edit [limited scope]"
