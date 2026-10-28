"""Authenticated private authoring API for living analyst documents."""
from __future__ import annotations

import json
from urllib.parse import urlsplit
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse

from app.personal_digest_routes import require_edit, personal_source_record, world
from app.services import living_workspaces as living

router = APIRouter()


@router.get("/api/workspaces/landscapes")
def landscape_choices(request: Request):
    from app.services.workspace_landscapes import choices
    main, _, _ = context(request)
    return {"landscapes": choices(main)}


@router.post("/workspaces/link-landscape")
async def link_from_landscape(request: Request):
    from app.services.workspace_landscapes import choices
    main, store, actor = context(request, True)
    form = await request.form()
    key, page_id = str(form.get("landscape_key") or ""), str(form.get("page_id") or "")
    option = next((row for row in choices(main) if row["id"] == key), None)
    page = store.get(page_id)
    if not option or not page or not page_id.startswith("wp-"):
        raise HTTPException(422, "Choose an available Landscape and workspace")
    if key not in page.get("landscape_links", []):
        page["landscape_links"] = page.get("landscape_links", []) + [key]
        checked(lambda: store.save_page(page_id, page, actor))
    return RedirectResponse(option["href"], status_code=303)


def social_observations(main):
    from app.services.social_intelligence.store import Store
    from datetime import datetime, timedelta, timezone
    return {row['id']: row for row in Store(main.INBOX_DIR).records() if row['mode'] != 'fixture' and not row.get('output_excluded')
            and datetime.fromisoformat(row['collected_at'].replace('Z', '+00:00')) + timedelta(days=row['retention_days']) >= datetime.now(timezone.utc)}


@router.post('/api/workspaces/social')
async def add_social_reference(request: Request):
    main, store, actor = context(request, True)
    payload = await body(request)
    key = payload.get('article_id')
    if set(payload) - {'article_id', 'kind', 'quote', 'page_id', 'token'} or payload.get('quote') or payload.get('kind') != 'social':
        raise HTTPException(422, 'Save a social reference without copying post text')
    if not isinstance(key, str) or not isinstance(payload.get('page_id') or 'wp-inbox', str):
        raise HTTPException(422, 'Choose a social observation and workspace')
    observation = social_observations(main).get(key)
    if not observation:
        raise HTTPException(422, 'Social observation is unavailable or is sample data')
    def create():
        with store.transaction() as db:
            replay = store.replay(db, payload.get('token'), payload)
            if replay:
                return replay
            page_id = payload.get('page_id') or 'wp-inbox'
            page = store.get(page_id, db)
            if not page and page_id == 'wp-inbox':
                page = store.put(db, 'page', {'id': page_id, 'title': 'Capture inbox', 'blocks': [], 'feed': {'mode': 'any', 'paused': True}, 'dismissed': [], 'parent_id': None}, actor)
            if not page or not page_id.startswith('wp-') or len(page['blocks']) >= 600:
                raise ValueError('Choose an available workspace with room for another item')
            block = living.Store.block('social', social_id=key, social_mode=observation['mode'])
            page['blocks'].append(block)
            page = store.put(db, 'page', page, actor, page['version'])
            result = {'page': page, 'block_id': block['id'], 'social_reference': key}
            store.remember(db, payload.get('token'), payload, result)
            return result
    return checked(create)


def context(request, mutate=False):
    from app import main
    if not main.AUTHORING_MODE:
        raise HTTPException(403, "Workspaces are private analyst material")
    if mutate:
        require_edit(request)
    store = living.Store(main.INBOX_DIR)
    store.ensure_berry_workspaces()
    store.flush()
    actor = main.session_username(request) or main.review_username() or "local analyst"
    return main, store, actor


async def body(request):
    if len(await request.body()) > 4_000_000:
        raise HTTPException(413, "Page is too large")
    try:
        payload = await request.json()
        if not isinstance(payload, dict):
            raise ValueError()
        return payload
    except (ValueError, TypeError) as exc:
        raise HTTPException(400, "Expected a JSON object") from exc


