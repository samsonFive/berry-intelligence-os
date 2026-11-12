"""Private operational controls; no navigation destination or provider transport."""
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from app.services import brand_media as media
from app.services.pipeline_lock import pipeline_lock
from app.services.collection_runner import CollectionLockedError

router = APIRouter()
ROOT = Path(__file__).resolve().parents[1]
HEADERS = {'Cache-Control': 'private, no-store', 'X-Robots-Tag': 'noindex'}


def context():
    from app import main
    if not main.AUTHORING_MODE:
        raise HTTPException(404, 'Media controls require the private analyst workspace')
    return main


async def mutation(request):
    from app.social_routes import mutation as validate_mutation
    return await validate_mutation(request, max_bytes=3_000_000)


@router.get('/media-review', response_class=HTMLResponse)
def review(request: Request, entity: str = ''):
    main = context()
    entities = {e['id']: e for e in main.all_entities()}
    if entity and entity not in entities:
        raise HTTPException(404, 'Entity not found')
    rows = [r for r in media.inventory(main.INBOX_DIR) if not entity or r['entity_id'] == entity]
    return main.templates.TemplateResponse(request=request, name='brand_media_review.html',
        context={'assets': rows, 'media_counts': media.operational_counts(main.INBOX_DIR), 'entities': entities,
                 'selected_entity': entities.get(entity), 'kinds': media.KINDS, 'authoring_mode': True}, headers=HEADERS)


@router.get('/api/brand-media')
def inventory(entity: str = '', export: bool = False):
    main = context()
    rows = [r for r in media.inventory(main.INBOX_DIR) if not entity or r['entity_id'] == entity]
    if export:
        # Metadata/provenance stays inspectable; source image URLs, local bytes
        # and image delivery references do not escape a per-asset export hold.
        rows = [r for r in rows if r['export_eligible']]
    return JSONResponse({'assets': rows, 'counts': media.operational_counts(main.INBOX_DIR)}, headers=HEADERS)


@router.get('/api/brand-media/entities')
def entity_galleries(ids: str):
    """Bounded curated seam for shared detail/comparison; no raw attributes."""
    main = context()
    selected = list(dict.fromkeys(part.strip() for part in ids.split(',') if part.strip()))
    if not selected or len(selected) > 20:
        raise HTTPException(422, 'Choose 1–20 existing company, brand or retailer IDs')
    entities = {e['id']: e for e in main.all_entities()}
    if any(entities.get(key, {}).get('entity_type') not in {'company', 'brand', 'retailer'} for key in selected):
        raise HTTPException(422, 'Every ID must name an existing company, brand or retailer')
    models = media.entity_media(main.INBOX_DIR, selected)
    fields = {'id', 'entity_id', 'kind', 'kind_label', 'caption', 'image_url', 'attribution', 'source_page_url',
              'inspection_href', 'published_at', 'historical_status', 'source_kind', 'source_account',
              'match_basis', 'width', 'height'}
    def present(asset):
        return {key: value for key, value in asset.items() if key in fields} if asset else None
    result = {}
    for key, model in models.items():
        result[key] = {'entity_id': key, 'entity_type': entities[key]['entity_type'],
                       'logo': present(model['logo']), 'packaging': [present(a) for a in model['packaging']],
                       'observations': [present(a) for a in model['observations']],
                       'social_images': [present(a) for a in model.get('social_images', [])],
                       'official_images': [present(a) for a in model.get('official_images', [])]}
    return JSONResponse({'version': 1, 'entities': result}, headers=HEADERS)


@router.get('/api/brand-media/{key}/image')
def image(key: str):
    main = context()
    try:
        path, mime = media.image_file(main.INBOX_DIR, key)
    except (ValueError, OSError):
        raise HTTPException(410, 'Image unavailable under its current source policy') from None
    return FileResponse(path, media_type=mime, headers={**HEADERS, 'X-Content-Type-Options': 'nosniff',
        'Content-Security-Policy': "default-src 'none'; sandbox"})


@router.post('/api/brand-media/reuse')
async def reuse(request: Request):
    payload = await mutation(request)
    if not isinstance(payload, dict) or set(payload) - {'entity_id'}:
        raise HTTPException(422, 'Choose an existing entity or the bounded cohort')
    main = context()
    entities = {e['id']: e for e in main.all_entities()}
    entity = payload.get('entity_id')
    if entity and (not isinstance(entity, str) or entity not in entities):
        raise HTTPException(422, 'Entity not found')
    accounts = json.loads((ROOT / 'data/configuration/brand_media_accounts.json').read_text(encoding='utf-8'))['accounts']
    try:
        with pipeline_lock(main.INBOX_DIR, 'brand_media_reuse'):
            result = media.reuse_social(main.INBOX_DIR, entities, accounts=accounts, entity_ids=[entity] if entity else [])
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    except CollectionLockedError:
        raise HTTPException(409, 'Another collection is using this runtime') from None
    return JSONResponse(result, headers=HEADERS)


@router.post('/api/brand-media/{key}/decision')
async def decision(request: Request, key: str):
    payload = await mutation(request)
    if not isinstance(payload, dict) or set(payload) != {'changes', 'reviewer'}:
        raise HTTPException(422, 'Media changes and reviewer required')
    main = context()
    try:
        row = media.decide(main.INBOX_DIR, key, payload['changes'], reviewer=payload['reviewer'], entities={e['id']: e for e in main.all_entities()})
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from None
    return JSONResponse({'asset_id': row['id'], 'saved': True}, headers=HEADERS)


@router.post('/api/brand-media/upload')
async def upload(request: Request):
    payload = await mutation(request)
    import base64
    if not isinstance(payload, dict) or set(payload) != {'metadata', 'content_base64'}:
        raise HTTPException(422, 'Authorized upload metadata and raster bytes required')
    main = context()
    try:
        data = base64.b64decode(payload['content_base64'], validate=True)
        row = media.authorized_upload(main.INBOX_DIR, payload['metadata'], data, entities={e['id']: e for e in main.all_entities()})
    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(422, str(exc)) from None
    return JSONResponse({'asset_id': row['id']}, headers=HEADERS)
