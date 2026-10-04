"""Glasshouse company directory and analyst-managed profile presentation."""
from urllib.parse import urlencode, urlsplit
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from starlette.concurrency import run_in_threadpool
from fastapi.responses import RedirectResponse

from app.personal_digest_routes import require_edit
from app.services import company_directory as directory, feed_first, personal_digest
from app.services.entity_logo_overrides import load_logo_overrides

router = APIRouter()


def context():
    from app import main
    entities = {row["id"]: row for row in main.living_catalog()}
    state = feed_first.load_state(main.INBOX_DIR) if main.AUTHORING_MODE else feed_first.empty_state()
    private = directory.load_profiles(main.INBOX_DIR) if main.AUTHORING_MODE else {"profiles": {}, "history": []}
    logos = load_logo_overrides(main.INBOX_DIR) if main.AUTHORING_MODE else {}
    return main, entities, state, private, directory.catalog(entities, logos=logos, profiles=private["profiles"], state=state)


def company_directory_page(request):
    main, _, state, _, rows = context()
    params = dict(request.query_params)
    if request.query_params.getlist("berry_choice"):
        params["berry"] = ",".join(request.query_params.getlist("berry_choice"))
    try:
        model = directory.directory(rows, state, params)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    query = model["filters"]
    model["letter_urls"] = {letter: "/entities/company?" + urlencode({**query, "letter": letter}) for letter in ["", *"ABCDEFGHIJKLMNOPQRSTUVWXYZ#"]}
    model["return_to"] = "/entities/company?" + urlencode(query)
    return main.templates.TemplateResponse(request=request, name="company_directory.html", context={**model, "authoring_mode": main.AUTHORING_MODE, "berries": main.BERRIES})


def safe_return(value, entity_id=""):
    parts = urlsplit(value or "")
    allowed = {"/entities/company", f"/entities/company/{entity_id}", f"/entities/brand/{entity_id}", f"/entities/breeding_program/{entity_id}"}
    if parts.scheme or parts.netloc or parts.path not in allowed:
        return "/entities/company"
    return parts.path + ("?" + parts.query if parts.query else "") + ("#" + parts.fragment if parts.fragment else "")


@router.post("/companies/{entity_id}/marks")
async def company_marks(request: Request, entity_id: str):
    require_edit(request)
    main, _, _, _, rows = context()
    form = await request.form()
    try:
        directory.mark(main.INBOX_DIR, entity_id=entity_id, action=str(form.get("action") or ""), value=str(form.get("value") or ""), allowed=set(rows))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return RedirectResponse(safe_return(str(form.get("return_to") or ""), entity_id), status_code=303)


@router.post("/companies/lists")
async def company_lists(request: Request):
    require_edit(request)
    main, _, state, _, rows = context()
    form = await request.form()
    # Renaming must preserve existing registry members, including non-company people.
    allowed = set(rows)
    if str(form.get("action") or "") == "edit":
        for group in personal_digest.company_lists(state):
            if group["id"] == str(form.get("list_id") or ""):
                allowed.update(group["company_ids"])
    try:
        personal_digest.edit_list(main.INBOX_DIR, action=str(form.get("action") or ""), list_id=str(form.get("list_id") or ""),
                                 name=str(form.get("name") or ""), company_ids=list(form.getlist("company_ids")), allowed_companies=allowed)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return RedirectResponse(safe_return(str(form.get("return_to") or "")) + "#company-lists", status_code=303)


@router.post("/companies/{entity_id}/profile")
async def company_profile_edit(request: Request, entity_id: str):
    require_edit(request)
    main, entities, _, private, rows = context()
    if entity_id not in rows:
        raise HTTPException(404, "Company not found")
    from app.services.people_watchlist import discover_people
    people = directory.people_for(entity_id, entities, main.all_relationships(), discover_people(entities.values()), private["profiles"].get(entity_id) or {})
    form = dict(await request.form())
    try:
        directory.edit_profile(main.INBOX_DIR, entity_id=entity_id, payload=form, known_people={p["id"] for p in people},
                               reviewer=main.session_username(request) or main.review_username() or "")
    except ValueError as exc:
        raise HTTPException(409 if "changed in another" in str(exc) else 400, str(exc)) from exc
    tab = "people" if form.get("action") in {"person", "hide_person", "restore_person", "restore_contact_version"} else "details"
    return RedirectResponse(rows[entity_id]["profile_url"].split("?")[0] + "?tab=" + tab + "&saved=1", status_code=303)


