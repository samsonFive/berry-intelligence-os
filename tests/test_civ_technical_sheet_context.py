"""Read sheet headings without converting trade labels or comparisons to facts."""
from copy import deepcopy
from pathlib import Path

from fastapi.testclient import TestClient
from app import main
from app.services.variety_portfolio_coverage import load_portfolio_observations, reconcile_portfolios

DATA = Path(__file__).resolve().parents[1] / "data"
PAIRS = {"CIVN223": "ANNELY", "CIVL514": "ARDEA", "CIVRH295": "EDWINA", "CIVN251": "QUICKY"}


def sheets():
    return [row for row in load_portfolio_observations(DATA) if row["id"].startswith("portfolio-civ-sheet-")]


def test_partial_and_failed_sheet_attempts_retain_index_leads_and_capture_limits():
    observed = sheets()
    assert len(observed) == 11 and sum(len(s["names"]) for s in observed) == 9
    assert sum(s["capture_status"] == "names_enumerated" for s in observed) == 7
    assert {s["id"] for s in observed if s["capture_status"] == "partial"} == {
        "portfolio-civ-sheet-edwina", "portfolio-civ-sheet-kamila"}
    assert {s["id"] for s in observed if s["capture_status"] == "unreadable"} == {
        "portfolio-civ-sheet-antea", "portfolio-civ-sheet-flaminia"}
    index = next(s for s in load_portfolio_observations(DATA) if s["id"] == "portfolio-civ-other-index")
    assert len(index["names"]) == 11 and not index["capture_reference"]["linked_pdf_bodies_checked"]
    assert all(not n.get("breeder_code") for n in index["names"])
    for s in observed:
        assert s["url"] in {n["product_url"] for n in index["names"]}
        assert not s.get("published_date")
        if s["capture_status"] != "names_enumerated":
            assert not s["capture_reference"]["body_checked"] and "accounting" not in s
        if s["capture_status"] == "unreadable":
            assert not s["names"] and "pages" not in s["capture_reference"]
    edwina = next(s for s in observed if s["id"].endswith("edwina"))
    assert edwina["capture_reference"]["method"] == "primary_pdf_text"
    assert "not independently visually verified" in edwina["limitations"]
    kamila = next(s for s in observed if s["id"].endswith("kamila"))
    assert "lower body/footer" in kamila["limitations"]


def test_literal_code_pairs_remain_separate_unreviewed_leads_without_photo_or_rights_promotion():
    observed = sheets()
    index = next(s for s in load_portfolio_observations(DATA) if s["id"] == "portfolio-civ-other-index")
    _, candidates = reconcile_portfolios(sources=[index, *observed], varieties=[], entities=[], candidates=[])
    named = {c["candidate_name"]: c for c in candidates}
    assert len(named) == 15  # Eleven index labels plus four separate code leads.
    for code, label in PAIRS.items():
        candidate = named[code]
        assert candidate["breeder_code"] == code and candidate["trade_name"] == label
        assert candidate["id"] != named[label]["id"]
        assert candidate["portfolio_identity_notes"] and named[label]["portfolio_identity_notes"]
        assert any("without it in another" in note for note in candidate["portfolio_identity_notes"])
    quicky = named["CIVN251"]["portfolio_sources"][0]
    assert quicky["product_url"] == "https://civ.it/wp-content/uploads/2025/02/Quicky%C2%AECIVN251_ITA.pdf"
    for candidate in candidates:
        assert candidate["status"] == "proposed" and not candidate["human_gated"] and not candidate["auto_confirmed"]
        assert not candidate["aliases"] and not candidate["proposed_relationships"]
        assert not candidate["breeder_owner"] and not candidate["deployment"]
        assert not candidate["registration"]["official_registry_source"]
        assert not any(candidate["registration"][key] for key in (
            "application_number", "grant_number", "status", "application_date", "grant_date", "expiry"))
        assert all(not ref.get("photos") for ref in candidate["portfolio_sources"])
    assert all(not n.get("breeder_code") for s in observed for n in s["names"] if n["candidate_name"] not in PAIRS)


def test_comparisons_are_accounted_but_never_extra_own_portfolio_observations():
    observed = sheets()
    original = deepcopy(observed)
    rows, candidates = reconcile_portfolios(sources=observed, varieties=[], entities=[], candidates=[])
    excluded = [e["label"] for s in observed for e in s.get("accounting", {}).get("exclusions", [])]
    assert sorted(excluded) == sorted(["Clery", "Clery", "Varietà 1", "Marmolada® onebor*", "Galiaciv"])
    assert not set(excluded) & {c["candidate_name"] for c in candidates}
    assert all(not s["accounting_view"]["issues"] for s in rows if s["capture_status"] == "names_enumerated")
    assert observed == original


def test_sheet_replay_and_private_get_preserve_analyst_decisions_and_user_edits(monkeypatch, tmp_path):
    observed = sheets()
    human = {"id": "human-quicky", "candidate_name": "CIVN251", "berry_id": "berry-strawberry",
             "status": "rejected", "identity_state": "rejected", "human_gated": True,
             "reviewer": "Analyst", "review_notes": "Retain my decision", "knowledge": {"notes": "My note"},
             "photos": [{"user_edit": "retained"}]}
    original = deepcopy(human)
    _, candidates = reconcile_portfolios(sources=observed, varieties=[], entities=[], candidates=[human])
    saved = next(c for c in candidates if c["id"] == human["id"])
    for key in ("status", "identity_state", "human_gated", "reviewer", "review_notes", "knowledge", "photos"):
        assert saved[key] == human[key]
    assert human == original
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    page = TestClient(main.app).get('/varieties/candidates', params={
        "source": "portfolio-civ-sheet-quicky", "q": "CIVN251", "berry": "berry-strawberry"})
    assert page.status_code == 200 and "CIVN251" in page.text and "QUICKY" in page.text
    assert "Check names before combining" in page.text
    assert quicky_url_in_html(page.text)
    assert not list(tmp_path.rglob('*.json'))


def quicky_url_in_html(html):
    return 'https://civ.it/wp-content/uploads/2025/02/Quicky%C2%AECIVN251_ITA.pdf' in html
