"""Profile region editor; the map and profile use the same private annotations."""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

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
    main, actor, entities, records, _, private, rows = context(entity_id)
    editing = next((row for row in rows if row["id"] == request.query_params.get("edit")), {})
    support_ids = {key for row in rows for key in row.get("evidence_ids", [])}
    return main.templates.TemplateResponse(request=request, name="profile_regions.html", context={
        "entity": actor, "rows": rows, "editing": editing, "activities": map_regions.ACTIVITIES[actor["entity_type"]],
        "geographies": sorted([e for e in entities.values() if e.get("entity_type") == "geography"], key=lambda e: e["name"]),
        "sources": sorted([r for r in records if r.get("id") in support_ids or entity_id in (r.get("entity_ids") or []) or entity_id in (r.get("company_ids") or [])], key=lambda r: r.get("published_date") or "", reverse=True),
        "statements": [f for f in main.all_facts() if f.get("status") == "active" and entity_id in (f.get("entity_ids") or [])],
        "history": [row for row in (private or {}).get("history", []) if row["after"]["entity_id"] == entity_id][-30:][::-1],
        "authoring_mode": main.AUTHORING_MODE,
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
