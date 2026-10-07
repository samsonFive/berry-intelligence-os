from copy import deepcopy
from datetime import date, timedelta
import re

import pytest
from fastapi.testclient import TestClient

from app import main
from app.services import company_directory, variety_photos as photos
from app.services.variety_portfolio_coverage import load_portfolio_observations


def photo(**changes):
    return {"image_url": "https://images.example.test/keepsake.jpg", "source_url": "https://example.test/keepsake",
            "credit": "Photographer · Publisher", "caption": "Keepsake strawberries in a trial",
            "named_variety": "Keepsake", "berry_id": "berry-strawberry", "reuse": "public_domain",
            "license_url": "https://example.test/photo-terms", "reuse_note": "Publisher explicitly permits reuse of this photo with credit",
            "checked_on": date.today().isoformat(), "kind": "fruit", **changes}


def variety(berry="berry-strawberry"):
    return {"id": "variety-keepsake", "name": "Keepsake", "berry_ids": [berry], "entity_type": "variety"}


def source(value=None):
    return [{"names": [{"candidate_name": "Keepsake", "berry_id": "berry-strawberry", "photos": [value or photo()]}]}]


def test_same_name_different_berry_is_never_a_photo_match():
    assert photos.source_photos(variety("berry-blueberry"), sources=source()) == []
    assert len(photos.source_photos(variety(), sources=source())) == 1
    candidate = {"id": "vcand-keepsake", "candidate_name": "Keepsake", "berry_id": "berry-blueberry",
                 "portfolio_sources": source()[0]["names"]}
    assert photos.source_photos(candidate, candidate=True) == []
    candidate["berry_ids"] = ["berry-blueberry", "berry-strawberry"]
    assert not photos.compatible(photo(), candidate, candidate=True)


def test_ambiguous_catalog_match_does_not_choose_a_profile():
    first = variety()
    second = {**variety(), "id": "variety-keepsake-2"}
    assert photos.source_photos(first, sources=source(), varieties=[first, second]) == []
    assert photos.source_photos(first, sources=source(), varieties=[first])


def test_private_gallery_is_read_only_and_never_public(monkeypatch, tmp_path):
    original = variety()
    sourced = photos.source_photos(original, sources=source())
    before = deepcopy(sourced)
    assert photos.gallery(original, sourced=sourced, authoring=False) == []
    assert photos.gallery(original, sourced=sourced, authoring=True)[0]["display_image"]
    assert sourced == before and not list(tmp_path.iterdir())
    # The template also refuses private content accidentally supplied by a caller.
    html = main.templates.env.get_template("_variety_photo_gallery.html").render(
        photo_gallery=photos.gallery(original, sourced=sourced, authoring=True), authoring_mode=True, static_build=True)
    assert "<img" not in html and "Photographer" not in html


def test_unknown_reuse_keeps_source_and_credit_without_inline_image():
    sourced = photos.source_photos(variety(), sources=source(photo(reuse="unknown", license_url="", reuse_note="")))
    gallery = photos.gallery(variety(), sourced=sourced, authoring=True)
    assert not gallery[0]["display_image"]
    html = main.templates.env.get_template("_variety_photo_gallery.html").render(
        photo_gallery=gallery, authoring_mode=True, static_build=False)
    assert "<img" not in html and "Photo source" in html and "Photographer" in html


@pytest.mark.parametrize("changes", [{"image_url": "javascript:alert(1)"}, {"image_url": "http://127.0.0.1/private"},
    {"source_url": "https://user:password@example.test/"}, {"license_url": "file:///secret"}, {"credit": ""},
    {"named_variety": ""}, {"reuse_note": ""}, {"license_url": ""}, {"kind": "logo"},
    {"checked_on": "bad-date"}, {"checked_on": (date.today() + timedelta(days=1)).isoformat()}])
def test_photo_requires_safe_attributed_dated_reuse(changes):
    with pytest.raises(ValueError):
        photos.validate_photo(photo(**changes))


def test_correction_hide_and_restore_survive_refreshed_sources(tmp_path):
    target = variety()
    sourced = photos.source_photos(target, sources=source())
    key = sourced[0]["id"]
    photos.edit(tmp_path, target=target, sourced=sourced, payload={**photo(credit="Corrected photographer"),
                "action": "save", "photo_id": key, "revision": "0"}, reviewer="Analyst")
    profile = company_directory.load_profiles(tmp_path)["profiles"][target["id"]]
    refreshed = photos.source_photos(target, sources=source(photo(credit="Refreshed publisher")))
    assert photos.gallery(target, sourced=refreshed, profile=profile, authoring=True)[0]["credit"] == "Corrected photographer"
    photos.edit(tmp_path, target=target, sourced=refreshed, payload={"action": "remove", "photo_id": key, "revision": "1"})
    profile = company_directory.load_profiles(tmp_path)["profiles"][target["id"]]
    assert photos.gallery(target, sourced=refreshed, profile=profile, authoring=True) == []
    photos.edit(tmp_path, target=target, sourced=refreshed, payload={"action": "restore", "photo_id": key, "revision": "2"})
    profile = company_directory.load_profiles(tmp_path)["profiles"][target["id"]]
    assert photos.gallery(target, sourced=refreshed, profile=profile, authoring=True)[0]["credit"] == "Corrected photographer"
    photos.edit(tmp_path, target=target, sourced=refreshed, payload={"action": "reset", "photo_id": key, "revision": "3"})
    state = company_directory.load_profiles(tmp_path)
    assert photos.gallery(target, sourced=refreshed, profile=state["profiles"][target["id"]], authoring=True)[0]["credit"] == "Refreshed publisher"
    assert len(state["history"]) == 4 and state["history"][0]["reviewer"] == "Analyst"
    assert target == variety()


