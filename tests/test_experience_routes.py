"""Private shell, full selector round trips and legacy saved-view boundaries."""
from copy import deepcopy
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from app import main
from app.services import landscape_workspace as workspace
from app.session_auth import DEFAULT_NEXT_PATH, safe_next_path


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path / "inbox")
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    monkeypatch.delenv("BIOS_REMOTE_INTERACTIVE", raising=False)
    return TestClient(main.app, follow_redirects=False)


def context():
    return {"ctx_v": "1", "berry": "berry-blueberry", "countries": "geography-china,geography-peru",
            "geo_basis": "company_connections", "actor_roles": "", "relationship_types": "develops",
            "news_from": "2025-01-01", "news_to": "2026-11-11", "focus": "company-fall-creek-farm-and-nursery",
            "cohort_companies": "company-fall-creek-farm-and-nursery,company-costa-group-holdings",
            "cohort_varieties": "variety-eterna", "lens": "comparison", "comparison_kind": "company",
            "detail_path": "company:company-costa-group-holdings~source:ev-producereport-blugenix-2026",
            "q": "Costa", "q_scope": "catalog", "saved_view_id": "", "saved_revision": ""}


def test_shell_requires_authoring_even_when_remote_mode_is_off(client, monkeypatch):
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    for path in ("/app", "/app/landscape", "/api/investigations/v1/saved", "/api/investigations/v1/saved/missing", "/api/investigations/v1/demo/sensory"):
        assert client.get(path).status_code == 403
    assert client.post("/api/investigations/v1/saved", json={}).status_code == 403


def test_shell_is_session_protected_before_reading_build(client, monkeypatch):
    monkeypatch.setenv("BIOS_REMOTE_INTERACTIVE", "true")
    monkeypatch.setenv("BIOS_REVIEW_USERNAME", "experience-test")
    monkeypatch.setenv("BIOS_REVIEW_PASSWORD", "experience-test-password")
    monkeypatch.setenv("BIOS_SESSION_SECRET", "experience-test-signing-secret-at-least-32")
    response = client.get("/app/landscape?ctx_v=1&countries=")
    assert response.status_code == 302
    assert response.headers["location"].startswith("/login?next=")
    assert client.get("/api/investigations/v1/saved").status_code in (302, 401)


def test_shell_serves_one_built_root_for_native_deep_links(client, monkeypatch, tmp_path):
    monkeypatch.setattr(main, "BASE_DIR", tmp_path)
    index = tmp_path / "app/static/investigation/index.html"
    index.parent.mkdir(parents=True)
    index.write_text('<div id="root"></div><script type="module" src="/static/investigation/client.js"></script>')
    for surface in ("landscape", "briefing", "workspaces", "learn"):
        response = client.get("/app/" + surface)
        assert response.status_code == 200
        assert response.text == index.read_text()
        assert response.headers["cache-control"] == "private, no-store"
    assert client.get("/app/not-a-surface").status_code == 404


def test_built_entry_cannot_bypass_private_application_route(client, monkeypatch):
    response = client.get("/static/investigation/index.html?ctx_v=1&countries=")
    assert response.status_code == 307
    assert response.headers["location"] == "/app/landscape?ctx_v=1&countries="
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    assert client.get("/static/investigation/index.html").status_code == 403


def test_published_snapshot_retains_public_assets_and_excludes_private_client(tmp_path):
    from scripts.build_static import copy_public_static_assets
    source, target = tmp_path / "source", tmp_path / "public"
    (source / "investigation/assets").mkdir(parents=True)
    (source / "investigation/index.html").write_text("private application entry")
    (source / "investigation/assets/client.js").write_text("private application bundle")
    (source / "news.css").write_text("existing public news styling")
    copy_public_static_assets(source, target)
    assert (target / "news.css").read_text() == "existing public news styling"
    assert not (target / "investigation").exists()


def test_investigation_save_reopen_resave_preserves_every_selector(client):
    selection = context()
    response = client.post("/api/investigations/v1/saved", json={"name": "China genetics", "context": selection})
    assert response.status_code == 201, response.text
    first = response.json()["data"]
    assert first["kind"] == "explorer" and first["is_investigation"]
    for key, value in selection.items():
        assert first["filters"][key] == value
    query = parse_qs(urlsplit(first["href"]).query, keep_blank_values=True)
    for key, value in selection.items():
        if key not in {"saved_view_id", "saved_revision"}:
            assert query[key] == [value]
    loaded = client.get("/api/investigations/v1/saved/" + first["id"]).json()["data"]
    assert loaded["filters"] == first["filters"]
    response = client.post("/api/investigations/v1/saved", json={
        "name": "China genetics", "context": loaded["filters"], "id": first["id"], "revision": first["revision"]})
    assert response.status_code == 200
    assert response.json()["data"]["filters"] == first["filters"]
    assert response.json()["data"]["revision"] == 2
    conflict = client.post("/api/investigations/v1/saved", json={
        "name": "Stale", "context": selection, "id": first["id"], "revision": 1})
    assert conflict.status_code == 409
    assert workspace.load_views(main.INBOX_DIR)["version"] == 1
    assert len(workspace.load_views(main.INBOX_DIR)["history"]) == 2


