"""Private read-only native learning entry and selected consumption APIs."""
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from app.services import experience_learning as service

router = APIRouter(prefix="/api/investigations/v1")
PRIVATE_HEADERS = {"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"}


def _response(request, kind=None, key=None):
    from app import main
    if not main.AUTHORING_MODE:
        raise HTTPException(403, "Learning consumption requires the private analyst workspace.")
    try:
        selection = service.normalize_selection(request.query_params)
        revision = request.query_params.get("revision", "0")
        if not revision.isdigit() or len(revision) > 10:
            raise ValueError("Investigation revision must be a non-negative integer.")
        catalog = service.load_catalog(main.INBOX_DIR)
        return_to = request.query_params.get("return_to", "")
        data = (service.selected_data(catalog, kind, key, return_to=return_to) if kind else
                service.learning_data(catalog, selection, return_to=return_to))
        scoped = selection if not kind else selection | {"kind": kind, "id": key}
        return JSONResponse({"api_v": 1, "request_id": uuid4().hex, "revision": int(revision),
                             "scope_key": service.scope_key(scoped), "applied_scope": service.applied_scope(scoped),
                             "issues": catalog["issues"], "data": data}, headers=PRIVATE_HEADERS)
    except ValueError as exc:
        raise HTTPException(422, str(exc)[:500]) from exc
    except LookupError as exc:
        raise HTTPException(404, str(exc)[:500]) from exc
    except OSError as exc:
        raise HTTPException(409, "The learning library changed or became unavailable while reading. Reload before opening it again.") from exc


@router.get("/learning")
def learning(request: Request):
    return _response(request)


@router.get("/learning/{kind}/{key}")
def learning_entry(request: Request, kind: str, key: str):
    return _response(request, kind, key)


def register(app):
    app.include_router(router)
