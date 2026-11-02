"""Current provider contract, real route submission and legacy-run preservation."""
from copy import deepcopy
import json
import re

from fastapi.testclient import TestClient
import httpx
import pytest

from app import main, learn_routes
from app.services import learn_research as service, learner
from app.services.ai_gateway import perplexity_deep_research as provider


def approved():
    return service.clean_request({"topic": "Primocane biology", "excerpt": "First-year canes",
        "return_to": "/today?story=source-1#reader", "berry": "berry-raspberry"},
        berries={"berry-raspberry": "Raspberry"}, entities={}, concepts=learner.all_concepts())


def test_learn_reservation_selects_deep_research_without_changing_prompt_identity(tmp_path):
    job, _ = service.reserve(tmp_path, approved(), "token00000000001")
    assert job["configuration"]["effort"] == "high"
    assert "preset" not in job["configuration"]
    # Prompt content is unchanged; a provider-contract repair must not cause
    # old form tokens / active jobs to be billed again under a new identity.
    assert job["request"]["prompt_version"] == "learn-deep-v1"
    assert provider.CONFIG.get("effort") == "medium"


def test_actual_learn_route_sends_high_once_and_preserves_edits(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    monkeypatch.setattr(learn_routes, "resolve_perplexity_api_key", lambda: "fixture-key")
    calls = []
    def transport(url, **kwargs):
        calls.append((url, deepcopy(kwargs.get("json"))))
        if url.endswith("/resp_fixture"):
            return httpx.Response(200, json={"id": "resp_fixture", "status": "completed", "model": "fixture-model",
                "effort": "high@fixture-version", "output": [{"type": "message", "content": [{
                    "type": "output_text", "text": "# The idea\n\nA sourced explanation.", "annotations": [{
                        "type": "url_citation", "url": "https://extension.example/lesson", "title": "Fixture source"}]}]}]})
        return httpx.Response(200, json={"id": "resp_fixture", "status": "queued", "effort": "high@fixture-version"})
    # Use the production factory and adapter; substitute only HTTP transport.
    real_client = provider.DeepResearchClient
    monkeypatch.setattr(learn_routes, "DeepResearchClient", lambda key, **kw: real_client(key, post=transport, get=transport, **kw))
    client = TestClient(main.app)
    form = client.get("/learn/research/new?topic=Primocane")
    assert form.status_code == 200 and not calls
    token = re.search(r'name="token" value="([^"]+)"', form.text)[1]
    data = {"topic": "Primocane biology", "excerpt": "First-year canes", "token": token}
    response = client.post("/learn/research/start", data=data)
    assert response.status_code == 200
    key = str(response.url).rsplit("/", 1)[-1]
    assert len(calls) == 1
    wire = calls[0][1]
    assert wire["effort"] == "high" and "preset" not in wire
    assert wire["background"] is True and wire["max_steps"] == 15 and wire["max_output_tokens"] == 6000
    row = service.load(tmp_path)["jobs"][key]
    assert row["configuration"] == row["submission_configuration"]
    assert row["reported_effort"] == "high@fixture-version"
    client.post("/learn/research/start", data=data)
    client.get("/learn"); client.get("/learn/research/jobs/" + key)
    assert len(calls) == 1
    client.post("/learn/research/jobs/" + key + "/check")
    assert len(calls) == 2 and calls[1] == (provider.CONFIG["endpoint"] + "/resp_fixture", None)
    store = service.load(tmp_path)
    lesson = store["lessons"][store["jobs"][key]["lesson_id"]]
    client.post("/learn/lessons/" + lesson["id"] + "/save", data={"revision": 1, "title": "My corrected lesson", "text": "My own explanation", "review_by": ""})
    before = service.path(tmp_path).read_bytes()
    client.post("/learn/research/jobs/" + key + "/check")
    client.get("/learn/lessons/" + lesson["id"])
    assert len(calls) == 2 and service.path(tmp_path).read_bytes() == before
    saved = service.load(tmp_path)["lessons"][lesson["id"]]
    assert saved["text"] == "My own explanation" and saved["original_text"] != saved["text"]


def test_legacy_unsubmitted_run_keeps_original_config_and_medium_level(tmp_path):
    job, _ = service.reserve(tmp_path, approved(), "token00000000001")
    legacy = deepcopy(job["configuration"])
    legacy.pop("effort", None)
    legacy["preset"] = "medium"
    store = service.load(tmp_path)
    store["jobs"][job["id"]]["configuration"] = legacy
    service.path(tmp_path).write_text(json.dumps(store), encoding="utf-8")
    submitted = []
    def factory(config):
        def post(url, **kwargs):
            submitted.append(kwargs["json"])
            return httpx.Response(200, json={"id": "resp_old", "status": "queued"})
        return provider.DeepResearchClient("fixture-key", configuration=config, post=post)
    service.submit(tmp_path, job["id"], factory)
    service.submit(tmp_path, job["id"], factory)
    row = service.load(tmp_path)["jobs"][job["id"]]
    assert row["configuration"] == legacy
    assert row["submission_configuration"]["effort"] == "medium"
    assert len(submitted) == 1 and submitted[0]["effort"] == "medium" and "preset" not in submitted[0]
    same, created = service.reserve(tmp_path, approved(), "token00000000002")
    assert not created and same["id"] == job["id"]


def test_legacy_recovery_and_cancellation_use_existing_run_only(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    monkeypatch.setattr(learn_routes, "resolve_perplexity_api_key", lambda: "fixture-key")
    job, _ = service.reserve(tmp_path, approved(), "token00000000001")
    store = service.load(tmp_path)
    row = store["jobs"][job["id"]]
    legacy = {**provider.CONFIG, "preset": "medium"}
    legacy.pop("effort", None)
    row.update(status="submission_uncertain", configuration=legacy)
    service.path(tmp_path).write_text(json.dumps(store), encoding="utf-8")
    calls = []
    def transport(url, **kwargs):
        calls.append((url, kwargs.get("json")))
        status = "cancelled" if url.endswith("/cancel") else "in_progress"
        return httpx.Response(200, json={"id": "resp_old", "status": status, "effort": "medium@legacy"})
    real_client = provider.DeepResearchClient
    monkeypatch.setattr(learn_routes, "DeepResearchClient", lambda key, **kw: real_client(key, post=transport, get=transport, **kw))
    client = TestClient(main.app)
    route = "/learn/research/jobs/" + job["id"]
    assert client.get(route).status_code == 200 and not calls
    client.post(route + "/recover", data={"confirm_run": "yes", "provider_id": "resp_old"})
    client.post(route + "/cancel")
    client.post(route + "/check")
    assert calls == [(provider.CONFIG["endpoint"] + "/resp_old", None), (provider.CONFIG["endpoint"] + "/resp_old/cancel", None)]
    saved = service.load(tmp_path)["jobs"][job["id"]]
    assert saved["configuration"] == legacy and saved["status"] == "cancelled"
    page = client.get(route)
    assert "Earlier research level: medium" in page.text and "Deep-research preset: medium" not in page.text
    assert saved["reported_effort"] == "medium@legacy"


@pytest.mark.parametrize("field,value", [("effort", "ultra-preview"), ("effort", []),
    ("endpoint", "https://other.example/collect"), ("max_steps", 100),
    ("max_output_tokens", True), ("prompt_version", None)])
def test_invalid_saved_configuration_never_reaches_transport(tmp_path, field, value):
    job, _ = service.reserve(tmp_path, approved(), "token00000000001")
    store = service.load(tmp_path)
    store["jobs"][job["id"]]["configuration"][field] = value
    service.path(tmp_path).write_text(json.dumps(store), encoding="utf-8")
    calls = []
    def factory(configuration):
        calls.append(configuration)
        raise AssertionError("Unsupported settings must not leave this workspace")
    service.submit(tmp_path, job["id"], factory)
    row = service.load(tmp_path)["jobs"][job["id"]]
    assert row["status"] == "failed" and not calls
    assert row["configuration"][field] == value and not row["provider_id"]
