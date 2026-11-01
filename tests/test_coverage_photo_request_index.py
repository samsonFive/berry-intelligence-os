"""Share repeated photo work without changing source or human decisions."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from app.services import variety_photos as photos
from app.services import variety_portfolio_coverage as portfolios
from app.services.variety_photo_review import photo_identity_reviews
from app.services.variety_profile_coverage import profile_field_coverage


def corpus():
    root = Path(__file__).resolve().parents[1] / 'data'
    varieties = [json.loads(p.read_text(encoding='utf-8')) for p in sorted((root/'entities/varieties').glob('*.json'))]
    return varieties, portfolios.load_portfolio_observations(root)


def test_all_current_profiles_keep_exact_photos_reviews_and_input_records(monkeypatch):
    varieties, sources = corpus()
    before = deepcopy((varieties, sources))
    expected = []
    for target in varieties:
        rows = photos.source_photos(target, sources=sources, varieties=varieties)
        expected.append((rows, photo_identity_reviews(target, sources=sources, varieties=varieties, sourced=rows)))
    calls = []
    calculate = portfolios._identity_pair_notes
    monkeypatch.setattr(portfolios, '_identity_pair_notes', lambda rows: (calls.append(rows), calculate(rows))[1])
    context = photos.SourcePhotoIndex(sources, varieties)
    actual = []
    for target in varieties:
        rows = photos.source_photos(target, sources=sources, varieties=varieties, _index=context)
        actual.append((rows, photo_identity_reviews(target, sources=sources, varieties=varieties, sourced=rows, _index=context)))
    assert actual == expected
    assert len(calls) == 1
    assert (varieties, sources) == before


def test_inventory_validates_each_source_photo_once_and_keeps_saved_hide(monkeypatch):
    varieties, sources = corpus()
    # The real full corpus includes larger-original overlays, identity-held
    # sources, different crops and repeated photo labels.
    raw = [p for source in sources for name in source['names'] for p in name.get('photos', [])]
    base_calls = []
    validate = photos.validate_photo
    def count(value):
        if any(value is p for p in raw):
            base_calls.append(id(value))
        return validate(value)
    monkeypatch.setattr(photos, 'validate_photo', count)
    target = next(v for v in varieties if v['id']=='variety-blue-manila')
    eligible = photos.source_photos(target, sources=sources, varieties=varieties)
    base_calls.clear()
    profiles = {target['id']: {'revision': 9, 'variety_photo_overrides': {p['id']: None for p in eligible}}}
    result = profile_field_coverage(varieties=varieties, entities=varieties, relationships=[],
        published_evidence=[], portfolio_sources=sources, profiles=profiles, reconciled_sources=[])
    assert len(base_calls) == len(set(id(p) for p in raw))
    row = next(r for r in result['rows'] if r['id']==target['id'])
    assert row['photos']==0 and row['photo_identity_reviews']==[] and 'photos' in row['missing']
    assert profiles[target['id']]['revision']==9


def test_new_inventory_rechecks_source_edits_and_catalog_ambiguity():
    varieties, sources = corpus()
    target = next(v for v in varieties if v['id']=='variety-blue-maldiva')
    sources = [s for s in sources if s['id']=='portfolio-plablue-original-uspp31403p2']
    varieties = [target]
    def inventory():
        return profile_field_coverage(varieties=varieties, entities=varieties, relationships=[],
            published_evidence=[], portfolio_sources=sources, reconciled_sources=[])['rows']
    assert inventory()[0]['photos']==1
    varieties.append({**deepcopy(target), 'id':'fixture-unresolved-second-identity'})
    rows = inventory()
    assert all(r['photos']==0 and r['photo_identity_reviews'] for r in rows)
    varieties.pop()
    assert inventory()[0]['photos']==1
    sources[0]['names'][0]['photos'][0]['image_url']='http://127.0.0.1/private-photo'
    with pytest.raises(ValueError, match='public http'):
        inventory()


def test_new_request_retains_new_identity_hold_and_rejects_another_snapshot():
    varieties, sources = corpus()
    target = next(v for v in varieties if v['id']=='variety-rutgers-dlight')
    coded = next(s for s in sources if s['id']=='portfolio-rutgers-original-grant-nj09-2-1')
    sources = [s for s in sources if s['id']=='portfolio-named-photo-cohort-rutgers-dlight']
    context = photos.SourcePhotoIndex(sources, varieties)
    assert photos.source_photos(target, sources=sources, varieties=varieties, _index=context)
    updated = [*sources, coded]
    with pytest.raises(ValueError, match='different source or catalog snapshot'):
        photos.source_photos(target, sources=updated, varieties=varieties, _index=context)
    fresh = photos.SourcePhotoIndex(updated, varieties)
    assert photos.source_photos(target, sources=updated, varieties=varieties, _index=fresh)==[]
    notes = photo_identity_reviews(target, sources=updated, varieties=varieties, _index=fresh)
    assert len(notes)==1 and any('code in one source' in n for n in notes[0]['review_notes'])
    assert 'image_url' not in notes[0] and 'q=Rutgers+D%27Light' in notes[0]['review_href']


def fixture_photo(name='Keepsake', **changes):
    return dict(dict(image_url='https://example.test/fruit.jpg', source_url='https://example.test/fruit',
        credit='Fixture publisher', caption='Source-labeled fruit', named_variety=name,
        berry_id='berry-strawberry', reuse='unknown', checked_on='2026-01-01', kind='fruit'), **changes)


def fixture_source(*raw, **changes):
    return dict(id='fixture-photo-source', company_ids=[], names=[dict(
        candidate_name='Keepsake', berry_id='berry-strawberry', photos=list(raw), **changes)])


@pytest.mark.parametrize('field', ['name', 'aliases', 'trade_name', 'commercial_name',
    'denomination', 'selection_code', 'breeder_code', 'patent_number', 'patent_id', 'rights_id'])
def test_prefilter_preserves_every_authoritative_identity_field(field):
    target = dict(id='fixture-variety', entity_type='variety', name='Different name',
        berry_ids=['berry-strawberry'], attributes={})
    if field == 'name':
        target['name'] = 'Kéepsake'
    elif field == 'aliases':
        target['aliases'] = ['Kéepsake', 'Keepsake']
    else:
        target['attributes'][field] = 'Kéepsake'
    sources, varieties = [fixture_source(fixture_photo())], [target]
    expected = photos.source_photos(target, sources=sources, varieties=varieties)
    assert len(expected) == 1
    index = photos.SourcePhotoIndex(sources, varieties)
    assert photos.source_photos(target, sources=sources, varieties=varieties, _index=index) == expected


def test_prefilter_keeps_duplicate_photo_order_and_calls_final_match_gate(monkeypatch):
    target = dict(id='fixture-variety', name='Keepsake', aliases=['Kéepsake', 'Other label'],
        berry_ids=['berry-strawberry'])
    first = fixture_photo(caption='First caption')
    last = fixture_photo('Other label', caption='Later caption for the same image')
    unrelated = fixture_photo('Unrelated')
    wrong_crop = {**fixture_photo(), 'berry_id': 'berry-blueberry'}
    sources = [fixture_source(first, unrelated, wrong_crop, last)]
    varieties = [target]
    before = deepcopy((sources, varieties))
    expected = photos.source_photos(target, sources=sources, varieties=varieties)
    calls = []
    compatible = photos.compatible
    def count(photo, record, **kwargs):
        calls.append(photo['named_variety'])
        return compatible(photo, record, **kwargs)
    monkeypatch.setattr(photos, 'compatible', count)
    actual = photos.source_photos(target, sources=sources, varieties=varieties,
        _index=photos.SourcePhotoIndex(sources, varieties))
    assert actual == expected and actual[0]['caption'] == 'Later caption for the same image'
    assert calls == ['Keepsake', 'Other label']
    assert (sources, varieties) == before


def test_prefilter_does_not_hide_invalid_unrelated_photos_or_validate_held_previews():
    target = dict(id='fixture-variety', name='Keepsake', berry_ids=['berry-strawberry'])
    # Review-only callers supply already chosen photos and historically validate
    # base metadata, not the optional image-preview overlay.
    held = fixture_source({**fixture_photo(), 'preview_image_url': 'http://127.0.0.1/private'},
        identity_notes=['Name requires review'])
    sources, varieties = [held], [target]
    assert photos.source_photos(target, sources=sources, varieties=varieties) == []
    index = photos.SourcePhotoIndex(sources, varieties)
    assert photos.source_photos(target, sources=sources, varieties=varieties, _index=index) == []
    expected = photo_identity_reviews(target, sources=sources, varieties=varieties, sourced=[])
    assert photo_identity_reviews(target, sources=sources, varieties=varieties, sourced=[], _index=index) == expected
    assert len(expected) == 1 and 'image_url' not in expected[0]
    held['names'][0]['photos'][0]['image_url'] = 'http://127.0.0.1/private'
    assert photos.source_photos(target, sources=sources, varieties=varieties,
        _index=photos.SourcePhotoIndex(sources, varieties)) == []
    with pytest.raises(ValueError, match='public http'):
        photo_identity_reviews(target, sources=sources, varieties=varieties, sourced=[],
            _index=photos.SourcePhotoIndex(sources, varieties))
    unrelated = [fixture_source({**fixture_photo('Other fruit'), 'image_url': 'http://127.0.0.1/private'})]
    for index in (None, photos.SourcePhotoIndex(unrelated, varieties)):
        with pytest.raises(ValueError, match='public http'):
            photos.source_photos(target, sources=unrelated, varieties=varieties, _index=index)


def test_short_names_still_fail_authoritative_match_and_catalog_ambiguity_is_global():
    target = dict(id='fixture-variety', name='AB', berry_ids=['berry-strawberry'])
    sources, varieties = [fixture_source(fixture_photo('AB'))], [target]
    assert photos.source_photos(target, sources=sources, varieties=varieties,
        _index=photos.SourcePhotoIndex(sources, varieties)) == []
    target['name'] = 'Keepsake'
    sources[0]['names'][0]['photos'][0]['named_variety'] = 'Keepsake'
    varieties.append(dict(id='fixture-other', name='Another cultivar', aliases=['Keepsake'],
        berry_ids=['berry-strawberry']))
    index = photos.SourcePhotoIndex(sources, varieties)
    assert photos.source_photos(target, sources=sources, varieties=varieties, _index=index) == []
    reviews = photo_identity_reviews(target, sources=sources, varieties=varieties, _index=index)
    assert len(reviews) == 1 and any('more than one catalog' in n for n in reviews[0]['review_notes'])
