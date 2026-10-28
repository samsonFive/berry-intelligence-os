"""Core News entry point and explicit manual refresh. Page loads are read-only."""
from datetime import UTC, datetime
import json
from pathlib import Path
from urllib.parse import urlencode

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

from app.personal_digest_routes import require_edit, world
from app.services import feed_first, news_workspace, news_images, news_tags
from app.services.analyst_state_io import atomic_json, serialized_write
from app.services.pipeline_lock import pipeline_lock

router = APIRouter()


def news_page(request: Request):
    main, context, records, entities = world()
    params = dict(request.query_params)
    saved = news_tags.preferences(main.INBOX_DIR, tag_actor(request))
    if not any(key in params for key in ('tag', 'topic', 'tag_choice', 'topic_choice')):
        params.update(saved)
    # Native multiselect checkboxes also work without JavaScript.
    for field in ("berry", "countries", "topic", "tag"):
        selected = request.query_params.getlist(field + "_choice")
        if selected:
            params[field] = ",".join(selected)
    if params.get("item") and not params.get("story"):
        params["story"] = params["item"]
    try:
        model = news_workspace.model(records=records, entities=entities, relationships=main.all_relationships(),
                                     facts=main.all_facts(), state=context["state"], params=params,
                                     tags=news_tags.catalog(main.INBOX_DIR), tag_assignments=news_tags.snapshot(main.INBOX_DIR))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    query = model["filters"]
    model['tag_research_href'] = '/research?' + urlencode({'tag': query['tag'], 'tag_mode': query['tag_mode'], 'q': 'What does the stored intelligence say about these subjects?'})
    model['clear_tags_href'] = '/today?' + urlencode({**query, 'tag': '', 'topic': ''})
    model['any_tags_href'] = '/today?' + urlencode({**query, 'tag_mode': 'any'})
    model['tag_job'] = news_tags.job_state(main.INBOX_DIR)
    for card in model['cards']:
        for tag in card['assigned_tags']:
            tag['filter_href'] = '/today?' + urlencode({**query, 'tag': ','.join(dict.fromkeys([*filter(None, query['tag'].split(',')), tag['id']]))})
    # Switching review lanes or pages always carries the same scope.
    model["pagination"] = {number: "/today?" + urlencode({**query, "page": number})
                           for number in (model["page"] - 1, model["page"] + 1)}
    model["review_urls"] = {view: "/today?" + urlencode({**query, "view": view}) for view in ("trusted", "unreviewed")}
    model["map_href"] = model["query"].url() + "&" + urlencode({"news_return": "/today?" + urlencode(query)})
    model["initial_story"] = str(params.get("story") or "")
    refresh = refresh_state(main.INBOX_DIR)
    model["refresh_state"] = {key: refresh.get(key) for key in ("status", "completed_at", "story_count", "error_count", "message")}
    return main.templates.TemplateResponse(request=request, name="news_workspace.html", context={
        **model, "authoring_mode": main.AUTHORING_MODE, "static_build": False,
        "pending_source_issue_count": context['pending_source_issue_count'],
        "berry_choices": {"berry-" + key: label for key, label in feed_first.CROP_LABELS.items()},
        "countries": sorted([row for row in entities.values() if row.get("entity_type") == "geography"], key=lambda row: row.get("name", "")),
        "companies": sorted([row for row in entities.values() if row.get("entity_type") in {"company", "person", "brand", "research_program"}], key=lambda row: row.get("name", "")),
    })


def tag_actor(request):
    from app.session_auth import session_username
    # Single-analyst local mode has its own account; remote users use sessions.
    return session_username(request) or 'local-analyst'


@router.post('/api/news/tags/preferences')
async def tag_preferences(request: Request):
    require_edit(request)
    from app import main
    data = await request.json()
    try:
        return news_tags.preferences(main.INBOX_DIR, tag_actor(request), data.get('tags', []), data.get('mode', 'all'))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


def classify_stored_tags():
    from app import main
    try:
        return _classify_stored_tags()
    except Exception:
        state = news_tags.job_state(main.INBOX_DIR)
        with news_tags.database(main.INBOX_DIR) as db:
            db.execute('INSERT OR REPLACE INTO jobs VALUES(1,?,?,?,?,?)',
                ('failed', state.get('processed', 0), state.get('total', 0),
                 'Stored source classification interrupted. Existing assignments are retained; recheck to resume.', news_tags.stamp()))
        raise


