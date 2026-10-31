"""Private scoped comparison and a reusable full captured-archive view."""
from __future__ import annotations

import csv
from contextlib import closing
import io
import json
import re
from datetime import date
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, Response, RedirectResponse

from app.personal_digest_routes import world, require_edit
from app.services import competitive_evaluation as ce, competitive_feed as feed, news_tags
from app.services.living_workspaces import Store, Conflict, digest

router = APIRouter()


def request_params(request):
    params = dict(request.query_params)
    for key in ('companies','berry','tags'):
        if key in request.query_params:
            params[key] = ','.join(dict.fromkeys(part for value in request.query_params.getlist(key) for part in feed.values(value)))
    return params


def private(request, mutate=False):
    from app import main
    if not main.AUTHORING_MODE:
        raise HTTPException(403, 'Competitive research requires the private analyst workspace')
    if mutate:
        require_edit(request)
    return main, Store(main.INBOX_DIR), main.session_username(request) or main.review_username() or 'local analyst'


def comparison(main, store, params):
    entities = {r['id']: r for r in main.all_entities()}
    selected = feed.values(params.get('companies'))
    if any(key not in entities for key in selected):
        raise ValueError('Choose canonical entities')
    role = params.get('role', '')
    if role and role not in {'breeder', 'grower', 'marketer', 'technology_provider'}:
        raise ValueError('Choose a peer role')
    with closing(store.connect()) as db:
        db.execute('BEGIN')
        records = store.rows('competitive_record', db)
        effective = [ce.effective_assessment(store, r, db) for r in store.rows('capability_automatic', db)]
        batch_history = store.rows('competitive_batch', db)
        saved_comparisons = store.rows('competitive_comparison', db)
    for row in records:
        if row['kind'] == 'source':
            row['safe_original_url'] = ce.safe_original_url(row['fields'].get('original_url'))
            try:
                row['publication_age_days'] = (date.today()-date.fromisoformat(str(row['fields'].get('published_date') or '')[:10])).days
            except ValueError:
                row['publication_age_days'] = None
    relevant = [r for r in records if not selected or r.get('entity_id') in selected]
    if params.get('berry'):
        def crop_matches(row):
            fields = row['fields']
            raw = ' '.join(str(fields.get(k) or '') for k in ('berry_scope','crop_program_scope','berry_market_program_scope'))
            explicit = set(re.findall(r'berry-(?:blueberry|strawberry|raspberry|blackberry)\b', raw))
            return not explicit or bool(set(feed.values(params['berry'])).intersection(explicit))
        relevant = [r for r in relevant if crop_matches(r)]
    for r in relevant:
        r['sources'] = ce.record_sources(r, records)
        observed = r['fields'].get('last_observed_date') or r['fields'].get('observed_date') or ''
        try:
            r['age_days'] = (date.today() - date.fromisoformat(observed[:10])).days
        except ValueError:
            r['age_days'] = None
        r['review_after_days'] = 30 if r['kind'] == 'job' else 730 if r['kind'] == 'relationship' else 180
    assessments = [r for r in effective
                   if (not selected or r['entity_id'] in selected)
                   and (not role or r['peer_role'] == role)
                   and (not params.get('berry') or r['berry_id'] in feed.values(params['berry']))
                   and (not params.get('destination') or r['destination_scope'] == params['destination'])]
    capabilities = {c['capability_id']:c for c in ce.catalogue()['capabilities']}
    held_scope_count = sum(a['peer_role'] not in capabilities[a['capability_id']]['eligible_peer_roles'] for a in assessments)
    assessments = [a for a in assessments if a['peer_role'] in capabilities[a['capability_id']]['eligible_peer_roles']]
    for a in assessments:
        a['capability_label'] = capabilities[a['capability_id']]['label']
        a['age_days'] = (date.today() - date.fromisoformat(a['assessed_at'])).days
        a['stale'] = a['age_days'] > 180
        a['effective_label'] = ('Unknown' if a['rating'] == 'unknown' else 'Not applicable' if a['rating'] == 'not_applicable'
                                else next(x['label'] for c in ce.catalogue()['capabilities'] if c['capability_id'] == a['capability_id'] for x in c['anchors'] if x['level'] == a['rating']))
    eligible = len(selected) if selected else len({a['entity_id'] for a in assessments})
    positions = ce.peer_positions(assessments, eligible)
    by_id = {r['id']: r for r in records}
    for a in assessments:
        a['observations'] = [by_id[key] for key in a.get('observation_ids', []) if key in by_id]
        a['sources'] = list({s['id']: s for obs in a['observations'] for s in ce.record_sources(obs, records)}.values())
        a['position'] = positions.get(a['id'])
        a['access_models'] = []
        for obs in records:
            f = obs['fields']
            value = f.get('access_control_model')
            if obs['kind'] != 'observation' or obs['resolution'] != 'accepted_structure' or not value or str(value).casefold() == 'unknown':
                continue
            if obs.get('entity_id') != a['entity_id'] or f.get('berry_scope') != a['berry_id']:
                continue
            matches = all((f.get(raw) or 'Unknown') == a[field] for field, raw in
                          [('destination_scope','destination_scope'),('origin_scope','origin_scope'),
                           ('program_or_variety','program_or_variety'),('period_start','period_start'),('period_end','period_end'),
                           ('use_system','production_system_fresh_processing')])
            if matches:
                a['access_models'].append({'value':value,'claim_status':f.get('fact_claim_plan_interpretation','unverified research'),
                                           'record_id':obs['id'], 'source_ids':obs['source_refs']})
    graph = []
    for r in main.all_relationships():
        if params.get('berry') and r.get('berry_ids') and not set(feed.values(params['berry'])).intersection(r['berry_ids']):
            continue
        if not selected or r.get('subject_id') in selected or r.get('object_id') in selected:
            graph.append({'id': r['id'], 'subject': r.get('subject_id'), 'object': r.get('object_id'),
                          'predicate': r.get('predicate'), 'status': r.get('status', 'Unknown'),
                          'basis': 'Existing canonical relationship; inspect its Evidence',
                          'hypothesis': r.get('status') in {'hypothesis', 'proposed'}, 'sources': r.get('evidence_ids', []),
                          'scope': {k:r.get(k) or 'Unknown' for k in ('berry_ids','effective_date','start_date','end_date','origin_scope','destination_scope','rights_territory','notes')}})
    for r in relevant:
        if r['kind'] == 'relationship':
            f = r['fields']
            graph.append({'id': r['id'], 'subject': str(f.get('subject_entity_id') or 'Unknown'),
                          'object': str(f.get('object_entity_id_or_proposed_name') or 'Unknown'), 'predicate': str(f.get('predicate') or 'Unknown'),
                          'status': f.get('fact_claim_hypothesis', 'unverified research'),
                          'basis': r['batch_id']+' / '+r['local_id']+' · '+r['resolution'], 'hypothesis': True,
                          'sources': [s['fields'].get('original_url') for s in r['sources']],
                          'scope': {k:f.get(k, 'Unknown') for k in ('berry_scope','origin_scope','destination_scope','rights_territory','start_date','end_date')}})
    inventory = json.loads((ce.ROOT / 'data/imports/competitive-landscape-2026-10-30-v1/commercial-entity-inventory.json').read_text(encoding='utf-8'))
    inventory_ids = {r['entity_id'] for r in inventory['entities'] if r['inclusion_status'] != 'out_of_scope'}
    entity_choices = sorted([row for key,row in entities.items() if key in inventory_ids or key in selected], key=lambda row:row.get('name','').casefold())
    latest_batches = {}
    for batch in batch_history:
        if batch['batch_id'] not in latest_batches or batch['updated_at'] > latest_batches[batch['batch_id']]['updated_at']:
            latest_batches[batch['batch_id']] = batch
    today = date.today()
    try:
        default_start = today.replace(year=today.year-2)
    except ValueError:
        default_start = today.replace(year=today.year-2, day=28)
    events_after = date.fromisoformat(params.get('events_after') or default_start.isoformat())
    people_query = str(params.get('people_q') or '').strip().casefold()
    people_rows, timeline = [], []
    jobs = ce.job_groups(relevant)
    if people_query:
        jobs = [job for job in jobs if people_query in json.dumps(job['latest']['fields'],ensure_ascii=False).casefold()]
    for r in relevant:
        if r['kind'] not in {'person', 'hiring_event'} or (people_query and people_query not in json.dumps(r['fields'],ensure_ascii=False).casefold()):
            continue
        if r['kind'] == 'hiring_event':
            f = r['fields']
            event_day, date_basis = None, 'Event date unknown; observation date is separate'
            for field in ('effective_date', 'announced_date', 'event_date'):
                try:
                    event_day = date.fromisoformat(str(f.get(field) or '')[:10])
                    date_basis = field+'; observation date is separate'
                    break
                except ValueError:
                    continue
            if event_day and event_day < events_after:
                continue
            timeline.append({**r, 'timeline_date': event_day.isoformat() if event_day else 'Unknown',
                             'timeline_basis': date_basis})
        people_rows.append(r)
    timeline.sort(key=lambda r: '' if r['timeline_date']=='Unknown' else r['timeline_date'], reverse=True)
    return {'entities': entities, 'inventory_ids': inventory_ids, 'entity_choices':entity_choices, 'selected': selected, 'assessments': assessments,
            'records': relevant, 'jobs': jobs, 'rubrics': ce.catalogue(), 'graph': graph,
            'people_rows': people_rows, 'timeline': timeline, 'events_after': events_after.isoformat(),
            'batches': list(latest_batches.values()), 'batch_revision_count': len(batch_history), 'saved': saved_comparisons,
            'scope': dict(params), 'assessment_count': len(assessments), 'held_scope_count': held_scope_count,
            'numeric_count': sum(isinstance(a['rating'], int) for a in assessments),
            'destinations': sorted({a['destination_scope'] for a in effective}),
            'captured_at': date.today().isoformat()}


