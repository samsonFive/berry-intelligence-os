"""Scoped capability research in the existing private workspace object store.

Canonical entities are supplied by the caller. Imports never publish Evidence,
create Atomic Facts, or infer entity/person identity from names. Automatic
capability decisions and analyst decisions are separate versioned objects.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from app.services.article_dedup import normalize_canonical_url
from app.services.living_workspaces import Store, Conflict, digest
from app.services.pipeline_lock import pipeline_lock

ROOT = Path(__file__).resolve().parents[2]
CATALOGUE = ROOT / 'data/imports/competitive-landscape-2026-10-30-v1/capability-rubrics.json'
KINDS = {'profile', 'observation', 'relationship', 'person', 'job', 'hiring_event', 'exposure', 'source', 'gap'}
TABLE_KINDS = {'profiles': 'profile', 'observations': 'observation', 'relationships': 'relationship',
               'people': 'person', 'jobs': 'job', 'hiring_events': 'hiring_event', 'exposures': 'exposure',
               'sources': 'source', 'gaps': 'gap'}
ROW_IDS = {'profile': 'entity_id', 'observation': 'observation_id', 'relationship': 'relationship_id',
           'person': 'person_id', 'job': 'job_id', 'hiring_event': 'event_id', 'exposure': 'exposure_id',
           'source': 'source_id', 'gap': 'gap_id'}
SCOPE = ('entity_id', 'peer_role', 'berry_id', 'destination_scope', 'origin_scope',
         'program_or_variety', 'period_start', 'period_end', 'use_system', 'rubric_version', 'capability_id')


def catalogue():
    return json.loads(CATALOGUE.read_text(encoding='utf-8'))


def identifier(prefix, value):
    return prefix + '-' + digest(value)[:28]


def source_refs(value):
    return list(dict.fromkeys(re.findall(r'[BR]\d{2}-S\d+', str(value or ''))))


def scope_key(scope):
    if any(not isinstance(scope.get(k), str) or not scope[k].strip() for k in SCOPE):
        raise ValueError('An explicit value is required for every scope field; use Unknown or unspecified where appropriate')
    return identifier('capability', [scope[k].strip() for k in SCOPE])


def source_check_usable(check):
    try:
        date.fromisoformat(str(check.get('checked_at') or '')[:10])
    except ValueError:
        return False
    return check.get('status') == 'inspected_supports_claim' and isinstance(check.get('support'), str) and bool(check['support'].strip())


def safe_original_url(value):
    try:
        parts = urlsplit(str(value or ''))
        return str(value) if parts.scheme in {'http', 'https'} and parts.hostname and not parts.username and not parts.password else ''
    except ValueError:
        return ''


def unpack_return(payload):
    """Normalize structural envelopes only; every original field stays intact."""
    if not isinstance(payload, dict):
        raise ValueError('Research return envelope must be an object')
    if 'tables' in payload:
        if not isinstance(payload['tables'], dict):
            raise ValueError('Research tables must be an object')
        result = []
        for key, table in payload['tables'].items():
            kind = TABLE_KINDS.get(key, 'unknown_table')
            rows = table.get('rows') if isinstance(table, dict) else None
            if not isinstance(rows, list):
                result.append({'record_kind':'malformed_table','local_id':str(key),'fields':{'raw':table}})
                continue
            for number, raw in enumerate(rows):
                fields = raw if isinstance(raw, dict) else {'raw':raw}
                result.append({'record_kind':kind if isinstance(raw, dict) else 'malformed_row',
                    'local_id':fields.get(ROW_IDS.get(kind,'')) or f'{key}-row-{number+1}', 'fields':fields})
        return result
    if not isinstance(payload.get('records'), list):
        raise ValueError('Research records must be a list; original envelope requires repair')
    return [deepcopy(row) if isinstance(row, dict) else {'record_kind':'malformed_row','fields':{'raw':deepcopy(row)}} for row in payload['records']]


def import_return(inbox_dir, *, batch_id, payload, original_sha256, entities, source_checks=None):
    if not re.fullmatch(r'(?:B\d{2}|R0[12])', batch_id):
        raise ValueError('Unsupported batch ID')
    if not re.fullmatch(r'[a-f0-9]{64}', original_sha256):
        raise ValueError('Original return SHA-256 is required')
    rows = unpack_return(payload)
    definitions = catalogue()
    rubric_version = definitions['rubric_version']
    caps = {c['capability_id']: c for c in definitions['capabilities']}
    sources = {r['fields']['source_id'] for r in rows if r.get('record_kind') == 'source' and isinstance(r.get('fields'),dict) and isinstance(r['fields'].get('source_id'),str)}
    source_checks = source_checks or {}
    if not isinstance(source_checks, dict):
        raise ValueError('Source inspections must be an object keyed by source ID')
    fingerprint = digest(['import-policy-v5', batch_id, original_sha256, rows, source_checks])
    batch_key = identifier('competitive-batch', [batch_id, fingerprint])
    store = Store(inbox_dir)
    with pipeline_lock(Path(inbox_dir), 'competitive-research-import'):
        with store.transaction() as db:
            previous = store.get(batch_key, db)
            if previous:
                return {**previous, 'replayed': True}
            counts, issues, ids = Counter(), [], []
            seen = {}
            for n, row in enumerate(rows):
                kind, fields = row.get('record_kind'), row.get('fields')
                reasons = []
                if not isinstance(kind, str) or kind not in KINDS or not isinstance(fields, dict):
                    reasons.append('Unrecognized or malformed row')
                    fields = fields if isinstance(fields, dict) else {'raw': fields}
                    kind = kind if isinstance(kind, str) else 'malformed_kind'
                eid = fields.get('entity_id', fields.get('subject_entity_id'))
                if (eid is not None and not isinstance(eid,str)) or (kind in KINDS-{'source'} and not eid) or (isinstance(eid,str) and eid not in entities):
                    reasons.append('Entity identity requires resolution; no name or multi-entity merge inferred')
                    eid = eid if isinstance(eid,str) else None
                elif eid in entities and kind not in {'gap', 'source'} and entities[eid].get('attributes', {}).get('identity_review_required'):
                    reasons.append('Canonical placeholder has an unresolved legal identity; no commercial identity inferred')
                if kind == 'observation' and (not isinstance(fields.get('capability_id'),str) or fields.get('capability_id') not in caps):
                    reasons.append('Capability mapping requires resolution')
                elif kind == 'observation' and fields.get('peer_role') not in caps[fields['capability_id']]['eligible_peer_roles']:
                    reasons.append('Peer role is ineligible for the mapped capability')
                if kind == 'observation' and any(fields.get(k) is not None and not isinstance(fields[k],str) for k in (*SCOPE,'berry_scope','production_system_fresh_processing') if k in fields):
                    reasons.append('Scope fields must be explicit text values; no list/object scope inferred')
                refs = source_refs(fields.get('source_ids'))
                if set(refs) - sources:
                    reasons.append('Missing source ledger reference')
                if kind == 'source' and not safe_original_url(fields.get('original_url')):
                    reasons.append('Original HTTP(S) source URL missing')
                if kind == 'source' and (not isinstance(fields.get('source_id'), str) or not re.fullmatch(r'[BR]\d{2}-S\d+', fields['source_id'])):
                    reasons.append('Source ledger ID requires repair')
                local = str(row.get('local_id') or f'row-{n + 1}')
                identity = [batch_id, kind, local]
                if tuple(identity) in seen and seen[tuple(identity)] != fields:
                    reasons.append('Conflicting versions retained for resolution')
                    identity.append(digest(fields))
                seen[tuple(identity[:3])] = fields
                key = identifier('competitive-record', identity)
                checked = source_checks.get(fields.get('source_id'), {}) if kind == 'source' and isinstance(fields.get('source_id'),str) else {}
                if not isinstance(checked, dict):
                    reasons.append('Source inspection metadata malformed; no verification inferred')
                    checked = {}
                record = {'id': key, 'batch_id': batch_id, 'kind': kind, 'local_id': local,
                          'entity_id': eid, 'fields': fields, 'source_refs': refs,
                          'original_return_sha256': original_sha256,
                          'original_row': {k: v for k, v in row.items() if k != 'fields'},
                          'verification': checked or {'status': 'unverified_research_return'},
                          'resolution': 'unresolved' if reasons else 'accepted_structure', 'issues': reasons}
                old = store.get(key, db)
                if old and old.get('article_id') and old['fields'].get('original_url') == fields.get('original_url'):
                    record['article_id'] = old['article_id']
                if kind == 'source' and not checked and old:
                    record['verification'] = deepcopy(old.get('verification', record['verification']))
                    if old['fields'] != fields and source_check_usable(record['verification']):
                        record['verification'] = {'status': 'source_changed_requires_reinspection',
                                                  'previous_check': record['verification']}
                # Original history is retained by Store.put. Analyst decisions live elsewhere.
                if old and old.get('original_return_sha256') != original_sha256:
                    record['supersedes_version'] = old['version']
                if not old or any(record.get(k) != old.get(k) for k in record):
                    store.put(db, 'competitive_record', record, 'research-import', expected=old['version'] if old else None)
                if kind == 'observation' and not reasons and fields.get('peer_role') in {'breeder', 'grower', 'marketer', 'technology_provider'} and fields.get('berry_scope') in {'berry-blueberry', 'berry-strawberry', 'berry-raspberry', 'berry-blackberry'}:
                    scope = {'entity_id': eid, 'peer_role': fields['peer_role'], 'berry_id': fields['berry_scope'],
                             'capability_id': fields['capability_id'], 'rubric_version': rubric_version,
                             'use_system': fields.get('production_system_fresh_processing') or 'Unknown'}
                    scope.update({k: fields.get(k) or 'Unknown' for k in SCOPE if k not in scope})
                    aid = scope_key(scope)
                    existing_auto = store.get(aid, db)
                    if not existing_auto:
                        unknown = {'id': aid, **scope, 'rating': 'unknown', 'label': 'Unknown',
                                   'status': 'unscored', 'confidence': 'unknown',
                                   'rationale': 'Research observation retained; no rubric anchor fully established.',
                                   'observation_ids': [key], 'source_ids': [], 'assessed_at': date.today().isoformat()}
                        unknown['basis'] = digest(unknown)
                        store.put(db, 'capability_automatic', unknown, 'research-import')
                    elif (old and record['original_return_sha256'] != old.get('original_return_sha256')) or key not in existing_auto.get('observation_ids', []):
                        update = deepcopy(existing_auto)
                        update['observation_ids'] = list(dict.fromkeys([*update.get('observation_ids', []), key]))
                        update['reassessment_needed'] = True
                        update['basis'] = digest([existing_auto['basis'], key, original_sha256])
                        store.put(db, 'capability_automatic', update, 'research-import', expected=existing_auto['version'])
                counts[record['resolution']] += 1
                if reasons:
                    issues.append({'record_id': key, 'row': local, 'reasons': reasons})
                ids.append(key)
            # A stricter validation pass can invalidate an earlier mapping. Keep
            # its history and analyst decision, while withdrawing the automatic
            # numeric proposal rather than displaying it as supported evidence.
            affected = set(ids)
            for auto in store.rows('capability_automatic', db):
                if not affected.intersection(auto.get('observation_ids', [])):
                    continue
                observations = [store.get(oid, db) for oid in auto.get('observation_ids', [])]
                def wrong_scope(observation):
                    if not observation or observation['resolution'] != 'accepted_structure':
                        return True
                    fields = observation['fields']
                    expected = {k:fields.get(k) or 'Unknown' for k in SCOPE}
                    expected.update(entity_id=observation['entity_id'], berry_id=fields.get('berry_scope'),
                                    use_system=fields.get('production_system_fresh_processing') or 'Unknown',
                                    rubric_version=rubric_version)
                    return any(auto[k] != expected[k] for k in SCOPE)
                if any(wrong_scope(o) for o in observations):
                    if auto.get('status') != 'requires_resolution':
                        update = {**auto, 'rating': 'unknown', 'label': 'Unknown', 'status': 'requires_resolution',
                                  'reassessment_needed': True, 'rationale': 'An observation mapping requires resolution; prior automatic proposal is retained in history.'}
                        update['basis'] = digest([auto['basis'], 'mapping_requires_resolution', original_sha256])
                        store.put(db, 'capability_automatic', update, 'research-validation', expected=auto['version'])
            report = {'id': batch_key, 'batch_id': batch_id, 'original_return_sha256': original_sha256,
                      'fingerprint': fingerprint, 'counts': dict(counts), 'issues': issues,
                      'record_ids': list(dict.fromkeys(ids)), 'source_checks': source_checks,
                      'trust_effect': 'No publication, Atomic Evidence or canonical identity changes',
                      'upstream_issues': deepcopy(payload.get('unresolved', [])),
                      'failed_rows': deepcopy(payload.get('failed', []))}
            return store.put(db, 'competitive_batch', report, 'research-import')


def record_sources(record, records):
    index = {(r['batch_id'], r['local_id']): r for r in records if r['kind'] == 'source'}
    return [index[(record['batch_id'], sid)] for sid in record['source_refs'] if (record['batch_id'], sid) in index]


def apply_anchor(inbox_dir, *, scope, observation_ids, checks, confidence, rationale, entities, confidence_details):
    """Apply a fully documented anchor; opaque score suggestions cannot pass."""
    key = scope_key(scope)
    cap = next((c for c in catalogue()['capabilities'] if c['capability_id'] == scope['capability_id']), None)
    if not cap or scope['entity_id'] not in entities or scope['peer_role'] not in cap['eligible_peer_roles']:
        raise ValueError('Canonical entity, capability and eligible role required')
    if entities[scope['entity_id']].get('attributes', {}).get('identity_review_required'):
        raise ValueError('Resolve the canonical entity identity before applying a capability anchor')
    if scope['rubric_version'] != cap['rubric_version']:
        raise ValueError('Rubric version mismatch')
    store = Store(inbox_dir)
    records = store.rows('competitive_record')
    by_id = {r['id']: r for r in records}
    selected = [by_id.get(i) for i in observation_ids]
    if not selected or any(not r or r['kind'] != 'observation' or r['resolution'] != 'accepted_structure' for r in selected):
        raise ValueError('Accepted, traceable observations are required')
    for r in selected:
        f = r['fields']
        if (r['entity_id'], f.get('peer_role'), f.get('capability_id')) != (scope['entity_id'], scope['peer_role'], scope['capability_id']):
            raise ValueError('Observation scope does not match assessment')
        if f.get('berry_scope') != scope['berry_id']:
            raise ValueError('Exact berry scope is required; no multi-crop expansion')
        for field, raw in [('destination_scope', 'destination_scope'), ('origin_scope', 'origin_scope'),
                           ('period_start', 'period_start'), ('period_end', 'period_end'),
                           ('program_or_variety', 'program_or_variety'),
                           ('use_system', 'production_system_fresh_processing')]:
            if (f.get(raw) or 'Unknown') != scope[field]:
                raise ValueError('Observation scope mismatch: ' + field)
    supported = []
    sources = {r['id']: r for obs in selected for r in record_sources(obs, records)}
    for anchor in cap['anchors']:
        proof = checks.get(str(anchor['level']))
        if not proof or proof.get('requirement') != anchor['requires'] or proof.get('all_conditions_supported') is not True:
            continue
        proofs = proof.get('source_ids', [])
        if not proofs or not isinstance(proof.get('explanation'), str) or not proof['explanation'].strip() or any(sid not in sources or sources[sid]['resolution'] != 'accepted_structure' or not source_check_usable(sources[sid]['verification']) for sid in proofs):
            continue
        supported.append(anchor)
    if not supported:
        raise ValueError('No anchor has every condition supported by inspected original evidence')
    if confidence not in {'low', 'medium', 'high'} or not rationale.strip():
        raise ValueError('Evidence confidence and rationale required')
    if any(not isinstance(confidence_details.get(k), str) or not confidence_details[k].strip() for k in ('directness', 'independence', 'recency', 'scope_fit', 'methodology', 'agreement')):
        raise ValueError('Describe every evidence-confidence factor')
    used = {sid for level in supported for sid in checks[str(level['level'])]['source_ids']}
    families = {sources[sid]['verification'].get('independence_group') or sources[sid]['verification'].get('source_family') for sid in used}
    families -= {None, '', 'Unknown', 'unknown'}
    urls = {normalize_canonical_url(sources[sid]['fields'].get('original_url')) for sid in used}
    if confidence == 'high' and (len(families) < 2 or len(urls - {''}) < 2):
        raise ValueError('High confidence requires independent corroboration')
    chosen = max(supported, key=lambda a: a['level'])
    auto = {'id': key, **scope, 'rating': chosen['level'], 'label': chosen['label'],
            'status': 'provisional', 'confidence': confidence, 'rationale': rationale,
            'observation_ids': observation_ids, 'source_ids': list(sources), 'anchor_checks': checks,
            'confidence_details': confidence_details,
            'assessed_at': date.today().isoformat(), 'claim_status': 'Original source attribution unchanged'}
    auto['source_basis'] = {sid: digest([s['fields'], s['verification']]) for sid, s in sources.items()}
    with store.transaction() as db:
        for sid, basis in auto['source_basis'].items():
            current = store.get(sid, db)
            if not current or digest([current['fields'], current['verification']]) != basis:
                raise Conflict('Source inspection changed during assessment; reload and reassess')
        for observation in selected:
            current = store.get(observation['id'], db)
            if not current or current['version'] != observation['version']:
                raise Conflict('Observation changed during assessment; reload and reassess')
        old = store.get(key, db)
        basis = digest({k: v for k, v in auto.items() if k != 'assessed_at'})
        if old and old.get('basis') == basis:
            return effective_assessment(store, old, db)
        auto['basis'] = basis
        result = store.put(db, 'capability_automatic', auto, 'rubric-application', expected=old['version'] if old else None)
        return effective_assessment(store, result, db)


def effective_assessment(store, auto, db=None):
    changed_sources = any(not (s := store.get(sid, db)) or digest([s['fields'], s['verification']]) != basis
                          for sid, basis in auto.get('source_basis', {}).items())
    decision = store.get('decision-' + auto['id'], db)
    if decision and decision.get('mode') != 'automatic':
        return {**auto, **decision['values'], 'automatic': auto, 'decision': decision,
                'new_evidence': changed_sources or decision.get('reviewed_basis') != auto['basis']}
    return {**auto, 'decision': decision, 'new_evidence': changed_sources or auto.get('reassessment_needed', False)}


def correct_assessment(inbox_dir, *, assessment_id, expected_version, mode, rating, rationale, actor, corrected_scope=None):
    store = Store(inbox_dir)
    if mode not in {'override', 'reviewed', 'automatic'} or not rationale.strip():
        raise ValueError('Choose review, correction or automatic and explain the decision')
    if rating not in {1, 2, 3, 4, 5, 'unknown', 'not_applicable'}:
        raise ValueError('Unsupported rating state')
    with store.transaction() as db:
        auto = store.get(assessment_id, db)
        if not auto or not assessment_id.startswith('capability-'):
            raise ValueError('Assessment not found')
        old = store.get('decision-' + assessment_id, db)
        if (old['version'] if old else 0) != expected_version:
            raise Conflict('A newer analyst decision exists; reload before saving')
        values = {'rating': rating if mode == 'override' else effective_assessment(store, auto, db)['rating'],
                  'status': 'overridden' if mode == 'override' else 'reviewed', 'rationale': rationale}
        if mode == 'override':
            values['confidence'] = 'unknown'
        allowed_scope = {'berry_id', 'destination_scope', 'origin_scope', 'program_or_variety', 'period_start', 'period_end', 'use_system'}
        if mode == 'reviewed' and old and old.get('mode') != 'automatic':
            values = {**old['values'], **values}
        if corrected_scope:
            if mode != 'override' or set(corrected_scope) != allowed_scope or any(not isinstance(v, str) or not v.strip() or len(v) > 2000 for v in corrected_scope.values()):
                raise ValueError('Scope corrections require an explicit override and every editable scope field')
            if corrected_scope['berry_id'] not in {'berry-blueberry', 'berry-strawberry', 'berry-raspberry', 'berry-blackberry', 'Unknown'}:
                raise ValueError('Choose a canonical berry or Unknown')
            values.update(corrected_scope, confidence='unknown', scope_corrected=True)
            values['effective_scope_key'] = scope_key({**auto, **corrected_scope})
        value = {'id': 'decision-' + assessment_id, 'mode': mode, 'reviewed_basis': auto['basis'],
                 'values': values,
                 'change_reason': 'analyst_scope_correction' if corrected_scope else 'analyst_' + mode,
                 'scope': {k: auto[k] for k in SCOPE}}
        return store.put(db, 'capability_decision', value, actor, expected=old['version'] if old else None)


def job_groups(records):
    """Keep postings distinct from unknown search results and unknown headcount.

    Known requisitions take precedence. A later discovered requisition can absorb
    an earlier URL-only observation only if that URL identifies one known
    requisition. A reused careers URL with different known IDs stays ambiguous.
    """
    groups, url_to_known, unknown = {}, {}, []
    empty = {'', 'unknown', 'none', 'n/a', 'not applicable', 'not found'}
    for record in records:
        if record['kind'] != 'job' or record['resolution'] != 'accepted_structure':
            continue
        f = record['fields']
        url = normalize_canonical_url(f.get('original_url')) if safe_original_url(f.get('original_url')) else ''
        req = str(f.get('requisition_id') or '').strip()
        title = str(f.get('title') or '').strip()
        known_req = req.casefold() not in empty
        if not known_req and (not url or title.casefold() in empty):
            continue  # A vacancy-search gap remains a record, not a posting count.
        if known_req:
            key = identifier('observed-job', [record['entity_id'], req])
            groups.setdefault(key, {'id': key, 'entity_id': record['entity_id'], 'observations': []})['observations'].append(record)
            if url:
                url_to_known.setdefault((record['entity_id'], url), set()).add(key)
        else:
            unknown.append((record, url))
    for record, url in unknown:
        matches = url_to_known.get((record['entity_id'], url), set())
        key = next(iter(matches)) if len(matches) == 1 else identifier('observed-job', [record['entity_id'], url])
        group = groups.setdefault(key, {'id': key, 'entity_id': record['entity_id'], 'observations': []})
        group['observations'].append(record)
        if len(matches) > 1:
            group['identity_issue'] = 'Original URL has multiple requisitions; URL-only observation held separately'
    for group in groups.values():
        group['observations'].sort(key=lambda r: (r['fields'].get('last_observed_date', ''), r['version']))
        group['latest'] = group['observations'][-1]
        group['interpretation'] = 'Observed posting history; no hire or workforce growth inferred'
    return list(groups.values())


def peer_positions(assessments, eligible_count):
    groups = {}
    keys = ('peer_role', 'berry_id', 'destination_scope', 'origin_scope', 'period_start', 'period_end', 'use_system', 'rubric_version', 'capability_id')
    for a in assessments:
        if isinstance(a['rating'], int):
            groups.setdefault(tuple(a[k] for k in keys), []).append(a)
    result = {}
    for cohort in groups.values():
        # Multiple programmes for one entity are observations, not extra competitors.
        entities = {a['entity_id'] for a in cohort}
        ambiguous = len(entities) != len(cohort)
        for a in cohort:
            rank = 1 + sum(b['rating'] > a['rating'] for b in cohort)
            result[a['id']] = {'rank': None if ambiguous else rank, 'ties': sum(b['rating'] == a['rating'] for b in cohort),
                               'size': len(entities), 'coverage': len(entities) / max(1, eligible_count),
                               'percentile': None, 'note': 'Selected compatible observations only; no industry percentile or overall score'}
    return result
