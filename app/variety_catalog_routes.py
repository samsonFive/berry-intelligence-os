"""Editable persistent variety catalog. All writes require the authoring session."""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.personal_digest_routes import require_edit
from app.repositories.json.entities import EntityRepository
from app.repositories.base import InvalidRecord
from app.services import variety_catalog as catalog
from app.services.collection_runner import CollectionLockedError

router = APIRouter()


def _main(request):
    require_edit(request)
    from app import main
    return main


def _record(main, entity_id):
    record = EntityRepository(main.DATA_DIR, main.SCHEMAS_DIR).get(entity_id)
    if not record or record.get('entity_type') != 'variety':
        raise HTTPException(404, 'Variety not found')
    return record


def _actor(main, request, form):
    return main.session_username(request) or main.review_username() or str(form.get('editor') or '').strip()


def _editor(main, request, record, *, new=False, error='', form=None, status=200):
    from app.services.variety_catalog_import import effective_record, imported_enrichment
    expected = catalog.revision(record)
    record = effective_record(record, imported_enrichment(main.INBOX_DIR))
    model = catalog.editor_model(record)
    model['revision'] = expected
    attrs = record.get('attributes') or {}
    model['table_rows'] = {key: list(attrs.get(key) or []) + [{}] for key in catalog.TABLES}
    if form is not None:
        for key, columns in catalog.TABLES.items():
            model['table_rows'][key] = [{column: form.getlist(key + '.' + column)[i] if i < len(form.getlist(key + '.' + column)) else '' for column in columns}
                                       for i in range(len(form.getlist(key + '.row'))) if str(i) not in form.getlist(key + '.remove')] + [{}]
        keys = form.getlist('extra.key')
        model['extra_fields'] = [{'key': key, 'value': form.getlist('extra.value')[i], 'kind': form.getlist('extra.kind')[i]}
                                 for i, key in enumerate(keys) if str(i) not in form.getlist('extra.remove')]
    return main.templates.TemplateResponse(request=request, name='variety_catalog_edit.html', context={
        **model, 'authoring_mode': True, 'static_build': False, 'new': new, 'error': error, 'form': form,
        'editor_name': main.session_username(request) or main.review_username() or '',
        'parties': sorted([row for row in main.living_catalog() if row.get('entity_type') in {'company', 'brand', 'breeding_program', 'retailer', 'person'}], key=lambda row: row['name'].casefold()),
        'catalog_history': [] if new else catalog.history(main.INBOX_DIR, record['id']),
        'catalog_relationships': [] if new else [{**row, 'revision': catalog.revision(row)} for row in main.all_relationships()
                                  if record['id'] in {row.get('subject_id'), row.get('object_id')}],
        'relationship_choices': json_relationship_choices(main),
    }, status_code=status, headers={'Cache-Control': 'private, no-store', 'X-Robots-Tag': 'noindex'})


def json_relationship_choices(main):
    import json
    return json.loads((main.SCHEMAS_DIR / 'relationship.schema.json').read_text(encoding='utf-8'))['properties']['predicate']['enum']


@router.get('/varieties/catalog/new')
def new_variety(request: Request):
    main = _main(request)
    return _editor(main, request, {'id': '', 'name': '', 'description': '', 'aliases': [],
                                 'berry_ids': [], 'status': 'unverified', 'attributes': {}}, new=True)


@router.post('/varieties/catalog/new')
async def create_variety(request: Request):
    main = _main(request)
    form = await request.form()
    try:
        record = catalog.create(main.INBOX_DIR, main.DATA_DIR, main.SCHEMAS_DIR, form, actor=_actor(main, request, form))
    except (ValueError, InvalidRecord, CollectionLockedError) as exc:
        return _editor(main, request, {'id': '', 'name': '', 'aliases': [], 'berry_ids': [], 'status': 'unverified', 'attributes': {}},
                       new=True, error=str(exc), form=form, status=422)
    return RedirectResponse('/entities/variety/' + record['id'], status_code=303)


@router.get('/varieties/catalog/removed')
def removed_varieties(request: Request):
    main = _main(request)
    records = EntityRepository(main.DATA_DIR, main.SCHEMAS_DIR).list(entity_type='variety')
    return main.templates.TemplateResponse(request=request, name='variety_catalog_removed.html', context={
        'authoring_mode': True, 'static_build': False,
        'removed_rows': sorted([catalog.editor_model(row) for row in records if (row.get('attributes') or {}).get('catalog_removed')], key=lambda row: row['record']['name'].casefold()),
    }, headers={'Cache-Control': 'private, no-store'})


@router.get('/varieties/catalog/{entity_id}/edit')
def edit_variety(request: Request, entity_id: str):
    main = _main(request)
    return _editor(main, request, _record(main, entity_id))


@router.post('/varieties/catalog/{entity_id}/edit')
async def save_variety(request: Request, entity_id: str):
    main = _main(request)
    form = await request.form()
    try:
        catalog.save(main.INBOX_DIR, main.DATA_DIR, main.SCHEMAS_DIR, entity_id, form, actor=_actor(main, request, form))
    except (ValueError, InvalidRecord, CollectionLockedError) as exc:
        # Keep the submitted revision on errors. A stale form must never become
        # a fresh form that silently overwrites another editor's changes.
        return _editor(main, request, _record(main, entity_id), error=str(exc), form=form,
                       status=409 if 'changed in another' in str(exc) else 422)
    return RedirectResponse('/entities/variety/' + entity_id + '?saved=1', status_code=303)


@router.post('/varieties/catalog/{entity_id}/{action}')
async def remove_restore_variety(request: Request, entity_id: str, action: str):
    main = _main(request)
    if action not in {'remove', 'restore'}:
        raise HTTPException(404, 'Unknown catalog action')
    form = await request.form()
    try:
        catalog.remove_or_restore(main.INBOX_DIR, main.DATA_DIR, main.SCHEMAS_DIR, entity_id,
                                  expected=form.get('revision'), actor=_actor(main, request, form),
                                  restore=action == 'restore', confirmation=str(form.get('confirmation') or ''))
    except (ValueError, InvalidRecord, CollectionLockedError) as exc:
        return _editor(main, request, _record(main, entity_id), error=str(exc), status=409)
    return RedirectResponse('/entities/variety' if action == 'remove' else '/entities/variety/' + entity_id, status_code=303)


@router.post('/varieties/catalog/{entity_id}/relationships/save')
async def save_catalog_relationship(request: Request, entity_id: str):
    main = _main(request)
    form = await request.form()
    try:
        catalog.save_relationship(main.INBOX_DIR, main.DATA_DIR, main.SCHEMAS_DIR, entity_id, form, actor=_actor(main, request, form))
    except (ValueError, InvalidRecord, CollectionLockedError) as exc:
        return _editor(main, request, _record(main, entity_id), error=str(exc), status=422)
    return RedirectResponse('/varieties/catalog/' + entity_id + '/edit#catalog-relationships', status_code=303)
