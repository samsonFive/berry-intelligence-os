"""Native Learn reads preserve education, provenance, privacy and boundedness."""
from copy import deepcopy
from base64 import b64encode
from datetime import date
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from fastapi import FastAPI
from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner
import pytest

from app import experience_learning_routes as routes, main
from app.services import experience_learning as api, learner, learn_research
from app.session_auth import EnvSessionMiddleware, remote_auth_middleware, SESSION_COOKIE_NAME


@pytest.fixture
def library(tmp_path, monkeypatch):
    concepts = tmp_path / "concepts"
    concepts.mkdir()
    original = Path(__file__).parents[1] / "data/learn/concepts"
    for slug in ("primocane-floricane", "firmness", "double-cropping"):
        (concepts / ("concept-" + slug + ".json")).write_bytes((original / ("concept-" + slug + ".json")).read_bytes())
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    monkeypatch.setattr(learner, "CONCEPTS_DIR", concepts)
    monkeypatch.setattr(main, "INBOX_DIR", inbox)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    monkeypatch.delenv("BIOS_REMOTE_INTERACTIVE", raising=False)
    api._cached_headers.cache_clear()
    app = FastAPI()
    routes.register(app)
    app.middleware("http")(remote_auth_middleware)
    app.add_middleware(EnvSessionMiddleware)
    yield concepts, inbox, TestClient(app, follow_redirects=False)
    api._cached_headers.cache_clear()


def write_store(inbox):
    request = {"topic": "Cane biology", "excerpt": "PRIVATE APPROVED RESEARCH EXCERPT",
               "berry": "berry-raspberry", "berry_label": "Raspberry", "geography": "geography-chile", "geography_label": "Chile",
               "concept_id": "concept-primocane-floricane", "pillar": "plant_biology_agronomy", "knowledge_class": "regional_production_practice"}
    job = {"id": "lr-one", "revision": 1, "request": request, "created_at": "2026-01-01T00:00:00Z", "status": "ready",
           "token": "PRIVATE JOB TOKEN", "fingerprint": "private-fingerprint", "configuration": {"api_key": "PRIVATE PROVIDER CONFIG"}}
    lesson = {"id": "lesson-one", "job_id": "lr-one", "revision": 2, "title": "My corrected cane lesson", "text": "# My corrected cane lesson\n\nSELECTED CURRENT TEXT [web:1]",
              "original_text": "PRIVATE ORIGINAL TEXT", "history": [{"text": "PRIVATE EARLIER EDIT", "revision": 1}],
              "request": request, "citations": [{"title": "Extension guide", "publisher": "University", "url": "https://extension.example/guide", "reference_ids": ["web:1"]}],
              "education_status": "analyst_edited", "partial": True, "reviewed_at": "2025-01-01", "review_by": "2026-01-01",
              "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-02T00:00:00Z"}
    other = deepcopy(lesson)
    other.update(id="lesson-other", title="Other learning topic", text="UNSELECTED OTHER LESSON BODY", education_status="ai_draft", partial=False, history=[])
    store = {"version": 1, "jobs": {job["id"]: job}, "lessons": {lesson["id"]: lesson, other["id"]: other}}
    path = inbox / "learn_research.json"
    path.write_text(json.dumps(store), encoding="utf-8")
    return path, store