def checked(callback):
    try:
        return callback()
    except living.Conflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(422, str(exc)) from exc


def source_snapshot(main, store, article_id, source_id=None):
    if source_id:
        source = store.get(source_id)
        if source and source["id"].startswith("src-") and source["article_id"] == article_id:
            return source
        raise HTTPException(404, "Archived source not found")
    from app.services.feed_first_reader import load_capture, merge_capture
    from app.services.source_body import reader_content
    from app.services.source_reading import reviewed_original_for_reading
    record = personal_source_record(article_id)
    if record is None:
        raise HTTPException(404, "Source is unavailable in this account")
    record = reviewed_original_for_reading(record, main.INBOX_DIR)
    record = merge_capture(record, load_capture(main.INBOX_DIR, article_id))
    content = reader_content(record)
    # All stored text is rendered as text, never publisher HTML.
    text = content["body"] if content["usable_in_app"] else ""
    availability = content["state"]
    if availability == "body_available" and ((record.get("reader_capture") or {}).get("availability") in {"partial", "excerpt_only", "blocked"} or (record.get("article") or {}).get("status") in {"partial", "excerpt_only"} or (record.get("article") or {}).get("completeness") == "partial" or (record.get("article") or {}).get("excerpt_kind") == "source_excerpt"):
        availability = "body_partial"
    return store.snapshot(record, text, availability)


def predicates(main):
    schema = json.loads((main.SCHEMAS_DIR / "relationship.schema.json").read_text(encoding="utf-8"))
    return schema["properties"]["predicate"]["enum"]


@router.get("/workspaces", response_class=HTMLResponse)
@router.get("/workspaces/{page_id}", response_class=HTMLResponse)
def workspace_page(request: Request, page_id: str = ""):
    main, store, _ = context(request)
    if page_id and not (store.get(page_id) or {}).get("id", "").startswith("wp-"):
        raise HTTPException(404, "Page not found")
    return main.templates.TemplateResponse(request=request, name="living_workspace.html", context={"authoring_mode": True, "static_build": False, "page_id": page_id})


@router.get("/api/workspaces")
def inventory(request: Request):
    main, store, _ = context(request)
    entities = [{"id": row["id"], "name": row.get("name", row["id"]), "type": row.get("entity_type", "topic"), "aliases": row.get("aliases", [])} for row in main.all_entities()]
    entities.extend(store.rows("entity"))
    from app.services import news_tags
    known = {row['id'] for row in entities}
    entities.extend({'id': tag['id'], 'name': tag['name'], 'type': 'topic', 'aliases': []}
                    for tag in news_tags.catalog(main.INBOX_DIR) if tag['id'] not in known)
    return {"pages": store.rows("page"), "entities": entities, "predicates": predicates(main)}


@router.post("/api/workspaces")
async def new_page(request: Request):
    _, store, actor = context(request, True)
    data = await body(request)
    return checked(lambda: store.create_page(data.get("title", ""), data.get("parent_id"), actor, data.get("token"), data.get("starter", False)))


@router.get("/api/workspaces/preferences/layout")
def get_layout_preferences(request: Request):
    _, store, actor = context(request)
    return store.layout_preferences(actor)


@router.put("/api/workspaces/preferences/layout")
async def put_layout_preferences(request: Request):
    _, store, actor = context(request, True)
    payload = await body(request)
    return checked(lambda: store.save_layout_preferences(actor, payload))


