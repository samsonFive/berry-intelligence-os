from copy import deepcopy
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.datastructures import FormData

from app import main
from app.repositories.json.entities import EntityRepository
from app.services import variety_catalog as service
from app.services import variety_catalog_import as imports
from app.services.analyst_state_io import atomic_json


SCHEMAS = Path(__file__).resolve().parents[1] / 'schemas'
VARIETY = {'id': 'variety-example', 'record_type': 'entity', 'entity_type': 'variety', 'name': 'Example',
           'status': 'unverified', 'berry_ids': ['berry-strawberry'], 'aliases': [], 'description': 'Original',
           'evidence_ids': ['ev-original'], 'fact_ids': ['fact-original'], 'relationship_ids': [],
           'attributes': {'parentage': 'Parent A × Parent B', 'traits': [{'trait': 'firmness', 'value': 'source assertion'}], 'custom_number': 3}}


def form_for(record, **changes):
    model = service.editor_model(record)
    pairs = [('name', record['name']), ('status', record['status']), ('description', record.get('description', '')),
             ('aliases', '\n'.join(record.get('aliases', []))), ('revision', service.revision(record)), ('editor', 'Test editor')]
    pairs += [('berry_ids', berry) for berry in record.get('berry_ids', [])]
    pairs += [(key, record.get('attributes', {}).get(key, '')) for key in service.SCALAR_FIELDS]
    for key, columns in service.TABLES.items():
        for row in record.get('attributes', {}).get(key, []):
            pairs.append((key + '.row', '1'))
            pairs += [(key + '.' + column, row.get(column, '')) for column in columns]
    for field in model['extra_fields']:
        pairs += [('extra.' + key, field[key]) for key in ('key', 'value', 'kind')]
    pairs = [(key, value) for key, value in pairs if key not in changes]
    pairs += list(changes.items())
    return FormData(pairs)


@pytest.fixture
def runtime(tmp_path):
    data, inbox = tmp_path / 'data', tmp_path / 'inbox'
    repo = EntityRepository(data, SCHEMAS)
    repo.create(deepcopy(VARIETY))
    return data, inbox, repo


def test_edit_retains_graph_links_structured_types_and_auditable_prior_values(runtime):
    data, inbox, repo = runtime
    form = form_for(VARIETY, description='Expanded description', name='New Example')
    saved = service.save(inbox, data, SCHEMAS, VARIETY['id'], form, actor='Johnny')
    assert saved['name'] == 'New Example' and saved['description'] == 'Expanded description'
    assert saved['attributes']['traits'] == VARIETY['attributes']['traits']
    assert saved['attributes']['custom_number'] == 3
    assert saved['fact_ids'] == ['fact-original'] and saved['evidence_ids'] == ['ev-original']
    assert service.history(inbox, saved['id'])[0]['before'] == VARIETY
    assert service.history(inbox, saved['id'])[0]['after'] == repo.get(saved['id'])
    with pytest.raises(ValueError, match='another session'):
        service.save(inbox, data, SCHEMAS, VARIETY['id'], form, actor='Second editor')
    assert repo.get(saved['id']) == saved


def test_creation_deletion_restore_and_no_accidental_identity_merge(runtime):
    data, inbox, repo = runtime
    with pytest.raises(ValueError, match='overlaps'):
        service.create(inbox, data, SCHEMAS, form_for(VARIETY), actor='Johnny')
    new = service.create(inbox, data, SCHEMAS, form_for(VARIETY, name='Different variety'), actor='Johnny')
    assert new['status'] == 'unverified' and not new['evidence_ids'] and not new['fact_ids']
    assert service.visible(new) and not service.visible(new, private=False)
    with pytest.raises(ValueError, match='confirm removal'):
        service.remove_or_restore(inbox, data, SCHEMAS, new['id'], expected=service.revision(new), actor='Johnny')
    removed = service.remove_or_restore(inbox, data, SCHEMAS, new['id'], expected=service.revision(new), actor='Johnny', confirmation=new['name'])
    assert not service.visible(removed) and repo.get(new['id']) is not None
    restored = service.remove_or_restore(inbox, data, SCHEMAS, new['id'], expected=service.revision(removed), actor='Johnny', restore=True)
    assert service.visible(restored) and len(service.history(inbox, new['id'])) == 3


@pytest.mark.parametrize('field,value', [('catalog_sources.url','javascript:alert(1)'), ('catalog_connections.source_url','http://localhost/private')])
def test_unsafe_sources_never_persist(runtime, field, value):
    data, inbox, repo = runtime
    key = field.split('.')[0]
    pairs = list(form_for(VARIETY).multi_items()) + [(key + '.row','1'), (field, value)]
    with pytest.raises(ValueError, match='public'):
        service.save(inbox, data, SCHEMAS, VARIETY['id'], FormData(pairs), actor='Johnny')
    assert repo.get(VARIETY['id']) == VARIETY and not service.history(inbox, VARIETY['id'])


