"""Native navigation on retained pages preserves one validated typed context."""
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlencode, urlsplit

from fastapi.testclient import TestClient
import pytest
from starlette.datastructures import QueryParams
from starlette.requests import Request

from app.session_auth import investigation_return_context
from app.services import investigation_api as api


def request_for(return_to="", path="/workspaces"):
    return Request({"type": "http", "scheme": "http", "server": ("testserver", 80), "path": path,
                    "query_string": urlencode({"return_to": return_to}).encode(), "headers": []})


def selection():
    return api.normalize_context({"berry": "berry-blueberry", "countries": "geography-china,geography-peru",
        "lens": "comparison", "comparison_kind": "company", "company_set": "watched",
        "cohort_companies": "company-fall-creek-farm-and-nursery,company-costa-group-holdings",
        "cohort_varieties": "variety-eterna", "focus": "company-costa-group-holdings",
        "detail_path": "company:company-costa-group-holdings~source:ev-source@brief",
        "demo_specimens": "demo-specimen-fern-1", "news_from": "2026-01-01", "news_to": "2026-11-12",
        "q": "Costa & suppliers #1 https://example.com/story?a=1", "q_scope": "catalog",
        "saved_view_id": "lview-one", "saved_revision": "3"})[0]


def test_header_links_share_exact_typed_selection_without_data_lookups(monkeypatch):
    ctx = selection()
    destination = "/app/landscape?" + api.context_query(ctx)
    monkeypatch.setattr(api, "load_world", lambda: pytest.fail("Header navigation must not load domain records"))
    result = investigation_return_context(request_for(destination, "/workspaces/wp-example"))
    assert result["investigation_return_href"] == destination
    assert result["investigation_header_current"] == "workspaces"
    links = result["investigation_header_links"]
    for name, path in (("landscape", "/app/landscape"), ("briefing", "/app/briefing"), ("learn", "/app/learn"), ("save", "/app/workspaces")):
        target = urlsplit(links[name])
        assert target.path == path and not target.netloc and not target.fragment
        assert api.normalize_context(QueryParams(target.query))[0] == ctx
    workspace = urlsplit(links["workspaces"])
    assert workspace.path == "/workspaces"
    assert parse_qs(workspace.query)["return_to"] == [destination]


def test_workspace_return_retains_nested_learning_destination():
    destination = "/app/learn/concept/firmness?ctx_v=1&berry=berry-blueberry&countries="
    links = investigation_return_context(request_for(destination))["investigation_header_links"]
    native_return = parse_qs(urlsplit(links["workspaces"]).query)["return_to"][0]
    assert urlsplit(native_return).path == "/app/learn/concept/firmness"
    assert parse_qs(urlsplit(native_return).query, keep_blank_values=True)["countries"] == [""]


@pytest.mark.parametrize("destination", [
    "https://external.example/app/landscape?ctx_v=1", "//external.example/app/landscape?ctx_v=1",
    "/app/landscape?ctx_v=1%0d%0aLocation%3Aevil", "/app/not-a-surface?ctx_v=1",
    "/app/landscape?ctx_v=2", "/app/landscape?berry=berry-blueberry",
    "/app/landscape?ctx_v=1&berry=berry-blueberry&berry=berry-strawberry",
    "/app/landscape?ctx_v=1&cohort_companies=company-a&cohort_companies=company-b",
    "/app/landscape?ctx_v=1&news_from=not-a-date", "/app/landscape?ctx_v=1&countries=../private",
])
def test_unsafe_unsupported_or_ambiguous_context_never_creates_typed_header_links(destination):
    assert investigation_return_context(request_for(destination))["investigation_header_links"] == {}


class HeaderNavigation(HTMLParser):
    def __init__(self):
        super().__init__()
        self.primary = []
        self.in_primary = False
        self.link = None
        self.save = None
        self.brand = None
        self.more = False
        self.anchors = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "nav" and attrs.get("aria-label") == "Primary":
            self.in_primary = True
        if tag == "details" and "glass-more" in attrs.get("class", "").split():
            self.more = True
        if tag == "a":
            self.anchors.append(attrs)
            if "glass-brand" in attrs.get("class", "").split():
                self.brand = attrs.get("href")
            if "glass-investigation-save" in attrs.get("class", "").split():
                self.save = attrs.get("href")
            if self.in_primary:
                self.link = {"href": attrs.get("href"), "current": attrs.get("aria-current"), "label": ""}
    def handle_data(self, value):
        if self.link is not None:
            self.link["label"] += value
    def handle_endtag(self, tag):
        if tag == "a" and self.link is not None:
            self.primary.append(self.link)
            self.link = None
        if tag == "nav":
            self.in_primary = False