def test_legacy_conversion_saves_new_and_old_routes_cannot_erase_context(client):
    old = workspace.save_view(main.INBOX_DIR, name="Legacy Explorer", filters={"berry": "berry-blueberry"}, kind="explorer")
    before = deepcopy(workspace.load_views(main.INBOX_DIR)["views"][old["id"]])
    denied = client.post("/api/investigations/v1/saved", json={
        "name": "Converted", "context": context(), "id": old["id"], "revision": old["revision"]})
    assert denied.status_code in (409, 422)
    saved = client.post("/api/investigations/v1/saved", json={
        "name": "Converted", "context": context(), "id": old["id"], "revision": 1, "save_as_new": True})
    assert saved.status_code == 201
    current = saved.json()["data"]
    assert current["id"] != old["id"]
    assert workspace.load_views(main.INBOX_DIR)["views"][old["id"]] == before
    with pytest.raises(ValueError, match="new Landscape"):
        workspace.save_view(main.INBOX_DIR, name="Lost state", filters={"berry": "berry-blueberry"},
                            kind="explorer", view_id=current["id"], revision="1")
    assert workspace.view_href(old).startswith("/landscapes/explorer?")


def test_new_saved_investigation_keeps_valid_legacy_explorer_defaults(client):
    from app.services.landscape_explorer import selection
    saved = workspace.save_view(main.INBOX_DIR, name="Compatible fallback", kind="explorer",
                                filters={**context(), "countries": "", "focus": "", "q": ""})
    fallback = selection(saved["filters"], {"berry-blueberry": {
        "id": "berry-blueberry", "name": "Blueberry", "entity_type": "berry"}})
    assert fallback["view"] == "portrait" and fallback["window"] == "all"
    assert fallback["evidence"] == "reviewed" and fallback["time"] == "published"
    assert saved["filters"]["detail_path"] == context()["detail_path"]
    assert saved["filters"]["cohort_companies"] == context()["cohort_companies"]


def test_source_sections_and_separate_demo_cohort_survive_save_reopen(client):
    selection = {**context(),
        "detail_path": "company:company-costa-group-holdings~source:ev-costa-vip@brief~source:ev-producereport-blugenix-2026@article",
        "demo_specimens": "demo-specimen-amber,demo-specimen-fern"}
    response = client.post("/api/investigations/v1/saved", json={"name": "Sections and demo", "context": selection})
    assert response.status_code == 201, response.text
    row = response.json()["data"]
    expected_path = selection["detail_path"].removesuffix("@article")
    assert row["filters"]["detail_path"] == expected_path
    assert row["filters"]["demo_specimens"] == selection["demo_specimens"]
    assert row["filters"]["cohort_companies"] == selection["cohort_companies"]
    assert row["filters"]["cohort_varieties"] == selection["cohort_varieties"]
    loaded = client.get("/api/investigations/v1/saved/" + row["id"]).json()["data"]
    query = parse_qs(urlsplit(loaded["href"]).query, keep_blank_values=True)
    assert query["detail_path"] == [expected_path]
    assert query["demo_specimens"] == [selection["demo_specimens"]]


def test_source_section_and_synthetic_namespace_validation_stays_typed():
    from app.services.investigation_api import normalize_context
    for path in ("company:company-a@brief", "source:ev-a@unsupported"):
        with pytest.raises(ValueError, match="section"):
            normalize_context({"detail_path": path})
    with pytest.raises(ValueError, match="demo specimen namespace"):
        normalize_context({"demo_specimens": "variety-real-commercial"})
    # Unknown fixture membership remains a selector for isolated-demo resolution;
    # normalization never fabricates a score or turns it into a real variety.
    normalized, _ = normalize_context({"demo_specimens": "demo-specimen-unknown"})
    assert normalized["demo_specimens"] == "demo-specimen-unknown"
    assert normalized["cohort_varieties"] == ""


