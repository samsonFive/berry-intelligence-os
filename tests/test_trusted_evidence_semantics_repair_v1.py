"""Trusted Evidence Semantics Repair V1.

Proves the hard acceptance test: an ordinary Publication's source
approval alone cannot create trusted Evidence -- an explicit,
analyst-approved factual claim is required, is independently auditable,
and legacy records are never mass-mutated.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main
from app.main import app
from app.services.evidence_claim_review import (
    ORIGIN_PUBLICATION_PROSE,
    ORIGIN_STRUCTURED_REGISTRY,
    TIER_APPROVED_SOURCE,
    TIER_REVIEWED_EVIDENCE,
    TIER_TRUSTED_EVIDENCE,
    evidence_trust_tier,
    prepare_candidate_proposition,
    trust_tier_label,
)
from app.services.review_events import load_review_events
from tests.test_review_publish_portability import SOURCE_ID, _item, _publish, _restore


@pytest.fixture
def restored_runtime(monkeypatch, tmp_path: Path):
    inbox = tmp_path / "inbox"
    data = tmp_path / "data"
    monkeypatch.setattr(main, "INBOX_DIR", inbox)
    monkeypatch.setattr(main, "DATA_DIR", data)
    main._JSON_FOLDER_CACHE.clear()
    repos = main.get_repositories(data, main.SCHEMAS_DIR)
    repos.sources.create({"id": SOURCE_ID, "name": "Lucentlands Podcast"})
    draft_id = _restore(inbox)
    return {"inbox": inbox, "data": data, "draft_id": draft_id}


# --- pure classification / preparation functions ---


def test_evidence_trust_tier_legacy_records_untouched():
    legacy = {"evidence_role": None, "fact_ids": []}
    assert evidence_trust_tier(legacy) == TIER_REVIEWED_EVIDENCE
    legacy_with_facts = {"evidence_role": None, "fact_ids": ["fact-x-1"]}
    assert evidence_trust_tier(legacy_with_facts) == TIER_REVIEWED_EVIDENCE


def test_evidence_trust_tier_atomic_evidence_untouched():
    atomic = {"evidence_role": "atomic_evidence", "fact_ids": []}
    assert evidence_trust_tier(atomic) == TIER_REVIEWED_EVIDENCE


def test_evidence_trust_tier_publication_without_facts_is_approved_source_only():
    record = {"evidence_role": "publication_artifact", "fact_ids": []}
    assert evidence_trust_tier(record) == TIER_APPROVED_SOURCE
    assert trust_tier_label(record) == "APPROVED SOURCE"


def test_evidence_trust_tier_publication_with_facts_is_trusted_evidence():
    record = {"evidence_role": "publication_artifact", "fact_ids": ["fact-x-1"]}
    assert evidence_trust_tier(record) == TIER_TRUSTED_EVIDENCE
    assert trust_tier_label(record) == "TRUSTED EVIDENCE"


def test_prepare_candidate_proposition_prose_uses_why_it_matters_first():
    draft = {"why_it_matters": "Real analyst-facing rationale.", "summary": "Fallback summary."}
    statement, origin = prepare_candidate_proposition(draft)
    assert statement == "Real analyst-facing rationale."
    assert origin == ORIGIN_PUBLICATION_PROSE


def test_prepare_candidate_proposition_prose_falls_back_to_summary():
    draft = {"why_it_matters": "", "summary": "Fallback summary text."}
    statement, origin = prepare_candidate_proposition(draft)
    assert statement == "Fallback summary text."
    assert origin == ORIGIN_PUBLICATION_PROSE


def test_prepare_candidate_proposition_never_invents_fields_not_present():
    draft = {"intake_type": "pvr_filing", "cpvo_filing": {"denomination": "Bella"}, "title": "x"}
    statement, origin = prepare_candidate_proposition(draft)
    assert origin == ORIGIN_STRUCTURED_REGISTRY
    assert "Bella" in statement
    assert "unstated applicant" in statement  # never fabricates a missing applicant name


def test_prepare_candidate_proposition_structured_registry_pvr():
    draft = {
        "intake_type": "pvr_filing",
        "cpvo_filing": {
            "denomination": "Plablue 1542",
            "species_name": "Vaccinium corymbosum L.",
            "applicants": ["Plantas de Navarra S.A."],
            "title_status": "approved",
            "granting_date": "2023-04-17",
        },
    }
    statement, origin = prepare_candidate_proposition(draft)
    assert origin == ORIGIN_STRUCTURED_REGISTRY
    assert "Plablue 1542" in statement
    assert "Plantas de Navarra S.A." in statement
    assert "2023-04-17" in statement


def test_prepare_candidate_proposition_structured_registry_patent():
    draft = {
        "intake_type": "patent_filing",
        "patent_filing": {
            "cultivar_name": "DrisStrawOneHundredOne",
            "assignees": ["Driscoll's, Inc."],
            "publication_number": "USPP35158P2",
            "grant_date": "2023-05-09",
        },
    }
    statement, origin = prepare_candidate_proposition(draft)
    assert origin == ORIGIN_STRUCTURED_REGISTRY
    assert "USPP35158P2" in statement
    assert "Driscoll's, Inc." in statement


# --- HTTP-level hard acceptance test ---


def test_publication_promote_alone_cannot_create_trusted_evidence(restored_runtime):
    """THE hard acceptance test: source approval alone is not enough."""
    client = TestClient(app)
    draft_id = restored_runtime["draft_id"]

    response = _publish(client, draft_id)
    assert response.status_code == 303
    assert response.headers["location"].startswith(f"/review/{draft_id}/claim")

    published = main.get_repositories(restored_runtime["data"], main.SCHEMAS_DIR).evidence.get(draft_id)
    assert published is not None
    assert published["status"] == "published"  # the record exists...
    assert published["fact_ids"] == []
    assert evidence_trust_tier(published) == TIER_APPROVED_SOURCE  # ...but is NOT trusted Evidence yet
    assert trust_tier_label(published) == "APPROVED SOURCE"
    assert "pending_claim" in published
    assert published["pending_claim"]["candidate_statement"]


def test_claim_review_get_never_mutates(restored_runtime):
    client = TestClient(app)
    draft_id = restored_runtime["draft_id"]
    _publish(client, draft_id)
    before = main.get_repositories(restored_runtime["data"], main.SCHEMAS_DIR).evidence.get(draft_id)

    response = client.get(f"/review/{draft_id}/claim")
    assert response.status_code == 200
    assert "Approve" in response.text
    assert before["pending_claim"]["candidate_statement"] in response.text

    after = main.get_repositories(restored_runtime["data"], main.SCHEMAS_DIR).evidence.get(draft_id)
    assert after == before  # GET changed nothing


def test_claim_approve_creates_fact_and_promotes_to_trusted_evidence(restored_runtime):
    client = TestClient(app)
    draft_id = restored_runtime["draft_id"]
    inbox = restored_runtime["inbox"]
    data = restored_runtime["data"]
    _publish(client, draft_id)

    response = client.post(
        f"/review/{draft_id}/claim/approve",
        data={
            "statement": "Lucentlands podcast discussed scaling the blueberry industry in Africa.",
            "proposed_statement": "",
            "classification": "fact",
            "confidence": "medium",
            "reviewer": "johnny",
            "origin": "publication_claim_review",
            "return_to": "/pending",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    repos = main.get_repositories(data, main.SCHEMAS_DIR)
    published = repos.evidence.get(draft_id)
    assert len(published["fact_ids"]) == 1
    assert "pending_claim" not in published
    assert evidence_trust_tier(published) == TIER_TRUSTED_EVIDENCE

    fact_id = published["fact_ids"][0]
    fact = repos.facts.get(fact_id)
    assert fact["statement"] == "Lucentlands podcast discussed scaling the blueberry industry in Africa."
    assert fact["reviewer"] == "johnny"
    assert fact["evidence_ids"] == [draft_id]
    assert fact["origin"] == "publication_claim_review"
    assert fact["edited_before_approval"] is True  # differs from the empty proposed_statement sent

    events = load_review_events(inbox)
    claim_events = [e for e in events if e["workflow"] == "evidence_claim_review"]
    assert len(claim_events) == 1
    assert claim_events[0]["action"] == "approve_claim"
    assert claim_events[0]["actor"] == "johnny"


def test_claim_edited_before_approval_is_recorded_accurately(restored_runtime):
    client = TestClient(app)
    draft_id = restored_runtime["draft_id"]
    data = restored_runtime["data"]
    _publish(client, draft_id)
    published = main.get_repositories(data, main.SCHEMAS_DIR).evidence.get(draft_id)
    candidate = published["pending_claim"]["candidate_statement"]

    # Approve verbatim, no edit.
    client.post(
        f"/review/{draft_id}/claim/approve",
        data={"statement": candidate, "proposed_statement": candidate, "reviewer": "johnny", "return_to": "/pending"},
        follow_redirects=False,
    )
    repos = main.get_repositories(data, main.SCHEMAS_DIR)
    fact = repos.facts.get(repos.evidence.get(draft_id)["fact_ids"][0])
    assert fact["edited_before_approval"] is False


def test_claim_reject_leaves_source_approved_but_not_trusted(restored_runtime):
    client = TestClient(app)
    draft_id = restored_runtime["draft_id"]
    inbox = restored_runtime["inbox"]
    data = restored_runtime["data"]
    _publish(client, draft_id)

    response = client.post(
        f"/review/{draft_id}/claim/reject",
        data={"reviewer": "johnny", "reason": "No distinct claim here.", "return_to": "/pending"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    published = main.get_repositories(data, main.SCHEMAS_DIR).evidence.get(draft_id)
    assert published["status"] == "published"  # source stays approved
    assert published["fact_ids"] == []
    assert evidence_trust_tier(published) == TIER_APPROVED_SOURCE  # still not trusted

    events = load_review_events(inbox)
    claim_events = [e for e in events if e["workflow"] == "evidence_claim_review"]
    assert len(claim_events) == 1 and claim_events[0]["action"] == "reject_claim"


def test_atomic_evidence_path_is_unaffected(restored_runtime):
    """Atomic Evidence review keeps its own unchanged mechanics and is
    never routed through the new claim-review screen."""
    client = TestClient(app)
    inbox = restored_runtime["inbox"]
    data = restored_runtime["data"]
    draft_id = restored_runtime["draft_id"]
    # Overwrite the restored draft as an atomic_evidence proposal instead.
    path = inbox / "evidence" / f"{draft_id}.json"
    draft = json.loads(path.read_text(encoding="utf-8"))
    draft["evidence_role"] = "atomic_evidence"
    draft["summary"] = "A specific proposed factual statement."
    draft["parent_evidence_id"] = "ev-parent-example"
    draft["artifact_locator"] = {"start_seconds": 20}
    draft["extraction_provenance"] = {"method": "human", "extracted_by": "johnny", "extracted_at": "2026-08-01"}
    path.write_text(json.dumps(draft), encoding="utf-8")

    response = _publish(client, draft_id, summary="A specific proposed factual statement.")
    assert response.status_code == 303
    assert "/claim" not in response.headers["location"]

    published = main.get_repositories(data, main.SCHEMAS_DIR).evidence.get(draft_id)
    assert evidence_trust_tier(published) == TIER_REVIEWED_EVIDENCE  # unconditional, unchanged
    assert "review_outcome" in published


def test_missing_evidence_claim_form_404s(restored_runtime):
    client = TestClient(app)
    response = client.get("/review/ev-media-does-not-exist/claim")
    assert response.status_code == 404
