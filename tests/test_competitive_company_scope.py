"""Shared company scope must not broaden exports or mutate a saved comparison."""
from copy import deepcopy
import json
import re

import pytest

from app import main, competitive_routes
from app.services import company_directory, feed_first, personal_digest, personal_scope
from app.services import competitive_evaluation as ce
from app.services.living_workspaces import Store
from tests.test_competitive_routes import client  # noqa: F401
from tests.test_competitive_evaluation import research  # noqa: F401


@pytest.fixture
def scoped(client, monkeypatch):
    http, research = client
    inbox, entities, scope, *_ = research
    monkeypatch.setattr(company_directory.seed_roster, 'build_roster', lambda _: [])
    monkeypatch.setattr(main, 'all_relationships', lambda: [
        {'id': 'edge-one-two', 'subject_id': 'company-one', 'object_id': 'company-two',
         'predicate': 'partners_with', 'status': 'active', 'evidence_ids': []}])
    state = feed_first.empty_state()
    state.update(entity_favorites={'company-one': True}, entity_tiers={'company-one': 'tier1'},
                 company_lists={'one': {'name': 'First peers', 'company_ids': ['company-one', 'unknown-retained']},
                                'two': {'name': 'Second peers', 'company_ids': ['company-two']}})
    feed_first.save_state(inbox, state)
    store = Store(inbox)
    with store.transaction() as db:
        for entity in entities:
            store.put(db, 'competitive_record', {'id': 'person-' + entity, 'kind': 'person',
                'entity_id': entity, 'batch_id': 'B16', 'local_id': 'P-' + entity,
                'fields': {'name_original': 'Person of ' + entity, 'role_title': 'Breeder',
                           'last_observed_date': '2026-10-30'}, 'resolution': 'accepted_structure', 'source_refs': []}, 'fixture')
        second = {**scope, 'entity_id': 'company-two'}
        store.put(db, 'capability_automatic', {'id': ce.scope_key(second), **second,
            'rating': 'unknown', 'status': 'unscored', 'confidence': 'unknown',
            'rationale': 'Fixture only', 'assessed_at': '2026-10-30', 'basis': 'fixture',
            'observation_ids': [], 'source_ids': []}, 'fixture')
    return http, inbox, entities


@pytest.mark.parametrize('query,expected', [
    ({'favorites': '1'}, ['company-one']),
    ({'company_tier': 'tier1'}, ['company-one']),
    ({'company_tier': 'untiered'}, ['company-two']),
    ({'list': 'two'}, ['company-two']),
    ({'list': 'two', 'favorites': '1'}, []),
    ({'companies': 'company-one,company-two', 'list': 'one'}, ['company-one']),
    ({'companies': 'company-one', 'list': 'two'}, []),
    ({'empty_cohort': '1'}, []),
])
def test_company_scope_applies_to_complete_exports_records_and_graph(scoped, query, expected):
    http, inbox, entities = scoped
    before = deepcopy(feed_first.load_state(inbox))
    response = http.get('/competitive-evaluation/export/json', params=query)
    assert response.status_code == 200
    model = response.json()
    assert model['selected'] == expected
    assert {row['entity_id'] for row in model['assessments']} == set(expected)
    assert all(row.get('entity_id') in expected for row in model['records'])
    assert all(row.get('entity_id') in expected for row in model['people_rows'])
    csv = http.get('/competitive-evaluation/records.csv', params={**query, 'view': 'people'})
    assert csv.status_code == 200
    for entity in entities:
        assert ('Person of ' + entity in csv.text) == (entity in expected)
    if not expected:
        assert not model['records'] and not model['assessments'] and not model['graph'] and not model['jobs']
        assert model['empty_cohort']
    else:
        assert not model['empty_cohort']
        assert model['graph'][0]['id'] == 'edge-one-two'  # Counterparty context stays attributed.
    # Original source references remain available even when a source row has no entity_id.
    if 'company-one' in expected:
        assert model['assessments'][0]['sources'][0]['fields']['original_url'] == 'https://example.org/design'
    assert feed_first.load_state(inbox) == before