def profile_context(request, entity_id, existing):
    from app import main
    from app.services import map_regions, news_workspace
    from app.services.people_watchlist import discover_people
    entities = {row["id"]: row for row in existing}
    state = feed_first.load_state(main.INBOX_DIR) if main.AUTHORING_MODE else feed_first.empty_state()
    private = directory.load_profiles(main.INBOX_DIR) if main.AUTHORING_MODE else {"profiles": {}, "history": []}
    logos = load_logo_overrides(main.INBOX_DIR) if main.AUTHORING_MODE else {}
    rows = directory.catalog(entities, logos=logos, profiles=private["profiles"], state=state)
    company = rows.get(entity_id)
    if not company:
        return {}
    override = private["profiles"].get(entity_id) or {"revision": 0, "people": {}}
    relations = main.all_relationships()
    published = main.published_evidence()
    records = personal_digest.source_records(published, main.INBOX_DIR) if main.AUTHORING_MODE else {r["id"]: r for r in published}
    # Seed companies are addressable identities, not inferred canonical companies.
    selector_entities = {**entities, entity_id: {**company, "entity_type": "company"}}
    news = news_workspace.model(records=records, entities=selector_entities, relationships=relations, facts=main.all_facts(), state=state,
                                params={"company": entity_id, "window": "", "view": "unreviewed", "tz": str(request.query_params.get("tz") or "UTC")})
    people = directory.people_for(entity_id, entities, relations, discover_people(existing), override)
    tab = str(request.query_params.get("tab") or "overview")
    if tab not in {"overview", "news", "intelligence", "varieties", "regions", "people", "details"}:
        tab = "overview"
    watched, watch_error = False, ""
    if main.AUTHORING_MODE and company.get("canonical") and company.get("entity_type") == "company":
        from app.services.watchlist import is_watched
        try:
            watched = is_watched(main.INBOX_DIR, "company", entity_id)
        except ValueError as exc:
            watch_error = str(exc)
    return {"company": company, "profile_override": override, "company_people": people, "company_rows": rows,
            "is_subject_watched": watched, "subject_watch_error": watch_error,
            "profile_history": directory.profile_history_rows(private["history"], entity_id),
            **research_context(main, entity_id, override, people, tab),
            "profile_regions": [r for r in map_regions.catalog(entities, relations, list(records.values()), map_regions.load(main.INBOX_DIR) if main.AUTHORING_MODE else None) if r["entity_id"] == entity_id],
            "company_news_model": news, "tiers": directory.TIERS, "lists": personal_digest.company_lists(state), "tab": tab,
            "return_to": company["profile_url"].split("?")[0] + "?tab=" + tab}


def research_context(main, entity_id, override, people, tab):
    # Public pages and unrelated company tabs never touch private research.
    if not main.AUTHORING_MODE or tab not in {"details", "people"}:
        return {}
    from app.services import company_profile_research as research
    try:
        jobs = [research.view(j, override, known_people=people) for j in research.load(main.INBOX_DIR)["jobs"].values()
                if j["company"]["id"] == entity_id]
        jobs.sort(key=lambda j: j["created_at"], reverse=True)
        return {"profile_research_jobs": jobs, "profile_research_token": uuid4().hex, "profile_research_error": ""}
    except ValueError as exc:
        return {"profile_research_jobs": [], "profile_research_error": str(exc)}


def profile_research_client():
    from app.services.ai_gateway.credentials import MissingCredentialError, resolve_perplexity_api_key
    from app.services.ai_gateway.perplexity_deep_research import DeepResearchClient, ResearchError
    try:
        return DeepResearchClient(resolve_perplexity_api_key())
    except MissingCredentialError as exc:
        raise ResearchError("Company research is not connected in this workspace. No provider request was sent.") from exc


