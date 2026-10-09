"""Historical diagram names preserve identity and unresolved source scope."""
from copy import deepcopy
from pathlib import Path

from app.services.variety_portfolio_coverage import load_portfolio_observations, reconcile_portfolios

DATA = Path(__file__).resolve().parents[1] / 'data'
DIAGRAM = 'portfolio-usda-lewis-2001-pedigree'


def test_original_pedigree_accounts_for_nodes_and_retains_the_unclear_code():
    sources = load_portfolio_observations(DATA)
    diagram = next(s for s in sources if s['id'] == DIAGRAM)
    rows, _ = reconcile_portfolios(sources=[diagram], varieties=[], entities=[], candidates=[])
    assert len(diagram['names']) == 13
    assert diagram['capture_status'] == 'partial' and rows[0]['needs_follow_up']
    assert rows[0]['accounting_view']['accounted_items'] == 16
    assert not rows[0]['accounting_view']['issues']
    assert {n['candidate_name'] for n in diagram['names']} >= {'Creston', 'Washington', 'Burnetholm', 'Malling Jewel'}
    assert all(n['candidate_name'] not in {'3B:45', '3B/45', 'R. strigosus'} for n in diagram['names'])
    assert any('separator is unresolved' in e['reason'] for e in diagram['accounting']['exclusions'])
    paper = next(s for s in sources if s['id'] == 'portfolio-usda-lewis-2001-paper')
    assert paper['capture_status'] == 'names_enumerated'
    assert paper['capture_reference']['visually_reviewed_pages'] == [1, 2, 3, 4]
    assert not paper.get('published_date')
    assert not diagram['capture_reference']['current_legal_status_verified']
    assert not diagram['capture_reference']['reuse_permission_verified']


def test_pedigree_addition_retains_all_prior_ids_and_operator_decisions():
    sources = load_portfolio_observations(DATA)
    prior = [s for s in sources if s['id'] != DIAGRAM]
    _, old = reconcile_portfolios(sources=prior, varieties=[], entities=[], candidates=[])
    _, added = reconcile_portfolios(sources=sources, varieties=[], entities=[], candidates=[])
    by_key = {(c['candidate_name'], c['berry_id']): c for c in added}
    assert all(by_key[c['candidate_name'], c['berry_id']]['id'] == c['id'] for c in old)
    assert len(added) == len(old) + 11
    human = deepcopy(next(c for c in old if c['candidate_name'] == 'Willamette' and c['berry_id'] == 'berry-raspberry'))
    human.update(human_gated=True, status='rejected', identity_state='rejected',
                 review_notes='Retain operator decision', photos=[{'operator_choice': 'Retain'}])
    expected = deepcopy(human)
    _, saved = reconcile_portfolios(sources=sources, varieties=[], entities=[], candidates=[human])
    actual = next(c for c in saved if c['id'] == human['id'])
    # Provenance is recomputed as new sources arrive; saved operator fields
    # and the input record itself must remain unchanged.
    fields = ('id', 'candidate_name', 'berry_id', 'human_gated', 'status',
              'identity_state', 'review_notes', 'photos', 'aliases', 'registration')
    assert all(actual[k] == expected[k] for k in fields) and human == expected