@pytest.mark.parametrize('view', ['matrix', 'overview', 'plot', 'relationships', 'exposure', 'people', 'imports', 'saved'])
def test_every_live_view_keeps_shared_filter_controls_and_empty_scope(scoped, view):
    http, _, _ = scoped
    page = http.get('/competitive-evaluation', params={'view': view, 'list': 'two', 'favorites': '1', 'companies': 'company-one'})
    assert page.status_code == 200
    assert 'name="list"' in page.text and 'name="company_tier"' in page.text and 'name="favorites"' in page.text
    assert '0 companies' in page.text and 'Shared company scope' in page.text
    assert 'Excluded: company-one' in page.text
    match = re.search(r'id="ce-coverage-context">(.*?)</script>', page.text)
    context = json.loads(match[1])
    assert context['empty_cohort'] is True and context['companies'] == []
    assert 'company_tier' not in context  # The archive receives resolved IDs, never personal state.


@pytest.mark.parametrize('query', [{'favorites': 'true'}, {'company_tier': 'Tier 1'}, {'list': 'missing'}, {'empty_cohort': 'maybe'}])
def test_invalid_shared_scope_is_422_in_screen_and_both_exports(scoped, query):
    http, _, _ = scoped
    for path in ('/competitive-evaluation', '/competitive-evaluation/export/json', '/competitive-evaluation/records.csv'):
        assert http.get(path, params=query).status_code == 422


def test_saved_comparison_and_record_csv_stay_frozen_after_list_archive_and_new_records(scoped):
    http, inbox, _ = scoped
    saved_response = http.post('/competitive-evaluation/save', data={
        'scope': json.dumps({'list': 'one', 'company_tier': 'tier1'}), 'title': 'Captured first peers', 'narrative': 'Original analyst wording'})
    assert saved_response.status_code == 200
    store = Store(inbox)
    saved = store.rows('competitive_comparison')[0]
    before = deepcopy(saved)
    params = {'saved': saved['id']}
    captured = http.get('/competitive-evaluation/export/json', params=params).json()
    assert captured['selected'] == ['company-one'] and captured['tracking_scope']['labels'] == ['Tier 1', 'First peers']
    personal_digest.edit_list(inbox, action='archive', list_id='one', allowed_companies={'company-one', 'company-two'})
    company_directory.mark(inbox, entity_id='company-one', action='tier', value='tier3', allowed={'company-one', 'company-two'})
    with store.transaction() as db:
        store.put(db, 'competitive_record', {'id': 'new-person', 'kind': 'person', 'entity_id': 'company-one',
            'batch_id': 'B16', 'local_id': 'P-new', 'fields': {'name_original': 'Added after snapshot'},
            'resolution': 'accepted_structure', 'source_refs': []}, 'fixture')
    assert http.get('/competitive-evaluation/export/json', params=params).json() == captured
    page = http.get('/competitive-evaluation', params={**params, 'view': 'people'})
    assert page.status_code == 200 and 'Captured company scope' in page.text and 'First peers' in page.text
    assert 'Added after snapshot' not in page.text
    csv = http.get('/competitive-evaluation/records.csv', params={**params, 'view': 'people'})
    assert csv.status_code == 200 and 'Person of company-one' in csv.text
    assert 'Added after snapshot' not in csv.text and 'Person of company-two' not in csv.text
    http.post('/competitive-evaluation/save', data={
        'scope': json.dumps({'companies': 'company-two'}), 'title': 'Unrelated second comparison'})
    index = http.get('/competitive-evaluation', params={**params, 'view': 'saved'})
    assert index.status_code == 200 and 'Unrelated second comparison' not in index.text
    assert store.get(saved['id']) == before


