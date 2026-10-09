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
    records = digest.source_records(main.published_evidence(), main.INBOX_DIR, include_private=main.AUTHORING_MODE)
    if main.AUTHORING_MODE:
        # Resolve only personally retained draft IDs here. Opening an article
        # does not add the entire publication backlog to the user's Digest.
        reading = analyst_queue.load_state(main.INBOX_DIR)
        for item_id in set(context["state"].get("decisions", {})) | set(reading.get("reading", {})):
            if digest.inclusion({"id": item_id}, context["state"], reading):
                record = personal_source_record(item_id, records=records)
                if record is not None:
                    records[item_id] = record
                else:
                    records.pop(item_id, None)
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


def personal_source_record(item_id: str, *, records=None):
    """Selected pending source lookup; never load all draft bodies in a Reader."""
    from app import main
    from app.services.variety_universe.article_sources import active_publication_record, inactive_publication_record
    if not feed_first.SAFE_ID_RE.fullmatch(item_id):
        return None
    if records is None:
        records = digest.source_records(main.published_evidence(), main.INBOX_DIR,
                                        include_private=main.AUTHORING_MODE)
    record = records.get(item_id)
    if record is not None and record.get("status") == "published":
        return record  # Never replace canonical prose with a pending version.
    if main.AUTHORING_MODE:
        original = main.get_draft(item_id)
        if original and original.get("id") == item_id and inactive_publication_record(original):
            return None
        draft = active_publication_record(original)
        if (draft is not None and draft["id"] == item_id
                and (record is None or draft.get("source_url") == record.get("source_url"))):
            return draft
    return record


def known_story(item_id: str, records, context, reading):
    if not feed_first.SAFE_ID_RE.fullmatch(item_id):
        raise HTTPException(400, "Invalid story")
    record = personal_source_record(item_id, records=records)
    if record is not None:
        return record
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
    from app.services.statement_workspace import present_statements
    if main.AUTHORING_MODE:
        record = merge_capture(record, load_capture(main.INBOX_DIR, str(record["id"])))
    context = main._feed_first_world() if main.AUTHORING_MODE else {"entities": main.all_entities(), "state": feed_first.empty_state()}
    entities = {str(row["id"]): row for row in context["entities"] if row.get("id")}
    card = feed_first.present_item(record, entities_by_id=entities, state=context["state"], filters=feed_first.parse_filters({}))
    card["entities"] = [row for row in card["entities"] if (entities.get(row["id"]) or {}).get("entity_type") in {"company", "brand", "research_program"}]
    content = reader_content(record)
    paragraphs = [] if content["contaminated"] else display_reader_passages([row["text"] for row in article_paragraphs(record)])
    if not paragraphs and content["body"] and content["state"] in {"body_available", "body_partial"}:
        paragraphs = display_reader_passages([content["body"]])
    if paragraphs == [content["summary"]]:
        paragraphs = []  # A syndicated synopsis is not the original article.
    document_blocks = record.get("reader_document_blocks", []) if main.AUTHORING_MODE and paragraphs else []
    card["source_url"] = card["source_url"] if is_public_http_url(card["source_url"]) else ""
    entry = ((analyst_queue.load_state(main.INBOX_DIR).get("reading") or {}).get(str(record["id"])) or {}) if main.AUTHORING_MODE else {}
    statement_reviews = present_statements(card["statements"], {str(record["id"]): record}, context["entities"], return_to="/statements") if main.AUTHORING_MODE else []
    article_varieties = []
    if main.AUTHORING_MODE and paragraphs:
        from app.services.variety_universe.candidates import load_variety_candidates
        from app.services.variety_universe.corpus_discovery import build_discovered_candidates, source_catalog_coverage
        report = build_discovered_candidates(
            varieties=[row for row in entities.values() if row.get("entity_type") == "variety"],
            entities=list(entities.values()), published_evidence=[], facts=[],
            existing_candidates=load_variety_candidates(main.INBOX_DIR), source_text_records=[record],
        )
        article_varieties = source_catalog_coverage(report).get(str(record["id"]), [])
    return_to = request.query_params.get("return_to") or "/digest"
    return_to = return_to if urlsplit(return_to).path == "/statements" and not urlsplit(return_to).netloc and not urlsplit(return_to).scheme else "/digest"
    return {"personal_reader": True, "card": card, "record": record, "article_text": paragraphs, "document_blocks": document_blocks,
            "article_available": bool(paragraphs), "reading_entry": entry, "summary": content["summary"],
            "trusted": source_reviewed(record), "escalated_statements": escalations(main.all_facts()).get(str(record["id"]), []),
            "statement_reviews": statement_reviews, "reader_return_to": return_to,
            "article_varieties": article_varieties,
            "authoring_mode": main.AUTHORING_MODE, "static_build": False}


@router.post("/api/digest/{item_id}/capture", response_class=HTMLResponse)
def digest_capture(request: Request, item_id: str):
    require_edit(request)
    from app.services.feed_first_reader import capture_item
    main, context, records, _ = world()
    record = known_story(item_id, records, context, analyst_queue.load_state(main.INBOX_DIR))
    if record.get("missing_source"):
        raise HTTPException(404, "Source no longer available")
    if request.query_params.get("refresh") == "1":
        capture = capture_item(main.INBOX_DIR, record, refresh=True)
    else:
        capture = capture_item(main.INBOX_DIR, record)
    view = reader_context(request, record)
    if isinstance(capture, dict) and not capture.get("ok"):
        view["capture_message"] = "Source text could not be loaded. Any previously captured text is still shown; you can try again or read at the publisher."
    return main.templates.TemplateResponse(request=request, name="_personal_reader.html", context=view)


def source_variety_report(item_id: str, *, existing_candidates=None):
    """Read one selected, already-captured source; no fetches or writes."""
    from app.services.feed_first_reader import load_capture, merge_capture
    from app.services.variety_universe.corpus_discovery import build_discovered_candidates

    main, context, records, _ = world()
    record = known_story(item_id, records, context, analyst_queue.load_state(main.INBOX_DIR))
    if record.get("missing_source"):
        raise HTTPException(404, "Source no longer available")
    record = merge_capture(record, load_capture(main.INBOX_DIR, item_id))
    entities = main.all_entities()
    report = build_discovered_candidates(
        varieties=[e for e in entities if e.get("entity_type") == "variety"], entities=entities,
        published_evidence=[], facts=[], existing_candidates=(existing_candidates if existing_candidates is not None
            else main.variety_candidate_universe()[1]),
        source_text_records=[record],
    )
    reasons = {row["reason"] for row in report["exclusions"]}
    if "source_text_unavailable" in reasons:
        raise HTTPException(422, "Readable article text is unavailable. Load available text in the Reader first, or use manual intake.")
    if "source_text_too_large" in reasons:
        raise HTTPException(422, "This document is too large for the quick name check. Use manual intake to review its variety lists.")
    return main, report


@router.post("/varieties/discover-source/{item_id}")
def discover_source_varieties(request: Request, item_id: str):
    """Explicit, single-source identity discovery; never capture or approve."""
    require_edit(request)
    from app import main
    from app.services.variety_universe.candidates import load_variety_candidates, persist_variety_candidates
    # Derived rows are visible before this action. Compare against persisted
    # decisions only so "keep" can retain newly discovered names additively.
    main, report = source_variety_report(item_id, existing_candidates=load_variety_candidates(main.INBOX_DIR))
    persist_variety_candidates(report["candidates"], inbox_dir=main.INBOX_DIR)
    return RedirectResponse('/varieties/candidates?' + urlencode({
        'source':item_id, 'discovery':'source-text'}), status_code=303)
