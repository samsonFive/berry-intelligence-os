"""Larger originals never reset identity, permission, user edits or hiding."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from app import main
from app.services import company_directory, variety_photos as photos
from app.services.variety_photo_previews import read_preview_overlays
from app.services.variety_portfolio_coverage import _source_fingerprint, load_portfolio_observations

DATA = Path(__file__).resolve().parents[1] / 'data'
FOLDER = 'variety-portfolio-observations-2026-10-28-full-image-previews'


def fixture():
    photo = dict(image_url='https://example.test/figure-small.png', source_url='https://example.test/filing',
                 credit='Document publisher; photographer not credited', caption='Named fruit figure',
                 named_variety='One', berry_id='berry-raspberry', reuse='unknown', license_url='',
                 reuse_note='Permission not established', checked_on='2026-10-28', kind='drawing')
    source = dict(id='fixture-source', title='Original filing', url='https://example.test/filing',
                  checked_on='2026-10-28', company_ids=[], berry_ids=['berry-raspberry'],
                  source_type='plant_patent', enumerated_scope='One named figure', limitations='Historical reference',
                  capture_status='names_enumerated', review_state='unreviewed', review_warnings=['Check this entry'],
                  names=[dict(candidate_name='One', berry_id='berry-raspberry', photos=[photo])])
    overlay = dict(source_id=source['id'], source_fingerprint=_source_fingerprint(source), candidate_name='One',
                   berry_id='berry-raspberry', image_url=photo['image_url'],
                   preview_image_url='https://example.test/figure-full.png',
                   preview_caption='Full-size original named fruit figure', checked_on='2026-10-28')
    target = dict(id='fixture-one', name='One', entity_type='variety', berry_ids=['berry-raspberry'])
    return source, overlay, target


def write_fixture(root, source, overlay, *, warning=True):
    path = root / 'imports/variety-portfolio-observations-fixture/observations.json'
    path.parent.mkdir(parents=True)
    payload = dict(kind='unreviewed_portfolio_name_observations', sources=[source], photo_preview_overlays=[overlay])
    if warning:
        payload['warning_scope_overlays'] = [dict(source_id=source['id'], source_fingerprint=_source_fingerprint(source),
             review_warning_scopes=[dict(message='Check this entry', candidate_names=['One'])])]
    path.write_text(json.dumps(payload), encoding='utf-8')
    return path


def test_larger_preview_and_scoped_warning_preserve_capture_and_stable_photo_identity(tmp_path):
    source, overlay, target = fixture(); before = deepcopy(source)
    path = write_fixture(tmp_path, source, overlay); original = path.read_bytes()
    first = load_portfolio_observations(tmp_path); second = load_portfolio_observations(tmp_path)
    assert first == second and path.read_bytes() == original and source == before
    assert first[0]['review_warning_scopes'][0]['candidate_names'] == ['One']
    copy = deepcopy(first[0]); del copy['review_warning_scopes']; del copy['names'][0]['photos'][0]['preview_image_url']
    del copy['names'][0]['photos'][0]['preview_caption']
    assert copy == source
    old = photos.source_photos(target, sources=[source])[0]
    new = photos.source_photos(target, sources=first)[0]
    assert old['id'] == new['id'] and old['image_url'] == new['image_url']
    assert new['preview_image_url'] == overlay['preview_image_url']
    assert new['caption'] == overlay['preview_caption'] and source['names'][0]['photos'][0]['caption'] == 'Named fruit figure'
    assert new['reuse'] == 'unknown' and not new['license_url']
    gallery = photos.gallery(target, sourced=[new], authoring=True)
    template = main.templates.env.get_template('_variety_photo_gallery.html')
    html = template.render(photo_gallery=gallery, authoring_mode=True, static_build=False)
    assert '<img' not in html and f'data-image-url="{overlay["preview_image_url"]}"' in html
    assert 'Full-size image' in html and 'Permission unconfirmed' in html
    for context in [dict(authoring_mode=False, static_build=False), dict(authoring_mode=True, static_build=True)]:
        assert not template.render(photo_gallery=gallery, **context).strip()


def test_saved_edits_hide_restore_and_reset_keep_their_original_photo_key(tmp_path):
    source, overlay, target = fixture()
    old = photos.source_photos(target, sources=[source]); key = old[0]['id']
    source['names'][0]['photos'][0]['preview_image_url'] = overlay['preview_image_url']
    new = photos.source_photos(target, sources=[source]); assert new[0]['id'] == key
    # A saved caption/URL remains the user's choice when source variants arrive.
    edited = {**old[0], 'caption': 'Operator caption', 'image_url': 'https://example.test/operator.png'}
    photos.edit(tmp_path, target=target, payload={**edited, 'revision':'0','photo_id':key,'action':'save'}, sourced=old)
    profile = company_directory.load_profiles(tmp_path)['profiles'][target['id']]
    visible = photos.gallery(target, sourced=new, profile=profile, authoring=True)
    assert visible[0]['caption'] == 'Operator caption' and visible[0]['image_url'] == edited['image_url']
    assert not visible[0].get('preview_image_url')
    photos.edit(tmp_path, target=target, payload=dict(revision='1', photo_id=key, action='remove'), sourced=new)
    profile = company_directory.load_profiles(tmp_path)['profiles'][target['id']]
    assert photos.gallery(target, sourced=new, profile=profile, authoring=True) == []
    photos.edit(tmp_path, target=target, payload=dict(revision='2', photo_id=key, action='restore'), sourced=new)
    profile = company_directory.load_profiles(tmp_path)['profiles'][target['id']]
    assert photos.gallery(target, sourced=new, profile=profile, authoring=True)[0]['caption'] == 'Operator caption'
    photos.edit(tmp_path, target=target, payload=dict(revision='3', photo_id=key, action='reset'), sourced=new)
    profile = company_directory.load_profiles(tmp_path)['profiles'][target['id']]
    reset = photos.gallery(target, sourced=new, profile=profile, authoring=True)[0]
    assert reset['preview_image_url'] == overlay['preview_image_url'] and not reset['display_image']
    assert len(company_directory.load_profiles(tmp_path)['history']) == 4


@pytest.mark.parametrize('newer', [False, True])
def test_changed_or_newer_capture_wins_including_permission_and_identity_edits(tmp_path, newer):
    source, overlay, _ = fixture(); path = write_fixture(tmp_path, source, overlay)
    changed = deepcopy(source); changed['names'][0]['photos'][0]['caption'] = 'New operator caption'
    changed['names'][0]['photos'][0].update(reuse='permission', license_url='https://example.test/terms', reuse_note='Operator permission')
    if newer:
        changed['checked_on'] = '2026-10-29'
        fresh = tmp_path / 'imports/variety-portfolio-observations-newer/observations.json'; fresh.parent.mkdir()
        fresh.write_text(json.dumps(dict(kind='unreviewed_portfolio_name_observations',sources=[changed])))
    else:
        payload=json.loads(path.read_text());payload['sources']=[changed];path.write_text(json.dumps(payload))
    assert load_portfolio_observations(tmp_path) == [changed]


@pytest.mark.parametrize('change', [dict(preview_image_url='http://127.0.0.1/private'),
    dict(preview_image_url='https://user:password@example.test/image'), dict(preview_image_url=[]),
    dict(source_fingerprint='invalid'), dict(berry_id='wrong'), dict(checked_on='not-a-date'),
    dict(extra='unexpected'), dict(preview_caption=[]), dict(preview_caption='')])
def test_invalid_preview_metadata_is_rejected(change):
    _, overlay, _ = fixture()
    with pytest.raises((ValueError, TypeError)):
        read_preview_overlays(dict(photo_preview_overlays=[{**overlay, **change}]))


@pytest.mark.parametrize('change', [dict(source_id='missing'), dict(candidate_name='Different'),
    dict(berry_id='berry-blueberry'), dict(image_url='https://example.test/different.png')])
def test_preview_cannot_attach_to_a_different_source_photo_or_crop(tmp_path, change):
    source, overlay, _ = fixture(); write_fixture(tmp_path, source, {**overlay, **change})
    with pytest.raises(ValueError):
        load_portfolio_observations(tmp_path)


def test_real_four_figures_keep_original_ids_and_review_bounds_without_extra_names():
    payload=json.loads((DATA/'imports'/FOLDER/'observations.json').read_text())
    assert payload['sources'] == [] and len(payload['photo_preview_overlays']) == 4
    original=json.loads((DATA/'imports/variety-portfolio-observations-2026-10-28-raspberry-original-patents/observations.json').read_text(encoding='utf-8'))['sources']
    loaded=load_portfolio_observations(DATA)
    for overlay in payload['photo_preview_overlays']:
        old=next(s for s in original if s['id']==overlay['source_id'])
        new=next(s for s in loaded if s['id']==old['id'])
        target=dict(id='fixture-'+overlay['candidate_name'],candidate_name=overlay['candidate_name'],berry_id=overlay['berry_id'],portfolio_sources=[old['names'][0]])
        previous=photos.source_photos(target,candidate=True)
        target['portfolio_sources']=[new['names'][0]]
        current=photos.source_photos(target,candidate=True)
        assert previous and current and previous[0]['id']==current[0]['id']
        assert current[0]['preview_image_url']==overlay['preview_image_url'] and current[0]['reuse']=='unknown'
        assert not photos.gallery(target,sourced=current,authoring=False)
