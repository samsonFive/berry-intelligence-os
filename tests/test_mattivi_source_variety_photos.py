"""Original name/code pairs and photos remain reviewable without trust writes."""
from copy import deepcopy
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.services import variety_photos as photos
from app.services.company_variety_discoveries import company_variety_discoveries
from app.services.variety_portfolio_coverage import load_portfolio_observations, reconcile_portfolios

DATA = Path(__file__).resolve().parents[1] / 'data'
COMPANY = 'company-mattivi-group'
PAIRS = {'Serena': 'M.P. 745', 'Nives': 'M.P. 102', 'Dolcevita': 'M.F. 500',
         'Isabella': 'M.F. 1116', 'Karima': 'A.Karima', 'Munira': 'A.Munira'}


def sources():
    return [s for s in load_portfolio_observations(DATA) if s['id'].startswith('portfolio-mattivi-')]


def reconcile():
    return reconcile_portfolios(sources=sources(), varieties=[], entities=[], candidates=[])


def test_complete_pages_account_for_paired_codes_and_exclude_blueberry_comparator():
    rows, candidates = reconcile()
    assert len(rows) == 12 and sum(len(s['names']) for s in rows) == 16
    assert sum(len(s['accounting_view']['exclusions']) for s in rows) == 13
    assert all(not s['accounting_view']['issues'] and not s['needs_follow_up'] for s in rows)
    assert {c['candidate_name'] for c in candidates} == {*PAIRS, 'M.H. 1-07', 'M.PB.64-01'}
    assert not {'Duke', *PAIRS.values(), 'AuroraKarima', 'AuroraMunira'} & {c['candidate_name'] for c in candidates}
    assert len(candidates) == 8


def test_code_pairings_are_searchable_source_labels_without_approving_identities_or_rights():
    rows, candidates = reconcile()
    view = company_variety_discoveries(entity_id=COMPANY, sources=rows)
    assert len(view['rows']) == 8 and view['source_count'] == 12 and view['follow_up_count'] == 0
    for label, code in PAIRS.items():
        row = next(r for r in view['rows'] if r['name'] == f'{label} · {code}')
        assert code.casefold() in row['search'] and row['code'] == ''
        assert 'q=' + label in row['href'] and 'source=portfolio-mattivi-' in row['href']
        assert any(code in n for n in row['notes'])
    assert all(not c['aliases'] and not c['human_gated'] and not c['auto_confirmed'] for c in candidates)
    assert all(not c['proposed_relationships'] and not c['registration']['status'] for c in candidates)
    assert all(not c.get('denomination') and not c.get('breeder_code') for c in candidates)
    assert not any(s.get('published_date') for s in rows)


def test_all_prior_candidate_links_and_saved_human_decisions_survive_new_sources():
    all_sources = load_portfolio_observations(DATA)
    _, old = reconcile_portfolios(sources=[s for s in all_sources if not s['id'].startswith('portfolio-mattivi-')],
        varieties=[], entities=[], candidates=[])
    _, new = reconcile_portfolios(sources=all_sources, varieties=[], entities=[], candidates=[])
    keys = {(c['berry_id'], c['candidate_name']): c['id'] for c in new}
    assert all(keys[(c['berry_id'], c['candidate_name'])] == c['id'] for c in old)
    human = dict(id='operator-nives', candidate_name='Nives', berry_id='berry-raspberry',
        status='rejected', identity_state='rejected', human_gated=True, reviewer='Analyst',
        aliases=['User name'], registration={'status': 'User status', 'application_number': 'User number'},
        review_notes='Retain rejection', knowledge={'notes': 'Retain my notes'})
    before = deepcopy(human)
    rows, candidates = reconcile_portfolios(sources=sources(), varieties=[], entities=[], candidates=[human])
    saved = next(c for c in candidates if c['id'] == human['id'])
    assert all(saved[k] == before[k] for k in ('aliases', 'registration', 'review_notes', 'knowledge', 'status'))
    assert not any(r['name'].startswith('Nives') for r in company_variety_discoveries(entity_id=COMPANY, sources=rows)['rows'])
    assert human == before


def test_original_named_photos_are_attributed_and_never_public_or_cross_crop():
    original = sources()
    before = deepcopy(original)
    _, candidates = reconcile()
    by_name = {c['candidate_name']: c for c in candidates}
    assert sum(len(n.get('photos', [])) for s in original for n in s['names']) == 4
    for label in ('Serena', 'Nives', 'Dolcevita', 'Isabella'):
        target = by_name[label]
        gallery = photos.gallery(target, sourced=photos.source_photos(target, candidate=True), authoring=True)
        assert len(gallery) == 1
        photo = gallery[0]
        assert photo['named_variety'] == label and photo['berry_id'] == 'berry-raspberry'
        assert photo['credit'] == 'Mattivi Group' and photo['reuse'] == 'unknown'
        assert not photo['display_image'] and not photo['license_url']
        assert photo['source_url'] == 'https://www.mattivi.it/raspberry-varieties/'
        assert '/elementor/thumbs/' in photo['image_url']
        assert not photos.gallery(target, sourced=gallery, authoring=False)
        assert not photos.compatible(photo, dict(candidate_name=label, berry_id='berry-blackberry'), candidate=True)
    assert not photos.source_photos(by_name['Karima'], candidate=True)
    assert original == before


def test_each_offering_keeps_original_detail_and_portfolio_references():
    rows, _ = reconcile()
    view = company_variety_discoveries(entity_id=COMPANY, sources=rows)
    assert all(len(r['sources']) == 2 for r in view['rows'])
    blackberry = next(r for r in view['rows'] if r['name'] == 'M.PB.64-01')
    assert {s['href'] for s in blackberry['sources']} == {
        'https://www.mattivi.it/blackberry-varieties/',
        'https://www.mattivi.it/blackberry-varieties/m-pb-64-01/'}
    blueberry = next(r for r in view['rows'] if r['name'] == 'M.H. 1-07')
    assert any(s['href'] == 'https://www.mattivi.it/m-h-1-07-pbr/' for s in blueberry['sources'])
    assert 'Duke' not in {r['name'] for r in view['rows']}


def test_private_preview_get_preserves_records_and_requires_explicit_session_choice(monkeypatch, tmp_path):
    _, candidates = reconcile()
    before = deepcopy(candidates)
    monkeypatch.setattr(main, 'INBOX_DIR', tmp_path)
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    monkeypatch.setattr(main, 'variety_candidate_universe', lambda: ([], candidates, {}))
    page = TestClient(main.app).get('/varieties/candidates', params={
        'source': 'portfolio-mattivi-01-raspberry', 'q': 'Nives', 'berry': 'berry-raspberry'})
    assert page.status_code == 200 and 'Nives' in page.text and 'M.P. 102' in page.text
    assert 'Ignore permission' in page.text and 'Permission unconfirmed' in page.text
    assert 'Needs identity review' in page.text and 'Not saved' in page.text
    image = next(n['photos'][0]['image_url'] for s in sources() for n in s['names'] if n.get('photos') and n['candidate_name'] == 'Nives')
    assert 'data-image-url="' + image + '"' in page.text and 'src="' + image + '"' not in page.text
    assert candidates == before and not list(tmp_path.rglob('*.json'))
    monkeypatch.setattr(main, 'AUTHORING_MODE', False)
    assert TestClient(main.app).get('/varieties/candidates').status_code == 403
