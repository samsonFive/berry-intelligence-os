"""Reconcile existing spreadsheet and source research into editable catalog entries.

Operator-authorized catalog population, never identity/claim approval. Original
research and review decisions remain untouched; all additions are unverified,
workspace-only records. Plans are hash-bound to their input and dry-run first.
"""
from copy import deepcopy
from hashlib import sha256
import json
import re
from pathlib import Path
from uuid import uuid4
from functools import lru_cache
from datetime import UTC, datetime

from app.repositories.json.entities import EntityRepository
from app.services import variety_catalog as catalog
from app.services.analyst_state_io import atomic_json, serialized_write
from app.services.collection_runner import CollectionRunLock
from app.services.map_regions import public_source_url
from app.services.variety_universe.identity import _identity_strings, fold_identity


def _unique(rows):
    result, seen = [], set()
    for row in rows:
        key = json.dumps(row, sort_keys=True, ensure_ascii=False)
        if key not in seen:
            result.append(row)
            seen.add(key)
    return result


def _digest(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def build_plan(*, entities, research_rows=(), research_profiles=None, seed_rows=(), portfolio_sources=(), candidates=(), include_portfolios=True):
    """Exact crop-scoped reconciliation; conflicts are held, never fuzzy merged."""
    original = {row['id']: deepcopy(row) for row in entities}
    working = deepcopy(original)
    research_profiles = research_profiles or {}
    held, links = [], []
    index = {}

    def add_index(record):
        for text, _ in _identity_strings(record):
            for berry in record.get('berry_ids') or catalog.BERRIES:
                key = (berry, fold_identity(text))
                if key[1]:
                    index.setdefault(key, set()).add(record['id'])

    for record in working.values():
        if record.get('entity_type') == 'variety':
            add_index(record)
    rejected = {(row.get('berry_id'), fold_identity(row.get('candidate_name'))) for row in candidates if row.get('status') == 'rejected' or row.get('identity_state') == 'rejected'}
    blocked = {(row.get('berry_id'), fold_identity(row.get('candidate_name'))) for row in candidates
               if row.get('human_gated') and row.get('identity_state') in {'unknown', 'possible_alias'}}
    confirmed = {(row.get('berry_id'), fold_identity(row.get('candidate_name'))): row.get('candidate_canonical_match')
                 for row in candidates if row.get('human_gated') and row.get('identity_state') == 'confirmed_same'}

    def commercial_party(party):
        cid, name = party.get('entity_id', ''), party.get('name', '')
        if cid and cid not in working:
            hits = [row for row in working.values() if row.get('entity_type') in {'company', 'brand', 'breeding_program'}
                    and fold_identity(row.get('name')) == fold_identity(name)]
            if len(hits) == 1:
                cid = hits[0]['id']
            elif len(hits) == 0 and re.fullmatch(r'company-research-[a-z0-9-]+', cid) and name:
                working[cid] = {'id': cid, 'record_type': 'entity', 'entity_type': 'company', 'name': name,
                                'aliases': [], 'status': 'unverified', 'description': 'Organization named in source-attributed variety research.',
                                'berry_ids': [], 'evidence_ids': [], 'fact_ids': [], 'relationship_ids': [],
                                'attributes': {'catalog_visibility': 'workspace'}}
            else:
                cid = ''
        return cid

    def attach(name, berry, *, key, preferred_id='', issue='', sources=(), connections=(), rights=(), summary='', reported_names=(), identity_attributes=None):
        identity = (berry, fold_identity(name))
        if not name or berry not in catalog.BERRIES or not identity[1] or identity in rejected or identity in blocked or issue:
            held.append({'key': key, 'name': name, 'berry': berry, 'reason': issue or 'Rejected, unresolved identity decision, missing name or crop'})
            return
        hits = set(index.get(identity, set()))
        if identity in confirmed:
            target = confirmed[identity]
            if not target or target not in working or working[target].get('entity_type') != 'variety':
                held.append({'key': key, 'name': name, 'berry': berry, 'reason': 'Saved identity decision has no available catalog target'})
                return
            hits.add(target)
        for text in reported_names:
            hits.update(index.get((berry, fold_identity(text)), set()))
        if len(hits) > 1:
            held.append({'key': key, 'name': name, 'berry': berry, 'reason': 'Multiple exact catalog identities', 'matches': sorted(hits)})
            return
        entity_id = next(iter(hits), '')
        if not entity_id:
            entity_id = preferred_id or 'variety-' + re.sub(r'[^a-z0-9]+', '-', name.casefold()).strip('-')[:90] + '-' + _digest(identity)[:8]
            if entity_id in working:
                held.append({'key': key, 'name': name, 'berry': berry, 'reason': 'Existing record ID belongs to a different identity'})
                return
            record = {'id': entity_id, 'record_type': 'entity', 'entity_type': 'variety', 'name': name,
                      'aliases': [], 'status': 'unverified', 'description': summary or 'Catalog entry from supplied research. Identity and source assertions remain unverified.',
                      'berry_ids': [berry], 'roles': [], 'evidence_ids': [], 'fact_ids': [], 'relationship_ids': [],
                      'attributes': {'catalog_visibility': 'workspace', 'catalog_import': {'kind': 'source_research', 'identity_review': 'unverified'}}}
            working[entity_id] = record
            add_index(record)
        for text in reported_names:
            if fold_identity(text):
                index.setdefault((berry, fold_identity(text)), set()).add(entity_id)
        record = working[entity_id]
        if not catalog.visible(record):
            held.append({'key': key, 'name': name, 'berry': berry, 'reason': 'Removed by an editor; import will not restore it'})
            return
        attrs = record.setdefault('attributes', {})
        if entity_id not in original:
            for field, value in (identity_attributes or {}).items():
                if value:
                    attrs.setdefault(field, value)
            add_index(record)
        # Existing public profiles receive private enrichment separately below;
        # their canonical bytes, identity and status are never rewritten.
        for field, values in [('catalog_sources', sources), ('catalog_connections', connections), ('catalog_rights', rights)]:
            if values:
                attrs[field] = _unique([*(attrs.get(field) or []), *values])
        if summary and entity_id not in original:
            record['description'] = summary
        links.append({'key': key, 'entity_id': entity_id, 'name': name, 'berry': berry})

    for row in research_rows:
        dossiers = (research_profiles.get(row['entity_id']) or {}).get('dossiers') or []
        sources, connections, rights = [], [], []
        issues = [item.get('issue') for item in dossiers if item.get('issue')]
        for dossier in dossiers:
            if dossier.get('rows'):
                sources.append({'title': 'Supplied patent/PBR spreadsheet photos', 'url': '',
                                'checked_on': dossier.get('checked_on', ''),
                                'note': 'Reconstructed photo rows ' + ', '.join(map(str, dossier['rows']))
                                        + '. Original transcription and research remain linked on this profile.',
                                'review_state': 'unreviewed'})
            for source in dossier.get('sources') or []:
                url = public_source_url(source.get('url'))
                if url:
                    sources.append({'title': source.get('title') or url, 'url': url, 'checked_on': dossier.get('checked_on', ''),
                                    'note': source.get('kind', ''), 'review_state': 'unreviewed'})
            for party in dossier.get('commercial_contacts') or []:
                urls = [url for raw in party.get('source_urls') or [] if (url := public_source_url(raw))]
                connections.append({'entity_id': commercial_party(party), 'name': party['name'], 'role': party.get('role') or 'Role unspecified',
                                    'territory': party.get('territory', ''), 'source_url': urls[0] if urls else '',
                                    'note': party.get('relationship_note', ''), 'review_state': 'unreviewed'})
            for application in dossier.get('applications') or []:
                rights.append({'number': application, 'jurisdiction': application.split('_')[0], 'status': 'As supplied; current legal status unverified',
                               'source_url': '', 'note': 'Photographed patent/PBR research; original transcription retained on this profile.', 'review_state': 'unreviewed'})
        private = row.get('private_entity') or original.get(row['entity_id']) or {}
        berries = private.get('berry_ids') or ['berry-' + str(berry).casefold() for berry in row.get('berries') or []]
        berry = berries[0] if len(berries) == 1 else ''
        attach(row['name'], berry, key='research:' + row['entity_id'], preferred_id=row['entity_id'], issue='; '.join(issues),
               sources=sources, connections=connections, rights=rights,
               summary=' '.join(dict.fromkeys(item.get('summary', '') for item in dossiers)).strip())

    for row in seed_rows:
        knowledge = row.get('knowledge') or {}
        connections = [{'entity_id': item.get('entity_id', ''), 'name': item.get('name', ''), 'role': 'Spreadsheet association; role unspecified',
                        'territory': '', 'source_url': '', 'note': item.get('registry_label', '') + ' · supplied spreadsheet photos, 30 September 2026',
                        'review_state': 'unreviewed'} for item in knowledge.get('company_associations') or []]
        name = row['candidate_name']
        # A short spreadsheet label such as Pop beside Fall Creek can be a
        # shorthand for SEKOYA Pop. Hold the overlap instead of inventing a
        # second cultivar or silently approving the shorthand as an alias.
        shorthand = [item for item in original.values() if item.get('entity_type') == 'variety'
                     and row['berry_id'] in (item.get('berry_ids') or [])
                     and len(fold_identity(name).split()) == 1
                     and fold_identity(item['name']).endswith(' ' + fold_identity(name))]
        attach(name, row['berry_id'], key='photo:' + name + ':' + row['berry_id'],
               issue=('Possible abbreviated catalog name: ' + ', '.join(item['name'] for item in shorthand)) if shorthand else '',
               sources=[{'title': 'Supplied variety spreadsheet photos · 30 September 2026', 'url': '', 'checked_on': '2026-09-30',
                         'note': 'Literal spreadsheet name; company role and identity have not been independently confirmed.', 'review_state': 'unreviewed'}], connections=connections)

    if include_portfolios:
        for source in portfolio_sources:
            for row in source.get('names') or []:
                name, berry = row.get('candidate_name') or '', row.get('berry_id') or ''
                # Discrepancy warnings and explicitly partial/unclear rows must
                # remain in the source queue. Do not choose a code/name mapping.
                issue = '; '.join(source.get('review_warnings') or [])
                warning_scopes = source.get('review_warning_scopes') or []
                if warning_scopes:
                    scoped_messages = {item['message'] for item in warning_scopes}
                    issue = '; '.join([message for message in source.get('review_warnings') or [] if message not in scoped_messages]
                                      + [item['message'] for item in warning_scopes if name in item.get('candidate_names', [])])
                if row.get('identity_hold') or row.get('review_warnings'):
                    issue = issue or 'Source identity needs review'
                if len(fold_identity(name)) < 3:
                    issue = issue or 'Short selection label needs source-specific identity resolution'
                url = public_source_url(row.get('product_url') or source.get('url'))
                company_ids = row.get('source_company_ids', source.get('company_ids') or [])
                role = ('Organization named in rights source' if source.get('source_type') in {'plant_patent', 'national_register', 'plant_breeders_rights_record'}
                        else 'Catalog / program listing' if source.get('source_type') in {'breeder_catalog', 'nursery_catalog', 'breeder_program_report'}
                        else 'Organization named in source')
                connections = [{'entity_id': cid, 'name': working.get(cid, {}).get('name', cid), 'role': role,
                                'territory': '', 'source_url': url, 'note': row.get('source_company_context') or source.get('limitations', ''),
                                'review_state': 'unreviewed'} for cid in company_ids]
                note = 'Observed as ' + name + '. ' + ' · '.join(str(row.get(field) or '') for field in ('portfolio_context', 'trade_name', 'breeder_code') if row.get(field))
                attach(name, berry, key='portfolio:' + source['id'] + ':' + name, issue=issue,
                       sources=[{'title': source.get('title') or source['id'], 'url': url, 'checked_on': source.get('checked_on', ''),
                                 'note': note, 'review_state': 'unreviewed'}], connections=connections,
                       reported_names=[str(row.get(field) or '') for field in ('denomination', 'trade_name', 'breeder_code')],
                       identity_attributes={field: str(row.get(field) or '') for field in ('denomination', 'trade_name', 'breeder_code')})

    additions = [record for key, record in working.items() if key not in original]
    # Do not overwrite existing canonical edits. Enrichment for those entries is
    # held privately and joined by the live catalog presenter.
    enrichment = {key: {field: row.get('attributes', {}).get(field, []) for field in catalog.TABLES}
                  for key, row in working.items() if key in original and row != original[key]}
    plan = {'version': 1, 'baseline': {key: catalog.revision(value) for key, value in original.items()},
            'additions': additions, 'enrichment': enrichment, 'held': held, 'links': links,
            'counts': {'existing_varieties': sum(row.get('entity_type') == 'variety' for row in original.values()),
                       'new_varieties': sum(row['entity_type'] == 'variety' for row in additions),
                       'new_organizations': sum(row['entity_type'] != 'variety' for row in additions),
                       'enriched_existing': len(enrichment), 'held_occurrences': len(held)}}
    plan['digest'] = _digest(plan)
    return plan


@serialized_write
def apply_plan(inbox_dir, data_dir, schemas_dir, plan, *, expected_digest, actor):
    if plan.get('digest') != expected_digest or _digest({key: value for key, value in plan.items() if key != 'digest'}) != expected_digest:
        raise ValueError('The catalog plan changed; review the new plan before applying')
    if not actor.strip():
        raise ValueError('Record the operator authorizing this catalog import')
    repository = EntityRepository(Path(data_dir), Path(schemas_dir))
    with CollectionRunLock(Path(inbox_dir) / 'catalog_history' / 'write.lock', run_id=uuid4().hex):
        current = {row['id']: row for row in repository.list()}
        # An interrupted/repeated import is additive and never overwrites edits.
        for key, digest in plan['baseline'].items():
            if key not in current or catalog.revision(current[key]) != digest:
                raise ValueError('Existing catalog changed since planning: ' + key)
        # Preflight the whole plan before the first write. A collision near the
        # end must not leave a partially applied batch.
        preview = dict(current)
        for record in plan['additions']:
            old = preview.get(record['id'])
            if old is not None and old != record:
                raise ValueError('An imported record already exists with changes: ' + record['id'])
            if old is None and record['entity_type'] == 'variety' and catalog.identity_collisions(record, list(preview.values())):
                raise ValueError('A new identity conflicts with the import plan: ' + record['name'])
            repository._validate(record)
            preview[record['id']] = record
        pending = []
        for record in plan['additions']:
            old = current.get(record['id'])
            if old is not None:
                if old != record:
                    raise ValueError('An imported record already exists with changes: ' + record['id'])
                continue
            pending.append(record)
        receipt_path = Path(inbox_dir) / 'catalog_imports' / (expected_digest + '.json')
        old_receipt = json.loads(receipt_path.read_text(encoding='utf-8')) if receipt_path.exists() else {}
        receipt = {'version': 1, 'plan_digest': expected_digest, 'actor': old_receipt.get('actor', actor),
                   'at': old_receipt.get('at', datetime.now(UTC).isoformat()), 'state': 'prepared',
                   'records': plan['additions'], 'added_ids': [row['id'] for row in pending],
                   'enrichment': plan['enrichment'], 'held': plan['held'], 'links': plan['links'], 'counts': plan['counts']}
        # One durable batch journal precedes the existing validated bulk-create
        # repository hook. This avoids a complete filesystem scan per variety.
        # A crash can be replayed: matching existing records are skipped, edits
        # are never overwritten, and the original journal remains recoverable.
        atomic_json(receipt_path, receipt)
        repository.create_many(pending)
        receipt['state'] = 'saved'
        atomic_json(receipt_path, receipt)
        return receipt


@lru_cache(maxsize=8)
def _read_enrichment(signature):
    result = {}
    for filename, _mtime, _size in signature:
        path = Path(filename)
        receipt = json.loads(path.read_text(encoding='utf-8'))
        for key, attrs in receipt.get('enrichment', {}).items():
            result.setdefault(key, {})
            for field, values in attrs.items():
                result[key][field] = _unique([*result[key].get(field, []), *values])
    return result


def imported_enrichment(inbox_dir):
    signature = tuple((str(path), path.stat().st_mtime_ns, path.stat().st_size)
                      for path in sorted((Path(inbox_dir) / 'catalog_imports').glob('*.json')))
    return deepcopy(_read_enrichment(signature))


def effective_record(record, enrichment):
    record = deepcopy(record)
    attrs = record.setdefault('attributes', {})
    for field, values in enrichment.get(record['id'], {}).items():
        # An explicit editor value (including an empty table) always wins.
        if field not in attrs:
            attrs[field] = deepcopy(values)
    return record


@lru_cache(maxsize=8)
def _read_import_history(signature):
    result = {}
    for filename, _mtime, _size in signature:
        batch = json.loads(Path(filename).read_text(encoding='utf-8'))
        for record in batch.get('records', []):
            result.setdefault(record['id'], []).append({'id': batch['plan_digest'], 'entity_id': record['id'],
                'at': batch.get('at', ''), 'actor': batch['actor'], 'action': 'import_unverified',
                'before': None, 'after': record, 'state': batch.get('state', 'prepared')})
    return result


def import_history(inbox_dir, entity_id):
    signature = tuple((str(path), path.stat().st_mtime_ns, path.stat().st_size)
                      for path in sorted((Path(inbox_dir) / 'catalog_imports').glob('*.json')))
    return deepcopy(_read_import_history(signature).get(entity_id, []))
