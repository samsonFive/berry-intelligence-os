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
from app.services import berry_strategy_inputs as inputs
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


def _profiles(main, snapshot, focal=""):
    linked = {key for source in snapshot["sources"].values() for key in source["entity_ids"]}
    if focal:
        linked.add(focal)
    store = _store(main)
    if store:
        linked.update(row["entity_id"] for row in inputs.scoped_inputs(store, snapshot["scope"]))
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
    selected = snapshot.get("analyst_inputs", [])
    company_frameworks = set()
    if review.get("focal") and selected:
        company_frameworks.add("swot_tows")
        if any(row["category"] == "capability" for row in selected):
            company_frameworks.add("vrio")
    input_query = {key: scope[key] for key in ("crop", "region") if scope[key]}
    if review.get("focal"):
        input_query["entity_id"] = review["focal"]
    input_href = "/strategy-inputs" + ("?" + urlencode(input_query) if input_query else "")
    return {**_paths(scope), "review": review, "stale": stale, "profiles": _profiles(main, snapshot, review.get("focal", "")),
            "scope_label": CROPS.get(scope["crop"], "All four berries") + " · " + REGIONS.get(scope["region"], "All regions"),
            "framework_labels": service.FRAMEWORKS, "company_frameworks": service.COMPANY_FRAMEWORKS,
            "correction_frameworks": [key for key in service.FRAMEWORKS
                                      if key not in service.COMPANY_FRAMEWORKS or key in company_frameworks],
            "input_href": input_href, "vrio_fields": inputs.VRIO_FIELDS,
            "criteria": CRITERIA, "model_enabled": _model_enabled()}


def _snapshot(main, model, focal=""):
    store = _store(main)
    approved = inputs.scoped_inputs(store, service.scope_for(model)) if store else []
    return service.snapshot_for(model, opportunities=load_opportunities(main.INBOX_DIR),
                                analyst_inputs=approved, focal=focal)


def panel(main, model):
    if not main.AUTHORING_MODE:
        return None
    store = _store(main)
    stored = store.get(service.scope_key(service.scope_for(model))) if store else None
    focal = stored.get("focal", "") if stored else ""
    snapshot = _snapshot(main, model, focal)
    stale = bool(stored and stored["basis"] != living.digest(snapshot))
    review = stored if stored and not stale else service.prepare(snapshot, focal=focal)
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
    snapshot = _snapshot(main, model, focal)
    if method not in {"local", "ai"}:
        raise HTTPException(422, "Choose a supported review method.")
    if focal and focal not in _input_entities(main):
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
                    notes: str = Form(""), framework: str = Form(""), citations: list[str] = Form(default=[]),
                    focal: str | None = Form(None)):
    main, model = _context(request, crop)
    store = _store(main)
    if store is None:
        raise HTTPException(409, "Generate and save a review before recording a decision.")
    current = store.get(service.scope_key(service.scope_for(model)))
    selected_focal = focal if focal is not None else (current or {}).get("focal", "")
    if selected_focal and selected_focal not in _input_entities(main):
        raise HTTPException(422, "Choose an existing focal organization before recording a decision.")
    snapshot = _snapshot(main, model, selected_focal)
    try:
        service.record_decision(store, snapshot, _actor(main, request), version, action, notes, framework, citations,
                                focal=selected_focal)
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


def _input_entities(main):
    return {key: row for key, row in main.entity_index().items()
            if row.get("entity_type") in {"company", "retailer", "breeding_program"}}


