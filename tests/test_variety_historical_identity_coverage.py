"""Older release sources retain bounded scope and source-specific identities."""
from copy import deepcopy
from pathlib import Path

from fastapi.testclient import TestClient
from app import main
from app.services.variety_navigation import candidate_queue
from app.services.variety_portfolio_coverage import load_portfolio_observations, reconcile_portfolios

ROOT = Path(__file__).resolve().parents[1]

def reconcile(sources, varieties=None, candidates=None):
    return reconcile_portfolios(sources=sources, varieties=varieties or [], entities=[], candidates=candidates or [])

def source(sid, name, code='', berry='berry-raspberry', company='one'):
    row = dict(candidate_name=code or name, berry_id=berry)
    if code:
        row.update(breeder_code=code, trade_name=name)
    return dict(id=sid, title=sid, url='https://example.test/'+sid, checked_on='2026-10-07',
        company_ids=[company], berry_ids=[berry], names=[row], source_type='breeder_release_record',
        capture_status='names_enumerated')

def test_shared_name_is_not_an_automatic_catalog_match_across_source_contexts():
    sources = [source('current', 'Lewis'), source('older', 'Lewis', 'ORUS 576-47', company='other')]
    varieties = [dict(id='v-lewis', entity_type='variety', name='Lewis', berry_ids=['berry-raspberry'])]
    original = deepcopy(sources)
    rows, candidates = reconcile(sources, varieties)
    assert len(candidates) == 2 and len({c['id'] for c in candidates}) == 2
    assert all(r['matched'] == 0 and r['names'][0]['identity_notes'] for r in rows)
    assert {c['candidate_name'] for c in candidate_queue(candidates, {'q': 'Lewis'})['candidates']} == {'Lewis', 'ORUS 576-47'}
    assert all(not c['auto_confirmed'] and not c['human_gated'] for c in candidates)
    assert sources == original
    assert all(not c['proposed_relationships'] and not c['deployment'] for c in candidates)

def test_existing_human_identity_and_edits_win_with_warning_retained():
    sources = [source('current', 'Lewis'), source('older', 'Lewis', 'ORUS 576-47', company='other')]
    varieties = [dict(id='v-lewis', entity_type='variety', name='Lewis', berry_ids=['berry-raspberry'])]
    _, candidates = reconcile(sources, varieties)
    human = {**candidates[0], 'human_gated': True, 'identity_state': 'confirmed_same',
        'candidate_canonical_match': 'v-lewis', 'review_notes': 'Verified this source separately', 'knowledge': {'notes': 'User edit'}}
    rejected = {**candidates[1], 'human_gated': True, 'status': 'rejected', 'review_notes': 'Human rejection'}
    originals = deepcopy([human, rejected])
    rows, visible = reconcile(sources, varieties, originals)
    assert rows[0]['matched'] == 1 and rows[0]['names'][0]['identity_notes']
    assert rows[1]['closed'] == 1
    assert originals == [human, rejected]
    assert visible[0]['knowledge'] == human['knowledge'] and visible[1]['review_notes'] == rejected['review_notes']

def test_different_codes_across_programs_are_advisory_not_distinct_decisions():
    rows, candidates = reconcile([source('one', 'Shared', 'CODE 1'), source('two', 'Shared', 'CODE 2', company='other')])
    assert all('different codes' in r['names'][0]['identity_notes'][0] for r in rows)
    assert len(candidates) == 2 and not any(c['human_gated'] for c in candidates)
    # Same literal code after normalization is not a discrepancy, nor is a name in another crop.
    rows, _ = reconcile([source('one', 'Shared', 'CODE 1'), source('two', 'Shared', 'code-1'),
        source('three', 'Shared', berry='berry-strawberry')])
    assert all(not r['names'][0]['identity_notes'] for r in rows)

