"""Original filing access never establishes rights or reverses identity review."""
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main
from app.services.variety_patent_references import original_patent_references
from app.services.variety_portfolio_coverage import load_portfolio_observations, reconcile_portfolios


VARIETY = {"id": "v1", "entity_type": "variety", "name": "Named", "aliases": ["Code-1"], "berry_ids": ["berry-blueberry"]}


def source(**extra):
    return {"id": "original-filing", "title": "Named original filing", "url": "https://example.test/patent",
            "company_ids": [], "berry_ids": ["berry-blueberry"], "checked_on": "2026-10-09",
            "source_type": "plant_patent", "capture_status": "names_enumerated", "limitations": "Historical filing only",
            "names": [{"candidate_name": "Named", "berry_id": "berry-blueberry", "grant_number": "USPP12345P2",
                       "grant_date": "2020-01-02", "product_url": "https://example.test/original.pdf#page=3"}],
            "capture_reference": {"claim_url": "https://example.test/patent#claims", "figures_url": "https://example.test/original.pdf#page=5"}, **extra}


def refs(sources, candidates=(), varieties=()):
    return original_patent_references(variety=VARIETY, varieties=[VARIETY, *varieties], entities=[],
                                      candidates=list(candidates), sources=sources)


def test_original_links_keep_historical_dates_and_unreviewed_scope_without_writes():
    sources = [source()]
    before = deepcopy(sources)
    view = refs(sources)
    assert len(view) == 1 and view[0]["published_date"] == "2020-01-02"
    assert view[0]["document_url"].endswith("#page=3") and view[0]["figures_url"].endswith("#page=5")
    assert view[0]["claim_url"].endswith("#claims") and view[0]["context"] == "Historical filing only"
    assert not {"legal_status", "owner", "current_rights", "trusted", "photo_permission"} & view[0].keys()
    assert sources == before


@pytest.mark.parametrize("state,status", [("distinct", "reviewed"), ("rejected", "rejected")])
def test_exact_name_cannot_override_a_saved_human_distinct_or_rejection(state, status):
    candidate = {"id": "human-candidate", "candidate_name": "Named", "berry_id": "berry-blueberry",
                 "human_gated": True, "identity_state": state, "status": status, "review_notes": "Keep my decision"}
    before = deepcopy(candidate)
    rows, saved = reconcile_portfolios(sources=[source()], varieties=[VARIETY], entities=[], candidates=[candidate])
    assert rows[0]["names"][0]["catalog_id"] is None
    assert rows[0]["names"][0]["status"] == ("distinct_awaiting_catalog" if state == "distinct" else "previously_rejected")
    assert saved[0]["id"] == "human-candidate" and saved[0]["review_notes"] == before["review_notes"]
    assert refs([source()], [candidate]) == [] and candidate == before


def test_human_same_decision_uses_existing_canonical_id_without_autocreating_records():
    row = source(names=[{"candidate_name": "Other label", "berry_id": "berry-blueberry"}])
    candidate = {"id": "human-same", "candidate_name": "Other label", "berry_id": "berry-blueberry", "human_gated": True,
                 "identity_state": "confirmed_same", "status": "reviewed", "candidate_canonical_match": VARIETY["id"]}
    assert len(refs([row], [candidate])) == 1
    candidate["candidate_canonical_match"] = "not-in-catalog"
    assert refs([row], [candidate]) == []


def test_ambiguous_names_wrong_crops_and_cross_source_code_conflicts_stay_unlinked():
    duplicate = {**VARIETY, "id": "v2"}
    assert refs([source()], varieties=[duplicate]) == []
    assert refs([source(names=[{"candidate_name": "Named", "berry_id": "berry-strawberry"}])]) == []
    grant = source(names=[{"candidate_name": "Named", "berry_id": "berry-blueberry", "breeder_code": "Code-1"}])
    other = source(id="other-source", source_type="nursery_catalog",
                   names=[{"candidate_name": "Named", "berry_id": "berry-blueberry", "breeder_code": "Code-2"}])
    assert refs([grant, other]) == []


def test_unsafe_urls_are_not_links_and_a_profile_alone_is_not_a_filing():
    bad = source(url="javascript:alert(1)")
    assert refs([bad]) == []
    row = source(capture_reference={"claim_url": "https://user:password@example.test/claim", "figures_url": "file:///private"},
                 names=[{"candidate_name": "Named", "berry_id": "berry-blueberry", "product_url": "javascript:alert(1)"}])
    result = refs([row])[0]
    assert not result["claim_url"] and not result["document_url"] and not result["figures_url"]
    assert refs([source(source_type="university_cultivar_profile")]) == []


def test_profile_lookup_does_not_reconcile_unrelated_catalogs(monkeypatch):
    from app.services import variety_portfolio_coverage
    original = variety_portfolio_coverage.resolve_identity
    looked_up = []

    def tracked(query, varieties):
        looked_up.append(query["candidate_name"])
        return original(query, varieties)

    monkeypatch.setattr(variety_portfolio_coverage, "resolve_identity", tracked)
    unrelated = source(id="other-catalog", source_type="nursery_catalog",
                       names=[{"candidate_name": "Unrelated", "berry_id": "berry-blueberry"}])
    assert len(refs([source(), unrelated])) == 1
    assert looked_up == ["Named"]


def test_profile_private_filing_links_and_both_recorded_number_fields_have_separate_visibility(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    client = TestClient(main.app)
    for suffix in ("", "?view=legacy"):
        html = client.get("/entities/variety/variety-colossus" + suffix).text
        assert "PP33,802" in html and "Recorded reference · current rights not verified." in html
        assert "Original filing references" in html and "Unreviewed reference" in html
        assert "https://patents.google.com/patent/USPP33802P3/en#claims" in html
        assert "USPP33802.pdf#page=5" in html
        assert "no patent number recorded" not in html
        rights = html.split('id="rights"', 1)[1].split('</dl>', 1)[0]
        assert '/entities/breeding_program/breeding_program-uf-ifas-blueberry-breeding' in rights
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    public = client.get("/entities/variety/variety-colossus").text
    assert "PP33,802" in public and "Original filing references" not in public
    assert "USPP33802.pdf#page=5" not in public
    assert not list(tmp_path.rglob("*.json"))


def test_original_colossus_document_accounts_for_parents_and_comparisons_without_approving_them():
    sources = load_portfolio_observations(Path(__file__).resolve().parents[1] / "data")
    source_row = next(s for s in sources if s["id"] == "portfolio-uf-original-grant-colossus")
    assert len(source_row["names"]) == 1 and source_row["names"][0]["breeder_code"] == "FL11-35"
    assert {x["label"] for x in source_row["accounting"]["exclusions"]} == {"FL08-35", "FL04-103", "FL07-399", "Emerald"}
    assert source_row["accounting"]["observed_items"] == 5
    assert source_row["capture_reference"]["visually_reviewed_pages"] == [1, 3, 5, 6]
    assert not source_row["capture_reference"]["current_legal_status_verified"]
    assert not source_row["capture_reference"]["reuse_permission_verified"]
    assert not source_row["names"][0].get("photos")
