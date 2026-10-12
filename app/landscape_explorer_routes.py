"""Authenticated analyst-only explorer; identical authorization for every format."""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

from app.services import landscape_explorer as explorer
from app.services import landscape_explorer_export as exports
from app.services.landscape_explorer_map import overview
from app.services.berries.landscape import SEED_FIXTURE_ENTITY_IDS, SEED_FIXTURE_EVIDENCE_IDS

router = APIRouter()


def context(request):
    from app import main
    if not main.AUTHORING_MODE:
        raise HTTPException(404, "Landscape Explorer is available in the analyst workspace.")
    if request.query_params.get("berry", "berry-blueberry") != "berry-blueberry":
        raise HTTPException(422, "Blueberry is enabled for this review milestone. Other berries await review.")
    entities = {row["id"]: row for row in main.all_entities() if row["id"] not in SEED_FIXTURE_ENTITY_IDS}
    evidence = [row for row in main.all_evidence() if row["id"] not in SEED_FIXTURE_EVIDENCE_IDS]
    try:
        bundle = explorer.build_bundle(entities, main.all_relationships(), evidence, request.query_params)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if bundle["filters"]["edge"] and bundle["filters"]["edge"] not in {row["id"] for row in bundle["edges"]}:
        raise HTTPException(422, "This relationship is unavailable in the selected scope. Reset the evidence selection.")
    return main, entities, bundle


@router.get("/landscapes/explorer", response_class=HTMLResponse)
def page(request: Request):
    try:
        main, entities, bundle = context(request)
    except HTTPException as exc:
        if exc.status_code != 422:
            raise
        from app import main
        return main.templates.TemplateResponse(request, "landscape_explorer_error.html", {
            "authoring_mode": main.AUTHORING_MODE, "message": exc.detail,
        }, status_code=422, headers={"Cache-Control": "private, no-store"})
    choices = sorted([row for row in entities.values() if row.get("entity_type") == "geography"], key=lambda row: row.get("name", row["id"]))
    source_lookup = {row["id"]: row for row in bundle["sources"]}
    focus_edges = [row for row in bundle["edges"] if bundle["filters"]["focus"] in {row["subject_id"], row["object_id"]}]
    return main.templates.TemplateResponse(request, "landscape_explorer.html", {
        "authoring_mode": main.AUTHORING_MODE, "bundle": bundle, "countries": choices,
        "roles": explorer.ROLE_LABELS, "questions": explorer.QUESTIONS, "href": explorer.href,
        "source_lookup": source_lookup, "focus_edges": focus_edges,
        "map_overview": overview(bundle),
        "export_query": bundle["url"].split("?", 1)[1],
    })


@router.get("/api/landscapes/explorer")
def api(request: Request):
    _, _, bundle = context(request)
    return JSONResponse(bundle, headers={"Cache-Control": "private, no-store"})


@router.get("/landscapes/explorer/briefing", response_class=HTMLResponse)
def briefing(request: Request):
    _, _, bundle = context(request)
    return HTMLResponse(exports.html_export(bundle, return_url=str(request.base_url).rstrip("/") + bundle["url"]),
                        headers={"Cache-Control": "private, no-store"})


@router.get("/landscapes/explorer/export/{format}")
def export(request: Request, format: str):
    _, _, bundle = context(request)
    generators = {"html": (lambda b: exports.html_export(b, return_url=str(request.base_url).rstrip("/") + b["url"]), "text/html; charset=utf-8"),
                  "svg": (exports.svg_export, "image/svg+xml"), "csv": (exports.csv_export, "text/csv; charset=utf-8")}
    if format not in generators:
        raise HTTPException(404, "Choose HTML, SVG or CSV.")
    generate, media_type = generators[format]
    return Response(generate(bundle), media_type=media_type, headers={
        "Content-Disposition": f'attachment; filename="blueberry-landscape-{bundle["version"]}.{format}"',
        "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
    })
