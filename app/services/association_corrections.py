"""Audited private association overlays. Never mutate source files or trust.

This module stays low in the import graph so all private read paths can reuse
the same exclusion semantics without importing dashboard presentation services.
"""
from contextlib import closing
from copy import deepcopy
import json
from pathlib import Path
import sqlite3


def load(inbox_dir):
    if inbox_dir is None:
        return []
    path = Path(inbox_dir) / 'living_workspaces' / 'workspace.sqlite3'
    if not path.is_file():
        return []
    with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)) as db:
        return [json.loads(row[0]) for row in db.execute("SELECT body FROM objects WHERE kind='global_watchlist_correction'")]


def excluded(record, entity_id, field='entity_ids'):
    return any(c.get('field') == field and c.get('entity_id') == entity_id and c.get('action') == 'exclude'
               for c in record.get('association_corrections', []))


def apply(records, corrections):
    if not corrections:
        return records
    by_id = {row['id']: deepcopy(row) for row in records}
    for correction in corrections:
        row = by_id.get(correction['record_id'])
        if row is None:
            continue
        field, entity_id = correction['field'], correction['entity_id']
        if field not in {'entity_ids', 'geography_ids', 'berry_ids'}:
            continue
        ids = set(row.get(field) or [])
        ids.add(entity_id) if correction['action'] == 'include' else ids.discard(entity_id)
        row[field] = sorted(ids)
        # Idempotent when a dashboard projects an already-corrected corpus.
        previous = [c for c in row.get('association_corrections', []) if c['id'] != correction['id']]
        row['association_corrections'] = [*previous, correction]
    return list(by_id.values())
