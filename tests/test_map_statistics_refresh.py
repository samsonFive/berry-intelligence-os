"""Explicit official-reference jobs, human selections and private/public parity."""
from copy import deepcopy
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main
from app.services import map_statistics_refresh as refresh
from app.services.global_explorer import IntelligenceQuery, snapshot_model
from app.services.map_workspace import statistics
from app.services.market_statistics_reference import group_id

ROOT = Path(__file__).resolve().parents[1]
BASELINE = json.loads((ROOT / 'data/configuration/market_statistics_reference.json').read_text(encoding='utf-8'))['groups']
TOKEN = 'explicit-reference-check-one'
ENTITIES = {'geography-portugal': {'id': 'geography-portugal', 'entity_type': 'geography', 'name': 'Portugal'}}


def proposal():
    group = deepcopy(next(group for group in BASELINE if group['country_id'] == 'geography-portugal'))
    group['metrics'][0]['value'] = 1.23
    group['accessed_date'] = '2026-10-04'
    return group


def ready(inbox_dir, token=TOKEN):
    job, _ = refresh.reserve(inbox_dir, token)
    refresh.update(inbox_dir, job['id'], status='ready', message='Ready to compare.', groups=[proposal()], capture_file='isolated-public-capture.json')
    return refresh.load(inbox_dir), job


def test_reservation_is_idempotent_and_active_check_is_reused(tmp_path):
    first, start = refresh.reserve(tmp_path, TOKEN)
    before = refresh.path(tmp_path).read_bytes()
    assert start
    assert refresh.reserve(tmp_path, TOKEN) == (first, False)
    assert refresh.reserve(tmp_path, 'another-explicit-check') == (first, False)
    assert refresh.path(tmp_path).read_bytes() == before


def test_interrupted_request_can_restart_without_old_worker_replacing_result(tmp_path, monkeypatch):
    old, _ = refresh.reserve(tmp_path, TOKEN)
    monkeypatch.setattr(refresh, 'now', lambda: datetime.now(UTC) + timedelta(minutes=6))
    new, start = refresh.reserve(tmp_path, 'new-explicit-retry-token')
    assert start and new['id'] != old['id']
    assert refresh.load(tmp_path)['jobs'][old['id']]['status'] == 'interrupted'
    assert not refresh.update(tmp_path, old['id'], status='ready', message='Old worker', groups=[proposal()])
    assert refresh.load(tmp_path)['jobs'][new['id']]['status'] == 'queued'


def test_failed_source_keeps_previous_approved_references_and_hides_details(tmp_path, monkeypatch):
    state, job = ready(tmp_path)
    refresh.apply(tmp_path, job['id'], [group_id(proposal())], state['revision'], 'Analyst')
    before = refresh.load(tmp_path)['approved']
    new, _ = refresh.reserve(tmp_path, 'new-check-failure-token')
    def unavailable(**kw):
        raise RuntimeError('PRIVATE PROVIDER DETAIL')
    monkeypatch.setattr(refresh, 'capture', unavailable)
    refresh.run(tmp_path, new['id'])
    state = refresh.load(tmp_path)
    assert state['jobs'][new['id']]['status'] == 'failed'
    assert state['approved'] == before and 'PRIVATE' not in str(state)


def test_capture_keeps_original_file_but_does_not_apply_until_selected(tmp_path, monkeypatch):
    job, _ = refresh.reserve(tmp_path, TOKEN)
    original = b'original-public-cells-and-flags'
    def capture(**kwargs):
        file = kwargs['output_dir'] / 'original.json'
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(original)
        return file, [proposal()]
    monkeypatch.setattr(refresh, 'capture', capture)
    refresh.run(tmp_path, job['id'])
    state = refresh.load(tmp_path)
    assert state['jobs'][job['id']]['status'] == 'ready' and state['approved'] == []
    refresh.apply(tmp_path, job['id'], [group_id(proposal())], state['revision'], 'Analyst')
    assert (tmp_path / refresh.SUBDIR / 'captures/original.json').read_bytes() == original
    assert refresh.load(tmp_path)['history'][0]['before'] == []
    assert refresh.load(tmp_path)['history'][0]['after'] == [proposal()]


