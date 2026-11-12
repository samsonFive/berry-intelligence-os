"""Workspace review links survive publication without creating another draft."""

import json
import pytest
from fastapi.testclient import TestClient

from app import main
from app.session_auth import reset_login_failures


IDENTITY = "ev-frontier-immaculate-uspp36781"


@pytest.fixture
def runtime(monkeypatch, tmp_path):
    data, inbox = tmp_path / "data", tmp_path / "inbox"
    monkeypatch.setattr(main, "DATA_DIR", data)
    monkeypatch.setattr(main, "INBOX_DIR", inbox)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    monkeypatch.setenv("BIOS_REMOTE_INTERACTIVE", "false")
    monkeypatch.delenv("BIOS_BASIC_AUTH", raising=False)
    main._JSON_FOLDER_CACHE.clear()
    yield data, inbox
    main._JSON_FOLDER_CACHE.clear()
    reset_login_failures()


def record(**changes):
    value = {
        "id": IDENTITY, "record_type": "evidence", "status": "published",
        "review_state": "published", "source_type": "web_article",
        "evidence_role": "publication_artifact", "title": "Previously reviewed source",
        "source_name": "Fixture publisher", "source_url": "https://example.test/source",
        "summary": "Existing source approval retains its separate claim decision.",
        "published_date": "2026-11-01", "captured_date": "2026-11-11",
        "entity_ids": [], "fact_ids": [], "relationship_ids": [],
        "priority": {key: {"level": "none", "rationale": ""} for key in
                     ("reading", "testing", "monitoring", "commercial_position")},
    }
    value.update(changes)
    return value


def write(folder, value):
    path = folder / "evidence" / (value["id"] + ".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def files(folder):
    return {str(path.relative_to(folder)): path.read_bytes()
            for path in folder.rglob("*") if path.is_file()}


def test_canonical_only_review_link_redirects_to_same_evidence_without_mutation(runtime):
    data, inbox = runtime
    write(data, record(pending_claim={"statement": "Still awaiting a claim decision."}))
    before = files(data), files(inbox)
    client = TestClient(main.app, follow_redirects=False)

    response = client.get("/review/" + IDENTITY)

    assert response.status_code == 302
    assert response.headers["location"] == "/evidence/" + IDENTITY
    assert client.get(response.headers["location"]).status_code == 200
    assert (files(data), files(inbox)) == before


@pytest.mark.parametrize("state", ["in_review", "saved", "rejected"])
def test_existing_draft_has_precedence_over_same_id_canonical_record(runtime, state):
    data, inbox = runtime
    write(data, record())
    write(inbox, record(title="Existing draft retains precedence", status=state, review_state=state))
    before = files(data), files(inbox)

    response = TestClient(main.app, follow_redirects=False).get("/review/" + IDENTITY)

    assert response.status_code == 200
    assert "Existing draft retains precedence" in response.text
    assert "location" not in response.headers
    assert (files(data), files(inbox)) == before


def test_unknown_review_identity_still_returns_404(runtime):
    data, inbox = runtime
    # A nearby record cannot satisfy an exact identity lookup.
    write(data, record(id=IDENTITY + "-other"))
    before = files(data), files(inbox)

    response = TestClient(main.app, follow_redirects=False).get("/review/" + IDENTITY)

    assert response.status_code == 404
    assert response.json()["detail"] == "Draft not found"
    assert (files(data), files(inbox)) == before


def test_canonical_review_fallback_remains_behind_session_login(runtime, monkeypatch):
    data, inbox = runtime
    write(data, record())
    monkeypatch.setenv("BIOS_REMOTE_INTERACTIVE", "true")
    monkeypatch.setenv("BIOS_REVIEW_USERNAME", "fixture-operator")
    monkeypatch.setenv("BIOS_REVIEW_PASSWORD", "fixture-review-password")
    monkeypatch.setenv("BIOS_SESSION_SECRET", "fixture-session-secret-is-distinct")
    reset_login_failures()
    client = TestClient(main.app, follow_redirects=False)

    for identity in (IDENTITY, "ev-unknown"):
        response = client.get("/review/" + identity)
        assert response.status_code == 302
        assert response.headers["location"].startswith("/login?next=")

    login = client.post("/login", data={"username": "fixture-operator", "password": "fixture-review-password"})
    assert login.status_code == 303
    authenticated = client.get("/review/" + IDENTITY)
    assert authenticated.status_code == 302
    assert authenticated.headers["location"] == "/evidence/" + IDENTITY
