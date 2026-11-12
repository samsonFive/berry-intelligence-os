"""Live investigation selectors must not be reinterpreted by legacy generation."""
from copy import deepcopy
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.services import workspace_landscapes as links
from app.services import landscape_workspace, living_workspaces as living


@pytest.fixture
def views(monkeypatch):
    def row(key, **values):
        return {"id": key, "name": key, "archived": False, "revision": 1,
                "filters": {"berry": "berry-blueberry", "countries": "geography-peru"}, **values}
    rows = {item["id"]: item for item in [
        row("lview-ordinary"), row("lview-explorer", kind="explorer"),
        row("lview-watch", surface="watchlist"), row("lview-archived", archived=True),
        row("lview-live-comparison", kind="explorer", filters={"ctx_v": "1", "lens": "comparison",
            "cohort_companies": "company-a,company-b", "countries": "geography-china"}),
        row("lview-live-news", kind="explorer", filters={"ctx_v": "1", "lens": "news", "company_set": "watched"}),
        row("lview-live-archived", kind="explorer", archived=True, filters={"ctx_v": "1"}),
    ]}
    monkeypatch.setattr(landscape_workspace, "load_views", lambda inbox: {"views": deepcopy(rows)})
    return rows


def stub_store(monkeypatch):
    comparison = {"id": "comparison-preserved", "title": "Original comparison", "snapshot": {
        "scope": {"companies": ["company-a"]}, "assessments": [], "captured_at": "2026-10-01"}}
    class ExistingStore:
        def __init__(self, inbox):
            pass
        def rows(self, kind):
            return [deepcopy(comparison)] if kind == "competitive_comparison" else []
        def get(self, key):
            return deepcopy(comparison) if key == comparison["id"] else None
    monkeypatch.setattr(living, "Store", ExistingStore)


def test_choices_preserve_existing_views_and_comparisons_but_exclude_live_selectors(views, monkeypatch, tmp_path):
    stub_store(monkeypatch)
    main = SimpleNamespace(INBOX_DIR=tmp_path, AUTHORING_MODE=True)
    before = deepcopy(views)
    result = {row["id"]: row for row in links.choices(main)}
    assert set(result) == {"gene-editing", "lview-ordinary", "lview-explorer", "lview-watch", "comparison-preserved"}
    assert result["lview-explorer"]["href"] == "/landscapes/explorer?saved_view=lview-explorer"
    assert result["lview-watch"]["href"] == "/global-watchlist?saved_view=lview-watch"
    assert result["comparison-preserved"]["href"] == "/competitive-evaluation?saved=comparison-preserved"
    assert views == before
    assert landscape_workspace.view_href(views["lview-live-comparison"]).startswith("/app/landscape?")
    assert "cohort_companies=company-a%2Ccompany-b" in landscape_workspace.view_href(views["lview-live-comparison"])


@pytest.mark.parametrize("key", ["lview-live-comparison", "lview-live-news"])
def test_live_links_fail_closed_before_any_legacy_context(views, monkeypatch, tmp_path, key):
    from app import landscape_explorer_routes, landscape_routes
    stub_store(monkeypatch)
    monkeypatch.setattr(landscape_explorer_routes, "context", lambda *args, **kwargs: pytest.fail("Live selectors reached legacy Explorer"))
    monkeypatch.setattr(landscape_routes, "context", lambda *args, **kwargs: pytest.fail("Live selectors reached legacy Landscape"))
    with pytest.raises(ValueError, match="^" + links.LIVE_INVESTIGATION_NOTICE.replace(".", r"\.") + "$"):
        links.resolve(SimpleNamespace(INBOX_DIR=tmp_path, AUTHORING_MODE=True), None, [key])


@pytest.mark.parametrize("key", ["lview-missing", "lview-archived", "lview-live-archived"])
def test_unknown_and_archived_links_keep_the_existing_guard(views, monkeypatch, tmp_path, key):
    stub_store(monkeypatch)
    with pytest.raises(ValueError, match="Linked Landscape is unavailable or archived"):
        links.resolve(SimpleNamespace(INBOX_DIR=tmp_path, AUTHORING_MODE=True), None, [key])


