"""Named source links do not approve rights, traits, photographs or identities."""
from copy import deepcopy
from pathlib import Path

from app.services.company_variety_discoveries import company_variety_discoveries
from app.services.variety_portfolio_coverage import load_portfolio_observations, reconcile_portfolios

DATA = Path(__file__).resolve().parents[1] / 'data'


def sources():
    return [s for s in load_portfolio_observations(DATA) if s['id'].startswith('portfolio-santorsola-')]


def test_source_claims_and_programme_date_do_not_become_rights_traits_or_photos():
    original = sources()
    before = deepcopy(original)
    rows, candidates = reconcile_portfolios(sources=original, varieties=[], entities=[], candidates=[])
    assert len(rows) == 3 and len(candidates) == 11
    assert {c['berry_id'] for c in candidates} == {'berry-strawberry', 'berry-raspberry'}
    assert all(not c['aliases'] and not c['proposed_relationships'] and not c['registration']['status'] for c in candidates)
    assert all(not s.get('published_date') and not s['capture_reference']['full_technical_sheets_checked'] for s in rows)
    assert not any(n.get('photos') for s in original for n in s['names'])
    assert sum(s['needs_follow_up'] for s in rows) == 1
    assert original == before


def test_company_discoveries_keep_name_specific_original_document_links():
    rows, _ = reconcile_portfolios(sources=sources(), varieties=[], entities=[], candidates=[])
    company = company_variety_discoveries(entity_id='company-sant-orsola', sources=rows)
    assert len(company['rows']) == 11
    names = {r['name'] for r in company['rows']}
    assert {'Delfi', 'Dolomia Plus', 'Lagorai Plus', 'Ofelia', 'Sungold'} <= names
    assert 'Enrosadira' not in names and 'Fragola' not in names and 'Lampone' not in names
    source_rows = [n for s in sources() for n in s['names']]
    assert len({n['product_url'] for n in source_rows}) == 11
    assert all(n['product_url'].startswith('https://www.santorsola.com/2020/wp-content/uploads/') and n['product_url'].endswith('.pdf') for n in source_rows)
    assert not company_variety_discoveries(entity_id='company-unrelated', sources=rows)['rows']


def test_replay_keeps_human_rejection_and_user_notes():
    human = dict(id='human-sungold', candidate_name='Sungold', berry_id='berry-raspberry',
                 status='rejected', identity_state='rejected', human_gated=True,
                 review_notes='Keep my decision', knowledge={'notes': 'My notes'})
    before = deepcopy(human)
    rows, candidates = reconcile_portfolios(sources=sources(), varieties=[], entities=[], candidates=[human])
    retained = next(c for c in candidates if c['id'] == human['id'])
    assert retained['review_notes'] == 'Keep my decision' and retained['knowledge'] == before['knowledge']
    assert human == before
    company = company_variety_discoveries(entity_id='company-sant-orsola', sources=rows)
    assert not any(r['name'] == 'Sungold' for r in company['rows'])
