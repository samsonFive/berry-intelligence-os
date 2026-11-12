"""Persistent application entry and explicit, revision-checked investigation saves.

The client bundle contains code only. Authentication and private store access stay
in FastAPI; no legacy page controller is injected into the React application.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

from app.personal_digest_routes import require_edit
from app.services import landscape_workspace as workspace

router = APIRouter()
SURFACES = {"landscape", "briefing", "workspaces", "learn"}
PRIVATE_HEADERS = {"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"}


def _private_main():
    from app import main
    if not main.AUTHORING_MODE:
        raise HTTPException(403, "Investigations require the private analyst workspace")
    return main


def _saved_row(row):
    return {**{key: row[key] for key in ("id", "name", "filters", "revision", "archived")},
            "filters": workspace.investigation_filters(row),
            "updated_at": str(row.get("updated_at") or ""),
            "kind": row.get("kind", "overview"), "surface": row.get("surface", ""),
            "href": workspace.view_href(row),
            "is_investigation": str(row.get("filters", {}).get("ctx_v") or "") == "1"}


@router.get("/app", include_in_schema=False)
def app_home():
    _private_main()
    return RedirectResponse("/app/landscape", status_code=307, headers=PRIVATE_HEADERS)


@router.get("/app/{surface}", include_in_schema=False)
def experience_page(surface: str):
    main = _private_main()
    if surface not in SURFACES:
        raise HTTPException(404, "Application destination not found")
    index = Path(main.BASE_DIR) / "app" / "static" / "investigation" / "index.html"
    if not index.is_file():
        return JSONResponse({"detail": "The experience client has not been built in this checkout.",
                             "build": "Build frontend/ with its pinned dependency lockfile."},
                            status_code=503, headers=PRIVATE_HEADERS)
    return FileResponse(index, media_type="text/html", headers=PRIVATE_HEADERS)


@router.get("/api/investigations/v1/saved")
def saved_investigations():
    main = _private_main()
    try:
        rows = workspace.load_views(main.INBOX_DIR)["views"].values()
        data = sorted((_saved_row(row) for row in rows if not row["archived"]),
                      key=lambda row: (row["updated_at"], row["id"]), reverse=True)
    except (ValueError, OSError) as exc:
        raise HTTPException(409, "Saved views need attention before they can be opened") from exc
    return JSONResponse({"api_v": 1, "data": data}, headers=PRIVATE_HEADERS)


@router.get("/app/learn/{kind}/{learning_id}", include_in_schema=False)
def learning_entry(kind: str, learning_id: str):
    _private_main()
    from app.session_auth import is_investigation_path
    if not is_investigation_path(f"/app/learn/{kind}/{learning_id}"):
        raise HTTPException(404, "Learning destination not found")
    return experience_page("learn")


@router.get("/api/investigations/v1/demo/sensory")
def sensory_demonstration():
    _private_main()
    # This is a code-owned fixture, deliberately outside canonical data/ and all
    # ordinary catalog, evidence, coverage and export loaders.
    path = Path(__file__).parent / "demo_data" / "flavor" / "synthetic-overall-liking-v1.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return JSONResponse({"api_v": 1, **data}, headers=PRIVATE_HEADERS)


@router.get("/api/investigations/v1/saved/{view_id}")
def saved_investigation(view_id: str):
    main = _private_main()
    try:
        row = workspace.load_views(main.INBOX_DIR)["views"].get(view_id)
    except (ValueError, OSError) as exc:
        raise HTTPException(409, "Saved views need attention before they can be opened") from exc
    if not row or row["archived"]:
        raise HTTPException(404, "This saved view is unavailable or archived")
    return JSONResponse({"api_v": 1, "data": _saved_row(row)}, headers=PRIVATE_HEADERS)


@router.post("/api/investigations/v1/saved")
async def save_investigation(request: Request):
    main = _private_main()
    require_edit(request)
    # Bound the streamed body before parsing; request.body() would accept an
    # arbitrarily large private document even though selectors are all we save.
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 16_384:
            raise HTTPException(413, "Save only a bounded investigation selection")
    try:
        payload = json.loads(body)
        if not isinstance(payload, dict) or not isinstance(payload.get("context"), dict):
            raise ValueError("Supply an investigation context")
        from app.services.investigation_api import normalize_context
        context, issues = normalize_context(payload["context"])
        # Store references identify the row, not part of its recursively saved
        # content. An explicit save-as-new never overwrites its originating row.
        context["saved_view_id"] = context["saved_revision"] = ""
        view_id = "" if payload.get("save_as_new") is True else str(payload.get("id") or "")
        revision = "0" if not view_id else str(payload.get("revision") or "")
        row = workspace.save_view(main.INBOX_DIR, name=str(payload.get("name") or ""),
                                  filters=context, view_id=view_id, revision=revision,
                                  kind="explorer", surface="")
    except (ValueError, TypeError, UnicodeDecodeError) as exc:
        message = str(exc)
        code = 409 if "another window" in message or "original" in message else 422
        raise HTTPException(code, message) from exc
    return JSONResponse({"api_v": 1, "data": _saved_row(row), "issues": issues},
                        status_code=201 if not view_id else 200, headers=PRIVATE_HEADERS)
