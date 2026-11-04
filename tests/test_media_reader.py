import json
from uuid import uuid4

from app.services.media_reader import stored_media
from app.services.media_transcription import write_transcript_artifact
from app.services.living_workspaces import Store


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
