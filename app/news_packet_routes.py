"""Explicit capture -> preview -> export. GETs never collect or update receipts."""
from datetime import date, timedelta
import json

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app.personal_digest_routes import require_edit
from app.services import competitor_news_packets as packets, feed_first, personal_digest

router = APIRouter()


def world():
    from app import main
    entities = {row["id"]: row for row in main.all_entities()}
    records = personal_digest.source_records(main.published_evidence(), main.INBOX_DIR)
    for row in main.all_evidence() + main.list_pending_drafts():
        if row.get("status") in {"in_review", "draft", "pending"} and row.get("id") not in records:
            records[row["id"]] = row
    projected = [{key: value for key, value in row.items() if key not in {"article", "transcript", "images", "reader_capture"}} for row in records.values()]
    return main, entities, projected


def known_job(inbox, job_id):
    try:
        return packets.load_job(inbox, job_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(404, "Packet not found") from exc


@router.get("/news-packets", response_class=HTMLResponse)
def packet_home(request: Request):
    from app import main
    today = date.today()
    entities = {row["id"]: row for row in main.all_entities()}
    return main.templates.TemplateResponse(request=request, name="news_packet_home.html", context={
        "lists": personal_digest.company_lists(feed_first.load_state(main.INBOX_DIR)),
        "registry": packets.registry(main.DATA_DIR, entities), "registry_list_id": packets.LIST_ID,
        "history": packets.export_history(main.INBOX_DIR), "start": (today - timedelta(days=29)).isoformat(),
        "end": today.isoformat(), "year_start": today.replace(month=1, day=1).isoformat(),
        "week_start": (today - timedelta(days=6)).isoformat(), "authoring_mode": main.AUTHORING_MODE,
        "static_build": False,
    })


@router.post("/news-packets/setup")
def setup_registry(request: Request):
    require_edit(request)
    from app import main
    try:
        packets.install_registry(main.INBOX_DIR, main.DATA_DIR, {row["id"]: row for row in main.all_entities()})
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return RedirectResponse("/news-packets", status_code=303)


@router.post("/news-packets/capture")
async def capture_packet(request: Request, tasks: BackgroundTasks):
    require_edit(request)
    main, entities, records = world()
    form = await request.form()
    try:
        job = packets.create_job(main.INBOX_DIR, list_id=str(form.get("list_id") or ""),
                                 start=str(form.get("start") or ""), end=str(form.get("end") or ""),
                                 review=str(form.get("review") or ""), entities=entities)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    tasks.add_task(packets.capture_job, main.INBOX_DIR, job["id"], entities, records)
    return RedirectResponse("/news-packets/" + job["id"], status_code=303)


@router.get("/news-packets/template.csv")
def csv_template():
    return Response(packets.csv_file([], packets.FIELDS), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="competitor-news-template.csv"', "Cache-Control": "no-store"})


@router.get("/news-packets/{job_id}", response_class=HTMLResponse)
def preview_packet(request: Request, job_id: str):
    from app import main
    job = known_job(main.INBOX_DIR, job_id)
    entities = {row["id"]: row for row in main.all_entities()}
    represented = {row["competitor_id"] for row in job["records"]}
    missing = [entities.get(key, {"name": key}) for key in job["scope"]["entity_ids"] if key not in represented]
    return main.templates.TemplateResponse(request=request, name="news_packet_preview.html", context={
        "job": job, "stories": len({row["external_record_id"] for row in job["records"]}),
        "missing": missing, "authoring_mode": main.AUTHORING_MODE, "static_build": False,
    })


@router.post("/news-packets/{job_id}/export")
def generate_packet(request: Request, job_id: str):
    require_edit(request)
    from app import main
    known_job(main.INBOX_DIR, job_id)
    try:
        packets.commit_export(main.INBOX_DIR, job_id)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return RedirectResponse(f"/news-packets/{job_id}/download.json", status_code=303)


@router.get("/news-packets/{job_id}/download.json")
def download_packet(job_id: str):
    from app import main
    job = known_job(main.INBOX_DIR, job_id)
    if job["status"] != "exported":
        raise HTTPException(409, "Generate the validated packet before downloading")
    return Response(json.dumps(job["packet"], ensure_ascii=False, indent=2), media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="{job_id}.json"', "Cache-Control": "no-store"})


@router.get("/news-packets/{job_id}/exceptions.csv")
def download_exceptions(job_id: str):
    from app import main
    job = known_job(main.INBOX_DIR, job_id)
    issues = job["validation"]["errors"] + job["validation"]["warnings"] + job["capture"]["errors"]
    return Response(packets.csv_file(issues, ("record_id", "competitor_id", "subject_id", "code", "message", "duplicate_of")),
                    media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{job_id}-exceptions.csv"', "Cache-Control": "no-store"})
