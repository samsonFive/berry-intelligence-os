"""Protected unified Global Watchlist; public static builds never call these routes."""
from urllib.parse import urlencode, urlsplit

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, Response

from app.competitive_routes import private, comparison
from app.services import global_watchlist as gw
from app.services import landscape_workspace as landscapes
from app.services.living_workspaces import Conflict
from app.services.watchlist import load_watches, add_watch, remove_watch

router = APIRouter()


def model(request, supplied_params=None):
    main, store, actor = private(request)
    params = dict(request.query_params) if supplied_params is None else dict(supplied_params)
    if supplied_params is None and request.query_params.getlist('region'):
        params['region'] = ','.join(request.query_params.getlist('region'))
    try:
        saved = landscapes.load_views(main.INBOX_DIR)['views']
        selected_view = saved.get(params.get('saved_view', ''))
        if params.get('saved_view'):
            if not selected_view or selected_view.get('surface') != 'watchlist' or selected_view['archived']:
                raise ValueError('Saved watchlist landscape is unavailable or archived')
            params = {**landscapes.watchlist_scope(selected_view), **params}
        result = gw.build(entities=main.all_entities(), evidence=main.published_evidence(),
            relationships=main.all_relationships(), signals=main.all_signals(), assessments=main.all_assessments(),
            data_dir=main.DATA_DIR, store=store, watches=load_watches(main.INBOX_DIR), params=params, sources=main.load_sources())
        result['selected_saved_view'] = selected_view
        result['saved_watchlist_views'] = [{**row, 'href': landscapes.view_href(row)} for row in saved.values()
            if row.get('surface') == 'watchlist' and not row['archived']]
        result['archived_watchlist_views'] = [row for row in saved.values() if row.get('surface') == 'watchlist' and row['archived']]
        result['watchlist_fields'] = landscapes.WATCHLIST_FIELDS
        # Reuse the already-governed capability framework and source trace.
        selected = [r['id'] for r in result['focus']]
        result['capabilities'] = comparison(main, store, {'companies': ','.join(selected),
            'berry': 'berry-' + params['berry'] if params.get('berry') else ''}) if selected else None
        if result['capabilities']:
            result['capabilities']['assessments'] = [a for a in result['capabilities']['assessments']
                if gw.real_record(a) and all(gw.real_record(o) and gw.real_record(o.get('fields', {})) for o in a.get('observations', []))
                and all(gw.real_record(s) and gw.real_record(s.get('fields', {})) for s in a.get('sources', []))]
            result['capabilities']['records'] = [r for r in result['capabilities'].get('records', [])
                if gw.real_record(r) and gw.real_record(r.get('fields', {}))]
        from app.services.competitive_record_sheet import build as record_sheet
        result['people'] = record_sheet(result['capabilities'], 'people', {})['all_rows'] if result['capabilities'] and result['capabilities'].get('records') else []
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    query = urlencode(params)
    result['return_to'] = '/global-watchlist' + ('?' + query if query else '')
    result['export_href'] = '/global-watchlist/export.pdf' + ('?' + query if query else '')
    clear_keys = {'company'} if result['company'] and result['selected'] else {'company', 'compare'}
    result['browse_href'] = '/global-watchlist?' + urlencode({k: v for k, v in params.items() if k not in clear_keys})
    for row in result['all_rows']:
        row['href'] = '/global-watchlist?' + urlencode({**params, 'company': row['id']})
    result['letter_urls'] = {letter: '/global-watchlist?' + urlencode({
        **{k: v for k, v in params.items() if k != 'letter'}, **({'letter': letter} if letter else {})
    }) + '#gw-results' for letter in ['', *'ABCDEFGHIJKLMNOPQRSTUVWXYZ#']}
    return main, store, actor, result


@router.get('/global-watchlist')
def page(request: Request):
    main, _, _, result = model(request)
    from app.services import feed_first, news_workspace
    from app.services.company_source_scope import source_reviewed
    state = feed_first.load_state(main.INBOX_DIR)
    support = news_workspace.escalations(main.all_facts())
    cards = []
    for story in result['news'][:30]:
        card = feed_first.present_item(story['lead'], entities_by_id=result['entities'],
            state=state, filters=feed_first.parse_filters({}))
        card.update(source_reviewed=source_reviewed(story['lead']),
            trusted=source_reviewed(story['lead']) and card['id'] in support,
            coverage_sources=story['sources'], independence=story['independence'])
        cards.append(card)
    return main.templates.TemplateResponse(request=request, name='global_watchlist.html', context={
        **result, 'cards': cards, 'scoped_news': True, 'authoring_mode': True, 'static_build': False, 'nav_work_counts': {}})


