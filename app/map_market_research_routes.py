"""Explicit country/berry research, progress and human statistical review."""
from urllib.parse import parse_qs, urlencode, urlsplit
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import RedirectResponse
from starlette.concurrency import run_in_threadpool

from app.map_statistics_routes import return_path
from app.personal_digest_routes import require_edit
from app.services import market_reference_research as research
from app.services.ai_gateway.perplexity_deep_research import DeepResearchClient, ResearchError
from app.services.map_statistics_refresh import references
from app.services.market_statistics_reference import group_id, reference_groups

router = APIRouter()
BASE = '/explorer/statistics/research'


def countries():
    from app import main
    rows = [e for e in main.all_entities() if e.get('entity_type') == 'geography'
            and len(str((e.get('attributes') or {}).get('iso_3166_1_alpha_2') or '')) == 2]
    counts = {}
    for row in rows:
        code = row['attributes']['iso_3166_1_alpha_2']
        counts[code] = counts.get(code, 0) + 1
    return {e['id']: e for e in sorted(rows, key=lambda e: e['name'].casefold())
            if counts[e['attributes']['iso_3166_1_alpha_2']] == 1}


def client_factory():
    from app.services.ai_gateway.credentials import MissingCredentialError, resolve_perplexity_api_key
    try:
        return DeepResearchClient(resolve_perplexity_api_key())
    except MissingCredentialError as exc:
        raise ResearchError('Market research is not connected in this workspace. No request was sent.') from exc


def page(request, *, error='', status_code=200, job_id='', return_to=''):
    from app import main
    if not main.AUTHORING_MODE:
        raise HTTPException(403, 'Market research requires the analyst workspace.')
    return_to = return_path(return_to or request.query_params.get('return_to', ''))
    try:
        state = research.load(main.INBOX_DIR)
        current = references(reference_groups(main.DATA_DIR), main.INBOX_DIR, True)
    except ValueError as exc:
        state, current = research.empty(), []
        error, status_code = str(exc), 409
    key = job_id or request.query_params.get('job', '')
    job = state['jobs'].get(key) if key else None
    if key and not job and not error:
        raise HTTPException(404, 'This market research is unavailable.')
    previous = {research.category(g): g for g in current}
    comparisons = [{**g, 'id': group_id(g), 'previous': previous.get(research.category(g))} for g in (job['groups'] if job else [])]
    params = parse_qs(urlsplit(return_to).query)
    country_values = params.get('countries', [''])[0].split(',')
    berry_values = params.get('berry', [''])[0].split(',')
    selected_country = job['scope']['country_id'] if job else (country_values[0] if len(country_values) == 1 else '')
    selected_berry = job['scope']['berry_id'] if job else (berry_values[0] if len(berry_values) == 1 else '')
    jobs = sorted(state['jobs'].values(), key=lambda j: (j['created_at'], j['id']), reverse=True)
    return main.templates.TemplateResponse(request=request, name='market_reference_research.html', status_code=status_code, context={
        'authoring_mode': True, 'static_build': False, 'error': error, 'job': job, 'comparisons': comparisons,
        'status_labels': research.LABELS, 'terminal': research.TERMINAL, 'revision': state['revision'], 'token': uuid4().hex,
        'countries': countries(), 'research_berries': research.BERRIES, 'selected_country': selected_country, 'selected_berry': selected_berry,
        'jobs': jobs, 'history': list(reversed(state['history'])), 'return_to': return_to,
        'review_href': '/explorer/statistics?' + urlencode({'return_to': return_to}),
        'research_href': destination(key, return_to),
        'compared_revision': research.reference_revision(current, job['groups'] if job else []),
        'current': [g for g in current if g['country_id'] == selected_country and g['berry_id'] == selected_berry],
    })


def destination(key, return_to):
    return BASE + '?' + urlencode({'job': key, 'return_to': return_path(return_to)})


@router.get(BASE)
def browse(request: Request):
    return page(request)


@router.post(BASE)
async def start(request: Request, tasks: BackgroundTasks):
    require_edit(request)
    from app import main
    form = await request.form()
    try:
        country = countries().get(str(form.get('country') or ''))
        selected = research.scope(country or {}, str(form.get('berry') or ''))
        references(reference_groups(main.DATA_DIR), main.INBOX_DIR, True)
        job, created = research.reserve(main.INBOX_DIR, selected, str(form.get('token') or ''))
    except ValueError as exc:
        return page(request, error=str(exc), status_code=422, return_to=str(form.get('return_to') or ''))
    if created:
        tasks.add_task(research.submit, main.INBOX_DIR, job['id'], client_factory)
    return RedirectResponse(destination(job['id'], str(form.get('return_to') or '')), status_code=303)


@router.post(BASE + '/{key}/{action}')
async def act(request: Request, key: str, action: str, tasks: BackgroundTasks):
    require_edit(request)
    from app import main
    form = await request.form()
    return_to = str(form.get('return_to') or '')
    try:
        state = research.load(main.INBOX_DIR)
        job = state['jobs'].get(key)
        if not job:
            raise HTTPException(404, 'This market research is unavailable.')
        supplied = str(form.get('revision') or '')
        if not supplied.isdecimal() or len(supplied) > 12 or int(supplied) != (state['revision'] if action == 'apply' else job['revision']):
            raise ValueError('Market research changed. Reload before making changes.')
        if action == 'apply':
            country = countries().get(job['scope']['country_id'])
            if not country or research.scope(country, job['scope']['berry_id'])['country_code'] != job['scope']['country_code']:
                raise ValueError('The country identity changed. Check it before using this research.')
            research.apply(main.INBOX_DIR, key, [str(v) for v in form.getlist('group')], int(supplied),
                           main.session_username(request) or main.review_username() or 'Analyst',
                           lambda: references(reference_groups(main.DATA_DIR), main.INBOX_DIR, True),
                           str(form.get('compared_revision') or ''))
            return RedirectResponse(return_path(return_to), status_code=303)
        if action == 'resume' and job['status'] == 'requested':
            tasks.add_task(research.submit, main.INBOX_DIR, key, client_factory)
        elif action == 'cancel' and job['status'] == 'requested':
            research.stop_unsubmitted(main.INBOX_DIR, key, job['revision'])
        else:
            if action == 'recover':
                if job['provider_id'] or job['status'] not in {'requested', 'submitting', 'submission_uncertain'} or form.get('confirm_run') != 'yes':
                    raise ValueError('Confirm that the existing research reference belongs to this country and berry.')
                provider_id = str(form.get('provider_id') or '').strip()
                if not provider_id:
                    raise ValueError('Enter the existing research reference.')
            elif action in {'check', 'cancel'} and job['provider_id'] and job['status'] not in research.TERMINAL:
                provider_id = job['provider_id']
            else:
                raise ValueError('This research has no active run for that action.')
            try:
                client = client_factory()
                result = await run_in_threadpool(client.cancel if action == 'cancel' else client.check, provider_id)
                research.apply_result(main.INBOX_DIR, key, result, job['revision'])
            except ResearchError as exc:
                research.failure(main.INBOX_DIR, key, exc, job['revision'])
    except ValueError as exc:
        return page(request, error=str(exc), status_code=409, job_id=key, return_to=return_to)
    return RedirectResponse(destination(key, return_to), status_code=303)
