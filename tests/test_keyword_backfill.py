import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.services import keyword_backfill as backfill, collection_settings as settings
from app.repositories.paths import SCHEMAS_DIR


def setup_monitor(inbox):
    key = settings.change(inbox, key='', kind='query', group='today_google', action='save', revision='',
        label='Floricane developments', enabled=True, query_builder=True, query_input='Floricane', scope_berry='blackberry')
    return key, settings.fingerprint(settings.load(inbox)['entries'][key])


def candidate(url='https://example.org/ervin', stamp='2026-02-08', topic='Floricane'):
    text = f'{topic} blackberry cultivar Ervin was introduced following field trials. '
    text += 'The university describes the variety and its production characteristics for growers. ' * 4
    return dict(title='Ervin blackberry cultivar release', source_url=url, published_date=stamp,
        retrieved_at='2026-10-27T12:00:00+00:00', publication_date_basis='publisher_metadata',
        article={'paragraphs': [{'index': 0, 'text': text}]}, passage=text, capture_status='full', source_version='fixture')


def discovered(rows):
    return lambda plan, **kwargs: dict(status='complete', failures=[], items=rows, queries=[plan.raw_query],
                                     queries_this_request=1, candidate_count=len(rows), capture_count=len(rows))


def test_backfill_collects_real_pending_body_and_reuses_it_without_trust_promotion(tmp_path):
    from app.services.topic_retrieval import retrieve, plan_query
    inbox, data = tmp_path/'inbox', tmp_path/'data'
    key, revision = setup_monitor(inbox)
    kwargs = dict(key=key, revision=revision, start='2026-01-01', end='2026-10-26', limit=10, actor='fixture')
    job = backfill.enqueue(inbox, **kwargs)
    with pytest.raises(ValueError, match='already running'):
        backfill.enqueue(inbox, **kwargs)
    discovery = discovered([candidate(), candidate('https://example.org/old', '2020-01-01'),
        candidate('https://example.org/undated', ''), candidate('https://example.org/raspberry', topic='Primocane')])
    result = backfill.execute(inbox, job['id'], data, SCHEMAS_DIR, discoverer=discovery)
    assert result['status'] == 'complete', result
    assert result['counts'] == dict(candidates=4, selected=1, collected=1, duplicates=0, skipped=3, failed=0)
    drafts = [json.loads(p.read_text(encoding='utf-8')) for p in (inbox/'evidence').glob('*.json')]
    assert len(drafts) == 1 and drafts[0]['status'] == 'draft' and drafts[0]['review_state'] == 'in_review'
    assert drafts[0]['published_date'] == '2026-02-08' and drafts[0]['article']['paragraphs']
    assert retrieve(drafts, plan_query('Blackberry Floricans'))
    assert not list((data/'evidence').glob('*.json'))
    before = (inbox/'evidence'/f"{drafts[0]['id']}.json").read_bytes()
    second = backfill.enqueue(inbox, **kwargs)
    repeated = backfill.execute(inbox, second['id'], data, SCHEMAS_DIR, discoverer=discovery)
    assert repeated['counts']['duplicates'] == 1 and repeated['counts']['collected'] == 0
    assert (inbox/'evidence'/f"{drafts[0]['id']}.json").read_bytes() == before


def test_scope_matching_requires_terms_crop_and_region_in_body():
    row = settings.compile_custom_query(query_input='Floricane, cultivar release', scope_berry='blackberry', term_match='any')
    assert backfill._scope_matches(row, candidate())
    row['term_match'] = 'all'
    assert not backfill._scope_matches(row, candidate())
    row = settings.compile_custom_query(query_input='Floricane', scope_berry='blackberry', scope_region='europe')
    assert not backfill._scope_matches(row, candidate())
    european = candidate(); european['article']['paragraphs'][0]['text'] += ' Trials in Spain.'
    assert backfill._scope_matches(row, european)


