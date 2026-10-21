"""Evidence-backed Gene Editing lens and deterministic, reviewable topic tags.

Monitoring membership never participates in classification. Research snapshots
retain source claims, not Facts; only the analyst Explorer reads this lens.
"""
import csv
from copy import deepcopy
from html import escape
from io import StringIO
import json
from pathlib import Path
import re
from urllib.parse import urlencode

VERSION = 'gene-editing-1'
TOPICS = {'gene-editing': 'Gene Editing', 'advanced-breeding': 'Advanced Breeding'}
EDIT = re.compile(r'\b(?:gene[ -]edit\w*|genome[ -]edit\w*|crispr(?:[ -]cas\w*)?|base editing|prime editing|targeted mutagenesis)\b|基因编辑|基因編輯|ゲノム編集|édition génomique|edición genética', re.I)
AG = re.compile(r'\b(?:plant\w*|agricultur\w*|crop\w*|breeding|germplasm|strawberr\w*|blueberr\w*|raspberr\w*|blackberr\w*|potato\w*|tomato\w*|rice|maize|corn|wheat|soybean\w*)\b|植物|作物|育种|草莓|蓝莓|水稻', re.I)
MED = re.compile(r'\b(?:patient\w*|clinical|cancer|human|therapy|therapeutic\w*|sickle.cell)\b', re.I)
CONTEXTUAL = re.compile(r'\b(?:NGT|NBT|precision breeding)\b', re.I)
ADVANCED = re.compile(r'\b(?:boosted breeding|advanced breeding|marker.assisted (?:selection|breeding)|genomic selection|AI.driven (?:predictive )?breeding)\b', re.I)
BERRY = re.compile(r'\b(?:strawberr\w*|blueberr\w*|raspberr\w*|blackberr\w*|berries)\b|草莓|蓝莓|树莓|黑莓', re.I)
NEGATED = re.compile(r'not established|does not establish|no (?:credible )?evidence|editing (?:is )?(?:unknown|unverified)|without (?:using )?(?:crispr|gene.editing)', re.I)


def classify(record):
    stored = record.get('classification') or {}
    if stored.get('reviewed_by') or stored.get('origin') == 'analyst':
        return {'version': VERSION, 'topics': [], 'berry_related': False, 'relevance': '',
                'reason': 'Analyst correction', 'excerpt': '', **stored}
    text = ' '.join(str(record.get(key) or '') for key in ('title', 'summary', 'supporting_excerpt'))
    # A medical sentence cannot borrow agricultural context from a different one.
    sentences = re.split(r'(?<=[.!?。])\s+|\n', text)
    editing = next((s for s in sentences if AG.search(s) and not MED.search(s) and not NEGATED.search(s) and
                    (EDIT.search(s) or (CONTEXTUAL.search(s) and re.search(r'edit|mutagen|regulat|基因', s, re.I)))), '')
    advanced = next((s for s in sentences if AG.search(s) and not MED.search(s) and ADVANCED.search(s)), '')
    topics = (['gene-editing'] if editing else []) + (['advanced-breeding'] if advanced else [])
    exclusions = {str(tag).removeprefix('topic-exclude-') for tag in record.get('tags', []) if str(tag).startswith('topic-exclude-')}
    topics = [key for key in topics if key not in exclusions]
    excerpt = editing or advanced
    berry = bool(BERRY.search(excerpt))
    label = ('Policy / IP' if re.search(r'licens|patent|regulat|legislation|许可|专利', excerpt, re.I) else
             'Enabling plant technology' if re.search(r'platform|tool|design|delivery|regenerat|workflow|system|工具|平台', excerpt, re.I) else
             'Direct berry development' if berry else
             'Adjacent crop signal') if topics else ''
    return {'version': VERSION, 'topics': topics, 'relevance': label, 'berry_related': berry,
            'reason': 'Explicit agricultural ' + ('editing' if editing else 'advanced breeding') + ' language' if topics else '',
            'excerpt': str(record.get('supporting_excerpt') or excerpt)[:700],
            'excerpt_kind': 'source_excerpt' if record.get('supporting_excerpt') else 'metadata_context',
            'provenance': 'deterministic title/summary/excerpt; company membership excluded; analyst exclusion tags honored'}


def topic_selection(params):
    raw = params.getlist('topic') if hasattr(params, 'getlist') else [params.get('topic', '')]
    values = sorted({part for value in raw for part in str(value).split(',') if part})
    if set(values) - set(TOPICS):
        raise ValueError('Choose Gene Editing or Advanced Breeding')
    return values


def load_snapshot(data_dir):
    paths = sorted((Path(data_dir)/'imports').glob('gene-editing-*/snapshot.json'))
    return json.loads(paths[-1].read_text(encoding='utf-8')) if paths else {'companies': [], 'programs': [], 'relationships': []}


