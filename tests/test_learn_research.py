"""Meaningful research privacy, duplicate charging, persistence and edit gates."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import re

from fastapi.testclient import TestClient
import httpx
import pytest

from app import main, learn_routes
from app.services import learn_research as service, learner
from app.services.ai_gateway.perplexity_deep_research import DeepResearchClient, ResearchError, normalize


def request(topic="Primocane biology"):
    return service.clean_request({"topic": topic, "excerpt": "First-year canes", "berry": "berry-raspberry",
        "concept_id": "concept-primocane-floricane", "return_to": "/today?story=source-1"},
        berries={"berry-raspberry": "Raspberry"}, entities={}, concepts=learner.all_concepts())


def result(status="completed", text="# The idea\n\nA sourced explanation.\n\n## How it works\n\n- First year\n- Second year"):
    return {"provider_id": "resp_1", "provider_status": status, "text": text,
            "citations": [{"url": "https://extension.example/guide", "title": "Extension guide"}],
            "model": "returned-model", "usage": {"input_tokens": 100, "output_tokens": 200, "total_tokens": 300}}


def create(tmp_path):
    job, _ = service.reserve(tmp_path, request(), "token00000000001")
    return job


def test_repeated_and_concurrent_submissions_reserve_once(tmp_path):
    approved = request()
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(lambda n: service.reserve(tmp_path, approved, "token000000000" + str(n)), range(4)))
    assert sum(created for _, created in rows) == 1
    assert len({row["id"] for row, _ in rows}) == 1
    job = rows[0][0]
    count = []
    class Client:
        def start(self, prompt):
            count.append(prompt)
            return result("queued", "")
    service.submit(tmp_path, job["id"], Client)
    service.submit(tmp_path, job["id"], Client)
    assert len(count) == 1
    assert service.load(tmp_path)["jobs"][job["id"]]["status"] == "running"


def test_form_token_cannot_be_reused_for_different_input(tmp_path):
    create(tmp_path)
    with pytest.raises(ValueError, match="already been used"):
        service.reserve(tmp_path, request("Different subject"), "token00000000001")


def test_case_change_and_return_page_do_not_resubmit(tmp_path):
    first = create(tmp_path)
    edited = request("PRIMOCANE BIOLOGY")
    edited["return_to"] = "/digest"
    second, created = service.reserve(tmp_path, edited, "token00000000002")
    assert not created and second["id"] == first["id"]


def test_provider_result_creates_one_lesson_and_preserves_analyst_edit(tmp_path):
    job = create(tmp_path)
    service.apply_result(tmp_path, job["id"], result())
    stored = service.load(tmp_path)
    key = stored["jobs"][job["id"]]["lesson_id"]
    source = stored["lessons"][key]
    service.edit_lesson(tmp_path, key, revision=1, title="My corrected lesson", text="", review_by="2027-01-01")
    service.apply_result(tmp_path, job["id"], result(text="Regenerated text"))
    final = service.load(tmp_path)["lessons"]
    assert len(final) == 1 and final[key]["text"] == ""
    assert final[key]["original_text"] == source["text"]
    assert final[key]["citations"] == source["citations"]
    assert final[key]["history"][0]["text"] == source["text"]
    assert final[key]["education_status"] == "analyst_edited"
    with pytest.raises(ValueError, match="another window"):
        service.edit_lesson(tmp_path, key, revision=1, title="Stale", text="Lost correction", review_by="")


def test_timeout_does_not_resubmit_unknown_paid_request(tmp_path):
    job = create(tmp_path)
    def timeout(*args, **kwargs):
        raise httpx.ReadTimeout("secret-key and private provider detail")
    service.submit(tmp_path, job["id"], lambda: DeepResearchClient("secret-key", post=timeout))
    stored = service.load(tmp_path)
    assert stored["jobs"][job["id"]]["status"] == "submission_uncertain"
    assert "secret-key" not in json.dumps(stored)
    same, created = service.reserve(tmp_path, request(), "token00000000002")
    assert same["id"] == job["id"] and not created


@pytest.mark.parametrize("status,expected,has_lesson", [
    ("incomplete", "partial", True), ("failed", "failed", False), ("cancelled", "cancelled", False),
    ("completed", "failed", False),
])
def test_partial_failed_cancelled_and_empty(tmp_path, status, expected, has_lesson):
    job = create(tmp_path)
    service.apply_result(tmp_path, job["id"], result(status, "Partial content" if has_lesson else ""))
    stored = service.load(tmp_path)
    assert stored["jobs"][job["id"]]["status"] == expected
    assert bool(stored["lessons"]) == has_lesson


def test_cancel_is_pending_until_provider_confirms(tmp_path):
    job = create(tmp_path)
    service.apply_result(tmp_path, job["id"], result("cancelling", ""))
    assert service.load(tmp_path)["jobs"][job["id"]]["status"] == "cancelling"
    service.apply_result(tmp_path, job["id"], result("cancelled", ""))
    assert service.load(tmp_path)["jobs"][job["id"]]["status"] == "cancelled"


def test_prompt_contains_only_selected_approved_data(tmp_path):
    approved = request()
    approved["private_notes"] = "secret unrelated notes"
    rendered = service.prompt(approved)
    assert "First-year canes" in rendered and "Raspberry" in rendered
    assert "secret unrelated notes" not in rendered and "/today" not in rendered


@pytest.mark.parametrize("target", ["https://evil.example", "//evil.example", "/\\evil.example", "/learn\nbad", "/admin"])
def test_return_destination_cannot_be_external_or_unrelated(target):
    assert service.return_path(target) == "/learn"


def test_corrupt_private_store_is_not_overwritten(tmp_path):
    file = service.path(tmp_path)
    original = '{"version":1,"jobs":{},"lessons":{"wrong":{"id":"wrong","revision":1}}}'
    file.write_text(original)
    with pytest.raises(ValueError, match="left unchanged"):
        service.reserve(tmp_path, request(), "token00000000001")
    assert file.read_text() == original


def test_normalizer_accepts_native_citations_not_generated_urls():
    body = {"id": "resp_1", "status": "completed", "output": [
        {"type": "web_search", "results": [{"url": "https://extension.example/guide", "title": "Guide"}]},
        {"type": "message", "content": [{"type": "output_text", "text": "Made-up URL https://invented.example",
            "annotations": [{"type": "url_citation", "url": "https://university.example/paper", "title": "Paper"},
                            {"type": "url_citation", "url": "javascript:alert(1)"}]}]}]}
    row = normalize(body)
    assert [r["url"] for r in row["citations"]] == ["https://extension.example/guide", "https://university.example/paper"]


def test_exact_background_provider_contract():
    calls = []
    def post(url, **kwargs):
        calls.append((url, kwargs))
        return httpx.Response(200, json={"id": "resp_1", "status": "queued"})
    client = DeepResearchClient("key-value", post=post)
    client.start("Only the approved public topic")
    url, params = calls[0]
    assert url == "https://api.perplexity.ai/v1/agent"
    assert params["json"] == {"preset": "medium", "background": True, "max_steps": 15, "max_output_tokens": 6000,
                             "input": "Only the approved public topic"}
    assert params["headers"]["Authorization"] == "Bearer key-value"


def test_reading_view_replaces_native_provider_tags_and_preserves_source_aliases():
    output = {"id": "resp_1", "status": "completed", "output": [{"type": "search_results", "results": [
        {"id": 8, "url": "https://university.example/guide", "title": "Guide"},
        {"id": 12, "url": "https://university.example/guide", "title": "Same guide"},
    ]}]}
    citations = normalize(output)["citations"]
    assert len(citations) == 1 and citations[0]["reference_ids"] == ["web:8", "web:12"]
    rendered = service.reading_inline("**The answer** [web:12] [web:999] <script>bad</script>", citations)
    assert "<strong>The answer</strong>" in rendered
    assert 'href="https://university.example/guide"' in rendered
    assert "[web:" not in rendered and "Source link unavailable" in rendered
    assert "<script>" not in rendered and "&lt;script&gt;" in rendered


def test_markdown_table_has_real_headers_and_rows():
    blocks = service.reading_blocks("# Explanation\n\n| Cane | Year |\n|---|---|\n| Primocane | 1 |\n| Floricane | 2 |\n\nMore explanation.")
    table = next(row for row in blocks if row["kind"] == "table")
    assert table["headers"] == ["Cane", "Year"]
    assert table["rows"] == [["Primocane", "1"], ["Floricane", "2"]]
    assert blocks[-1]["kind"] == "paragraph"


def test_late_status_check_does_not_undo_cancellation_request(tmp_path):
    job = create(tmp_path)
    service.apply_result(tmp_path, job["id"], result("queued", ""))
    previous = service.load(tmp_path)["jobs"][job["id"]]["revision"]
    service.apply_result(tmp_path, job["id"], result("cancelling", ""), expected_revision=previous)
    service.apply_result(tmp_path, job["id"], result("in_progress", ""), expected_revision=previous)
    assert service.load(tmp_path)["jobs"][job["id"]]["status"] == "cancelling"


def test_citation_alias_recovery_does_not_change_analyst_content(tmp_path):
    job = create(tmp_path)
    completed = result()
    service.apply_result(tmp_path, job["id"], completed)
    key = service.load(tmp_path)["jobs"][job["id"]]["lesson_id"]
    service.edit_lesson(tmp_path, key, revision=1, title="My title", text="My corrected text", review_by="")
    improved = deepcopy(completed)
    improved["citations"][0]["reference_ids"] = ["web:8"]
    service.refresh_provenance(tmp_path, job["id"], improved)
    final = service.load(tmp_path)["lessons"][key]
    assert final["text"] == "My corrected text" and final["revision"] == 2
    assert final["citations"][0]["reference_ids"] == ["web:8"]
    improved["text"] = "Different provider response"
    with pytest.raises(ValueError, match="left unchanged"):
        service.refresh_provenance(tmp_path, job["id"], improved)


def test_updated_research_creates_a_separate_draft_and_deduplicates_active_run(tmp_path):
    first = create(tmp_path)
    service.apply_result(tmp_path, first["id"], result())
    store = service.load(tmp_path)
    key = store["jobs"][first["id"]]["lesson_id"]
    service.edit_lesson(tmp_path, key, revision=1, title="Corrected", text="My correction", review_by="")
    updated = service.clean_request({"topic": "Primocane biology", "excerpt": "First-year canes", "berry": "berry-raspberry",
        "concept_id": "concept-primocane-floricane", "update_from": key, "generation": "generation0000001"},
        berries={"berry-raspberry": "Raspberry"}, entities={}, concepts=learner.all_concepts(), lessons=store["lessons"])
    newer, created = service.reserve(tmp_path, updated, "token00000000002")
    assert created and newer["id"] != first["id"]
    repeated = {**updated, "generation": "generation0000002"}
    duplicate, created = service.reserve(tmp_path, repeated, "token00000000003")
    assert not created and duplicate["id"] == newer["id"]
    service.apply_result(tmp_path, newer["id"], {**result(), "provider_id": "resp_2", "text": "Updated research"})
    lessons = service.load(tmp_path)["lessons"]
    assert len(lessons) == 2 and lessons[key]["text"] == "My correction"


def test_missing_credential_failure_can_be_retried_but_never_sends_a_request(tmp_path):
    job = create(tmp_path)
    def missing():
        raise ResearchError("Research is not connected; no provider request was sent.")
    service.submit(tmp_path, job["id"], missing)
    assert service.load(tmp_path)["jobs"][job["id"]]["status"] == "failed"
    retry, created = service.reserve(tmp_path, request(), "token00000000002")
    assert created and retry["id"] != job["id"]


def test_browser_forms_keep_origin_and_update_fields_without_javascript(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    first = create(tmp_path)
    service.apply_result(tmp_path, first["id"], result())
    lesson_id = service.load(tmp_path)["jobs"][first["id"]]["lesson_id"]
    client = TestClient(main.app)
    page = client.get("/learn/research/new", params={"update_from": lesson_id, "return_to": "/today?story=source-1"})
    assert page.status_code == 200
    assert 'id="learn-research"' in page.text and 'form="learn-research"' in page.text
    assert 'name="update_from" value="' + lesson_id + '"' in page.text
    origin = client.get("/learn/shelf-life", params={"return_to": "/today?story=source-1"})
    assert 'href="/today?story=source-1"' in origin.text


def test_route_flow_no_provider_on_get_then_edit_and_reload(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    calls = []
    class Client:
        def start(self, prompt):
            calls.append("start")
            return result("queued", "")
        def check(self, key):
            calls.append("check")
            return result(text="# The idea\n\n<script>alert('bad')</script>\n\n## Deeper explanation\n\nA detailed lesson.")
    monkeypatch.setattr(learn_routes, "client_factory", Client)
    client = TestClient(main.app)
    form = client.get("/learn/research/new?topic=primocane&return_to=%2Ftoday%3Fstory%3Dsource-1")
    assert form.status_code == 200 and not calls and "You may already have a lesson" in form.text
    token = re.search(r'name="token" value="([^"]+)"', form.text)[1]
    payload = {"token": token, "topic": "Primocane biology", "excerpt": "First-year canes", "berry": "berry-raspberry"}
    created = client.post("/learn/research/start", data=payload)
    assert created.status_code == 200 and calls == ["start"]
    key = str(created.url).rsplit("/", 1)[-1]
    client.get("/learn"); client.get("/learn/research/jobs/" + key)
    assert calls == ["start"]
    client.post("/learn/research/start", data=payload)
    assert calls == ["start"]
    completed = client.post("/learn/research/jobs/" + key + "/check")
    assert completed.status_code == 200 and calls == ["start", "check"]
    stored = service.load(tmp_path)
    lesson = next(iter(stored["lessons"].values()))
    page = client.get("/learn/lessons/" + lesson["id"])
    assert "<script>alert('bad')</script>" not in page.text and "&lt;script&gt;" in page.text
    saved = client.post("/learn/lessons/" + lesson["id"] + "/save", data={"revision": 1, "title": "Corrected", "text": "My private edits", "review_by": ""})
    assert saved.status_code == 200 and "Your lesson changes are saved" in saved.text
    assert "My private edits" in client.get("/learn/lessons/" + lesson["id"]).text
    assert service.load(tmp_path)["lessons"][lesson["id"]]["original_text"] != "My private edits"
    assert calls == ["start", "check"]
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    assert client.get("/learn/lessons/" + lesson["id"]).status_code == 403
    assert "Corrected" not in client.get("/learn").text


def test_cross_origin_cannot_start_research(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    page = TestClient(main.app).post("/learn/research/start", headers={"origin": "https://other.example"}, data={"topic": "test"})
    assert page.status_code == 403 and not service.path(tmp_path).exists()


def test_catalog_remains_available_when_private_research_is_damaged(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    service.path(tmp_path).write_text("{ damaged", encoding="utf-8")
    response = TestClient(main.app).get("/learn")
    assert response.status_code == 200 and "left unchanged" in response.text
    assert "Primocane" in response.text and service.path(tmp_path).read_text() == "{ damaged"


def test_recover_retrieves_existing_provider_run_without_resubmitting(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    job = create(tmp_path)
    service.failure(tmp_path, job["id"], ResearchError("Check the existing run", uncertain=True))
    calls = []
    class Client:
        def check(self, key):
            calls.append(key)
            return result()
    monkeypatch.setattr(learn_routes, "client_factory", Client)
    client = TestClient(main.app)
    route = "/learn/research/jobs/" + job["id"] + "/recover"
    assert client.post(route, data={"provider_id": "resp_1"}).status_code == 422
    assert not calls
    assert client.post(route, data={"provider_id": "resp_1", "confirm_run": "yes"}).status_code == 200
    assert calls == ["resp_1"]
    assert service.load(tmp_path)["jobs"][job["id"]]["lesson_id"]


def test_private_lesson_search_and_origin_do_not_trigger_research(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    job = create(tmp_path)
    service.apply_result(tmp_path, job["id"], result())
    lesson = next(iter(service.load(tmp_path)["lessons"].values()))
    client = TestClient(main.app)
    assert lesson["id"] in client.get("/learn?q=Primocane").text
    assert lesson["id"] not in client.get("/learn?q=Not-a-matching-question").text
    response = client.get("/learn/lessons/" + lesson["id"], params={"return_to": "/today?story=source-1"})
    assert 'href="/today?story=source-1"' in response.text


def test_malformed_optional_provider_content_cannot_crash_citation_parser():
    envelope = {"id": "resp_1", "status": "queued", "output": [{"content": 1}, {"content": [{"annotations": 4}]}]}
    assert normalize(envelope)["citations"] == []
