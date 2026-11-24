"""Authoring-only dialog and download routes; never used by employee viewers."""
from datetime import date
import json
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response, FileResponse
from starlette.datastructures import UploadFile
from starlette.concurrency import run_in_threadpool

from app.personal_digest_routes import require_edit, world
from app.services import analyst_queue, personal_digest, viewer_content, viewer_reports
from app.services import viewer_export as service

router = APIRouter()
FILTERS = ('q', 'status', 'origin', 'berry', 'country', 'window', 'start', 'end', 'priority', 'tier', 'favorites', 'list')
HEADERS = {'Cache-Control': 'private, no-store', 'X-Robots-Tag': 'noindex, nofollow'}


@router.get('/viewer')
def viewer_hub(request: Request):
    require_edit(request)
    from app import main
    latest = service.load_latest(main.INBOX_DIR)
    return main.templates.TemplateResponse(request=request, name='viewer_hub.html', context={
        'authoring_mode': True, 'static_build': False, 'latest': latest,
        'published': service.load_published(main.INBOX_DIR), 'counts': service.counts(latest['workspace']) if latest else None,
    }, headers=HEADERS)


@router.get('/viewer/guide')
def viewer_guide(request: Request):
    require_edit(request)
    from app import main
    return main.templates.TemplateResponse(request=request, name='viewer_guide.html', context={
        'authoring_mode': True, 'static_build': False,
    }, headers=HEADERS)


@router.get('/viewer/files/{name}')
def viewer_file(request: Request, name: str):
    require_edit(request)
    from app import main
    import csv
    from io import BytesIO, StringIO
    from zipfile import ZipFile
    latest = service.load_latest(main.INBOX_DIR)
    if name == 'workspace.json':
        if not latest:
            raise HTTPException(404, 'Prepare and download a research release first.', headers=HEADERS)
        body, mime = service.json_bytes(latest['workspace']), 'application/json'
    elif name == 'company-ids.csv':
        directory = latest['workspace']['directory'] if latest else _directory('')
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(['company_id', 'company_name'])
        writer.writerows((r['id'], "'" + r['name'] if r['name'].startswith(('=', '+', '-', '@', '\t', '\r')) else r['name']) for r in directory['companies'])
        body, mime = output.getvalue().encode('utf-8-sig'), 'text/csv'
    else:
        allowed = {'starter-kit.zip': None, 'corporate-site.example.json': 'corporate-site.example.json',
                   'project-template.html': 'site/project-template.html', 'publishing-guide.md': 'START-HERE.md'}
        if name not in allowed:
            raise HTTPException(404, 'Unknown viewer file.', headers=HEADERS)
        starter, _ = service.build_release(service.empty_workspace())
        if name == 'starter-kit.zip':
            body, mime = starter, 'application/zip'
        else:
            with ZipFile(BytesIO(starter)) as archive:
                body = archive.read(allowed[name])
            mime = {'json': 'application/json', 'html': 'text/html', 'md': 'text/markdown'}[name.rsplit('.', 1)[1]]
    return Response(body, media_type=mime, headers={**HEADERS, 'Content-Disposition': f'attachment; filename="{name}"', 'X-Content-Type-Options': 'nosniff'})


@router.get('/viewer/releases/latest.zip')
def viewer_latest(request: Request):
    require_edit(request)
    from app import main
    latest = service.load_latest(main.INBOX_DIR)
    if not latest:
        raise HTTPException(404, 'Prepare and download a release first.', headers=HEADERS)
    body, _ = service.build_release(latest['workspace'], created_at=latest['created_at'], issue=latest.get('issue'))
    return Response(body, media_type='application/zip', headers={**HEADERS, 'Content-Disposition': f'attachment; filename="berry-viewer-{latest["release_id"]}.zip"'})


@router.get('/viewer/preview/{name:path}')
def viewer_preview(request: Request, name: str):
    require_edit(request)
    from app import main
    try:
        path = service.preview_file(main.INBOX_DIR, name)
    except ValueError as exc:
        raise HTTPException(404, str(exc), headers=HEADERS) from exc
    return FileResponse(path, headers={**HEADERS, 'X-Content-Type-Options': 'nosniff',
        'Content-Security-Policy': "default-src 'none'; script-src 'none'; style-src 'unsafe-inline'; img-src 'self' data:; connect-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'self'"})


def _content(filters):
    main, context, records, entities = world()
    model = personal_digest.digest_model(records=records, entities=entities, state=context['state'],
                                         reading=analyst_queue.load_state(main.INBOX_DIR), params=filters, paginate=False)
    candidates = [c for c in model['cards'] if service.exportable(c, records.get(c['id'], {}))]
    return main, candidates, records, model


def _filters(params):
    return {k: service.text(str(params.get('digest_' + k, params.get(k, 'all' if k == 'status' else ''))), 2000) for k in FILTERS}


