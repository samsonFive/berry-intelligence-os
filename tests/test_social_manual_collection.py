"""Paid-prepaid collection safety: no live provider requests in tests."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from app.services.social_intelligence import manual_collection as m
from app.services.social_intelligence.store import Store
from app.services.social_intelligence.adapters import AccessBlocked
from tests.test_social_intelligence import sample, ENTITIES
from tests.test_social_routes import client

@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv('BIOS_SOCIAL_MANUAL_COLLECTION','true')
    monkeypatch.setenv('SOCIAVAULT_API_KEY','test-only')

class Client:
    def __init__(self,balances=None,code=200,payload=None):
        self.balances=iter(balances or [6010,6009]);self.calls=[];self.code=code
        self.payload=payload or {'success':True,'data':{'posts':{},'credits_used':1}}
    def account(self):return next(self.balances)
    def _read(self,path,params):self.calls.append((path,params));return self.code,self.payload

def options():return {'berry':'berry-blueberry','perspective':'consumer','period':'week','platforms':['reddit']}

def test_no_configuration_no_queue_or_charges(tmp_path,monkeypatch):
    monkeypatch.delenv('BIOS_SOCIAL_MANUAL_COLLECTION',raising=False)
    with pytest.raises(AccessBlocked):m.queue(tmp_path,options())
    assert Store(tmp_path).jobs()==[]

@pytest.mark.parametrize('payload',[{'platforms':['forums-retail']},{'platforms':['x','x']},{'period':'day'}, {'url':'https://evil.test'}, {'platforms':'x'}])
def test_only_bounded_operator_options(payload):
    with pytest.raises(ValueError):m.plan(payload)

def test_default_all_berries_and_date_limitations():
    p=m.plan({});assert p['max_credits']==26 and 'Facebook' in p['note']
    assert {q['berry'] for q in p['queries']}==set(m.BERRIES)|{'all'}
    assert all('https://' not in q['params'].get('query','') for q in p['queries'])
    assert not any(q['source']=='instagram' and q['scope']=='corporate' for q in p['queries'])
    with pytest.raises(ValueError):m.plan({'platforms':list(m.SOURCES)})

def test_restart_duplicate_click_reuses_without_requests(configured,tmp_path):
    job,new=m.queue(tmp_path,options());assert new
    with pytest.raises(AccessBlocked):m.queue(tmp_path,options())
    client=Client();m.run(tmp_path,job['id'],ENTITIES,client)
    same,new=m.queue(tmp_path,options());assert same['id']==job['id'] and not new
    m.run(tmp_path,job['id'],ENTITIES,client);assert len(client.calls)==1
    assert m.status(tmp_path)['reserved_credits']==1

def test_reservation_precedes_request_and_survives_transport(configured,tmp_path):
    job,_=m.queue(tmp_path,options())
    class Failing(Client):
        def _read(self,path,params):
            ledger=json.loads((tmp_path/'social/manual-credit-ledger.json').read_text())
            assert ledger['reservations'][0]['state']=='reserved'
            raise AccessBlocked('Transport unavailable; no retry')
    client=Failing();m.run(tmp_path,job['id'],ENTITIES,client)
    assert m.status(tmp_path)['reserved_credits']==1
    result=Store(tmp_path).job(job['id'])['results'][0]
    assert result['returned'] is None and result['state']=='failed'
    assert Store(tmp_path).job(job['id']+'-0')['observed_volume'] is None

def test_outage_versus_zero(configured,tmp_path):
    job,_=m.queue(tmp_path,options());m.run(tmp_path,job['id'],ENTITIES,Client())
    result=Store(tmp_path).job(job['id'])['results'][0]
    assert result['state']=='success' and result['returned']==0
    assert Store(tmp_path).job(job['id']+'-0')['observed_volume']==0

def test_cost_mismatch_halts_before_ingestion(configured,tmp_path):
    job,_=m.queue(tmp_path,options());client=Client([6010,6007])
    m.run(tmp_path,job['id'],ENTITIES,client)
    assert m.status(tmp_path)['halted'] and not Store(tmp_path).records()
    with pytest.raises(AccessBlocked):m.queue(tmp_path,options())

def test_low_balance_stops_without_provider_request(configured,tmp_path):
    job,_=m.queue(tmp_path,options());client=Client([100]);m.run(tmp_path,job['id'],ENTITIES,client)
    assert not client.calls and Store(tmp_path).job(job['id'])['status']=='blocked'

def test_monthly_credit_limit_blocks_queue(configured,tmp_path):
    path=tmp_path/'social/manual-credit-ledger.json';path.parent.mkdir()
    path.write_text(json.dumps({'version':m.VERSION,'halted':False,'reservations':[{'at':m.now()}]*m.MONTH_LIMIT}))
    with pytest.raises(AccessBlocked):m.queue(tmp_path,options())

def test_real_intake_replay_preserves_mode_labels_and_media(configured,tmp_path,monkeypatch):
    row=sample('live',native_id='real-1',language='en',language_basis='source',text='I bought blueberries and they are sweet',content_role='unknown',content_role_basis='Not classified')
    monkeypatch.setattr(m,'normalize',lambda *a:{'rows':[deepcopy(row)],'returned_items':1,'mapping_errors':[]})
    Store(tmp_path).ingest([sample('fixture',native_id='real-1')],ENTITIES)
    job,_=m.queue(tmp_path,options());m.run(tmp_path,job['id'],ENTITIES,Client())
    retained=Store(tmp_path).records(mode='live');assert len(retained)==1
    assert retained[0]['content_role']=='consumer' and 'Proposed' in retained[0]['content_role_basis']
    assert retained[0]['discovery_method']=='sociavault-manual-prepaid'
    assert len(Store(tmp_path).records(mode='fixture'))==1

@pytest.mark.parametrize('text',[
    'Compré arándanos frescos en el supermercado y estaban deliciosos, pero algunos estaban demasiado blandos y otros no tenían sabor.',
    'Comprei mirtilos frescos no mercado e estavam deliciosos, mas alguns estavam muito moles e outros não tinham sabor.',
    '今天我去超市买了一盒蓝莓，味道很甜，但是有些果实太软了，下次想买更新鲜的。',
    'スーパーで買ったブルーベリーは甘かったですが、一部は柔らかすぎました。次はもっと新鮮なものを買いたいです。',
    'blueberries',
])
def test_non_english_and_short_unknown_not_silently_english(text):
    row=sample('live',language='und',text=text)
    assert m.propose_labels(row)['language']=='und'

def test_offline_english_proposal_has_provenance():
    row=sample('live',language='und',text='I bought a large box of fresh blueberries from the supermarket yesterday and they were sweet, crunchy and delicious with my breakfast.')
    m.propose_labels(row);assert row['language']=='en' and 'langid' in row['language_basis']

def test_prior_language_and_role_only_reused_for_identical_text():
    row=sample('live',language='und',text='Blueberries',content_role='unknown',content_role_basis='Not classified');prior={**row,'language':'en','language_basis':'human','content_role':'company_owned','content_role_basis':'verified native author'}
    m.propose_labels(row,prior);assert row['content_role']=='company_owned' and row['language']=='en'
    changed=sample('live',language='und',text='Arándanos');m.propose_labels(changed,prior);assert changed['language']=='und'

def test_collection_routes_require_origin_and_operator_enablement(client,monkeypatch):
    headers={'Origin':'http://testserver'}
    monkeypatch.delenv('BIOS_SOCIAL_MANUAL_COLLECTION',raising=False)
    assert client.post('/api/social/collection/start',json=options()).status_code==403
    assert client.post('/api/social/collection/start',json=options(),headers=headers).status_code==409
    assert client.post('/api/social/collection/preview',json=options(),headers=headers).json()['max_credits']==1
    assert client.get('/api/social/collection/status').json()['enabled'] is False
    assert 'Collect now' in client.get('/social').text

def test_collection_route_runs_guarded_background_job(client,configured,monkeypatch):
    fake=Client();monkeypatch.setattr(m,'PrepaidClient',lambda *a,**k:fake)
    r=client.post('/api/social/collection/start',json=options(),headers={'Origin':'http://testserver'})
    assert r.status_code==202 and len(fake.calls)==1
    repeat=client.post('/api/social/collection/start',json=options(),headers={'Origin':'http://testserver'})
    assert repeat.status_code==200 and repeat.json()['reused'] and len(fake.calls)==1

def test_collection_routes_are_private(client,monkeypatch):
    from tests.test_remote_auth import _enable_remote
    from fastapi.testclient import TestClient
    from app.main import app
    _enable_remote(monkeypatch);remote=TestClient(app,follow_redirects=False)
    assert remote.get('/api/social/collection/status').status_code==302
    assert remote.post('/api/social/collection/start',json=options(),headers={'Origin':'http://testserver'}).status_code==302

def test_explicit_proxy_origin_does_not_trust_forwarded_header(client,monkeypatch):
    monkeypatch.setenv('BIOS_PUBLIC_ORIGIN','https://intel.example.test')
    assert client.post('/api/social/collection/preview',json=options(),headers={'Origin':'https://intel.example.test'}).status_code==200
    assert client.post('/api/social/collection/preview',json=options(),headers={'Origin':'http://testserver','X-Forwarded-Proto':'https'}).status_code==403