@router.get("/api/workspaces/page/{page_id}")
def get_page(request: Request, page_id: str):
    main, store, _ = context(request)
    page = store.get(page_id)
    if not page or not page_id.startswith("wp-"):
        raise HTTPException(404, "Page not found")
    keys = {b.get("item_id") for b in page["blocks"]}
    items = [item for item in store.rows("item") if item["id"] in keys]
    # Existing human review status wins over the initial capture status.
    published = {row["id"]: row for row in main.published_evidence()}
    for item in items:
        review_id = item.get("review_evidence_id", item["id"])
        evidence = published.get(review_id) or main.get_draft(review_id) or {}
        item["verification_state"] = evidence.get("verification_state", "unverified")
        item["review_status"] = evidence.get("status", "in_review")
    source_keys = {i["source_id"] for i in items}
    overview = page.get("overview")
    from app.services.workspace_landscapes import resolve
    landscape_error = ""
    try:
        landscapes = resolve(main, request, page.get("landscape_links", []))
    except (ValueError, HTTPException) as exc:
        landscapes, landscape_error = [], str(getattr(exc, "detail", exc))
    updated = max([page.get("content_updated_at", page.get("updated_at", ""))] + [i.get("updated_at", "") for i in items])
    social_ids = {b.get('social_id') for b in page['blocks'] if b['type'] == 'social'}
    social = [{k: row.get(k) for k in ('id', 'text', 'source', 'published_at', 'collected_at', 'mode', 'translation')} for row in social_observations(main).values() if row['id'] in social_ids] if social_ids else []
    return {"page": page, "items": items, "social": social, "sources": [s for s in store.rows("source") if s["id"] in source_keys], "landscapes": [{k: v for k, v in row.items() if k != "data"} for row in landscapes], "landscape_error": landscape_error, "page_material_updated_at": updated, "overview_stale": bool(overview and (landscape_error or overview.get("basis") != living.overview_basis(page, {i["id"]: i for i in items}, landscapes)))}


@router.put("/api/workspaces/page/{page_id}")
async def save_page(request: Request, page_id: str):
    main, store, actor = context(request, True)
    payload = await body(request)
    if "landscape_links" in payload:
        from app.services.workspace_landscapes import choices
        allowed = {row["id"] for row in choices(main)}
        if not isinstance(payload["landscape_links"], list) or any(not isinstance(key, str) or key not in allowed for key in payload["landscape_links"]):
            raise HTTPException(422, "Choose an available Landscape")
    page = checked(lambda: store.save_page(page_id, payload, actor))
    store.flush()
    return page


@router.post("/api/workspaces/capture")
async def capture(request: Request):
    main, store, actor = context(request, True)
    payload = await body(request)
    payload["allowed_predicates"] = predicates(main)
    def previous():
        with store.transaction() as db:
            return store.replay(db, payload.get("token"), payload)
    replay = checked(previous)
    if replay:
        return replay
    source = source_snapshot(main, store, payload.get("article_id", ""), payload.get("source_id"))
    entities = main.entity_index() | {row["id"]: row for row in store.rows("entity")}
    return checked(lambda: store.capture(payload, source, actor, entities))


@router.get("/api/workspaces/source/{article_id}")
def source(request: Request, article_id: str):
    main, store, _ = context(request)
    return source_snapshot(main, store, article_id, request.query_params.get("source_id"))