def _defaults(latest, candidates):
    old = (latest or {}).get('settings') or {}
    today = date.today().isoformat()
    return {'title': old.get('title', 'The berry briefing'), 'date': today, 'issue_id': 'digest-' + today,
            'intro': old.get('intro', ''), 'editor': old.get('editor', ''), 'format': 'site',
            'directory_berry': old.get('directory_berry', ''), 'baseline_mode': 'previous' if latest else 'first',
            'add_newsletter': bool(candidates), 'report_ids': old.get('report_ids', []),
            'story_ids': [c['id'] for c in candidates if (c.get('decision') or {}).get('saved')]}


def _render(request, main, candidates, filters, values, latest, *, preview=None, error='', status=200):
    return main.templates.TemplateResponse(request=request, name='viewer_export.html', context={
        'authoring_mode': True, 'static_build': False, 'candidates': candidates, 'filters': filters,
        'values': values, 'latest': latest, 'baseline_revision': service.revision(latest),
        'preview': preview, 'preview_counts': service.counts(preview['workspace']) if preview else None,
        'export_error': error, 'berries': main.BERRIES,
        'published': service.load_published(main.INBOX_DIR), 'report_candidates': viewer_reports.candidates(main),
        'digest_return': '/digest?' + urlencode(filters),
    }, status_code=status, headers=HEADERS)


@router.get('/exports/viewer')
def export_dialog(request: Request):
    require_edit(request)
    filters = _filters(request.query_params)
    try:
        main, candidates, _, _ = _content(filters)
        latest = service.load_latest(main.INBOX_DIR)
        return _render(request, main, candidates, filters, _defaults(latest, candidates), latest)
    except ValueError as exc:
        raise HTTPException(422, str(exc), headers=HEADERS) from exc


async def _form(request):
    """Bound the whole multipart body before any parser spools uploaded files."""
    total, chunks = 0, []
    async for chunk in request.stream():
        total += len(chunk)
        if total > 22 * 1024 * 1024:
            raise HTTPException(413, 'Export inputs exceed the 22 MB request limit.', headers=HEADERS)
        chunks.append(chunk)
    sent = False

    async def receive():
        nonlocal sent
        if sent:
            return {'type': 'http.disconnect'}
        sent = True
        return {'type': 'http.request', 'body': b''.join(chunks), 'more_body': False}

    bounded = Request(request.scope, receive)
    return await bounded.form(max_files=2, max_fields=22000, max_part_size=service.MAX_FILE)


async def _upload(form, key):
    value = form.get(key)
    if not isinstance(value, UploadFile) or not value.filename:
        return None
    data = await value.read(service.MAX_FILE + 1)
    if len(data) > service.MAX_FILE:
        raise ValueError('Each uploaded file must be no larger than 10 MB.')
    return value.filename, data


def _directory(berry):
    from app.company_routes import context
    from app.services.variety_catalog_import import effective_record, imported_enrichment
    main, entities, _, _, company_rows = context()
    if berry and berry not in main.BERRIES:
        raise ValueError('Choose a supported directory berry scope.')
    enrichment = imported_enrichment(main.INBOX_DIR)
    enriched = [effective_record(r, enrichment) if r.get('entity_type') == 'variety' else r for r in entities.values()]
    companies = [r for r in company_rows.values() if not r.get('is_registry') and r.get('status') not in {'rejected', 'archived'}]
    return service.directory_from_catalog(companies, enriched, main.all_relationships(), berry,
                                          evidence=viewer_content.information_records(main, include_private=main.AUTHORING_MODE))


