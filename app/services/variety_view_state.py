"""Private per-analyst sheet layouts; optimistic revisions protect other tabs."""
import hashlib
import json
import re
from pathlib import Path

from app.services.analyst_state_io import atomic_json, serialized_write

NAME = 'variety_view_state.json'
KEY = re.compile(r'^[a-z0-9-]{1,80}$')


def actor_key(actor):
    return hashlib.sha256(str(actor).encode()).hexdigest()[:24]


def load(inbox_dir):
    path = Path(inbox_dir) / NAME
    if not path.exists():
        return {'version': 1, 'analysts': {}}
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('version') != 1 or not isinstance(data.get('analysts'), dict):
        raise ValueError('Saved layouts need checking; they have not been overwritten.')
    return data


def get(inbox_dir, actor, key):
    if not KEY.fullmatch(key):
        raise ValueError('Unsupported view key')
    return load(inbox_dir)['analysts'].get(actor_key(actor), {}).get(key, {'revision': 0, 'widths': {}, 'order': [], 'hidden': [], 'filters': {}})


def clean(payload):
    if not isinstance(payload, dict):
        raise ValueError('A layout object is required')
    widths, order, hidden, filters = (payload.get(k, default) for k, default in [('widths', {}), ('order', []), ('hidden', []), ('filters', {})])
    if not isinstance(widths, dict) or len(widths) > 40 or not isinstance(order, list) or len(order) > 40 or not isinstance(hidden, list) or len(hidden) > 40 or not isinstance(filters, dict) or len(filters) > 25:
        raise ValueError('Invalid layout dimensions')
    ids = [*widths, *order, *hidden]
    if any(not isinstance(k, str) or not KEY.fullmatch(k) for k in ids):
        raise ValueError('Invalid column identifier')
    if any(type(v) is not int or not 48 <= v <= 1200 for v in widths.values()) or len(set(order)) != len(order) or len(set(hidden)) != len(hidden):
        raise ValueError('Invalid column size or order')
    if any(not isinstance(k, str) or len(k) > 40 or not isinstance(v, str) or len(v) > 400 for k, v in filters.items()):
        raise ValueError('Invalid saved filters')
    return dict(widths=widths, order=order, hidden=hidden, filters=filters)


@serialized_write
def save(inbox_dir, actor, key, payload):
    cleaned = clean(payload)
    current = get(inbox_dir, actor, key)
    if payload.get('revision') != current['revision']:
        raise ValueError('This layout changed in another tab. Reload before saving more changes.')
    entry = {**cleaned, 'revision': current['revision'] + 1}
    state = load(inbox_dir)
    views = state['analysts'].setdefault(actor_key(actor), {})
    if key not in views and len(views) >= 100:
        raise ValueError('The saved-view limit has been reached')
    views[key] = entry
    atomic_json(Path(inbox_dir) / NAME, state)
    return entry