def test_catalog_is_metadata_only_with_honest_empty_private_library(library, monkeypatch):
    _, _, client = library
    monkeypatch.setattr(learn_research, "load", lambda *a: pytest.fail("Full private store hydration is not a list read"))
    monkeypatch.setattr(learner, "all_concepts", lambda: pytest.fail("The catalog must not hydrate all concept bodies"))
    response = client.get("/api/investigations/v1/learning?revision=7&berry=berry-blueberry&countries=geography-peru")
    assert response.status_code == 200
    model = response.json()
    assert model["api_v"] == 1 and model["revision"] == 7 and model["request_id"] and model["scope_key"]
    assert model["data"]["counts"] == {"concepts": 3, "lessons": 0, "stale": 0, "partial": 0}
    assert model["data"]["collections"]["lessons"] == {"status": "empty", "total": 0, "matched_count": 0, "items": [], "has_more": False}
    assert model["data"]["education_boundary"]["competitive_evidence"] is False
    assert "navigation context" in model["applied_scope"]["applicability"]
    assert model["applied_scope"]["filters"]["q"] == ""
    assert "what_is_it" not in response.text and "text\"" not in response.text
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_saved_draft_list_retains_real_counts_class_scope_and_freshness_without_bodies(library):
    _, inbox, client = library
    path, _ = write_store(inbox)
    before = path.read_bytes()
    response = client.get("/api/investigations/v1/learning?kind=lesson&limit=1")
    data = response.json()["data"]
    assert response.status_code == 200 and data["counts"]["lessons"] == 2
    assert data["counts"]["partial"] == 1 and data["counts"]["stale"] == 2
    lessons = data["collections"]["lessons"]
    assert lessons["matched_count"] == 2 and lessons["has_more"] and len(lessons["items"]) == 1
    item = lessons["items"][0]
    assert item["education_status"] == "analyst_edited" and item["partial"] and item["is_stale"]
    assert item["knowledge_class"] == "regional_production_practice"
    assert item["scope"]["geography_label"] == "Chile" and item["scope"]["berry_id"] == "berry-raspberry"
    assert item["source_count"] == 1
    for secret in ("SELECTED CURRENT TEXT", "UNSELECTED OTHER LESSON BODY", "PRIVATE", "original_text", "history", "configuration", "fingerprint", "excerpt"):
        assert secret not in response.text
    assert path.read_bytes() == before


def test_catalog_filters_count_all_matches_before_paging_and_do_not_infer_global_scope(library):
    _, inbox, client = library
    write_store(inbox)
    first = client.get("/api/investigations/v1/learning?kind=lesson&q=corrected&knowledge_class=regional_production_practice&countries=geography-peru").json()
    assert first["data"]["collections"]["lessons"]["matched_count"] == 1
    assert first["data"]["collections"]["lessons"]["items"][0]["scope"]["geography_label"] == "Chile"
    second = client.get("/api/investigations/v1/learning?kind=lesson&q=corrected&knowledge_class=regional_production_practice&countries=geography-china&focus=company-other").json()
    assert first["scope_key"] == second["scope_key"]
    assert first["data"] == second["data"]
    assert sum(row["count"] for row in first["data"]["facets"]["pillars"]) == 5
    page = client.get("/api/investigations/v1/learning?kind=lesson&offset=1&limit=1").json()["data"]["collections"]["lessons"]
    assert page["items"][0]["id"] == "lesson-other" and page["has_more"] is False


def test_selected_concept_reuses_teaching_sources_license_and_real_related_records(library):
    _, _, client = library
    response = client.get("/api/investigations/v1/learning/concept/concept-primocane-floricane")
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data["sections"]) == 5 and "first-year" in data["sections"][0]["text"]
    assert data["teaching"]["figure"]["license"] == "CC BY 2.5"
    assert "Steffen Flor" in data["teaching"]["figure"]["attribution"]
    assert "does not establish cane age" in data["teaching"]["figure"]["caption"]
    assert data["teaching"]["cane_diagram"] is True
    assert data["citations"][0]["publisher"] == "Alabama Cooperative Extension System"
    assert all(row["display"] == "source_link" for row in data["media"])
    assert any(row["kind"] == "video" and "not copied" in row["reuse_basis"] for row in data["media"])
    assert data["related"] == [{"kind": "concept", "id": "concept-double-cropping", "title": "Double cropping", "href": "/app/learn/concept/concept-double-cropping"}]
    assert data["item"]["href"] == "/app/learn/concept/concept-primocane-floricane"
    assert urlsplit(data["expand_href"]).path == "/learn/primocane-floricane"


def test_selected_concept_preserves_original_when_existing_visual_overlay_clarifies(library):
    _, _, client = library
    data = client.get("/api/investigations/v1/learning/concept/concept-double-cropping").json()["data"]
    assert "reusing a strawberry bed" in data["item"]["summary"]
    assert data["clarification"]["retained_original"]["summary"] != data["item"]["summary"]
    diagram = data["teaching"]["diagram"]
    assert diagram["illustrative"] and diagram["mode"] == "comparison"
    assert diagram["sources"] and diagram["limit"] and diagram["steps"][0]["detail"]


