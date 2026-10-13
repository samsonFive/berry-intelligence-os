"""Company lists and named photos do not approve identities or growing claims."""
from copy import deepcopy
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.services import variety_photos as photos
from app.services.variety_portfolio_coverage import load_portfolio_observations, reconcile_portfolios

DATA = Path(__file__).resolve().parents[1] / "data"


def observations():
    return [source for source in load_portfolio_observations(DATA) if source["id"] in {
        "portfolio-asd-victoria-names", "portfolio-asd-queensland-names",
        "portfolio-benning-history-name-check", "portfolio-inkas-matias-product",
        "portfolio-inkas-salvador-product"}]


def test_literal_names_repeated_context_and_nonbreeder_claims_stay_separate():
    sources = observations()
    original = deepcopy(sources)
    rows, candidates = reconcile_portfolios(sources=sources, varieties=[], entities=[], candidates=[])
    asd = [row for row in rows if row["id"].startswith("portfolio-asd-")]
    assert sum(len(row["names"]) for row in asd) == 10
    assert {name["candidate_name"] for row in asd for name in row["names"]} == {
        "Albion", "Peteluma", "Grenada", "Cabrillo", "Fontarias", "Red Rhapsody",
        "Sundrench", "Parisienne Kiss", "Scarlet Rose"}
    red = next(row for row in candidates if row["candidate_name"] == "Red Rhapsody")
    assert {ref["id"] for ref in red["portfolio_sources"]} == {
        "portfolio-asd-victoria-names", "portfolio-asd-queensland-names"}
    assert not photos.source_photos(red, candidate=True)
    assert all(not photos.source_photos(row, candidate=True) for row in candidates
               if row["source_id"].startswith("portfolio-asd-"))
    assert all(row["source_tier"] == "weak_noncanonical_lead" for row in candidates
               if row["source_id"].startswith("portfolio-asd-"))
    benning = next(row for row in rows if row["id"] == "portfolio-benning-history-name-check")
    assert not benning["names"] and "not zero varieties" in benning["limitations"]
    assert not any(row["source_id"] == benning["id"] for row in candidates)
    for row in candidates:
        assert row["status"] == "proposed" and not row["human_gated"] and not row["auto_confirmed"]
        assert not row["aliases"] and not row["breeder_owner"] and not row["deployment"]
        assert not row["proposed_relationships"] and not row["registration"]["official_registry_source"]
        assert not any(row["registration"][field] for field in (
            "application_number", "grant_number", "application_date", "grant_date", "status", "expiry"))
    assert sources == original


def test_labeled_product_images_are_held_and_generic_background_is_excluded():
    sources = observations()
    original = deepcopy(sources)
    _, candidates = reconcile_portfolios(sources=sources, varieties=[], entities=[], candidates=[])
    for name in ["Matías", "Salvador"]:
        target = next(row for row in candidates if row["candidate_name"] == name)
        gallery = photos.gallery(target, sourced=photos.source_photos(target, candidate=True), authoring=True)
        assert len(gallery) == 1
        image = gallery[0]
        assert image["named_variety"] == name and image["berry_id"] == "berry-blueberry"
        assert image["source_url"] == target["portfolio_sources"][0]["product_url"]
        assert "ar_2" not in image["image_url"] and image["kind"] == "fruit"
        assert "Photographer not credited" in image["credit"]
        assert image["reuse"] == "unknown" and not image["display_image"] and not image["license_url"]
        assert not photos.gallery(target, sourced=gallery, authoring=False)
    assert sources == original


def test_product_source_preview_get_never_loads_images_or_writes_review_state(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    client = TestClient(main.app)
    for source in observations():
        for name in source["names"]:
            for photo in name.get("photos", []):
                response = client.get("/varieties/candidates", params={
                    "source": source["id"], "berry": "berry-blueberry", "q": name["candidate_name"]})
                assert response.status_code == 200
                assert 'data-image-url="' + photo["image_url"] + '"' in response.text
                assert 'src="' + photo["image_url"] + '"' not in response.text
                assert "Ignore permission" in response.text and "Permission unconfirmed" in response.text
    assert not list(tmp_path.rglob("*.json"))
