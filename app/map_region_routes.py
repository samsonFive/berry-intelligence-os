"""Profile region editor; the map and profile use the same private annotations."""
from uuid import uuid4
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.concurrency import run_in_threadpool

from app.personal_digest_routes import require_edit
from app.services import map_regions, personal_digest

router = APIRouter()


def context(entity_id):
    from app import main
    entities = main.entity_index()
    actor = entities.get(entity_id, {})
    if actor.get("entity_type") not in map_regions.ACTIVITIES:
        raise HTTPException(404, "Company or variety not found")
    records = list(personal_digest.source_records(main.published_evidence(), main.INBOX_DIR).values()) if main.AUTHORING_MODE else main.published_evidence()
    relationships = main.all_relationships()
    private = map_regions.load(main.INBOX_DIR) if main.AUTHORING_MODE else None
    rows = [row for row in map_regions.catalog(entities, relationships, records, private) if row["entity_id"] == entity_id]
    return main, actor, entities, records, relationships, private, rows


@router.get("/profiles/{entity_id}/regions", response_class=HTMLResponse)
def profile_regions(request: Request, entity_id: str):
    from app import main
    source_id, fact_id = request.query_params.get("from_source", ""), request.query_params.get("from_statement", "")
    research_job, proposal_id = request.query_params.get("research_job", ""), request.query_params.get("proposal", "")
    if (source_id or fact_id or research_job or proposal_id) and not main.AUTHORING_MODE:
        raise HTTPException(403, "Preparing a region requires the analyst workspace")
    main, actor, entities, records, relationships, private, rows = context(entity_id)
    editing = next((row for row in rows if row["id"] == request.query_params.get("edit")), {})
    statements = [f for f in main.all_facts() if f.get("status") == "active" and entity_id in (f.get("entity_ids") or [])]
    prepared = {}
    if source_id or fact_id or research_job or proposal_id:
        if request.query_params.get("edit"):
            raise HTTPException(409, "Finish the current edit before starting a new region from a source")
        try:
            if research_job or proposal_id:
                from app.services.region_source_research import get_proposal
                _, _, prepared = get_proposal(main.INBOX_DIR, entity_id, research_job, proposal_id, entities=entities,
                                             records=records, relationships=relationships, facts=statements)
            else:
                prepared = map_regions.prepare_from_source(entity_id, source_id=source_id, fact_id=fact_id,
                    entities=entities, records=records, relationships=relationships, facts=statements)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
    return main.templates.TemplateResponse(request=request, name="profile_regions.html", context={
        "entity": actor, "rows": rows, "editing": editing, "prepared": prepared,
        "form_values": prepared.get("draft") or editing, "activities": map_regions.ACTIVITIES[actor["entity_type"]],
        "geographies": sorted([e for e in entities.values() if e.get("entity_type") == "geography"], key=lambda e: e["name"]),
        "sources": map_regions.supporting_sources(entity_id, records, relationships, statements),
        "statements": statements,
        "history": [row for row in (private or {}).get("history", []) if row["after"]["entity_id"] == entity_id][-30:][::-1],
        "authoring_mode": main.AUTHORING_MODE,
        **research_context(main, entity_id, entities, rows, relationships),
    })


@router.post("/profiles/{entity_id}/regions")
async def edit_profile_region(request: Request, entity_id: str):
    require_edit(request)
    main, _, entities, records, relationships, _, _ = context(entity_id)
    form = dict(await request.form())
    form["entity_id"] = entity_id
    # Removal must belong to the route's profile too.
    if form.get("id"):
        current = next((r for r in map_regions.catalog(entities, relationships, records, map_regions.load(main.INBOX_DIR)) if r["id"] == form["id"]), None)
        if not current or current["entity_id"] != entity_id:
            raise HTTPException(404, "Region not found on this profile")
    try:
        map_regions.edit(main.INBOX_DIR, payload=form, entities=entities, relationships=relationships, records=records, facts=main.all_facts(),
                         reviewer=main.session_username(request) or main.review_username() or "")
    except ValueError as exc:
        raise HTTPException(409 if "changed in another" in str(exc) else 400, str(exc)) from exc
    return RedirectResponse(f"/profiles/{entity_id}/regions", status_code=303)


