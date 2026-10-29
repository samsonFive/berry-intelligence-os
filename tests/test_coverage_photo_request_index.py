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
