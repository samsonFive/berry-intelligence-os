from copy import deepcopy
import json
import os

import pytest

from app.services import feed_first_reader as reader
from app.services.feed_first_live import save_bundle
from app.services.variety_universe import article_sources as sources


def story(**changes):
    return {'id': 'ev-memo-source', 'status': 'published',
            'source_url': 'https://example.test/article',
            'summary': 'A publisher describes its berry portfolio.', **changes}


def capture(root, record, text, **changes):
    return reader.save_capture(root, record['id'], {
        'item_id': record['id'], 'requested_url': record['source_url'],
        'ok': True, 'availability': 'partial', 'passages': [text], **changes})


def files(root):
    return {str(path.relative_to(root)): path.read_bytes()
            for path in root.rglob('*') if path.is_file()}


@pytest.mark.skipif(os.name != 'posix', reason='File change-time freshness requires POSIX')
def test_unchanged_selection_reuses_work_and_owns_returned_values(monkeypatch, tmp_path):
    record = story(article={'full_text': 'Blueberry varieties include Original Blue.'})
    original = deepcopy(record)
    calls = []
    real = sources.reader_content

    def counted(row):
        calls.append(1)
        return real(row)

    monkeypatch.setattr(sources, 'reader_content', counted)
    first = sources.available_article_sources([record], tmp_path)
    second = sources.available_article_sources([record], tmp_path)
    assert first == second and len(calls) == 1
    second[0][0]['article']['full_text'] = 'Caller edit'
    assert sources.available_article_sources([record], tmp_path) == first
    assert len(calls) == 1 and record == original and files(tmp_path) == {}


@pytest.mark.parametrize('change', ['body', 'source-url', 'status', 'summary', 'company', 'metadata'])
def test_every_record_edit_matches_current_uncached_selection(tmp_path, change):
    record = story(article={'full_text': 'Blueberry varieties include Original Blue.'})
    sources.available_article_sources([record], tmp_path)
    if change == 'body':
        record['article']['full_text'] = 'Before you continue to Google. If you choose to accept all.'
    elif change == 'source-url':
        record['source_url'] = 'https://example.test/other'
    elif change == 'status':
        record['status'] = 'unreviewed'
    elif change == 'summary':
        record['summary'] = record['article']['full_text']
    elif change == 'company':
        record['entity_ids'] = ['company-new']
    else:
        record['private_note'] = {'lines': ['Current operator note']}
    before = files(tmp_path)
    assert sources.available_article_sources([record], tmp_path) == sources.available_article_sources.__wrapped__([record], tmp_path)
    assert files(tmp_path) == before


@pytest.mark.parametrize('change', ['add', 'edit', 'delete', 'failed', 'malformed', 'preview', 'archive', 'packet'])
def test_stored_capture_and_news_inputs_invalidate_without_writes(tmp_path, change):
    record = story()
    path = capture(tmp_path, record, 'Blueberry varieties include Original Blue.')
    sources.available_article_sources([record], tmp_path)
    if change == 'add':
        capture(tmp_path, story(id='ev-new'), 'Raspberry varieties include New Red.')
        record = story(id='ev-new')
    elif change == 'edit':
        capture(tmp_path, record, 'Blueberry varieties include Updated Blue.')
    elif change == 'delete':
        path.unlink()
    elif change == 'failed':
        capture(tmp_path, record, 'Blueberry varieties include Hidden Blue.', ok=False)
    elif change == 'malformed':
        path.write_text('{broken', encoding='utf-8')
    elif change == 'preview':
        preview = path.parent / 'previews' / path.name
        preview.parent.mkdir(exist_ok=True)
        preview.write_text(json.dumps({'item_id': record['id'], 'source_url': record['source_url'],
                                       'image_url': 'https://example.test/new-image.jpg'}))
    else:
        raw = story(id='ev-retained', article={'full_text': 'Blackberry varieties include Stored Black.'})
        if change == 'archive':
            save_bundle(tmp_path, {'today': '2026-11-03', 'records': [raw]})
        else:
            packet = tmp_path / 'news_packets' / 'captures' / 'packet-probe.json'
            packet.parent.mkdir(parents=True)
            packet.write_text(json.dumps({'records': [raw]}))
    before = files(tmp_path)
    assert sources.available_article_sources([record], tmp_path) == sources.available_article_sources.__wrapped__([record], tmp_path)
    assert files(tmp_path) == before


