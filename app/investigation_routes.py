"""Private, versioned read APIs for the persistent investigation application."""
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


def register(app):
    app.include_router(router)