def test_import_is_unverified_additive_replayable_and_keeps_existing_records(runtime):
    data, inbox, repo = runtime
    sources = [{'id':'source-a','title':'A portfolio','url':'https://example.com/varieties','checked_on':'2026-10-01',
                'company_ids':[], 'names':[{'candidate_name':'New cultivar','berry_id':'berry-strawberry'}]}]
    plan = imports.build_plan(entities=repo.list(), portfolio_sources=sources)
    original = repo.get(VARIETY['id'])
    receipt = imports.apply_plan(inbox, data, SCHEMAS, plan, expected_digest=plan['digest'], actor='Johnny · authorized catalog population')
    assert len(receipt['added_ids']) == 1 and repo.get(VARIETY['id']) == original
    added = repo.get(receipt['added_ids'][0])
    assert added['status'] == 'unverified' and not added['aliases'] and not added['relationship_ids'] and not added['fact_ids']
    assert added['attributes']['catalog_sources'][0]['url'] == 'https://example.com/varieties'
    assert not service.visible(added, private=False)
    assert not imports.apply_plan(inbox, data, SCHEMAS, plan, expected_digest=plan['digest'], actor='Johnny')['added_ids']
    assert not (data / 'facts').exists() and not (data / 'evidence').exists()


def test_import_holds_rejections_ambiguous_names_and_warning_scopes(runtime):
    _, _, repo = runtime
    source = {'id':'source-a','title':'Portfolio','url':'https://example.com', 'company_ids':[],
              'review_warnings':['A code is ambiguous'], 'review_warning_scopes':[{'message':'A code is ambiguous','candidate_names':['Unclear']}],
              'names':[{'candidate_name':name,'berry_id':'berry-strawberry'} for name in ['Unclear','Rejected','Clear']]}
    plan = imports.build_plan(entities=repo.list(), portfolio_sources=[source],
                             candidates=[{'candidate_name':'Rejected','berry_id':'berry-strawberry','status':'rejected'}])
    assert [row['name'] for row in plan['additions']] == ['Clear']
    assert {row['name'] for row in plan['held']} == {'Unclear','Rejected'}


def test_import_stale_baseline_and_tampering_cannot_write(runtime):
    data, inbox, repo = runtime
    plan = imports.build_plan(entities=repo.list(), seed_rows=[{'candidate_name':'New','berry_id':'berry-strawberry'}])
    changed = deepcopy(plan)
    changed['additions'][0]['status'] = 'active'
    with pytest.raises(ValueError, match='plan changed'):
        imports.apply_plan(inbox, data, SCHEMAS, changed, expected_digest=plan['digest'], actor='Johnny')
    record = repo.get(VARIETY['id'])
    record['description'] = 'Edited since plan'
    repo.update(record['id'],record)
    with pytest.raises(ValueError, match='changed since planning'):
        imports.apply_plan(inbox, data, SCHEMAS, plan, expected_digest=plan['digest'], actor='Johnny')
    assert len(repo.list()) == 1


def test_existing_catalog_enrichment_is_private_and_editor_empty_value_wins(runtime):
    data, inbox, repo = runtime
    plan = imports.build_plan(entities=repo.list(), seed_rows=[{'candidate_name':'Example','berry_id':'berry-strawberry'}])
    imports.apply_plan(inbox, data, SCHEMAS, plan, expected_digest=plan['digest'], actor='Johnny')
    assert repo.get(VARIETY['id']) == VARIETY
    enriched = imports.effective_record(VARIETY, imports.imported_enrichment(inbox))
    assert enriched['attributes']['catalog_sources']
    saved = service.save(inbox, data, SCHEMAS, VARIETY['id'], form_for(VARIETY), actor='Johnny')
    assert imports.effective_record(saved, imports.imported_enrichment(inbox))['attributes']['catalog_sources'] == []


def test_authoring_routes_cross_origin_readonly_stale_forms_and_removed_page(runtime,monkeypatch):
    data, inbox, repo = runtime
    monkeypatch.setattr(main,'DATA_DIR',data)
    monkeypatch.setattr(main,'INBOX_DIR',inbox)
    monkeypatch.setattr(main,'AUTHORING_MODE',True)
    monkeypatch.setattr(main,'all_relationships',lambda: [])
    monkeypatch.setattr(main,'review_username',lambda: '')
    client = TestClient(main.app)
    response = client.get('/varieties/catalog/' + VARIETY['id'] + '/edit')
    assert response.status_code == 200 and 'Save variety' in response.text and 'parentage' in response.text.lower()
    assert client.post('/varieties/catalog/new',headers={'Origin':'https://other.example'}).status_code == 403
    from urllib.parse import urlencode
    pairs = form_for(VARIETY, description='route saved').multi_items()
    response = client.post('/varieties/catalog/' + VARIETY['id'] + '/edit',content=urlencode(pairs),headers={'Content-Type':'application/x-www-form-urlencoded'},follow_redirects=False)
    assert response.status_code == 303 and repo.get(VARIETY['id'])['description'] == 'route saved'
    response = client.post('/varieties/catalog/' + VARIETY['id'] + '/edit',content=urlencode(pairs),headers={'Content-Type':'application/x-www-form-urlencoded'})
    assert response.status_code == 409 and 'route saved' in response.text and service.revision(VARIETY) in response.text
    current = repo.get(VARIETY['id'])
    service.remove_or_restore(inbox,data,SCHEMAS,current['id'],expected=service.revision(current),actor='Johnny',confirmation=current['name'])
    assert client.get('/entities/variety/' + current['id']).status_code == 410
    assert current['id'] not in {row['id'] for row in main.all_entities()}
    assert 'Example' in client.get('/varieties/catalog/removed').text
    monkeypatch.setattr(main,'AUTHORING_MODE',False)
    assert client.get('/varieties/catalog/new').status_code == 403
    assert client.post('/varieties/catalog/' + current['id'] + '/restore').status_code == 403


