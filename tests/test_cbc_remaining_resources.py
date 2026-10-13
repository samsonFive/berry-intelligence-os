"""Literal technical-document scope stays separate from approved identity/traits."""
from copy import deepcopy
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.services.variety_navigation import candidate_queue
from app.services.variety_portfolio_coverage import load_portfolio_observations, reconcile_portfolios

DATA = Path(__file__).resolve().parents[1] / 'data'
PREFIX = 'portfolio-cbc-resource-'
COMPANY = 'company-california-berry-cultivars'
POSTER = PREFIX + 'oxnard-grower-codes-2026'
CODES = {'118.060-601', '118.066-601', '121.008-601', '121.257-605'}


def sources():
    return load_portfolio_observations(DATA)


def reconcile(rows, candidates=()):
    return reconcile_portfolios(sources=rows, varieties=[],
                               entities=[dict(id=COMPANY, name='California Berry Cultivars', entity_type='company')],
                               candidates=list(candidates))


def test_complete_original_resources_account_for_literals_without_invented_dates_or_photos():
    rows, candidates = reconcile([s for s in sources() if s['id'].startswith(PREFIX)])
    assert len(rows) == 3 and sum(len(r['names']) for r in rows) == 8
    assert all(not r['accounting_view']['issues'] and r['capture_reference']['all_pages_read'] for r in rows)
    assert all(not r.get('published_date') for r in rows)
    poster = next(r for r in rows if r['id'] == POSTER)
    assert {n['candidate_name'] for n in poster['names']} == CODES
    assert all(n['candidate_name'] == n['breeder_code'] for n in poster['names'])
    assert not any(n.get('photos') or n.get('denomination') or n.get('trade_name') for r in rows for n in r['names'])
    cultivars = next(r for r in rows if r['id'].endswith('oxnard-cultivars-2026'))
    assert {n['candidate_name'] for n in cultivars['names']} == {'Adelanto', 'Belvedere', 'Castaic'}
    assert [e['label'] for e in cultivars['accounting_view']['exclusions']] == ['Fronteras']
    assert not any(c['candidate_name'] == 'Fronteras' for c in candidates)
    update = next(r for r in rows if r['id'].endswith('september-alturas-2026'))
    assert 'different denominators' in update['enumerated_scope']
    assert 'not independently verified market share' in update['names'][0]['portfolio_context']


def test_separate_document_pairings_are_reviewable_without_merging_nearby_codes():
    cbc = [s for s in sources() if COMPANY in s['company_ids']]
    _, candidates = reconcile(cbc)
    before = deepcopy(candidates)
    for code, label in [('118.060-601', 'Dunsmuir'), ('118.066-601', 'CBC030'),
                        ('121.008-601', 'CBC045'), ('121.257-605', 'CBC043')]:
        selected = candidate_queue(candidates, {'q': code, 'source': POSTER})['candidates']
        assert [c['candidate_name'] for c in selected] == [code]
        field = selected[0]
        named = next(c for c in candidates if c['candidate_name'] == label)
        assert field['id'] != named['id']
        assert len(field['portfolio_sources']) == 1
        assert label in field['portfolio_sources'][0]['portfolio_context']
        assert not field['aliases'] and not field['human_gated'] and not field['auto_confirmed']
        assert not field['registration']['official_registry_source']
        assert not field['deployment'] and not field['proposed_relationships']
    assert candidates == before


def test_replay_preserves_old_anchors_and_operator_rejection_of_literal_code():
    all_rows = sources()
    _, old = reconcile([s for s in all_rows if not s['id'].startswith(PREFIX)])
    _, new = reconcile(all_rows)
    old_ids = {(c['candidate_name'], c['berry_id'], c['id']) for c in old}
    new_ids = {(c['candidate_name'], c['berry_id'], c['id']) for c in new}
    assert old_ids <= new_ids
    assert {name for name, _, _ in new_ids - old_ids} == CODES
    operator = dict(id='operator-field-code', candidate_name='118.060-601', berry_id='berry-strawberry',
                    status='rejected', human_gated=True, identity_state='rejected',
                    review_notes='Keep separate', aliases=['My alias'], registration={'status': 'My status'})
    before = deepcopy(operator)
    rows, merged = reconcile(all_rows, [operator])
    saved = next(c for c in merged if c['id'] == operator['id'])
    assert operator == before and all(saved[k] == v for k, v in before.items())
    assert next(n for r in rows if r['id'] == POSTER for n in r['names']
                if n['candidate_name'] == '118.060-601')['status'] == 'previously_rejected'


def test_literal_source_scope_renders_privately_without_promoting_or_writing(monkeypatch, tmp_path):
    _, candidates = reconcile([s for s in sources() if COMPANY in s['company_ids']])
    before = deepcopy(candidates)
    monkeypatch.setattr(main, 'INBOX_DIR', tmp_path)
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    monkeypatch.setattr(main, 'variety_candidate_universe', lambda: ([], candidates, {}))
    client = TestClient(main.app)
    page = client.get('/varieties/candidates', params={'company': COMPANY, 'source': POSTER, 'q': '118.060-601'})
    assert page.status_code == 200 and '1 of 19' in page.text
    assert 'this poster prints only the field code' in page.text
    assert 'Ox26GwrPst_EN.jpeg' in page.text
    assert candidates == before and not list(tmp_path.rglob('*.json'))
    monkeypatch.setattr(main, 'AUTHORING_MODE', False)
    assert client.get('/varieties/candidates', params={'source': POSTER}).status_code == 403
