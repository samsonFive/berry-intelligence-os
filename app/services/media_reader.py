"""Resolve one private recording's stored transcript; never acquire on read."""
import json
from dataclasses import asdict
import ijson

from app.services.feed_first import SAFE_ID_RE
from app.services.feed_first_reader import is_public_http_url
from app.services.media_transcription import load_transcript_artifact, transcripts_dir
from app.services.transcript_evidence import TranscriptArtifact, TranscriptContractError

SPOKEN = {'podcast', 'video', 'conference_video'}


def transcript_headers(inbox_dir):
    """Read bounded metadata headers, never materialize recording bodies."""
    headers = []
    for path in sorted(transcripts_dir(inbox_dir).glob('*.json'))[:2048]:
        header = {}
        try:
            if path.is_symlink() or path.stat().st_size > 16_000_000:
                continue
            with path.open('rb') as handle:
                for prefix, event, value in ijson.parse(handle):
                    if prefix == 'segments' and event == 'start_array':
                        break
                    if prefix in {'parent_evidence_id', 'item_id', 'source_id', 'language'} and event == 'string':
                        header[prefix] = value
            if header.get('item_id') == path.stem and SAFE_ID_RE.fullmatch(path.stem):
                headers.append(header)
        except (OSError, ValueError, ijson.JSONError):
            continue
    return headers


def _bound_item_id(record, inbox_dir):
    """Use an explicit parent binding, never a title or shared homepage."""
    matches = [row['item_id'] for row in transcript_headers(inbox_dir)
               if row.get('parent_evidence_id') == record.get('id') and row.get('source_id') == record.get('source_id')]
    return matches[0] if len(matches) == 1 else ''


def attach_transcript_metadata(records, inbox_dir):
    headers = transcript_headers(inbox_dir)
    by_item = {row['item_id']: row for row in headers}
    by_parent = {}
    for row in headers:
        if row.get('parent_evidence_id'):
            by_parent.setdefault(row['parent_evidence_id'], []).append(row)
    result = {}
    for key, record in records.items():
        header = by_item.get(record.get('discovered_item_id'))
        parents = by_parent.get(key, [])
        header = header or (parents[0] if len(parents) == 1 else None)
        if header and header.get('source_id') == record.get('source_id'):
            record = {**record, 'transcript_status': 'stored'}
        result[key] = record
    return result


def stored_media(record, inbox_dir):
    if record.get('media_format') not in SPOKEN and record.get('source_type') != 'industry_podcast':
        return record
    projected = dict(record)
    key = str(record.get('discovered_item_id') or '')
    if not key:
        key = _bound_item_id(record, inbox_dir)
    if not SAFE_ID_RE.fullmatch(key):
        return projected
    projected['discovered_item_id'] = key
    from app.services.media_transcription_jobs import read_status
    projected['transcript_job'] = read_status(inbox_dir, key)
    try:
        path = inbox_dir / 'discovered_media' / (key + '.json')
        if path.stat().st_size <= 1_000_000:
            item = json.loads(path.read_text(encoding='utf-8'))
            if item.get('id') == key and item.get('source_id') == record.get('source_id'):
                enclosures = (item.get('raw_metadata') or {}).get('enclosures', [])
                media_url = next((row.get('url') for row in enclosures if str(row.get('type') or '').startswith(('audio/', 'video/'))
                                  and is_public_http_url(row.get('url') or '')), '')
                if media_url:
                    projected['media_url'] = media_url
    except (OSError, ValueError, TypeError, AttributeError):
        pass  # A missing discovery sidecar must not hide a retained transcript.
    try:
        transcript_path = transcripts_dir(inbox_dir) / (key + '.json')
        if transcript_path.stat().st_size > 16_000_000 or transcript_path.is_symlink():
            raise ValueError('transcript exceeds reading limit')
        payload = load_transcript_artifact(inbox_dir, key)
        if payload.get('item_id', payload.get('discovered_item_id', key)) != key:
            raise ValueError('transcript lineage mismatch')
        if payload.get('parent_evidence_id') not in {None, record['id']}:
            raise ValueError('transcript parent mismatch')
        transcript = TranscriptArtifact.from_dict({**payload, 'parent_evidence_id': record['id']})
        reference = record.get('source_artifact') or {}
        if reference.get('kind') == 'transcript' and reference.get('content_sha256') != transcript.content_sha256():
            raise ValueError('transcript version changed')
        projected['transcript'] = {'status': 'available', 'language': transcript.language,
            'source': transcript.provenance.method, 'text': '\n'.join(seg.text for seg in transcript.segments),
            'segments': [asdict(seg) for seg in transcript.segments]}
        projected['transcript_version'] = transcript.content_sha256()
        projected['transcript_provenance'] = asdict(transcript.provenance)
    except FileNotFoundError:
        pass
    except (OSError, ValueError, TypeError, AttributeError, TranscriptContractError):
        projected['transcript_read_error'] = 'Stored transcript unavailable or inconsistent; description remains available.'
    return projected


def transcript_text(record):
    transcript = record.get('transcript')
    return (transcript.get('text') or '') if isinstance(transcript, dict) else ''