def research_context(main, entity_id, entities, rows, relationships):
    if not main.AUTHORING_MODE:
        return {}
    from app.services import region_source_research as research
    try:
        return {"region_research_jobs": research.views(main.INBOX_DIR, entity_id, entities, rows, relationships), "region_research_token": uuid4().hex}
    except ValueError as exc:
        return {"region_research_error": str(exc), "region_research_jobs": []}


def research_client():
    from app.services.ai_gateway.credentials import MissingCredentialError, resolve_perplexity_api_key
    from app.services.ai_gateway.perplexity_deep_research import DeepResearchClient, ResearchError
    try:
        return DeepResearchClient(resolve_perplexity_api_key())
    except MissingCredentialError as exc:
        raise ResearchError("Location research is not connected in this workspace. No provider request was sent.") from exc


@router.post("/profiles/{entity_id}/regions/research")
async def start_region_research(request: Request, entity_id: str, background_tasks: BackgroundTasks):
    require_edit(request)
    main, actor, entities, records, relationships, _, _ = context(entity_id)
    form = dict(await request.form())
    from app.services import region_source_research as research
    try:
        prepared = map_regions.prepare_from_source(entity_id, source_id=str(form.get("source_id") or ""), fact_id=str(form.get("fact_id") or ""),
                                                  entities=entities, records=records, relationships=relationships, facts=main.all_facts())
        job, created = research.reserve(main.INBOX_DIR, actor, prepared, str(form.get("token") or ""))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if created:
        background_tasks.add_task(research.submit, main.INBOX_DIR, job["id"], research_client)
    return RedirectResponse(f"/profiles/{entity_id}/regions#location-suggestions", status_code=303)


@router.post("/profiles/{entity_id}/regions/research/{key}/{action}")
async def region_research_action(request: Request, entity_id: str, key: str, action: str, background_tasks: BackgroundTasks):
    require_edit(request)
    main, _, _, _, _, _, _ = context(entity_id)
    from app.services import region_source_research as research
    from app.services.ai_gateway.perplexity_deep_research import ResearchError
    form = dict(await request.form())
    try:
        job = research.load(main.INBOX_DIR)["jobs"].get(key)
        if not job or job["scope"]["entity_id"] != entity_id:
            raise HTTPException(404, "This location check is unavailable on this profile")
        if action == "dismiss":
            research.dismiss(main.INBOX_DIR, key, str(form.get("proposal_id") or ""), revision=form.get("revision"),
                             reviewer=main.session_username(request) or main.review_username() or "")
        elif action == "resume":
            if job["status"] != "requested":
                raise ValueError("This source check has started. Reconnect or check the existing run")
            background_tasks.add_task(research.submit, main.INBOX_DIR, key, research_client)
        elif action == "cancel" and job["status"] == "requested":
            research.stop_unsubmitted(main.INBOX_DIR, key, revision=form.get("revision"))
        elif action == "recover":
            if job["provider_id"] or job["status"] not in {"requested", "submitting", "submission_uncertain"} or form.get("confirm_run") != "yes":
                raise ValueError("Confirm that this existing research reference belongs to this source check")
            try:
                result = await run_in_threadpool(lambda: research_client().check(str(form.get("provider_id") or "").strip()))
                research.apply_result(main.INBOX_DIR, key, result, revision=job["revision"])
            except ResearchError as exc:
                research.failure(main.INBOX_DIR, key, exc, revision=job["revision"])
        elif action in {"check", "cancel"} and job["status"] not in research.TERMINAL and job["provider_id"]:
            try:
                client = research_client()
                result = await run_in_threadpool(client.check if action == "check" else client.cancel, job["provider_id"])
                research.apply_result(main.INBOX_DIR, key, result, revision=job["revision"])
            except ResearchError as exc:
                research.failure(main.INBOX_DIR, key, exc, revision=job["revision"])
        else:
            raise ValueError("This source check has no active run for that action")
    except ValueError as exc:
        raise HTTPException(409 if "changed in another" in str(exc) else 422, str(exc)) from exc
    return RedirectResponse(f"/profiles/{entity_id}/regions#location-suggestions", status_code=303)