def test_selected_lesson_retains_current_edits_inline_refs_and_explicit_companion_only(library, monkeypatch):
    _, inbox, client = library
    path, store = write_store(inbox)
    before = path.read_bytes()
    monkeypatch.setattr(learn_research, "load", lambda *a: pytest.fail("Do not hydrate original research/history"))
    monkeypatch.setattr(learn_research, "submit", lambda *a: pytest.fail("Navigation cannot research"))
    response = client.get("/api/investigations/v1/learning/lesson/lesson-one")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["content_markdown"] == store["lessons"]["lesson-one"]["text"]
    assert data["citations"][0]["reference_ids"] == ["web:1"]
    assert data["provenance"]["history_count"] == 1 and data["provenance"]["revision"] == 2
    assert data["teaching"]["companion"]["id"] == "concept-primocane-floricane"
    assert data["item"]["status_label"] == "Edited educational draft"
    for secret in ("PRIVATE", "UNSELECTED OTHER LESSON BODY", "original_text", "configuration", "excerpt", "fingerprint"):
        assert secret not in response.text
    assert path.read_bytes() == before
    store["lessons"]["lesson-one"]["request"]["concept_id"] = ""
    path.write_text(json.dumps(store), encoding="utf-8")
    assert client.get("/api/investigations/v1/learning/lesson/lesson-one").json()["data"]["teaching"] is None


def test_metadata_cache_invalidates_on_edit_and_never_crosses_runtime_stores(library, tmp_path):
    concepts, inbox, _ = library
    path, store = write_store(inbox)
    first = api.load_catalog(inbox)
    api.load_catalog(inbox)
    assert api._cached_headers.cache_info().hits >= 1
    store["lessons"]["lesson-one"]["title"] = "An updated title"
    store["lessons"]["lesson-one"]["revision"] = 3
    path.write_text(json.dumps(store), encoding="utf-8")
    second = api.load_catalog(inbox)
    assert first["lessons"][0]["title"] == "My corrected cane lesson"
    assert second["lessons"][0]["title"] == "An updated title"
    assert api.load_catalog(tmp_path / "other-runtime")["lessons"] == []
    assert "SELECTED CURRENT TEXT" not in repr(second)
    # Concept body edits invalidate their metadata even when a selected concept
    # was never opened, rather than retaining learner._load_all's lifetime cache.
    concept_path = concepts / "concept-firmness.json"
    record = json.loads(concept_path.read_text(encoding="utf-8"))
    record["name"] = "Firmness revised"
    concept_path.write_text(json.dumps(record), encoding="utf-8")
    assert any(row["name"] == "Firmness revised" for row in api.load_catalog(inbox)["concepts"])


@pytest.mark.parametrize("malformed", ["not json", '{"version":2,"jobs":{},"lessons":{}}', '{"version":1,"jobs":{},"lessons":{"bad":[]}}'])
def test_bad_private_store_is_explicitly_unavailable_without_hiding_concepts(library, malformed):
    _, inbox, client = library
    path = inbox / "learn_research.json"
    path.write_text(malformed, encoding="utf-8")
    response = client.get("/api/investigations/v1/learning")
    assert response.status_code == 200
    model = response.json()
    assert model["data"]["collections"]["lessons"]["status"] == "unavailable"
    assert model["data"]["counts"]["lessons"] is None
    assert model["data"]["counts"]["stale"] is None and model["data"]["counts"]["partial"] is None
    assert model["data"]["counts"]["concepts"] == 3 and model["issues"][0]["field"] == "lessons"
    assert path.read_text(encoding="utf-8") == malformed
    assert client.get("/api/investigations/v1/learning/lesson/lesson-one").status_code == 422


def test_oversized_store_does_not_claim_an_empty_library(library, monkeypatch):
    _, inbox, client = library
    write_store(inbox)
    monkeypatch.setattr(api, "MAX_STORE_BYTES", 20)
    model = client.get("/api/investigations/v1/learning").json()
    assert model["data"]["collections"]["lessons"]["status"] == "unavailable"
    assert model["data"]["counts"]["lessons"] is None


def test_unverified_generated_links_are_not_promoted_to_media_or_citations(library):
    _, inbox, client = library
    path, store = write_store(inbox)
    store["lessons"]["lesson-one"]["text"] = "![A generated suggestion](https://unverified.example/photo.jpg)"
    store["lessons"]["lesson-one"]["citations"].append({"title": "Unsafe target", "url": "javascript:alert(1)"})
    path.write_text(json.dumps(store), encoding="utf-8")
    data = client.get("/api/investigations/v1/learning/lesson/lesson-one").json()["data"]
    assert data["media"] == [] and data["citations"][-1]["url"] == ""
    assert "unverified.example" not in json.dumps(data["citations"])


