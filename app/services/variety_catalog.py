"""Analyst-authored variety records with optimistic concurrency and private history.

Catalog membership is independent of claim/identity qualification. An imported
record can be useful and editable while its identity and commercial claims are
explicitly unverified. This module never creates Facts or approves Evidence.
"""
from copy import deepcopy
from datetime import UTC, datetime
from hashlib import sha256
import json
import re
from pathlib import Path
from uuid import uuid4

from app.repositories.json.entities import EntityRepository
from app.services.analyst_state_io import atomic_json, serialized_write
from app.services.collection_runner import CollectionRunLock
from app.services.map_regions import public_source_url
from app.services.variety_universe.identity import fold_identity, _identity_strings

BERRIES = ('berry-blueberry', 'berry-strawberry', 'berry-raspberry', 'berry-blackberry')
STATUSES = ('unverified', 'active', 'inactive', 'historical')
SCALAR_FIELDS = ('denomination', 'trade_name', 'commercial_name', 'breeder_code',
                 'selection_code', 'breeder', 'parentage', 'origin', 'geography_note',
                 'patent_number', 'rights_id', 'package_note')
TABLES = {
    'catalog_sources': ('title', 'url', 'checked_on', 'note'),
    'catalog_connections': ('entity_id', 'name', 'role', 'territory', 'source_url', 'note'),
    'catalog_rights': ('number', 'jurisdiction', 'status', 'source_url', 'note'),
    'catalog_traits': ('trait', 'value', 'conditions', 'source_url', 'note'),
}
RESERVED = {'catalog_removed', 'catalog_visibility', 'catalog_import'}