def test_dates_stale_monitors_failures_and_limits_are_honest(tmp_path):
    inbox = tmp_path/'inbox'
    key, revision = setup_monitor(inbox)
    args = dict(key=key, revision=revision, start='2026-01-01', end='2026-10-26', limit=10, actor='fixture')
    for override in ({'start':'invalid'}, {'start':'2026-10-27'}, {'end':'2099-01-01'}, {'limit':21}, {'revision':'stale'}):
        with pytest.raises(ValueError):
            backfill.enqueue(inbox, **{**args, **override})
    job = backfill.enqueue(inbox, **args)
    result = backfill.execute(inbox, job['id'], tmp_path/'data', SCHEMAS_DIR,
        discoverer=lambda *a, **k: {'status':'unavailable', 'items':[], 'failures':['MissingCredentialError']})
    assert result['status'] == 'failed' and not (inbox/'evidence').exists()
    with pytest.raises(ValueError):
        backfill.read(inbox, '../outside')


def test_backfill_routes_require_authoring_csrf_and_explicit_provider(tmp_path, monkeypatch):
    import app.main as main
    inbox, data = tmp_path/'inbox', tmp_path/'data'
    key, revision = setup_monitor(inbox)
    monkeypatch.setattr(main, 'INBOX_DIR', inbox)
    monkeypatch.setattr(main, 'DATA_DIR', data)
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    monkeypatch.setattr(main, '_feed_first_world', lambda: {'official_hosts':set()})
    monkeypatch.setenv('BIOS_REMOTE_INTERACTIVE', 'false')
    monkeypatch.setattr(backfill, 'execute', lambda *a: None)
    client = TestClient(main.app)
    page = client.get('/settings/collection')
    token = re.search(r'name="csrf_token" value="([^"]+)"', page.text)[1]
    args = dict(key=key, revision=revision, start='2026-01-01', end='2026-10-26', limit='10')
    endpoint = '/settings/collection/backfill'
    assert client.post(endpoint, data=args).status_code == 403
    args['csrf_token'] = token
    assert client.post(endpoint, data=args).status_code == 400
    args['provider'] = 'perplexity_search'
    assert client.post(endpoint, data=args, follow_redirects=False).status_code == 303
    page = client.get('/settings/collection')
    assert page.status_code == 200 and 'Historical backfills' in page.text
    job = backfill.recent(inbox)[0]
    assert client.get('/settings/collection/backfills/'+job['id']).json()['status'] == 'queued'
    monkeypatch.setattr(main, 'AUTHORING_MODE', False)
    assert client.post(endpoint, data=args).status_code == 403


def test_queued_monitor_edit_stops_before_provider_and_corrupt_run_stays_visible(tmp_path):
    inbox = tmp_path/'inbox'
    key, revision = setup_monitor(inbox)
    job = backfill.enqueue(inbox, key=key, revision=revision, start='2026-01-01', end='2026-10-26', limit=1, actor='fixture')
    settings.change(inbox, key=key, kind='query', group='today_google', action='remove', revision=revision)
    def forbidden(*args, **kwargs):
        raise AssertionError('Changed monitor must not issue provider calls')
    result = backfill.execute(inbox, job['id'], tmp_path/'data', SCHEMAS_DIR, discoverer=forbidden)
    assert result['status'] == 'failed' and not (inbox/'evidence').exists()
    (backfill.folder(inbox)/(job['id']+'.json')).write_text('broken')
    assert backfill.recent(inbox)[0]['label'] == 'Unreadable backfill record'