def test_custom_photo_restore_and_concurrent_edit_preserve_other_profile_fields(tmp_path):
    company_directory.edit_profile(tmp_path, entity_id=variety()["id"], payload={"revision": "0", "website": "https://example.test", "socials": ""})
    photos.edit(tmp_path, target=variety(), payload={**photo(), "action": "save", "revision": "1"})
    state = company_directory.load_profiles(tmp_path)
    key = next(iter(state["profiles"][variety()["id"]]["variety_photo_overrides"]))
    with pytest.raises(ValueError, match="changed in another"):
        photos.edit(tmp_path, target=variety(), payload={"action": "remove", "photo_id": key, "revision": "1"})
    photos.edit(tmp_path, target=variety(), payload={"action": "remove", "photo_id": key, "revision": "2"})
    photos.edit(tmp_path, target=variety(), payload={"action": "restore", "photo_id": key, "revision": "3"})
    state = company_directory.load_profiles(tmp_path)
    assert state["profiles"][variety()["id"]]["website"] == "https://example.test"
    assert photos.gallery(variety(), profile=state["profiles"][variety()["id"]], authoring=True)[0]["image_url"] == photo()["image_url"]


def test_invalid_photo_does_not_replace_private_history(tmp_path):
    photos.edit(tmp_path, target=variety(), payload={**photo(), "action": "save", "revision": "0"})
    before = (tmp_path / company_directory.PROFILE_FILE).read_bytes()
    with pytest.raises(ValueError, match="match this variety"):
        photos.edit(tmp_path, target=variety(), payload={**photo(berry_id="berry-blueberry"), "action": "save", "revision": "1"})
    assert (tmp_path / company_directory.PROFILE_FILE).read_bytes() == before


def test_photo_editor_auth_edit_guard_and_existing_target(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "variety_candidate_universe", lambda: ([variety()], [], {}))
    client = TestClient(main.app)
    url = "/varieties/photos/catalog/variety-keepsake"
    page = client.get(url)
    assert page.status_code == 200 and not list(tmp_path.iterdir())
    berry_select = re.search(r'<select name="berry_id">(.*?)</select>', page.text, re.S).group(1)
    assert 'value="berry-strawberry"' in berry_select and 'value="berry-blueberry"' not in berry_select
    assert client.post(url, data={**photo(), "action": "save", "revision": "0"}, headers={"Origin": "https://evil.test"}).status_code == 403
    assert client.post(url, data={**photo(), "action": "save", "revision": "0"}, follow_redirects=False).status_code == 303
    assert client.post(url, data={**photo(), "action": "save", "revision": "0"}).status_code == 409
    assert client.get("/varieties/photos/catalog/missing").status_code == 404
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    assert client.get(url).status_code == 403
    assert client.post(url, data={}).status_code == 403


def test_photo_credits_are_escaped_in_gallery():
    sourced = photos.source_photos(variety(), sources=source(photo(credit='<script>bad()</script>')))
    html = main.templates.env.get_template("_variety_photo_gallery.html").render(
        photo_gallery=photos.gallery(variety(), sourced=sourced, authoring=True), authoring_mode=True)
    assert "<script>" not in html and "&lt;script&gt;" in html


def test_catalog_profile_and_directory_share_private_photo_and_readonly_hides_it(monkeypatch, tmp_path):
    target = next(row for row in main.all_entities() if row["id"] == "variety-keepsake")
    photos.edit(tmp_path, target=target, payload={**photo(berry_id="berry-blueberry", caption="Photo labeled Keepsake blueberry"),
                "action": "save", "revision": "0"})
    before = (tmp_path / company_directory.PROFILE_FILE).read_bytes()
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    client = TestClient(main.app)
    profile = client.get("/entities/variety/variety-keepsake")
    directory = client.get("/entities/variety?berry=berry-blueberry&q=Keepsake")
    assert profile.status_code == directory.status_code == 200
    assert 'aria-label="Variety photos"' in profile.text and "Photographer" in profile.text
    assert 'class="variety-photo-thumb"' in directory.text and photo()["image_url"] in directory.text
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    assert photo()["image_url"] not in client.get("/entities/variety/variety-keepsake").text
    assert photo()["image_url"] not in client.get("/entities/variety?berry=berry-blueberry&q=Keepsake").text
    assert (tmp_path / company_directory.PROFILE_FILE).read_bytes() == before


def test_real_source_photo_has_caption_credit_license_and_does_not_approve_identity():
    sources = load_portfolio_observations(main.DATA_DIR)
    source = next(row for row in sources if row["id"] == "portfolio-usda-corvallis-fy2022")
    assert source["names"][0]["photos"][0]["named_variety"] == "Columbia Star"
    assert "Chad Finn" in source["names"][0]["photos"][0]["credit"]
    assert "unavailable" in source["names"][0]["photos"][0]["reuse_note"]
    from app.services.variety_portfolio_coverage import reconcile_portfolios
    _, candidates = reconcile_portfolios(sources=[source], varieties=[], entities=[], candidates=[])
    assert len(candidates) == 7 and not candidates[0]["human_gated"]
    assert not candidates[0]["auto_confirmed"]
    assert photos.source_photos(candidates[0], candidate=True)
