"""A multi-program journal snapshot must not become trusted catalog or rights data."""
from copy import deepcopy
from pathlib import Path

from app.services.variety_portfolio_coverage import load_portfolio_observations, reconcile_portfolios
from app.services.variety_patent_references import original_patent_references

DATA = Path(__file__).resolve().parents[1] / 'data'
PREFIX = 'portfolio-register52-2024-'


def test_checked_headings_account_for_referrals_and_unresolved_glyphs():
    sources = [s for s in load_portfolio_observations(DATA) if s['id'].startswith(PREFIX)]
    assert len(sources) == 8
    assert sum(len(s['names']) for s in sources) == 388
    assert sum(s['accounting']['observed_items'] for s in sources) == 398
    assert sum(len(s['accounting']['exclusions']) for s in sources) == 10
    rows, candidates = reconcile_portfolios(sources=sources, varieties=[], entities=[], candidates=[])
    assert all(s['capture_status'] == 'partial' and not s['company_ids'] for s in sources)
    assert all(r['needs_follow_up'] and not r['accounting_view']['issues'] for r in rows)
    names = {(n['berry_id'], n['candidate_name']) for s in sources for n in s['names']}
    assert ('berry-blackberry', 'América') in names
    assert ('berry-strawberry', 'FL 17.15-86') in names
    assert ('berry-strawberry', 'Florida Beauty') not in names  # parent/continuation, not a heading
    assert ('berry-raspberry', 'Lewis') not in names  # referral, not another described entry
    assert ('berry-raspberry', 'Bonnie Lewis') in names
    assert all('Ml-' not in n for _, n in names)
    assert ('berry-blackberry', 'APF-268') in names and ('berry-blackberry', 'APF-268T') not in names
    assert all(not c['human_gated'] and not c['auto_confirmed'] and not c['registration']['official_registry_source'] for c in candidates)
    assert all(not c['breeder_owner'] and not c['proposed_relationships'] and not c['deployment'] for c in candidates)


def test_register_replay_preserves_prior_ids_and_rejected_operator_record():
    sources = load_portfolio_observations(DATA)
    prior_sources = [s for s in sources if not s['id'].startswith(PREFIX)]
    _, old = reconcile_portfolios(sources=prior_sources, varieties=[], entities=[], candidates=[])
    _, added = reconcile_portfolios(sources=sources, varieties=[], entities=[], candidates=[])
    by_key = {(c['candidate_name'], c['berry_id']): c for c in added}
    assert all(by_key[c['candidate_name'], c['berry_id']]['id'] == c['id'] for c in old)
    human = deepcopy(next(c for c in old if c['candidate_name'] == 'Colossus' and c['berry_id'] == 'berry-blueberry'))
    human.update(status='rejected', human_gated=True, identity_state='rejected', review_notes='Operator rejected this pairing', photos=[{'operator_choice':'Retain'}])
    original = deepcopy(human)
    variety = {'id':'variety-colossus','name':'Colossus','entity_type':'variety','berry_ids':['berry-blueberry']}
    rows, saved = reconcile_portfolios(sources=sources, varieties=[variety], entities=[], candidates=[human])
    actual = next(c for c in saved if c['id'] == human['id'])
    fields = ('id','candidate_name','berry_id','status','human_gated','identity_state','review_notes','photos','aliases','registration')
    assert all(actual[k] == original[k] for k in fields) and human == original
    register = next(r for r in rows if r['id'] == PREFIX + 'blueberry-main')
    colossus = next(n for n in register['names'] if n['candidate_name'] == 'Colossus')
    assert colossus['catalog_id'] is None and colossus['status'] == 'previously_rejected'
    assert colossus['product_url'].endswith('#page=12')


def test_journal_rights_citations_are_not_original_official_filings():
    sources = [s for s in load_portfolio_observations(DATA) if s['id'].startswith(PREFIX)]
    variety = {'id':'variety-colossus','name':'Colossus','entity_type':'variety','berry_ids':['berry-blueberry']}
    assert not original_patent_references(variety=variety,varieties=[variety],entities=[],candidates=[],sources=sources)
    assert all(not s['capture_reference']['current_legal_status_verified'] and not s['capture_reference']['reuse_permission_verified'] for s in sources)