def _classify_stored_tags():
    main, context, records, entities = world()
    # Hydrate stored content only in background work, never on the feed path.
    from app.services import personal_digest
    full = personal_digest.source_records(main.published_evidence(), main.INBOX_DIR,
        include_private=main.AUTHORING_MODE, metadata_only=False)
    if main.AUTHORING_MODE:
        from app.services.publication_sources import active_publication_record
        for key in records.keys() - full.keys():
            original = main.get_draft(key)
            source = active_publication_record(original) if original else None
            if source:
                full[key] = source
    from app.services.feed_first_reader import load_capture, merge_capture
    corpus = {**records, **full}
    if main.AUTHORING_MODE:
        corpus = {key: merge_capture(row, load_capture(main.INBOX_DIR, key)) for key, row in corpus.items()}
    from app.services import news_tag_semantics
    if news_tag_semantics.enabled():
        news_tag_semantics.enqueue(main.INBOX_DIR,corpus)
        news_tag_semantics.run(main.INBOX_DIR)
    else:
        news_tags.backfill(main.INBOX_DIR, corpus)
    from app.services.source_body import article_full_text
    with_body = sum(bool(article_full_text(row)) for row in corpus.values())
    return {'sources': len(corpus), 'with_stored_body': with_body, 'metadata_or_excerpt_only': len(corpus)-with_body}


@router.post('/api/news/tags')
async def create_tag(request: Request, tasks: BackgroundTasks):
    require_edit(request)
    from app import main
    data = await request.json()
    try:
        tag = news_tags.create(main.INBOX_DIR, data.get('name', ''), data.get('description', ''))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    queue_tags(main.INBOX_DIR, tasks)
    return {'tag': tag, 'status': 'queued'}


@router.post('/api/news/tags/definition')
async def edit_tag_definition(request: Request, tasks: BackgroundTasks):
    require_edit(request)
    from app import main
    data = await request.json()
    try:
        changed = news_tags.update(main.INBOX_DIR, data.get('id'), data.get('name', ''), data.get('description', ''))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if changed:
        queue_tags(main.INBOX_DIR, tasks)
    return {'status': 'queued' if changed else 'saved'}


def queue_tags(inbox_dir, tasks):
    from app.services.chronology import parse_stamp
    with news_tags.database(inbox_dir) as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT * FROM jobs WHERE id=1').fetchone()
        started = parse_stamp(row['updated_at']) if row else None
        if row and row['status'] in {'running', 'queued'} and started and (datetime.now(UTC)-started).total_seconds() < 600:
            # A tag may have been created after the running worker took its
            # catalog snapshot. A cached, serialized follow-up covers it.
            tasks.add_task(classify_stored_tags)
            return
        db.execute('INSERT OR REPLACE INTO jobs VALUES(1,?,?,?,?,?)', ('queued', 0, 0, '', news_tags.stamp()))
    tasks.add_task(classify_stored_tags)


@router.post('/api/news/tags/classify')
def classify_tags(request: Request, tasks: BackgroundTasks):
    require_edit(request)
    from app import main
    queue_tags(main.INBOX_DIR, tasks)
    return JSONResponse({'status': 'queued'}, status_code=202)


@router.get('/api/news/tags/status')
def tag_status():
    from app import main
    return news_tags.job_state(main.INBOX_DIR)


@router.get('/api/news/tags/explanations/{article}')
def tag_explanations(article: str):
    main, context, records, entities = world()
    if article not in records:
        raise HTTPException(404, 'Article is unavailable')
    if not news_tags.exists(main.INBOX_DIR):
        return {'assignments': []}
    with news_tags.database(main.INBOX_DIR) as db:
        rows = db.execute('''SELECT t.id,t.name,a.rationale,a.classifier_version,o.present AS manual
            FROM tags t LEFT JOIN automatic a ON a.tag=t.id AND a.article=?
            LEFT JOIN overrides o ON o.tag=t.id AND o.article=?
            WHERE COALESCE(o.present,a.present,0)=1''', (article, article)).fetchall()
        return {'assignments': [{'id': r['id'], 'name': r['name'], 'origin': 'Manual addition' if r['manual'] is not None else 'Automatic subject match' if str(r['classifier_version'] or '').startswith('semantic-') else 'Automatic terminology match',
                 'rationale': r['rationale'] or 'Added by an analyst.'} for r in rows]}


@router.post('/api/news/tags/assignment')
async def edit_tag_assignment(request: Request):
    require_edit(request)
    data = await request.json()
    main, context, records, entities = world()
    if data.get('article') not in records:
        raise HTTPException(404, 'Article is unavailable')
    try:
        news_tags.override(main.INBOX_DIR, data['article'], data.get('tag'), data.get('action'), tag_actor(request))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {'status': 'saved', 'tags': news_tags.effective(records[data['article']],
        news_tags.catalog(main.INBOX_DIR), *news_tags.snapshot(main.INBOX_DIR))}


def refresh_path(inbox_dir: Path):
    return inbox_dir / "news_workspace" / "refresh.json"


