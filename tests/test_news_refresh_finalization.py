"""A failed optional classifier must not strand a completed News capture."""
import json

import pytest

from app import news_workspace_routes as routes
from app.services import feed_first_live


@pytest.mark.parametrize('source_errors', [[], [{'reason': 'A source was unavailable'}]])
def test_tag_failure_finalizes_capture_without_retry_or_losing_stories(tmp_path, monkeypatch, source_errors):
    calls = []

    def collect(**kwargs):
        calls.append(('collect', kwargs))
        return {'records': [{'id': 'new-story'}, {'id': 'other-story'}], 'lane_errors': source_errors}

    def classify():
        calls.append(('classify', None))
        raise RuntimeError('provider detail must stay out of the user message')

    monkeypatch.setattr(feed_first_live, 'live_feed_bundle', collect)
    monkeypatch.setattr(routes, 'classify_stored_tags', classify)
    context = {'entities': [], 'official_hosts': [], 'official_host_map': {}, 'muted_entity_ids': []}
    routes.run_refresh(tmp_path, context, [])

    state = routes.refresh_state(tmp_path)
    assert state['status'] == 'partial'
    assert state['story_count'] == 2
    assert state['error_count'] == len(source_errors) + 1
    assert state['completed_at'] >= state['started_at']
    assert 'existing tags are retained' in state['message']
    assert 'provider detail' not in json.dumps(state)
    assert [name for name, _ in calls] == ['collect', 'classify']
    options = calls[0][1]
    assert all(options[key] is False for key in ['enable_perplexity', 'enable_exa', 'enable_apitube'])
    assert not (tmp_path / 'operations' / 'collection.lock').exists()
    receipts = list((tmp_path / 'operations' / 'pipelines' / 'news_workspace_refresh' / 'runs').glob('*.json'))
    assert len(receipts) == 1
    receipt = json.loads(receipts[0].read_text())
    assert receipt['outcome'] == 'PARTIAL' and receipt['failure_count'] == len(source_errors) + 1
    assert receipt['items_new'] == 2 and receipt['publication_drafts'] == 0


def test_capture_failure_still_fails_and_does_not_classify(tmp_path, monkeypatch):
    def collect(**kwargs):
        raise RuntimeError('capture failed')

    monkeypatch.setattr(feed_first_live, 'live_feed_bundle', collect)
    monkeypatch.setattr(routes, 'classify_stored_tags', lambda: pytest.fail('No tags after failed capture'))
    routes.run_refresh(tmp_path, {'entities': [], 'official_hosts': [], 'official_host_map': {}, 'muted_entity_ids': []}, [])
    state = routes.refresh_state(tmp_path)
    assert state['status'] == 'failed' and state['error_count'] == 1 and state['completed_at']


def test_successful_capture_keeps_ready_status(tmp_path, monkeypatch):
    monkeypatch.setattr(feed_first_live, 'live_feed_bundle', lambda **kwargs: {'records': [{'id': 'story'}]})
    monkeypatch.setattr(routes, 'classify_stored_tags', lambda: None)
    routes.run_refresh(tmp_path, {'entities': [], 'official_hosts': [], 'official_host_map': {}, 'muted_entity_ids': []}, [])
    state = routes.refresh_state(tmp_path)
    assert state['status'] == 'ready' and state['error_count'] == 0
    assert state['story_count'] == 1 and state['completed_at']