def test_ordinary_explorer_watch_and_snapshot_comparison_keep_existing_resolution(views, monkeypatch, tmp_path):
    from app import landscape_explorer_routes, landscape_routes
    from app.services import global_watchlist
    stub_store(monkeypatch)
    source = {"id": "ev-preserved", "title": "Original source", "published_date": "2026-10-01",
              "source_url": "https://example.com/source", "summary": "Original summary", "supporting_excerpt": "Original excerpt"}
    calls = []
    def ordinary(params):
        calls.append(("ordinary", params))
        return None, {"filters": dict(params), "panels": {"companies": [{"id": "company-a"}], "sources": [source]}}, None, None, None
    def explorer(request, params):
        calls.append(("explorer", params))
        return None, None, {"filters": {"focus": "company-b"}, "nodes": {"company-b": {"label": "Company B"}}, "edges": [], "sources": [source]}, None, None
    def watch(**kwargs):
        calls.append(("watch", kwargs["params"]))
        return {"rows": [{"id": "company-c", "name": "Company C", "roles": ["grower"], "tier": "untiered", "confidence": "unknown", "regions": []}],
                "news": [{"sources": [source]}], "data_note": "Original coverage limit"}
    monkeypatch.setattr(landscape_routes, "context", ordinary)
    monkeypatch.setattr(landscape_explorer_routes, "context", explorer)
    monkeypatch.setattr(global_watchlist, "build", watch)
    main = SimpleNamespace(INBOX_DIR=tmp_path, DATA_DIR=tmp_path, AUTHORING_MODE=True,
        all_entities=lambda: [], published_evidence=lambda: [], all_relationships=lambda: [],
        all_signals=lambda: [], all_assessments=lambda: [], load_sources=lambda: [])
    result = links.resolve(main, None, ["lview-ordinary", "lview-explorer", "lview-watch", "comparison-preserved"])
    assert [row["id"] for row in result] == ["lview-ordinary", "lview-explorer", "lview-watch", "comparison-preserved"]
    assert calls == [("ordinary", {**views["lview-ordinary"]["filters"], "configured": "1"}),
                     ("explorer", {"saved_view": "lview-explorer"}), ("watch", {"berry": "blueberry"})]
    assert result[0]["data"]["panels"]["companies"] == [{"id": "company-a"}]
    assert result[1]["data"]["filters"] == {"focus": "company-b"}
    assert result[2]["data"]["coverage_note"] == "Original coverage limit"
    assert result[3]["data"]["scope"] == {"companies": ["company-a"]}
    assert all(row["data"]["sources"][0]["supporting_excerpt"] == "Original excerpt" for row in result[:3])


@pytest.mark.parametrize("key", ["lview-live-comparison", "lview-live-news"])
def test_already_linked_live_selection_blocks_generation_before_model_and_preserves_page(views, monkeypatch, tmp_path, key):
    from app import living_workspace_routes as routes
    from app.services.ai_gateway import untrusted_complete
    store = living.Store(tmp_path / "inbox")
    page = store.create_page("Local boundary fixture", None, "Fixture analyst", "boundary-create")
    page["landscape_links"] = [key]
    page = store.save_page(page["id"], page, "Fixture analyst")
    main = SimpleNamespace(INBOX_DIR=tmp_path / "inbox", AUTHORING_MODE=True)
    monkeypatch.setattr(routes, "context", lambda request, mutate=False: (main, store, "Fixture analyst"))
    monkeypatch.setattr(untrusted_complete, "maybe_untrusted_completer", lambda: pytest.fail("Blocked link reached provider setup"))
    monkeypatch.setattr(living, "model_narrative", lambda *args, **kwargs: pytest.fail("Blocked link reached model generation"))
    app = FastAPI()
    app.include_router(routes.router)
    response = TestClient(app).post("/api/workspaces/generate/" + page["id"], json={
        "token": "boundary-generate", "version": page["version"], "target": "overview", "use_model": True})
    assert response.status_code == 422
    assert response.json()["detail"] == links.LIVE_INVESTIGATION_NOTICE
    assert store.get(page["id"]) == page
