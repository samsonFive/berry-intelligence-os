"""Private, versioned read APIs for the persistent investigation application."""
import json
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from app.services import investigation_api as service

router = APIRouter(prefix="/api/investigations/v1")


def _private():
    from app import main
    if not main.AUTHORING_MODE:
        raise HTTPException(403, "Investigations require the private analyst workspace.")


def response(request, module):
    _private()
    try:
        params = ({"ctx_v": request.query_params.get("ctx_v", "1"), "q": request.query_params.get("q", ""),
                   "q_scope": "catalog"} if module == "options" else request.query_params)
        context, issues = service.normalize_context(params)
        revision_text = request.query_params.get("revision", "0")
        if not revision_text.isdigit() or len(revision_text) > 10:
            raise ValueError("Investigation revision must be a non-negative integer.")
        page = service.pagination(request.query_params, default_limit=10 if module == "monitoring" else 36) if module in {"news", "monitoring"} else {}
        world = service.load_catalog_world() if module == "options" else service.load_world()
        bundle = None if module == "options" else service.base_bundle(world, context)
        if bundle is not None and module not in {"news", "monitoring"}:
            issues += service.selection_issues(world, context, bundle)
        if module == "landscape" and context["geo_basis"] != "company_connections":
            issues.append(service.issue("unsupported_in_module", "geo_basis",
                "This analytical field supports recorded company/genetic connections. Source geography applies to developments; growing and rights need their dedicated views."))
        if module == "options":
            data = service.catalog_options(world, context)
        elif module == "landscape":
            data = service.landscape_data(world, context, bundle)
        elif module == "comparison":
            data = service.comparison_data(world, context)
        elif module == "developments":
            data = service.developments_data(world, context, bundle)
        elif module == "monitoring":
            data = service.monitoring_data(world, context, bundle, **page)
        elif module == "news":
            data = service.news_data(world, context, bundle, **page)
        else:
            data = service.detail_data(world, context, bundle, request.query_params.get("type", ""),
                                       request.query_params.get("id", ""), request=request)
        return JSONResponse({"api_v": 1, "request_id": uuid4().hex, "revision": int(revision_text),
                             "scope_key": service.scope_key(context),
                             "applied_scope": service.module_scope(context, module),
                             "issues": issues, "data": data}, headers={"Cache-Control": "private, no-store"})
    except ValueError as exc:
        raise HTTPException(422, str(exc)[:500]) from exc
    except LookupError as exc:
        raise HTTPException(404, str(exc)[:500]) from exc


@router.get("/landscape")
def landscape(request: Request):
    return response(request, "landscape")


@router.get("/options")
def options(request: Request):
    return response(request, "options")


@router.get("/comparison")
def comparison(request: Request):
    return response(request, "comparison")


@router.get("/detail")
def detail(request: Request):
    return response(request, "detail")


@router.get("/developments")
def developments(request: Request):
    return response(request, "developments")


@router.get("/monitoring")
def monitoring(request: Request):
    return response(request, "monitoring")


@router.get("/news")
def news(request: Request):
    return response(request, "news")


@router.post("/companies/{entity_id}/tier")
async def assign_company_tier(request: Request, entity_id: str):
    _private()
    from app.personal_digest_routes import require_edit
    from app.services import investigation_tiers
    require_edit(request)
    if request.headers.get("sec-fetch-site") not in {None, "same-origin", "none"}:
        raise HTTPException(403, "Use this workspace to make changes")
    if request.headers.get("content-type", "").split(";", 1)[0].strip().casefold() != "application/json":
        raise HTTPException(415, "Supply an application/json tier change.")
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 2048:
            raise HTTPException(413, "Supply only an assigned tier and its expected value.")
    def object_fields(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Supply each tier field once.")
            result[key] = value
        return result
    try:
        payload = json.loads(body, object_pairs_hook=object_fields)
        if not isinstance(payload, dict) or set(payload) - {"tier", "expected_tier"} or "tier" not in payload:
            raise ValueError("Supply only tier and optional expected_tier.")
        if "expected_tier" in payload and not isinstance(payload["expected_tier"], str):
            raise ValueError("Supply the current assigned tier before saving.")
        if not service.ID_RE.fullmatch(entity_id):
            raise ValueError("Choose a canonical company identifier.")
        world = service.load_catalog_world()
        data = investigation_tiers.assign(world.main.INBOX_DIR, entity_id=entity_id, tier=payload["tier"],
            expected_tier=payload.get("expected_tier"), allowed=set(service.monitoring_companies(world)))
    except investigation_tiers.TierConflict as exc:
        raise HTTPException(409, {"message": str(exc), "code": "tier_conflict", **exc.data}) from exc
    except (TypeError, ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(422, str(exc)[:500]) from exc
    except LookupError as exc:
        raise HTTPException(404, str(exc)[:500]) from exc
    return JSONResponse({"api_v": 1, "request_id": uuid4().hex, "data": data},
                        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


def register(app):
    app.include_router(router)
