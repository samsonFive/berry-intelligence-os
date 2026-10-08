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
            data = {'id': BUILD, 'buildNumber': '0.0.114', 'status': 'SUCCEEDED',
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
            return httpx.Response(201, json={'data': {'id': 'run12345', 'status': 'RUNNING'}})
        else:
            data = {'currentPricingInfo': {'pricingModel': 'PAY_PER_EVENT'},
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
