"""Private photo corrections reuse the existing profile history and edit guard."""
from datetime import date
from urllib.parse import urlencode, urlsplit

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.personal_digest_routes import require_edit
from app.services import company_directory, variety_photos
from app.services.variety_portfolio_coverage import load_portfolio_observations

router = APIRouter()


def photo_return(kind, target_id, value=""):
    path = f"/entities/variety/{target_id}" if kind == "catalog" else "/varieties/candidates"
    fallback = path if kind == "catalog" else path + "#" + target_id
    try:
        parts = urlsplit(str(value or ""))
    except ValueError:
        return fallback
    if parts.scheme or parts.netloc or parts.path != path:
        return fallback
    return path + ("?" + parts.query if parts.query else "") + ("#" + target_id if kind == "candidate" else "")


def photo_context(kind, target_id):
    from app import main
    if not main.AUTHORING_MODE:
        raise HTTPException(403, "Photo editing requires the analyst workspace")
    if kind not in {"catalog", "candidate"}:
        raise HTTPException(404, "Variety not found")
    varieties, candidates, _ = main.variety_candidate_universe()
    target = next((row for row in (candidates if kind == "candidate" else varieties) if row["id"] == target_id), None)
    if target is None:
        raise HTTPException(404, "Variety not found")
    try:
        sources = load_portfolio_observations(main.DATA_DIR)
        sourced = variety_photos.source_photos(target, sources=sources, candidate=kind == "candidate", varieties=varieties)
        private = company_directory.load_profiles(main.INBOX_DIR)
        profile = private["profiles"].get(target_id) or {"revision": 0}
        photos = variety_photos.gallery(target, sourced=sourced, profile=profile, authoring=True)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return main, target, sourced, profile, photos


@router.get("/varieties/photos/{kind}/{target_id}")
def photo_page(request: Request, kind: str, target_id: str):
    main, target, sourced, profile, photos = photo_context(kind, target_id)
    hidden = set((profile.get("variety_photo_overrides") or {})) - {row["id"] for row in photos}
    return main.templates.TemplateResponse(request=request, name="variety_photos.html", context={
        "target": target, "kind": kind, "photos": photos, "photo_gallery": photos, "profile": profile,
        "hidden_photos": sorted(hidden), "reuse_choices": variety_photos.REUSE, "photo_kinds": variety_photos.KINDS,
        "photo_berries": {key: main.BERRIES[key] for key in ([target.get("berry_id")] if kind == "candidate" else target.get("berry_ids") or []) if key in main.BERRIES},
        "today": date.today().isoformat(), "authoring_mode": True, "static_build": False,
        "back_url": photo_return(kind, target_id, request.query_params.get("return_to", "")),
    })


@router.post("/varieties/photos/{kind}/{target_id}")
async def edit_photo(request: Request, kind: str, target_id: str):
    require_edit(request)
    main, target, sourced, _, _ = photo_context(kind, target_id)
    try:
        variety_photos.edit(main.INBOX_DIR, target=target, payload=dict(await request.form()), sourced=sourced,
                            reviewer=main.session_username(request) or main.review_username() or "")
    except ValueError as exc:
        raise HTTPException(409 if "changed in another" in str(exc) else 400, str(exc)) from exc
    back = photo_return(kind, target_id, request.query_params.get("return_to", ""))
    return RedirectResponse(f"/varieties/photos/{kind}/{target_id}?" + urlencode({"saved": "1", "return_to": back}), status_code=303)
