"""Stored photo leads stay visible without crossing identity or reuse gates."""
from copy import deepcopy
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.services.variety_photo_review import photo_identity_reviews
from app.services.variety_photos import gallery, source_photos
from app.services.variety_portfolio_coverage import load_portfolio_observations


def inputs():
    root = Path(__file__).resolve().parents[1] / 'data'
    varieties = [json.loads(p.read_text(encoding='utf-8')) for p in (root/'entities/varieties').glob('*.json')]
    target = next(v for v in varieties if v['id'] == 'variety-rutgers-dlight')
    sources = load_portfolio_observations(root)
    sources = [s for s in sources if s['id'] in {'portfolio-rutgers-original-grant-nj09-2-1', 'portfolio-named-photo-cohort-rutgers-dlight'}]
    return target, sources, varieties


def test_actual_rutgers_photo_lead_has_review_and_source_links_but_no_image_or_identity_promotion():
    target, sources, varieties = inputs(); before = deepcopy((target, sources, varieties))
    assert source_photos(target, sources=sources, varieties=varieties) == []
    notes = photo_identity_reviews(target, sources=sources, varieties=varieties)
    assert len(notes) == 1 and notes[0]['named_variety'] == "Rutgers D'Light"
    assert notes[0]['source_url'].startswith('https://sebsnjaesnews.rutgers.edu/')
    assert 'q=Rutgers+D%27Light' in notes[0]['review_href'] and 'berry=berry-strawberry' in notes[0]['review_href']
    assert any('code in one source' in n for n in notes[0]['review_notes'])
    assert not any('image_url' in n or 'display_image' in n for n in notes)
    assert gallery(target, sourced=source_photos(target, sources=sources, varieties=varieties), authoring=True) == []
    assert (target, sources, varieties) == before


def test_eligible_photos_or_user_hiding_are_not_misreported_as_identity_holds():
    target, sources, varieties = inputs()
    sources = [s for s in sources if s['id'].startswith('portfolio-named-photo-')]
    eligible = source_photos(target, sources=sources, varieties=varieties)
    assert len(eligible) == 1 and not photo_identity_reviews(target, sources=sources, varieties=varieties, sourced=eligible)
    assert not gallery(target, sourced=eligible, profile={'variety_photo_overrides': {eligible[0]['id']: None}}, authoring=True)
    assert not photo_identity_reviews(target, sources=sources, varieties=varieties, sourced=eligible)
    # A different crop is not a photo lead, even with the same literal name.
    assert not photo_identity_reviews({**target, 'berry_ids': ['berry-blueberry']}, sources=sources, varieties=varieties)


def test_ambiguous_catalog_name_reports_a_hold_without_choosing_a_profile():
    target, sources, _ = inputs()
    sources = [s for s in sources if s['id'].startswith('portfolio-named-photo-')]
    other = {**target, 'id': 'fixture-distinct-same-label'}
    assert source_photos(target, sources=sources, varieties=[target, other]) == []
    notes = photo_identity_reviews(target, sources=sources, varieties=[target, other])
    assert len(notes) == 1 and any('more than one catalog entry' in n for n in notes[0]['review_notes'])


def test_source_review_notes_are_defensively_absent_outside_private_authoring():
    template = main.templates.env.get_template('_variety_photo_identity_reviews.html')
    notes = [{'named_variety': 'PRIVATE PHOTO LEAD', 'source_url': 'https://example.test/private-photo-source',
              'review_href': '/varieties/candidates?source=private', 'review_notes': ['PRIVATE IDENTITY NOTE']}]
    for authoring, static in [(False, False), (False, True), (True, True)]:
        assert not template.render(photo_identity_reviews=notes, authoring_mode=authoring, static_build=static).strip()
    html = template.render(photo_identity_reviews=notes, authoring_mode=True, static_build=False)
    assert 'Photo found' in html and 'Review name match' in html and '<img' not in html
    assert ' open' not in html.split('<details', 1)[1].split('>', 1)[0]


def test_actual_profile_coverage_and_candidate_handoffs_are_read_only(monkeypatch, tmp_path):
    monkeypatch.setattr(main, 'INBOX_DIR', tmp_path)
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    target, sources, varieties = inputs()
    before = deepcopy((target, sources, varieties))
    client = TestClient(main.app)
    profile = client.get('/entities/variety/variety-rutgers-dlight')
    assert profile.status_code == 200 and 'Photo found · name match needs review' in profile.text
    assert 'data-photo-session' not in profile.text
    legacy = client.get('/entities/variety/variety-rutgers-dlight?view=legacy')
    editor = client.get('/varieties/photos/catalog/variety-rutgers-dlight')
    for response in [legacy, editor]:
        assert response.status_code == 200 and 'Photo found · name match needs review' in response.text
        assert 'data-photo-session' not in response.text
    assert 'Add credited photo' in editor.text
    directory = client.get('/entities/variety?q=Rutgers&berry=berry-strawberry')
    assert directory.status_code == 200 and 'Photo match review' in directory.text
    table = client.get('/varieties/coverage?profile_q=Rutgers&profile_gap=photos')
    assert table.status_code == 200 and 'Name match needs review' in table.text
    assert '1 without linked photos' in table.text
    href = photo_identity_reviews(target, sources=sources, varieties=varieties)[0]['review_href']
    handoff = client.get(href)
    assert handoff.status_code == 200 and 'NJ09-2-1' in handoff.text
    assert not list(tmp_path.rglob('*.json')) and (target, sources, varieties) == before
    monkeypatch.setattr(main, 'AUTHORING_MODE', False)
    readonly = client.get('/entities/variety/variety-rutgers-dlight')
    assert readonly.status_code == 200 and 'Photo found · name match needs review' not in readonly.text
