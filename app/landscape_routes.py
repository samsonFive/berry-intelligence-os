"""Configurable Landscape with explicit, private saved-selection actions."""
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.personal_digest_routes import require_edit
from app.services import company_directory, feed_first, landscape_workspace, map_regions, personal_digest
from app.services.berries.landscape import SEED_FIXTURE_ENTITY_IDS

router = APIRouter()


def context(params):
    from app import main
    entities = {row["id"]: row for row in main.all_entities() if row["id"] not in SEED_FIXTURE_ENTITY_IDS}
    state = feed_first.load_state(main.INBOX_DIR) if main.AUTHORING_MODE else {}
    companies = company_directory.catalog(entities, state=state)
    companies = {key: row for key, row in companies.items() if key not in SEED_FIXTURE_ENTITY_IDS}
    filters = landscape_workspace.parameters(params, entities=entities, companies=companies, berries=main.BERRIES, state=state)
    relationships, evidence = main.all_relationships(), main.published_evidence()
    selected = landscape_workspace.values(filters, "berry") or list(main.BERRIES)
    contexts = {berry: main._cached_landscape_context(berry, "global", "all") for berry in selected}
    model = landscape_workspace.model(contexts=contexts, entities=entities, companies=companies, relationships=relationships,
                                      evidence=evidence, region_rows=map_regions.catalog(entities, relationships, evidence),
                                      state=state, params=params, berries=main.BERRIES)
    return main, model, entities, companies, state


def landscape_page(request: Request):
    try:
        main, model, entities, companies, state = context(request.query_params)
        store = landscape_workspace.load_views(main.INBOX_DIR) if main.AUTHORING_MODE else {"views": {}}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    selected_view = store["views"].get(str(request.query_params.get("saved_view") or ""))
    model["saved_views"] = [{**row, "href": landscape_workspace.view_href(row)} for row in store["views"].values()]
    # Handoffs state their narrower semantics instead of silently carrying unsupported scope.
    news_params = {key: value for key, value in model["filters"].items() if key in {"berry", "countries", "list", "tier", "favorites", "window", "start", "end"} and value}
    news_params["view"] = "unreviewed"
    selected_companies = landscape_workspace.values(model["filters"], "company")
    if len(selected_companies) == 1:
        news_params["company"] = selected_companies[0]
    model["news_href"] = "/today?" + urlencode(news_params)
    model["map_href"] = "/explorer?" + urlencode({key: value for key, value in news_params.items() if key not in {"window", "start", "end", "view"}})
    # Brief composition supports one berry and selected canonical organizations/varieties, not source date ranges or country filters.
    brief_params = {"companies": ",".join(row["id"] for row in model["panels"]["companies"][:4]) if "companies" in model["sections"] else "",
                    "varieties": ",".join(row["id"] for row in model["panels"]["varieties"][:4]) if "varieties" in model["sections"] else ""}
    if len(landscape_workspace.values(model["filters"], "berry")) == 1:
        brief_params["berry"] = model["filters"]["berry"]
    model["brief_href"] = "/brief-pack?" + urlencode(brief_params)
    report_params = {"origin": "landscape", "report_type": "competitive_landscape", "company_ids": model["filters"]["company"],
                     "variety_ids": model["filters"]["variety"], "geography_ids": model["filters"]["countries"],
                     "focus_notes": "Landscape sections requested: " + ", ".join(model["section_choices"][key] for key in model["sections"])}
    if len(landscape_workspace.values(model["filters"], "berry")) == 1:
        report_params["berry"] = model["filters"]["berry"]
    elif model["filters"]["berry"]:
        report_params["focus_notes"] += ". Requested berries: " + ", ".join(main.BERRIES[key] for key in landscape_workspace.values(model["filters"], "berry")) + "; confirm the report's berry scope."
    if model["filters"]["window"] in {"7d", "30d"}:
        report_params["date_window_days"] = model["filters"]["window"].rstrip("d")
    if model["filters"]["window"] in {"ytd", "custom"}:
        report_params["focus_notes"] += f". Requested source dates: {model['source_start'] or 'all'} through {model['source_end']}; custom dates require report-scope review."
    if model["filters"]["list"] or model["filters"]["tier"] or model["filters"]["favorites"]:
        report_params["company_ids"] = ",".join(row["id"] for row in model["panels"]["companies"] if row["id"] in entities)
    model["report_enabled"] = not (model["filters"]["list"] or model["filters"]["tier"] or model["filters"]["favorites"]) or bool(report_params["company_ids"])
    model["brief_enabled"] = bool(brief_params["companies"] or brief_params["varieties"])
    model["report_href"] = "/reports/new?" + urlencode(report_params)
    try:
        source_page = max(1, int(request.query_params.get("source_page") or "1"))
    except ValueError:
        source_page = 1
    model["source_pages"] = max(1, (len(model["panels"]["sources"]) + 39) // 40)
    model["source_page"] = min(source_page, model["source_pages"])
    model["source_rows"] = model["panels"]["sources"][(model["source_page"] - 1) * 40:model["source_page"] * 40]
    page_query = {**model["query"]}
    if selected_view:
        page_query["saved_view"] = selected_view["id"]
    model["source_pagination"] = {page: "/landscapes?" + urlencode({**page_query, "source_page": page}) + "#landscape-sources" for page in (model["source_page"] - 1, model["source_page"] + 1)}
    return main.templates.TemplateResponse(request=request, name="landscape_workspace.html", context={
        **model, "selected_view": selected_view, "authoring_mode": main.AUTHORING_MODE,
        "berries": main.BERRIES, "tiers": company_directory.TIERS, "lists": personal_digest.company_lists(state),
        "scope_choices": {"company": sorted(companies.values(), key=lambda row: row["name"].casefold()),
                          "variety": sorted([row for row in entities.values() if row.get("entity_type") == "variety"], key=lambda row: row["name"].casefold()),
                          "countries": sorted([row for row in entities.values() if row.get("entity_type") == "geography"], key=lambda row: row["name"].casefold())},
    })


@router.post("/landscapes/views")
async def save_landscape_view(request: Request):
    require_edit(request)
    from app import main
    form = await request.form()
    action = str(form.get("action") or "save")
    if action not in {"save", "archive", "restore"}:
        raise HTTPException(422, "Choose a supported saved-view action")
    key = str(form.get("view_id") or "")
    try:
        if action == "save":
            _, model, _, _, _ = context(form)
            filters, name = model["filters"], str(form.get("name") or "")
        else:
            original = landscape_workspace.load_views(main.INBOX_DIR)["views"].get(key)
            if not original:
                raise ValueError("Saved Landscape view is unavailable")
            filters, name = original["filters"], original["name"]
        row = landscape_workspace.save_view(main.INBOX_DIR, name=name, filters=filters, view_id=key,
                                            revision=str(form.get("revision") or "0"), archive=action == "archive")
    except ValueError as exc:
        raise HTTPException(409 if "another window" in str(exc) else 422, str(exc)) from exc
    return RedirectResponse("/landscapes" if action == "archive" else landscape_workspace.view_href(row), status_code=303)