def revision(record):
    return sha256(json.dumps(record, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def visible(record, *, private=True):
    attrs = record.get('attributes') or {}
    return not attrs.get('catalog_removed') and (private or attrs.get('catalog_visibility') != 'workspace')


def present_connections(connections, entities):
    rows = deepcopy(connections)
    for row in rows:
        party = entities.get(row.get('entity_id')) or {}
        row['href'] = '/entities/' + party['entity_type'] + '/' + party['id'] if party else ''
    return rows


def _repository(data_dir, schemas_dir):
    return EntityRepository(Path(data_dir), Path(schemas_dir))


def history(inbox_dir, entity_id):
    result = []
    for path in sorted((Path(inbox_dir) / 'catalog_history' / entity_id).glob('*.json'), reverse=True):
        event = json.loads(path.read_text(encoding='utf-8'))
        result.append(event)
    from app.services.variety_catalog_import import import_history
    return sorted([*result, *import_history(inbox_dir, entity_id)], key=lambda event: event.get('at', ''), reverse=True)


def _write(inbox_dir, repository, before, after, *, actor, action, history_id=None):
    if not actor.strip():
        raise ValueError('Record the editor name before saving')
    stamp = datetime.now(UTC).isoformat()
    target = history_id or after['id']
    event = {'id': uuid4().hex, 'entity_id': target, 'at': stamp, 'actor': actor,
             'action': action, 'before': before, 'after': after, 'state': 'prepared'}
    path = Path(inbox_dir) / 'catalog_history' / target / (stamp.replace(':', '-') + '-' + event['id'] + '.json')
    atomic_json(path, event)
    if before is None:
        repository.create(after)
    else:
        repository.update(after['id'], after)
    # The prepared event retains the exact recovery data even if this final
    # bookkeeping write fails after the canonical write succeeds.
    event['state'] = 'saved'
    atomic_json(path, event)
    return after


def _strings(value):
    return list(dict.fromkeys(line.strip() for line in str(value or '').splitlines() if line.strip()))


def identity_collisions(record, records):
    names = {fold_identity(text) for text, _ in _identity_strings(record) if fold_identity(text)}
    crops = set(record.get('berry_ids') or [])
    return [other for other in records if other['id'] != record['id'] and other.get('entity_type') == 'variety'
            and (not crops or not other.get('berry_ids') or crops.intersection(other['berry_ids']))
            and names.intersection(fold_identity(text) for text, _ in _identity_strings(other))]


def _table(form, key):
    columns = TABLES[key]
    count = len(form.getlist(key + '.row'))
    values = {column: form.getlist(key + '.' + column) for column in columns}
    result = []
    for index in range(count):
        if str(index) in form.getlist(key + '.remove'):
            continue
        row = {column: str(values[column][index] if index < len(values[column]) else '').strip() for column in columns}
        if not any(row.values()):
            continue
        if any(len(value) > 8000 for value in row.values()):
            raise ValueError('Keep each catalog detail below 8,000 characters')
        for column in ('url', 'source_url'):
            if row.get(column) and not public_source_url(row[column]):
                raise ValueError('Use complete public http or https source links')
        row['review_state'] = 'user_annotation'
        result.append(row)
    return result


def from_form(form, before, records):
    record = deepcopy(before)
    record['name'] = str(form.get('name') or '').strip()
    if not record['name'] or len(record['name']) > 256:
        raise ValueError('Enter a variety name of up to 256 characters')
    record['description'] = str(form.get('description') or '').strip()
    record['aliases'] = _strings(form.get('aliases'))
    record['berry_ids'] = list(dict.fromkeys(form.getlist('berry_ids')))
    if not record['berry_ids'] or any(berry not in BERRIES for berry in record['berry_ids']):
        raise ValueError('Choose at least one supported berry')
    if form.get('status') not in STATUSES:
        raise ValueError('Choose a supported catalog status')
    record['status'] = form['status']
    attrs = deepcopy(before.get('attributes') or {})
    for key in SCALAR_FIELDS:
        value = str(form.get(key) or '').strip()
        if value:
            attrs[key] = value
        else:
            attrs.pop(key, None)
    # Additional fields are individually editable. Structured values use JSON
    # only in the optional advanced control; scalar values stay simple text.
    keys, values, kinds = (form.getlist('extra.' + key) for key in ('key', 'value', 'kind'))
    protected = RESERVED | set(SCALAR_FIELDS) | set(TABLES)
    extra = {}
    for index, key in enumerate(keys):
        if str(index) in form.getlist('extra.remove'):
            continue
        key = str(key).strip()
        if not key:
            continue
        if key in protected or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_ -]{0,100}', key):
            raise ValueError('Choose a unique descriptive field name outside the standard fields')
        if key in extra:
            raise ValueError('Additional field names must be unique')
        value = str(values[index] if index < len(values) else '')
        try:
            extra[key] = json.loads(value) if index < len(kinds) and kinds[index] == 'json' else value
        except ValueError as exc:
            raise ValueError('Structured field ' + key + ' must contain valid JSON') from exc
    attrs = {key: value for key, value in attrs.items() if key in protected}
    attrs.update(extra)
    for key in TABLES:
        attrs[key] = _table(form, key)
    entities = {item['id']: item for item in records}
    for row in attrs['catalog_connections']:
        if row['entity_id']:
            party = entities.get(row['entity_id'])
            if not party or party.get('entity_type') not in {'company', 'brand', 'breeding_program', 'retailer', 'person'}:
                raise ValueError('Choose an existing commercial organization or leave the organization link blank')
            row['name'] = party['name']
        if not row['name']:
            raise ValueError('Give each commercial connection an organization name')
    record['attributes'] = attrs
    collisions = identity_collisions(record, records)
    # Existing ambiguous records remain editable without forcing a merge.
    if collisions and (record['name'] != before['name'] or record['aliases'] != before.get('aliases', []) or record['berry_ids'] != before.get('berry_ids', [])):
        raise ValueError('This identity overlaps ' + ', '.join(row['name'] for row in collisions) + '. Resolve the overlap before changing names or crop.')
    return record


@serialized_write
def save(inbox_dir, data_dir, schemas_dir, entity_id, form, *, actor):
    repository = _repository(data_dir, schemas_dir)
    with CollectionRunLock(Path(inbox_dir) / 'catalog_history' / 'write.lock', run_id=uuid4().hex):
        before = repository.get(entity_id)
        if before is None or before.get('entity_type') != 'variety':
            raise ValueError('Variety not found')
        if form.get('revision') != revision(before):
            raise ValueError('This variety changed in another session. Reload before saving.')
        if not visible(before):
            raise ValueError('Restore the removed variety before editing')
        from app.services.variety_catalog_import import effective_record, imported_enrichment
        effective = effective_record(before, imported_enrichment(inbox_dir))
        after = from_form(form, effective, repository.list())
        return _write(inbox_dir, repository, before, after, actor=actor, action='edit')


@serialized_write
def create(inbox_dir, data_dir, schemas_dir, form, *, actor):
    repository = _repository(data_dir, schemas_dir)
    with CollectionRunLock(Path(inbox_dir) / 'catalog_history' / 'write.lock', run_id=uuid4().hex):
        before = {'id': 'variety-' + uuid4().hex[:16], 'record_type': 'entity', 'entity_type': 'variety',
                  'name': '', 'aliases': [], 'status': 'unverified', 'berry_ids': [],
                  'evidence_ids': [], 'fact_ids': [], 'relationship_ids': [], 'attributes': {'catalog_visibility': 'workspace'}}
        after = from_form(form, before, repository.list())
        return _write(inbox_dir, repository, None, after, actor=actor, action='create')


@serialized_write
def remove_or_restore(inbox_dir, data_dir, schemas_dir, entity_id, *, expected, actor, restore=False, confirmation=''):
    repository = _repository(data_dir, schemas_dir)
    with CollectionRunLock(Path(inbox_dir) / 'catalog_history' / 'write.lock', run_id=uuid4().hex):
        before = repository.get(entity_id)
        if before is None or before.get('entity_type') != 'variety':
            raise ValueError('Variety not found')
        if expected != revision(before):
            raise ValueError('This variety changed in another session. Reload before saving.')
        if not restore and confirmation != before['name']:
            raise ValueError('Type the variety name to confirm removal')
        after = deepcopy(before)
        after.setdefault('attributes', {})['catalog_removed'] = not restore
        return _write(inbox_dir, repository, before, after, actor=actor, action='restore' if restore else 'remove')


def editor_model(record):
    attrs = record.get('attributes') or {}
    return {'record': record, 'revision': revision(record), 'scalar_fields': SCALAR_FIELDS,
            'catalog_tables': TABLES, 'statuses': STATUSES, 'berry_options': BERRIES,
            'extra_fields': [{'key': key, 'value': json.dumps(value, ensure_ascii=False, indent=2) if not isinstance(value, str) else value,
                              'kind': 'text' if isinstance(value, str) else 'json'}
                             for key, value in attrs.items() if key not in RESERVED | set(SCALAR_FIELDS) | set(TABLES)],
            'removed': bool(attrs.get('catalog_removed'))}


@serialized_write
def save_relationship(inbox_dir, data_dir, schemas_dir, entity_id, form, *, actor):
    """An explicit human role edit over published support, never an AI approval."""
    from app.repositories.json.relationships import RelationshipRepository
    from app.repositories.json.evidence import EvidenceRepository
    with CollectionRunLock(Path(inbox_dir) / 'catalog_history' / 'write.lock', run_id=uuid4().hex):
        entity_repo = _repository(data_dir, schemas_dir)
        variety = entity_repo.get(entity_id)
        if not variety or variety.get('entity_type') != 'variety' or not visible(variety):
            raise ValueError('Variety not found')
        repository = RelationshipRepository(Path(data_dir), Path(schemas_dir))
        rel_id = str(form.get('relationship_id') or '')
        before = repository.get(rel_id) if rel_id else None
        if rel_id and (not before or entity_id not in {before.get('subject_id'), before.get('object_id')}):
            raise ValueError('Choose a relationship linked to this variety')
        if form.get('relationship_revision', '') != (revision(before) if before else ''):
            raise ValueError('This relationship changed in another session. Reload before saving.')
        if form.get('role_reviewed') != 'yes':
            raise ValueError('Confirm that you reviewed the supporting sources for this role')
        after = deepcopy(before) if before else {'id': 'rel-catalog-' + uuid4().hex, 'record_type': 'relationship'}
        after.update({key: str(form.get(key) or '').strip() for key in ('subject_id', 'object_id', 'predicate', 'status', 'notes')})
        if entity_id not in {after['subject_id'], after['object_id']}:
            raise ValueError('The relationship must include this variety')
        if not entity_repo.get(after['subject_id']) or not entity_repo.get(after['object_id']):
            raise ValueError('Both relationship endpoints must be existing catalog records')
        after['evidence_ids'] = _strings(form.get('evidence_ids'))
        evidence = EvidenceRepository(Path(data_dir), Path(schemas_dir))
        if not after['evidence_ids'] or any((evidence.get(key) or {}).get('status') != 'published' for key in after['evidence_ids']):
            raise ValueError('Link at least one existing published supporting source ID')
        after['effective_date'] = str(form.get('effective_date') or '').strip() or None
        repository._validate(after)
        return _write(inbox_dir, repository, before, after, actor=actor, action='edit_relationship' if before else 'add_relationship', history_id=entity_id)
