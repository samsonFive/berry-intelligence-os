import json
from pathlib import Path

import httpx
import pytest

from app.services import media_discovery
from app.services.pipeline_scheduler import classify_outcome
from scripts import refresh_news_workspace


def test_transient_publisher_507_retries_once(monkeypatch):
    calls = []
    def get(url, **kwargs):
        calls.append(url)
        return httpx.Response(507 if len(calls) == 1 else 200,
            request=httpx.Request('GET', url), content=b'<rss><channel><item><title>Blueberry news</title></item></channel></rss>')
    monkeypatch.setattr(media_discovery.httpx, 'get', get)
    monkeypatch.setattr(media_discovery.time, 'sleep', lambda _: None)
    parsed, _ = media_discovery._fetch_podcast_rss('https://berries.net.au/feed/')
    assert len(calls) == 2 and parsed.entries[0].title == 'Blueberry news'


@pytest.mark.parametrize('status,attempts', [(507, 2), (503, 2), (403, 1), (429, 1)])
def test_feed_failure_stays_visible_and_bounded(monkeypatch, status, attempts):
    calls = []
    def get(url, **kwargs):
        calls.append(url)
        return httpx.Response(status, request=httpx.Request('GET', url))
    monkeypatch.setattr(media_discovery.httpx, 'get', get)
    monkeypatch.setattr(media_discovery.time, 'sleep', lambda _: None)
    with pytest.raises(httpx.HTTPStatusError):
        media_discovery._fetch_podcast_rss('https://berries.net.au/feed/')
    assert len(calls) == attempts


@pytest.mark.parametrize('status,errors,outcome,exit_code', [
    ('ready', 0, 'SUCCESS', 0), ('partial', 1, 'PARTIAL', 0), ('failed', 1, 'FAILED', 1),
])
def test_scheduled_news_uses_same_refresh_and_reports_health(monkeypatch, capsys, status, errors, outcome, exit_code):
    from app import main
    from app import news_workspace_routes as routes
    calls = []
    monkeypatch.setattr(main, '_feed_first_world', lambda: {'fixture': True})
    monkeypatch.setattr(main, 'load_sources', lambda: [])
    monkeypatch.setattr(routes, 'run_refresh', lambda *args: calls.append(args))
    monkeypatch.setattr(routes, 'refresh_state', lambda _: {'status': status, 'error_count': errors, 'story_count': 10})
    code = refresh_news_workspace.main()
    payload = json.loads(capsys.readouterr().out)
    assert code == exit_code and calls == [(main.INBOX_DIR, {'fixture': True}, [])]
    assert classify_outcome('news_workspace_refresh', payload, code)[0] == outcome
    assert payload['counts']['publication_drafts_created'] == 0


def test_news_pipeline_is_scheduled_without_paid_or_manual_lanes():
    pipelines = json.loads(Path('data/configuration/collection_pipelines.json').read_text(encoding='utf-8'))['pipelines']
    rows = {r['id']: r for r in pipelines}
    news = rows['news_workspace_refresh']
    assert news['enabled'] and news['scheduled'] and news['schedule_entrypoint']
    assert news['cadence_seconds'] == 600 and news['runner'] == 'scripts/refresh_news_workspace.py'
    assert not rows['industry_pulse_intake']['enabled']
    assert not rows['social_manual_prepaid']['scheduled']
