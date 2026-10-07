from copy import deepcopy
import json
from pathlib import Path
import pytest

def test_remote_session_protects_social_workspace_and_mutations(client, monkeypatch):
    from tests.test_remote_auth import _enable_remote
    _enable_remote(monkeypatch)
    from fastapi.testclient import TestClient
    from app.main import app
    remote = TestClient(app, follow_redirects=False)
    assert remote.get('/social').status_code == 302
    assert remote.get('/api/social').status_code == 302
    assert remote.post('/api/social/manual', json={}, headers={'Origin':'http://testserver'}).status_code == 302

from fastapi.testclient import TestClient
from app import main
from app.services.social_intelligence.store import Store

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=json.loads((ROOT/'benchmarks/social-blueberry-fixtures.json').read_text(encoding='utf-8'))

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setattr(main,'INBOX_DIR',tmp_path)
    monkeypatch.setattr(main,'AUTHORING_MODE',True)
    Store(tmp_path).ingest(FIXTURE['records'],main.all_entities())
    return TestClient(main.app)

@pytest.mark.parametrize('view',['posts','phrases','heatmap','atlas','momentum','coverage'])
def test_views_same_bundle_filters_safe_render_and_drawer(client,view):
    api=client.get('/api/social?mode=fixture&language=es&view='+view).json()
    page=client.get('/social?mode=fixture&language=es&view='+view)
    assert page.status_code==200 and 'Sample posts' in page.text
    assert api['version'] in page.text and 'v2ReaderOffcanvas' in page.text
    assert all(r['language']=='es' and r['mode']=='fixture' for r in api['records'])
    key=api['records'][0]['id'];reader=client.get('/api/social/'+key+'/reader')
    assert reader.status_code==200 and 'Not reviewed' in reader.text
    assert 'Translation' in reader.text and 'Purchased in' in reader.text
    assert client.get('/social/briefing?mode=fixture&language=es').status_code==200
    assert client.get('/social/export?mode=fixture&language=es').json()['count']==api['count']

def test_dense_post_sheet_full_original_translation_dates_and_roles(client):
    page=client.get('/social?mode=fixture&language=es&role=consumer').text
    assert 'social-post-grid' in page and '10/01/26' in page
    assert 'data-sort-value="2026-10-' in page
    assert 'Encontré arándanos en Costco; grande y crujiente pero insípido.' in page
    assert 'social-original-hover' in page and 'ES original' in page
    assert 'Purchased in' in page
    assert 'value="consumer" selected' in page
    assert 'Inspect this cell' not in page and '>FIXTURE<' not in page

def test_manual_import_provenance_csrf_and_schema(client):
    headers={'Origin':'http://testserver'}
    payload={'source':'reddit','native_id':'manual1','canonical_url':'https://example.org/allowed-public-reference',
     'text':'Blueberries crunchy <script>alert(1)</script>','language':'en','language_basis':'analyst','attribution':'minimal',
     'permission_basis':'permitted analyst quotation'}
    assert client.post('/api/social/manual',json=payload).status_code==403
    response=client.post('/api/social/manual',json=payload,headers=headers)
    assert response.status_code==200,response.text
    key=response.json()['ids'][0]
    reader=client.get('/api/social/'+key+'/reader');assert '&lt;script&gt;' in reader.text and '<script>alert(1)</script>' not in reader.text
    handoff=client.post('/api/social/'+key+'/handoff',json={},headers=headers)
    assert handoff.status_code==200 and handoff.json()['review_url']=='/review/'+key
    r=deepcopy(FIXTURE['records'][0]);r.update(mode='imported',translation=None,native_id='import1')
    assert client.post('/api/social/import',json=[r],headers=headers).status_code==200
    r['mode']='live';assert client.post('/api/social/import',json=[r],headers=headers).status_code==422
    assert client.post('/api/social/import',content='a'*1000001,headers=headers).status_code==413

def test_error_empty_and_blueberry_gate(client):
    page=client.get('/social?mode=live');assert page.status_code==200 and 'No posts in this selection' in page.text
    assert client.get('/social?berry=berry-strawberry').status_code==422
    assert 'Reset Social Listening' in client.get('/social?view=fiction').text
    assert client.get('/api/social/missing/reader').status_code==410

@pytest.mark.parametrize('path',['/social','/api/social','/social/briefing','/social/export','/api/social/missing/reader','/api/social/missing/media/missing'])
def test_every_read_is_private_authoring(client,monkeypatch,path):
    monkeypatch.setattr(main,'AUTHORING_MODE',False)
    assert client.get(path).status_code==404

def test_media_api_retrieves_comment_and_removal_invalidation(client,tmp_path):
    store=Store(tmp_path);row=next(r for r in store.records() if r['native_id']=='demo-es-4');mid=row['media'][0]['id']
    store.attach_media(row['id'],mid,b'\x89PNG\r\n\x1a\nfixture','image/png')
    path='/api/social/'+row['id']+'/media/'+mid
    response=client.get(path);assert response.status_code==200 and response.headers['cache-control']=='private, no-store'
    reader=client.get('/api/social/'+row['id']+'/reader');assert path in reader.text and 'demo-es-0' in reader.text
    store.remove(row['id'],media_id=mid,state='restricted')
    assert client.get(path).status_code==410
    assert 'Literal label' not in client.get('/api/social/'+row['id']+'/reader').text
