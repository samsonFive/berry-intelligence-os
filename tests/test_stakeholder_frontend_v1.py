"""Stakeholder presentation layer — shell, search rank, and demo surfaces."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.services.global_search import SearchPools, search_global
from app.services.stakeholder_ui import compose_stakeholder_front, humanize_label


def test_humanize_role_and_identity_slugs() -> None:
    assert humanize_label("genetics_licensor") == "Genetics licensor"
    assert humanize_label("no_canonical_identity_match") == "Needs a human name decision"
    assert humanize_label("") == ""


def test_compose_front_uses_trusted_when_top_stories_empty() -> None:
    trusted = {"id": "ev-1", "title": "Trusted item", "trust_label": "REVIEWED EVIDENCE"}
    composed = compose_stakeholder_front(
        {
            "top_stories": [],
            "sections": [{"key": "trusted_intelligence", "rows": [trusted]}],
            "worth_revisiting": [],
        }
    )
    assert composed["lead"]["id"] == "ev-1"
    assert composed["using_fallback"] is True
    assert composed["freshness_note"]


def test_stakeholder_today_has_slim_nav_not_ops_chrome() -> None:
    page = TestClient(app).get("/today")
    assert page.status_code == 200
    html = page.text
    assert 'class="sh-nav' in html
    assert ">Today<" in html
    assert ">Companies<" in html
    assert ">Markets<" in html
    assert ">Watchlist<" in html
    assert ">Reports<" in html
    assert "stakeholder.css" in html
    assert "v2-count-action" not in html
    assert "Publication Review" not in html
    assert "Collection Operations" not in html
    assert "Coverage Assurance" not in html
    assert "Morning Brief" not in html
    assert "elapsed_ms" not in html
    assert "All berries" in html
    assert "Blueberry" in html
    assert "Raspberry" in html


def test_search_planasa_company_is_first_and_hides_latency() -> None:
    page = TestClient(app).get("/search", params={"q": "Planasa"})
    assert page.status_code == 200
    html = page.text
    assert " ms" not in html.split("result")[0]
    assert "elapsed_ms" not in html
    companies = html.split('data-search-group="companies"')[1].split("data-search-group=")[0]
    first_title = companies.split('sh-search-title')[1]
    assert "Planasa" in first_title or "Plantas de Navarra" in first_title


def test_search_newest_undated_entities_keep_exact_match_first() -> None:
    pools = SearchPools(
        entities=[
            {
                "id": "company-abb",
                "record_type": "entity",
                "entity_type": "company",
                "name": "ABB",
                "status": "active",
                "aliases": [],
                "description": "Investor note mentioning Planasa",
            },
            {
                "id": "company-planasa",
                "record_type": "entity",
                "entity_type": "company",
                "name": "Planasa",
                "status": "active",
                "aliases": ["Plantas de Navarra"],
                "description": "",
            },
        ]
    )
    payload = search_global("Planasa", pools, include_private=False, sort="newest")
    group = next(g for g in payload["groups"] if g["id"] == "companies")
    titles = [row["title"] for row in group["in_context"]]
    assert titles[0] == "Planasa"


def test_company_page_humanizes_roles() -> None:
    page = TestClient(app).get("/entities/company/company-planasa")
    assert page.status_code == 200
    html = page.text
    assert "genetics_licensor" not in html
    assert "What changed" in html
    assert "v2-company" in html
    assert 'class="sh-page' in html


def test_reports_empty_has_primary_build_action() -> None:
    page = TestClient(app).get("/reports")
    assert page.status_code == 200
    assert "Build a report" in page.text
    assert "Blueberry genetics in Europe" in page.text
    builder = TestClient(app).get("/reports/new")
    assert builder.status_code == 200
    assert "What do you want to understand?" in builder.text
    assert "Interpret request" not in builder.text


def test_analyst_shell_still_has_work_nav() -> None:
    page = TestClient(app).get("/brief")
    assert page.status_code == 200
    assert 'class="v2-nav-group">Work</p>' in page.text
    assert "Live Intelligence" in page.text
