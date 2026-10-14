"""An original paper can name research cultivars without establishing releases."""
from copy import deepcopy
from pathlib import Path

from app.services.variety_portfolio_coverage import load_portfolio_observations, reconcile_portfolios, portfolio_coverage

DATA = Path(__file__).resolve().parents[1] / 'data'
SOURCE_ID = 'portfolio-original-paper-cas-strawberry-materials'
COMPANY = 'company-institute-of-botany-cas'


def sources():
    return [s for s in load_portfolio_observations(DATA) if s['id'] in {
        SOURCE_ID, 'portfolio-cas-strawberry-ripening-research'}]


def test_original_methods_recover_both_names_without_rewriting_the_announcement():
    rows = sources()
    announcement = next(s for s in rows if s['id'] != SOURCE_ID)
    paper = next(s for s in rows if s['id'] == SOURCE_ID)
    assert announcement['published_date'] == '2021-06-04' and not announcement['names']
    assert paper['published_date'] == '2021-06-03' and paper['capture_status'] == 'partial'
    assert {n['candidate_name'] for n in paper['names']} == {'Hawaii-4', 'Benihoppe'}
    assert 'reported_items' not in paper['accounting']
    assert paper['accounting']['observed_items'] == 2 + len(paper['accounting']['exclusions'])
    assert not paper['capture_reference']['complete_release_portfolio']
    assert all(n['source_company_ids'] == [COMPANY] and 'research material' in n['source_company_context'] for n in paper['names'])


def test_research_use_reaches_review_without_creating_roles_traits_or_aliases():
    rows, candidates = reconcile_portfolios(sources=sources(), varieties=[], entities=[], candidates=[])
    assert {c['candidate_name'] for c in candidates} == {'Hawaii-4', 'Benihoppe'}
    assert all(not r['accounting_view']['issues'] for r in rows)
    for candidate in candidates:
        assert candidate['berry_id'] == 'berry-strawberry'
        assert not candidate['human_gated'] and not candidate['aliases'] and not candidate['proposed_relationships']
        assert not candidate['registration']['status'] and not candidate.get('photos')
        assert not candidate.get('growing_regions') and not candidate.get('traits')
        assert all('research material' in s['source_company_context'] for s in candidate['portfolio_sources'])
    report = portfolio_coverage(data_dir=DATA, sources=sources(), varieties=[], entities=[], candidates=[])
    subject = next(s for s in report['subjects'] if COMPANY in s['entity_ids'])
    assert subject['source_status'] == 'partial' and subject['has_source_gaps']


def test_existing_human_identity_decisions_survive_new_research_context():
    human = dict(id='analyst-benihoppe', candidate_name='Benihoppe', berry_id='berry-strawberry',
                 status='reviewed', human_gated=True, reviewer='Analyst', identity_state='distinct',
                 aliases=['User spelling'], review_notes='Keep user judgment',
                 knowledge={'notes': 'User notes'}, photos=[{'operator': 'User photo'}])
    before = deepcopy(human)
    _, candidates = reconcile_portfolios(sources=sources(), varieties=[], entities=[], candidates=[human])
    result = next(c for c in candidates if c['id'] == human['id'])
    assert human == before
    for key in ('aliases', 'review_notes', 'knowledge', 'photos', 'identity_state', 'human_gated'):
        assert result[key] == before[key]
    assert any(s['id'] == SOURCE_ID for s in result['portfolio_sources'])
