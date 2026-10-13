"""Authenticated analyst-only explorer; identical authorization for every format."""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response, RedirectResponse

from app.services import landscape_explorer as explorer
from app.services import landscape_explorer_export as exports
from app.services.landscape_explorer_pdf import pdf_export
from app.services.landscape_explorer_map import overview
from app.services.berries.landscape import SEED_FIXTURE_ENTITY_IDS, SEED_FIXTURE_EVIDENCE_IDS
from app.services.variety_universe.coverage import BERRY_ORDER
from app.services import landscape_workspace as workspace, feed_first, company_directory, personal_digest
from app.personal_digest_routes import require_edit
import json

router = APIRouter()


def company_state(inbox):
    path = feed_first.state_path(inbox)
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError()
            for field in ("entity_favorites", "entity_tiers", "company_lists"):
                if raw.get(field) is not None and not isinstance(raw[field], dict):
                    raise ValueError()
            if any(value is not None and not isinstance(value, str) for value in (raw.get("entity_tiers") or {}).values()):
                raise ValueError()
            for group in (raw.get("company_lists") or {}).values():
                if not isinstance(group, dict) or not isinstance(group.get("company_ids") or [], list) or any(not isinstance(key, str) for key in group.get("company_ids") or []):
                    raise ValueError()
        except (OSError, ValueError, TypeError):
            raise ValueError("Company preferences cannot be read. Restore the saved preferences before using this view.") from None
        state = feed_first.empty_state()
        state.update({key: raw.get(key, state[key]) for key in state})
        return state
    return feed_first.empty_state()


def context(request, params=None):
    from app import main
    if not main.AUTHORING_MODE:
        raise HTTPException(404, "Landscape Explorer is available in the analyst workspace.")
    params = request.query_params if params is None else params
    try:
        store = workspace.load_views(main.INBOX_DIR)
        selected_view = store["views"].get(str(params.get("saved_view") or ""))
        if params.get("saved_view") and (not selected_view or selected_view.get("kind") != "explorer" or selected_view["archived"]):
            raise ValueError("This saved Explorer view is unavailable or archived. Choose a current saved view.")
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    # Explicit URL/form edits override the saved selectors; the stored row is
    # changed only by its revision-checked POST action.
    raw_params = params
    params = {**(selected_view["filters"] if selected_view else {}), **dict(raw_params)}
    # QueryParams/FormData can repeat countries; retain the existing multi-select.
    if "countries" in raw_params:
        params["countries"] = ",".join(workspace.values(raw_params, "countries"))
    if params.get("berry", "berry-blueberry") not in (*BERRY_ORDER, "all"):
        raise HTTPException(422, "Choose blueberry, strawberry, raspberry, blackberry or All berries.")
    entities = {row["id"]: row for row in main.all_entities() if row["id"] not in SEED_FIXTURE_ENTITY_IDS}
    evidence = [row for row in main._social_eligible_outputs(main.all_evidence()) if row["id"] not in SEED_FIXTURE_EVIDENCE_IDS]
    relationships = main._social_eligible_outputs(main.all_relationships())
    try:
        state = company_state(main.INBOX_DIR)
        bundle = explorer.build_bundle(entities, relationships, evidence, params, state=state)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if bundle["filters"]["edge"] and bundle["filters"]["edge"] not in {row["id"] for row in bundle["edges"]}:
        raise HTTPException(422, "This relationship is unavailable in the selected scope. Reset the evidence selection.")
    if selected_view:
        bundle["filters"]["saved_view"] = selected_view["id"]
        bundle["url"] = explorer.href(bundle["filters"])
        bundle["saved_view"] = {key: selected_view[key] for key in ("id", "name", "revision")}
    return main, entities, bundle, store, state