def test_save_is_same_origin_bounded_and_selector_only(client):
    assert client.post("/api/investigations/v1/saved", headers={"origin": "https://unrelated.example"},
                       json={"name": "Cross site", "context": context()}).status_code == 403
    assert client.post("/api/investigations/v1/saved", content=b"x" * 16_385).status_code == 413
    selection = {**context(), "article_text": "private source body", "private_notes": "unrelated note"}
    response = client.post("/api/investigations/v1/saved", json={"name": "Selectors only", "context": selection})
    assert response.status_code == 201
    content = (main.INBOX_DIR / workspace.VIEW_FILE).read_text()
    assert "private source body" not in content and "unrelated note" not in content


def test_demo_is_explicitly_synthetic_isolated_and_has_no_implied_distribution(client):
    response = client.get("/api/investigations/v1/demo/sensory?berry=berry-blackberry&countries=geography-china")
    assert response.status_code == 200
    data = response.json()
    assert data["synthetic"] is True and data["namespace"] == "synthetic-sensory-v1"
    assert data["metric"]["label"] == "Synthetic overall liking"
    assert (data["metric"]["minimum"], data["metric"]["maximum"]) == (1, 9)
    assert all(row["id"].startswith("demo-specimen-") and 1 <= row["value"] <= 9 for row in data["specimens"])
    assert "do not apply" in data["scope_note"]
    assert "not measured" in data["disclaimer"] and "no distribution" in data["disclaimer"]
    assert response.headers["cache-control"] == "private, no-store"
    assert not (main.DATA_DIR / "demo_data").exists()


def test_bounded_investigation_login_return_keeps_nested_context():
    from urllib.parse import urlencode
    investigation_url = "/app/landscape?" + urlencode(context())
    assert 512 < len(investigation_url) < 4096
    assert safe_next_path(investigation_url) == investigation_url
    escaped_search = "/app/landscape?" + urlencode({**context(), "q": "Costa & suppliers #1"})
    assert parse_qs(urlsplit(safe_next_path(escaped_search)).query)["q"] == ["Costa & suppliers #1"]
    url_search = "/app/landscape?" + urlencode({**context(), "q": "https://example.org/article"})
    assert safe_next_path(url_search) == url_search
    assert safe_next_path("/news?q=" + "x" * 600) == DEFAULT_NEXT_PATH
    assert safe_next_path("/app/landscape?q=" + "x" * 4096) == DEFAULT_NEXT_PATH
    for value in ("https://outside.example/app/landscape", "//outside.example/app/landscape", "http://[", "//[",
                  "/app/landscape?x=%0Aunsafe", "/app/landscape\\outside"):
        assert safe_next_path(value) == DEFAULT_NEXT_PATH


def test_native_learning_deep_link_and_legacy_editor_return_keep_context(client, monkeypatch, tmp_path):
    from app.services.learn_research import return_path
    from app.session_auth import is_investigation_path
    from urllib.parse import urlencode
    monkeypatch.setattr(main, "BASE_DIR", tmp_path)
    index = tmp_path / "app/static/investigation/index.html"
    index.parent.mkdir(parents=True)
    index.write_text('<div id="root"></div>')
    destination = "/app/learn/concept/pruning-basics?" + urlencode(context())
    assert client.get(destination).status_code == 200
    assert safe_next_path(destination) == destination and return_path(destination) == destination
    assert is_investigation_path("/app/learn/lesson/lesson-example-123")
    assert not is_investigation_path("/app/learn/concept/..")
    assert not is_investigation_path("/app/learn/unknown/item")
    assert return_path("https://external.example/app/learn") == "/learn"


def test_expanded_legacy_detail_has_safe_explicit_investigation_return():
    from app.session_auth import investigation_return_context
    from starlette.requests import Request
    from urllib.parse import urlencode
    from lxml import html
    destination = "/app/landscape?" + urlencode(context())
    request = Request({"type": "http", "method": "GET", "path": "/entities/company/company-costa-group-holdings",
                       "query_string": urlencode({"return_to": destination}).encode(), "headers": []})
    values = investigation_return_context(request)
    assert values["investigation_return_href"] == destination
    template = main.templates.get_template("_breadcrumbs.html")
    rendered = template.render(**values, authoring_mode=True, static_build=False)
    assert html.fromstring(rendered).xpath('//nav[@aria-label="Investigation return"]//a/@href') == [destination]
    assert "Return to investigation" not in template.render(**values, authoring_mode=False, static_build=False)
    assert "Return to investigation" not in template.render(**values, authoring_mode=True, static_build=True)
    request = Request({"type": "http", "method": "GET", "path": "/learn/topic",
                       "query_string": b"return_to=https%3A%2F%2Fexternal.example", "headers": []})
    assert investigation_return_context(request)["investigation_return_href"] == ""
