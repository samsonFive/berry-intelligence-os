"""Large source inventories defer detail without losing scope or review gates."""
from copy import deepcopy
from html import unescape
import re
from pathlib import Path
import shutil
import subprocess

from fastapi.testclient import TestClient
import pytest

from app import main


def test_large_inventory_keeps_every_row_but_defers_closed_bodies(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    client = TestClient(main.app)
    page = client.get("/varieties/coverage?profile_q=Rutgers&external_status=")
    assert page.status_code == 200
    coverage = page.context["coverage"]
    sources = coverage["portfolios"]["sources"]
    assert len(sources) >= 522 and coverage["defer_portfolio_details"]
    assert len(re.findall(r' data-portfolio-source>', page.text)) == len(sources)
    assert all('id="portfolio-source-' + row["id"] + '"' in page.text for row in sources)
    assert 'data-portfolio-source-content' not in page.text
    assert 'variety_coverage_sources.js?v=1' in page.text
    inline_context = {**page.context, "coverage": {**coverage, "defer_portfolio_details": False}}
    inline = main.templates.env.get_template("variety_coverage.html").render(**inline_context)
    assert len(page.content) < len(inline.encode()) * 0.65
    links = re.findall(r'data-portfolio-source-link href="([^"]+)"', page.text)
    assert len(links) == len(sources) and all("profile_q=Rutgers" in link for link in links)
    detail = client.get(unescape(links[0]))
    assert detail.status_code == 200 and sources[0]["title"] in detail.text
    assert "Open primary source" in detail.text and "What we checked" in detail.text
    assert "Back to coverage" in detail.text and "#portfolio-source-" + sources[0]["id"] in detail.text
    assert "profile_q=Rutgers" in detail.text and "variety_coverage_sources.js" not in detail.text
    fragment = client.get(unescape(links[0]) + "&fragment=1")
    assert fragment.status_code == 200 and 'data-portfolio-source-content' in fragment.text
    assert "<html" not in fragment.text and "glass-header" not in fragment.text
    assert fragment.headers["x-berry-portfolio-fragment"] == "1"
    assert "no-store" in fragment.headers["cache-control"] and "Cookie" in fragment.headers["vary"]
    assert list(tmp_path.rglob("*.json")) == []


@pytest.fixture
def source_scope(monkeypatch, tmp_path):
    from app.services import variety_portfolio_coverage as portfolio
    source = {"id": "fixture-source", "title": "Original breeder page", "url": "https://example.test/source",
              "checked_on": "2026-10-07", "capture_status": "names_enumerated", "source_type": "breeder_catalog",
              "review_state": "unreviewed", "company_ids": ["company-a"], "berry_ids": ["berry-blueberry"],
              "enumerated_scope": "One named blueberry", "limitations": "This is not the complete portfolio",
              "review_warnings": ["Printed identity needs checking"],
              "names": [{"candidate_name": "Alpha", "berry_id": "berry-blueberry"}]}
    varieties = [{"id": "variety-alpha", "name": "Alpha", "berry_ids": ["berry-blueberry"], "entity_type": "variety"}]
    candidate = {"id": "human-alpha", "candidate_name": "Alpha", "berry_id": "berry-blueberry", "status": "rejected",
                 "human_gated": True, "identity_state": "rejected", "review_notes": "Human edit must survive"}
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    monkeypatch.setattr(main, "variety_candidate_universe", lambda: (varieties, [candidate], {}))
    monkeypatch.setattr(main, "all_entities", lambda: varieties + [{"id": "company-a", "name": "Breeder", "entity_type": "company"}])
    monkeypatch.setattr(portfolio, "load_portfolio_observations", lambda _: [source])
    return source, varieties, candidate, tmp_path


def test_details_respect_current_human_decisions_edits_and_scope_without_writes(source_scope):
    source, varieties, candidate, tmp_path = source_scope
    before = deepcopy((source, varieties, candidate))
    client = TestClient(main.app)
    page = client.get("/varieties/coverage/source/fixture-source?fragment=1&berry=berry-blueberry&company=company-a")
    assert page.status_code == 200 and "Previously rejected" in page.text
    assert "Printed identity needs checking" in page.text and "Source context and limits" in page.text
    assert "This is not the complete portfolio" in page.text and "data-status=\"catalog_match\"" not in page.text
    assert (source, varieties, candidate) == before
    candidate.update(status="reviewed", identity_state="confirmed_same", candidate_canonical_match="variety-alpha")
    page = client.get("/varieties/coverage/source/fixture-source?fragment=1")
    assert page.status_code == 200 and 'href="/entities/variety/variety-alpha"' in page.text
    source["names"][0]["candidate_name"] = "Later edit"
    assert "Later edit" in client.get("/varieties/coverage/source/fixture-source?fragment=1").text
    for scope in ("berry=berry-raspberry", "company=company-b", "q=Other"):
        assert client.get("/varieties/coverage/source/fixture-source?fragment=1&" + scope).status_code == 404
    assert client.get("/varieties/coverage/source/fixture-source?berry=invalid").status_code == 422
    assert client.get("/varieties/coverage/source/not-saved").status_code == 404
    assert not list(tmp_path.rglob("*.json"))


def test_private_source_endpoint_fails_closed_before_loading_records(monkeypatch):
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    monkeypatch.setattr(main, "variety_candidate_universe", lambda: pytest.fail("public request loaded private source data"))
    for suffix in ("", "?fragment=1"):
        response = TestClient(main.app).get("/varieties/coverage/source/private-source" + suffix)
        assert response.status_code == 403 and "data-portfolio-source-content" not in response.text


def test_unreadable_source_is_not_presented_as_zero_varieties(source_scope):
    source, _varieties, _candidate, _tmp_path = source_scope
    source.update(capture_status="unreadable", names=[])
    response = TestClient(main.app).get("/varieties/coverage/source/fixture-source")
    assert response.status_code == 200 and "Variety names have not been checked" in response.text
    assert "0 name occurrences" not in response.text


def test_remote_anonymous_requests_do_not_reach_source_records(monkeypatch, tmp_path):
    monkeypatch.setenv("BIOS_REMOTE_INTERACTIVE", "true")
    monkeypatch.setenv("BIOS_REVIEW_USERNAME", "fixture-source-login")
    monkeypatch.setenv("BIOS_REVIEW_PASSWORD", "fixture-only")
    monkeypatch.setenv("BIOS_SESSION_SECRET", "fixture-source-login-secret-at-least-32-characters")
    monkeypatch.delenv("BIOS_BASIC_AUTH", raising=False)
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    monkeypatch.setattr(main, "variety_candidate_universe", lambda: pytest.fail("anonymous request loaded private data"))
    response = TestClient(main.app, follow_redirects=False).get("/varieties/coverage/source/private-source?fragment=1")
    assert response.status_code == 302 and response.headers["location"].startswith("/login?")
    assert "x-berry-portfolio-fragment" not in response.headers


def test_source_disclosures_load_retry_and_keep_native_fallbacks():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is needed for the source-disclosure contract")
    subprocess.run([node, str(Path(__file__).with_name("coverage_source_details_checks.js"))],
                   check=True, capture_output=True, text=True)
