"""Current source portfolios keep placeholders, partner roles and photos honest."""
from copy import deepcopy
from pathlib import Path

from fastapi.testclient import TestClient
from app import main
from app.services import variety_photos as photos
from app.services.variety_portfolio_coverage import load_portfolio_observations, reconcile_portfolios

DATA = Path(__file__).resolve().parents[1] / 'data'
IDS = {'portfolio-mountain-blue-blueberry-page', 'portfolio-mountain-blue-strawberry-page',
       'portfolio-mountain-blue-raspberry-page', 'portfolio-mountain-blue-blackberry-placeholders',
       'portfolio-costa-produce-blueberry-section', 'portfolio-blugenix-five-varieties',
       'portfolio-mountain-blue-nebula-technical-report'}


def sources():
    return [s for s in load_portfolio_observations(DATA) if s['id'] in IDS]


def test_bounded_counts_keep_placeholders_and_comparators_outside_named_portfolios():
    observed = sources()
    original = deepcopy(observed)
    rows, candidates = reconcile_portfolios(sources=observed, varieties=[], entities=[], candidates=[])
    assert len(rows) == 7 and sum(len(s['names']) for s in rows) == 28
    assert len(candidates) == 23  # Five Costa/BluGenix names recur across two sources.
    black = next(s for s in rows if s['id'].endswith('blackberry-placeholders'))
    assert not black['names'] and black['accounting_view']['accounted_items'] == 2
    assert 'not a zero-variety' in black['enumerated_scope']
    assert [e['label'] for e in black['accounting_view']['exclusions']] == ['Blackberry variety 1', 'Blackberry variety 2']
    blugenix = next(s for s in rows if s['id'] == 'portfolio-blugenix-five-varieties')
    assert len(blugenix['names']) == 5 and blugenix['accounting_view']['accounted_items'] == 6
    assert [e['label'] for e in blugenix['accounting_view']['exclusions']] == ['Kirra']
    bounty = next(c for c in candidates if c['candidate_name'] == 'Bounty')
    assert {p['id'] for p in bounty['portfolio_sources']} == {'portfolio-costa-produce-blueberry-section', 'portfolio-blugenix-five-varieties'}
    assert not any(c['candidate_name'] in {'Midnight Beauty', 'BluGenix', 'Blackberry variety 1', 'Blackberry variety 2'} for c in candidates)
    assert all(not s['accounting_view']['issues'] for s in rows if s['capture_status'] == 'names_enumerated')
    assert observed == original


def test_partner_and_selection_context_never_creates_breeder_rights_or_canonical_aliases():
    _, candidates = reconcile_portfolios(sources=sources(), varieties=[], entities=[], candidates=[])
    named = {c['candidate_name']: c for c in candidates}
    assert named['SI-145']['berry_id'] == 'berry-raspberry'
    assert 'not independently established' in named['SI-145']['portfolio_sources'][0]['portfolio_context']
    assert named['Limvalnera']['source_tier'] == 'tier_2_nursery_catalog'
    assert named['Nebula']['source_tier'] == 'weak_noncanonical_lead'
    nebula = next(s for s in sources() if s['id'].endswith('technical-report'))
    assert nebula['capture_status'] == 'partial' and not nebula['capture_reference']['visually_checked']
    assert 'accounting' not in nebula
    for c in candidates:
        assert c['status'] == 'proposed' and not c['auto_confirmed'] and not c['human_gated']
        assert not c['aliases'] and not c['proposed_relationships'] and not c['breeder_owner'] and not c['deployment']
        assert not c['registration']['official_registry_source'] and not c['registration']['grant_number']
    assert all(not s.get('published_date') for s in sources())


def test_named_images_keep_literal_urls_and_unclear_dazzle_photo_is_withheld():
    _, candidates = reconcile_portfolios(sources=sources(), varieties=[], entities=[], candidates=[])
    held = [p for c in candidates for p in photos.source_photos(c, candidate=True)]
    assert len(held) == 3 and {p['named_variety'] for p in held} == {'Eureka Sunrise', 'Eureka Gold', 'Bounty'}
    assert all(p['reuse'] == 'unknown' and not p['license_url'] for p in held)
    gold = next(p for p in held if p['named_variety'] == 'Eureka Gold')
    assert 'EurekaGold%5B10594%5D.png?format=500w' in gold['image_url']
    blue = next(s for s in sources() if s['id'].endswith('blueberry-page'))
    assert blue['capture_reference']['photo_mismatch']['display_label'] == 'Dazzle'
    assert not next(n for n in blue['names'] if n['candidate_name'] == 'Dazzle').get('photos')
    for c in candidates:
        gallery = photos.gallery(c, sourced=photos.source_photos(c, candidate=True), authoring=True)
        assert all(not p['display_image'] for p in gallery)
        assert not photos.gallery(c, sourced=photos.source_photos(c, candidate=True), authoring=False)


def test_candidate_get_does_not_load_unapproved_image_or_create_review_state(monkeypatch, tmp_path):
    monkeypatch.setattr(main, 'INBOX_DIR', tmp_path)
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    client = TestClient(main.app)
    page = client.get('/varieties/candidates', params={'source': 'portfolio-blugenix-five-varieties', 'q': 'Bounty', 'berry': 'berry-blueberry'})
    assert page.status_code == 200 and 'Ignore permission' in page.text
    image = 'https://blugenix.com.au/wp-content/uploads/2025/12/Bounty.png'
    assert f'data-image-url="{image}"' in page.text and f'src="{image}"' not in page.text
    assert 'Costa BluGenix variety page' in page.text and 'Permission unconfirmed' in page.text
    assert not list(tmp_path.rglob('*.json'))
    monkeypatch.setattr(main, 'AUTHORING_MODE', False)
    public = client.get('/varieties/candidates', params={'q': 'Bounty', 'berry': 'berry-blueberry'})
    assert image not in public.text and 'Ignore permission' not in public.text