def refresh_state(inbox_dir: Path):
    try:
        return json.loads(refresh_path(inbox_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def run_refresh(inbox_dir, context, sources, *, update_publishers=False):
    """Reuse the existing bounded public-news collector; disable paid lanes."""
    from app.services.feed_first_live import live_feed_bundle
    from app.services.clock import utc_today
    started = datetime.now(UTC)
    result = {"status": "running", "started_at": started.isoformat()}
    try:
        with pipeline_lock(inbox_dir, "news_workspace_refresh"):
            atomic_json(refresh_path(inbox_dir), result)
            if update_publishers:
                from app.services.publisher_coverage import refresh_publisher_coverage
                coverage = refresh_publisher_coverage(inbox_dir)
            else:
                coverage = []
            bundle = live_feed_bundle(inbox_dir=inbox_dir, entities=context["entities"], sources=sources,
                                      refresh=True, today=utc_today(), official_hosts=context["official_hosts"],
                                      official_host_map=context["official_host_map"], muted_ids=context["muted_entity_ids"],
                                      enrich_lead=False, enable_perplexity=False, enable_exa=False, enable_apitube=False,
                                      fetch_preview_images=False, translate_live=False)
            errors = bundle.get("lane_errors") or []
            errors = errors + [row for row in coverage if row.get('status') in {'failed', 'partial'}]
            # Publish fresh stories immediately. Images and optional translation
            # must not hold the news view behind additional publisher requests.
            result.update(status="partial" if errors else "ready", story_count=len(bundle.get("records") or []),
                          error_count=len(errors), message="Some sources could not be checked." if errors else "News capture completed.")
    except Exception:
        # Provider details and exception traces belong in operations, never UI.
        result.update(status="failed", error_count=1, message="News could not be refreshed. Another collection may be running; try again.")
    if result.get('status') in {'ready', 'partial'}:
        classify_stored_tags()
    result["completed_at"] = datetime.now(UTC).isoformat()
    atomic_json(refresh_path(inbox_dir), result)
    atomic_json(inbox_dir / "operations" / "pipelines" / "news_workspace_refresh" / "runs" / (started.strftime("%Y%m%dT%H%M%S%fZ") + ".json"), {
        "pipeline": "news_workspace_refresh",
        "outcome": {"failed": "FAILED", "partial": "PARTIAL"}.get(result["status"], "SUCCESS"),
        "started_at": result["started_at"], "completed_at": result["completed_at"],
        "failure_count": result.get("error_count", 0), "items_new": result.get("story_count", 0), "publication_drafts": 0,
        "counts": {"items_new": result.get("story_count", 0), "publication_drafts_created": 0},
    })


@router.post("/api/news/refresh")
def refresh_news(request: Request, tasks: BackgroundTasks):
    require_edit(request)
    from app import main
    queue_refresh(main.INBOX_DIR, tasks, main)
    return JSONResponse({"status": "queued"}, status_code=202)


@serialized_write
def queue_refresh(inbox_dir, tasks, main):
    # The shared lease is the cross-pipeline guard. No polling/paid acquisition on GET.
    state = refresh_state(inbox_dir)
    started = state.get("started_at")
    if state.get("status") in {"queued", "running"} and started:
        from app.services.chronology import parse_stamp
        stamp = parse_stamp(started)
        if stamp and (datetime.now(UTC) - stamp).total_seconds() < 600:
            return
    atomic_json(refresh_path(inbox_dir), {"status": "queued", "started_at": datetime.now(UTC).isoformat()})
    tasks.add_task(run_refresh, inbox_dir, main._feed_first_world(), main.load_sources())


@router.get("/api/news/refresh")
def refresh_news_status():
    from app import main
    state = refresh_state(main.INBOX_DIR)
    return {key: state.get(key) for key in ("status", "completed_at", "story_count", "error_count", "message")}


@router.post("/api/news/images")
def capture_news_images(request: Request, tasks: BackgroundTasks):
    require_edit(request)
    main, context, records, entities = world()
    try:
        selected = news_workspace.model(records=records, entities=entities,
            relationships=main.all_relationships(), facts=main.all_facts(),
            state=context['state'], params=dict(request.query_params))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    queue_images(main.INBOX_DIR, tasks, [records[card['id']] for card in selected['cards']])
    return JSONResponse({'status': 'queued'}, status_code=202)


@serialized_write
def queue_images(inbox_dir, tasks, records):
    current = news_images.state(inbox_dir)
    from app.services.chronology import parse_stamp
    started = parse_stamp(current.get('started_at'))
    if current.get('status') in {'queued', 'running'} and started and (datetime.now(UTC) - started).total_seconds() < 600:
        return
    atomic_json(news_images.state_path(inbox_dir), {'status': 'queued', 'started_at': datetime.now(UTC).isoformat()})
    tasks.add_task(news_images.run, inbox_dir, records)


@router.get("/api/news/images")
def news_image_status():
    from app import main
    return news_images.state(main.INBOX_DIR)