def _input_page(request, main, *, selected=None, values=None, error="", status=200, historical=False, token="",
                submitted_version=None):
    scope = {"crop": str(request.query_params.get("crop") or ""),
             "region": str(request.query_params.get("region") or "")}
    if (scope["crop"] and scope["crop"] not in CROPS) or (scope["region"] and scope["region"] not in REGIONS):
        raise HTTPException(422, "Choose a supported crop and macroregion.")
    entities = _input_entities(main)
    company = str(request.query_params.get("entity_id") or "")
    if company and company not in entities:
        raise HTTPException(422, "Choose an existing organization.")
    store = _store(main)
    rows = inputs.scoped_inputs(store, scope, [company] if company else None, approved_only=False) if store else []
    revisions = store.history(selected["id"]) if store and selected else []
    form = values if values is not None else selected or {
        "entity_id": company, **scope, "category": "capability", "vrio": {},
    }
    crop = form.get("crop", "")
    region = form.get("region", "")
    back = "/landscapes/global" + (f"/{crop}" if crop else "")
    if region:
        back += "?" + urlencode({"region": region})
    return main.templates.TemplateResponse(request=request, name="berry_strategy_inputs.html", status_code=status,
        context={"authoring_mode": True, "entities": entities, "inputs": rows, "selected": selected,
                 "form": form, "form_version": submitted_version if submitted_version is not None else (selected or {}).get("version", 0),
                 "error": error, "historical": historical, "conflict": status == 409,
                 "revisions": [{"version": row["version"], "actor": row["actor"], "at": row["at"],
                                "state": json.loads(row["body"])["state"]} for row in revisions],
                 "categories": inputs.CATEGORIES, "vrio_fields": inputs.VRIO_FIELDS, "vrio_values": inputs.VRIO_VALUES,
                 "crops": CROPS, "regions": REGIONS, "scope": scope, "company": company,
                 "back_href": back + "#berry-strategy-review", "token": token or living.ident("strategy-request-")},
        headers={"Cache-Control": "private, no-store"})


@router.get("/strategy-inputs")
def input_list(request: Request):
    main = _review_main(request, "all")
    return _input_page(request, main)


@router.get("/strategy-inputs/{input_id}")
def input_detail(request: Request, input_id: str, version: int | None = None):
    main = _review_main(request, "all")
    store = _store(main)
    selected = store.get(input_id) if store and input_id.startswith("berry-strategy-input-") else None
    if not selected or selected.get("kind") != inputs.KIND:
        raise HTTPException(404, "Strategy input not found.")
    historical = version is not None
    if historical:
        revision = next((row for row in store.history(input_id) if row["version"] == version), None)
        if not revision:
            raise HTTPException(404, "Strategy input revision not found.")
        selected = json.loads(revision["body"])
    return _input_page(request, main, selected=selected, historical=historical)


@router.post("/strategy-inputs")
async def input_save(request: Request, version: int = Form(0), input_id: str = Form(""), token: str = Form(...)):
    main = _review_main(request, "all", edit=True)
    form = await request.form()
    payload = {key: str(form.get(key) or "") for key in
               ("entity_id", "crop", "region", "title", "statement", "category", "reference", "observed_date", "source_url")}
    if input_id:
        payload["id"] = input_id
    payload["vrio"] = {key: {"judgment": str(form.get(f"vrio_{key}") or "unknown"),
                            "rationale": str(form.get(f"vrio_{key}_rationale") or "")}
                       for key in inputs.VRIO_FIELDS}
    store = _store(main, create=True)
    selected = store.get(input_id) if input_id.startswith(inputs.PREFIX) else None
    if selected and selected.get("kind") != inputs.KIND:
        selected = None
    try:
        saved = inputs.save_input(store, payload, _actor(main, request), _input_entities(main), expected=version, token=token)
    except living.Conflict as exc:
        return _input_page(request, main, selected=selected, values=payload, error=str(exc), status=409, token=token,
                           submitted_version=version)
    except ValueError as exc:
        if selected and selected["version"] != version:
            return _input_page(request, main, selected=selected, values=payload,
                               error="The input changed. Open the current input to compare before saving.",
                               status=409, token=token, submitted_version=version)
        return _input_page(request, main, selected=selected, values=payload, error=str(exc), status=422, token=token,
                           submitted_version=version)
    return RedirectResponse(f"/strategy-inputs/{saved['id']}", status_code=303)


@router.post("/strategy-inputs/{input_id}/decision")
def input_decision(request: Request, input_id: str, version: int = Form(...), action: str = Form(...), token: str = Form(...)):
    main = _review_main(request, "all", edit=True)
    store = _store(main)
    selected = store.get(input_id) if store and input_id.startswith("berry-strategy-input-") else None
    if not selected or selected.get("kind") != inputs.KIND:
        raise HTTPException(404, "Strategy input not found.")
    try:
        inputs.decide_input(store, input_id, _actor(main, request), _input_entities(main), version, action, token=token)
    except living.Conflict as exc:
        return _input_page(request, main, selected=selected, error=str(exc), status=409)
    except ValueError as exc:
        return _input_page(request, main, selected=selected, error=str(exc), status=422)
    return RedirectResponse(f"/strategy-inputs/{input_id}", status_code=303)
