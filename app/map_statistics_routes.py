"""Analyst review of explicitly captured official market references."""
from urllib.parse import urlencode, urlsplit
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.personal_digest_routes import require_edit
from app.services import map_statistics_refresh as refresh
from app.services.market_statistics_reference import group_id, reference_groups

router = APIRouter()


def return_path(value):
    try:
        parts = urlsplit(value)
        if not parts.scheme and not parts.netloc and parts.path in {'/explorer', '/explorer/snapshot'}:
            return parts.path + ('?' + parts.query if parts.query else '') + '#gx-statistics'
    except ValueError:
        pass
    return '/explorer#gx-statistics'


def page(request, *, error='', status_code=200, return_to=None):
    from app import main
    if not main.AUTHORING_MODE:
        raise HTTPException(403, 'Reference checks require the analyst workspace.')
    return_to = return_path(return_to or request.query_params.get('return_to', ''))
    try:
        state = refresh.load(main.INBOX_DIR)
    except ValueError as exc:
        state = refresh.empty()
        error = str(exc)
        status_code = 409
    try:
        baseline = reference_groups(main.DATA_DIR)
    except ValueError as exc:
        baseline = []
        error = str(exc)
        status_code = 409
    try:
        current = refresh.references(baseline, main.INBOX_DIR, True)
    except ValueError as exc:
        current = []
        error = str(exc)
        status_code = 409
    current_by_category = {refresh.category(group): group for group in current}
    jobs = sorted(state['jobs'].values(), key=lambda job: (job['created_at'], job['id']), reverse=True)
    job = jobs[0] if jobs else None
    comparisons = [{**group, 'id': group_id(group), 'previous': current_by_category.get(refresh.category(group))}
                   for group in (job['groups'] if job and job['status'] == 'ready' else [])]
    return main.templates.TemplateResponse(request=request, name='map_statistics_review.html', status_code=status_code, context={
        'authoring_mode': True, 'static_build': False, 'active_href': '/explorer', 'error': error, 'job': job,
        'comparisons': comparisons, 'current': current, 'revision': state['revision'], 'token': uuid4().hex,
        'history': list(reversed(state['history'])), 'return_to': return_to,
        'review_href': '/explorer/statistics?' + urlencode({'return_to': return_to}),
        'research_href': '/explorer/statistics/research?' + urlencode({'return_to': return_to}),
    })


@router.get('/explorer/statistics')
def review_page(request: Request):
    return page(request)


@router.post('/explorer/statistics/check')
async def check(request: Request, tasks: BackgroundTasks):
    require_edit(request)
    from app import main
    form = await request.form()
    try:
        reference_groups(main.DATA_DIR)
        job, start = refresh.reserve(main.INBOX_DIR, str(form.get('token') or ''))
    except ValueError as exc:
        return page(request, error=str(exc), status_code=409, return_to=str(form.get('return_to') or ''))
    if start:
        tasks.add_task(refresh.run, main.INBOX_DIR, job['id'])
    return RedirectResponse('/explorer/statistics?' + urlencode({'return_to': return_path(str(form.get('return_to') or ''))}), status_code=303)


@router.post('/explorer/statistics/apply')
async def apply(request: Request):
    require_edit(request)
    from app import main
    form = await request.form()
    revision = str(form.get('revision') or '')
    if not revision.isdecimal() or len(revision) > 12:
        return page(request, error='Reload before saving reviewed figures.', status_code=409, return_to=str(form.get('return_to') or ''))
    try:
        reference_groups(main.DATA_DIR)
        refresh.apply(main.INBOX_DIR, str(form.get('job_id') or ''), [str(value) for value in form.getlist('group')],
                      int(revision), main.session_username(request) or main.review_username() or 'Analyst')
    except ValueError as exc:
        return page(request, error=str(exc), status_code=409, return_to=str(form.get('return_to') or ''))
    return RedirectResponse(return_path(str(form.get('return_to') or '')), status_code=303)
