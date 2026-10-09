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
    return [{"id": "photo-source", "company_ids": [], "names": [{"candidate_name": "Keepsake", "berry_id": "berry-strawberry", "photos": [value or photo()]}]}]


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


def test_shared_source_label_with_different_codes_is_held_even_with_one_catalog_match():
    sources = source()
    sources[0]["names"][0].update(breeder_code="ABC123", trade_name="Keepsake")
    sources.append({"id": "second-source", "company_ids": [], "names": [
        {"candidate_name": "Keepsake", "trade_name": "Keepsake", "breeder_code": "XYZ456", "berry_id": "berry-strawberry"}]})
    assert photos.source_photos(variety(), sources=sources, varieties=[variety()]) == []


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
    assert 'data-photo-session' in html and 'Ignore permission' in html
    assert 'data-image-url="https://images.example.test/keepsake.jpg"' in html
    assert 'Permission unconfirmed' in html and '<form' not in html


def test_session_controls_and_held_photos_never_enter_readonly_or_static():
    sourced = photos.source_photos(variety(), sources=source(photo(reuse="unknown")))
    gallery = photos.gallery(variety(), sourced=sourced, authoring=True)
    template = main.templates.env.get_template("_variety_photo_gallery.html")
    for context in ({"authoring_mode": False}, {"authoring_mode": True, "static_build": True}):
        html = template.render(photo_gallery=gallery, **context)
        assert 'Ignore permission' not in html and photo()['image_url'] not in html


def test_original_public_program_fruit_figures_stay_session_only_and_cultivar_specific():
    from pathlib import Path
    sources = [row for row in load_portfolio_observations(Path(__file__).resolve().parents[1] / "data")
               if row["id"].startswith("portfolio-public-program-grant-")]
    template = main.templates.env.get_template("_variety_photo_gallery.html")
    assert sum(len(row["names"][0].get("photos", [])) for row in sources) == 2
    for source_row in sources:
        observation = source_row["names"][0]
        if not observation.get("photos"):
            continue
        target = {"id": "fixture-candidate", "candidate_name": observation["candidate_name"],
                  "berry_id": "berry-blackberry", "portfolio_sources": [observation]}
        sourced = photos.source_photos(target, candidate=True)
        assert len(sourced) == 1 and sourced[0]["reuse"] == "unknown" and not sourced[0]["license_url"]
        assert "Photographer not credited" in sourced[0]["credit"]
        gallery = photos.gallery(target, sourced=sourced, authoring=True)
        assert not gallery[0]["display_image"]
        private = template.render(photo_gallery=gallery, authoring_mode=True, static_build=False)
        assert "Ignore permission" in private and "<img" not in private
        for context in ({"authoring_mode": False}, {"authoring_mode": True, "static_build": True}):
            public = template.render(photo_gallery=gallery, **context)
            assert sourced[0]["image_url"] not in public and "Ignore permission" not in public
        assert photos.source_photos({**target, "berry_id": "berry-blueberry"}, candidate=True) == []


def test_session_script_loads_only_the_chosen_asset_and_never_persists_permission():
    from pathlib import Path
    import shutil
    import subprocess
    node = shutil.which('node')
    if not node:
        pytest.skip('Node runtime unavailable for session-script behavior test')
    result = subprocess.run([node, str(Path(__file__).with_name('variety_photo_session_checks.js'))],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr


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
    before = (tmp_path / company_directory.PROFILE_FILE).read_bytes()
    with pytest.raises(ValueError, match="no source version"):
        photos.edit(tmp_path, target=variety(), payload={"action": "reset", "photo_id": key, "revision": "2"})
    assert (tmp_path / company_directory.PROFILE_FILE).read_bytes() == before
    assert not photos.gallery(variety(), profile=state["profiles"][variety()["id"]], authoring=True)[0]["has_source"]
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


def test_berryum_product_photos_remain_held_and_brand_does_not_become_breeder():
    from app.services.variety_portfolio_coverage import reconcile_portfolios
    source = next(s for s in load_portfolio_observations(main.DATA_DIR)
                  if s['id'] == 'portfolio-berryum-blackberry-products')
    assert source['company_ids'] == ['brand-berryum']
    assert source['berry_ids'] == ['berry-blackberry']
    rows, candidates = reconcile_portfolios(sources=[source], varieties=[], entities=[], candidates=[])
    assert len(candidates) == 6 and rows[0]['accounting_view']['accounted_items'] == 7
    assert rows[0]['accounting_view']['exclusions'][0]['label'] == 'LOCH NESS'
    assert not any(c['proposed_relationships'] or c['human_gated'] or c['auto_confirmed'] for c in candidates)
    for candidate in candidates:
        sourced = photos.source_photos(candidate, candidate=True)
        assert len(sourced) == 1 and sourced[0]['reuse'] == 'unknown'
        assert sourced[0]['source_url'] == candidate['portfolio_sources'][0]['product_url']
        assert sourced[0]['named_variety'] == candidate['trade_name']
        assert 'Photographer not credited' in sourced[0]['credit']
        assert 'written consent' in sourced[0]['reuse_note']
        gallery = photos.gallery(candidate, sourced=sourced, authoring=True)
        assert not gallery[0]['display_image']


def test_real_held_photo_controls_render_privately_without_file_or_permission_writes(monkeypatch, tmp_path):
    monkeypatch.setattr(main, 'INBOX_DIR', tmp_path)
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    client = TestClient(main.app)
    page = client.get('/varieties/candidates?q=Furia&berry=berry-blackberry')
    assert page.status_code == 200 and 'Ignore permission' in page.text
    assert 'Berryneo / BerrYum' in page.text and 'Permission unconfirmed' in page.text
    image = 'https://www.berryneo.com/wp-content/uploads/2021/05/moras_berryum_furia2.png'
    assert f'data-image-url="{image}"' in page.text and f'src="{image}"' not in page.text
    assert not list(tmp_path.rglob('*'))
    monkeypatch.setattr(main, 'AUTHORING_MODE', False)
    public = client.get('/varieties/candidates?q=Furia&berry=berry-blackberry')
    assert image not in public.text and 'Ignore permission' not in public.text


def test_editor_return_preserves_candidate_scope_through_saved_redirect(monkeypatch, tmp_path):
    from urllib.parse import parse_qs, urlencode, urlsplit
    from app.variety_photo_routes import photo_return
    target = {'id': 'vcand-keepsake', 'candidate_name': 'Keepsake', 'berry_id': 'berry-strawberry'}
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    monkeypatch.setattr(main, 'INBOX_DIR', tmp_path)
    monkeypatch.setattr(main, 'variety_candidate_universe', lambda: ([], [target], {}))
    back = '/varieties/candidates?q=Keepsake&berry=berry-strawberry&letter=K#vcand-keepsake'
    url = '/varieties/photos/candidate/vcand-keepsake?' + urlencode({'return_to': back})
    client = TestClient(main.app)
    page = client.get(url)
    assert page.status_code == 200 and back.replace('&', '&amp;') in page.text
    assert not list(tmp_path.iterdir())
    saved = client.post(url, data={**photo(), 'action': 'save', 'revision': '0'}, follow_redirects=False)
    assert saved.status_code == 303
    assert parse_qs(urlsplit(saved.headers['location']).query)['return_to'] == [back]
    assert back.replace('&', '&amp;') in client.get(saved.headers['location']).text
    for unsafe in ('https://evil.test/varieties/candidates', '//evil.test/varieties/candidates', '/today', '/entities/variety/other', 'https://[invalid'):
        assert photo_return('candidate', target['id'], unsafe) == '/varieties/candidates#vcand-keepsake'
