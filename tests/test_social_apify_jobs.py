"""Offline transport/ledger failure checks; never real Apify calls."""
import json
import httpx
import pytest

from app.services.social_intelligence.apify_jobs import ApifyJobs
from app.services.social_intelligence.adapters import AccessBlocked

ACTOR = 'harvestapi/linkedin-post-search'
BUILD = 'build12345'
INPUT = {'searchQueries': ['blueberry sorting']}


def harness(tmp_path, *, submission_error=False, status='RUNNING', paying=False):
    requests = []
    def handle(request):
        requests.append(request)
        path = request.url.path
        if path.endswith('/users/me'):
            data = {'plan': {'id': 'FREE'}, 'isPaying': paying}
        elif path.endswith('/users/me/limits'):
            data = {'limits': {'maxMonthlyUsageUsd': 5},
                    'current': {'monthlyUsageUsd': .1, 'activeActorJobCount': 0}}
        elif '/actor-builds/' in path:
            data = {'id': BUILD, 'actId': 'actor12345', 'buildNumber': '0.0.114', 'status': 'SUCCEEDED',
                    'inputSchema': json.dumps({'type': 'object', 'required': ['searchQueries'],
                                             'properties': {'searchQueries': {'type': 'array'}}})}
        elif '/actor-runs/' in path:
            data = {'id': 'run12345', 'buildId': BUILD, 'status': status,
                    'defaultDatasetId': 'dataset12345', 'usageTotalUsd': .01}
        elif '/datasets/' in path:
            return httpx.Response(200, json=[{'id': 'post12345', 'text': 'Blueberry sorter'}])
        elif request.method == 'POST':
            if submission_error:
                raise httpx.ReadTimeout('Ambiguous response', request=request)
            return httpx.Response(201, json={'data': {'id': 'run12345', 'actId': 'actor12345', 'buildId': BUILD, 'status': 'RUNNING'}})
        else:
            data = {'id': 'actor12345', 'currentPricingInfo': {'pricingModel': 'PAY_PER_EVENT'},
                    'defaultRunOptions': {'memoryMbytes': 4096}}
        return httpx.Response(200, json={'data': data})
    client = httpx.Client(transport=httpx.MockTransport(handle))
    return ApifyJobs(tmp_path, enabled=True, client=client, token='synthetic-secret'), requests, client


def launch(jobs, case='blueberry-sorting', **overrides):
    return jobs.launch(case, ACTOR, build_id=BUILD, build_number='0.0.114', actor_input=INPUT, **overrides)


def test_restart_reuses_reservation_and_polls_same_run(tmp_path):
    jobs, requests, client = harness(tmp_path)
    first = launch(jobs)
    restarted = ApifyJobs(tmp_path, enabled=True, client=client, token='synthetic-secret')
    assert launch(restarted)['reused'] is True
    observed = restarted.observe('blueberry-sorting')
    assert observed == {'case': 'blueberry-sorting', 'run_id': first['run_id'],
                        'state': 'RUNNING', 'terminal': False, 'items': None}
    posts = [r for r in requests if r.method == 'POST']
    assert len(posts) == 1
    assert posts[0].url.params['build'] == '0.0.114'
    assert posts[0].url.params['maxTotalChargeUsd'] == '0.1'
    assert posts[0].url.params['restartOnError'] == 'false'
    assert posts[0].url.params['forcePermissionLevel'] == 'LIMITED_PERMISSIONS'
    assert all(r.headers['Authorization'] == 'Bearer synthetic-secret' for r in requests)
    assert 'synthetic-secret' not in (tmp_path / 'ledger.json').read_text()


def test_ambiguous_submission_never_relaunches(tmp_path):
    jobs, requests, client = harness(tmp_path, submission_error=True)
    with pytest.raises(AccessBlocked, match='transport'):
        launch(jobs)
    restarted = ApifyJobs(tmp_path, enabled=True, client=client, token='synthetic-secret')
    assert launch(restarted)['state'] == 'reserved-before-launch'
    with pytest.raises(AccessBlocked, match='No saved run'):
        restarted.observe('blueberry-sorting')
    assert len([r for r in requests if r.method == 'POST']) == 1


def test_terminal_success_bounds_dataset_and_persists_private_items(tmp_path):
    jobs, requests, _ = harness(tmp_path, status='SUCCEEDED')
    launch(jobs)
    observed = jobs.observe('blueberry-sorting')
    assert observed['terminal'] and len(observed['items']) == 1
    assert json.loads((tmp_path / 'blueberry-sorting-items.json').read_text()) == observed['items']
    dataset = next(r for r in requests if '/datasets/' in r.url.path)
    assert dataset.url.params['limit'] == '20'


def test_failed_actor_is_not_successful_zero(tmp_path):
    jobs, requests, _ = harness(tmp_path, status='FAILED')
    launch(jobs)
    observed = jobs.observe('blueberry-sorting')
    assert observed['terminal'] and observed['state'] == 'FAILED' and observed['items'] is None
    assert not any('/datasets/' in r.url.path for r in requests)


