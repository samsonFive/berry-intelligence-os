"""A complete article capture adds context without promoting identity or region."""
from copy import deepcopy
import json
from pathlib import Path

from app.services.variety_portfolio_coverage import load_portfolio_observations, reconcile_portfolios

DATA = Path(__file__).resolve().parents[1] / 'data'
SOURCE = 'portfolio-mountain-blue-nebula-technical-report'


def captures():
    old = next(s for s in json.loads((DATA / 'imports/variety-portfolio-observations-2026-10-07-mountain-blue-costa/observations.json').read_text(encoding='utf-8'))['sources'] if s['id'] == SOURCE)
    current = next(s for s in load_portfolio_observations(DATA) if s['id'] == SOURCE)
    return old, current


def reconcile(rows, candidates=()):
    return reconcile_portfolios(sources=rows, varieties=[], entities=[], candidates=list(candidates))


def test_new_capture_accounts_for_both_pages_without_changing_historical_capture():
    old, current = captures()
    assert old['checked_on'] == '2026-10-07' and old['capture_status'] == 'partial'
    assert not old['capture_reference']['visually_checked'] and 'accounting' not in old
    assert current['checked_on'] == '2026-11-04' and not current.get('published_date')
    assert current['capture_reference']['pdf_total_pages'] == 2
    assert current['capture_reference']['printed_pages'] == [82, 83]
    assert current['capture_reference']['publication_period'] == 'Winter 2025, Edition 23'
    rows, candidates = reconcile([current])
    assert not rows[0]['accounting_view']['issues']
    assert rows[0]['accounting_view']['accounted_items'] == 2
    assert [c['candidate_name'] for c in candidates] == ['Nebula']
    assert not current['names'][0].get('photos')
    assert current['names'][0]['product_url'].endswith('.pdf#page=2')
    assert 'sample sizes are not supplied' in current['names'][0]['portfolio_context']


def test_recapture_keeps_candidate_id_and_unreviewed_identity_role_region_gates():
    old, current = captures()
    _, before = reconcile([old])
    _, after = reconcile([current])
    assert before[0]['id'] == after[0]['id']
    candidate = after[0]
    assert candidate['source_tier'] == 'weak_noncanonical_lead'
    assert not candidate['auto_confirmed'] and not candidate['human_gated']
    assert candidate['status'] == 'proposed'
    assert not candidate['aliases'] and not candidate['breeder_owner']
    assert not candidate['proposed_relationships'] and not candidate['deployment']
    assert not candidate['registration']['official_registry_source']
    assert 'not confirmed growing regions' in candidate['portfolio_sources'][0]['portfolio_context']


def test_operator_rejection_notes_and_photo_choices_win_over_new_capture():
    _, current = captures()
    human = dict(id='operator-nebula', candidate_name='Nebula', berry_id='berry-blackberry',
                 status='rejected', identity_state='rejected', human_gated=True,
                 review_notes='My decision', aliases=['My alias'],
                 photos=[{'operator': 'Keep private'}], registration={'status': 'My status'})
    before = deepcopy(human)
    rows, candidates = reconcile([current], [human])
    saved = next(c for c in candidates if c['id'] == human['id'])
    assert human == before and all(saved[k] == v for k, v in before.items())
    assert rows[0]['names'][0]['status'] == 'previously_rejected'
