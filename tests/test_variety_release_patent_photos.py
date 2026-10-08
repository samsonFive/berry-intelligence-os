"""Real named photos remain source-labeled, private and crop-specific."""
from copy import deepcopy
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.services import variety_photos as photos
from app.services.variety_portfolio_coverage import load_portfolio_observations, reconcile_portfolios

DATA = Path(__file__).resolve().parents[1] / "data"


def sources():
    return [row for row in load_portfolio_observations(DATA) if row["id"] in {
        "portfolio-usda-keepsake-2019-news", "portfolio-fc11-164-patent-figure1"}]


def catalog(name):
    return json.loads((DATA / "entities/varieties" / (name + ".json")).read_text(encoding="utf-8"))


def test_strawberry_release_photos_never_attach_to_blueberry_keepsake():
    release = next(row for row in sources() if row["id"] == "portfolio-usda-keepsake-2019-news")
    blueberry = catalog("variety-keepsake")
    assert photos.source_photos(blueberry, sources=[release], varieties=[blueberry]) == []
    rows, candidates = reconcile_portfolios(sources=[release], varieties=[blueberry], entities=[], candidates=[])
    assert rows[0]["matched"] == 0 and rows[0]["accounting_view"]["accounted_items"] == 6
    assert {row["candidate_name"] for row in candidates} == {"Keepsake", "Flavorfest"}
    candidate = next(row for row in candidates if row["candidate_name"] == "Keepsake")
    assert candidate["berry_id"] == "berry-strawberry" and not candidate["candidate_canonical_match"]
    gallery = photos.gallery(candidate, sourced=photos.source_photos(candidate, candidate=True), authoring=True)
    assert len(gallery) == 2 and all(row["reuse"] == "unknown" and not row["display_image"] for row in gallery)
    assert all("Photographer not credited" in row["credit"] for row in gallery)
    assert all("Sharon Durham" not in row["credit"] and "Kim Lewers" not in row["credit"] for row in gallery)
    for row in candidates:
        assert not row["aliases"] and not row["human_gated"] and not row["auto_confirmed"]
        assert not row["proposed_relationships"] and not row["registration"]["official_registry_source"]


def test_patent_figure_is_exact_code_photo_without_identity_or_rights_approval():
    source = next(row for row in sources() if row["id"] == "portfolio-fc11-164-patent-figure1")
    target = catalog("variety-fc11-164")
    before = deepcopy(target)
    sourced = photos.source_photos(target, sources=[source], varieties=[target])
    assert len(sourced) == 1 and sourced[0]["named_variety"] == "FC11-164"
    assert "/1f/ee/15/" in sourced[0]["image_url"]  # Verified full-resolution asset, not the thumbnail.
    assert "grayscale" in sourced[0]["caption"] and "July 30, 2020" in sourced[0]["caption"]
    assert "USPP34903P2" in sourced[0]["credit"] and sourced[0]["reuse"] == "unknown"
    assert not photos.gallery(target, sourced=sourced, authoring=True)[0]["display_image"]
    assert photos.gallery(target, sourced=sourced, authoring=False) == []
    rows, candidates = reconcile_portfolios(sources=[source], varieties=[target], entities=[], candidates=[])
    assert rows[0]["matched"] == 1 and candidates == []
    assert target == before and target["status"] == "unverified"
    assert "Everlast" not in target["aliases"]


def test_live_photo_sources_and_controls_are_private_no_get_writes(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    client = TestClient(main.app)
    release = next(row for row in sources() if row["id"] == "portfolio-usda-keepsake-2019-news")
    patent = next(row for row in sources() if row["id"] == "portfolio-fc11-164-patent-figure1")
    strawberry = client.get("/varieties/candidates?source=portfolio-usda-keepsake-2019-news&berry=berry-strawberry&q=Keepsake")
    blueberry = client.get("/entities/variety/variety-keepsake")
    profile = client.get("/entities/variety/variety-fc11-164")
    assert strawberry.status_code == blueberry.status_code == profile.status_code == 200
    assert "A different berry uses this name" in strawberry.text
    assert "Open catalog record" not in strawberry.text
    for photo in release["names"][0]["photos"]:
        assert photo["image_url"] in strawberry.text and photo["image_url"] not in blueberry.text
        assert 'src="' + photo["image_url"] + '"' not in strawberry.text
    image = patent["names"][0]["photos"][0]["image_url"]
    assert image in profile.text and 'src="' + image + '"' not in profile.text
    assert "Ignore permission" in profile.text and "Permission unconfirmed" in profile.text
    assert "USPP34903P2 patent document" in profile.text and "Edit variety photos" in profile.text
    assert list(tmp_path.rglob("*.json")) == []
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    assert image not in client.get("/entities/variety/variety-fc11-164").text
    assert client.get("/varieties/candidates?source=portfolio-usda-keepsake-2019-news").status_code == 403
    assert list(tmp_path.rglob("*.json")) == []


def test_patent_photo_personal_hide_survives_source_reload(tmp_path):
    source = next(row for row in sources() if row["id"] == "portfolio-fc11-164-patent-figure1")
    target = catalog("variety-fc11-164")
    sourced = photos.source_photos(target, sources=[source], varieties=[target])
    original = deepcopy(source)
    profile = photos.edit(tmp_path, target=target, sourced=sourced,
                         payload={"action": "remove", "photo_id": sourced[0]["id"], "revision": "0"})
    assert photos.gallery(target, sourced=sourced, profile=profile, authoring=True) == []
    refreshed = photos.source_photos(target, sources=sources(), varieties=[target])
    assert photos.gallery(target, sourced=refreshed, profile=profile, authoring=True) == []
    assert source == original and sourced[0]["reuse"] == "unknown"
