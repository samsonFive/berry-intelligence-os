import json
import pytest
from uuid import uuid4

from app.services.media_reader import stored_media
from app.services.media_transcription import write_transcript_artifact
from app.services.living_workspaces import Store, compose_brief, transcript_passage_label


def test_changed_transcript_selection_cannot_be_reattached_to_new_version(tmp_path):
    store = Store(tmp_path)
    source = store.snapshot({'id': 'ev-recording', 'transcript_version': 'new-version'},
                            'Same words in a replacement transcript.', 'transcript_available')
    payload = {'token': uuid4().hex, 'quote': 'Same words', 'locator': {'start': 0},
               'transcript_version': 'previous-version'}
    with pytest.raises(ValueError, match='Transcript changed'):
        store.capture(payload, source, 'analyst', {})
    assert store.rows('item') == []
    assert not list((tmp_path / 'evidence').glob('*.json'))


def test_repeated_transcript_words_use_codepoint_position_and_correct_time(tmp_path):
    store = Store(tmp_path)
    source = store.snapshot({'id': 'ev-recording', 'transcript_version': 'v1',
                            'transcript': {'segments': [
                                {'text': '🌱 First repeated words.', 'start_seconds': 1, 'end_seconds': 4},
                                {'text': 'Second repeated words.', 'start_seconds': 20, 'end_seconds': 24}]}},
                            '🌱 First repeated words.\nSecond repeated words.', 'transcript_available')
    result = store.capture({'token': uuid4().hex, 'quote': 'repeated words.',
                            'locator': {'start': 31}, 'transcript_version': 'v1'}, source, 'analyst', {})
    assert result['item']['locator']['state'] == 'exact'
    assert result['item']['locator']['start_seconds'] == 20
    assert result['item']['locator']['transcript_version'] == 'v1'


def test_retained_transcript_without_discovery_survives_capture_restart_and_retry(tmp_path):
    key = 'discovered-real-recording'
    record = {'id': 'ev-recording', 'discovered_item_id': key, 'source_id': 'source-show',
              'source_url': 'https://publisher.org/episode', 'source_name': 'Issuer', 'media_format': 'podcast'}
    payload = {'item_id': key, 'transcript_id': 'transcript-recording', 'parent_evidence_id': None,
               'language': 'es', 'provenance': {'method': 'publisher_provided', 'created_by': 'fixture-publisher', 'created_at': '2026-11-03'},
               'segments': [{'text': 'First source passage.', 'start_seconds': 5, 'end_seconds': 8},
                            {'text': 'Second source passage.', 'start_seconds': 20, 'end_seconds': 24}]}
    write_transcript_artifact(tmp_path, payload)
    projected = stored_media(record, tmp_path)
    assert projected['transcript']['language'] == 'es'
    assert 'transcript' not in record
    store = Store(tmp_path)
    source = store.snapshot(projected, projected['transcript']['text'], 'transcript_available')
    request = {'token': uuid4().hex, 'kind': 'evidence', 'quote': 'Second source passage.', 'locator': {'start': 999}}
    result = store.capture(request, source, 'analyst', {})
    assert store.capture(request, source, 'analyst', {}) == result
    reopened = Store(tmp_path)
    saved = reopened.get(result['item']['id'])
    assert saved['locator']['start_seconds'] == 20
    assert saved['locator']['end_seconds'] == 24
    assert saved['locator']['transcript_version'] == projected['transcript_version']
    assert reopened.get(saved['source_id'])['transcript_provenance']['method'] == 'publisher_provided'
    assert saved['verification_state'] == 'unverified'
    archived = reopened.get(saved['source_id'])
    assert archived['transcript_language'] == 'es'
    page = reopened.get(result['page']['id'])
    brief = compose_brief(page, {saved['id']: saved}, {archived['id']: archived}, [])
    assert 'Recording passage: 20.00–24.00 seconds' in brief['text']
    assert brief['citations'][0]['locator']['transcript_version'] == projected['transcript_version']
    assert transcript_passage_label(saved, {**archived, 'transcript_version': 'different'}) == ''
    assert transcript_passage_label({**saved, 'locator': {'state': 'unresolved'}}, archived) == ''


def test_inconsistent_transcript_cannot_replace_description(tmp_path):
    key = 'discovered-recording'
    write_transcript_artifact(tmp_path, {'item_id': 'discovered-other'})
    # The actual file name must match the selected discovery's id too.
    folder = tmp_path / 'discovered_media/_normalized_transcripts'
    (folder / 'discovered-other.json').rename(folder / (key + '.json'))
    record = {'id': 'ev-recording', 'discovered_item_id': key, 'media_format': 'video', 'summary': 'Publisher description'}
    projected = stored_media(record, tmp_path)
    assert projected['summary'] == record['summary']
    assert 'transcript' not in projected and projected['transcript_read_error']


def test_legacy_publication_uses_only_explicit_transcript_parent_binding(tmp_path):
    record = {'id': 'ev-legacy', 'source_id': 'source-show', 'media_format': 'podcast',
              'transcript': {'status': 'not_available'}}
    payload = {'item_id': 'discovered-old', 'source_id': 'source-show', 'transcript_id': 'transcript-old',
               'parent_evidence_id': 'ev-legacy', 'language': 'en',
               'provenance': {'method': 'auto_generated', 'created_by': 'historical-worker', 'created_at': '2026-08-15'},
               'segments': [{'text': 'Historical source wording.', 'start_seconds': 5, 'end_seconds': 10}]}
    write_transcript_artifact(tmp_path, payload)
    projected = stored_media(record, tmp_path)
    assert projected['transcript']['text'] == 'Historical source wording.'
    assert record['transcript']['status'] == 'not_available'
    assert stored_media({**record, 'source_id': 'source-other'}, tmp_path)['transcript']['status'] == 'not_available'
    from app.services.media_reader import attach_transcript_metadata
    metadata = attach_transcript_metadata({'ev-legacy': record}, tmp_path)
    assert metadata['ev-legacy']['transcript_status'] == 'stored'
    assert 'text' not in metadata['ev-legacy']['transcript']