def test_paid_account_and_exhausted_reservations_block_post(tmp_path):
    jobs, requests, _ = harness(tmp_path, paying=True)
    with pytest.raises(AccessBlocked, match='guard'):
        launch(jobs)
    assert not any(r.method == 'POST' for r in requests)
    jobs, requests, _ = harness(tmp_path)
    tmp_path.joinpath('ledger.json').write_text(json.dumps({'ceiling_free_credit_usd': .2,
        'cash_spend': 0, 'attempts': [{'case': 'prior', 'cap_usd': .1}, {'case': 'other', 'cap_usd': .1}]}))
    with pytest.raises(AccessBlocked, match='guard'):
        launch(jobs)
    assert not any(r.method == 'POST' for r in requests)


def test_input_pin_changes_and_corrupt_ledger_fail_closed(tmp_path):
    jobs, requests, _ = harness(tmp_path)
    launch(jobs)
    with pytest.raises(AccessBlocked, match='differs'):
        jobs.launch('blueberry-sorting', ACTOR, build_id=BUILD, build_number='0.0.114', actor_input={'searchQueries': ['other']})
    tmp_path.joinpath('ledger.json').write_text('{bad')
    with pytest.raises(AccessBlocked, match='unreadable'):
        launch(jobs, 'new-case')
    assert len([r for r in requests if r.method == 'POST']) == 1


def test_wrong_actor_build_is_rejected_before_reservation(tmp_path):
    jobs, requests, client = harness(tmp_path)
    original = client._transport
    def handle(request):
        response = original.handle_request(request)
        if '/actor-builds/' in request.url.path:
            payload = response.json();payload['data']['actId'] = 'otherActor'
            return httpx.Response(200,json=payload)
        return response
    jobs.client = httpx.Client(transport=httpx.MockTransport(handle))
    with pytest.raises(AccessBlocked,match='pin'):
        launch(jobs)
    assert not any(r.method == 'POST' for r in requests)
    assert not (tmp_path/'ledger.json').exists()


def test_observe_rejects_path_cases_and_duplicate_ledger_cases(tmp_path):
    jobs, requests, _ = harness(tmp_path)
    with pytest.raises(ValueError,match='identifier'):
        jobs.observe('../outside')
    tmp_path.joinpath('ledger.json').write_text(json.dumps({'ceiling_free_credit_usd':1,
        'cash_spend':0,'attempts':[{'case':'same','cap_usd':.1},{'case':'same','cap_usd':.1}]}))
    with pytest.raises(AccessBlocked,match='unreadable'):
        launch(jobs)
    assert requests == []


def test_null_current_pricing_selects_effective_history_not_future(tmp_path):
    jobs, requests, client = harness(tmp_path)
    original = client._transport
    def handle(request):
        response=original.handle_request(request)
        if '/acts/' in request.url.path and request.method=='GET':
            payload=response.json();payload['data']['currentPricingInfo']=None
            payload['data']['pricingInfos']=[
                {'pricingModel':'PAY_PER_EVENT','startedAt':'2020-01-01T00:00:00Z'},
                {'pricingModel':'RENTAL','startedAt':'2099-01-01T00:00:00Z'}]
            return httpx.Response(200,json=payload)
        return response
    jobs.client=httpx.Client(transport=httpx.MockTransport(handle))
    result=launch(jobs)
    assert result['pricing_model']=='PAY_PER_EVENT'
    assert result['pricing_started_at']=='2020-01-01T00:00:00Z'
    assert len([r for r in requests if r.method=='POST'])==1



def test_cached_normalization_is_offline_imported_and_keeps_time(tmp_path):
    jobs, requests, _ = harness(tmp_path, status='SUCCEEDED')
    launch(jobs);jobs.observe('blueberry-sorting')
    # Replace synthetic minimal transport item with inspected synthetic shape.
    tmp_path.joinpath('blueberry-sorting-items.json').write_text(json.dumps([
        {'type':'post','id':'post12345','linkedinUrl':'https://www.linkedin.com/posts/test/',
         'content':'Blueberry supplier','postedAt':{'date':'2026-10-07T10:00:00Z'}}]))
    before=len(requests)
    offline=ApifyJobs(tmp_path,enabled=False,token=None)
    receipt=offline.normalize_cached('blueberry-sorting')
    assert len(requests)==before and receipt['mode']=='imported' and not receipt['ingested']
    assert receipt['normalized']==1 and receipt['rejected']==0
    rows=json.loads(tmp_path.joinpath('blueberry-sorting-normalized-import.json').read_text())
    ledger=json.loads(tmp_path.joinpath('ledger.json').read_text())
    assert rows[0]['collected_at']==ledger['attempts'][0]['data_observed_at'].replace('+00:00','Z')
    assert rows[0]['publication_date_basis']=='estimated' and rows[0]['language']=='und'
    assert rows[0]['mode']=='imported' and rows[0]['content_role']=='unknown'
    assert offline.normalize_cached('blueberry-sorting')['normalized']==1


