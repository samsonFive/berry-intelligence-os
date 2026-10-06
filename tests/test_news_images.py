"""Publisher thumbnails and honest visual fallbacks across the reading flow."""
from copy import deepcopy
import json
import base64
import os
from time import time

from app import main
from app.services import news_images, feed_first_reader as reader
from tests.test_news_workspace import article, workspace


def test_bounded_capture_preserves_source_records_and_reuses_metadata(tmp_path):
    rows = [article('ev-photo-' + str(i)) for i in range(45)]
    before = deepcopy(rows)
    calls = []
    def fetch(url):
        calls.append(url)
        return 'https://publisher.example/photo.jpg'
    result = news_images.collect(tmp_path, rows, fetch=fetch)
    assert result == {'checked': 36, 'found': 36} and len(calls) == 36
    assert rows == before
    assert news_images.collect(tmp_path, rows[:36], fetch=fetch)['checked'] == 0
    assert not reader.capture_path(tmp_path, rows[0]['id']).exists()
    projected = reader.attach_capture_previews({row['id']: row for row in rows}, tmp_path)
    assert projected[rows[0]['id']]['image_url'] == 'https://publisher.example/photo.jpg'
    assert projected[rows[0]['id']]['status'] == before[0]['status']
    changed = {**rows[0], 'source_url': 'https://publisher.example/changed'}
    assert reader.attach_capture_previews({changed['id']: changed}, tmp_path)[changed['id']] == changed


def test_missing_images_retry_after_a_day_and_unsafe_urls_stay_empty(tmp_path):
    row = article()
    calls = []
    def fetch(url):
        calls.append(url)
        return 'http://127.0.0.1/private.jpg'
    assert news_images.collect(tmp_path, [row], fetch=fetch)['found'] == 0
    assert news_images.collect(tmp_path, [row], fetch=fetch)['checked'] == 0
    path = news_images.preview_path(tmp_path, row['id'])
    os.utime(path, (time() - 90000, time() - 90000))
    assert news_images.collect(tmp_path, [row], fetch=fetch)['checked'] == 1
    assert json.loads(path.read_text())['image_url'] == ''
    assert len(calls) == 2


def test_capture_uses_existing_source_images_and_refuses_private_sources(tmp_path):
    rows = [article(image_url='https://publisher.example/existing.jpg'),
            article('ev-private', source_url='http://127.0.0.1/secret')]
    def fetch(url):
        raise AssertionError('Neither source should be fetched')
    assert news_images.collect(tmp_path, rows, fetch=fetch)['checked'] == 0
    assert list(tmp_path.iterdir()) == []


def test_decodable_wrapper_keeps_original_identity_and_explicit_retry(tmp_path):
    publisher = 'https://publisher.example/blueberry-story'
    token = base64.urlsafe_b64encode(publisher.encode()).decode().rstrip('=')
    row = article(source_url='https://news.google.com/rss/articles/' + token)
    calls = []
    def missing(url):
        calls.append(url)
        return ''
    news_images.collect(tmp_path, [row], fetch=missing)
    news_images.collect(tmp_path, [row], fetch=missing, retry_missing=True)
    assert calls == [publisher, publisher]
    assert json.loads(news_images.preview_path(tmp_path, row['id']).read_text())['source_url'] == row['source_url']


def test_news_reader_digest_show_labeled_illustrations_and_real_images_win(workspace, monkeypatch):
    html = workspace.get('/today').text
    assert '/static/news-images/blueberry-orchard.webp' in html
    assert 'AI-generated agricultural illustration' in html
    assert workspace.post('/digest/stories/live-raw', json={'action': 'save'}).status_code == 200
    assert '/static/news-images/blueberry-orchard.webp' in workspace.get('/digest').text
    reader_html = workspace.get('/api/intelligence/live-raw/reader?personal=1').text
    assert 'Illustration' in reader_html and 'not an article photograph' in reader_html
    monkeypatch.setattr(reader, 'fetch_source_preview_image', lambda url: 'https://publisher.example/article.jpg')
    assert workspace.post('/api/news/images?company=company-grower').status_code == 202
    state = workspace.get('/api/news/images').json()
    assert state['status'] == 'ready' and state['found'] == 2
    html = workspace.get('/today').text
    assert 'src="https://publisher.example/article.jpg"' in html and 'data-publisher-image' in html
    assert 'data-image-fallback hidden' in html
    assert 'https://publisher.example/article.jpg' in workspace.get('/digest').text
    assert 'https://publisher.example/article.jpg' in workspace.get('/api/intelligence/live-raw/reader?personal=1').text
    assert 'data-image-fallback hidden' in workspace.get('/today?view=trusted').text or 'No news matches' in workspace.get('/today?view=trusted').text


def test_thumbnail_action_keeps_scope_and_edit_gates(workspace, monkeypatch):
    monkeypatch.setattr(reader, 'fetch_source_preview_image', lambda url: 'https://publisher.example/article.jpg')
    assert workspace.post('/api/news/images?company=company-other').status_code == 202
    assert workspace.get('/api/news/images').json()['checked'] == 0
    assert workspace.post('/api/news/images', headers={'origin':'https://other.example'}).status_code == 403
    monkeypatch.setattr(main, 'AUTHORING_MODE', False)
    assert workspace.post('/api/news/images').status_code == 403
