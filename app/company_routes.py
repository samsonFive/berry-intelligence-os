"""Glasshouse company directory and analyst-managed profile presentation."""
from urllib.parse import urlencode, urlsplit

from fastapi import APIRouter, HTTPException, Request
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
    tab = "people" if form.get("action") in {"person", "hide_person", "restore_person"} else "details"
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
    return {"company": company, "profile_override": override, "company_people": people, "company_rows": rows,
            "profile_history": [h for h in private["history"] if h["entity_id"] == entity_id][-30:][::-1],
            "profile_regions": [r for r in map_regions.catalog(entities, relations, list(records.values()), map_regions.load(main.INBOX_DIR) if main.AUTHORING_MODE else None) if r["entity_id"] == entity_id],
            "company_news_model": news, "tiers": directory.TIERS, "lists": personal_digest.company_lists(state), "tab": tab,
            "return_to": company["profile_url"].split("?")[0] + "?tab=" + tab}
