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
def test_unsafe_unsupported_or_ambiguous_context_never_enables_native_header(destination):
    assert investigation_return_context(request_for(destination))["investigation_header_links"] == {}


class HeaderNavigation(HTMLParser):
    def __init__(self):
        super().__init__()
        self.primary = []
        self.in_primary = False
        self.link = None
        self.save = None
        self.brand = None
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "nav" and attrs.get("aria-label") == "Primary":
            self.in_primary = True
        if tag == "a":
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
    monkeypatch.setattr(main, "all_entities", lambda: [])
    monkeypatch.setattr(main, "entity_index", lambda: {})
    monkeypatch.setattr(main, "published_evidence", lambda: [])
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


@pytest.mark.parametrize("destination", [None, "https://external.example/app/landscape?ctx_v=1", "/app/landscape?ctx_v=1&berry=berry-blueberry&berry=berry-strawberry"])
def test_ordinary_or_invalid_context_workspace_keeps_established_navigation(retained_client, destination):
    response = retained_client.get("/workspaces", params={"return_to": destination} if destination is not None else {})
    parsed = header(response)
    assert [item["label"] for item in parsed.primary] == ["News", "Personal Digest", "Map Explorer", "Social Listening", "Workspaces", "Global Watchlist", "Companies", "Learn"]
    assert parsed.primary[0]["href"] == "/today?refresh=1"
    assert parsed.brand == "/today" and parsed.save is None
