"""Grower listings add provenance, not breeding, ownership or generic photos."""
from copy import deepcopy
from pathlib import Path

from fastapi.testclient import TestClient
from app import main
from app.services.variety_navigation import candidate_queue
from app.services.variety_portfolio_coverage import load_portfolio_observations, reconcile_portfolios
from app.services.variety_photos import source_photos

DATA = Path(__file__).resolve().parents[1] / 'data'
PREFIX = 'portfolio-royakkers-original-'
COMPANY = 'company-royakkers'


def reconcile(sources, candidates=()):
    # Registry crop tags must not override the crop explicitly named by this source.
    return reconcile_portfolios(sources=sources, varieties=[], candidates=list(candidates),
        entities=[dict(id=COMPANY, name='Royakkers', entity_type='company',
                       berry_ids=['berry-blueberry', 'berry-blackberry'])])


def test_two_strawberry_grower_names_do_not_create_breeder_or_owner_claims():
    sources = [s for s in load_portfolio_observations(DATA) if s['id'].startswith(PREFIX)]
    rows, candidates = reconcile(sources)
    named = next(s for s in rows if s['id'].endswith('strawberry-fruit'))
    assert len(rows) == 10 and named['accounting_view']['accounted_items'] == 2
    assert named['accounting_view']['issues'] == []
    assert named['source_type'] == 'company_product_page'
    assert {c['candidate_name'] for c in candidates} == {'Elsanta', 'Portola'}
    for c in candidates:
        assert c['berry_id'] == 'berry-strawberry'
        assert not c['proposed_relationships'] and not c['breeder_owner'] and not c['deployment']
        assert not c['aliases'] and not c['auto_confirmed'] and not c['human_gated']
        assert not c['registration']['official_registry_source'] and not c['registration']['status']
        assert not source_photos(c, candidate=True)
        assert 'variety it grows' in c['portfolio_sources'][0]['portfolio_context']
        assert {ref['entity_id'] for ref in c['portfolio_sources'][0]['companies']} == {COMPANY}
    assert not any(s.get('published_date') for s in sources)


def test_unnamed_dutch_nurseries_and_wrong_content_english_paths_remain_gaps():
    sources = [s for s in load_portfolio_observations(DATA) if s['id'].startswith(PREFIX)]
    gaps = [s for s in sources if not s['names']]
    assert len(gaps) == 9 and all(s['capture_status'] == 'partial' for s in gaps)
    assert all('not an empty portfolio' in s['limitations'] for s in gaps)
    dutch = [s for s in gaps if s['id'].endswith(('dutch-raspberry-nursery', 'dutch-blackberry-nursery'))]
    assert len(dutch) == 2 and all(s['capture_reference']['language'] == 'nl' for s in dutch)
    wrong = [s for s in gaps if s['id'].endswith('nursery-gap')]
    assert len(wrong) == 2 and all(s['capture_reference']['nursery_detail_rendered'] is False for s in wrong)
    assert all('No HTTP redirect' in s['limitations'] and s['capture_reference']['attempted_url'] == s['url'] for s in wrong)
    assert not reconcile(gaps)[1]


def test_existing_candidate_ids_human_rejection_and_profile_edits_survive_new_grower_sources():
    sources = load_portfolio_observations(DATA)
    _, old = reconcile([s for s in sources if not s['id'].startswith(PREFIX)])
    _, refreshed = reconcile(sources)
    assert {(c['candidate_name'], c['berry_id'], c['id']) for c in old} == {
        (c['candidate_name'], c['berry_id'], c['id']) for c in refreshed}
    old_elsanta = next(c for c in old if c['candidate_name'] == 'Elsanta' and c['berry_id'] == 'berry-strawberry')
    human = {**old_elsanta, 'status': 'rejected', 'identity_state': 'rejected', 'human_gated': True,
             'review_notes': 'Keep my decision', 'knowledge': {'notes': 'My growing note'},
             'photos': [{'operator': 'My photo'}], 'aliases': ['User spelling'],
             'registration': {'status': 'My jurisdiction note'}}
    before = deepcopy(human)
    rows, candidates = reconcile(sources, [human])
    saved = next(c for c in candidates if c['id'] == human['id'])
    assert human == before
    assert all(saved[k] == before[k] for k in ['review_notes', 'knowledge', 'photos', 'aliases', 'registration', 'identity_state'])
    named = next(s for s in rows if s['id'] == PREFIX + 'strawberry-fruit')
    assert next(n for n in named['names'] if n['candidate_name'] == 'Elsanta')['status'] == 'previously_rejected'


def test_private_company_scope_shows_shared_candidate_provenance_without_writing(monkeypatch, tmp_path):
    _, candidates = reconcile(load_portfolio_observations(DATA))
    before = deepcopy(candidates)
    scoped = candidate_queue(candidates, {'company': COMPANY})['candidates']
    assert {c['candidate_name'] for c in scoped} == {'Elsanta', 'Portola'}
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    monkeypatch.setattr(main, 'INBOX_DIR', tmp_path)
    monkeypatch.setattr(main, 'variety_candidate_universe', lambda: ([], candidates, {}))
    client = TestClient(main.app)
    page = client.get('/varieties/candidates', params={'company': COMPANY, 'q': 'Portola', 'source': PREFIX + 'strawberry-fruit'})
    assert page.status_code == 200 and '1 of ' in page.text
    assert 'variety it grows' in page.text and 'licensing' in page.text
    assert 'https://www.softfruit.be/en/products/fruit/strawberries/' in page.text
    assert candidates == before and not list(tmp_path.rglob('*.json'))
    monkeypatch.setattr(main, 'AUTHORING_MODE', False)
    assert client.get('/varieties/candidates').status_code == 403