def test_empty_snapshot_never_becomes_all_after_company_preferences_change(scoped):
    http, inbox, _ = scoped
    http.post('/competitive-evaluation/save', data={'scope': json.dumps({'list': 'two', 'favorites': '1'}), 'title': 'Empty captured scope'})
    saved = Store(inbox).rows('competitive_comparison')[0]
    company_directory.mark(inbox, entity_id='company-two', action='favorite', value='1', allowed={'company-one', 'company-two'})
    assert http.get('/competitive-evaluation/export/json', params={'list': 'two', 'favorites': '1'}).json()['selected'] == ['company-two']
    snapshot = http.get('/competitive-evaluation/export/json', params={'saved': saved['id']}).json()
    assert snapshot['selected'] == [] and not snapshot['assessments'] and not snapshot['records']
    assert snapshot['empty_cohort']
    assert '0 companies' in http.get('/competitive-evaluation', params={'saved': saved['id']}).text
    assert 'Person of ' not in http.get('/competitive-evaluation/records.csv', params={'saved': saved['id'], 'view': 'people'}).text


def test_scope_is_shared_but_digest_details_are_not_serialized(scoped):
    _, inbox, entities = scoped
    with personal_scope.bind('Alice', 'Alice'):
        state = feed_first.load_state(inbox)
        state['digest_subscriptions'] = ['one']
        state['decisions'] = {'ALICE_PRIVATE_STORY': {'saved': True}}
        feed_first.save_state(inbox, state)
    with personal_scope.bind('Bob', 'Alice'):
        result = competitive_routes.company_scope(main, entities, {'favorites': '1', 'list': 'one'})
        assert result['selected'] == ['company-one']
        assert 'ALICE_PRIVATE_STORY' not in repr(result) and 'subscribed' not in repr(result)
        assert not feed_first.load_state(inbox)['digest_subscriptions']


def test_existing_legacy_tier_is_displayed_and_filterable_without_reassignment(scoped):
    http, inbox, _ = scoped
    state = feed_first.load_state(inbox)
    state['entity_tiers']['company-one'] = 'watch'
    feed_first.save_state(inbox, state)
    model = http.get('/competitive-evaluation/export/json?company_tier=watch').json()
    assert model['selected'] == ['company-one'] and model['tracking_scope']['labels'] == ['Legacy watch']
    assert feed_first.load_state(inbox)['entity_tiers']['company-one'] == 'watch'


def test_preexisting_snapshot_without_tracking_metadata_still_opens_unchanged(scoped):
    http, inbox, _ = scoped
    http.post('/competitive-evaluation/save', data={'scope': json.dumps({'companies': 'company-one'}), 'title': 'Historical format'})
    store = Store(inbox)
    saved = store.rows('competitive_comparison')[0]
    for key in ('tracking_scope', 'requested_companies', 'empty_cohort'):
        saved['snapshot'].pop(key)
    with store.transaction() as db:
        saved = store.put(db, 'competitive_comparison', saved, 'old-format fixture', expected=saved['version'])
    before = deepcopy(saved)
    assert http.get('/competitive-evaluation', params={'saved': saved['id']}).status_code == 200
    assert http.get('/competitive-evaluation/export/json', params={'saved': saved['id']}).json() == saved['snapshot']
    assert store.get(saved['id']) == before


def test_actual_coverage_script_uses_resolved_and_frozen_cohorts():
    from pathlib import Path
    import shutil
    import subprocess
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is unavailable for the existing browser script unit check')
    root = Path(__file__).resolve().parents[1]
    for name in ('competitive_sheet.js', 'competitive_coverage.js'):
        syntax = subprocess.run([node, '--check', str(root / 'app/static' / name)],
                                capture_output=True, text=True, timeout=20)
        assert syntax.returncode == 0, syntax.stderr
    result = subprocess.run([node, str(root / 'tests/competitive_company_scope_checks.cjs')],
                            cwd=root, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert 'Five real-script coverage handoff cases pass' in result.stdout