@pytest.mark.parametrize('selected', [[], ['not-displayed'], [group_id(proposal()), 'not-displayed']])
def test_only_explicit_displayed_selections_can_be_applied(tmp_path, selected):
    state, job = ready(tmp_path)
    before = refresh.path(tmp_path).read_bytes()
    with pytest.raises(ValueError, match='Select at least'):
        refresh.apply(tmp_path, job['id'], selected, state['revision'], 'Analyst')
    assert refresh.path(tmp_path).read_bytes() == before


def test_stale_revision_cannot_overwrite_other_changes(tmp_path):
    state, job = ready(tmp_path)
    refresh.reserve(tmp_path, 'another-check-new-revision')
    before = refresh.path(tmp_path).read_bytes()
    with pytest.raises(ValueError, match='changed while'):
        refresh.apply(tmp_path, job['id'], [group_id(proposal())], state['revision'], 'Analyst')
    assert refresh.path(tmp_path).read_bytes() == before


def test_older_check_cannot_replace_newer_saved_reference(tmp_path):
    state, job = ready(tmp_path)
    refresh.apply(tmp_path, job['id'], [group_id(proposal())], state['revision'], 'Analyst')
    older, _ = refresh.reserve(tmp_path, 'older-explicit-review-token')
    old_group = proposal()
    old_group['accessed_date'] = '2026-10-03'
    refresh.update(tmp_path, older['id'], status='ready', message='Older check', groups=[old_group])
    state = refresh.load(tmp_path)
    before = refresh.path(tmp_path).read_bytes()
    with pytest.raises(ValueError, match='newer reference'):
        refresh.apply(tmp_path, older['id'], [group_id(old_group)], state['revision'], 'Analyst')
    assert refresh.path(tmp_path).read_bytes() == before


def test_one_country_selection_leaves_other_sources_and_countries_intact(tmp_path):
    state, job = ready(tmp_path)
    refresh.apply(tmp_path, job['id'], [group_id(proposal())], state['revision'], 'Analyst')
    combined = refresh.references(BASELINE, tmp_path, True)
    assert len(combined) == len(BASELINE)
    assert [group for group in combined if group['country_id'] != 'geography-portugal'] == [group for group in BASELINE if group['country_id'] != 'geography-portugal']
    before = refresh.path(tmp_path).read_bytes()
    assert not refresh.apply(tmp_path, job['id'], [group_id(proposal())], refresh.load(tmp_path)['revision'], 'Analyst')
    assert refresh.path(tmp_path).read_bytes() == before


@pytest.mark.parametrize('mutation', ['source', 'unit', 'confidential', 'nan', 'country', 'revision', 'history'])
def test_corrupt_state_is_not_hidden_or_overwritten(tmp_path, mutation):
    state, job = ready(tmp_path)
    group = state['jobs'][job['id']]['groups'][0]
    if mutation == 'source': group['source_url'] = 'https://elsewhere.invalid/figure'
    if mutation == 'unit': group['metrics'][0]['unit'] = 'million lb'
    if mutation == 'confidential': group['metrics'][0]['source_flag'] = 'c'
    if mutation == 'nan': group['metrics'][0]['value'] = float('nan')
    if mutation == 'country': group['country_id'] = 'geography-china'
    if mutation == 'revision': state['revision'] = True
    if mutation == 'history': state['history'] = [{'job_id': 'missing'}]
    refresh.path(tmp_path).write_text(json.dumps(state), encoding='utf-8')
    before = refresh.path(tmp_path).read_bytes()
    with pytest.raises(ValueError, match='history cannot'):
        refresh.reserve(tmp_path, 'another-check-new-token')
    assert refresh.path(tmp_path).read_bytes() == before


def test_private_references_match_map_snapshot_and_leave_public_data_unchanged(tmp_path, monkeypatch):
    baseline_bytes = (ROOT / 'data/configuration/market_statistics_reference.json').read_bytes()
    state, job = ready(tmp_path)
    refresh.apply(tmp_path, job['id'], [group_id(proposal())], state['revision'], 'Analyst')
    query = IntelligenceQuery(('geography-portugal',), berry_ids=('berry-strawberry',))
    private = statistics(query, ENTITIES, [], inbox_dir=tmp_path, authoring=True)
    snapshot = snapshot_model(query, [], ENTITIES, [], {'berry-strawberry':'Strawberry'}, ['statistics'], inbox_dir=tmp_path, authoring=True)
    assert private['groups'] == snapshot['statistics']['groups']
    assert private['groups'][0]['metrics'][0]['value'] == 1.23
    assert len(snapshot['packet']['source_trace']) == 1 and 'geo=PT' in snapshot['packet']['source_trace'][0]['source_url']
    monkeypatch.setattr(refresh, 'load', lambda *args: pytest.fail('Public rendering must not read private references.'))
    public = statistics(query, ENTITIES, [], inbox_dir=tmp_path, authoring=False)
    assert public['groups'][0]['metrics'][0]['value'] == 0.39
    assert (ROOT / 'data/configuration/market_statistics_reference.json').read_bytes() == baseline_bytes


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, 'INBOX_DIR', tmp_path)
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    monkeypatch.setattr(main, 'entity_index', lambda: ENTITIES)
    monkeypatch.setattr(main, 'published_evidence', lambda: [])
    monkeypatch.setattr(main, 'all_relationships', lambda: [])
    monkeypatch.setattr(main, 'all_facts', lambda: [])
    return TestClient(main.app)


