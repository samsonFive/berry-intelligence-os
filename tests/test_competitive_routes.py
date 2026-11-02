import json

import pytest
from fastapi.testclient import TestClient

from app import main, competitive_routes
from app.services import competitive_evaluation as ce
from tests.test_competitive_evaluation import research


@pytest.fixture
def client(research, monkeypatch):
    inbox, entities, _, _, _, _, kwargs = research
    for key, row in entities.items():
        row.update(name=key, entity_type='company')
    monkeypatch.setattr(main, 'INBOX_DIR', inbox)
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    monkeypatch.setattr(main, 'all_entities', lambda: list(entities.values()))
    ce.apply_anchor(inbox, **kwargs)
    return TestClient(main.app), research


@pytest.mark.parametrize('view', ['matrix', 'overview', 'plot', 'relationships', 'exposure', 'people', 'imports', 'saved'])
def test_actual_templates_with_scoped_records(client, view):
    http, _ = client
    result = http.get('/competitive-evaluation?companies=company-one&view='+view)
    assert result.status_code == 200
    assert 'Competitive evaluation' in result.text and 'competitive_coverage.js' in result.text
    assert 'Unknown means insufficient evidence' in result.text


def test_review_conflict_export_snapshot_and_public_boundary(client, monkeypatch):
    http, research = client
    inbox, _, scope, _, _, _, _ = research
    key = ce.scope_key(scope)
    form = dict(assessment_id=key, version='0', mode='override', rating='2', rationale='Analyst scope-specific correction')
    result = http.post('/competitive-evaluation/decision', data=form, follow_redirects=False)
    assert result.status_code == 303
    assert http.post('/competitive-evaluation/decision', data=form).status_code == 409
    assert http.post('/competitive-evaluation/decision', data=form, headers={'Origin': 'https://other.example'}).status_code == 403
    assert http.post('/competitive-evaluation/save', data={'scope': json.dumps({'companies':'company-one'}), 'title':'Cited comparison'}).status_code == 200
    from app.services.living_workspaces import Store
    saved = Store(inbox).rows('competitive_comparison')[0]
    snapshot = http.get('/competitive-evaluation/export/json?saved='+saved['id']).json()
    assert snapshot['assessments'][0]['rating'] == 2
    assert snapshot['assessments'][0]['sources'][0]['fields']['original_url'] == 'https://example.org/design'
    snapshot_page = http.get('/competitive-evaluation?saved='+saved['id'])
    assert snapshot_page.status_code == 200 and 'Saved immutable comparison' in snapshot_page.text
    assert '>Save decision<' not in snapshot_page.text
    assert http.get('/competitive-evaluation/export/json?saved='+saved['id']).json() == snapshot
    assert 'rubric_version' in http.get('/competitive-evaluation/export/csv?saved='+saved['id']).text
    monkeypatch.setattr(main, 'AUTHORING_MODE', False)
    assert http.get('/competitive-evaluation').status_code == 403
    assert http.get('/competitive-evaluation/export/json').status_code == 403


def test_archive_template_and_empty_state(client, monkeypatch):
    http, _ = client
    entities = {'company-one': dict(id='company-one', name='One', entity_type='company')}
    monkeypatch.setattr(competitive_routes, 'world', lambda: (main, {'pending_source_issue_count': 1}, {
        'ev-one': dict(id='ev-one', title='Original article', source_url='https://example.org/a',
                       entity_ids=['company-one'], published_date='2020-01-01', captured_date='2026-10-30')}, entities))
    monkeypatch.setattr(main, 'all_relationships', lambda: [])
    result = http.get('/coverage/archive?companies=company-one&embedded=1')
    assert result.status_code == 200
    assert 'Incomplete indexing' in result.text and 'Published 2020-01-01' in result.text
    assert 'data-open-reader' in result.text
    assert 'No captured matches' in http.get('/coverage/archive?companies=company-two').text


def test_checkbox_selection_keeps_multiple_entities_without_javascript(client):
    http,_=client
    query='companies=company-one&companies=company-two&berry=berry-strawberry'
    page=http.get('/competitive-evaluation?'+query)
    assert page.status_code==200
    assert 'data-ce-entity-picker' in page.text and 'type="checkbox" name="companies"' in page.text
    assert '<select name="companies"' not in page.text
    exported=http.get('/competitive-evaluation/export/json?'+query).json()
    assert exported['selected']==['company-one','company-two']
    assert exported['scope']['companies']=='company-one,company-two'
    assert 'companies=company-one%2Ccompany-two' in page.text


