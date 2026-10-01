"""Local analyst Digest routes; no collection or paid research on page loads."""
from __future__ import annotations

from urllib.parse import urlencode, urlsplit

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.services import analyst_queue, feed_first, personal_digest as digest

router = APIRouter()


def world():
    from app import main
    context = main._feed_first_world()
    records = digest.source_records(main.published_evidence(), main.INBOX_DIR)
    entities = {str(row["id"]): row for row in context["entities"] if row.get("id")}
    return main, context, records, entities


def require_edit(request: Request):
    from app import main
    if not main.AUTHORING_MODE:
        raise HTTPException(403, "Personal changes require the local analyst workspace")
    origin = request.headers.get("origin")
    if origin and urlsplit(origin).netloc != request.url.netloc:
        raise HTTPException(403, "Use this workspace to make changes")
    if request.headers.get("sec-fetch-site") == "cross-site":
        raise HTTPException(403, "Use this workspace to make changes")


def return_path(value: str) -> str:
    parts = urlsplit(value)
    if parts.scheme or parts.netloc or parts.path != "/digest":
        return "/digest"
    return "/digest" + ("?" + parts.query if parts.query else "")


@router.get("/digest", response_class=HTMLResponse)
def personal_digest_page(request: Request):
    main, context, records, entities = world()
    try:
        model = digest.digest_model(records=records, entities=entities, state=context["state"],
                                    reading=analyst_queue.load_state(main.INBOX_DIR), params=dict(request.query_params))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    query = dict(request.query_params)
    query.pop("story", None)
    model["return_to"] = "/digest" + ("?" + urlencode(query) if query else "")
    model["pagination"] = {number: "/digest?" + urlencode({**query, "page": number}) for number in (model["page"] - 1, model["page"] + 1)}
    retained_members = {key for row in model["lists"] for key in row.get("company_ids", [])}
    return main.templates.TemplateResponse(request=request, name="personal_digest.html", context={
        **model, "authoring_mode": main.AUTHORING_MODE, "static_build": False,
        "companies": sorted([row for row in entities.values() if row.get("entity_type") == "company" or row.get("id") in retained_members], key=lambda row: row.get("name", "").casefold()),
        "berry_choices": feed_first.CROP_LABELS,
        "countries": sorted([row for row in entities.values() if row.get("entity_type") == "geography"], key=lambda row: row.get("name", "")),
    })


@router.post("/digest/lists")
async def digest_lists(request: Request):
    require_edit(request)
    main, context, _, entities = world()
    form = await request.form()
    retained_members = {member for group in context["state"].get("company_lists", {}).values() for member in group.get("company_ids", [])}
    try:
        digest.edit_list(main.INBOX_DIR, action=str(form.get("action") or ""), list_id=str(form.get("list_id") or ""),
                         name=str(form.get("name") or ""), company_ids=[str(value) for value in form.getlist("company_ids")],
                         allowed_companies={key for key, row in entities.items() if row.get("entity_type") == "company" or key in retained_members})
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return RedirectResponse(return_path(str(form.get("return_to") or "")) + "#subscriptions", status_code=303)


def known_story(item_id: str, records, context, reading):
    if not feed_first.SAFE_ID_RE.fullmatch(item_id):
        raise HTTPException(400, "Invalid story")
    if item_id in records:
        return records[item_id]
    if feed_first.decision_for(item_id, context["state"])["saved"] or item_id in reading.get("reading", {}):
        return {"id": item_id, "missing_source": True}
    raise HTTPException(404, "Story not found")


