"""Explicit in-app public-query research; no provider calls on GET."""
from urllib.parse import urlsplit
import re

from fastapi import APIRouter, Form, HTTPException, Request

from app.personal_digest_routes import require_edit
from app.services.ai_gateway.credentials import MissingCredentialError, resolve_perplexity_api_key
from app.services.ai_gateway.errors import GatewayError
from app.services.ai_gateway.perplexity_search import PerplexitySearchClient
from app.services.map_regions import public_source_url
from app.services.competitor_pulse import _BERRY_PATTERNS
from app.services.berry_vocabulary import canonicalize_crop_words
from app.services.variety_keyword_search import fold

router = APIRouter()


@router.post('/varieties/candidates/{candidate_id}/promote')
def promote_candidate(request: Request, candidate_id: str, decision_digest: str = Form('')):
    from app import main
    from fastapi.responses import RedirectResponse
    from app.services.variety_catalog_management import canonical_record, promotion_digest as digest
    from app.services.variety_universe.candidates import persist_variety_candidates
    require_edit(request)
    varieties,candidates,_=main.variety_candidate_universe()
    candidate=next((r for r in candidates if r['id']==candidate_id),None)
    if not candidate:raise HTTPException(404,'Candidate not found')
    # A retry links to the already-created catalog record instead of duplicating it.
    existing=next((v for v in varieties if (v.get('attributes') or {}).get('catalog_candidate_id')==candidate_id),None)
    if existing:return RedirectResponse('/entities/variety/'+existing['id'],303)
    if digest(candidate)!=decision_digest:raise HTTPException(409,'The candidate changed. Reload its review before adding it.')
    try:
        actor=main.session_username(request) or 'local analyst'
        record=canonical_record(candidate,varieties=varieties,candidates=candidates,actor=actor,authorization='Explicit Add canonical variety action')
        main.get_repositories(main.DATA_DIR,main.SCHEMAS_DIR).entities.create(record)
        updated={**candidate,'identity_state':'confirmed_same','identity_label':'CONFIRMED SAME VARIETY','candidate_canonical_match':record['id'],'human_gated':True,'reviewer':actor,'reviewed_at':record['attributes']['identity_review']['reviewed_at'],'status':'reviewed'}
        persist_variety_candidates([updated],inbox_dir=main.INBOX_DIR,overwrite=True)
    except ValueError as exc:raise HTTPException(409,str(exc)) from exc
    return RedirectResponse('/entities/variety/'+record['id'],303)


@router.get('/varieties/removed')
def removed_varieties(request: Request):
    from app import main
    if not main.AUTHORING_MODE:raise HTTPException(403,'Catalog management requires the analyst workspace')
    rows=[r for r in main.all_entities() if r.get('entity_type')=='variety' and (r.get('attributes') or {}).get('catalog_removed')]
    return main.templates.TemplateResponse(request=request,name='variety_removed.html',context={'rows':rows,'authoring_mode':True,'static_build':False})


@router.post('/varieties/{variety_id}/catalog-status')
def catalog_status(request: Request,variety_id: str,action: str = Form('')):
    from app import main
    from fastapi.responses import RedirectResponse
    from app.services.variety_catalog_management import set_removed
    require_edit(request)
    if action not in {'remove','restore'}:raise HTTPException(422,'Choose remove or restore')
    repo=main.get_repositories(main.DATA_DIR,main.SCHEMAS_DIR).entities
    record=repo.get(variety_id)
    if not record or record.get('entity_type')!='variety':raise HTTPException(404,'Variety not found')
    repo.update(variety_id,set_removed(record,removed=action=='remove',actor=main.session_username(request) or 'local analyst'))
    return RedirectResponse('/varieties/removed' if action=='remove' else '/entities/variety/'+variety_id,303)


@router.get('/api/varieties/view-state/{view_key}')
def saved_view(request: Request, view_key: str):
    from app import main
    from app.services import variety_view_state
    if not main.AUTHORING_MODE:
        raise HTTPException(403, 'Saved views require the analyst workspace')
    try:
        return variety_view_state.get(main.INBOX_DIR, main.session_username(request) or 'local', view_key)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post('/api/varieties/view-state/{view_key}')
async def save_view(request: Request, view_key: str):
    from app import main
    from app.services import variety_view_state
    require_edit(request)
    if len(await request.body()) > 20_000:
        raise HTTPException(413, 'Layout is too large')
    try:
        return variety_view_state.save(main.INBOX_DIR, main.session_username(request) or 'local', view_key, await request.json())
    except (ValueError, TypeError) as exc:
        raise HTTPException(409, str(exc)) from exc