def research_redirect(rows, entity_id, form, notice=""):
    tab = "people" if form.get("tab") == "people" else "details"
    return RedirectResponse(rows[entity_id]["profile_url"].split("?")[0] + "?tab=" + tab + ("&research_notice=" + notice if notice else "") + "#company-research", status_code=303)


@router.post("/companies/{entity_id}/research/start")
async def company_research_start(request: Request, entity_id: str, background_tasks: BackgroundTasks):
    require_edit(request)
    main, entities, _, private, rows = context()
    if entity_id not in rows:
        raise HTTPException(404, "Company not found")
    form = dict(await request.form())
    from app.services import company_profile_research as research
    # Fresh PUBLIC projection: the private website, contacts and annotations
    # are deliberately excluded from what is sent to the research service.
    public_company = directory.catalog(entities)[entity_id]
    try:
        job, created = research.reserve(main.INBOX_DIR, public_company, str(form.get("token") or ""),
                                        profile_revision=(private["profiles"].get(entity_id) or {}).get("revision", 0))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if created:
        background_tasks.add_task(research.submit, main.INBOX_DIR, job["id"], profile_research_client)
    return research_redirect(rows, entity_id, form, "requested")


@router.post("/companies/{entity_id}/research/{key}/{action}")
async def company_research_action(request: Request, entity_id: str, key: str, action: str, background_tasks: BackgroundTasks):
    require_edit(request)
    from app.services import company_profile_research as research
    from app.services.ai_gateway.perplexity_deep_research import ResearchError
    main, entities, _, private, rows = context()
    if entity_id not in rows:
        raise HTTPException(404, "Company not found")
    form = dict(await request.form())
    try:
        job = research.load(main.INBOX_DIR)["jobs"].get(key)
        if not job or job["company"]["id"] != entity_id:
            raise HTTPException(404, "This company research run is unavailable")
        if action == "resume":
            if job["status"] != "requested":
                raise ValueError("This request has already started; check or reconnect the existing run")
            background_tasks.add_task(research.submit, main.INBOX_DIR, key, profile_research_client)
        elif action == "cancel" and job["status"] == "requested":
            research.stop_unsubmitted(main.INBOX_DIR, key, revision=form.get("job_revision"))
        elif action in {"check", "cancel", "recover"}:
            if action == "recover":
                if job["provider_id"] or job["status"] not in {"requested", "submitting", "submission_uncertain"}:
                    raise ValueError("This run already has a research reference")
                if form.get("confirm_run") != "yes":
                    raise ValueError("Confirm that this research reference belongs to this company")
                result = await run_in_threadpool(lambda: profile_research_client().check(str(form.get("provider_id") or "").strip()))
                research.apply_result(main.INBOX_DIR, key, result, revision=job["revision"])
            elif job["status"] not in research.TERMINAL and job["provider_id"]:
                try:
                    client = profile_research_client()
                    result = await run_in_threadpool(client.check if action == "check" else client.cancel, job["provider_id"])
                    research.apply_result(main.INBOX_DIR, key, result, revision=job["revision"])
                except ResearchError as exc:
                    research.failure(main.INBOX_DIR, key, exc, revision=job["revision"])
            else:
                raise ValueError("This run has no active research reference to check or stop")
        elif action == "dismiss":
            research.dismiss(main.INBOX_DIR, key, str(form.get("proposal_id") or ""), revision=form.get("job_revision"),
                             reviewer=main.session_username(request) or main.review_username() or "")
        elif action == "accept":
            from app.services.people_watchlist import discover_people
            people = directory.people_for(entity_id, entities, main.all_relationships(), discover_people(entities.values()),
                                          private["profiles"].get(entity_id) or {})
            research.accept(main.INBOX_DIR, key, str(form.get("proposal_id") or ""), profile_revision=form.get("revision"),
                            replace=form.get("replace") == "yes", current_socials=rows[entity_id]["socials"], known_people=people,
                            reviewer=main.session_username(request) or main.review_username() or "")
        else:
            raise HTTPException(404, "This research action is unavailable")
    except ValueError as exc:
        raise HTTPException(409 if "changed in another" in str(exc) else 422, str(exc)) from exc
    return research_redirect(rows, entity_id, form, action)