def _prepare(main, candidates, records, filters, values, latest, baseline_upload, flavor_upload, expected):
    if expected != service.revision(latest):
        raise service.ExportConflict('The previous export changed. Reopen this dialog before choosing the baseline.')
    mode = values['baseline_mode']
    if mode == 'previous':
        if not latest:
            raise ValueError('There is no previous export for your account. Upload a viewer backup or choose New site.')
        baseline = latest['workspace']
    elif mode == 'upload':
        if not baseline_upload:
            raise ValueError('Choose the viewer workspace JSON backup to preserve offsite records.')
        raw = service.parse_json(baseline_upload[1])
        if not isinstance(raw, dict):
            raise ValueError('Upload a research workspace JSON object.')
        if raw.get('scores'):
            raise ValueError('Flavor data stays corporate. Upload only a research workspace with no flavor records.')
        baseline = service.normalize_workspace(raw)
    elif mode == 'first':
        if latest:
            raise ValueError('Use the previous export or upload a newer viewer backup. A new-site export cannot silently discard existing history.')
        baseline = None
    else:
        raise ValueError('Choose a baseline source.')
    chosen_reports = viewer_reports.selected_reports(main, values.get('report_ids', []))
    directory = _directory(values['directory_berry'])
    if flavor_upload:
        raise ValueError('Flavor data stays corporate. Keep the flavor supplement out of platform exports.')
    if baseline:
        baseline = {**baseline, 'scores': []}
    issue = service.issue_from_selection(candidates, records, values['story_ids'], values) if values['add_newsletter'] else None
    workspace = service.assemble_workspace(directory, baseline, issue)
    from app.company_routes import context
    _, entity_map, _, _, company_rows = context()
    public_records = {r['id']: r for r in viewer_content.supplemental_records(main.INBOX_DIR, entity_map)}
    public_records.update({r['id']: r for r in viewer_content.information_records(main, include_private=True)})
    from app.services.social_intelligence.output_eligibility import output_exclusions
    blocked = set(output_exclusions(main.DATA_DIR, main.INBOX_DIR))
    stored = list(public_records.values())
    for r in stored + main.all_evidence():
        if (r.get('status') in viewer_content.INACTIVE or r.get('review_state') in viewer_content.INACTIVE
                or r.get('publication_scope') == 'private'):
            blocked.add(r['id'])
    workspace['activity'] = viewer_content.retain_archive(viewer_content.activity_from_records(stored, directory), baseline,
        stored, directory, blocked=blocked)
    for edition in workspace['issues']:
        edition['items'] = [r for r in edition['items'] if r['id'] not in blocked]
    if issue:
        issue['items'] = [r for r in issue['items'] if r['id'] not in blocked]
    workspace['assets'], workspace['asset_omissions'] = viewer_content.collect_assets(
        viewer_content.asset_candidates(main.INBOX_DIR, list(company_rows.values()), list(entity_map.values()), directory) + viewer_content.activity_asset_candidates(workspace['activity']))
    workspace['reports'] = chosen_reports
    workspace['as_of'] = date.today().isoformat()
    published = service.load_published(main.INBOX_DIR)
    comparison = published or latest
    workspace['changes'] = viewer_content.change_report(workspace, comparison['workspace'] if comparison else baseline,
        baseline_id=comparison['release_id'] if comparison else '', basis='confirmed_published' if published else 'previous_generated',
        old_scope=(comparison or {}).get('settings', {}).get('directory_berry', ''), scope=values['directory_berry'])
    settings = {k: service.text(values[k], limit) for k, limit in
                (('title', 300), ('date', 50), ('issue_id', 120), ('intro', 8000), ('editor', 200),
                 ('directory_berry', 100), ('format', 10))}
    settings['digest_filters'] = filters
    settings['report_ids'] = values.get('report_ids', [])
    return service.prepare(main.INBOX_DIR, workspace, settings, expected_revision=expected, issue=issue)


@router.post('/exports/viewer/preview')
async def preview_export(request: Request):
    require_edit(request)
    form = await _form(request)
    try:
        filters = _filters(form)
        main, candidates, records, _ = await run_in_threadpool(_content, filters)
        latest = service.load_latest(main.INBOX_DIR)
        values = {k: str(form.get(k) or '') for k in ('title', 'date', 'issue_id', 'intro', 'editor', 'directory_berry', 'format', 'baseline_mode')}
        values.update(add_newsletter=form.get('add_newsletter') == '1', story_ids=form.getlist('story_ids'), report_ids=form.getlist('report_ids'))
        if values['format'] not in {'site', 'json'}:
            raise HTTPException(422, 'Choose Full site release or Content JSON only.', headers=HEADERS)
        try:
            baseline_upload, flavor_upload = await _upload(form, 'baseline'), await _upload(form, 'flavor')
            preview = await run_in_threadpool(_prepare, main, candidates, records, filters, values, latest,
                                              baseline_upload, flavor_upload, str(form.get('baseline_revision') or ''))
            return _render(request, main, candidates, filters, values, latest, preview=preview)
        except ValueError as exc:
            return _render(request, main, candidates, filters, values, latest, error=str(exc),
                           status=409 if isinstance(exc, service.ExportConflict) else 422)
    except ValueError as exc:
        raise HTTPException(422, str(exc), headers=HEADERS) from exc
    finally:
        await form.close()


@router.post('/exports/viewer/confirm')
async def confirm_publication(request: Request):
    require_edit(request)
    from app import main
    from fastapi.responses import RedirectResponse
    form = await _form(request)
    try:
        try:
            await run_in_threadpool(service.confirm_published, main.INBOX_DIR, str(form.get('release_id') or ''))
        except ValueError as exc:
            raise HTTPException(409, str(exc), headers=HEADERS) from exc
        return RedirectResponse('/exports/viewer', status_code=303, headers=HEADERS)
    finally:
        await form.close()


@router.post('/exports/viewer/download')
async def download_export(request: Request):
    require_edit(request)
    from app import main
    form = await _form(request)
    try:
        try:
            data, manifest = await run_in_threadpool(service.download_prepared, main.INBOX_DIR, str(form.get('token') or ''))
        except ValueError as exc:
            raise HTTPException(409 if isinstance(exc, service.ExportConflict) else 422, str(exc), headers=HEADERS) from exc
        filename = 'berry-viewer-release-' + manifest['release_id'] + '.zip'
        return Response(data, media_type='application/zip', headers={**HEADERS, 'Content-Disposition': f'attachment; filename="{filename}"'})
    finally:
        await form.close()