def test_interrupted_backfill_resumes_saved_candidates_without_provider_calls(tmp_path, monkeypatch):
    from datetime import datetime, timedelta, timezone
    inbox, data = tmp_path/'inbox', tmp_path/'data'
    key, revision = setup_monitor(inbox)
    job = backfill.enqueue(inbox, key=key, revision=revision, start='2026-01-01',
                           end='2026-10-26', limit=10, actor='fixture')
    original_write = backfill._write
    def crash_after_first_checkpoint(path, value):
        original_write(path, value)
        if value.get('next_candidate') == 1:
            raise SystemExit('simulated process interruption')
    monkeypatch.setattr(backfill, '_write', crash_after_first_checkpoint)
    second = candidate('https://example.org/second', stamp='2026-09-01')
    second['title'] = 'New European floricane blackberry licensing programme'
    second['article']['paragraphs'][0]['text'] += ' A separate licensing announcement describes European development rights.'
    with pytest.raises(SystemExit):
        backfill.execute(inbox, job['id'], data, SCHEMAS_DIR,
                         discoverer=discovered([candidate(), second]))
    monkeypatch.setattr(backfill, '_write', original_write)
    path = backfill.folder(inbox)/(job['id']+'.json')
    saved = json.loads(path.read_text())
    assert saved['next_candidate'] == 1 and saved['counts']['collected'] == 1
    saved['updated_at'] = (datetime.now(timezone.utc)-timedelta(minutes=21)).isoformat()
    original_write(path, saved)
    assert backfill.read(inbox, job['id'])['status'] == 'interrupted'
    backfill.resume(inbox, job['id'], actor='reviewer')
    def forbidden_search(*args, **kwargs):
        raise AssertionError('resume must not call an external provider')
    result = backfill.execute(inbox, job['id'], data, SCHEMAS_DIR, discoverer=forbidden_search)
    assert result['status'] == 'complete'
    assert result['counts']['collected'] == 2 and result['counts']['selected'] == 2
    assert len(result['items']) == 2
    assert len(list((inbox/'evidence').glob('*.json'))) == 2
    assert not list((data/'evidence').glob('*.json'))
    assert backfill.execute(inbox, job['id'], data, SCHEMAS_DIR, discoverer=forbidden_search) == result


def test_resume_requires_saved_search_and_unchanged_monitor(tmp_path):
    inbox = tmp_path/'inbox'
    key, revision = setup_monitor(inbox)
    job = backfill.enqueue(inbox, key=key, revision=revision, start='2026-01-01',
                           end='2026-10-26', limit=10, actor='fixture')
    path = backfill.folder(inbox)/(job['id']+'.json')
    job['status'] = 'failed'
    backfill._write(path, job)
    with pytest.raises(ValueError, match='No completed search'):
        backfill.resume(inbox, job['id'], actor='reviewer')
    job.update(candidates=[], discovery={'status':'complete'}, revision='changed')
    backfill._write(path, job)
    with pytest.raises(ValueError, match='monitor changed'):
        backfill.resume(inbox, job['id'], actor='reviewer')


def test_resume_route_is_csrf_protected_and_status_omits_captured_bodies(tmp_path, monkeypatch):
    import app.main as main
    inbox = tmp_path/'inbox'
    key, revision = setup_monitor(inbox)
    job = backfill.enqueue(inbox, key=key, revision=revision, start='2026-01-01',
                           end='2026-10-26', limit=10, actor='fixture')
    job.update(status='failed', candidates=[candidate()], discovery={'status':'complete'})
    backfill._write(backfill.folder(inbox)/(job['id']+'.json'), job)
    monkeypatch.setattr(main, 'INBOX_DIR', inbox)
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    monkeypatch.setattr(main, '_feed_first_world', lambda: {'official_hosts':set()})
    monkeypatch.setenv('BIOS_REMOTE_INTERACTIVE', 'false')
    monkeypatch.setattr(backfill, 'execute', lambda *args: None)
    client = TestClient(main.app)
    page = client.get('/settings/collection')
    assert 'Resume saved backfill' in page.text
    token = re.search(r'name="csrf_token" value="([^"]+)"', page.text)[1]
    endpoint = '/settings/collection/backfills/'+job['id']+'/resume'
    assert client.post(endpoint).status_code == 403
    status = client.get('/settings/collection/backfills/'+job['id']).json()
    assert 'candidates' not in status and 'monitor' not in status
    assert client.post(endpoint, data={'csrf_token':token}, follow_redirects=False).status_code == 303
    assert backfill.read(inbox, job['id'])['status'] == 'queued'
    monkeypatch.setattr(main, 'AUTHORING_MODE', False)
    assert client.post(endpoint, data={'csrf_token':token}).status_code == 403