@router.get("/landscapes/explorer", response_class=HTMLResponse)
def page(request: Request):
    try:
        main, entities, bundle, store, state = context(request)
    except HTTPException as exc:
        if exc.status_code != 422:
            raise
        from app import main
        return main.templates.TemplateResponse(request, "landscape_explorer_error.html", {
            "authoring_mode": main.AUTHORING_MODE, "message": exc.detail,
        }, status_code=422, headers={"Cache-Control": "private, no-store"})
    choices = sorted([row for row in entities.values() if row.get("entity_type") == "geography"], key=lambda row: row.get("name", row["id"]))
    source_lookup = {row["id"]: row for row in bundle["sources"]}
    groups = personal_digest.company_lists(state)
    actor_marks = {key: {"favorite": bool((state.get("entity_favorites") or {}).get(key)),
                         "tier": company_directory.TIERS.get((state.get("entity_tiers") or {}).get(key) or "untiered", "Existing tier"),
                         "lists": [row["name"] for row in groups if key in row.get("company_ids", [])]}
                   for key, row in bundle["nodes"].items() if row["type"] in {"company", "breeding_program"}}
    focus_edges = [row for row in bundle["edges"] if bundle["filters"]["focus"] in {row["subject_id"], row["object_id"]}]
    return main.templates.TemplateResponse(request, "landscape_explorer.html", {
        "authoring_mode": main.AUTHORING_MODE, "bundle": bundle, "browser_bundle": {**explorer.browser_bundle(bundle), "actor_marks": actor_marks}, "countries": choices,
        "actor_marks": actor_marks, "company_lists": groups,
        "company_tiers": {**company_directory.CURRENT_TIERS, **({bundle["filters"]["tier"]: company_directory.TIERS[bundle["filters"]["tier"]]} if bundle["filters"]["tier"] else {})},
        "explorer_berries": [entities[key] for key in BERRY_ORDER if key in entities and entities[key].get("entity_type") == "berry"],
        "roles": explorer.ROLE_LABELS, "questions": explorer.QUESTIONS, "href": explorer.href,
        "source_lookup": source_lookup, "focus_edges": focus_edges,
        "saved_views": [{**row, "href": workspace.view_href(row)} for row in store["views"].values() if row.get("kind") == "explorer"],
        "selected_view": store["views"].get(bundle["filters"].get("saved_view", "")),
        "explorer_fields": workspace.EXPLORER_FIELDS,
        "map_overview": overview(bundle),
        "export_query": bundle["url"].split("?", 1)[1],
    })


@router.get("/api/landscapes/explorer")
def api(request: Request):
    _, _, bundle, _, _ = context(request)
    return JSONResponse(bundle, headers={"Cache-Control": "private, no-store"})


@router.get("/landscapes/explorer/briefing", response_class=HTMLResponse)
def briefing(request: Request):
    _, _, bundle, _, _ = context(request)
    return HTMLResponse(exports.html_export(bundle, return_url=str(request.base_url).rstrip("/") + bundle["url"]),
                        headers={"Cache-Control": "private, no-store"})


@router.get("/landscapes/explorer/export/{format}")
def export(request: Request, format: str):
    _, _, bundle, _, _ = context(request)
    generators = {"html": (lambda b: exports.html_export(b, return_url=str(request.base_url).rstrip("/") + b["url"]), "text/html; charset=utf-8"),
                  "svg": (exports.svg_export, "image/svg+xml"), "csv": (exports.csv_export, "text/csv; charset=utf-8"),
                  "pdf": (lambda b: pdf_export(b, return_url=str(request.base_url).rstrip("/")+b["url"]), "application/pdf")}
    if format not in generators:
        raise HTTPException(404, "Choose PDF, HTML, SVG or CSV.")
    generate, media_type = generators[format]
    return Response(generate(bundle), media_type=media_type, headers={
        "Content-Disposition": f'attachment; filename="{exports.scope_slug(bundle)}-landscape-{bundle["version"]}.{format}"',
        "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
    })


@router.post("/landscapes/explorer/views")
async def save_explorer_view(request: Request):
    require_edit(request)
    from app import main
    form = await request.form()
    action = str(form.get("action") or "save")
    if action not in {"save", "copy", "archive", "restore"}:
        raise HTTPException(422, "Choose a supported saved-view action.")
    key = str(form.get("view_id") or "")
    try:
        if action in {"save", "copy"}:
            _, _, bundle, _, _ = context(request, form)
            filters = {**bundle["filters"], "countries": ",".join(bundle["filters"]["countries"])}
            name = str(form.get("name") or "")
            if action == "copy":
                key = ""
        else:
            original = workspace.load_views(main.INBOX_DIR)["views"].get(key)
            if not original or original.get("kind") != "explorer":
                raise ValueError("Saved Explorer view is unavailable.")
            filters, name = original["filters"], original["name"]
        row = workspace.save_view(main.INBOX_DIR, name=name, filters=filters, view_id=key,
            revision="0" if action == "copy" else str(form.get("revision") or "0"),
            archive=action == "archive", kind="explorer")
    except ValueError as exc:
        raise HTTPException(409 if "another window" in str(exc) else 422, str(exc)) from exc
    return RedirectResponse("/landscapes/explorer#landscape-saved" if action == "archive" else workspace.view_href(row), status_code=303,
                            headers={"Cache-Control": "private, no-store"})