@router.get("/api/workspaces/feed/{page_id}")
def feed(request: Request, page_id: str):
    main, store, _ = context(request)
    page = store.get(page_id)
    if not page or not page_id.startswith("wp-"):
        raise HTTPException(404, "Page not found")
    if page["feed"].get("paused"):
        return {"state": "paused", "items": [], "last_success": None}
    _, feed_context, records, entities = world()
    from app.services import feed_first
    from app.services.news_workspace import source_reviewed, escalations
    support = escalations(main.all_facts())
    from app.services import news_tags
    tag_catalog = news_tags.catalog(main.INBOX_DIR)
    tag_assignments = news_tags.snapshot(main.INBOX_DIR)
    cards, news_cards, seen = [], [], set()
    for row in sorted(records.values(), key=lambda r: str(r.get("published_date") or ""), reverse=True):
        if row["id"] in page["dismissed"]:
            continue
        assigned = news_tags.effective(row, tag_catalog, *tag_assignments)
        matches = living.feed_matches({**row, 'topic_ids': sorted(set(row.get('topic_ids') or []) | set(assigned))}, page["feed"])
        # Canonical URL, then exact normalized title. No fuzzy evidence merges.
        url = urlsplit(str(row.get("source_url") or ""))
        key = (url.netloc.lower(), url.path.rstrip("/")) if url.netloc else (row["id"],)
        title_key = " ".join(str(row.get("title", "")).casefold().split())
        if not matches or key in seen or ("title", title_key) in seen:
            continue
        seen.add(key)
        seen.add(("title", title_key))
        cards.append({"id": row["id"], "title": row.get("title"), "publisher": row.get("source_name"), "published_date": row.get("published_date"), "discovered_date": row.get("captured_date"), "entity_ids": row.get("entity_ids", []), "matches": matches})
        # Use the News presenter and template; hydrate article bodies only in the Reader.
        preview = {key: value for key, value in row.items() if key not in {"article", "transcript", "transcript_excerpt", "reader_capture", "images"}}
        preview["article"] = {"image_url": feed_first.safe_image_url(row)}
        card = feed_first.present_item(preview, entities_by_id=entities, state=feed_context.get("state", {}), filters=feed_first.parse_filters({}))
        from app.services.feed_first_reader import is_public_http_url
        from app.services.source_body import looks_like_interstitial
        card["source_url"] = card["source_url"] if is_public_http_url(card["source_url"]) else ""
        if looks_like_interstitial(card["deck"]):
            card["deck"] = "Article summary unavailable. Open the story for source links."
        card.update(source_reviewed=source_reviewed(row), trusted=source_reviewed(row) and row["id"] in support)
        news_cards.append(card)
        if len(cards) == 100:
            break
    html = main.templates.get_template("_news_cards.html").render(cards=news_cards, workspace_feed=True, authoring_mode=True)
    return {"state": "active", "last_success": living.now(), "items": cards, "html": html}


@router.post("/api/workspaces/generate/{page_id}")
async def generate(request: Request, page_id: str):
    main, store, actor = context(request, True)
    payload = await body(request)
    payload["page_id"] = page_id
    def create():
        with store.transaction() as db:
            replay = store.replay(db, payload.get("token"), payload)
            if replay:
                return replay
            page = store.get(page_id, db)
            if not page or page["version"] != payload.get("version"):
                raise living.Conflict("Reload the page before generating from a newer revision")
            items = {i["id"]: i for i in store.rows("item", db)}
            sources = {s["id"]: s for s in store.rows("source", db)}
        block = living.compose_overview(page, items, sources) if payload.get("target") == "overview" else living.compose_brief(page, items, sources, payload.get("selected", []))
        from app.services.workspace_landscapes import resolve, add_summary_context
        landscapes = resolve(main, request, page.get("landscape_links", [])) if payload.get("target") == "overview" else []
        add_summary_context(block, items, landscapes)
        if payload.get("use_model"):
            from app.services.ai_gateway.untrusted_complete import maybe_untrusted_completer
            from urllib.parse import urlsplit
            import os
            from app.services.ai_gateway.perplexity_agent import DEFAULT_PERPLEXITY_AGENT_BASE_URL
            full_articles = payload.get("target") == "overview"
            endpoint = os.environ.get("BIOS_PERPLEXITY_AGENT_BASE_URL", DEFAULT_PERPLEXITY_AGENT_BASE_URL)
            approved = urlsplit(endpoint).scheme == "https" and urlsplit(endpoint).netloc == "api.perplexity.ai"
            completer = maybe_untrusted_completer() if not full_articles or approved else None
            block = living.model_narrative(block, items, completer=completer, style=payload.get("style", "briefing"), sources=sources if full_articles else None)
            if full_articles and not approved:
                block["generation_notice"] = "Full-article summaries require the approved Perplexity endpoint. Cited evidence digest preserved."
        if (payload.get("target") == "overview" and payload.get("use_model")
                and (not block.get("quality_checks") or block.get("method") != "configured model + cited evidence digest")):
            raise ValueError(block.get("generation_notice", "AI summary quality checks failed.") + " Saved page and previous summary were not changed. You can retry, or turn off AI to compile a source digest.")
        # No model/network work holds the capture database lock.
        with store.transaction() as db:
            replay = store.replay(db, payload.get("token"), payload)
            if replay:
                return replay
            if payload.get("target") == "overview":
                page["overview"] = {**block, "basis": living.overview_basis(page, items, landscapes)}
            else:
                page["blocks"].append(block)
            page = store.put(db, "page", page, actor, payload.get("version"))
            store.remember(db, payload["token"], payload, page)
            return page
    return checked(create)