@router.get('/global-watchlist/export.pdf')
def export_pdf(request: Request):
    _, _, _, result = model(request)
    from app.services.global_watchlist_pdf import render
    return Response(render(result), media_type='application/pdf', headers={
        'Content-Disposition': 'attachment; filename="global-watchlist.pdf"', 'Cache-Control': 'no-store'})


@router.post('/global-watchlist/views')
async def save_view(request: Request):
    main, _, _ = private(request, mutate=True)
    form = dict(await request.form())
    action = form.get('action', 'save')
    if action not in {'save', 'copy', 'archive', 'restore'}:
        raise HTTPException(422, 'Choose a supported saved-landscape action')
    key = form.get('view_id', '')
    try:
        if action in {'archive', 'restore'}:
            old = landscapes.load_views(main.INBOX_DIR)['views'].get(key)
            if not old or old.get('surface') != 'watchlist':
                raise ValueError('Saved watchlist landscape is unavailable')
            name, filters = old['name'], old['filters']
        else:
            params = {field: form.get(field, '') for field in landscapes.WATCHLIST_FIELDS}
            _, _, _, projection = model(request, params)
            filters = {field: projection['params'].get(field, '') for field in landscapes.WATCHLIST_FIELDS}
            if filters.get('berry'):
                filters['berry'] = 'berry-' + filters['berry']
            name = form.get('name', '')
        row = landscapes.save_view(main.INBOX_DIR, name=name, filters=filters,
            view_id='' if action == 'copy' else key, revision='0' if action == 'copy' else form.get('revision', '0'),
            archive=action == 'archive', kind='overview' if action in {'save', 'copy'} else None, surface='watchlist')
    except ValueError as exc:
        raise HTTPException(409 if 'another window' in str(exc) else 422, str(exc)) from exc
    return RedirectResponse('/global-watchlist' if action == 'archive' else landscapes.view_href(row), status_code=303)


def destination(value):
    parts = urlsplit(str(value or ''))
    return str(value) if not parts.scheme and not parts.netloc and parts.path == '/global-watchlist' else '/global-watchlist'


@router.post('/global-watchlist/actions')
async def actions(request: Request):
    main, store, actor = private(request, mutate=True)
    form = dict(await request.form())
    entities = {r['id']: r for r in main.all_entities()}
    try:
        action = form.get('action')
        if action in {'create', 'rename', 'delete', 'add', 'remove'}:
            result = gw.edit_group(store, actor=actor, action=action, name=form.get('name', ''),
                group_id=form.get('group_id', ''), entity_id=form.get('entity_id', ''),
                version=form.get('version', 0), entities=entities)
            if action == 'create':
                return RedirectResponse('/global-watchlist?' + urlencode({'group': result['id']}), status_code=303)
            if action == 'delete':
                return RedirectResponse('/global-watchlist', status_code=303)
        elif action in {'follow', 'unfollow'}:
            key = form.get('entity_id')
            if key not in entities or entities[key].get('entity_type') not in gw.ENTITY_TYPES:
                raise ValueError('Choose a canonical organization')
            (add_watch if action == 'follow' else remove_watch)(main.INBOX_DIR, 'company', key)
        elif action == 'note':
            gw.add_note(store, actor=actor, entity_id=form.get('entity_id'), classification=form.get('classification'),
                text=form.get('text', ''), observed_at=form.get('observed_at', ''), reference=form.get('reference', ''), entities=entities)
        elif action == 'correct':
            gw.correct_association(store, actor=actor, record_id=form.get('record_id'), field=form.get('field'),
                entity_id=form.get('entity_id'), action=form.get('association_action'), reason=form.get('reason', ''),
                version=form.get('version', 0), entities=entities, evidence={r['id']: r for r in main.published_evidence()})
        else:
            raise ValueError('Choose a supported action')
    except Conflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return RedirectResponse(destination(form.get('return_to')), status_code=303)
