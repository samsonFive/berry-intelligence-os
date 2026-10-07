"""Analyst-only workspace. Reads never collect; mutations validate origin/size."""
import json
import os
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from app.services.social_intelligence.store import Store, now
from app.services.social_intelligence.aggregate import bundle, href, VIEWS
from app.services.social_intelligence.model import PLATFORMS
from app.services.social_intelligence.presentation import player, readable_in_english

router=APIRouter()
ROOT=Path(__file__).resolve().parents[1]

def context():
    from app import main
    if not main.AUTHORING_MODE:
        raise HTTPException(404,'Social Listening requires the private analyst workspace')
    return main,Store(main.INBOX_DIR)

def view_bundle(request):
    main,store=context()
    access=json.loads((ROOT/'docs/v2/social-source-access.json').read_text(encoding='utf-8'))['sources']
    try:
        b=bundle([r for r in store.records() if readable_in_english(r)],store.jobs(),request.query_params,access={r['source']:r for r in access})
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc
    return main,store,b

@router.get('/social',response_class=HTMLResponse)
def page(request:Request):
    try:
        main,store,b=view_bundle(request)
    except HTTPException as exc:
        if exc.status_code!=422: raise
        main,_=context()
        return main.templates.TemplateResponse(request,'social_error.html',{'authoring_mode':True,'message':exc.detail},status_code=422)
    from app.services.landscape_explorer_map import overview
    # Existing geography boundary contract, no second geocoder or explorer.
    map_locator=overview({'lanes':[]})
    entities=sorted((e for e in main.all_entities() if e.get('entity_type') in ('company','variety')),key=lambda e:e.get('name',e['id']).casefold())
    return main.templates.TemplateResponse(request,'social.html',{'authoring_mode':True,'bundle':b,'href':href,'views':VIEWS,'platforms':PLATFORMS,'map_locator':map_locator,'social_entities':entities,'trial_preview':os.environ.get('BIOS_SOCIAL_TRIAL_PREVIEW')=='true','player_for':player},headers={'Cache-Control':'private, no-store'})

@router.get('/api/social')
def api(request:Request):
    _,_,b=view_bundle(request)
    return JSONResponse(b,headers={'Cache-Control':'private, no-store'})

@router.get('/api/social/{key}/reader',response_class=HTMLResponse)
def reader(request:Request,key:str):
    main,store=context()
    row=next((r for r in store.records() if r['id']==key),None)
    if not row: raise HTTPException(410,'Observation unavailable or removed')
    if not readable_in_english(row): raise HTTPException(409,'An English version is pending')
    thread=[r for r in store.records(mode=row['mode']) if readable_in_english(r) and r['source']==row['source'] and (r['native_id']==row.get('parent_native_id') or r.get('parent_native_id')==row['native_id'])]
    return main.templates.TemplateResponse(request,'social_reader.html',{'row':row,'thread':thread,'player':player(row)},headers={'Cache-Control':'private, no-store'})

@router.get('/api/social/{key}/media/{media_id}')
def media(key:str,media_id:str):
    _,store=context()
    try: path,mime=store.media(key,media_id)
    except ValueError as exc: raise HTTPException(410,str(exc)) from exc
    return FileResponse(path,media_type=mime,headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})

async def mutation(request):
    context()
    if request.headers.get('origin')!=str(request.base_url).rstrip('/'):
        raise HTTPException(403,'Same-origin action required')
    body=bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body)>1_000_000: raise HTTPException(413,'Intake limit is 1 MB')
    try: return json.loads(body)
    except ValueError as exc: raise HTTPException(422,'Expected JSON intake') from exc

@router.post('/api/social/import')
async def import_records(request:Request):
    payload=await mutation(request); main,store=context()
    if not isinstance(payload,list) or len(payload)>100: raise HTTPException(422,'Import 1–100 normalized records')
    try: ids=store.ingest(payload,main.all_entities(),mode='imported')
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    return {'ids':ids,'mode':'imported','monitoring':False}

@router.post('/api/social/manual')
async def manual(request:Request):
    payload=await mutation(request); main,store=context()
    if not isinstance(payload,dict): raise HTTPException(422,'Expected manual record')
    # No URL fetch: captures analyst-provided permitted text and URL only.
    payload.update(mode='manual',collected_at=now(),discovery_method='analyst-url-capture',query_version='manual-1')
    try: ids=store.ingest([payload],main.all_entities(),mode='manual')
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    return {'ids':ids,'mode':'manual','fetched':False}

@router.post('/api/social/{key}/handoff')
async def handoff(request:Request,key:str):
    await mutation(request); _,store=context()
    try: return {'review_url':store.handoff(key)}
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc

@router.get('/social/briefing',response_class=HTMLResponse)
def briefing(request:Request):
    main,_,b=view_bundle(request)
    return main.templates.TemplateResponse(request,'social_briefing.html',{'bundle':b},headers={'Cache-Control':'private, no-store'})

@router.get('/social/export')
def export(request:Request):
    _,_,b=view_bundle(request)
    return JSONResponse(b,headers={'Cache-Control':'private, no-store','Content-Disposition':'attachment; filename="social-observation-snapshot.json"'})
