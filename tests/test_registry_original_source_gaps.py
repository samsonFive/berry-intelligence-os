"""Ambiguous labels and missing websites remain gaps, not cultivar approvals."""
from copy import deepcopy
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.services.variety_portfolio_coverage import (
    load_portfolio_observations, portfolio_coverage, reconcile_portfolios,
)

DATA = Path(__file__).resolve().parents[1] / "data"
PREFIX = "portfolio-registry-original-gap-"


def sources():
    return [s for s in load_portfolio_observations(DATA) if s["id"].startswith(PREFIX)]


def test_readable_brands_inputs_and_unreachable_site_do_not_become_varieties():
    rows, candidates = reconcile_portfolios(
        sources=sources(), varieties=[], entities=[], candidates=[])
    assert len(rows) == 11 and candidates == []
    assert sum(s["capture_status"] == "partial" for s in rows) == 10
    assert sum(s["capture_status"] == "unreadable" for s in rows) == 1
    assert all(s["needs_follow_up"] and not s["names"] for s in rows)
    assert all(not s["accounting_view"]["issues"] for s in rows)
    labels = {x["label"] for s in rows for x in s["accounting"]["exclusions"]}
    assert labels >= {"Rouge", "Blanc", "BLOOOM", "BIOGROW3", "Nitro Aire",
                      "Mira Valle", "Ojo Zarco", "Eureka Blueberries",
                      "Marvelus Strawberries", "Fruitist Jumbo", "Sekoya"}
    unreachable = next(s for s in rows if s["id"].endswith("grupoheres-dns"))
    assert unreachable["berry_ids"] == []
    assert unreachable["url"] == "https://www.grupoheres.com.mx/"
    assert unreachable["capture_reference"]["outcome"] == "net::ERR_NAME_NOT_RESOLVED"
    assert "unknown, not an empty portfolio" in unreachable["limitations"]


def test_original_dates_crop_content_and_existing_company_identity_are_preserved():
    rows = sources()
    launch = next(s for s in rows if s["id"].endswith("singrow-launch"))
    assert launch["published_date"] == "2023-02-02"
    assert all(not s.get("published_date") for s in rows if s != launch)
    assert "February 22, 2023" in next(s for s in rows if s["id"].endswith("singrow-media"))["limitations"]
    strawberry = next(s for s in rows if s["id"].endswith("biogea-strawberry-trial"))
    assert strawberry["url"] == "https://www.biogea.mx/en/frambuesa-jalisco"
    assert strawberry["berry_ids"] == ["berry-strawberry"]
    assert "trial period" in strawberry["limitations"].lower()
    fruitist = [s for s in rows if "fruitist-" in s["id"]]
    assert len(fruitist) == 2
    assert all(s["company_ids"] == ["company-agrovision"] for s in fruitist)
    historical = next(s for s in fruitist if s["id"].endswith("2022"))
    assert "not a publication date" in historical["limitations"]
    assert "not obtained" in historical["enumerated_scope"]
    assert all(len(s["capture_reference"]["capture_sha256"]) == 64
               for s in rows if s["capture_status"] != "unreadable")


def test_new_gap_sources_keep_existing_candidate_anchors_and_human_fields():
    all_sources = load_portfolio_observations(DATA)
    human = dict(id="operator-gap-review", candidate_name="Private user selection",
                 berry_id="berry-strawberry", human_gated=True, status="reviewed",
                 identity_state="distinct", aliases=["User spelling"],
                 review_notes="Keep private notes", registration={"status": "User status"},
                 photos=[{"operator": "Keep photo"}])
    before = deepcopy(human)
    _, old = reconcile_portfolios(
        sources=[s for s in all_sources if not s["id"].startswith(PREFIX)],
        varieties=[], entities=[], candidates=[human])
    _, new = reconcile_portfolios(
        sources=all_sources, varieties=[], entities=[], candidates=[human])
    assert len(new) == len(old)
    assert {(c["berry_id"], c["candidate_name"], c["id"]) for c in new} == {
        (c["berry_id"], c["candidate_name"], c["id"]) for c in old}
    saved = next(c for c in new if c["id"] == human["id"])
    assert all(saved[k] == before[k] for k in before)
    assert human == before


def test_partial_pages_do_not_close_registry_name_enumeration_gaps():
    report = portfolio_coverage(data_dir=DATA, sources=sources(), varieties=[],
                                entities=[], candidates=[])
    subjects = [s for s in report["subjects"] if s["sources"]]
    assert len(subjects) >= 5
    assert all(not s["checked"] and s["has_source_gaps"] for s in subjects)
    assert report["summary"]["registry_entries_checked"] == 0
    assert report["summary"]["follow_up_sections"] == 11
    assert report["summary"]["names"] == report["summary"]["needs_review"] == 0
    assert not report["visible_candidates"]


def test_live_source_gaps_show_originals_without_writes_or_public_review_leaks(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    client = TestClient(main.app)
    page = client.get("/varieties/coverage", params={"company": "company-biogea"})
    assert page.status_code == 200
    assert "We haven’t captured variety names in these pages" in page.text
    assert "Partial source check · named-variety coverage remains" in page.text
    assert 'href="https://www.biogea.mx/en/frambuesa-jalisco"' in page.text
    assert "BIOGROW3" in page.text and "Ojo Zarco" in page.text
    assert "Partial variety coverage" in page.text
    assert "Review these source names" not in page.text
    assert "Ignore permission" not in page.text
    assert not list(tmp_path.rglob("*.json"))
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    public = client.get("/varieties/coverage", params={"company": "company-biogea"})
    assert public.status_code == 200
    assert PREFIX not in public.text and "BIOGROW3" not in public.text
    assert not list(tmp_path.rglob("*.json"))