def landscape_model(data_dir, entities, records, params, *, evidence_aliases=None):
    snapshot = load_snapshot(data_dir)
    from app.services.feed_first_reader import is_public_http_url
    fields = ('crop', 'role', 'technology', 'trait', 'geography', 'stage', 'verification', 'company', 'adjacent')
    filters = {key: str(params.get(key) or '') for key in fields}
    sources = {r['id']: {**r, 'source_url': r.get('source_url') if is_public_http_url(r.get('source_url') or '') else ''}
               for r in records if r.get('id') and r.get('status') not in {'rejected', 'archived'}
               and r.get('review_state') not in {'rejected', 'archived'}}
    for key, target in (evidence_aliases or {}).items():
        if target in sources:
            sources.setdefault(key, sources[target])
    companies = []
    program_rows = []
    for profile in snapshot['companies']:
        entity = entities.get(profile['entity_id'])
        if not entity:
            continue
        row = deepcopy(profile)
        row['name'] = entity['name']
        row['programs'] = []
        if filters['company'] and filters['company'] != entity['id']:
            continue
        for original in snapshot['programs']:
            # Analyst edits on the native program record supersede the snapshot.
            program = {**original, **((entities.get(original['id']) or {}).get('attributes', {}).get('gene_editing') or {})}
            if entity['id'] not in program['company_ids']:
                continue
            if not filters['adjacent'] and not program.get('berry_ids'):
                continue
            p = deepcopy(program)
            p['sources'] = [sources[key] for key in p['evidence_ids'] if key in sources]
            if not p['sources']:
                p['verification'] = 'evidence gap / source unavailable or rejected'
            elif any(s.get('verification_state') == 'disputed' for s in p['sources']):
                p['verification'] = 'disputed source / claim requires review'
            if any(filters[key] and filters[key].casefold() not in str(p.get(key) or '').casefold()
                   for key in ('crop', 'role', 'technology', 'trait', 'geography', 'stage', 'verification')):
                continue
            p['company'] = entity['name']
            p['entity_id'] = entity['id']
            p['company_names'] = ' / '.join(entities[key]['name'] for key in p['company_ids'] if key in entities)
            row['programs'].append(p)
            program_rows.append(p)
        row['sources'] = [sources[key] for key in row.get('evidence_ids', []) if key in sources]
        companies.append(row)
    selected_programs = {p['id'] for p in program_rows}
    company_ids = {c['entity_id'] for c in companies}
    relationships = []
    for relation in snapshot['relationships']:
        if not selected_programs.intersection(relation.get('program_ids', [])):
            continue
        endpoints = {relation['subject_id'], relation['object_id']}
        if not endpoints.intersection(company_ids) or not endpoints <= entities.keys():
            continue
        linked = [sources[key] for key in relation['evidence_ids'] if key in sources]
        if linked:
            relationships.append({**relation, 'sources': linked,
                                  'verification': 'disputed source / relationship requires review' if any(s.get('verification_state') == 'disputed' for s in linked) else relation['verification'],
                                  'subject': entities[relation['subject_id']]['name'],
                                  'object': entities[relation['object_id']]['name']})
    query = urlencode({'topic': 'gene-editing', **filters})
    return {'title': 'Gene Editing & Advanced Breeding', 'companies': companies, 'programs': program_rows,
            'company_choices': [{'id':c['entity_id'], 'name':entities[c['entity_id']]['name']} for c in snapshot['companies'] if c['entity_id'] in entities],
            'relationships': relationships, 'filters': filters, 'query': query,
            'version': snapshot.get('version', VERSION), 'research_date': snapshot.get('research_date'),
            'research_status': snapshot.get('research_status', ''),
            'counts': {'companies': len(companies), 'programs': len(selected_programs),
                       'relationships': len(relationships), 'sources': len({s['id'] for c in companies for s in c['sources']})}}


EXPORT_FIELDS = ('entity_id', 'company', 'name', 'role', 'technology', 'crop', 'trait', 'partner', 'geography', 'stage', 'milestone_date', 'milestone', 'verification', 'gaps')


def csv_export(model):
    output = StringIO(newline='')
    writer = csv.writer(output)
    writer.writerow([*EXPORT_FIELDS, 'evidence_id', 'source_url', 'publisher', 'published_date', 'access_date', 'supporting_excerpt', 'attribution'])
    for company in model['companies']:
        programs = company['programs'] or [{'entity_id': company['entity_id'], 'company': company['name'], 'gaps': company['gaps']}]
        for program in programs:
            linked = program['sources'] if 'sources' in program else company['sources']
            for source in linked or [{}]:
                cells = [program.get(key) or 'Unknown' for key in EXPORT_FIELDS] + [source.get(key) or '' for key in
                    ('id', 'source_url', 'source_name', 'published_date', 'captured_date', 'supporting_excerpt', 'attribution')]
                writer.writerow(["'"+str(v) if str(v).lstrip().startswith(('=', '+', '-', '@')) else str(v) for v in cells])
    return output.getvalue()


def html_export(model):
    e = lambda value: escape(str(value or 'Unknown'))
    rows = ''.join('<tr>'+''.join('<td>'+e(p.get(k))+'</td>' for k in EXPORT_FIELDS)+
                   '<td>'+''.join('<a href="'+e(s.get('source_url'))+'">'+e(s.get('title'))+'</a><p>'+e(s.get('supporting_excerpt'))+'</p>' for s in p.get('sources', []))+'</td></tr>'
                   for c in model['companies'] for p in (c['programs'] or [{'company':c['name'], 'gaps':c['gaps']}]))
    return '<!doctype html><html lang="en"><meta charset="utf-8"><title>'+e(model['title'])+'</title><h1>'+e(model['title'])+'</h1><p>Source claims awaiting analyst review · research '+e(model['research_date'])+'</p><table border="1"><tr>'+''.join('<th>'+e(k)+'</th>' for k in (*EXPORT_FIELDS, 'Evidence'))+'</tr>'+rows+'</table></html>'