@router.patch("/api/workspaces/item/{item_id}")
async def edit_item(request: Request, item_id: str):
    main, store, actor = context(request, True)
    payload = await body(request)
    def edit():
        with store.transaction() as db:
            item = store.get(item_id, db)
            if not item or not item_id.startswith("ev-workspace-"):
                raise ValueError("Item not found")
            # The quote, provenance, identity and review state are immutable here.
            for field in ("text", "note", "withdrawn"):
                if field in payload:
                    if (field == "withdrawn" and type(payload[field]) is not bool) or (field != "withdrawn" and not isinstance(payload[field], str)):
                        raise ValueError("Invalid interpretation field")
                    item[field] = payload[field]
            if "supporting_item_ids" in payload:
                if not isinstance(payload["supporting_item_ids"], list):
                    raise ValueError("Supporting evidence must be a list")
                for key in payload["supporting_item_ids"]:
                    if not (store.get(key, db) or {}).get("id", "").startswith("ev-workspace-"):
                        raise ValueError("Supporting capture does not exist")
                item["supporting_item_ids"] = list(dict.fromkeys(payload["supporting_item_ids"]))
            if "relation" in payload:
                relation = payload["relation"]
                if not item.get("relation") or not isinstance(relation, dict):
                    raise ValueError("Use capture to create a typed relationship")
                entities = main.entity_index() | {row["id"]: row for row in store.rows("entity", db)}
                if relation.get("subject_id") not in entities or relation.get("object_id") not in entities or relation.get("predicate") not in predicates(main) or relation.get("nature") not in {"source_statement", "analyst_hypothesis"}:
                    raise ValueError("Invalid relationship revision")
                if relation["nature"] != item["nature"]:
                    raise ValueError("Capture a separate source claim to develop a hypothesis; changing its nature is not a review action")
                item["relation"] = relation
                item["entity_ids"] = list(dict.fromkeys(item["entity_ids"] + [relation["subject_id"], relation["object_id"]]))
            item["review_evidence_id"] = item["id"] + "-r" + str(item["version"] + 1)
            revised = store.put(db, "item", item, actor, payload.get("version"))
            projection = {**revised, "id": revised["review_evidence_id"]}
            store.queue_projection(db, projection, store.get(item["source_id"], db), actor)
            return revised
    revised = checked(edit)
    store.flush()
    return revised


@router.post("/api/workspaces/move")
async def move_placement(request: Request):
    _, store, actor = context(request, True)
    payload = await body(request)
    def move():
        with store.transaction() as db:
            replay = store.replay(db, payload.get("token"), payload)
            if replay:
                return replay
            first, target = store.get(payload.get("from_page"), db), store.get(payload.get("to_page"), db)
            if not first or not target or not first["id"].startswith("wp-") or not target["id"].startswith("wp-"):
                raise ValueError("Destination not found")
            if first["id"] == target["id"]:
                return {"page": target}
            block = next((b for b in first["blocks"] if b["id"] == payload.get("block_id")), None)
            if not block:
                raise ValueError("Placement has changed")
            first["blocks"].remove(block)
            target["blocks"].append(block)
            first = store.put(db, "page", first, actor, payload.get("from_version"))
            target = store.put(db, "page", target, actor, payload.get("to_version"))
            result = {"page": target, "from_page": first}
            store.remember(db, payload["token"], payload, result)
            return result
    return checked(move)


@router.post("/api/workspaces/entity")
async def entity_stub(request: Request):
    _, store, actor = context(request, True)
    payload = await body(request)
    name = str(payload.get("name", "")).strip()[:240]
    kind = payload.get("type", "company")
    if not name or kind not in {"company", "variety", "technology", "topic"}:
        raise HTTPException(422, "Provide a name and entity type")
    # Explicitly unresolved: never silently merged into canonical identities.
    with store.transaction() as db:
        return store.put(db, "entity", {"id": living.ident("unresolved-"), "name": name, "type": kind, "status": "unverified", "identity_state": "unresolved"}, actor)