def test_public_static_catalog_excludes_workspace_and_removed_records(monkeypatch):
    from scripts import build_static
    private = deepcopy(VARIETY)
    private['id'] = 'variety-private'
    private['attributes']['catalog_visibility'] = 'workspace'
    removed = deepcopy(VARIETY)
    removed['id'] = 'variety-removed'
    removed['attributes']['catalog_removed'] = True
    monkeypatch.setattr(build_static,'_all_entities',lambda:[VARIETY,private,removed])
    assert build_static.all_entities() == [VARIETY]
    assert set(build_static.entity_index()) == {VARIETY['id']}


def test_reviewed_role_edits_need_explicit_source_review_and_keep_role_history(runtime):
    from app.repositories.json.relationships import RelationshipRepository
    data, inbox, repo = runtime
    repo.create({'id':'company-example','record_type':'entity','entity_type':'company','name':'Example nursery','status':'active'})
    atomic_json(data / 'evidence' / 'ev-source.json', {'id':'ev-source','status':'published'})
    payload = {'subject_id':'company-example','object_id':VARIETY['id'],'predicate':'markets','status':'active',
               'evidence_ids':'ev-source','notes':'Scope stated by source','relationship_revision':''}
    with pytest.raises(ValueError,match='reviewed the supporting'):
        service.save_relationship(inbox,data,SCHEMAS,VARIETY['id'],payload,actor='Johnny')
    payload['role_reviewed'] = 'yes'
    saved = service.save_relationship(inbox,data,SCHEMAS,VARIETY['id'],payload,actor='Johnny')
    assert saved['predicate'] == 'markets'
    payload.update(relationship_id=saved['id'],relationship_revision=service.revision(saved),status='historical')
    updated = service.save_relationship(inbox,data,SCHEMAS,VARIETY['id'],payload,actor='Johnny')
    assert updated['status']=='historical'
    assert RelationshipRepository(data,SCHEMAS).get(saved['id']) == updated
    assert service.history(inbox,VARIETY['id'])[0]['before']==saved
    with pytest.raises(ValueError,match='another session'):
        service.save_relationship(inbox,data,SCHEMAS,VARIETY['id'],payload,actor='Other editor')


def test_expansion_uses_saved_same_identity_and_rejects_batch_collision_before_writes(runtime):
    data,inbox,repo=runtime
    plan=imports.build_plan(entities=repo.list(),seed_rows=[{'candidate_name':'An explicit alias','berry_id':'berry-strawberry'}],
        candidates=[{'candidate_name':'An explicit alias','berry_id':'berry-strawberry','human_gated':True,
                     'identity_state':'confirmed_same','candidate_canonical_match':VARIETY['id']}])
    assert not plan['additions'] and plan['links'][0]['entity_id']==VARIETY['id']
    sources=[{'id':'catalog','title':'Example','url':'https://example.com', 'company_ids':[],
              'names':[{'candidate_name':name,'berry_id':'berry-strawberry'} for name in ['First new','Second new']]}]
    plan=imports.build_plan(entities=repo.list(),portfolio_sources=sources)
    collided=deepcopy(VARIETY);collided.update(id='variety-conflict',name='Second new')
    repo.create(collided)
    with pytest.raises(ValueError,match='conflicts with the import plan'):
        imports.apply_plan(inbox,data,SCHEMAS,plan,expected_digest=plan['digest'],actor='Johnny')
    assert {r['id'] for r in repo.list()}=={VARIETY['id'],'variety-conflict'}


def test_navigation_pages_larger_catalog_without_losing_letter_filters():
    from app.services.variety_navigation import directory
    cards=[{'id':f'variety-{i:03}','name':f'Example {i:03}'} for i in range(235)]
    first=directory(cards,params={},state={},entities={},relationships=[],regions=[])
    second=directory(cards,params={'page':'2'},state={},entities={},relationships=[],regions=[])
    last=directory(cards,params={'page':'100'},state={},entities={},relationships=[],regions=[])
    assert len(first['variety_rows'])==len(second['variety_rows'])==100
    assert last['catalog_page']==3 and len(last['variety_rows'])==35
    assert not {row['id'] for row in first['variety_rows']}.intersection(row['id'] for row in second['variety_rows'])
    assert 'page=' not in second['letter_urls']['E']
