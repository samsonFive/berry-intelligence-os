"""Portfolio reconciliation must expose content gaps and respect profile edits."""
from copy import deepcopy
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.services import company_directory
from app.services.variety_portfolio_coverage import (
    load_portfolio_observations, portfolio_coverage, reconcile_portfolios,
    source_content_coverage,
)

ROOT = Path(__file__).resolve().parents[1]


def registry(tmp_path, *, website=""):
    folder = tmp_path / "imports/competitor-coverage-registry-2026-09-21"
    folder.mkdir(parents=True)
    path = folder / "reconciliation-matrix.json"
    path.write_text(json.dumps({"rows": [{"input_registry_name": "Example Program",
        "canonical_entity_ids": ["breeding_program-example"], "website": website,
        "resolution_status": "matched"}]}), encoding="utf-8")
    return path


def plan(tmp_path, entity, **kwargs):
    return portfolio_coverage(data_dir=tmp_path, sources=[], varieties=[],
        entities=[entity], candidates=[], **kwargs)["subjects"][0]


def test_existing_directory_website_fields_fill_source_plan_without_mutation(tmp_path):
    path = registry(tmp_path)
    before = path.read_bytes()
    entity = {"id": "breeding_program-example", "entity_type": "breeding_program",
        "name": "Example Program", "attributes": {"official_website": "https://example.test/official"},
        "website": "https://example.test/legacy"}
    original = deepcopy(entity)
    result = plan(tmp_path, entity)
    assert result["website"] == result["starting_url"] == "https://example.test/official"
    assert result["href"] == "/entities/breeding_program/breeding_program-example"
    assert not result["checked"]
    assert entity == original
    entity["attributes"] = {}
    assert plan(tmp_path, entity)["starting_url"] == "https://example.test/legacy"
    assert path.read_bytes() == before and original["attributes"]["official_website"] == result["website"]


def test_analyst_website_edit_and_explicit_clear_override_older_registry_link(tmp_path):
    path = registry(tmp_path, website="https://example.test/old-registry")
    before = path.read_bytes()
    entity = {"id": "breeding_program-example", "entity_type": "breeding_program",
        "name": "Example Program", "attributes": {"website": "https://example.test/canonical"}}
    original = deepcopy(entity)
    for value in ("https://example.test/analyst-edit", ""):
        profiles = {entity["id"]: {"website": value}}
        profile_before = deepcopy(profiles)
        catalog = company_directory.catalog({entity["id"]: entity}, profiles=profiles)
        result = plan(tmp_path, entity, company_catalog=catalog)
        assert result["website"] == result["starting_url"] == value
        assert not result["checked"]
        assert profiles == profile_before
    assert path.read_bytes() == before and entity == original


def test_source_content_counts_keep_full_partial_transcript_and_access_distinct():
    def record(id, **kw):
        return {"id": id, "status": "published", **kw}
    rows = [
        record("full", article={"paragraphs": [{"text": "A readable berry source describes cultivation and trials. " * 15}]}),
        record("partial", article={"paragraphs": [{"text": "Short source paragraph about berry cultivation."}]}),
        record("transcript", transcript={"text": "A recorded discussion about berry trials."}),
        record("wall", article={"paragraphs": [{"text": "Before you continue to Google. Accept all cookies."}]}),
        record("summary", summary="Varieties including Example Red and Example Gold."),
        record("description", publisher_description="Publisher preview of a berry article."),
        record("paywall", discovery_provenance={"acquisition_failure_category": "paywall"}),
        {"id": "pending", "status": "draft", "article": {"full_text": "PRIVATE BODY " * 100}},
    ]
    original = deepcopy(rows)
    result = source_content_coverage(rows)
    assert result == {"published_sources": 7, "full_articles": 1, "partial_articles": 1,
        "transcripts": 1, "readable_sources": 3, "access_screens": 1,
        "descriptions_only": 1, "access_limited": 1, "body_unavailable": 1}
    assert rows == original
    assert "PRIVATE BODY" not in json.dumps(result) and "text" not in result
    assert source_content_coverage([])["published_sources"] == 0