def test_matrix_paginates_after_scoping_while_export_keeps_all_cells(client):
    http,research=client
    inbox,_,scope,*_=research
    from app.services.living_workspaces import Store
    store=Store(inbox)
    with store.transaction() as db:
        for number in range(30):
            cell={**scope,'program_or_variety':'Fixture programme '+str(number)}
            store.put(db,'capability_automatic',{'id':ce.scope_key(cell),**cell,'rating':'unknown',
                'status':'unscored','confidence':'unknown','rationale':'Deterministic fixture; no rating established',
                'assessed_at':'2026-10-30','basis':'fixture','observation_ids':[],'source_ids':[]},'test fixture')
    query='companies=company-one&matrix_page=2'
    page=http.get('/competitive-evaluation?'+query)
    assert page.status_code==200 and 'Page 2 of 2' in page.text
    assert page.text.count('<tr id="capability-')==7
    assert len(http.get('/competitive-evaluation/export/json?'+query).json()['assessments'])==31


def test_sheet_search_filter_and_sort_apply_before_pagination_and_export(client):
    http, research = client
    inbox, _, scope, *_ = research
    from app.services.living_workspaces import Store
    store = Store(inbox)
    with store.transaction() as db:
        for number in range(30):
            cell = {**scope, 'program_or_variety': 'Searchable programme %02d' % number}
            store.put(db, 'capability_automatic', {'id': ce.scope_key(cell), **cell,
                'rating': 'unknown', 'status': 'unscored', 'confidence': 'unknown',
                'rationale': 'Fixture only', 'assessed_at': '2020-01-01', 'basis': 'fixture',
                'observation_ids': [], 'source_ids': []}, 'test fixture')
    query = 'companies=company-one&q=programme+29&rating_state=unknown&matrix_page=2'
    page = http.get('/competitive-evaluation?' + query)
    assert page.status_code == 200 and 'Page 1 of 1' in page.text
    assert page.text.count('<tr id="capability-') == 1
    exported = http.get('/competitive-evaluation/export/json?' + query).json()['assessments']
    assert len(exported) == 1 and exported[0]['program_or_variety'] == 'Searchable programme 29'
    assert len(http.get('/competitive-evaluation/export/json?rating_state=needs_review').json()['assessments']) == 30
    for direction in ('asc', 'desc'):
        values = http.get('/competitive-evaluation/export/json?sort=rating&direction=' + direction).json()['assessments']
        assert isinstance(values[0]['rating'], int)
        assert all(value['rating'] == 'unknown' for value in values[1:])
    assert Store(inbox).rows('capability_decision') == []


@pytest.mark.parametrize('query', ['sort=arbitrary', 'direction=sideways', 'rating_state=trusted'])
def test_sheet_rejects_unsupported_filter_values(client, query):
    assert client[0].get('/competitive-evaluation?' + query).status_code == 422


def test_people_sheet_export_searches_before_pagination_and_is_private(client,monkeypatch):
    http,research=client
    inbox,*_=research
    from app.services.living_workspaces import Store
    store=Store(inbox)
    with store.transaction() as db:
        for number in range(65):
            store.put(db,'competitive_record',{'id':'person-fixture-'+str(number),'kind':'person',
                'entity_id':'company-one','batch_id':'B01','local_id':'P'+str(number),
                'fields':{'name_original':'=Source formula' if number==64 else 'Professional '+str(number),
                          'role_title':'Breeder','last_observed_date':'2026-10-30'},
                'resolution':'accepted_structure','source_refs':[]},'test fixture')
    page=http.get('/competitive-evaluation?view=people&record_page=2')
    assert page.status_code==200 and 'Page 2 of 2' in page.text
    assert 'ce-record-grid' in page.text and '<ol>' not in page.text
    import csv,io
    exported=list(csv.DictReader(io.StringIO(http.get('/competitive-evaluation/records.csv?view=people&record_page=2').text)))
    assert len(exported)==65 and any(r['name']=="'=Source formula" for r in exported)
    searched=list(csv.DictReader(io.StringIO(http.get('/competitive-evaluation/records.csv?view=people&people_q=Professional+63').text)))
    assert len(searched)==1 and searched[0]['name']=='Professional 63'
    monkeypatch.setattr(main,'AUTHORING_MODE',False)
    assert http.get('/competitive-evaluation/records.csv?view=people').status_code==403
