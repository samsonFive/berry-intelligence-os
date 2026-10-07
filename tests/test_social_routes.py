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

def test_error_empty_and_approved_berry_selection(client):
    page=client.get('/social?mode=live');assert page.status_code==200 and 'No posts in this selection' in page.text
    assert client.get('/social?berry=berry-strawberry').status_code==200
    assert client.get('/social?berry=berry-invalid').status_code==422
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

def test_english_visibility_covers_counts_reader_and_translation_arrival(client):
    from copy import deepcopy
    from app.services.social_intelligence.presentation import readable_in_english
    assert not readable_in_english({'language':'ja','text':'ブルーベリー'})
    assert not readable_in_english({'language':'und','text':'Looks English but unverified'})
    r=deepcopy(FIXTURE['records'][0]);r.update(native_id='english-filter-test',mode='imported',language='es',text='Arándanos crujientes',translation=None)
    store=Store(main.INBOX_DIR);key=store.ingest([r],main.all_entities(),mode='imported')[0]
    assert client.get('/api/social?mode=imported').json()['count']==0
    assert client.get('/social/export?mode=imported').json()['count']==0
    assert client.get('/api/social/'+key+'/reader').status_code==409
    assert len(store.records(mode='imported'))==1
    r['translation']={'text':'Crunchy blueberries','language':'en','method':'machine','version':'test-double','uncertainty':'Deterministic test response; not a live translation'}
    store.ingest([r],main.all_entities(),mode='imported')
    assert client.get('/api/social?mode=imported').json()['count']==1
    assert client.get('/api/social/'+key+'/reader').status_code==200

def test_perspectives_keep_corporate_and_consumer_separate(client):
    store=Store(main.INBOX_DIR)
    for role in ('company_owned','consumer','unknown'):
        r=deepcopy(FIXTURE['records'][0]);r.update(native_id='perspective-'+role,mode='imported',content_role=role,language='en',translation=None)
        store.ingest([r],main.all_entities(),mode='imported')
    for perspective,role in [('corporate','company_owned'),('consumer','consumer'),('unclear','unknown')]:
        result=client.get('/api/social?mode=imported&perspective='+perspective).json()
        assert result['count']==1 and result['records'][0]['content_role']==role
        assert client.get('/social/export?mode=imported&perspective='+perspective).json()['count']==1
        assert 'perspective='+perspective in client.get('/social?mode=imported&perspective='+perspective).text


@pytest.mark.parametrize('berry',['berry-strawberry','berry-raspberry','berry-blackberry'])
def test_approved_berries_keep_scope_across_views_export_and_manual_capture(client,berry):
    rows=json.loads((ROOT/'benchmarks/social-all-berries-fixtures.json').read_text(encoding='utf-8'))['records']
    Store(main.INBOX_DIR).ingest(rows,main.all_entities())
    for view in ('posts','phrases','heatmap','atlas','momentum','coverage'):
        params={'berry':berry,'mode':'fixture','view':view,'perspective':'consumer','language':'es'}
        page=client.get('/social',params=params)
        assert page.status_code==200
        assert f'value="{berry}" selected' in page.text
        data=client.get('/api/social',params=params).json()
        assert data['count']==1
        assert all(berry in r['analysis']['berry_ids'] for r in data['records'])
        assert client.get('/social/export',params=params).json()['records']==data['records']
        assert client.get('/social/briefing',params=params).status_code==200
        assert client.get('/api/social/'+data['records'][0]['id']+'/reader').status_code==200
    imported=deepcopy(next(r for r in rows if berry in r['native_id'] and r['language']=='en'))
    imported.update(mode='imported',native_id='approved-import-'+berry)
    assert client.post('/api/social/import',json=[imported],headers={'Origin':'http://testserver'}).status_code==200
    assert client.get('/api/social',params={'berry':berry,'mode':'imported'}).json()['count']==1
    assert client.get('/api/social',params={'berry':'berry-blueberry','mode':'imported'}).json()['count']==0


def test_rollout_search_matches_displayed_english_translation(client):
    rows=json.loads((ROOT/'benchmarks/social-all-berries-fixtures.json').read_text(encoding='utf-8'))['records']
    Store(main.INBOX_DIR).ingest(rows,main.all_entities())
    result=client.get('/api/social',params={'berry':'berry-raspberry','mode':'fixture','language':'es','q':'raspberries'}).json()
    assert result['count']==2
    assert all('frambuesas' in r['text'] and 'raspberries' in r['translation']['text'] for r in result['records'])
