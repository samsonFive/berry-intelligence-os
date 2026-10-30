import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
from types import SimpleNamespace
from threading import Event

from app.services.research_progress import events
from app.services.topic_discovery import discover_topic
from app.services.topic_retrieval import plan_query


def test_stream_delivers_an_early_frame_before_the_operation_finishes():
    release=Event(); calls=[]
    async def operation(progress):
        def worker():
            calls.append('one request')
            progress({'stage':'capture','captured':1,'capture_total':2,'items':[{'title':'First source'}]})
            assert release.wait(3)
            return SimpleNamespace(body=b'<p>Final sources</p>')
        return await asyncio.to_thread(worker)
    async def verify():
        stream=events(operation)
        assert json.loads(await anext(stream))['stage']=='starting'
        frame=json.loads(await anext(stream))
        assert frame['items'][0]['title']=='First source' and not release.is_set()
        release.set()
        remaining=[json.loads(frame) async for frame in stream]
        assert remaining[-1]=={'type':'complete','html':'<p>Final sources</p>'}
    asyncio.run(verify())
    assert calls==['one request']


def test_stream_failure_does_not_emit_exception_details_or_reexecute():
    calls=[]
    async def operation(progress):
        calls.append(1)
        raise ValueError('secret-provider-token')
    async def verify():
        rows=[json.loads(frame) async for frame in events(operation)]
        assert rows[-1]['type']=='error'
        assert 'secret-provider-token' not in json.dumps(rows)
    asyncio.run(verify());assert calls==[1]


def test_disconnect_cleans_up_operation_and_waiting_progress_task():
    async def verify():
        started=asyncio.Event();cancelled=asyncio.Event()
        async def operation(progress):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()
        existing=asyncio.all_tasks()
        stream=events(operation)
        await anext(stream)
        consumer=asyncio.create_task(anext(stream))
        await started.wait()
        consumer.cancel()
        await asyncio.gather(consumer,return_exceptions=True)
        await stream.aclose()
        assert cancelled.is_set()
        assert not [task for task in asyncio.all_tasks()-existing if not task.done()]
    asyncio.run(verify())


def test_capture_completion_streams_before_a_slow_source_and_keeps_final_order(tmp_path):
    release=Event();early=[]
    class Client:
        def search(self,*args,**kwargs):
            return SimpleNamespace(provider='fixture',hits=[SimpleNamespace(url='https://example.org/'+name,title='Floricane blackberry '+name,published_date='2026-09-01',snippet='') for name in ['slow','fast']])
    def fetch(url):
        if url.endswith('/slow'):assert release.wait(3)
        return {'headline':'Floricane blackberry cultivar release','published_date':'2026-09-01','availability':'full',
                'passages':['A new floricane blackberry cultivar was introduced after extensive field trials. '+url]}
    def progress(frame):
        if frame['stage']=='capture' and frame['captured']==1:
            early.extend(frame['items']);release.set()
    result=discover_topic(plan_query('Floricane blackberry developments'),inbox_dir=tmp_path,client=Client(),fetcher=fetch,progress=progress)
    assert early and early[0]['source_url'].endswith('/fast')
    assert result['capture_count']==2
    cached=discover_topic(plan_query('Floricane blackberry developments'),inbox_dir=tmp_path,client=Client(),fetcher=lambda u: (_ for _ in ()).throw(AssertionError('cache must not refetch')))
    assert cached['cache_hit'] and cached['items']==result['items'] and cached['queries_this_request']==0

def test_stream_route_preserves_validation_and_executes_only_once(monkeypatch):
    from fastapi.responses import HTMLResponse
    from fastapi.testclient import TestClient
    from app import main
    calls=[]
    monkeypatch.setenv('BIOS_REMOTE_INTERACTIVE','false')
    monkeypatch.setattr(main,'entity_index',lambda: {})
    async def finish(request,payload,scope,entities,started,progress=None):
        calls.append(scope.question)
        if progress:progress({'stage':'capture','captured':1,'capture_total':1,'items':[]})
        return HTMLResponse('<p>Fixture finished</p>')
    monkeypatch.setattr(main,'_finish_research_live',finish)
    client=TestClient(main.app)
    headers={'Accept':'application/x-ndjson'}
    assert client.post('/api/research/live',json={'scope':{'question':'blackberry 2026-99-99'}},headers=headers).status_code==422
    assert client.post('/api/research/live',json={'scope':{'question':'blackberry','tag_ids':['private-tag']}},headers=headers).status_code==422
    assert calls==[]
    response=client.post('/api/research/live',json={'scope':{'question':'blackberry'}},headers=headers)
    assert response.headers['content-type'].startswith('application/x-ndjson')
    assert response.headers['cache-control']=='no-store'
    frames=[json.loads(line) for line in response.text.splitlines()]
    assert frames[-1]=={'type':'complete','html':'<p>Fixture finished</p>'} and calls==['blackberry']


def test_fast_provider_candidate_arrives_before_a_slow_provider_without_changing_final_results():
    from datetime import datetime,timezone
    from app.services.research_desk import ResearchScope,run_live_research
    from app.services.industry_pulse.models import DiscoveryHit
    release=Event();frames=[]
    hit=DiscoveryHit(title='Strawberry breeding trial results',url='https://example.org/strawberry',source_domain='example.org',published_date='2026-09-01',snippet='Strawberry cultivar research results',query_id='fixture',query_text='fixture',geography='global',berry='strawberry',topic='research',provider='fast')
    class Fast:
        name='fast'
        def discover(self,query):return [hit]
    class Slow:
        name='slow'
        def discover(self,query):assert release.wait(3);return []
    def progress(frame):
        frames.append(frame)
        if frame.get('provider')=='fast':
            assert frame.get('items') and not release.is_set()
            assert frame['items'][0]['capture_status']=='Provider metadata only · body not checked'
            release.set()
    scope=ResearchScope.from_dict({'question':'Strawberry breeding trials','berry_id':'berry-strawberry','all_time':True})
    result=run_live_research(scope,providers=[Fast(),Slow()],entities={},progress=progress,now=datetime(2026,10,29,tzinfo=timezone.utc))
    assert result['items'][0]['url']==hit.url and len(frames)==2


def test_captured_source_excerpts_are_not_exported_as_model_snippets():
    from app.services.research_desk import _public_digest
    live={'items':[{'id':'captured','title':'Public captured title','source_name':'Publisher','date':'2026-09-01',
                    'snippet':'LOCAL CAPTURED BODY EXCERPT','source_version':'sha','capture_status':'excerpt_only','passage_locator':'article:0'},
                   {'id':'provider','title':'Public provider title','source_name':'Publisher','date':'2026-09-01','snippet':'Allowed public provider snippet'}]}
    digest='\n'.join(_public_digest({},live))
    assert 'LOCAL CAPTURED BODY EXCERPT' not in digest
    assert 'Public captured title' in digest and 'Allowed public provider snippet' in digest
