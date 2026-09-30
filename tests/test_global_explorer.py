from fastapi.testclient import TestClient
from app.main import app
from app.services.global_explorer import IntelligenceQuery, explorer_model, snapshot_model

ENTITIES = {f'geography-{x}': {'id': f'geography-{x}', 'name':x.title(), 'entity_type':'geography', 'attributes': {'iso_3166_1_alpha_2':iso}} for x,iso in [('peru','PE'),('chile','CL'),('china','CN')]}
ENTITIES['geography-lima'] = {'id':'geography-lima','name':'Lima','entity_type':'geography'}
ENTITIES['company-grower'] = {'id':'company-grower','name':'Grower','entity_type':'company'}
BERRIES = {'berry-blueberry':'Blueberry','berry-strawberry':'Strawberry'}
REL = [{'subject_id':'geography-lima','object_id':'geography-peru','predicate':'part_of','status':'active'}]
def evidence(eid, geo, berry='berry-blueberry', **extra):
    return dict(id=eid,title=eid,status='published',geography_ids=[geo],berry_ids=[berry],source_url='https://example.org/'+eid,entity_ids=['company-grower'], **extra)
RECORDS=[evidence('pe','geography-peru'),evidence('cl','geography-chile'),evidence('cn','geography-china'),evidence('lima','geography-lima'),evidence('straw','geography-peru','berry-strawberry'),evidence('elsewhere','geography-spain'),evidence('structural','geography-peru',tags=['structural'])]

def test_multi_country_and_berry_composition():
    query=IntelligenceQuery.parse('geography-peru,geography-chile,geography-china,geography-peru','berry-blueberry',ENTITIES,BERRIES)
    assert len(query.geography_ids)==3
    assert {r['id'] for r in query.retrieve(RECORDS,REL)} == {'pe','cl','cn','lima'}
    assert query.params()['berry']=='berry-blueberry'

def test_no_pending_enrichment_or_hq_inference():
    query=IntelligenceQuery(('geography-peru',),'berry-blueberry')
    pending=evidence('draft','geography-peru');pending['status']='draft'
    untagged=evidence('untagged','geography-spain');untagged['ai_enrichment']={'suggested_geography_ids':['geography-peru']}
    assert query.retrieve([pending,untagged],REL)==[]

def test_empty_and_snapshot_provenance():
    query=IntelligenceQuery(('geography-peru',),'berry-blueberry')
    m=snapshot_model(query,RECORDS,ENTITIES,REL,BERRIES,['companies','developments'])
    assert m['report']['scope']['geography_ids']==['geography-peru']
    assert {s['section_id'] for s in m['report']['sections']}=={'companies','developments'}
    assert {r['id'] for r in m['packet']['source_trace']}=={'pe','lima'}
    assert all(r['source_url'].startswith('https://') for r in m['packet']['source_trace'])
    empty=snapshot_model(query,[],ENTITIES,REL,BERRIES,['varieties'])
    assert empty['report']['sections'][0]['status']=='unavailable'
    assert empty['packet']['source_trace']==[]

def test_global_and_invalid_queries():
    import pytest
    assert len(IntelligenceQuery().retrieve(RECORDS,REL))==6
    with pytest.raises(ValueError): IntelligenceQuery.parse('company-grower','',ENTITIES,BERRIES)
    with pytest.raises(ValueError): IntelligenceQuery.parse('','demo',ENTITIES,BERRIES)

def test_routes_and_pdf(monkeypatch):
    import app.main as main
    monkeypatch.setattr(main,'entity_index',lambda:ENTITIES)
    monkeypatch.setattr(main,'published_evidence',lambda:RECORDS)
    monkeypatch.setattr(main,'all_relationships',lambda:REL)
    client=TestClient(app)
    scope='?countries=geography-peru,geography-chile,geography-china&berry=berry-blueberry'
    response=client.get('/explorer'+scope)
    assert response.status_code==200
    assert 'Create Market Snapshot' in response.text
    response=client.get('/explorer/snapshot'+scope+'&sections=companies')
    assert response.status_code==200
    assert 'Company activity' in response.text
    assert '/intelligence/pe' in response.text
    pdf=client.get('/explorer/snapshot.pdf'+scope+'&sections=companies')
    assert pdf.status_code==200 and pdf.content.startswith(b'%PDF')
    assert client.get('/explorer?countries=missing').status_code==422
    assert client.get('/explorer?berry=missing').status_code==422


def test_source_text_is_escaped_for_pdf_markup():
    rows=[evidence('unsafe','geography-peru')]
    rows[0]['title']='<img src="file:///private"> & unsupported markup'
    m=snapshot_model(IntelligenceQuery(('geography-peru',)),rows,ENTITIES,REL,BERRIES,['developments'])
    assert '<img' not in m['report']['sections'][0]['generated_prose']
    assert '&lt;img' in m['report']['sections'][0]['generated_prose']


def test_remote_session_boundary(monkeypatch):
    monkeypatch.setenv('BIOS_REMOTE_INTERACTIVE','1')
    monkeypatch.setenv('BIOS_REVIEW_USERNAME','fixture')
    monkeypatch.setenv('BIOS_REVIEW_PASSWORD','fixture-only-password')
    monkeypatch.setenv('BIOS_SESSION_SECRET','fixture-session-key-different-and-over-32-chars')
    monkeypatch.delenv('BIOS_BASIC_AUTH',raising=False)
    client=TestClient(app)
    for path in ['/explorer','/explorer/snapshot','/explorer/snapshot.pdf']:
        response=client.get(path,follow_redirects=False)
        assert response.status_code in {302,303,307}
        assert '/login' in response.headers['location']


def test_unavailable_country_is_explicit_empty_scope():
    query=IntelligenceQuery.parse('iso:KW','berry-blueberry',ENTITIES,BERRIES)
    assert query.country_codes==('KW',)
    assert query.retrieve(RECORDS,REL)==[]
    model=snapshot_model(query,RECORDS,ENTITIES,REL,BERRIES,['developments'])
    assert model['selected'][0]['name']=='Kuwait'
    assert model['report']['scope']['country_codes']==['KW']
    assert model['packet']['source_trace']==[]
    combined=IntelligenceQuery.parse('iso:KW,geography-peru','berry-blueberry',ENTITIES,BERRIES)
    assert {r['id'] for r in combined.retrieve(RECORDS,REL)}=={'pe','lima'}
    # ISO selection resolves a stored canonical entity where one actually exists.
    assert IntelligenceQuery.parse('iso:PE','',ENTITIES,BERRIES).geography_ids==('geography-peru',)
