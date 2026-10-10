"""Original Chandler references retain crop, grant scope and human decisions."""
from copy import deepcopy
import json
from pathlib import Path

from app.services.variety_navigation import candidate_queue
from app.services.variety_patent_references import original_patent_references
from app.services.variety_portfolio_coverage import load_portfolio_observations, reconcile_portfolios

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'portfolio-chandler-original-'


def inputs():
    sources = load_portfolio_observations(ROOT / 'data')
    entities = [json.loads(p.read_text(encoding='utf-8')) for p in (ROOT / 'data/entities').rglob('*.json')]
    varieties = [row for row in entities if row.get('entity_type') == 'variety']
    return sources, entities, varieties


def test_original_selection_codes_and_assignee_are_searchable_without_approved_aliases_or_roles():
    sources, entities, varieties = inputs()
    before = deepcopy(sources)
    rows, candidates = reconcile_portfolios(sources=sources, entities=entities, varieties=varieties,
        candidates=[], source_ids={s['id'] for s in sources if s['id'].startswith(PREFIX)})
    focal = next(s for s in rows if s['source_type'] == 'plant_patent')
    assert focal['companies'] == [] and focal['names'][0]['source_company_ids'] == []
    assert all(not r['accounting_view']['issues'] for r in rows)
    assert focal['capture_reference']['visually_reviewed_pages'] == [1, 2]
    assert not focal['capture_reference']['current_legal_status_verified']
    assert not focal['capture_reference']['reuse_permission_verified']
    for query in ('Cal 77.32-103', 'C24', 'Regents of the University of California'):
        selected = candidate_queue(candidates, {'q': query})['candidates']
        assert [c['candidate_name'] for c in selected] == ['Chandler']
    focal_lead = next(c for c in candidates if c['candidate_name'] == 'Chandler')
    assert focal_lead['registration']['grant_number'] == 'USPP5262P'
    assert focal_lead['registration']['application_date'] == '1982-12-23'
    assert not focal_lead['aliases'] and not focal_lead['proposed_relationships']
    assert not focal_lead['applicant'] and not focal_lead['breeder_owner']
    assert not focal_lead['registration']['status'] and not focal_lead['registration']['official_registry_source']
    assert not focal_lead['human_gated'] and not focal_lead['auto_confirmed']
    assert sources == before


def test_parent_codes_and_comparators_do_not_inherit_the_chandler_grant_or_figures():
    sources, entities, varieties = inputs()
    selected = [s for s in sources if s['id'].startswith(PREFIX)]
    rows, candidates = reconcile_portfolios(sources=selected, entities=entities, varieties=varieties, candidates=[])
    historic = next(r for r in rows if r['source_type'] == 'historical_document_mentions')
    assert {r['candidate_name'] for r in historic['names']} == {'Douglas', 'Cal 72.361-105', 'Tioga', 'Aliso', 'Tufts', 'Aiko', 'Pajaro'}
    assert all(not r.get('grant_number') and not r.get('photos') for r in historic['names'])
    assert 'claim_url' not in historic['capture_reference'] and 'figures_url' not in historic['capture_reference']
    assert [c['candidate_name'] for c in candidate_queue(candidates, {'q': 'C55'})['candidates']] == ['Cal 72.361-105']
    for lead in candidates:
        if lead['candidate_name'] != 'Chandler':
            assert not lead['registration']['grant_number'] and not lead['registration']['application_number']


def test_original_strawberry_grant_cannot_attach_to_a_same_named_blueberry_or_reverse_human_review():
    sources, _, _ = inputs()
    selected = [s for s in sources if s['id'] == PREFIX + 'us-grant']
    blueberry = dict(id='fictional-blueberry-chandler', entity_type='variety', name='Chandler', aliases=[], berry_ids=['berry-blueberry'])
    strawberry = dict(id='fictional-strawberry-chandler', entity_type='variety', name='Chandler', aliases=[], berry_ids=['berry-strawberry'])
    def refs(target, candidates=()):
        return original_patent_references(variety=target, varieties=[blueberry, strawberry], entities=[],
            candidates=list(candidates), sources=selected)
    assert refs(blueberry) == []
    result = refs(strawberry)
    assert len(result) == 1 and result[0]['number'] == 'USPP5262P'
    assert result[0]['claim_url'].endswith('#claims') and result[0]['figures_url'].endswith('#page=2')
    assert result[0]['published_date'] == '1984-07-24'
    assert not {'owner', 'current_rights', 'photo_permission', 'legal_status'} & result[0].keys()
    for status, identity in (('rejected', 'rejected'), ('reviewed', 'distinct')):
        human = dict(id='operator-chandler', candidate_name='Chandler', berry_id='berry-strawberry',
            human_gated=True, status=status, identity_state=identity, aliases=['User spelling'],
            review_notes='Keep my notes', registration={'status': 'User status'}, photos=[{'operator': 'Keep'}])
        before = deepcopy(human)
        _, candidates = reconcile_portfolios(sources=selected, entities=[], varieties=[strawberry], candidates=[human])
        saved = next(c for c in candidates if c['id'] == human['id'])
        assert all(saved[k] == before[k] for k in ('status', 'identity_state', 'aliases', 'review_notes', 'registration', 'photos'))
        assert refs(strawberry, [human]) == [] and human == before


def test_additive_observations_preserve_existing_candidate_anchors():
    sources, entities, varieties = inputs()
    _, old = reconcile_portfolios(sources=[s for s in sources if not s['id'].startswith(PREFIX)], entities=entities,
        varieties=varieties, candidates=[])
    _, current = reconcile_portfolios(sources=sources, entities=entities, varieties=varieties, candidates=[])
    ids = {(c['berry_id'], c['candidate_name']): c['id'] for c in current}
    assert all(ids[(c['berry_id'], c['candidate_name'])] == c['id'] for c in old)
