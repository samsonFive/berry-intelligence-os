"""Private Strategy Review. Review revisions live in the shared analyst store."""

from __future__ import annotations

import json
import os
from urllib.parse import urlencode

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import RedirectResponse

from app.personal_digest_routes import require_edit
from app.services import berry_strategy_review as service, living_workspaces as living
from app.services.berry_strategy_priorities import CRITERIA, load_opportunities
from app.services.global_berry_landscape import CROPS, REGIONS, filters_for

router = APIRouter()


def _paths(scope):
    crop = scope["crop"] or "all"
    query = urlencode({key: value for key, value in scope.items() if key != "crop" and value})
    suffix = "?" + query if query else ""
    base = f"/strategy-reviews/berries/{crop}"
    back = "/landscapes/global" + (f"/{crop}" if crop != "all" else "")
    return {"refresh_href": base + "/refresh" + suffix, "review_href": base + "/review" + suffix,
            "history_href": base + "/history" + suffix, "back_href": back + suffix + "#berry-strategy-review"}


def _store(main, *, create=False):
    if create or (main.INBOX_DIR / "living_workspaces" / "workspace.sqlite3").is_file():
        return living.Store(main.INBOX_DIR)
    return None


def _model_enabled():
    from app.services.ai_gateway.credentials import credit_free_research_enabled
    return os.environ.get("BIOS_BERRY_STRATEGY_PUBLIC_AI") == "1" and not credit_free_research_enabled()


def _profiles(main, snapshot):
    linked = {key for source in snapshot["sources"].values() for key in source["entity_ids"]}
    entities = main.entity_index()
    rows = {}
    for key in sorted(linked & entities.keys()):
        row = entities[key]
        kind = row["entity_type"]
        rows[key] = {"label": row["name"], "kind": kind, "href": f"/entities/{kind}/{key}"}
    return rows


def _present(main, review, *, stale=False):
    snapshot = review["snapshot"]
    scope = snapshot["scope"]
    return {**_paths(scope), "review": review, "stale": stale, "profiles": _profiles(main, snapshot),
            "scope_label": CROPS.get(scope["crop"], "All four berries") + " · " + REGIONS.get(scope["region"], "All regions"),
            "framework_labels": service.FRAMEWORKS, "company_frameworks": service.COMPANY_FRAMEWORKS,
            "criteria": CRITERIA, "model_enabled": _model_enabled()}


def _snapshot(main, model):
    return service.snapshot_for(model, opportunities=load_opportunities(main.INBOX_DIR))


def panel(main, model):
    if not main.AUTHORING_MODE:
        return None
    snapshot = _snapshot(main, model)
    store = _store(main)
    stored = store.get(service.scope_key(snapshot["scope"])) if store else None
    stale = bool(stored and stored["basis"] != living.digest(snapshot))
    review = stored if stored and not stale else service.prepare(snapshot)
    if not stored or stale:
        review.update(generated_at="", method="Evidence preview", version=stored["version"] if stored else 0)
    result = _present(main, review, stale=stale)
    result["has_history"] = bool(stored)
    return result


def _review_main(request, crop, *, edit=False):
    from app import main
    if not main.AUTHORING_MODE:
        raise HTTPException(403, "Strategy Review requires private authoring access.")
    if edit:
        require_edit(request)
    if crop != "all" and crop not in CROPS:
        raise HTTPException(404, "Unknown berry strategy scope.")
    return main


def _context(request, crop):
    main = _review_main(request, crop, edit=True)
    from app.berry_landscape_routes import context
    try:
        model = context(main, request.query_params, "" if crop == "all" else crop)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return main, model


def _actor(main, request):
    return main.session_username(request) or main.review_username() or "local analyst"


@router.post("/strategy-reviews/berries/{crop}/refresh")
async def refresh(request: Request, crop: str, version: int = Form(0), focal: str = Form(""), method: str = Form("local")):
    main, model = _context(request, crop)
    snapshot = _snapshot(main, model)
    if method not in {"local", "ai"}:
        raise HTTPException(422, "Choose a supported review method.")
    if focal and _profiles(main, snapshot).get(focal, {}).get("kind") not in {"company", "retailer", "breeding_program"}:
        raise HTTPException(422, "Choose a focal organization from the selected evidence scope.")
    completer = None
    if method == "ai":
        if not _model_enabled():
            raise HTTPException(403, "Public-source model generation is disabled for this runtime.")
        from app.services.ai_gateway.untrusted_complete import complete_untrusted_json
        completer = complete_untrusted_json
    store = _store(main, create=True)
    old = store.get(service.scope_key(snapshot["scope"]))
    if version != (old["version"] if old else 0):
        raise HTTPException(409, "The review changed. Reload before refreshing it.")
    review = await run_in_threadpool(service.prepare, snapshot, focal=focal, completer=completer)
    try:
        service.save_draft(store, review, _actor(main, request), version)
    except living.Conflict as exc:
        raise HTTPException(409, str(exc)) from exc
    return RedirectResponse(_paths(snapshot["scope"])["back_href"], status_code=303)


@router.post("/strategy-reviews/berries/{crop}/review")
def review_decision(request: Request, crop: str, version: int = Form(...), action: str = Form(...),
                    notes: str = Form(""), framework: str = Form(""), citations: list[str] = Form(default=[])):
    main, model = _context(request, crop)
    snapshot = _snapshot(main, model)
    store = _store(main)
    if store is None:
        raise HTTPException(409, "Generate and save a review before recording a decision.")
    try:
        service.record_decision(store, snapshot, _actor(main, request), version, action, notes, framework, citations)
    except living.Conflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return RedirectResponse(_paths(snapshot["scope"])["back_href"], status_code=303)


@router.get("/strategy-reviews/berries/{crop}/history")
def history(request: Request, crop: str, version: int | None = None):
    main = _review_main(request, crop)
    try:
        scope = service.scope_for({"filters": filters_for(request.query_params, "" if crop == "all" else crop)})
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    store = _store(main)
    rows = store.history(service.scope_key(scope)) if store else []
    selected = next((row for row in rows if version is None or row["version"] == version), None)
    if not selected:
        raise HTTPException(404, "No such Strategy Review revision for this scope.")
    selected_review = json.loads(selected["body"])
    revisions = [{"version": row["version"], "actor": row["actor"], "at": row["at"],
                  "state": json.loads(row["body"])["state"]} for row in rows]
    return main.templates.TemplateResponse(request=request, name="berry_strategy_history.html",
        context={"strategy": _present(main, selected_review), "revisions": revisions, "strategy_history": True, "authoring_mode": True},
        headers={"Cache-Control": "private, no-store"})
