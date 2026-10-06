"""Explicit, bounded thumbnail capture. No evidence/body/trust writes."""
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
import json
import logging
from pathlib import Path
from time import time

from app.services import feed_first, feed_first_reader as reader
from app.services.analyst_state_io import atomic_json
from app.services.google_news_url import resolve_google_news_url

LIMIT = 36
RETRY_SECONDS = 86400


def preview_path(inbox_dir, item_id):
    path = reader.capture_path(inbox_dir, item_id)
    return path.parent / 'previews' / path.name


def collect(inbox_dir, records, *, fetch=None, retry_missing=False):
    """Capture only images for this page; retain original source identity/edits."""
    getter = fetch or reader.fetch_source_preview_image
    selected = []
    for row in records[:LIMIT]:
        key, source = str(row.get('id') or ''), str(row.get('source_url') or '')
        if not feed_first.SAFE_ID_RE.fullmatch(key) or len(source) > 4096:
            continue
        if feed_first.safe_image_url(row) or not reader.is_public_http_url(source):
            continue
        path = preview_path(inbox_dir, key)
        try:
            value = json.loads(path.read_text(encoding='utf-8')) if path.stat().st_size <= 8192 else {}
            if (value.get('item_id') == key and value.get('source_url') == source
                    and ((reader.is_public_http_url(str(value.get('image_url') or ''))
                          and feed_first.safe_image_url(value))
                         or (not retry_missing and time() - path.stat().st_mtime < RETRY_SECONDS))):
                continue
        except (OSError, ValueError, AttributeError):
            pass
        selected.append(row)

    def capture(row):
        source = str(row['source_url'])
        try:
            image = getter(resolve_google_news_url(source))
            image = feed_first.safe_image_url({'image_url': image})
            if not reader.is_public_http_url(image) or len(image) > 2048:
                image = ''
        except Exception:
            image = ''
        # Metadata only; the original source URL and record are never replaced.
        atomic_json(preview_path(inbox_dir, row['id']), {
            'item_id': row['id'], 'source_url': source, 'image_url': image,
        })
        return bool(image)

    with ThreadPoolExecutor(max_workers=4) as pool:
        found = sum(pool.map(capture, selected))
    return {'checked': len(selected), 'found': found}


def state_path(inbox_dir):
    return Path(inbox_dir) / 'news_workspace' / 'images.json'


def state(inbox_dir):
    try:
        value = json.loads(state_path(inbox_dir).read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def run(inbox_dir, records):
    from app.services.pipeline_lock import pipeline_lock
    try:
        with pipeline_lock(inbox_dir, 'news_images'):
            atomic_json(state_path(inbox_dir), {'status': 'running', 'started_at': datetime.now(UTC).isoformat()})
            result = collect(inbox_dir, records, retry_missing=True)
            result.update(status='ready', message='Article images checked. Illustrations cover unavailable photos.')
    except Exception:
        logging.getLogger(__name__).exception('Article thumbnail capture failed')
        result = {'status': 'failed', 'message': 'Article images could not be checked. Try again.'}
    result['completed_at'] = datetime.now(UTC).isoformat()
    atomic_json(state_path(inbox_dir), result)