def test_ucdavis_historical_accounting_keeps_ambiguous_labels_without_inferred_identity():
    sources = [s for s in load_portfolio_observations(ROOT / "data") if s["id"].startswith("portfolio-ucdavis-")]
    assert len(sources) == 2 and sum(len(s["names"]) for s in sources) == 45
    historical = next(s for s in sources if "historical" in s["id"])
    assert historical["accounting"]["observed_items"] == 35
    assert {x["label"] for x in historical["accounting"]["exclusions"]} == {"Selva Chandler", "Marshall/Banner"}
    assert {x["candidate_name"] for x in historical["names"]} >= {"Klondike", "Nich Ohmer", "Lassen", "Shasta"}
    assert not any("published_date" in s for s in sources)
    rows, candidates = reconcile_portfolios(sources=sources, varieties=[], entities=[], candidates=[])
    assert all(not row["accounting_view"]["issues"] for row in rows)
    assert not {"Selva", "Chandler", "Marshall", "Banner", "Selva Chandler", "Marshall/Banner"} & {c["candidate_name"] for c in candidates}
    assert all(not c["human_gated"] and not c["proposed_relationships"] and not c["deployment"] for c in candidates)


def test_uc_prefix_is_not_an_alias_and_conflicting_original_urls_remain_separate():
    sources = [s for s in load_portfolio_observations(ROOT / "data") if s["id"].startswith("portfolio-ucdavis-")]
    original = deepcopy(sources)
    varieties = [{"id": "v-eclipse", "entity_type": "variety", "name": "Eclipse", "berry_ids": ["berry-strawberry"]}]
    rows, candidates = reconcile_portfolios(sources=sources, varieties=varieties, entities=[], candidates=[])
    eclipse = next(c for c in candidates if c["candidate_name"] == "UC Eclipse")
    assert not any(n["catalog_id"] for row in rows for n in row["names"] if n["candidate_name"] == "UC Eclipse")
    assert {r["product_url"] for r in eclipse["portfolio_sources"]} == {
        "https://strawberry.ucdavis.edu/ucd-eclipse", "https://strawberry.ucdavis.edu/uc-eclipse"}
    assert eclipse["aliases"] == [] and not eclipse["auto_confirmed"]
    assert sources == original


def test_live_coverage_respects_profile_edits_and_never_writes_on_get(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    path = tmp_path / company_directory.PROFILE_FILE
    path.write_text(json.dumps({"version": 1, "profiles": {
        "company-black-venture-farm": {"website": "https://example.test/custom-portfolio"}},
        "history": [{"note": "PRIVATE HISTORY MARKER"}]}), encoding="utf-8")
    before = path.read_bytes()
    client = TestClient(main.app)
    page = client.get("/varieties/coverage?q=Black+Venture")
    assert page.status_code == 200 and "https://example.test/custom-portfolio" in page.text
    assert "PRIVATE HISTORY MARKER" not in page.text
    assert "Article text coverage" in page.text and "1269 saved sources" in page.text
    assert "excluding pending news" in page.text
    assert 'href="/source-fidelity"' in page.text
    assert path.read_bytes() == before and list(tmp_path.iterdir()) == [path]
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    public = client.get("/varieties/coverage")
    assert public.status_code == 200 and "https://example.test/custom-portfolio" not in public.text
    assert "Article text coverage" not in public.text and "portfolio-ucdavis" not in public.text


def test_candidate_provenance_links_keep_portfolio_and_individual_page_separate(monkeypatch, tmp_path):
    from html.parser import HTMLParser
    class Links(HTMLParser):
        def __init__(self):
            super().__init__()
            self.href, self.text, self.links = None, [], {}

        def handle_starttag(self, tag, attrs):
            if tag == "a":
                self.href, self.text = dict(attrs).get("href"), []

        def handle_data(self, data):
            if self.href is not None:
                self.text.append(data)

        def handle_endtag(self, tag):
            if tag == "a" and self.href is not None:
                self.links["".join(self.text).strip()] = self.href
                self.href = None

    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    response = TestClient(main.app).get("/varieties/candidates?q=UCD+Royal+Royce&berry=berry-strawberry")
    assert response.status_code == 200
    parser = Links()
    parser.feed(response.text)
    links = parser.links
    assert links["UC Davis — current strawberry release list ↗"] == "https://strawberry.ucdavis.edu/released-varieties"
    assert links["UC Davis — historical strawberry timeline ↗"] == "https://strawberry.ucdavis.edu/breeding-timeline"
    assert links["Variety page ↗"] == "https://strawberry.ucdavis.edu/ucd-royal-royce"
    assert not list(tmp_path.rglob("*"))
