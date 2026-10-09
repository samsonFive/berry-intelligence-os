import json
import httpx
import pytest
from app.services.social_intelligence.sociavault_pilot import MultiPlatformPilot,private_key
from app.services.social_intelligence.adapters import AccessBlocked

def client_for(*,balance=50,status='free',price=1,fail=False):
    calls=[]
    def respond(request):
        calls.append(request)
        if request.url.path=='/v1/credits':
            return httpx.Response(200,json={'credits':balance,'subscriptionStatus':status,
                                           'subscriptionId':'purchased' if status=='active' else None})
        return httpx.Response(503 if fail else 200,json={'success':not fail,'credits_used':price,'data':{'posts':[]}})
    return httpx.Client(transport=httpx.MockTransport(respond)),calls

def test_opt_in_and_actual_account_required(tmp_path):
    client,calls=client_for(status='active')
    pilot=MultiPlatformPilot(tmp_path,key='synthetic',client=client)
    with pytest.raises(AccessBlocked):pilot.fetch('reddit-search',{'query':'blueberries'},case_id='a')
    assert calls==[]
    pilot.enabled=True
    with pytest.raises(AccessBlocked):pilot.fetch('reddit-search',{'query':'blueberries'},case_id='a')
    assert len(calls)==1 and calls[0].url.path=='/v1/credits'

def test_every_uncached_call_balance_checked_and_restart_budget_durable(tmp_path):
    client,calls=client_for()
    pilot=MultiPlatformPilot(tmp_path,enabled=True,key='synthetic',client=client,ceiling=1)
    assert not pilot.fetch('reddit-search',{'query':'blueberries'},case_id='a')[1]
    assert [r.url.path for r in calls]==['/v1/credits','/v1/scrape/reddit/search','/v1/credits']
    assert pilot.fetch('reddit-search',{'query':'blueberries'},case_id='a')[1] and len(calls)==3
    restarted=MultiPlatformPilot(tmp_path,enabled=True,key='synthetic',client=client,ceiling=1)
    with pytest.raises(AccessBlocked):restarted.fetch('x-search',{'query':'blueberries'},case_id='b')
    assert len(calls)==4 and calls[-1].url.path=='/v1/credits'
    assert 'synthetic' not in ''.join(p.read_text() for p in tmp_path.glob('*.json'))

def test_failure_not_zero_not_retried_and_price_change_stops(tmp_path):
    client,calls=client_for(fail=True)
    pilot=MultiPlatformPilot(tmp_path,enabled=True,key='synthetic',client=client)
    with pytest.raises(AccessBlocked):pilot.fetch('reddit-search',{'query':'blueberries'},case_id='a')
    with pytest.raises(AccessBlocked,match='not retried'):pilot.fetch('reddit-search',{'query':'blueberries'},case_id='a')
    assert len(calls)==3 and pilot.ledger['attempts'][0]['state']=='provider-error'
    client,calls=client_for(price=2)
    pilot=MultiPlatformPilot(tmp_path/'other',enabled=True,key='synthetic',client=client)
    with pytest.raises(AccessBlocked,match='Unexpected'):pilot.fetch('reddit-search',{'query':'blueberries'},case_id='a')
    with pytest.raises(AccessBlocked,match='Previous price'):pilot.fetch('x-search',{'query':'blueberries'},case_id='b')
    assert len(calls)==3

def test_secret_file_label_variants_and_no_arbitrary_endpoints(tmp_path):
    path=tmp_path/'keysz.txt';path.write_text('Other credential = ignored\nSocial Vault API key: sk_live_synthetic')
    assert private_key(path)=='sk_live_synthetic'
    client,calls=client_for()
    pilot=MultiPlatformPilot(tmp_path/'run',enabled=True,key='synthetic',client=client)
    with pytest.raises(AccessBlocked):pilot.fetch('arbitrary',{},case_id='a')
    with pytest.raises(AccessBlocked):pilot.fetch('reddit-search',{'cursor':'unbounded'},case_id='a')
    assert not calls
