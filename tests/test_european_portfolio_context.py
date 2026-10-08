"""Current breeder lists retain scope and images without bypassing review."""
from copy import deepcopy
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.services import variety_photos as photos
from app.services.variety_portfolio_coverage import load_portfolio_observations, reconcile_portfolios

DATA = Path(__file__).resolve().parents[1] / "data"
IDS = {
    "portfolio-civ-everbearing-index", "portfolio-civ-high-chill-index",
    "portfolio-civ-low-chill-index", "portfolio-civ-other-index",
    "portfolio-hansabred-cultivars-index", "portfolio-nsg-current-hub",
}


def sources():
    return [row for row in load_portfolio_observations(DATA) if row["id"] in IDS]


def test_bounded_index_counts_exclude_other_scopes_and_keep_links_literal():
    observed = sources()
    original = deepcopy(observed)
    rows, candidates = reconcile_portfolios(sources=observed, varieties=[], entities=[], candidates=[])
    assert len(rows) == 6 and sum(len(row["names"]) for row in rows) == 40
    civ = [row for row in rows if row["id"].startswith("portfolio-civ-")]
    assert sorted(len(row["names"]) for row in civ) == [4, 6, 8, 11]
    assert all(not row["accounting_view"]["issues"] for row in rows)
    other = next(row for row in civ if row["id"] == "portfolio-civ-other-index")
    assert not other["capture_reference"]["linked_pdf_bodies_checked"]
    assert all(not name.get("breeder_code") and not name.get("denomination") for name in other["names"])
    quicky = next(name for name in other["names"] if name["candidate_name"] == "QUICKY")
    assert quicky["product_url"] == "https://civ.it/wp-content/uploads/2025/02/Quicky%C2%AECIVN251_ITA.pdf"
    hans = next(row for row in rows if row["id"] == "portfolio-hansabred-cultivars-index")
    assert len(hans["names"]) == 6
    fontaine = next(name for name in hans["names"] if name["candidate_name"] == "Fontaine")
    assert "Fragaria iinumae" in fontaine["portfolio_context"] and "ornamental" in fontaine["portfolio_context"]
    assert not {"Elsanta", "Malling Centenary", "P-120279", "Flair", "Elegance", "Pineberrry"} & {
        name["candidate_name"] for name in hans["names"]}
    nsg = next(row for row in rows if row["id"] == "portfolio-nsg-current-hub")
    assert len(nsg["names"]) == 5
    assert {name.get("breeder_code") for name in nsg["names"]} == {None, "NSG 203", "NSG 207", "NSG 465", "NSG 48"}
    assert all(name["product_url"] for row in rows for name in row["names"])
    assert all(not row.get("published_date") for row in rows)
    assert observed == original


def test_source_pairing_and_photos_never_approve_aliases_roles_or_rights():
    observed = sources()
    _, candidates = reconcile_portfolios(sources=observed, varieties=[], entities=[], candidates=[])
    assert len(candidates) == 40
    for candidate in candidates:
        assert candidate["status"] == "proposed" and not candidate["human_gated"] and not candidate["auto_confirmed"]
        assert not candidate["aliases"] and not candidate["proposed_relationships"]
        assert not candidate["breeder_owner"] and not candidate["deployment"]
        assert not candidate["registration"]["official_registry_source"]
        assert not any(candidate["registration"][key] for key in (
            "application_number", "grant_number", "status", "application_date", "grant_date", "expiry"))
    held = [photo for candidate in candidates for photo in photos.source_photos(candidate, candidate=True)]
    assert len(held) == 4
    assert {photo["named_variety"] for photo in held} == {"CIVH725", "Renaissance", "NSG 207"}
    assert all(photo["reuse"] == "unknown" and not photo["license_url"] for photo in held)
    assert all("Photographer not credited" in photo["credit"] for photo in held)
    assert not any("fragola-header-def" in photo["image_url"] for photo in held)
    for candidate in candidates:
        assert not photos.gallery(candidate, sourced=photos.source_photos(candidate, candidate=True), authoring=False)


def test_import_replay_preserves_real_human_rejection_and_user_photo_edits():
    observed = sources()
    human = {"id": "human-renaissance", "candidate_name": "Renaissance", "berry_id": "berry-strawberry",
             "status": "rejected", "identity_state": "rejected", "human_gated": True,
             "reviewer": "Analyst", "review_notes": "Keep the prior decision", "knowledge": {"notes": "User note"},
             "photos": [{"user_edit": "retained"}]}
    original = deepcopy(human)
    _, candidates = reconcile_portfolios(sources=observed, varieties=[], entities=[], candidates=[human])
    saved = next(row for row in candidates if row["id"] == human["id"])
    assert saved["status"] == "rejected" and saved["human_gated"]
    assert saved["review_notes"] == human["review_notes"] and saved["knowledge"] == human["knowledge"]
    assert saved["photos"] == human["photos"] and human == original


def test_photo_preview_get_has_no_image_load_or_state_writes(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    client = TestClient(main.app)
    for source in sources():
        for name in source["names"]:
            if not name.get("photos"):
                continue
            page = client.get("/varieties/candidates", params={"source": source["id"], "q": name["candidate_name"], "berry": "berry-strawberry"})
            assert page.status_code == 200
            assert "Ignore permission" in page.text and "Permission unconfirmed" in page.text
            for photo in name["photos"]:
                assert 'data-image-url="' + photo["image_url"] + '"' in page.text
                assert 'src="' + photo["image_url"] + '"' not in page.text
    assert not list(tmp_path.rglob("*.json"))
