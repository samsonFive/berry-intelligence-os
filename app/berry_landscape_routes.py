"""Live Global Berry Landscape overview and directly linked crop views."""
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.services import company_directory, global_berry_landscape as landscape
from app.services.global_berry_coverage import public_coverage

router = APIRouter()
PAGE_SIZE = 30


def landscape_href(crop='', query=None):
    path = '/landscapes/global' + (f'/{crop}' if crop else '')
    return path + ('?' + urlencode(query) if query else '')


def context(main, params, crop=''):
    filters = landscape.filters_for(params, crop)
    entities = main.entity_index()
    coverage = public_coverage(main.DATA_DIR, crop=crop, region=filters['region'], role=filters['role'])
    model = landscape.model(entities=entities, companies=company_directory.catalog(entities),
                            relationships=main.all_relationships(), evidence=main.published_evidence(),
                            coverage=coverage, filters=filters)
    query = {key: value for key, value in filters.items() if value and key not in {'crop', 'sort'}}
    return {**model, 'filters': filters, 'query': query}


def _page(model, key, params, path):
    rows = model[key]
    page_key = f'{key}_page'
    try:
        page = int(params.get(page_key) or 1)
    except ValueError:
        page = 1
    pages = max(1, (len(rows) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(pages, max(1, page))
    # Preserve the current page in other sections when paging this one.
    query = {**model['query'], 'sort': model['filters']['sort']}
    query.update({field: params[field] for field in ('companies_page', 'footprint_page', 'relationships_page', 'events_page')
                  if str(params.get(field) or '').isdigit()})
    return {'rows': rows[(page - 1) * PAGE_SIZE:page * PAGE_SIZE], 'total': len(rows), 'number': page, 'pages': pages,
            'previous': f'{path}?{urlencode({**query, page_key: page - 1})}#{key}' if page > 1 else '',
            'next': f'{path}?{urlencode({**query, page_key: page + 1})}#{key}' if page < pages else ''}


@router.get('/landscapes/global', response_class=HTMLResponse)
def global_berry_overview(request: Request):
    return global_berry_landscape(request, '')


@router.get('/landscapes/global/{crop}', response_class=HTMLResponse)
def global_berry_landscape(request: Request, crop: str):
    from app import main

    if crop and crop not in landscape.CROPS:
        raise HTTPException(404, 'Unknown berry')
    try:
        model = context(main, request.query_params, crop)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    path = landscape_href(crop)
    map_query = {'berry': 'berry-' + crop} if crop else {}
    if model['map_geographies']:
        map_query['countries'] = ','.join(model['map_geographies'])
    map_href = '/explorer' + ('?' + urlencode(map_query) if map_query else '')
    tabs = {slug: landscape_href(slug, model['query']) for slug in ('', *landscape.CROPS)}
    pages = {key: _page(model, key, request.query_params, path) for key in ('companies', 'footprint', 'relationships', 'events')}
    strategy = None
    if main.AUTHORING_MODE:
        from app.berry_strategy_routes import panel
        strategy = panel(main, model)
    return main.templates.TemplateResponse(request=request, name='global_berry_landscape.html',
                                           headers={'Cache-Control': 'private, no-store'} if main.AUTHORING_MODE else None, context={
        **model, 'crop': crop, 'tabs': tabs, 'pages': pages, 'path': path, 'map_href': map_href,
        'crops': landscape.CROPS, 'regions': landscape.REGIONS, 'roles': landscape.ROLES,
        'event_types': landscape.EVENT_TYPES, 'footprint_types': landscape.FOOTPRINT_TYPES,
        'directory_sorts': landscape.DIRECTORY_SORTS, 'authoring_mode': main.AUTHORING_MODE,
        'strategy': strategy,
    })
