"""Original naming evidence cannot approve aliases or lend a grant to parents."""
from copy import deepcopy
import json
from pathlib import Path

from app.services.variety_navigation import candidate_queue
from app.services.variety_patent_references import original_patent_references
from app.services.variety_portfolio_coverage import load_portfolio_observations, reconcile_portfolios

ROOT = Path(__file__).resolve().parents[1]


def inputs():
    sources = load_portfolio_observations(ROOT / 'data')
    entities = [json.loads(p.read_text(encoding='utf-8')) for p in (ROOT / 'data/entities').rglob('*.json')]
    varieties = [r for r in entities if r.get('entity_type') == 'variety']
    selected = {s['id'] for s in sources if s['id'].startswith('portfolio-rutgers-original-grant-')}
    return sources, entities, varieties, selected


def test_original_code_and_trade_name_are_searchable_without_catalog_or_company_approval():
    sources, entities, varieties, selected = inputs()
    before = deepcopy(sources)
    sections, candidates = reconcile_portfolios(sources=sources, entities=entities, varieties=varieties,
                                               candidates=[], source_ids=selected)
    focal = next(s for s in sections if s['source_type'] == 'plant_patent')
    name = focal['names'][0]
    assert name['candidate_name'] == 'NJ09-2-1' and name['trade_name'] == "Rutgers D'Light"
    assert name['catalog_id'] is None and name['status'] == 'needs_review'
    assert focal['companies'] == [] and name['source_company_ids'] == []
    queue = candidate_queue(candidates, {'q':"Rutgers D'Light"})
    assert [c['candidate_name'] for c in queue['candidates']] == ['NJ09-2-1']
    assert all(not c['human_gated'] and not c['auto_confirmed'] for c in candidates)
    canonical = next(v for v in varieties if v['id'] == 'variety-rutgers-dlight')
    assert original_patent_references(variety=canonical, varieties=varieties, entities=entities,
                                      candidates=[], sources=sources) == []
    assert sources == before


def test_historical_parent_and_comparison_names_do_not_inherit_the_focal_grant():
    sources, entities, varieties, selected = inputs()
    sections, candidates = reconcile_portfolios(sources=sources, entities=entities, varieties=varieties,
                                               candidates=[], source_ids=selected)
    historical = next(s for s in sections if s['source_type'] == 'historical_document_mentions')
    assert {r['candidate_name'] for r in historical['names']} == {'NJ6-13-1', 'NJ03-232-2', 'NJ08-08-6', 'Chandler'}
    assert not any(r.get('grant_number') or r.get('application_number') or r.get('photos') for r in historical['names'])
    assert all(not s['accounting_view']['issues'] for s in sections)
    for name in ('NJ6-13-1', 'NJ03-232-2'):
        lead = next(c for c in candidates if c['candidate_name'] == name)
        assert not lead['registration']['grant_number']
        assert {r['source_type'] for r in lead['portfolio_sources']} == {'historical_document_mentions'}


def test_filing_links_respect_existing_human_rejection_and_separate_claim_and_figures():
    sources, entities, varieties, selected = inputs()
    human = dict(id='saved-rutgers-decision', candidate_name='NJ09-2-1', berry_id='berry-strawberry',
                 status='rejected', human_gated=True, identity_state='rejected', review_notes='Keep this decision')
    sections, candidates = reconcile_portfolios(sources=sources, entities=entities, varieties=varieties,
                                               candidates=[human], source_ids=selected)
    focal = next(s for s in sections if s['source_type'] == 'plant_patent')
    assert focal['names'][0]['status'] == 'previously_rejected'
    saved = next(c for c in candidates if c['id'] == human['id'])
    assert saved['review_notes'] == human['review_notes'] and saved['status'] == 'rejected'
    capture = focal['capture_reference']
    assert capture['claim_page'] == 3 and capture['trade_name_page'] == 2 and capture['fruit_page'] == 4
    assert capture['claim_url'].endswith('#claims') and capture['figures_url'].endswith('#page=4')
    assert capture['visually_reviewed_pages'] == [1, 2, 3, 4, 6]
    assert not capture['current_legal_status_verified'] and not capture['reuse_permission_verified']