def test_unfinished_cache_does_not_become_import_or_successful_zero(tmp_path):
    jobs, requests, _ = harness(tmp_path)
    launch(jobs)
    tmp_path.joinpath('blueberry-sorting-items.json').write_text('[]')
    before=len(requests)
    with pytest.raises(AccessBlocked,match='Successful saved job'):
        jobs.normalize_cached('blueberry-sorting')
    assert len(requests)==before and not tmp_path.joinpath('blueberry-sorting-normalized-import.json').exists()



def test_cached_health_never_turns_failure_or_metadata_into_zero(tmp_path):
    jobs, requests, _ = harness(tmp_path,status='SUCCEEDED')
    launch(jobs);jobs.observe('blueberry-sorting')
    before=len(requests)
    assert jobs.cached_status()['jobs'][0]['observed_volume'] is None
    # The minimal fixture response is metadata, not a valid post.
    jobs.normalize_cached('blueberry-sorting')
    status=jobs.cached_status()
    assert status['jobs'][0]['status']=='failed'
    assert status['jobs'][0]['observed_volume'] is None
    assert status['reserved_free_credit_usd']==.1 and not status['fresh_account_verified']
    assert len(requests)==before


def test_empty_normalized_search_is_zero_but_changed_cache_is_unverified(tmp_path):
    jobs, requests, _ = harness(tmp_path,status='SUCCEEDED')
    launch(jobs);jobs.observe('blueberry-sorting')
    tmp_path.joinpath('blueberry-sorting-items.json').write_text('[]')
    jobs.normalize_cached('blueberry-sorting')
    before=len(requests)
    status=jobs.cached_status()['jobs'][0]
    assert status['status']=='partial' and status['observed_volume']==0 and status['last_success']
    receipt_path=tmp_path/'blueberry-sorting-normalization.json'
    receipt=json.loads(receipt_path.read_text());receipt['data_observed_at']='invalid'
    receipt_path.write_text(json.dumps(receipt))
    invalid=jobs.cached_status()['jobs'][0]
    assert invalid['status']=='unknown' and invalid['observed_volume'] is None and invalid['last_success'] is None
    jobs.normalize_cached('blueberry-sorting')
    tmp_path.joinpath('blueberry-sorting-items.json').write_text('[{}]')
    assert jobs.cached_status()['jobs'][0]['observed_volume'] is None
    assert len(requests)==before


def test_explicit_two_dollar_allowance_preserves_consumed_reservations(tmp_path):
    jobs, requests, client = harness(tmp_path)
    attempts=[{'case':f'prior-{i}','cap_usd':.1,'state':'FAILED'} for i in range(10)]
    tmp_path.joinpath('ledger.json').write_text(json.dumps({'ceiling_free_credit_usd':2,'cash_spend':0,'attempts':attempts}))
    launch(jobs)
    saved=json.loads(tmp_path.joinpath('ledger.json').read_text())
    assert saved['attempts'][:10]==attempts and len(saved['attempts'])==11
    assert len([r for r in requests if r.method=='POST'])==1
    saved['attempts']=[{'case':f'prior-{i}','cap_usd':.1,'state':'FAILED'} for i in range(20)]
    tmp_path.joinpath('ledger.json').write_text(json.dumps(saved))
    with pytest.raises(AccessBlocked,match='budget guard'):
        launch(ApifyJobs(tmp_path,enabled=True,client=client,token='synthetic-secret'),case='next-case')
    assert len([r for r in requests if r.method=='POST'])==1


def test_allowance_defaults_to_one_and_rejects_above_authorized_maximum(tmp_path):
    jobs, requests, _ = harness(tmp_path)
    assert jobs._read()['ceiling_free_credit_usd']==1
    tmp_path.joinpath('ledger.json').write_text(json.dumps({'ceiling_free_credit_usd':2.01,'cash_spend':0,'attempts':[]}))
    with pytest.raises(AccessBlocked,match='ledger unreadable'):
        launch(jobs)
    assert not requests


@pytest.mark.parametrize('override',[{'searchType':'profile'},{'maxItems':6},{'maxItems':True},{'maxComments':1},{'maxFollowers':1},{'unknownAddon':1}])
def test_x_search_rejects_addons_and_unbounded_inputs_before_requests(tmp_path,override):
    jobs, requests, _ = harness(tmp_path)
    inputs={'searchType':'search','searchQuery':'blueberries','maxItems':5,**override}
    with pytest.raises(AccessBlocked,match='bounded search only'):
        jobs.launch('x-trial','atomus/twitter-scraper',build_id=BUILD,build_number='1.0.45',actor_input=inputs)
    assert not requests and not tmp_path.joinpath('ledger.json').exists()