@router.get('/competitive-evaluation', response_class=HTMLResponse)
def evaluation(request: Request):
    main, store, _ = private(request)
    params = request_params(request)
    view = request.query_params.get('view', 'matrix')
    if view not in {'matrix','overview','plot','relationships','exposure','people','imports','saved'}:
        raise HTTPException(422, 'Choose a comparison view')
    try:
        saved = store.get(request.query_params.get('saved', '')) if request.query_params.get('saved') else None
        if request.query_params.get('saved') and (not saved or not saved.get('snapshot')):
            raise HTTPException(404, 'Saved comparison not found')
        model = comparison(main, store, saved['snapshot']['scope'] if saved else params)
        if saved:
            model.update(saved['snapshot'], snapshot_id=saved['id'], snapshot_title=saved['title'])
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    from app.services.workspace_landscapes import panel
    try:
        matrix_page = max(1,int(params.get('matrix_page') or 1))
    except ValueError as exc:
        raise HTTPException(422,'Choose a numbered matrix page') from exc
    matrix_pages = max(1,(len(model['assessments'])+23)//24)
    matrix_page = min(matrix_page,matrix_pages)
    display_assessments = model['assessments'][(matrix_page-1)*24:matrix_page*24]
    plot_fields = (*ce.SCOPE,'id','rating','confidence','status','access_models')
    plot_assessments = [{**{k:a.get(k) for k in plot_fields},'entity_name':model['entities'].get(a['entity_id'],{}).get('name',a['entity_id'])} for a in model['assessments']]
    return main.templates.TemplateResponse(request=request, name='competitive_evaluation.html', context={
        **model, 'authoring_mode': True, 'static_build': False,
        'display_assessments':display_assessments,'plot_assessments':plot_assessments,
        'matrix_page':matrix_page,'matrix_pages':matrix_pages,
        'matrix_previous':'/competitive-evaluation?'+urlencode({**params,'view':'matrix','matrix_page':max(1,matrix_page-1)}),
        'matrix_next':'/competitive-evaluation?'+urlencode({**params,'view':'matrix','matrix_page':matrix_page+1}),
        **panel(main, saved['id'] if saved else None),
        'view': view,
        'query': urlencode({k: v for k, v in params.items() if k != 'view'})})


@router.post('/competitive-evaluation/decision')
async def decision(request: Request):
    main, _, actor = private(request, True)
    form = await request.form()
    rating = str(form.get('rating') or 'unknown')
    try:
        corrected_scope = {field: str(form.get('correct_' + field) or '') for field in
            ('berry_id', 'destination_scope', 'origin_scope', 'program_or_variety', 'period_start', 'period_end', 'use_system')} if form.get('scope_change') == '1' else None
        ce.correct_assessment(main.INBOX_DIR, assessment_id=str(form.get('assessment_id')),
            expected_version=int(form.get('version') or 0), mode=str(form.get('mode')),
            rating=int(rating) if rating.isdigit() else rating,
            rationale=str(form.get('rationale') or ''), actor=actor, corrected_scope=corrected_scope)
    except Conflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return RedirectResponse('/competitive-evaluation?' + str(form.get('return_query') or ''), status_code=303)


@router.get('/competitive-evaluation/history/{assessment_id}')
def history(request: Request, assessment_id: str):
    _, store, _ = private(request)
    if not assessment_id.startswith('capability-') or not store.get(assessment_id):
        raise HTTPException(404, 'Assessment not found')
    return {'automatic': store.history(assessment_id), 'analyst': store.history('decision-'+assessment_id)}


@router.post('/competitive-evaluation/save')
async def save(request: Request):
    main, store, actor = private(request, True)
    form = await request.form()
    try:
        params = json.loads(str(form.get('scope') or '{}'))
        if not isinstance(params, dict):
            raise ValueError('Comparison scope must be an object')
        model = comparison(main, store, params)
        snapshot = {k: model[k] for k in ('scope', 'selected', 'assessments', 'captured_at', 'rubrics', 'records', 'jobs', 'graph', 'people_rows', 'timeline', 'events_after', 'assessment_count', 'numeric_count')}
        key = 'comparison-' + digest([str(form.get('title') or 'Comparison'), snapshot, str(form.get('narrative') or '')])[:28]
        with store.transaction() as db:
            if not store.get(key, db):
                store.put(db, 'competitive_comparison', {'id': key, 'title': str(form.get('title') or 'Comparison'),
                    'snapshot': snapshot, 'narrative': str(form.get('narrative') or ''),
                    'source_policy': 'Only cited cell evidence; refreshing feeds does not change this snapshot'}, actor)
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return RedirectResponse('/competitive-evaluation?view=saved', status_code=303)


@router.get('/competitive-evaluation/export/{format}')
def export(request: Request, format: str):
    main, store, _ = private(request)
    saved = store.get(request.query_params.get('saved', '')) if request.query_params.get('saved') else None
    if request.query_params.get('saved') and (not saved or 'snapshot' not in saved):
        raise HTTPException(404, 'Saved comparison not found')
    if saved:
        model = saved['snapshot']
    else:
        live = comparison(main, store, request_params(request))
        model = {k:live[k] for k in ('scope','selected','assessments','captured_at','rubrics','records','jobs','graph','people_rows','timeline','events_after','assessment_count','numeric_count')}
    if format == 'json':
        return Response(json.dumps(model, ensure_ascii=False, indent=2, default=str), media_type='application/json',
                        headers={'Content-Disposition': 'attachment; filename="competitive-comparison.json"'})
    if format != 'csv':
        raise HTTPException(404, 'Choose JSON or CSV')
    out = io.StringIO()
    fields = [*ce.SCOPE, 'rating', 'effective_label', 'status', 'confidence', 'assessed_at', 'rationale', 'sources']
    writer = csv.DictWriter(out, fieldnames=fields, extrasaction='ignore')
    writer.writeheader()
    for a in model['assessments']:
        row = {**a, 'sources': '; '.join(s['fields'].get('original_url', '') for s in a.get('sources', []))}
        # Spreadsheet formula injection protection for exported source text.
        writer.writerow({k: "'"+str(v) if str(v).startswith(('=', '+', '-', '@')) else v for k, v in row.items()})
    return Response(out.getvalue(), media_type='text/csv', headers={'Content-Disposition': 'attachment; filename="competitive-comparison.csv"'})


@router.get('/coverage/archive', response_class=HTMLResponse)
def archive(request: Request):
    try:
        main, context, records, entities = world()
    except (OSError, ValueError):
        return HTMLResponse('<h1>Captured coverage unavailable</h1><p>Retrieval failed. Retry this view; no empty result has been inferred.</p>', status_code=503)
    params = request_params(request)
    try:
        tags = news_tags.catalog(main.INBOX_DIR) if main.AUTHORING_MODE else []
        automatic, overrides = news_tags.snapshot(main.INBOX_DIR) if main.AUTHORING_MODE else ({}, {})
        tag_map = {key: news_tags.effective(r, tags, automatic, overrides) for key, r in records.items()}
        model = feed.select(records, params, relationships=main.all_relationships(), tag_map=tag_map, entities=entities)
        from app.services.feed_first import safe_image_url
        for record in model['items']:
            record['preview_image'] = safe_image_url(record)
            if not str(record.get('source_url') or '').startswith(('https://', 'http://')):
                record['source_url'] = ''
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    query = {k: v for k, v in params.items() if k != 'page'}
    from app.services.berries.landscape import SEED_FIXTURE_ENTITY_IDS
    feed_entities = {key:row for key,row in entities.items() if key not in SEED_FIXTURE_ENTITY_IDS}
    entity_choices = sorted([row for row in feed_entities.values() if row.get('entity_type') in {'company','brand','breeding_program','retailer'}], key=lambda row:row.get('name','').casefold())
    return main.templates.TemplateResponse(request=request, name='competitive_archive.html', context={
        **model, 'entities': feed_entities, 'entity_choices':entity_choices, 'tags': tags, 'authoring_mode': main.AUTHORING_MODE, 'static_build': False,
        'index_issues': context.get('pending_source_issue_count', 0), 'params': params,
        'prev': '/coverage/archive?' + urlencode({**query, 'page': max(1, model['page']-1)}),
        'next': '/coverage/archive?' + urlencode({**query, 'page': model['page']+1}),
        'berry_choices': {'berry-'+b: b.title() for b in ('blueberry', 'strawberry', 'raspberry', 'blackberry')}})
