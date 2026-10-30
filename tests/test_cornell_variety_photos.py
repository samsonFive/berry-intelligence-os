"""Source-specific photos retain crop, identity, user edits and publication gates."""
from copy import deepcopy
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.services import variety_photos as photos
from app.services.variety_portfolio_coverage import load_portfolio_observations
from app.services.variety_profile_coverage import profile_field_coverage

DATA = Path(__file__).resolve().parents[1] / "data"


def records(folder):
    return [json.loads(path.read_text(encoding="utf-8"))
            for path in sorted((DATA / folder).rglob("*.json"))]


def photo_sources():
    return [source for source in load_portfolio_observations(DATA)
            if source["id"].startswith("portfolio-cornell-photo-")]


def test_cornell_photos_fill_four_named_profile_gaps_without_other_field_changes():
    entities = records("entities")
    varieties = [row for row in entities if row.get("entity_type") == "variety"]
    sources = load_portfolio_observations(DATA)
    before = deepcopy(sources)
    kwargs = dict(varieties=varieties, entities=entities, relationships=records("relationships"),
                  published_evidence=records("evidence"), facts=records("facts"))
    baseline = profile_field_coverage(**kwargs, portfolio_sources=[
        source for source in sources if not source["id"].startswith("portfolio-cornell-photo-")])
    corrected = profile_field_coverage(**kwargs, portfolio_sources=sources)
    assert baseline["catalog_total"] == corrected["catalog_total"] == len(varieties)
    # Dickens now has an admitted identity alongside the original three profiles.
    assert baseline["missing_counts"]["photos"] - corrected["missing_counts"]["photos"] == 4
    assert {key: count for key, count in baseline["missing_counts"].items() if key != "photos"} == {
        key: count for key, count in corrected["missing_counts"].items() if key != "photos"}
    baseline_rows = {row["id"]: row for row in baseline["rows"]}
    changed = []
    for row in corrected["rows"]:
        old = baseline_rows[row["id"]]
        if row["photos"] != old["photos"]:
            changed.append(row["name"])
            assert row["photos"] == row["held_photos"] == 1
        assert {key: value for key, value in row.items() if key not in {"photos", "held_photos", "missing"}} == {
            key: value for key, value in old.items() if key not in {"photos", "held_photos", "missing"}}
    assert set(changed) == {"Crimson Night", "Crimson Treasure", "Double Gold", "Dickens"}
    assert sources == before


def test_caption_identity_never_borrows_a_nearby_or_other_crop_photo():
    sources = photo_sources()
    assert len(sources) == 4
    varieties = records("entities/varieties")
    target = next(row for row in varieties if row["id"] == "variety-crimson-night")
    selected = photos.source_photos(target, sources=sources, varieties=varieties)
    assert len(selected) == 1 and selected[0]["image_url"].endswith("/CrimsonNight.jpg")
    assert "Courtney Weber" in selected[0]["credit"]
    assert selected[0]["license_url"] == "https://news.cornell.edu/about/copyright"
    assert "permission" in selected[0]["reuse_note"].lower()
    for source in sources:
        assert source["capture_reference"]["visually_reviewed"]
        assert not source["capture_reference"]["image_downloaded"]
        assert not source["capture_reference"]["whole_page_name_enumeration"]
        assert source["checked_on"] != source["published_date"]
        ref = source["names"][0]
        candidate = {"id": "vcand-test", "candidate_name": ref["candidate_name"],
                     "berry_id": ref["berry_id"], "portfolio_sources": [ref]}
        gallery = photos.gallery(candidate, sourced=photos.source_photos(candidate, candidate=True), authoring=True)
        assert len(gallery) == 1 and gallery[0]["reuse"] == "unknown"
        assert not gallery[0]["display_image"]
        candidate["berry_id"] = "berry-blueberry"
        assert photos.source_photos(candidate, candidate=True) == []
    dickens = next(source["names"][0] for source in sources
                   if source["id"] == "portfolio-cornell-photo-dickens")
    # Source association remains crop-specific after Dickens identity admission.
    dickens_profile = next(row for row in varieties if row["name"] == "Dickens")
    assert dickens_profile["status"] == "unverified" and dickens_profile["berry_ids"] == ["berry-strawberry"]
    assert dickens["berry_id"] == "berry-strawberry"


def test_cornell_photo_hide_survives_rediscovery_without_permission_change(tmp_path):
    target = next(row for row in records("entities/varieties") if row["id"] == "variety-double-gold")
    sourced = photos.source_photos(target, sources=photo_sources(), varieties=[target])
    profile = photos.edit(tmp_path, target=target, sourced=sourced,
                         payload={"action": "remove", "photo_id": sourced[0]["id"], "revision": "0"})
    refreshed = photos.source_photos(target, sources=load_portfolio_observations(DATA), varieties=[target])
    assert photos.gallery(target, sourced=refreshed, profile=profile, authoring=True) == []
    assert sourced[0]["reuse"] == refreshed[0]["reuse"] == "unknown"


def test_cornell_photo_routes_are_private_readonly_and_initially_withheld(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    client = TestClient(main.app)
    response = client.get("/entities/variety/variety-crimson-night")
    image = "https://news.cornell.edu/sites/chronicle.cornell/files/CrimsonNight.jpg"
    assert response.status_code == 200
    assert image in response.text and 'src="' + image + '"' not in response.text
    assert "Courtney Weber" in response.text and "Ignore permission" in response.text
    assert "Permission unconfirmed" in response.text and "Edit variety photos" in response.text
    target = next(row for row in main.living_catalog() if row.get("entity_type") == "variety" and row["name"] == "Dickens" and row.get("berry_ids") == ["berry-strawberry"])
    candidate = client.get("/entities/variety/" + target["id"])
    dickens = next(row["names"][0]["photos"][0] for row in photo_sources()
                   if row["id"] == "portfolio-cornell-photo-dickens")
    assert candidate.status_code == 200 and dickens["image_url"] in candidate.text
    assert 'src="' + dickens["image_url"] + '"' not in candidate.text
    assert "Permission unconfirmed" in candidate.text and "Ignore permission" in candidate.text
    assert not list(tmp_path.rglob("*.json"))
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    assert image not in client.get("/entities/variety/variety-crimson-night").text
    assert client.get("/varieties/candidates?source=portfolio-cornell-photo-dickens").status_code == 403
    gallery = photos.gallery({"id": "test", "name": "Dickens", "berry_ids": ["berry-strawberry"]},
                            sourced=photos.source_photos({"id": "test", "name": "Dickens", "berry_ids": ["berry-strawberry"]},
                                                        sources=photo_sources()), authoring=True)
    html = main.templates.env.get_template("_variety_photo_gallery.html").render(
        photo_gallery=gallery, authoring_mode=True, static_build=True)
    assert dickens["image_url"] not in html and "Ignore permission" not in html
    assert not list(tmp_path.rglob("*.json"))
