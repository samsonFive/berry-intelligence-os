"""Exercise private capability input decisions through the analyst's normal forms."""

import pytest
from fastapi.testclient import TestClient

from app import main
from app.services import berry_strategy_inputs as inputs, living_workspaces as living


ENTITY = "company-fixture-capabilities"


@pytest.fixture
def workspace(monkeypatch, tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    monkeypatch.setattr(main, "INBOX_DIR", inbox)
    monkeypatch.setattr(main, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    monkeypatch.setattr(main, "entity_index", lambda: {
        ENTITY: {"id": ENTITY, "name": "Synthetic Nursery", "entity_type": "company"},
    })
    monkeypatch.setattr(main, "all_relationships", list)
    monkeypatch.setattr(main, "published_evidence", list)
    return TestClient(main.app), inbox


def form(token="fixture-create-input"):
    return {"version": "0", "token": token, "entity_id": ENTITY, "crop": "raspberry", "region": "europe",
            "title": "Private capability sentinel", "statement": "An analyst recorded a synthetic cold-chain capability.",
            "category": "capability", "reference": "Synthetic internal report, section 2", "observed_date": "2026-11-01",
            "vrio_valuable": "yes", "vrio_valuable_rationale": "The synthetic trial measured lower losses."}


def create(client, payload=None):
    response = client.post("/strategy-inputs", data=payload or form(), follow_redirects=False)
    assert response.status_code == 303
    return response.headers["location"]


def test_empty_get_creates_no_store_and_reuses_compact_sheet(workspace):
    client, inbox = workspace
    page = client.get("/strategy-inputs?crop=raspberry&region=europe")
    assert page.status_code == 200 and page.headers["cache-control"] == "private, no-store"
    assert "strategy-inputs-layout" in page.text and 'id="strategy-input-library"' in page.text
    assert "Save draft revision" in page.text and "Approve for Strategy Review" not in page.text
    assert not (inbox / "living_workspaces").exists()


def test_form_approval_scoped_review_and_frozen_input_history(workspace):
    client, inbox = workspace
    path = create(client)
    draft = client.get(path)
    assert "Approve for Strategy Review" in draft.text
    assert client.post(path + "/decision", data={"version": "1", "action": "approve", "token": "fixture-approve-input"},
                       follow_redirects=False).status_code == 303
    page = client.get("/landscapes/global/raspberry?region=europe")
    assert ENTITY in page.text and "Manage private strategy inputs" in page.text
    response = client.post("/strategy-reviews/berries/raspberry/refresh?region=europe",
                           data={"version": "0", "method": "local", "focal": ENTITY}, follow_redirects=False)
    assert response.status_code == 303
    review = client.get(response.headers["location"])
    assert "Private capability sentinel" in review.text and "Approved analyst VRIO judgments" in review.text
    assert path + "?version=2" in review.text and 'name="focal" value="' + ENTITY + '"' in review.text
    assert '<option value="vrio">' in review.text
    history = client.get(path + "?version=1")
    assert history.status_code == 200 and "Input revision 1" in history.text
    assert "Save draft revision" not in history.text and "Approve for Strategy Review" not in history.text
    assert "Private capability sentinel" not in client.get("/landscapes/global/blueberry?region=europe").text
    assert "Private capability sentinel" not in client.get("/landscapes/global/raspberry?region=mea").text
    rows = living.Store(inbox).rows(inputs.KIND)
    assert len(rows) == 1 and rows[0]["state"] == "approved"


def test_input_edit_invalidates_review_and_stale_forms_preserve_text(workspace):
    client, inbox = workspace
    path = create(client)
    client.post(path + "/decision", data={"version": "1", "action": "approve", "token": "fixture-approve-input"})
    base = "/strategy-reviews/berries/raspberry"
    client.post(base + "/refresh?region=europe", data={"version": "0", "method": "local", "focal": ENTITY})
    changed = {**form("fixture-edit-input"), "input_id": path.rsplit("/", 1)[-1], "version": "2",
               "statement": "Changed private capability sentinel"}
    assert client.post("/strategy-inputs", data=changed, follow_redirects=False).status_code == 303
    current = client.get("/landscapes/global/raspberry?region=europe")
    assert "The evidence changed" in current.text and "Approved analyst VRIO judgments" not in current.text
    assert client.post(base + "/review?region=europe", data={"version": "1", "action": "approve", "focal": ENTITY}).status_code == 409
    stale = client.post("/strategy-inputs", data={**changed, "token": "fixture-stale-input", "statement": "Recovery text sentinel"})
    assert stale.status_code == 409 and "Recovery text sentinel" in stale.text
    assert "Open the current input to compare" in stale.text and "Save draft revision" not in stale.text
    row = living.Store(inbox).get(path.rsplit("/", 1)[-1])
    assert row["state"] == "draft" and row["statement"] == changed["statement"]


def test_retry_validation_and_private_access(workspace, monkeypatch):
    client, inbox = workspace
    payload = form()
    path = create(client, payload)
    assert create(client, payload) == path
    assert len(living.Store(inbox).rows(inputs.KIND)) == 1
    invalid = client.post("/strategy-inputs", data={**form("fixture-invalid-input"), "reference": ""})
    assert invalid.status_code == 422 and "Reference is required" in invalid.text
    assert "Private capability sentinel" in invalid.text
    cross_site = client.post("/strategy-inputs", data=form("fixture-cross-site"), headers={"origin": "https://example.org"})
    assert cross_site.status_code == 403
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    assert client.get("/strategy-inputs").status_code == 403
    assert client.get(path).status_code == 403
    assert client.post(path + "/decision", data={"version": "1", "action": "approve", "token": "fixture-public-attempt"}).status_code == 403
    public = client.get("/landscapes/global/raspberry")
    assert "Private capability sentinel" not in public.text and "Manage private strategy inputs" not in public.text


def test_invalid_edit_cannot_approve_hidden_saved_content_or_edit_other_objects(workspace):
    client, inbox = workspace
    path = create(client)
    bad_edit = {**form("fixture-invalid-edit"), "input_id": path.rsplit("/", 1)[-1], "version": "1",
                "reference": "", "statement": "Unsaved rejected text sentinel"}
    invalid = client.post("/strategy-inputs", data=bad_edit)
    assert invalid.status_code == 422 and "Unsaved rejected text sentinel" in invalid.text
    assert "Approve for Strategy Review" not in invalid.text
    update = {**form("fixture-newer-edit"), "input_id": path.rsplit("/", 1)[-1], "version": "1",
              "statement": "Newer saved text sentinel"}
    assert client.post("/strategy-inputs", data=update, follow_redirects=False).status_code == 303
    stale_invalid = client.post("/strategy-inputs", data={**bad_edit, "token": "fixture-invalid-stale-edit"})
    assert stale_invalid.status_code == 409 and "Unsaved rejected text sentinel" in stale_invalid.text
    assert 'name="version" value="1"' in stale_invalid.text and "Save draft revision" not in stale_invalid.text
    store = living.Store(inbox)
    page = store.create_page("Synthetic research page", None, "Analyst", "fixture-page-token")
    wrong_kind = client.post("/strategy-inputs", data={**form("fixture-wrong-kind"), "input_id": page["id"]})
    assert wrong_kind.status_code == 422
    assert store.get(page["id"])["title"] == "Synthetic research page"
