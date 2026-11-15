"""Private research navigation, human decisions and source-capture confinement."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main
from app.services.cultivar_measurements import normalize_measurement, stage_measurement
from app.services.cultivar_measurement_workspace import import_packets, source_artifact, workspace
from app.services.cultivar_measurements import CultivarMeasurementError


@pytest.fixture
def research_world(monkeypatch, tmp_path):
    data, inbox = tmp_path / "data", tmp_path / "inbox"
    monkeypatch.setattr(main, "DATA_DIR", data)
    monkeypatch.setattr(main, "INBOX_DIR", inbox)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    main._JSON_FOLDER_CACHE.clear()
    repos = main.get_repositories(data, main.SCHEMAS_DIR)
    for entity_id, kind, name in [("berry-strawberry", "berry", "Strawberry"),
                                  ("variety-one", "variety", "Cultivar One"),
                                  ("variety-two", "variety", "Cultivar Two")]:
        repos.entities.create({"id": entity_id, "record_type": "entity", "entity_type": kind,
                               "name": name, "status": "active", "berry_ids": ["berry-strawberry"]})
    repos.evidence.create({"id": "ev-planting-source", "record_type": "evidence", "status": "published",
                           "source_type": "report", "title": "Regional planting survey", "captured_date": "2026-11-14",
                           "source_url": "https://owner.example/survey.pdf", "summary": "Approved source context",
                           "submitted_by": "fixture", "evidence_role": "publication_artifact",
                           "entity_ids": ["berry-strawberry", "variety-one", "variety-two"], "fact_ids": [],
                           "priority": {k: {"level": "none", "rationale": ""} for k in
                                        ("reading", "testing", "commercial_position", "monitoring")}})
    native = {"id": "REGION-1", "region": "Spain", "subregion": "Huelva plants",
              "cultivar": "Cultivar One", "record_kind": "cultivar", "platform_entity_ids": ["variety-one"],
              "platform_candidate_ids": ["variety-one"], "source_ids": ["S1"], "claim": "A reported planting share",
              "evidence_type": "Reported planting share", "value": 13.5, "unit": "percent plants",
              "denominator": "Huelva surveyed plants", "data_period": "2025/26",
              "limitations": "Province only. <script>bad()</script>"}
    binding = {"source_id": "S1", "evidence_id": "ev-planting-source", "source_url": "https://owner.example/survey.pdf",
               "source_title": "Regional planting survey", "locator": "Figure 1, p7", "source_dataset": "2025-26"}
    record = normalize_measurement(native, source_bindings=[binding], berry_id="berry-strawberry",
                                   captured_at="2026-11-14T00:00:00Z", import_batch_id="fixture-import",
                                   entities_by_id={r["id"]: r for r in repos.entities.list()})
    stage_measurement(inbox, record)
    return {"data": data, "inbox": inbox, "repos": repos, "record": record,
            "native": native, "binding": binding, "client": TestClient(main.app)}


def test_private_list_and_detail_show_scope_and_never_execute_source_prose(research_world):
    w = research_world
    response = w["client"].get("/variety-plantings?region=Spain&berry=strawberry")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    assert "Huelva surveyed plants" in response.text and "2025/26" in response.text
    assert "&lt;script&gt;bad()&lt;/script&gt;" in response.text
    assert "<script>bad()</script>" not in response.text
    detail = w["client"].get("/variety-plantings/" + w["record"]["id"])
    assert detail.status_code == 200
    assert "Primary source for this proposition" in detail.text
    assert "source_confirmation_note" in detail.text and "confirm_individual_review" in detail.text
    assert "Cultivar identity" in detail.text
    assert w["repos"].facts.list() == []


def test_filtering_keeps_unknown_values_distinct_from_zero_and_paginates():
    rows = [{"id": str(i), "region": "Queensland", "cultivar_label": "Label", "review_state": "pending",
             "berry_id": "berry-strawberry", "value": 0 if i == 0 else None, "data_period": "2026"}
            for i in range(45)]
    model = workspace(rows, region="Queensland", page=2)
    assert model["matching"] == 45 and len(model["rows"]) == 5
    assert model["previous_href"] and model["next_href"] is None
    assert workspace(rows, berry="berry-blueberry")["matching"] == 0
    assert rows[0]["value"] == 0 and rows[1]["value"] is None


def test_review_requires_individual_confirmation_and_explicit_source(research_world):
    w = research_world; url = "/variety-plantings/" + w["record"]["id"] + "/review"
    payload = {"action": "approve", "content_sha256": w["record"]["content_sha256"], "reviewer": "analyst"}
    assert w["client"].post(url, data=payload).status_code == 400
    payload["confirm_individual_review"] = "true"
    assert w["client"].post(url, data=payload).status_code == 409
    assert w["repos"].facts.list() == []


def test_explicit_claim_decision_uses_session_actor_and_exact_cultivar_scope(research_world, monkeypatch):
    w = research_world
    monkeypatch.setattr(main, "session_username", lambda request: "signed-in-analyst")
    response = w["client"].post("/variety-plantings/" + w["record"]["id"] + "/review", data={
        "action": "approve", "content_sha256": w["record"]["content_sha256"], "reviewer": "spoofed-person",
        "confirm_individual_review": "true", "source_id": "S1", "source_version_confirmed": "true",
        "source_confirmation_note": "Read Figure 1 p7 in the original 2025/26 report.",
    }, follow_redirects=False)
    assert response.status_code == 303
    facts = w["repos"].facts.list(); assert len(facts) == 1
    assert facts[0]["reviewer"] == "signed-in-analyst" and facts[0]["classification"] == "claim"
    assert set(facts[0]["entity_ids"]) == {"berry-strawberry", "variety-one"}
    assert "variety-two" not in facts[0]["entity_ids"]
    assert "reviewed" in w["client"].get(response.headers["location"]).text.lower()


def test_defer_saves_private_review_without_touching_canonical_facts(research_world):
    w = research_world
    response = w["client"].post("/variety-plantings/" + w["record"]["id"] + "/review", data={
        "action": "defer", "content_sha256": w["record"]["content_sha256"], "reviewer": "analyst",
        "confirm_individual_review": "true", "notes": "Need the exact survey population.",
    }, follow_redirects=False)
    assert response.status_code == 303 and w["repos"].facts.list() == []
    assert "Deferred" in w["client"].get(response.headers["location"]).text


def test_readonly_does_not_expose_private_research_or_accept_reviews(research_world, monkeypatch):
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    w = research_world
    assert w["client"].get("/variety-plantings").status_code == 404
    assert w["client"].get("/variety-plantings/" + w["record"]["id"]).status_code == 404
    assert w["client"].post("/variety-plantings/" + w["record"]["id"] + "/review", data={
        "action": "approve", "content_sha256": w["record"]["content_sha256"]}).status_code == 403
    assert w["repos"].facts.list() == []


def _artifact(inbox: Path, content=b"<html><script>untrusted()</script></html>"):
    root = inbox / "cultivar_measurement_imports" / "fixture-import"
    (root / "artifacts").mkdir(parents=True, exist_ok=True)
    sha = hashlib.sha256(content).hexdigest(); path = root / "artifacts" / (sha + ".html")
    path.write_bytes(content)
    (root / "packet.json").write_text(json.dumps({"artifacts": [{"path": "artifacts/" + path.name,
        "sha256": sha, "bytes": len(content), "original_filename": "source.html", "source_ids": ["S1"]}]}), encoding="utf-8")
    return path, sha


def test_registered_html_capture_is_download_only_and_hash_checked(research_world):
    w = research_world; path, sha = _artifact(w["inbox"])
    response = w["client"].get(f"/variety-plantings/imports/fixture-import/artifacts/{sha}")
    assert response.status_code == 200
    assert response.headers["content-disposition"].startswith("attachment")
    assert response.headers["content-type"] == "application/octet-stream"
    assert response.headers["content-security-policy"] == "sandbox"
    path.write_bytes(b"changed")
    assert w["client"].get(f"/variety-plantings/imports/fixture-import/artifacts/{sha}").status_code == 404


def test_capture_path_cannot_escape_into_sibling_private_data(tmp_path):
    path, sha = _artifact(tmp_path)
    manifest = path.parents[1] / "packet.json"
    data = json.loads(manifest.read_text()); data["artifacts"][0]["path"] = "../auth/accounts.json"
    manifest.write_text(json.dumps(data))
    with pytest.raises(CultivarMeasurementError):
        source_artifact(tmp_path, "fixture-import", sha)
    with pytest.raises(CultivarMeasurementError):
        source_artifact(tmp_path, "..", sha)


def test_list_metadata_does_not_open_packet_article_bodies(tmp_path):
    root = tmp_path / "cultivar_measurement_imports" / "fixture-import"
    root.mkdir(parents=True)
    (root / "packet.json").write_text("Full article packet must not be opened on this path.")
    (root / "import-index.json").write_text(json.dumps({"batch_id": "fixture-import", "berry_id": "berry-strawberry",
                                                       "artifacts": [], "counts": {"observations": 613}}))
    result = import_packets(tmp_path)
    assert len(result) == 1 and result[0]["counts"]["observations"] == 613
    assert "documents" not in result[0]


def test_identity_decision_creates_revised_proposal_and_preserves_catalog(research_world):
    w = research_world; row = dict(w["native"]); row["id"] = "AMBIGUOUS-1"
    row["platform_candidate_ids"] = ["variety-one", "variety-two"]
    record = normalize_measurement(row, source_bindings=[w["binding"]], berry_id="berry-strawberry",
                                   captured_at="2026-11-14T00:00:00Z", import_batch_id="fixture-import")
    stage_measurement(w["inbox"], record)
    before = {r["id"]: r for r in w["repos"].entities.list()}
    response = w["client"].post("/variety-plantings/" + record["id"] + "/identity", data={
        "selected_entity_id": "variety-one", "content_sha256": record["content_sha256"],
        "reviewer": "analyst", "notes": "Original source pairs this name with the existing selection code.",
        "confirm_individual_review": "true"}, follow_redirects=False)
    assert response.status_code == 303
    assert record["id"] not in response.headers["location"]
    assert {r["id"]: r for r in w["repos"].entities.list()} == before
    assert w["repos"].facts.list() == []


def test_remote_anonymous_users_cannot_read_captures_or_submit_decisions(research_world, monkeypatch):
    w = research_world
    monkeypatch.setenv("BIOS_REMOTE_INTERACTIVE", "true")
    monkeypatch.setenv("BIOS_REVIEW_USERNAME", "fixture-operator")
    monkeypatch.setenv("BIOS_REVIEW_PASSWORD", "isolated-test-password")
    monkeypatch.setenv("BIOS_SESSION_SECRET", "isolated-session-signing-secret-12345")
    monkeypatch.delenv("BIOS_BASIC_AUTH", raising=False)
    path, sha = _artifact(w["inbox"])
    client = TestClient(main.app, base_url="https://testserver", follow_redirects=False)
    for url in ("/variety-plantings", "/variety-plantings/" + w["record"]["id"],
                f"/variety-plantings/imports/fixture-import/artifacts/{sha}"):
        response = client.get(url)
        assert response.status_code == 302 and response.headers["location"].startswith("/login?next=")
    response = client.post("/variety-plantings/" + w["record"]["id"] + "/review", data={
        "action": "approve", "content_sha256": w["record"]["content_sha256"], "reviewer": "spoofed",
        "confirm_individual_review": "true"})
    assert response.status_code == 302 and w["repos"].facts.list() == []