def test_different_codes_do_not_collapse_when_sources_use_the_label_as_candidate_name():
    sources = [source('one', 'Shared', 'CODE 1'), source('two', 'Shared', 'CODE 2', company='other')]
    for s in sources:
        s['names'][0]['candidate_name'] = 'Shared'
    original = deepcopy(sources)
    varieties = [dict(id='v-shared', name='Shared', entity_type='variety', berry_ids=['berry-raspberry'])]
    rows, candidates = reconcile(sources, varieties)
    assert all(r['matched'] == 0 and r['names'][0]['identity_notes'] for r in rows)
    assert {c['candidate_name'] for c in candidates} == {'CODE 1', 'CODE 2'}
    assert len({c['id'] for c in candidates}) == 2 and sources == original
    assert all(c['trade_name'] == 'Shared' and len(c['portfolio_sources']) == 1 for c in candidates)
    # A code-specific human decision still applies on replay; an uncoded decision
    # is retained but must not be copied to both new code-specific leads.
    human = {**candidates[0], 'candidate_name': 'Shared', 'human_gated': True,
             'identity_state': 'confirmed_same', 'candidate_canonical_match': 'v-shared', 'review_notes': 'Code 1 checked'}
    uncoded = dict(id='vcand-human', candidate_name='Shared', berry_id='berry-raspberry',
                   human_gated=True, status='rejected', review_notes='Earlier uncoded lead')
    rows, visible = reconcile(sources, varieties, [human, uncoded])
    assert rows[0]['matched'] == 1 and rows[1]['matched'] == 0
    assert next(c for c in visible if c['id'] == human['id'])['review_notes'] == 'Code 1 checked'
    assert next(c for c in visible if c['id'] == uncoded['id']) == {**uncoded, 'portfolio_sources': [], 'portfolio_identity_notes': []}

def test_two_codes_under_one_label_in_one_source_still_require_separate_review():
    s = source('one', 'Shared', 'CODE 1')
    s['names'] = [dict(candidate_name='Shared', breeder_code=code, berry_id='berry-raspberry')
                  for code in ['CODE 1', 'CODE 2']]
    rows, candidates = reconcile([s], [dict(id='v1', name='Shared', berry_ids=['berry-raspberry'])])
    assert rows[0]['matched'] == 0 and len(candidates) == 2
    assert len({c['id'] for c in candidates}) == 2
    assert all(n['identity_notes'] for n in rows[0]['names'])

def test_historical_sources_keep_comparators_and_unread_pedigree_out_of_release_claims():
    sources = load_portfolio_observations(ROOT / 'data')
    selected = [s for s in sources if s['id'] in {'portfolio-hutton-legacy-raspberry-list', 'portfolio-usda-lewis-2001-paper'}]
    rows, candidates = reconcile(selected)
    hutton = next(r for r in rows if 'hutton' in r['id'])
    paper = next(r for r in rows if 'usda' in r['id'])
    assert len(hutton['names']) == 6 and all(n['product_url'].endswith('.asp') for n in hutton['names'])
    assert paper['capture_status'] == 'partial' and paper['needs_follow_up']
    assert len(paper['names']) == 13 and paper['accounting_view']['accounted_items'] == 16
    assert {e['label'] for e in paper['accounting_view']['exclusions']} == {'ORUS 1570', 'ORUS 1748', 'Centennial'}
    assert not {'ORUS 1570', 'ORUS 1748', 'Centennial'} & {c['candidate_name'] for c in candidates}
    assert all('published_date' not in s for s in selected)
    assert not any(c['breeder_owner'] or c['proposed_relationships'] or c['deployment'] for c in candidates)

def test_reader_routes_expose_both_lewis_leads_read_only_in_authoring(monkeypatch, tmp_path):
    monkeypatch.setattr(main, 'INBOX_DIR', tmp_path)
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    client = TestClient(main.app)
    response = client.get('/varieties/candidates?q=Lewis')
    assert response.status_code == 200 and 'ORUS 576-47' in response.text
    assert 'Check whether they refer to the same variety' in response.text
    assert 'ORUS 576-47 · Lewis' in response.text and 'Check shared name' in response.text
    assert 'Identity unresolved' in response.text
    assert 'Lewismanuscript.pdf' in response.text
    assert not list(tmp_path.rglob('*'))
    monkeypatch.setattr(main, 'AUTHORING_MODE', False)
    assert client.get('/varieties/candidates?q=Lewis').status_code == 403