def test_separate_inboxes_cannot_share_a_capture(tmp_path):
    record = story()
    left, right = tmp_path / 'left', tmp_path / 'right'
    left.mkdir(); right.mkdir()
    capture(left, record, 'Blueberry varieties include Private Blue.')
    assert sources.available_article_sources([record], left)[0]
    assert sources.available_article_sources([record], right)[0] == []


@pytest.mark.skipif(os.name != 'posix', reason='File change-time freshness requires POSIX')
def test_capture_edit_preserving_mtime_and_length_is_still_current(tmp_path):
    record = story()
    path = capture(tmp_path, record, 'Blueberry varieties include First Blue.')
    sources.available_article_sources([record], tmp_path)
    before = path.stat()
    payload = path.read_text().replace('First Blue', 'Other Blue')
    path.write_text(payload)
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    result = sources.available_article_sources([record], tmp_path)
    assert 'Other Blue' in result[0][0]['article']['paragraphs'][0]['text']


@pytest.mark.skipif(os.name != 'posix', reason='POSIX symlink freshness')
def test_capture_symlink_replacement_cannot_reuse_a_previously_valid_body(tmp_path):
    record = story()
    path = capture(tmp_path, record, 'Blueberry varieties include Original Blue.')
    sources.available_article_sources([record], tmp_path)
    target = tmp_path / 'target.json'
    path.rename(target)
    path.symlink_to(target)
    assert sources.available_article_sources([record], tmp_path)[0] == []


def test_pending_review_edit_and_opaque_record_keep_original_behavior(tmp_path):
    pending = story(status='draft', review_state='in_review', evidence_role='publication_artifact',
                    article={'full_text': 'Raspberry varieties include Draft Red.'})
    sources.available_article_sources([], tmp_path, pending=[pending])
    pending['review_state'] = 'rejected'
    assert sources.available_article_sources([], tmp_path, pending=[pending]) == sources.available_article_sources.__wrapped__([], tmp_path, pending=[pending])

    class Opaque:
        def __reduce_ex__(self, protocol):
            pytest.fail('Memo input must not execute a custom reducer')

    record = story(article={'full_text': 'Blueberry varieties include Current Blue.'}, private_note=Opaque())
    assert sources.available_article_sources([record], tmp_path)[0][0]['private_note'] is record['private_note']


def test_source_fidelity_decisions_remain_current(tmp_path):
    from app.services.source_fidelity_recovery import (
        build_recovery_artifact, decide_recovery_artifact, match_recoveries,
    )
    from tests.test_source_fidelity_recovery import _trusted, _rich, _candidate
    record = _trusted()
    assert sources.available_article_sources([record], tmp_path)[0] == []
    artifact = build_recovery_artifact(match_recoveries([record], [_candidate(_rich())])[0], record)
    path = tmp_path / 'source_fidelity' / 'artifacts' / (record['id'] + '.json')
    path.parent.mkdir(parents=True)
    for decision in ('affirmed', 'rejected', 'needs_investigation'):
        changed = decide_recovery_artifact(artifact, record, decision=decision, reviewer='Fictional analyst')
        path.write_text(json.dumps(changed))
        before = files(tmp_path)
        result = sources.available_article_sources([record], tmp_path)
        assert result == sources.available_article_sources.__wrapped__([record], tmp_path)
        assert bool(result[0]) is (decision == 'affirmed')
        assert files(tmp_path) == before and record == _trusted()


@pytest.mark.skipif(os.name != 'posix', reason='Cache admission requires POSIX')
def test_change_during_preparation_is_not_saved_as_an_unchanged_snapshot(monkeypatch, tmp_path):
    record = story()
    capture(tmp_path, record, 'Blueberry varieties include Original Blue.')
    original = sources.reader_content
    changed = []

    def edit_after_read(row):
        result = original(row)
        if not changed:
            capture(tmp_path, record, 'Blueberry varieties include Modified Blue.')
            changed.append(True)
        return result

    monkeypatch.setattr(sources, 'reader_content', edit_after_read)
    sources.available_article_sources([record], tmp_path)
    result = sources.available_article_sources([record], tmp_path)
    assert 'Modified Blue' in result[0][0]['article']['paragraphs'][0]['text']


@pytest.mark.skipif(os.name != 'posix', reason='Cache dependency replacement requires POSIX')
def test_replaced_selector_cannot_serve_its_previous_result(monkeypatch, tmp_path):
    record = story(article={'full_text': 'Blueberry varieties include Original Blue.'})
    assert sources.available_article_sources([record], tmp_path)[0]
    original = sources.reader_content
    monkeypatch.setattr(sources, 'reader_content', lambda row: {**original(row), 'state': 'interstitial'})
    assert sources.available_article_sources([record], tmp_path)[0] == []
