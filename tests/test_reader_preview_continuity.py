"""Captured article images reach cards without original text reads or fetching."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from app import main
from app.services import feed_first, personal_digest
from app.services import feed_first_reader as reader
from tests.test_personal_digest import article, workspace

IMAGE = 'https://publisher.example/blueberry-news.jpg'


def capture(row, **changes):
    return {'item_id': row['id'], 'requested_url': row['source_url'], 'url': 'https://publisher.example/redirected-story',
            'ok': True, 'availability': 'partial', 'passages': ['ORIGINAL BODY NEVER READ FOR CARD IMAGES'],
            'images': [{'url': IMAGE}], **changes}


def test_preview_projection_preserves_records_without_reading_body_or_fetching(tmp_path, monkeypatch):
    row = article()
    before = deepcopy(row)
    reader.save_capture(tmp_path, row['id'], capture(row))
    body = reader.capture_path(tmp_path, row['id'])
    original_bytes = body.read_bytes()
    real_read = Path.read_text
    def bounded_read(path, *args, **kwargs):
        assert path != body, 'Feed image projection must not read original body'
        return real_read(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'read_text', bounded_read)
    monkeypatch.setattr(reader, 'fetch_public_article', lambda *a, **k: pytest.fail('Browsing must not fetch'))
    projected = personal_digest.source_records([row], tmp_path)
    assert projected[row['id']]['image_url'] == IMAGE
    assert projected[row['id']]['summary'] == before['summary']
    assert projected[row['id']]['status'] == 'published'
    assert 'article' not in projected[row['id']]
    assert row == before and body.read_bytes() == original_bytes
    sidecar = body.parent / 'previews' / body.name
    assert set(json.loads(sidecar.read_text())) == {'item_id', 'source_url', 'image_url'}


@pytest.mark.parametrize('changes', [
    {'item_id': 'ev-other'}, {'source_url': 'https://publisher.example/other'},
    {'image_url': 'javascript:alert(1)'}, {'image_url': 'http://127.0.0.1/private'},
])
def test_mismatched_or_unsafe_sidecar_cannot_supply_image(tmp_path, changes):
    row = article()
    body = reader.capture_path(tmp_path, row['id'])
    sidecar = body.parent / 'previews' / body.name
    sidecar.parent.mkdir(parents=True)
    sidecar.write_text(json.dumps({'item_id': row['id'], 'source_url': row['source_url'], 'image_url': IMAGE, **changes}))
    assert reader.attach_capture_previews({row['id']: row}, tmp_path) == {row['id']: row}


def test_existing_image_wins_and_public_projection_never_reads_private_sidecars(tmp_path, monkeypatch):
    row = article(image_url='https://publisher.example/existing.jpg')
    reader.save_capture(tmp_path, row['id'], capture(row))
    assert reader.attach_capture_previews({row['id']: row}, tmp_path)[row['id']]['image_url'] == row['image_url']
    monkeypatch.setattr(reader, 'attach_capture_previews', lambda *a, **k: pytest.fail('Public projection must not read private captures'))
    assert personal_digest.source_records([row], tmp_path, include_private=False)[row['id']] == row


def test_corrupt_and_oversized_preview_stay_intact_and_are_ignored(tmp_path):
    row = article()
    sidecar = reader.capture_path(tmp_path, row['id'])
    sidecar = sidecar.parent / 'previews' / sidecar.name
    sidecar.parent.mkdir(parents=True)
    for content in ('{incomplete', json.dumps({'image_url': 'x' * 9000})):
        sidecar.write_text(content)
        assert reader.attach_capture_previews({row['id']: row}, tmp_path) == {row['id']: row}
        assert sidecar.read_text() == content


def test_overlong_url_is_omitted_from_preview_without_truncating_original_capture(tmp_path):
    row = article(source_url='https://publisher.example/' + 'x' * 4100)
    saved = capture(row)
    reader.save_capture(tmp_path, row['id'], saved)
    assert reader.load_capture(tmp_path, row['id']) == saved
    assert reader.attach_capture_previews({row['id']: row}, tmp_path)[row['id']] == row


def test_explicit_capture_retries_failure_and_reuses_success(tmp_path, monkeypatch):
    row = article()
    reader.save_capture(tmp_path, row['id'], capture(row, ok=False, availability='error', reason='ConnectError', passages=[], images=[]))
    calls = []
    def fetch(url, **kwargs):
        calls.append(url)
        return capture(row)
    monkeypatch.setattr(reader, 'fetch_public_article', fetch)
    assert reader.capture_item(tmp_path, row)['ok'] is True
    assert reader.capture_item(tmp_path, row)['ok'] is True
    assert calls == [row['source_url']]
    assert reader.attach_capture_previews({row['id']: row}, tmp_path)[row['id']]['image_url'] == IMAGE
    changed = {**row, 'source_url': 'https://publisher.example/replacement'}
    assert reader.merge_capture(changed, reader.load_capture(tmp_path, row['id'])) == changed
    assert reader.attach_capture_previews({row['id']: changed}, tmp_path)[row['id']] == changed
    reader.capture_item(tmp_path, changed)
    assert calls[-1] == changed['source_url'] and len(calls) == 2


def test_news_digest_and_trusted_map_show_preview_without_original_body(workspace, monkeypatch):
    client, _ = workspace
    row = article()
    reader.save_capture(main.INBOX_DIR, row['id'], capture(row))
    monkeypatch.setattr(main, 'all_facts', lambda: [{'id': 'fact-preview', 'status': 'active', 'evidence_ids': [row['id']], 'statement': 'Reviewed statement'}])
    state = feed_first.load_state(main.INBOX_DIR)
    state['decisions'][row['id']] = {'saved': True}
    feed_first.save_state(main.INBOX_DIR, state)
    before = deepcopy(row)
    body = reader.capture_path(main.INBOX_DIR, row['id'])
    original_read = Path.read_text
    def read(path, *args, **kwargs):
        assert path != body, 'Card route must not hydrate original article text'
        return original_read(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'read_text', read)
    monkeypatch.setattr(reader, 'fetch_public_article', lambda *a, **k: pytest.fail('GET must not capture'))
    for route in ('/today?view=trusted', '/digest', '/explorer?view=trusted'):
        response = client.get(route)
        assert response.status_code == 200
        assert IMAGE in response.text and 'ORIGINAL BODY NEVER READ' not in response.text
    assert row == before