def test_reading_and_progress_are_pure_explicit_check_is_guarded(client, tmp_path, monkeypatch):
    calls = []
    def run(inbox, key):
        calls.append(key)
        refresh.update(inbox, key, status='ready', message='Ready.', groups=[proposal()])
    monkeypatch.setattr(refresh, 'run', run)
    assert client.get('/explorer/statistics').status_code == 200
    assert not list(tmp_path.rglob('*'))
    assert client.post('/explorer/statistics/check', data={'token':TOKEN}, headers={'origin':'https://elsewhere.invalid'}).status_code == 403
    assert not calls
    response = client.post('/explorer/statistics/check', data={'token':TOKEN}, follow_redirects=True)
    assert response.status_code == 200 and 'Ready to compare' in response.text and len(calls) == 1
    before = refresh.path(tmp_path).read_bytes()
    assert client.get('/explorer/statistics').status_code == 200 and refresh.path(tmp_path).read_bytes() == before
    assert client.post('/explorer/statistics/check', data={'token':TOKEN}).status_code == 200 and len(calls) == 1
    monkeypatch.setattr(main, 'AUTHORING_MODE', False)
    for url in ('/explorer/statistics/check', '/explorer/statistics/apply'):
        assert client.post(url, data={'token':TOKEN}).status_code == 403
    assert client.get('/explorer/statistics').status_code == 403


def test_apply_route_keeps_scope_and_conflicts_are_readable(client, tmp_path):
    state, job = ready(tmp_path)
    form = {'job_id':job['id'], 'revision':str(state['revision']), 'group':group_id(proposal()),
            'return_to':'/explorer?countries=geography-portugal&berry=berry-strawberry&layer=companies'}
    result = client.post('/explorer/statistics/apply', data=form, follow_redirects=False)
    assert result.status_code == 303 and result.headers['location'] == form['return_to'] + '#gx-statistics'
    before = refresh.path(tmp_path).read_bytes()
    conflict = client.post('/explorer/statistics/apply', data=form)
    assert conflict.status_code == 409 and 'changed while you were reviewing' in conflict.text
    assert 'Reload references' in conflict.text and refresh.path(tmp_path).read_bytes() == before
    bad = client.post('/explorer/statistics/apply', data={**form,'revision':'not-a-number'})
    assert bad.status_code == 409 and 'invalid literal' not in bad.text


def test_snapshot_pdf_uses_selected_private_references_and_public_view_does_not(client, tmp_path, monkeypatch):
    from app.services.report_builder import pdf_export
    text = []
    paragraph = pdf_export.Paragraph
    def remember(value, style, **kwargs):
        text.append(value)
        return paragraph(value, style, **kwargs)
    monkeypatch.setattr(pdf_export, 'Paragraph', remember)
    state, job = ready(tmp_path)
    refresh.apply(tmp_path, job['id'], [group_id(proposal())], state['revision'], 'Analyst')
    params = {'countries':'geography-portugal','berry':'berry-strawberry','sections':'statistics'}
    private = client.get('/explorer/snapshot.pdf', params=params)
    assert private.status_code == 200 and private.content.startswith(b'%PDF')
    assert '1.23' in ' '.join(text) and '0.39' not in ' '.join(text)
    assert '2026-10-04' in ' '.join(text) and 'geo=PT' in ' '.join(text)
    text.clear()
    monkeypatch.setattr(main, 'AUTHORING_MODE', False)
    public = client.get('/explorer/snapshot.pdf', params=params)
    assert public.status_code == 200 and '0.39' in ' '.join(text) and '1.23' not in ' '.join(text)