def search_client():
    return PerplexitySearchClient(resolve_perplexity_api_key())


def relevant_hit(hit, *, query, target=None, known_hosts=()):
    """Suppress film/phone/name collisions without claiming search completeness."""
    text=' '.join(str(getattr(hit,k,'') or '') for k in ('title','snippet','url'))
    normalized=fold(text)
    if target:
        names=[target['name'],*(target.get('aliases') or [])]
        if not any(re.search(r'(?<!\w)'+re.escape(fold(name))+r'(?!\w)',normalized) for name in names if name):
            return False
    crops=set((target or {}).get('berry_ids') or []) or {key for key,pattern in _BERRY_PATTERNS.items() if pattern.search(canonicalize_crop_words(query))}
    if not crops:
        return True
    host=(urlsplit(hit.url).hostname or '').removeprefix('www.')
    if host in known_hosts:return True
    latin={'berry-blueberry':r'\bVaccinium\b','berry-raspberry':r'\bRubus\s+(idaeus|occidentalis)\b','berry-strawberry':r'\bFragaria\b','berry-blackberry':r'\bRubus\s+(fruticosus|subgenus)\b'}
    return any((_BERRY_PATTERNS[key].search(canonicalize_crop_words(text)) or re.search(latin[key],text,re.I)) for key in crops if key in _BERRY_PATTERNS)


def render(request, *, query='', entity_id='', hits=(), error='', omitted=0, scoped=True):
    from app import main
    entity = main.entity_index().get(entity_id)
    if entity_id and (not entity or entity.get('entity_type') not in {'variety', 'company', 'brand', 'breeding_program'}):
        raise HTTPException(404, 'Research target not found')
    return main.templates.TemplateResponse(request=request, name='entity_research.html', context={
        'authoring_mode': True, 'static_build': False, 'query': query, 'target': entity,
        'hits': hits, 'error': error, 'omitted':omitted,'scoped':scoped, 'reviewer': main.session_username(request) or main.review_username() or 'analyst',
    })


@router.get('/varieties/research')
def research_page(request: Request, q: str = '', entity_id: str = ''):
    from app import main
    if not main.AUTHORING_MODE:
        raise HTTPException(403, 'Research requires the analyst workspace')
    return render(request, query=q[:1200], entity_id=entity_id)


@router.post('/varieties/research')
def research_search(request: Request, query: str = Form(''), entity_id: str = Form(''), scope_results: str = Form('1')):
    require_edit(request)
    query = query.strip()
    if not 2 <= len(query) <= 1200:
        return render(request, query=query[:1200], entity_id=entity_id, error='Enter a public search query of 2–1,200 characters.')
    # Validate the selected target before a provider call; it is context, not an inferred identity.
    from app import main
    target = main.entity_index().get(entity_id)
    if entity_id and (not target or target.get('entity_type') not in {'variety', 'company', 'brand', 'breeding_program'}):
        raise HTTPException(404, 'Research target not found')
    try:
        response = search_client().search(query, max_results=10)  # No implicit recency filter.
        hits = [];omitted=0;hosts=set()
        if target and target.get('entity_type')=='variety':
            from app.services.variety_profile_sources import profile_source_details
            notes=profile_source_details(main.DATA_DIR,target,varieties=[v for v in main.all_entities() if v.get('entity_type')=='variety'])
            urls=[s['url'] for s in (notes or {}).get('sources',{}).values()]
            urls.append(((target.get('attributes') or {}).get('identity_review') or {}).get('source_url') or '')
            hosts={(urlsplit(url).hostname or '').removeprefix('www.') for url in urls if url}
        seen = set()
        for hit in response.hits:
            url = public_source_url(hit.url)
            if not url or url in seen:
                continue
            seen.add(url)
            if scope_results!='0' and not relevant_hit(hit,query=query,target=target,known_hosts=hosts):
                omitted+=1;continue
            hits.append(dict(title=hit.title[:500], url=url, snippet=hit.snippet[:3000], date=hit.published_date,
                             publisher=urlsplit(url).hostname))
        return render(request, query=query, entity_id=entity_id, hits=hits,omitted=omitted,scoped=scope_results!='0',
                      error='' if hits else 'No results returned for this query. Try a denomination, breeder code or broader wording.')
    except MissingCredentialError:
        return render(request, query=query, entity_id=entity_id, error='Public web search is not configured. Saved intelligence and Ask Berry remain available in the panel.')
    except GatewayError:
        return render(request, query=query, entity_id=entity_id, error='The search provider could not complete this query. Retry without losing your query.')
