"""A named current product stays distinct from the previously unnamed pipeline."""
from pathlib import Path

from app.services.variety_photos import gallery, source_photos
from app.services.variety_portfolio_coverage import load_portfolio_observations, reconcile_portfolios


def test_named_fontana_does_not_approve_unnamed_seedless_identity_or_image_reuse():
    sources = load_portfolio_observations(Path(__file__).resolve().parents[1] / 'data')
    current = next(s for s in sources if s['id'] == 'portfolio-pairwise-fontana-original-products')
    earlier = next(s for s in sources if s['id'] == 'portfolio-gap-pairwise-blackberry-products')
    assert earlier['names'] == [] and earlier['capture_status'] == 'partial'
    assert current['url'] == 'https://www.pairwise.com/products'
    assert not current.get('published_date')
    assert current['accounting']['observed_items'] == 2
    assert [r['label'] for r in current['accounting']['exclusions']] == ['Seedless blackberry']
    rows, candidates = reconcile_portfolios(sources=[earlier, current], varieties=[], entities=[], candidates=[])
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate['candidate_name'] == 'Fontana' and candidate['berry_id'] == 'berry-blackberry'
    assert not candidate['human_gated'] and not candidate['auto_confirmed']
    assert candidate['persisted'] is False and not candidate['registration']['official_registry_source']
    assert not candidate.get('breeder_code') and not candidate.get('denomination')
    assert rows[1]['matched'] == 0 and rows[1]['needs_review'] == 1
    assert not rows[1]['accounting_view']['issues']
    photos = source_photos(candidate, candidate=True)
    assert len(photos) == 2 and {p['kind'] for p in photos} == {'plant', 'fruit'}
    assert all(p['named_variety'] == 'Fontana' and p['source_url'] == current['url'] for p in photos)
    assert all(not p['display_image'] for p in gallery(candidate, sourced=photos, authoring=True))
    assert gallery(candidate, sourced=photos, authoring=False) == []