@pytest.mark.parametrize("query", ["ctx_v=2", "pillar=invented", "knowledge_class=fact", "kind=company", "offset=-1", "limit=101", "limit=0", "revision=-1", "q=" + "x" * 201])
def test_invalid_learning_selection_is_not_silently_broadened(library, query):
    assert library[2].get("/api/investigations/v1/learning?" + query).status_code == 422


def test_missing_entries_and_pathlike_ids_are_not_hydrated(library):
    client = library[2]
    for path in ("concept/missing", "lesson/missing", "company/company-a", "concept/..%2Fprivate"):
        assert client.get("/api/investigations/v1/learning/" + path).status_code == 404


def test_routes_require_authoring_and_remote_session_before_store_reads(library, monkeypatch):
    _, _, client = library
    monkeypatch.setattr(api, "load_catalog", lambda *a, **k: pytest.fail("Unauthenticated/public reads must not reach stores"))
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    assert client.get("/api/investigations/v1/learning").status_code == 403
    assert client.get("/api/investigations/v1/learning/concept/concept-firmness").status_code == 403
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    monkeypatch.setenv("BIOS_REMOTE_INTERACTIVE", "true")
    monkeypatch.setenv("BIOS_REVIEW_USERNAME", "learn-test")
    monkeypatch.setenv("BIOS_REVIEW_PASSWORD", "learn-test-password")
    monkeypatch.setenv("BIOS_SESSION_SECRET", "learning-test-secret-long-enough-for-session")
    for path in ("/api/investigations/v1/learning", "/api/investigations/v1/learning/lesson/lesson-one"):
        response = client.get(path)
        assert response.status_code == 302 and response.headers["location"].startswith("/login?next=")


def test_expand_links_preserve_safe_native_return_context_and_reject_external(library):
    _, _, client = library
    path = "/api/investigations/v1/learning/concept/concept-firmness"
    safe = "/app/learn?ctx_v=1&berry=berry-blueberry&q=firmness%26texture"
    data = client.get(path, params={"return_to": safe}).json()["data"]
    assert parse_qs(urlsplit(data["expand_href"]).query)["return_to"] == [safe]
    data = client.get(path, params={"return_to": "https://evil.example/app/learn"}).json()["data"]
    assert parse_qs(urlsplit(data["expand_href"]).query)["return_to"] == ["/app/learn"]


def test_authenticated_remote_session_can_read_private_learning(library, monkeypatch):
    _, _, client = library
    secret = "learning-test-secret-long-enough-for-session"
    monkeypatch.setenv("BIOS_REMOTE_INTERACTIVE", "true")
    monkeypatch.setenv("BIOS_REVIEW_USERNAME", "learn-test")
    monkeypatch.setenv("BIOS_REVIEW_PASSWORD", "learn-test-password")
    monkeypatch.setenv("BIOS_SESSION_SECRET", secret)
    signed = TimestampSigner(secret).sign(b64encode(json.dumps({"user": "learn-test"}).encode())).decode()
    client.cookies.set(SESSION_COOKIE_NAME, signed)
    response = client.get("/api/investigations/v1/learning")
    assert response.status_code == 200 and response.json()["data"]["counts"]["concepts"] == 3


def test_bounded_selected_body_is_explicit_instead_of_truncated(library, monkeypatch):
    _, inbox, client = library
    write_store(inbox)
    monkeypatch.setattr(api, "MAX_SELECTED_TEXT", 10)
    response = client.get("/api/investigations/v1/learning/lesson/lesson-one")
    assert response.status_code == 422 and "retained Learn page" in response.json()["detail"]


def test_review_freshness_is_evaluated_at_read_time_not_cached(library, monkeypatch):
    _, inbox, _ = library
    write_store(inbox)
    catalog = api.load_catalog(inbox)
    class EarlierDate:
        @staticmethod
        def today():
            return date(2025, 1, 1)
    monkeypatch.setattr(api, "date", EarlierDate)
    first = api.learning_data(catalog, api.normalize_selection({}))
    assert first["counts"]["stale"] == 0
    monkeypatch.setattr(api, "date", date)
    assert api.learning_data(catalog, api.normalize_selection({}))["counts"]["stale"] == 2
