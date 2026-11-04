"""Persisted least-recently-attempted scheduling within the existing host budget."""
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid

from app.services.collection_runner import CollectionRunLock


def reserve(rows, inbox, limit=6):
    # Record reservation before network work: failed hosts must yield their turn too.
    path = Path(inbox) / 'operations' / 'official_host_rotation.json'
    with CollectionRunLock(path.with_suffix('.lock'), run_id=uuid.uuid4().hex):
        state = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'sequence': 0, 'hosts': {}}
        ordered = sorted(rows, key=lambda row: (state['hosts'].get(row.id, {}).get('attempt', -1), row.id))[:limit]
        state['sequence'] += 1
        for row in ordered:
            state['hosts'][row.id] = {**state['hosts'].get(row.id, {}), 'attempt': state['sequence'],
                                     'last_attempt': datetime.now(timezone.utc).isoformat()}
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(state, indent=2) + '\n', encoding='utf-8')
        temporary.replace(path)
    return ordered


def record_results(rows, errors, inbox):
    path = Path(inbox) / 'operations' / 'official_host_rotation.json'
    failed = {row.get('query_id') or row.get('query') for row in errors}
    with CollectionRunLock(path.with_suffix('.lock'), run_id=uuid.uuid4().hex):
        state = json.loads(path.read_text(encoding='utf-8'))
        for row in rows:
            if row.id not in failed:
                state['hosts'][row.id]['last_success'] = datetime.now(timezone.utc).isoformat()
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(state, indent=2) + '\n', encoding='utf-8')
        temporary.replace(path)
