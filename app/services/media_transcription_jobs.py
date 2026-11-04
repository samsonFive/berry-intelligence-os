"""Explicit bounded publisher/caption jobs over the existing transcript artifacts.

No timer, page load, paid provider or speech-to-text is enabled here.
"""
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from app.services.analyst_state_io import atomic_json
from app.services.feed_first import SAFE_ID_RE
from app.services.pipeline_lock import pipeline_lock


def status_path(inbox_dir, item_id):
    if not SAFE_ID_RE.fullmatch(item_id):
        raise ValueError('Invalid discovered item ID')
    return Path(inbox_dir) / 'operations/transcription' / (item_id + '.json')


def read_status(inbox_dir, item_id):
    try:
        path = status_path(inbox_dir, item_id)
        if path.stat().st_size > 32_000 or path.is_symlink():
            raise ValueError('invalid job status')
        row = json.loads(path.read_text(encoding='utf-8'))
        return row if isinstance(row, dict) and row.get('item_id') == item_id else {}
    except (OSError, ValueError):
        return {}


def run_job(inbox_dir, item_id, *, timeout=60, executor=subprocess.run):
    if type(timeout) is not int or not 1 <= timeout <= 300:
        raise ValueError('Caption job timeout must be between 1 and 300 seconds')
    path = status_path(inbox_dir, item_id)
    item_path = Path(inbox_dir) / 'discovered_media' / (item_id + '.json')
    item = json.loads(item_path.read_text(encoding='utf-8'))
    if item.get('id') != item_id or item.get('media_format') not in {'podcast', 'video', 'conference_video'}:
        raise ValueError('Choose an existing spoken-media discovery')
    # The same collection lease prevents overlap with discovery and other jobs.
    with pipeline_lock(Path(inbox_dir), 'bounded-caption-job'):
        prior = read_status(inbox_dir, item_id)
        row = {'item_id': item_id, 'state': 'queued', 'attempt': int(prior.get('attempt', 0)) + 1,
               'queued_at': datetime.now(UTC).isoformat(), 'max_tier': 2, 'timeout_seconds': timeout,
               'speech_to_text': False, 'paid_calls': 0}
        atomic_json(path, row)
        row.update(state='running', started_at=datetime.now(UTC).isoformat())
        atomic_json(path, row)
        try:
            command = [sys.executable, str(Path(__file__).resolve().parents[2] / 'scripts/transcribe_media_job.py'),
                       '--worker', '--item', item_id, '--inbox-dir', str(Path(inbox_dir).resolve())]
            completed = executor(command, text=True, capture_output=True, timeout=timeout, check=False)
            result = json.loads(completed.stdout) if completed.returncode == 0 else {}
            if result.get('status') == 'ok' and result.get('segment_count', 0) > 0:
                row.update(state='partial' if result.get('partial') else 'ready', segment_count=result['segment_count'], language=result.get('language'),
                           tier=result.get('tier'), reason='Stored timed transcript acquired; source claims remain unreviewed.')
            elif result.get('tier') == 'deferred_expensive_transcription':
                row.update(state='deferred', reason='No permitted publisher transcript or usable platform captions recovered. Local speech-to-text requires a separate resource budget.')
                if result.get('caption_reason') == 'platform_access_blocked':
                    row.update(reason_code='platform_access_blocked', reason='Platform access challenge blocked caption inspection. No challenge bypass or speech-to-text was attempted.')
            else:
                row.update(state='failed', reason='Transcript acquisition failed. Inspect the source and access restrictions before retrying.')
        except subprocess.TimeoutExpired:
            row.update(state='deferred', reason='Bounded caption attempt reached its time limit; no speech-to-text was started.')
        except (OSError, ValueError, TypeError):
            row.update(state='failed', reason='Transcript worker failed or returned invalid output.')
        row['completed_at'] = datetime.now(UTC).isoformat()
        atomic_json(path, row)
        return row
