"""Named products, comparator scope and conflicting labels stay distinct."""
from copy import deepcopy
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.services.variety_portfolio_coverage import load_portfolio_observations, reconcile_portfolios, source_company_ids

ROOT = Path(__file__).resolve().parents[1]
IDS = {'portfolio-cbc-visible-cultivars', 'portfolio-ava-named-varieties',
       'portfolio-angus-ava-carousel', 'portfolio-ava-breeding-alicia-label'}


def sources():
    return [s for s in load_portfolio_observations(ROOT / 'data') if s['id'] in IDS]


def test_cbc_stated_minimum_and_comparators_do_not_become_owned_products():
    source = next(s for s in sources() if 'cbc' in s['id'])
    rows, candidates = reconcile_portfolios(sources=[source], varieties=[], entities=[], candidates=[])
    row = rows[0]
    assert row['accounting_view']['accounted_items'] == 11
    assert row['accounting_view']['reported_items'] == 12 and row['needs_follow_up']
    assert row['accounting_view']['issues']
    assert not {'Monterey', 'Cabrillo', 'Fronteras', 'Portola', 'Ruby June', 'San andreas', 'Bounty'} & {
        c['candidate_name'] for c in candidates}
    elcano = next(n for n in row['names'] if n['candidate_name'] == 'Elcano')
    assert elcano['breeder_code'] == 'CBC027' and not elcano.get('denomination')
    assert all(not c['proposed_relationships'] and not c['human_gated'] for c in candidates)


def test_ava_spelling_discrepancies_never_guess_crop_or_alias():
    rows, candidates = reconcile_portfolios(sources=sources(), varieties=[], entities=[], candidates=[])
    names = {c['candidate_name']: c for c in candidates}
    assert names['AVA Dalicia']['id'] != names['AVA Alicia']['id']
    assert 'AVA Dalacia' not in names and 'Magnum' not in names
    carousel = next(r for r in rows if r['id'] == 'portfolio-angus-ava-carousel')
    assert carousel['accounting_view']['accounted_items'] == 7 and carousel['needs_follow_up']
    assert carousel['accounting_view']['exclusions'][0]['label'] == 'AVA Dalacia'
    named = next(r for r in rows if r['id'] == 'portfolio-ava-named-varieties')
    assert sum(n['berry_id'] == 'berry-strawberry' for n in named['names']) == 5
    assert sum(n['berry_id'] == 'berry-raspberry' for n in named['names']) == 2
    assert not any(n.get('photos') or n.get('denomination') for n in named['names'])
    assert all(not c['deployment'] and not c['human_gated'] for c in candidates)


def test_new_company_sources_preserve_existing_human_rejection_and_notes():
    rejected = {'id': 'vcand-user-elcano', 'candidate_name': 'Elcano', 'berry_id': 'berry-strawberry',
                'status': 'rejected', 'identity_state': 'rejected', 'human_gated': True,
                'reviewer': 'Analyst', 'review_notes': 'Keep my decision', 'knowledge': {'notes': 'User edit'}}
    before = deepcopy(rejected)
    rows, candidates = reconcile_portfolios(sources=sources(), varieties=[], entities=[], candidates=[rejected])
    kept = next(c for c in candidates if c['id'] == rejected['id'])
    assert rejected == before and kept['review_notes'] == before['review_notes']
    assert kept['knowledge'] == before['knowledge'] and kept['status'] == 'rejected'
    assert next(r for r in rows if 'cbc' in r['id'])['closed'] == 1
    assert sum(c['candidate_name'] == 'Elcano' for c in candidates) == 1


def test_company_crosschecks_render_privately_without_writing_or_public_leaks(monkeypatch, tmp_path):
    monkeypatch.setattr(main, 'INBOX_DIR', tmp_path)
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    client = TestClient(main.app)
    # California Giant now also has source sections; scope this CBC assertion.
    cbc = client.get('/varieties/coverage?q=California%20Berry%20Cultivars')
    assert cbc.status_code == 200 and '11 observed items' in cbc.text
    assert '12 minimum cultivars' in cbc.text
    # A newer complete page does not erase the older index's shortfall.
    assert 'Partial variety coverage' in cbc.text and 'CBC027' in cbc.text
    assert 'Names found · more sources to check' in cbc.text
    read_sections = sum(s['capture_status'] != 'unreadable' for s in
                        load_portfolio_observations(ROOT / 'data')
                        if 'company-california-berry-cultivars' in source_company_ids(s))
    assert f'{read_sections} source sections read' in cbc.text
    assert '0 page sections checked' not in cbc.text
    ava = client.get('/varieties/coverage?q=Angus')
    assert ava.status_code == 200 and 'AVA Dalacia' in ava.text and 'AVA Alicia' in ava.text
    assert 'Website correction suggested.' in ava.text
    assert 'Saved website points to another organization' not in ava.text
    assert not list(tmp_path.rglob('*'))
    monkeypatch.setattr(main, 'AUTHORING_MODE', False)
    public = client.get('/varieties/coverage?q=Angus')
    assert public.status_code == 200 and 'AVA Dalacia' not in public.text
    assert 'portfolio-angus-ava-carousel' not in public.text
