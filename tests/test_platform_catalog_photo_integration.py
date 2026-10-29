"""The platform's catalog path must retain the richer source branch's results."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from app.services import variety_photos as photos
from app.services.variety_photo_review import photo_identity_reviews
from app.services.variety_portfolio_coverage import load_portfolio_observations


def corpus():
    root = Path(__file__).resolve().parents[1] / 'data'
    varieties = [json.loads(p.read_text(encoding='utf-8'))
                 for p in sorted((root/'entities/varieties').glob('*.json'))]
    return varieties, load_portfolio_observations(root)


def test_full_catalog_retains_single_profile_previews_holds_and_user_edits():
    varieties, sources = corpus()
    before = deepcopy((varieties, sources))
    expected = {v['id']: photos.source_photos(v, sources=sources, varieties=varieties) for v in varieties}
    actual = photos.catalog_source_photos(sources=sources, varieties=varieties)
    assert actual == expected
    assert not actual['variety-kwanza'] and not actual['variety-rutgers-dlight']
    target = next(v for v in varieties if v['id'] == 'variety-blue-manila')
    photo = actual[target['id']][0]
    profile = {'revision': 12, 'variety_photo_overrides': {photo['id']: {**photo, 'caption': 'My retained caption'}}}
    saved = deepcopy(profile)
    gallery = photos.gallery(target, sourced=actual[target['id']], profile=profile, authoring=True)
    assert gallery[0]['caption'] == 'My retained caption' and not gallery[0]['display_image']
    assert not photos.gallery(target, sourced=actual[target['id']], profile=profile, authoring=False)
    assert profile == saved and (varieties, sources) == before


def test_larger_original_preview_survives_for_an_exact_code_without_creating_an_alias():
    _, sources = corpus()
    # These originals currently describe coded candidates rather than approved
    # catalog identities. Use one real source with an isolated exact-code
    # catalog fixture; never invent an alias to attach it to a live variety.
    source = next(s for s in sources if s['id'] == 'portfolio-raspberry-original-uspp36008p3')
    raw = next(p for n in source['names'] for p in n.get('photos', []) if p.get('preview_image_url'))
    target = {'id': 'fixture-abb135-exact-code', 'name': raw['named_variety'], 'berry_ids': [raw['berry_id']]}
    original = deepcopy((source, target))
    expected = photos.source_photos(target, sources=[source], varieties=[target])
    actual = photos.catalog_source_photos(sources=[source], varieties=[target])[target['id']]
    assert actual == expected and len(actual) == 1
    assert actual[0]['preview_image_url'] == raw['preview_image_url']
    assert actual[0]['image_url'] == raw['image_url'] and actual[0]['reuse'] == 'unknown'
    assert not photos.gallery(target, sourced=actual, authoring=True)[0]['display_image']
    assert (source, target) == original and 'aliases' not in target


def test_catalog_and_held_review_share_validation_and_reject_a_different_snapshot(monkeypatch):
    varieties, sources = corpus()
    raw_ids = {id(p) for s in sources for n in s['names'] for p in n.get('photos', [])}
    validate, calls = photos.validate_photo, []
    def counted(value):
        if id(value) in raw_ids:
            calls.append(id(value))
        return validate(value)
    monkeypatch.setattr(photos, 'validate_photo', counted)
    context = photos.SourcePhotoIndex(sources, varieties)
    projected = photos.catalog_source_photos(sources=sources, varieties=varieties, _index=context)
    held = {v['id']: photo_identity_reviews(v, sources=sources, varieties=varieties,
                sourced=projected[v['id']], _index=context) for v in varieties}
    assert set(calls) == raw_ids and len(calls) == len(raw_ids)
    assert held['variety-kwanza'] and held['variety-rutgers-dlight']
    assert all('image_url' not in row for rows in held.values() for row in rows)
    with pytest.raises(ValueError, match='different source or catalog snapshot'):
        photos.catalog_source_photos(sources=list(sources), varieties=varieties, _index=context)
