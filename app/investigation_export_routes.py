"""Authenticated explicit preview-to-PDF investigation output; no new store."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictStr

from app.services import investigation_api as api
from app.services import investigation_export as service

router = APIRouter(prefix="/api/investigations/v1/export")


class ExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    context: dict[str, StrictStr]
    section_ids: list[StrictStr] = Field(min_length=1, max_length=6)
    include_demo: StrictBool = False
    expected_content_hash: StrictStr | None = Field(default=None, max_length=64)


def _private():
    from app import main
    if not main.AUTHORING_MODE:
        raise HTTPException(403, "Investigation exports require the private analyst workspace.")


@router.post("/preview")
def preview(request: ExportRequest):
    _private()
    try:
        result = service.preview(api.load_world(), request.context, request.section_ids, request.include_demo)
        return JSONResponse(result, headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})
    except ValueError as exc:
        raise HTTPException(422, str(exc)[:500]) from exc


@router.post("/pdf")
def pdf(request: ExportRequest):
    _private()
    try:
        content, digest = service.pdf(api.load_world(), request.context, request.section_ids,
                                      request.include_demo, request.expected_content_hash)
        return Response(content, media_type="application/pdf", headers={
            "Cache-Control": "private, no-store", "Content-Disposition": 'attachment; filename="berry-investigation.pdf"',
            "X-Content-Type-Options": "nosniff", "X-Investigation-Content-Hash": digest,
        })
    except service.ContentChangedError as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)[:500]) from exc


def register(app):
    app.include_router(router)
