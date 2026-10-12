"""Fictional workflow acceptance: identity != source approval != verified claim."""
import json
from html.parser import HTMLParser

import pytest
from fastapi.testclient import TestClient

from app import main
from app.services.evidence_claim_review import evidence_trust_tier, TIER_APPROVED_SOURCE, TIER_TRUSTED_EVIDENCE
from app.services.variety_catalog_handoff import catalog_handoff, decision_digest
from app.services.review_publish import PublishRequest
from app.services.variety_universe.candidates import apply_identity_decision, load_variety_candidates, persist_variety_candidates


@pytest.fixture
def workspace(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path / "inbox")
    monkeypatch.setattr(main, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    repos = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    candidate = apply_identity_decision({
        "id": "vcand-fictional-handoff", "record_type": "variety_candidate",
        "candidate_name": "Fictional Review Blue", "berry_id": "berry-blueberry",
        "source_url": "https://example.test/portfolio?lang=en&item=blue", "source_label": "Fictional portfolio",
        "knowledge": {}, "registration": {}, "identity_state": "unknown", "status": "pending",
        "breeder_code": "TEST 001", "review_notes": None,
    }, decision="distinct", reviewer="fixture-identity-reviewer", notes="Fictional private identity note")
    persist_variety_candidates([candidate], inbox_dir=main.INBOX_DIR)
    monkeypatch.setattr(main, "variety_candidate_universe", lambda: (
        [r for r in repos.entities.list() if r.get("entity_type") == "variety"],
        load_variety_candidates(main.INBOX_DIR), {},
    ))
    return TestClient(main.app), candidate, repos


def intake_data(candidate):
    return {"intake_type": "article_or_url", "catalog_candidate": candidate["id"],
            "catalog_decision_digest": decision_digest(candidate), "title": "Fictional catalog source",
            "source_url": candidate["source_url"], "source_name": "Fictional portfolio",
            "summary": "The fictional portfolio lists Fictional Review Blue as a blueberry variety.",
            "suggested_varieties": candidate["candidate_name"], "submitted_by": "fixture-operator"}


def publish_data(candidate):
    data = intake_data(candidate)
    return {**data, "varieties": candidate["candidate_name"], "berries": [candidate["berry_id"]],
            "reviewer": "fixture-source-reviewer"}


def create_draft(client, candidate):
    response = client.post("/intake", data=intake_data(candidate), follow_redirects=False)
    assert response.status_code == 303, response.text
    assert response.headers["location"].startswith("/review/")
    return response.headers["location"].rsplit("/", 1)[-1]


def snapshot():
    return {str(p): p.read_bytes() for root in (main.INBOX_DIR, main.DATA_DIR) for p in root.rglob("*.json")}


def test_preparation_is_read_only_and_does_not_invent_source_text_dates_or_roles(workspace):
    client, candidate, _ = workspace
    before = snapshot()
    response = client.get(catalog_handoff(candidate, [])["href"])
    assert response.status_code == 200
    assert "Identity checked → Source review → Claim review" in response.text
    assert '<textarea id="summary" name="summary" rows="4" required></textarea>' in response.text
    assert 'name="published_date" type="date" value=""' in response.text
    assert 'name="suggested_competitors" type="text" placeholder="Comma-separated" value=""' in response.text
    assert "lang=en&amp;item=blue" in response.text
    assert "Fictional private identity note" in response.text
    assert snapshot() == before


def test_handoff_preserves_identity_and_requires_separate_source_and_claim_decisions(workspace):
    client, candidate, repos = workspace
    candidate_path = main.INBOX_DIR / "variety_candidates" / (candidate["id"] + ".json")
    identity_bytes = candidate_path.read_bytes()
    draft_id = create_draft(client, candidate)
    draft = main.get_draft(draft_id)
    assert draft["evidence_role"] == "publication_artifact"
    assert draft["berry_ids"] == ["berry-blueberry"]
    assert not repos.entities.list()
    assert client.get(f"/review/{draft_id}").status_code == 200
    missing = client.post(f"/review/{draft_id}/publish", data={**publish_data(candidate), "reviewer": ""})
    assert missing.status_code == 400
    assert not repos.entities.list()
    response = client.post(f"/review/{draft_id}/publish", data=publish_data(candidate), follow_redirects=False)
    assert response.status_code == 303, response.text
    assert response.headers["location"].startswith(f"/review/{draft_id}/claim")
    entity, = repos.entities.list()
    assert entity["name"] == candidate["candidate_name"]
    assert entity["status"] == "unverified"
    assert entity["aliases"] == [] and entity["roles"] == [] and entity["attributes"] == {}
    assert entity["evidence_ids"] == [draft_id]
    evidence = repos.evidence.get(draft_id)
    assert evidence["source_url"] == candidate["source_url"]
    assert evidence["fact_ids"] == []
    assert evidence_trust_tier(evidence) == TIER_APPROVED_SOURCE
    assert not repos.facts.list() and not repos.relationships.list()
    public_text = json.dumps(evidence)
    assert "catalog_handoff" not in public_text and candidate["id"] not in public_text
    assert "Fictional private identity note" not in public_text
    assert candidate_path.read_bytes() == identity_bytes
    before = snapshot()
    claim_page = client.get(f"/review/{draft_id}/claim")
    assert claim_page.status_code == 200
    assert 'id="claim-reviewer" type="text" name="reviewer"' in claim_page.text
    assert 'id="claim-reject-reviewer" type="text" name="reviewer"' in claim_page.text
    assert snapshot() == before
    assert client.post(f"/review/{draft_id}/claim/approve", data={
        "statement": intake_data(candidate)["summary"], "reviewer": "",
    }).status_code == 400
    assert snapshot() == before
    approved = client.post(f"/review/{draft_id}/claim/approve", data={
        "statement": intake_data(candidate)["summary"], "reviewer": "fixture-claim-reviewer",
        "classification": "fact", "confidence": "medium",
    }, follow_redirects=False)
    assert approved.status_code == 303
    assert evidence_trust_tier(repos.evidence.get(draft_id)) == TIER_TRUSTED_EVIDENCE
    assert len(repos.facts.list()) == 1
    assert repos.entities.get(entity["id"])["status"] == "unverified"
    assert candidate_path.read_bytes() == identity_bytes


@pytest.mark.parametrize("change", [{"human_gated": False}, {"human_gated": "false"}, {"identity_state": "possible_alias"},
    {"status": "rejected"}, {"reviewer": ""}, {"reviewed_at": None}, {"berry_id": None}])
def test_unresolved_candidates_cannot_prepare_or_save(workspace, change):
    client, candidate, _ = workspace
    revised = {**candidate, **change}
    persist_variety_candidates([revised], inbox_dir=main.INBOX_DIR, overwrite=True)
    before = snapshot()
    assert client.get(catalog_handoff(revised, [])["href"]).status_code == 409
    assert client.post("/intake", data=intake_data(revised)).status_code == 409
    assert snapshot() == before


@pytest.mark.parametrize("point", ["intake", "publish"])
def test_stale_decision_blocks_all_writes(workspace, point):
    client, candidate, _ = workspace
    draft_id = create_draft(client, candidate) if point == "publish" else None
    updated = apply_identity_decision(candidate, decision="rejected", reviewer="fixture-second-reviewer")
    persist_variety_candidates([updated], inbox_dir=main.INBOX_DIR, overwrite=True)
    before = snapshot()
    response = client.post(f"/review/{draft_id}/publish" if draft_id else "/intake",
                           data=publish_data(candidate) if draft_id else intake_data(candidate))
    assert response.status_code == 409
    assert snapshot() == before


@pytest.mark.parametrize("alias", [False, True])
def test_existing_name_or_alias_blocks_duplicate_and_preserves_user_edits(workspace, alias):
    client, candidate, repos = workspace
    draft_id = create_draft(client, candidate)
    existing = {"id": "variety-user-entry", "record_type": "entity", "entity_type": "variety",
                "name": "User Canonical Name" if alias else candidate["candidate_name"],
                "aliases": [candidate["candidate_name"]] if alias else [], "status": "active",
                "description": "User-edited description"}
    repos.entities.create(existing)
    before = snapshot()
    assert client.get(catalog_handoff(candidate, [existing])["href"]).status_code == 409
    assert client.post(f"/review/{draft_id}/publish", data=publish_data(candidate)).status_code == 409
    assert snapshot() == before and repos.entities.get(existing["id"]) == existing


def test_ambiguous_aliases_cannot_prepare_a_third_record(workspace):
    client, candidate, repos = workspace
    for suffix in ("one", "two"):
        repos.entities.create({"id": "variety-" + suffix, "record_type": "entity", "entity_type": "variety",
                              "name": "Fictional " + suffix, "aliases": [candidate["candidate_name"]], "status": "active"})
    before = snapshot()
    response = client.post("/intake", data=intake_data(candidate))
    assert response.status_code == 409 and "multiple catalog records" in response.text
    assert snapshot() == before


@pytest.mark.parametrize("alias", [False, True])
def test_reviewed_cross_crop_name_creates_separate_source_linked_variety(workspace, alias):
    client, candidate, repos = workspace
    draft_id = create_draft(client, candidate)
    existing = {"id": "variety-fictional-review-blue", "record_type": "entity", "entity_type": "variety",
                "name": "Fictional Strawberry" if alias else candidate["candidate_name"], "berry_ids": ["berry-strawberry"],
                "aliases": [candidate["candidate_name"]] if alias else [],
                "status": "unverified", "description": "User-edited strawberry entry"}
    repos.entities.create(existing)
    before = snapshot()
    plan = catalog_handoff(candidate, [existing])
    assert plan["ready"] and plan["catalog_entity"] is None
    assert client.get(plan["href"]).status_code == 200
    assert snapshot() == before
    missing = client.post(f"/review/{draft_id}/publish", data={**publish_data(candidate), "reviewer": ""})
    assert missing.status_code == 400 and snapshot() == before
    assert client.post(f"/review/{draft_id}/publish", data=publish_data(candidate), follow_redirects=False).status_code == 303
    created, = [row for row in repos.entities.list() if row["id"] != existing["id"]]
    assert created["name"] == candidate["candidate_name"] and created["berry_ids"] == ["berry-blueberry"]
    assert created["status"] == "unverified" and not created["aliases"] and not created["roles"]
    assert created["evidence_ids"] == [draft_id] and not created["attributes"]
    assert repos.entities.get(existing["id"]) == existing
    assert repos.evidence.get(draft_id)["entity_ids"] == [created["id"]]
    assert not repos.facts.list() and not repos.relationships.list()
    from app.services.entity_identity import audit_entity_identity
    assert not audit_entity_identity(repos.entities.list())["varieties"]["canonical_collisions"]


@pytest.mark.parametrize("berries", [["berry-blueberry"], [], ["berry-blueberry", "berry-strawberry"]])
def test_crop_scoped_review_still_blocks_compatible_or_unknown_catalog_entries(workspace, berries):
    client, candidate, repos = workspace
    draft_id = create_draft(client, candidate)
    existing = {"id": "variety-overlap", "record_type": "entity", "entity_type": "variety",
                "name": candidate["candidate_name"], "berry_ids": berries, "aliases": [], "status": "unverified"}
    repos.entities.create(existing)
    before = snapshot()
    assert not catalog_handoff(candidate, [existing])["ready"]
    assert client.post(f"/review/{draft_id}/publish", data=publish_data(candidate)).status_code == 409
    assert snapshot() == before


def test_generic_source_review_cannot_attach_a_name_to_the_wrong_crop(workspace):
    client, candidate, repos = workspace
    draft_id = create_draft(client, candidate)
    draft = main.get_draft(draft_id)
    draft.pop("catalog_handoff")
    main.save_draft(draft)
    existing = {"id": "variety-other-crop", "record_type": "entity", "entity_type": "variety",
                "name": candidate["candidate_name"], "berry_ids": ["berry-strawberry"], "aliases": [], "status": "unverified"}
    repos.entities.create(existing)
    before = snapshot()
    response = client.post(f"/review/{draft_id}/publish", data=publish_data(candidate))
    assert response.status_code == 400 and "belongs to another berry" in response.text
    assert snapshot() == before


def test_review_aids_do_not_expand_the_checked_name_or_berry_scope(workspace):
    client, candidate, _ = workspace
    draft_id = create_draft(client, candidate)
    draft = main.get_draft(draft_id)
    draft["summary"] = "The fictional blueberry is separate from strawberry Fictional Other Name."
    draft["ai_enrichment"] = {"suggested_berry_ids": ["berry-strawberry"]}
    main.save_draft(draft)
    before = snapshot()
    class ScopeInputs(HTMLParser):
        def __init__(self):
            super().__init__()
            self.fields = []

        def handle_starttag(self, tag, attrs):
            fields = dict(attrs)
            if tag == "input" and fields.get("name") in {"berries", "varieties"}:
                self.fields.append(fields)

    page = ScopeInputs()
    page.feed(client.get(f"/review/{draft_id}").text)
    assert [item["value"] for item in page.fields if item["name"] == "berries" and "checked" in item] == [candidate["berry_id"]]
    assert next(item["value"] for item in page.fields if item["name"] == "varieties") == candidate["candidate_name"]
    assert snapshot() == before


@pytest.mark.parametrize("change", ["no_marker", "name", "berry", "invalid_berry", "catalog_arrived"])
def test_publish_service_rechecks_scoped_context_before_writes(workspace, change):
    client, candidate, repos = workspace
    draft_id = create_draft(client, candidate)
    draft = main.get_draft(draft_id)
    scope = (candidate["candidate_name"], candidate["berry_id"])
    if change == "no_marker":
        draft.pop("catalog_handoff")
    elif change == "name":
        scope = ("Changed Name", candidate["berry_id"])
    elif change == "berry":
        scope = (candidate["candidate_name"], "berry-strawberry")
    elif change == "invalid_berry":
        scope = (candidate["candidate_name"], "unknown-berry")
    else:
        repos.entities.create({"id": "variety-newly-added", "record_type": "entity", "entity_type": "variety",
                               "name": candidate["candidate_name"], "berry_ids": [candidate["berry_id"]], "status": "unverified"})
    before = snapshot()
    result = main._review_publish_service().publish(PublishRequest(
        draft=draft, draft_id=draft_id, title="Fictional scoped review", source_type="article",
        source_name="Fixture", source_url=candidate["source_url"], published_date=None, captured_date="2026-10-07",
        summary="Fictional source text", why_it_matters="", tags=[], selected_berries=[candidate["berry_id"]],
        all_entity_names_by_type={"variety": [candidate["candidate_name"]]}, facts_input=[], relationships_input=[],
        priority={}, strategic_question_text=[], reviewer="fixture-source-reviewer", catalog_variety_scope=scope))
    assert not result.ok and result.schema_errors
    assert snapshot() == before


@pytest.mark.parametrize("change", [{"suggested_varieties": "Different Name"},
    {"intake_type": "standalone_fact"}, {"source_url": "http://localhost/private"}])
def test_intake_refuses_changed_name_type_or_private_source(workspace, change):
    client, candidate, _ = workspace
    before = snapshot()
    assert client.post("/intake", data={**intake_data(candidate), **change}).status_code == 400
    assert snapshot() == before


@pytest.mark.parametrize("change", [{"varieties": "Different Name"}, {"berries": ["berry-strawberry"]},
    {"source_url": "http://127.0.0.1/private"}])
def test_review_cannot_change_checked_identity_or_use_private_source(workspace, change):
    client, candidate, _ = workspace
    draft_id = create_draft(client, candidate)
    before = snapshot()
    response = client.post(f"/review/{draft_id}/publish", data={**publish_data(candidate), **change})
    assert response.status_code == 400
    assert snapshot() == before


def test_same_origin_guard_and_readonly_apply_before_writes(workspace, monkeypatch):
    client, candidate, _ = workspace
    draft_id = create_draft(client, candidate)
    before = snapshot()
    for path, data in [("/intake", intake_data(candidate)),
                       (f"/review/{draft_id}/publish", publish_data(candidate)),
                       (f"/varieties/candidates/{candidate['id']}/decision", {"decision": "rejected"})]:
        assert client.post(path, data=data, headers={"origin": "https://foreign.example"}).status_code == 403
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    assert client.get(catalog_handoff(candidate, [])["href"]).status_code == 403
    assert client.post("/intake", data=intake_data(candidate)).status_code == 403
    assert snapshot() == before


def test_invalid_identity_decision_does_not_materialize_transient_candidate(workspace, monkeypatch):
    client, candidate, _ = workspace
    transient = {**candidate, "id": "vcand-transient"}
    monkeypatch.setattr(main, "variety_candidate_universe", lambda: ([], [transient], {}))
    before = snapshot()
    assert client.post("/varieties/candidates/vcand-transient/decision", data={"decision": "invalid"}).status_code == 400
    assert snapshot() == before


def test_saved_variety_decisions_never_read_signal_candidates_or_rediscover(workspace, monkeypatch):
    client, candidate, _ = workspace
    def forbidden(*args, **kwargs):
        raise AssertionError("A saved variety decision must use its private variety record")
    monkeypatch.setattr(main, "candidate_by_id", forbidden)
    monkeypatch.setattr(main, "variety_candidate_universe", forbidden)
    response = client.post(f"/varieties/candidates/{candidate['id']}/decision", data={
        "decision": "distinct", "reviewer": "fixture-identity-reviewer", "notes": "Keep saved variety provenance",
    }, follow_redirects=False)
    assert response.status_code == 303
    saved, = load_variety_candidates(main.INBOX_DIR)
    assert saved["source_url"] == candidate["source_url"] and saved["breeder_code"] == "TEST 001"
    assert saved["review_notes"] == "Keep saved variety provenance"


def test_filtered_return_and_notes_survive_identity_review(workspace):
    client, candidate, _ = workspace
    scope = "/varieties/candidates?berry=berry-blueberry&q=Fictional#" + candidate["id"]
    response = client.post(f"/varieties/candidates/{candidate['id']}/decision", data={
        "decision": "distinct", "reviewer": "fixture-identity-reviewer", "notes": "Keep this private note", "return_to": scope,
    }, follow_redirects=False)
    assert response.status_code == 303 and response.headers["location"] == scope
    page = client.get(scope)
    assert page.status_code == 200 and 'value="Keep this private note"' in page.text
    assert 'name="reviewer" value="fixture-identity-reviewer" required' in page.text
    assert "Prepare catalog review" in page.text
    for unsafe in ("https://foreign.example/varieties/candidates", "//foreign.example/varieties/candidates", "http://[broken"):
        response = client.post(f"/varieties/candidates/{candidate['id']}/decision", data={
            "decision": "distinct", "reviewer": "fixture-identity-reviewer", "return_to": unsafe,
        }, follow_redirects=False)
        assert response.headers["location"] == "/varieties/candidates"
