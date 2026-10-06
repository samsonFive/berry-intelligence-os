"""Core News entry point and explicit manual refresh. Page loads are read-only."""
from datetime import UTC, datetime
import json
from pathlib import Path
from urllib.parse import urlencode

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

from app.personal_digest_routes import require_edit, world
from app.services import feed_first, news_workspace, news_images
from app.services.analyst_state_io import atomic_json, serialized_write
from app.services.pipeline_lock import pipeline_lock

router = APIRouter()


def news_page(request: Request):
    main, context, records, entities = world()
    params = dict(request.query_params)
    # Native multiselect checkboxes also work without JavaScript.
    for field in ("berry", "countries"):
        selected = request.query_params.getlist(field + "_choice")
        if selected:
            params[field] = ",".join(selected)
    if params.get("item") and not params.get("story"):
        params["story"] = params["item"]
    try:
        model = news_workspace.model(records=records, entities=entities, relationships=main.all_relationships(),
                                     facts=main.all_facts(), state=context["state"], params=params)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    query = model["filters"]
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
        "berry_choices": {"berry-" + key: label for key, label in feed_first.CROP_LABELS.items()},
        "countries": sorted([row for row in entities.values() if row.get("entity_type") == "geography"], key=lambda row: row.get("name", "")),
        "companies": sorted([row for row in entities.values() if row.get("entity_type") in {"company", "person", "brand", "research_program"}], key=lambda row: row.get("name", "")),
    })


def refresh_path(inbox_dir: Path):
    return inbox_dir / "news_workspace" / "refresh.json"


def refresh_state(inbox_dir: Path):
    try:
        return json.loads(refresh_path(inbox_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def run_refresh(inbox_dir, context, sources):
    """Reuse the existing bounded public-news collector; disable paid lanes."""
    from app.services.feed_first_live import live_feed_bundle
    from app.services.clock import utc_today
    started = datetime.now(UTC)
    result = {"status": "running", "started_at": started.isoformat()}
    try:
        with pipeline_lock(inbox_dir, "news_workspace_refresh"):
            atomic_json(refresh_path(inbox_dir), result)
            bundle = live_feed_bundle(inbox_dir=inbox_dir, entities=context["entities"], sources=sources,
                                      refresh=True, today=utc_today(), official_hosts=context["official_hosts"],
                                      official_host_map=context["official_host_map"], muted_ids=context["muted_entity_ids"],
                                      enrich_lead=False, enable_perplexity=False, enable_exa=False, enable_apitube=False)
            errors = bundle.get("lane_errors") or []
            # Explicit news capture includes bounded thumbnail acquisition too.
            news_images.collect(inbox_dir, bundle.get("records") or [])
            result.update(status="partial" if errors else "ready", story_count=len(bundle.get("records") or []),
                          error_count=len(errors), message="Some sources could not be checked." if errors else "News capture completed.")
    except Exception:
        # Provider details and exception traces belong in operations, never UI.
        result.update(status="failed", error_count=1, message="News could not be refreshed. Another collection may be running; try again.")
    result["completed_at"] = datetime.now(UTC).isoformat()
    atomic_json(refresh_path(inbox_dir), result)
    atomic_json(inbox_dir / "operations" / "pipelines" / "news_workspace_refresh" / "runs" / (started.strftime("%Y%m%dT%H%M%S%fZ") + ".json"), {
        "pipeline": "news_workspace_refresh", "status": "FAILED" if result["status"] in {"failed", "partial"} else "SUCCESS",
        "started_at": result["started_at"], "completed_at": result["completed_at"],
        "failure_count": result.get("error_count", 0), "items_new": result.get("story_count", 0), "publication_drafts": 0,
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
