from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.personal_digest_routes import require_edit
from app.services import operator_variety_seed as seeds

router = APIRouter()


@router.get("/variety-seeds", response_class=HTMLResponse)
def variety_seeds(request: Request, company: str = "", berry: str = "", letter: str = "", q: str = ""):
    from app import main
    context = seeds.workspace(main.INBOX_DIR, main.DATA_DIR, {row["id"]: row for row in main.all_entities()},
                              company=company, berry=berry, letter=letter.upper()[:1], q=q)
    return main.templates.TemplateResponse(request=request, name="variety_seeds.html",
                                           context={**context, "authoring_mode": main.AUTHORING_MODE, "static_build": False})


@router.post("/variety-seeds/import")
def import_seeds(request: Request):
    require_edit(request)
    from app import main
    try:
        seeds.install(main.INBOX_DIR, main.DATA_DIR, {row["id"]: row for row in main.all_entities()})
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return RedirectResponse("/variety-seeds", status_code=303)