@router.get("/api/workspaces/history/{key}")
def history(request: Request, key: str):
    _, store, _ = context(request)
    if key.startswith("layout-"):
        raise HTTPException(404, "History not found")
    return {"revisions": store.history(key)}


@router.get("/api/workspaces/entity/{entity_id}")
def entity_material(request: Request, entity_id: str):
    _, store, _ = context(request)
    return {"items": [item for item in store.rows("item") if entity_id in item.get("entity_ids", [])]}


@router.get("/api/workspaces/related/{page_id}")
def related_material(request: Request, page_id: str):
    main, store, _ = context(request)
    page = store.get(page_id)
    if not page or not page_id.startswith("wp-"):
        raise HTTPException(404, "Page not found")
    keys = {b.get("item_id") for b in page["blocks"]}
    linked = {entity for i in store.rows("item") if i["id"] in keys for entity in i.get("entity_ids", [])}
    external = [{**i, "outside_page": True} for i in store.rows("item") if i["id"] not in keys and i.get("relation") and linked.intersection(i.get("entity_ids", []))]
    # Canonical graph rows retain their existing status and evidence links.
    for row in main.all_relationships():
        if linked.intersection({row.get("subject_id"), row.get("object_id")}):
            external.append({"id": row["id"], "relation": {**row, "nature": "source_statement"}, "nature": "source_statement", "verification_state": "existing graph: " + row.get("status", "unknown"), "outside_page": True, "canonical": True, "evidence_ids": row.get("evidence_ids", [])})
    return {"items": external}


@router.get("/workspaces/evidence/{item_id}", response_class=HTMLResponse)
def evidence(request: Request, item_id: str):
    main, store, _ = context(request)
    item = store.get(item_id)
    if not item or not item_id.startswith("ev-workspace-"):
        raise HTTPException(404, "Capture not found")
    source = store.get(item["source_id"])
    start = item.get("locator", {}).get("start")
    exact = type(start) is int and item.get("quote") and source["text"][start:start + len(item["quote"])] == item["quote"]
    passage = {"before": source["text"][:start], "quote": item["quote"], "after": source["text"][start+len(item["quote"]):]} if exact else None
    return main.templates.TemplateResponse(request=request, name="living_evidence.html", context={"item": item, "source": source, "passage": passage, "history": store.history(item_id), "authoring_mode": True, "static_build": False})


@router.get("/api/workspaces/export/{page_id}")
def export(request: Request, page_id: str):
    _, store, _ = context(request)
    page = store.get(page_id)
    if not page or not page_id.startswith("wp-"):
        raise HTTPException(404, "Page not found")
    if request.query_params.get("format") == "json":
        keys = {b.get("item_id") for b in page["blocks"]}
        items = [i for i in store.rows("item") if i["id"] in keys]
        return {"format_version": 1, "page": page, "items": items, "sources": [s for s in store.rows("source") if s["id"] in {i["source_id"] for i in items}]}
    lines = ["# " + page["title"]]
    if page.get("overview"):
        overview = page["overview"]
        lines.extend(["Page overview · generated " + overview["generated_at"], overview["text"]])
        for ref in overview.get("citations", []):
            lines.append(f'[{ref["number"]}] {ref["title"]} — {ref["url"]} — /workspaces/evidence/{ref["item_id"]}')
    for block in page["blocks"]:
        lines.append(block.get("text", ""))
        if block.get("item_id"):
            item = store.get(block["item_id"])
            source = store.get(item["source_id"])
            lines.extend([item["nature"] + " · unverified", item["text"], "> " + item["quote"], f'{source["title"]} — {source["url"]} — /workspaces/evidence/{item["id"]}'])
        if block.get("rows"):
            lines.extend(" | ".join(row) for row in block["rows"])
    return PlainTextResponse("\n\n".join(lines), headers={"Content-Disposition": f'attachment; filename="{page_id}.md"'})