@pytest.fixture
def retained_client(tmp_path, monkeypatch):
    from app import main
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path / "inbox")
    monkeypatch.setattr(main, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    entities = {key: {"id": key, "name": label, "entity_type": "berry", "status": "published"}
                for key, label in main.BERRIES.items()}
    entities.update({f"geography-{name.lower()}": {"id": f"geography-{name.lower()}", "name": name,
                     "entity_type": "geography", "country_code": code, "status": "published"}
                     for name, code in (("Chile", "CL"), ("China", "CN"), ("Peru", "PE"))})
    monkeypatch.setattr(main, "all_entities", lambda: list(entities.values()))
    monkeypatch.setattr(main, "entity_index", lambda: entities)
    monkeypatch.setattr(main, "all_evidence", lambda: [])
    monkeypatch.setattr(main, "published_evidence", lambda: [])
    monkeypatch.setattr(main, "all_relationships", lambda: [])
    monkeypatch.setattr(main, "all_facts", lambda: [])
    monkeypatch.setattr(main, "_compute_nav_work_counts", lambda: {})
    return TestClient(main.app)


def header(response):
    assert response.status_code == 200
    parsed = HeaderNavigation()
    parsed.feed(response.text)
    return parsed


def test_actual_workspace_route_uses_same_four_primary_destinations_and_separate_save(retained_client):
    ctx = selection()
    destination = "/app/landscape?" + api.context_query(ctx)
    parsed = header(retained_client.get("/workspaces", params={"return_to": destination}))
    assert [item["label"] for item in parsed.primary] == ["Landscape", "Briefing", "Workspaces", "Learn"]
    assert [item["label"] for item in parsed.primary if item["current"] == "page"] == ["Workspaces"]
    assert urlsplit(parsed.brand).path == "/app/landscape"
    assert urlsplit(parsed.save).path == "/app/workspaces"
    for item in parsed.primary:
        target = urlsplit(item["href"])
        if item["label"] != "Workspaces":
            assert api.normalize_context(QueryParams(target.query))[0] == ctx
    assert all("refresh=1" not in item["href"] for item in parsed.primary)


@pytest.mark.parametrize("path,current", [("/workspaces", "Workspaces"), ("/landscapes/explorer", "Landscape")])
@pytest.mark.parametrize("destination", [None, "https://external.example/app/landscape?ctx_v=1&focus=company-untrusted-header", "/app/landscape?ctx_v=1&berry=berry-blueberry&berry=berry-strawberry", "/app/landscape?ctx_v=2&company_set=watched"])
def test_direct_or_invalid_return_uses_only_four_canonical_authoring_links(retained_client, destination, path, current):
    response = retained_client.get(path, params={"return_to": destination} if destination is not None else {})
    parsed = header(response)
    assert [item["label"] for item in parsed.primary] == ["Landscape", "Briefing", "Workspaces", "Learn"]
    assert [item["href"] for item in parsed.primary] == ["/app/landscape", "/app/briefing", "/workspaces", "/app/learn"]
    assert [item["label"] for item in parsed.primary if item["current"] == "page"] == [current]
    assert parsed.brand == "/app/landscape" and parsed.save == "/app/workspaces"
    assert parsed.more
    assert all(not urlsplit(item["href"]).query for item in parsed.primary)


def test_direct_map_explorer_does_not_coerce_legacy_filters_into_native_selectors(retained_client):
    parsed = header(retained_client.get("/explorer", params={
        "berry": "berry-strawberry", "q": "UNVALIDATED_HEADER_QUERY", "focus": "company-untrusted-header",
        "cohort_companies": "company-untrusted-header", "company_set": "watched",
    }))
    assert [item["href"] for item in parsed.primary] == ["/app/landscape", "/app/briefing", "/workspaces", "/app/learn"]
    assert parsed.save == "/app/workspaces"


def test_actual_explorer_valid_return_preserves_full_native_selection(retained_client):
    context = selection()
    destination = "/app/briefing?" + api.context_query(context)
    parsed = header(retained_client.get("/landscapes/explorer", params={"return_to": destination}))
    assert [item["label"] for item in parsed.primary] == ["Landscape", "Briefing", "Workspaces", "Learn"]
    for link in parsed.primary:
        target = urlsplit(link["href"])
        if link["label"] == "Workspaces":
            native = parse_qs(target.query)["return_to"][0]
            assert api.normalize_context(QueryParams(urlsplit(native).query))[0] == context
        else:
            assert api.normalize_context(QueryParams(target.query))[0] == context
    assert api.normalize_context(QueryParams(urlsplit(parsed.save).query))[0] == context


@pytest.mark.parametrize("static_build,authoring", [(True, True), (True, False), (False, False)])
def test_static_and_read_only_shell_keep_public_navigation_rules(retained_client, static_build, authoring):
    from app import main
    request = request_for("/app/landscape?" + api.context_query(selection()), path="/explorer")
    request.scope["app"] = main.app
    response = main.templates.TemplateResponse(request=request, name="glasshouse_base.html", context={
        "authoring_mode": authoring, "static_build": static_build,
    })
    parsed = HeaderNavigation()
    parsed.feed(response.body.decode())
    assert parsed.save is None
    assert not any(link["href"].startswith(("/app/", "/workspaces")) for link in parsed.primary)
    if static_build:
        assert [link["label"] for link in parsed.primary] == ["News", "Companies", "Varieties", "Learn", "Search"]
        assert parsed.brand == "/"
    else:
        assert [link["label"] for link in parsed.primary] == ["News", "Personal Digest", "Map Explorer", "Companies", "Learn"]
        assert parsed.brand == "/today"


def test_guide_inherited_body_links_keep_the_validated_investigation_return(retained_client):
    context = selection()
    destination = "/app/landscape?" + api.context_query(context)
    parsed = header(retained_client.get("/guide", params={"return_to": destination}))
    body_links = [row for row in parsed.anchors if "guide-button" in row.get("class", "").split()
                  and urlsplit(row.get("href", "")).path == "/workspaces"]
    assert body_links, "The Guide child template must receive its parent's scope-link macro"
    for row in body_links:
        target = parse_qs(urlsplit(row["href"]).query)["return_to"][0]
        assert urlsplit(target).path == "/app/landscape"
        assert api.normalize_context(QueryParams(urlsplit(target).query))[0] == context


@pytest.mark.parametrize("candidate", ["https://external.example/path?keep=1", "//external.example/path", "/\\external/path", "/workspaces#section"])
def test_parent_scope_macro_never_adds_investigation_selectors_to_external_or_unsafe_destinations(retained_client, candidate):
    from app import main
    request = request_for("/app/landscape?" + api.context_query(selection()), path="/guide")
    request.scope["app"] = main.app
    template = main.templates.env.from_string('{% extends "glasshouse_base.html" %}{% block content %}<a id="header-probe" href="{{ workspace_shell_href(candidate) }}">Probe</a>{% endblock %}')
    html = template.render(request=request, candidate=candidate, authoring_mode=True, static_build=False,
                           berries=main.BERRIES, nav_work_counts={}, **investigation_return_context(request))
    parsed = HeaderNavigation()
    parsed.feed(html)
    probe = next(row["href"] for row in parsed.anchors if row.get("id") == "header-probe")
    assert probe == candidate
    assert "return_to=" not in probe and "cohort_companies" not in probe


def test_parent_scope_macro_does_not_propagate_an_ambiguous_return_context(retained_client):
    from app import main
    request = request_for("/app/landscape?ctx_v=1&berry=berry-blueberry&berry=berry-strawberry", path="/guide")
    request.scope["app"] = main.app
    template = main.templates.env.from_string('{% extends "glasshouse_base.html" %}{% block content %}<a id="header-probe" href="{{ workspace_shell_href("/workspaces?entity=company-example") }}">Probe</a>{% endblock %}')
    html = template.render(request=request, authoring_mode=True, static_build=False, berries=main.BERRIES,
                           nav_work_counts={}, **investigation_return_context(request))
    parsed = HeaderNavigation()
    parsed.feed(html)
    assert next(row["href"] for row in parsed.anchors if row.get("id") == "header-probe") == "/workspaces?entity=company-example"
