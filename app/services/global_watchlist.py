"""Unified, evidence-backed company projection and private workspace state.

No name matching is used for evidence associations. Corrections are overlays,
applied on every projection; ingestion cannot overwrite analyst decisions.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from datetime import date
from urllib.parse import urlsplit

from app.services.article_dedup import normalize_canonical_url
from app.services.berries.geography import geography_region, REGIONS
from app.services.berries.landscape import SEED_FIXTURE_ENTITY_IDS, SEED_FIXTURE_EVIDENCE_IDS
from app.services.competitor_landscape import normalize_tier_status, TIER_STATUS_VALUES
from app.services.competitor_registry import load_latest_snapshot, load_reconciliation_matrix, monitoring_state_for_entity
from app.services.living_workspaces import Conflict, digest, ident, now
from app.services.entity_identity import merged_into_id
from app.services.story_threads import group_story_threads
from app.services.association_corrections import apply as apply_corrections

KINDS = {name: 'global_watchlist_' + name for name in ('group', 'note', 'correction', 'tiers')}
ENTITY_TYPES = {'company', 'breeding_program', 'brand', 'retailer', 'nursery', 'technology_provider'}
BERRIES = ('blueberry', 'strawberry', 'raspberry', 'blackberry')


def real_record(row):
    """Demo content never contributes to coverage, assessment or export."""
    attrs = row.get('attributes') or {}
    return not (row.get('id') in SEED_FIXTURE_EVIDENCE_IDS or row.get('is_demo') or
                row.get('demo') or row.get('data_class') in {'demo', 'illustrative'} or
                attrs.get('is_demo') or attrs.get('demo') or row.get('illustrative'))


def safe_url(value):
    try:
        parsed = urlsplit(str(value or ''))
        return str(value) if parsed.scheme in {'http', 'https'} and parsed.hostname and not parsed.username and not parsed.password else ''
    except ValueError:
        return ''


def checked_version(old, version):
    if (old or {}).get('version', 0) != int(version):
        raise Conflict('This record changed. Reload before saving your changes.')


def groups(store):
    return sorted([g for g in store.rows(KINDS['group']) if not g.get('deleted')], key=lambda g: g['name'].casefold())


def edit_group(store, *, actor, action, name='', group_id='', entity_id='', version=0, entities=None):
    if action not in {'create', 'rename', 'delete', 'add', 'remove'}:
        raise ValueError('Choose a group action')
    with store.transaction() as db:
        old = store.get(group_id, db) if group_id else None
        if action != 'create' and (not old or old.get('kind') != 'monitoring_group' or old.get('deleted')):
            raise ValueError('Monitoring group not found')
        checked_version(old, version)
        value = deepcopy(old) if old else {'id': ident('gw-group-'), 'kind': 'monitoring_group',
                    'schema_version': 1, 'visibility': 'workspace', 'member_ids': [], 'created_by': actor, 'created_at': now()}
        if action in {'create', 'rename'}:
            if not 1 <= len(name.strip()) <= 100:
                raise ValueError('Group name must contain 1 to 100 characters')
            value['name'] = name.strip()
        elif action == 'delete':
            value['deleted'] = True
        else:
            if entity_id not in (entities or {}) or entities[entity_id].get('entity_type') not in ENTITY_TYPES:
                raise ValueError('Choose a canonical organization')
            members = set(value['member_ids'])
            if action == 'add':
                members.add(entity_id)
            else:
                members.discard(entity_id)
            value['member_ids'] = sorted(members)
        return store.put(db, KINDS['group'], value, actor, expected=old['version'] if old else None)


def add_note(store, *, actor, entity_id, classification, text, observed_at, reference, entities):
    if entity_id not in entities:
        raise ValueError('Choose a canonical entity')
    if classification not in {'sourced_claim', 'hypothesis', 'anecdote', 'observation'}:
        raise ValueError('Choose observation, sourced claim, hypothesis or anecdote')
    if not text.strip() or len(text) > 10000:
        raise ValueError('Enter a note of up to 10,000 characters')
    observed_at = date.fromisoformat(observed_at).isoformat()
    if reference and not safe_url(reference):
        raise ValueError('Reference must be an HTTP(S) source URL')
    value = {'id': ident('gw-note-'), 'schema_version': 1, 'entity_id': entity_id,
             'classification': classification, 'text': text.strip(), 'observed_at': observed_at,
             'created_at': now(), 'author': actor, 'visibility': 'workspace', 'review_state': 'unreviewed',
             'reference': reference, 'limitation': 'Analyst capture; not a verified Fact'}
    with store.transaction() as db:
        return store.put(db, KINDS['note'], value, actor)


def correct_association(store, *, actor, record_id, field, entity_id, action, reason, version, entities, evidence):
    if record_id not in evidence or field not in {'entity_ids', 'geography_ids', 'berry_ids'}:
        raise ValueError('Choose a captured source and supported association field')
    if entity_id not in entities or action not in {'include', 'exclude'} or not reason.strip():
        raise ValueError('Choose a canonical association and explain the correction')
    expected_type = {'geography_ids': 'geography', 'berry_ids': 'berry'}.get(field)
    if expected_type and entities[entity_id].get('entity_type') != expected_type:
        raise ValueError('Association type does not match the selected field')
    key = 'gw-correction-' + digest([record_id, field, entity_id])
    with store.transaction() as db:
        old = store.get(key, db)
        checked_version(old, version)
        return store.put(db, KINDS['correction'], {'id': key, 'schema_version': 1, 'record_id': record_id,
            'field': field, 'entity_id': entity_id, 'action': action, 'reason': reason.strip(),
            'visibility': 'workspace'}, actor, expected=old['version'] if old else None)


def corrected_records(evidence, corrections):
    return apply_corrections([deepcopy(row) for row in evidence if real_record(row) and row.get('status') == 'published'], corrections)


def tier_report(snapshot, matrix, entities):
    """Validate existing canonical import without upgrading its review status."""
    rows = (matrix or {}).get('rows', [])
    if not isinstance(rows, list):
        raise ValueError('Tier import rows must be a list')
    unmatched, conflicts, seen, assignments = [], [], {}, []
    for row in rows:
        if not isinstance(row, dict):
            conflicts.append({'issue': 'Malformed tier row retained for repair', 'row': row})
            continue
        key = row.get('canonical_entity_id')
        if key not in entities:
            unmatched.append({'label': row.get('spreadsheet_label'), 'entity_id': key})
            if row.get('alias_conflicts'):
                conflicts.append({'label': row.get('spreadsheet_label'), 'alias_matches': row['alias_conflicts']})
            continue
        if not isinstance(row.get('berry_tier', {}), dict) or not isinstance(row.get('regions', []), list) or any(not isinstance(r, str) for r in row.get('regions', [])):
            conflicts.append({'entity_id': key, 'issue': 'Tier cells must be an object and regions a list of strings'})
            continue
        for berry, raw in (row.get('berry_tier') or {}).items():
            tier = normalize_tier_status(raw)
            if berry not in BERRIES or tier not in TIER_STATUS_VALUES:
                conflicts.append({'entity_id': key, 'berry': berry, 'value': raw})
                continue
            source_scope = {'regions': row.get('regions', []), 'scope': row.get('scope'),
                            'effective_date': row.get('effective_date'), 'end_date': row.get('end_date')}
            identity = (key, berry, digest(source_scope))
            if identity in seen and seen[identity] != tier:
                conflicts.append({'entity_id': key, 'berry': berry, 'values': [seen[identity], tier]})
                continue
            if identity not in seen:
                assignments.append({'entity_id': key, 'berry': berry, 'tier': tier,
                    **source_scope,
                    'source_snapshot_date': (snapshot or {}).get('snapshot_date')})
            seen[identity] = tier
    return {'source': (snapshot or {}).get('source', 'Unavailable'),
        'snapshot_date': (snapshot or {}).get('snapshot_date', 'Unknown'),
        'review_state': 'unreviewed_import' if snapshot else 'source_unavailable',
        'caveat': (snapshot or {}).get('transcription_caveat', 'No authoritative tier source available; assignments remain unassigned.'),
        'provenance_evidence_id': (snapshot or {}).get('provenance_evidence_id'),
        'tier_definitions': (snapshot or {}).get('tier_definitions') or 'Definitions not supplied by the retained source; labels are preserved without inferring a scoring methodology.',
        'assignments': assignments, 'unmatched': unmatched, 'conflicts': conflicts,
        'source_row_count': len(rows)}


def import_tiers(store, snapshot, matrix, entities, actor='tier-import'):
    report = tier_report(snapshot, matrix, entities)
    key = 'gw-tiers-' + digest([snapshot, matrix])
    with store.transaction() as db:
        old = store.get(key, db)
        if old:
            return old
        return store.put(db, KINDS['tiers'], {'id': key, 'schema_version': 1, **report}, actor)


def grouped_news(records):
    # Reuse the established conservative same-development grouping. It adds
    # organizational edges only, never entity links or confidence.
    dated = []
    for record in records:
        try:
            date.fromisoformat(str(record.get('published_date') or '')[:10])
        except ValueError:
            continue
        dated.append(record)
    # The general thread service may fall back to capture dates. Undated
    # catalog/about pages must never become one "development" through capture.
    threads = group_story_threads(dated)
    story_by_id = {key: thread['id'] for thread in threads for key in thread['member_ids']}
    grouped = defaultdict(list)
    for row in records:
        key = row.get('syndication_group_id') or story_by_id.get(row['id']) or normalize_canonical_url(row.get('canonical_url') or row.get('source_url')) or row['id']
        grouped[key].append(row)
    result = []
    for members in grouped.values():
        members.sort(key=lambda r: (r.get('published_date') or '', r['id']), reverse=True)
        families = {r.get('syndication_group_id') or normalize_canonical_url(r.get('canonical_url') or r.get('source_url')) or r['id'] for r in members}
        result.append({'lead': members[0], 'sources': members,
                       'independence': ('Syndication / shared URL; not independent corroboration' if len(families) == 1 else 'Grouped development; source independence not established') if len(members) > 1 else 'Source independence not established'})
    return sorted(result, key=lambda g: (g['lead'].get('published_date') or '', g['lead']['id']), reverse=True)


def build(*, entities, evidence, relationships, signals, assessments, data_dir, store, watches, params, sources=()):
    entities = {r['id']: r for r in entities if r['id'] not in SEED_FIXTURE_ENTITY_IDS and not merged_into_id(r)}
    corrections = store.rows(KINDS['correction'])
    records = corrected_records(evidence, corrections)
    snapshot, matrix = load_latest_snapshot(data_dir), load_reconciliation_matrix(data_dir)
    report = tier_report(snapshot, matrix, entities)
    imported = sorted(store.rows(KINDS['tiers']), key=lambda r: (r['snapshot_date'], r['updated_at']), reverse=True)
    if imported and (not snapshot or imported[0]['snapshot_date'] >= report['snapshot_date']):
        report = imported[0]
    tier_rows = {r['canonical_entity_id']: r for r in (matrix or {}).get('rows', [])}
    scoped_assignments = defaultdict(list)
    selected_regions = set(str(params.get('region') or '').split(',')) - {''}
    for assignment in report['assignments']:
        if selected_regions and assignment['regions'] and not selected_regions.intersection(assignment['regions']):
            continue
        scoped_assignments[(assignment['entity_id'], assignment['berry'])].append(assignment)
    assignments = {key: next(iter(tiers)) if len(tiers := {a['tier'] for a in values}) == 1 else 'Unknown/Unassigned'
                   for key, values in scoped_assignments.items()}
    # Any conflicted cell stays unknown instead of arbitrarily choosing a value.
    for conflict in report['conflicts']:
        assignments.pop((conflict.get('entity_id'), conflict.get('berry')), None)
    by_entity, rels = defaultdict(list), defaultdict(list)
    for record in records:
        for key in set(record.get('entity_ids') or []):
            by_entity[key].append(record)
    for rel in relationships:
        if not real_record(rel):
            continue
        for key in {rel.get('subject_id'), rel.get('object_id')}:
            rels[key].append(rel)
    group_rows = groups(store)
    selected_group = next((g for g in group_rows if g['id'] == params.get('group')), None)
    if params.get('group') and not selected_group:
        raise ValueError('Monitoring group not found; select another group or reset filters')
    berry = params.get('berry', '')
    if berry and berry not in BERRIES:
        raise ValueError('Choose a supported berry')
    tier = params.get('tier', '')
    if tier and tier not in TIER_STATUS_VALUES:
        raise ValueError('Choose a supported tier')
    if tier and not berry:
        raise ValueError('Choose a berry when filtering by its tier')
    followed = {w['object_id'] for w in watches if w.get('watch_type') == 'company'}
    rows = []
    for key, entity in entities.items():
        if entity.get('entity_type') not in ENTITY_TYPES and key not in tier_rows:
            continue
        tier_row = tier_rows.get(key, {})
        linked = by_entity[key]
        linked_rels = rels[key]
        geography_ids = set()
        berry_ids = set(entity.get('berry_ids') or [])
        for ev in linked:
            geography_ids.update(ev.get('geography_ids') or [])
            geography_ids.update(x for x in ev.get('entity_ids', []) if entities.get(x, {}).get('entity_type') == 'geography')
            berry_ids.update(ev.get('berry_ids') or [])
        for rel in linked_rels:
            other_id = rel.get('object_id') if rel.get('subject_id') == key else rel.get('subject_id')
            if entities.get(other_id, {}).get('entity_type') == 'geography' and rel.get('status') == 'active':
                geography_ids.add(other_id)
            if rel.get('status') == 'active':
                berry_ids.update(rel.get('berry_ids') or [])
        geographies = [entities[x] for x in sorted(geography_ids) if x in entities]
        regions = sorted({geography_region(g) for g in geographies} - {None})
        # Imported regions are monitoring scope, kept separate from observed geography.
        monitoring_regions = sorted({region for assignment in report['assignments'] if assignment['entity_id'] == key
                                     for region in assignment['regions']}) or tier_row.get('regions') or []
        current_tier = assignments.get((key, berry), 'Unknown/Unassigned') if berry else 'Select a berry'
        linked.sort(key=lambda ev: (ev.get('published_date') or '', ev['id']), reverse=True)
        row_assessments = [a for a in assessments if key in (a.get('entity_ids') or []) and real_record(a)
                           and (not berry or not a.get('market_ids') or 'berry-' + berry in a['market_ids'])]
        row = {'id': key, 'name': entity['name'], 'entity': entity, 'tier': current_tier,
            'tiers': {b: assignments.get((key, b), 'Unknown/Unassigned') for b in BERRIES},
            'tier_details': [a for a in report['assignments'] if a['entity_id'] == key],
            'roles': entity.get('roles') or [entity.get('entity_type', 'Organization')],
            'berries': sorted(berry_ids), 'regions': regions, 'monitoring_regions': monitoring_regions,
            'geographies': geographies, 'evidence': linked, 'assessments': row_assessments,
            'signals': [s for s in signals if key in (s.get('entity_ids') or []) and real_record(s)
                        and (not berry or not s.get('berry_ids') or 'berry-' + berry in s['berry_ids'])],
            'relationships': linked_rels, 'followed': key in followed,
            'monitoring': monitoring_state_for_entity(key, sources=list(sources), inbox_dir=store.inbox),
            'genetic_evidence': [ev for ev in linked if ev.get('patent_filing') or ev.get('cpvo_filing') or ev.get('source_type') in {'patent_record', 'plant_patent', 'government_registry'}],
            'adoption_evidence': [ev for ev in linked if ev.get('commercial_observation')],
            'latest': linked[0] if linked else None,
            'confidence': ' / '.join(sorted({str(a.get('confidence') or 'Unknown') for a in row_assessments})) or 'Insufficient assessed evidence',
            'profile_href': '/entities/' + entity.get('entity_type', 'company') + '/' + key,
            'imported_tier': any(assignments.get((key, b)) in {'Tier 1', 'Tier 2', 'Tier 3'} for b in BERRIES),
            'group_ids': [g['id'] for g in group_rows if key in g['member_ids']]}
        rows.append(row)
    all_rows = sorted(rows, key=lambda r: r['name'].casefold())
    filtered = []
    for row in all_rows:
        if selected_group and row['id'] not in selected_group['member_ids']:
            continue
        if params.get('followed') and not row['followed']:
            continue
        if berry and 'berry-' + berry not in row['berries'] and row['tiers'][berry] in {'Unknown/Unassigned', 'Not Applicable'}:
            continue
        if tier and row['tier'] != tier:
            continue
        region = params.get('region')
        requested_regions = set(str(region or '').split(',')) - {''}
        if requested_regions and not requested_regions.intersection([*row['regions'], *row['monitoring_regions']]):
            continue
        if params.get('priority') and tier_rows.get(row['id'], {}).get('strategic_priority') != params['priority']:
            continue
        if params.get('type') and params['type'] not in str(tier_rows.get(row['id'], {}).get('competitor_type') or ''):
            continue
        if params.get('market') and params['market'] not in {g['id'] for g in row['geographies']}:
            continue
        if params.get('entity') and params['entity'] != row['id']:
            continue
        if params.get('q') and params['q'].casefold().strip() not in ' '.join([row['name'], *row['entity'].get('aliases', [])]).casefold():
            continue
        filtered.append(row)
    filtered.sort(key=lambda r: (not r['followed'], not bool(r['group_ids']), not r['imported_tier'], r['name'].casefold()))
    selected = list(dict.fromkeys(x for x in params.get('compare', '').split(',') if x))
    by_id = {r['id']: r for r in all_rows}
    if len(selected) > 4 or any(x not in by_id for x in selected):
        raise ValueError('Select up to four canonical organizations to compare')
    company = params.get('company', '')
    if company and company not in by_id:
        raise ValueError('Company not found')
    focus = [by_id[company]] if company else [by_id[x] for x in selected]
    focus_ids = {r['id'] for r in focus or filtered}
    news_records = [r for r in records if focus_ids.intersection(r.get('entity_ids') or [])
                    and (not berry or 'berry-' + berry in (r.get('berry_ids') or []))
                    and (not params.get('source_type') or r.get('source_type') == params['source_type'])
                    and (not params.get('event_type') or r.get('event_type') == params['event_type'])
                    and (not params.get('market') or params['market'] in set(r.get('geography_ids') or []) | set(r.get('entity_ids') or []))]
    for record in news_records:
        record['source_url'] = safe_url(record.get('source_url'))
    news = grouped_news(news_records)
    notes = [n for n in store.rows(KINDS['note']) if n['entity_id'] in focus_ids]
    return {'rows': filtered, 'all_rows': all_rows, 'focus': focus, 'selected': selected, 'company': company,
        'entities': entities, 'news': news, 'notes': notes, 'corrections': corrections, 'groups': group_rows,
        'selected_group': selected_group, 'tier_report': report, 'params': params, 'berry_options': BERRIES,
        'tier_options': TIER_STATUS_VALUES, 'region_options': list(dict.fromkeys([*REGIONS, 'DOTA', 'DEMEA', 'DOA_DANZ',
            *[region for row in all_rows for region in row['monitoring_regions']]])),
        'markets': sorted([g for g in entities.values() if g.get('entity_type') == 'geography'], key=lambda g: g['name']),
        'source_types': sorted({r.get('source_type') for r in records if r.get('source_type')}),
        'event_types': sorted({r.get('event_type') for r in records if isinstance(r.get('event_type'), str) and r['event_type']}),
        'corpus_count': len(all_rows), 'record_count': len(news_records), 'exported_at': now(),
        'data_note': 'Captured coverage, not market share or competitive strength. Missing evidence is unknown. No live feed connection is implied.'}