@router.post("/digest/stories/{item_id}")
async def digest_story_action(request: Request, item_id: str):
    require_edit(request)
    main, context, records, _ = world()
    json_request = request.headers.get("content-type", "").startswith("application/json")
    payload = await request.json() if json_request else await request.form()
    record = known_story(item_id, records, context, analyst_queue.load_state(main.INBOX_DIR))
    action = str(payload.get("action") or "")
    try:
        if action in {"save", "unsave", "useful", "not_relevant", "clear_feedback"}:
            digest.set_personal_decision(main.INBOX_DIR, item_id, action)
        elif action in {"start", "reopen", "mark_read", "dismiss", "keep", "set_priority"}:
            analyst_queue.apply_action(main.INBOX_DIR, dimension="reading", item_id=item_id, action=action,
                                       reviewer=main.session_username(request) or main.review_username() or "",
                                       subject=record, reading_priority=str(payload.get("priority") or "none"))
        elif action == "location":
            digest.save_reader_location(main.INBOX_DIR, item_id, mode=str(payload.get("mode") or ""), position=payload.get("position"))
        else:
            raise ValueError("Unknown reading action")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if json_request:
        return JSONResponse({"ok": True, "decision": feed_first.decision_for(item_id, feed_first.load_state(main.INBOX_DIR)),
                             "progress": analyst_queue.reading_state(item_id, analyst_queue.load_state(main.INBOX_DIR))})
    return RedirectResponse(return_path(str(payload.get("return_to") or "")), status_code=303)


@router.post("/digest/complete")
async def digest_complete_selected(request: Request):
    require_edit(request)
    main, context, records, _ = world()
    form = await request.form()
    ids = list(dict.fromkeys(str(value) for value in form.getlist("item_ids")))
    if not ids or len(ids) > 36:
        raise HTTPException(400, "Select 1–36 stories")
    reading = analyst_queue.load_state(main.INBOX_DIR)
    selected = [known_story(item_id, records, context, reading) for item_id in ids]
    if any(not digest.inclusion(row, context["state"], reading) for row in selected):
        raise HTTPException(400, "Select stories in your Digest")
    for record in selected:
        analyst_queue.apply_action(main.INBOX_DIR, dimension="reading", item_id=record["id"], action="mark_read",
                                   subject=record, reviewer=main.session_username(request) or main.review_username() or "")
    return RedirectResponse(return_path(str(form.get("return_to") or "")), status_code=303)


def reader_context(request: Request, record: dict):
    from app import main
    from app.services.feed_first_reader import load_capture, merge_capture, display_reader_passages, is_public_http_url
    from app.services.intelligence_feed import article_paragraphs
    from app.services.source_body import reader_content
    from app.services.news_workspace import source_reviewed, escalations
    record = merge_capture(record, load_capture(main.INBOX_DIR, str(record["id"])))
    context = main._feed_first_world()
    entities = {str(row["id"]): row for row in context["entities"] if row.get("id")}
    card = feed_first.present_item(record, entities_by_id=entities, state=context["state"], filters=feed_first.parse_filters({}))
    card["entities"] = [row for row in card["entities"] if (entities.get(row["id"]) or {}).get("entity_type") in {"company", "brand", "research_program"}]
    content = reader_content(record)
    paragraphs = [] if content["contaminated"] else display_reader_passages([row["text"] for row in article_paragraphs(record)])
    if paragraphs == [content["summary"]]:
        paragraphs = []  # A syndicated synopsis is not the original article.
    card["source_url"] = card["source_url"] if is_public_http_url(card["source_url"]) else ""
    entry = (analyst_queue.load_state(main.INBOX_DIR).get("reading") or {}).get(str(record["id"])) or {}
    return {"personal_reader": True, "card": card, "record": record, "article_text": paragraphs,
            "article_available": bool(paragraphs), "reading_entry": entry, "summary": content["summary"],
            "trusted": source_reviewed(record), "escalated_statements": escalations(main.all_facts()).get(str(record["id"]), []),
            "authoring_mode": main.AUTHORING_MODE, "static_build": False}


@router.post("/api/digest/{item_id}/capture", response_class=HTMLResponse)
def digest_capture(request: Request, item_id: str):
    require_edit(request)
    from app.services.feed_first_reader import capture_item
    main, context, records, _ = world()
    record = known_story(item_id, records, context, analyst_queue.load_state(main.INBOX_DIR))
    if record.get("missing_source"):
        raise HTTPException(404, "Source no longer available")
    capture_item(main.INBOX_DIR, record)
    return main.templates.TemplateResponse(request=request, name="_personal_reader.html", context=reader_context(request, record))
