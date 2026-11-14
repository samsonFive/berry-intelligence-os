"""Company news review preset within the existing private Report Builder."""
from datetime import date, timedelta
from urllib.parse import urlencode

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from app.personal_digest_routes import require_edit
from app.services import feed_first, personal_digest
from app.services.report_builder import company_news, company_news_jobs as jobs, reports_store

router = APIRouter()


def main_module():
    from app import main
    return main


def review_or_404(report_id):
    main = main_module()
    try:
        return jobs.load_review(main.INBOX_DIR, report_id)
    except ValueError as exc:
        raise HTTPException(404, "Company news review not found") from exc


def start_page(request, *, values=None, error="", status_code=200):
    main = main_module()
    entities = {row["id"]: row for row in main.living_catalog()}
    today = date.today()
    values = {"title": "Company news review", "roster": "", "from_date": (today - timedelta(days=365)).isoformat(),
        "through_date": today.isoformat(), "berry": "", "topic": "", "source_scope": "combined", **(values or {})}
    return main.templates.TemplateResponse(request=request, name="company_news_start.html", status_code=status_code, context={
        "values": values, "error": error, "berries": main.BERRIES,
        "company_lists": personal_digest.company_lists(feed_first.load_state(main.INBOX_DIR)),
        "companies": sorted([r for r in entities.values() if r.get("entity_type") == "company"], key=lambda r: r.get("name", "").casefold()),
        "authoring_mode": main.AUTHORING_MODE, "static_build": False,
    })


def archive_world():
    main = main_module()
    entities = main.living_catalog()
    from app.services.social_intelligence.output_eligibility import output_exclusions, eligible_records
    from app.services.article_dedup import normalize_canonical_url
    issues = []
    records = personal_digest.source_records(main.published_evidence(), main.INBOX_DIR,
        pending=main.list_pending_drafts(), index_issues=issues)
    blocked = output_exclusions(main.DATA_DIR, main.INBOX_DIR)
    excluded_urls = sorted({normalize_canonical_url(row.get("source_url")) for row in main.all_evidence()
        if row.get("id") in blocked and row.get("source_url")}) if blocked else []
    return entities, eligible_records(list(records.values()), blocked), main.DATA_DIR, {
        "excluded_source_urls": excluded_urls, "archive_index_unavailable": bool(issues)}


def ensure_output_allowed(record):
    main = main_module()
    from app.services.research_source_holds import source_quote_hold
    snapshot = record["scope"]["company_news_review"]
    if any((row.get("excerpt") or row.get("passage")) and source_quote_hold(row) for row in snapshot.get("sources", [])):
        raise HTTPException(409, "A saved source quotation now requires verification. Create a refreshed version before using this report.")
    if not main._social_eligible_outputs([record]):
        raise HTTPException(409, "This report cites a deleted source. Create a refreshed version before using it.")
    from app.services.social_intelligence.output_eligibility import output_exclusions
    from app.services.article_dedup import normalize_canonical_url
    blocked = output_exclusions(main.DATA_DIR, main.INBOX_DIR)
    if blocked:
        urls = {normalize_canonical_url(row.get("source_url")) for row in main.all_evidence() if row.get("id") in blocked and row.get("source_url")}
        if any(normalize_canonical_url(row.get("url") or row.get("source_url")) in urls for row in snapshot.get("sources", [])):
            raise HTTPException(409, "This report cites a deleted source. Create a refreshed version before using it.")


def schedule(tasks, report_id):
    main = main_module()
    token = jobs.queue_review(main.INBOX_DIR, report_id)
    tasks.add_task(jobs.run_review, main.INBOX_DIR, report_id, token, world=archive_world)


@router.post("/reports/new/company-news")
async def create_company_news(request: Request, tasks: BackgroundTasks):
    require_edit(request)
    main = main_module()
    form = await request.form()
    values = {key: str(form.get(key) or "").strip() for key in ("title", "roster", "from_date", "through_date", "berry", "topic", "source_scope", "company_list_id")}
    try:
        if len(values["roster"]) > 20000 or len(values["topic"]) > 500 or len(values["title"]) > 200:
            raise ValueError("Keep the company roster under 20,000 characters, public focus under 500 and title under 200")
        entities = main.living_catalog()
        by_id = {r["id"]: r for r in entities}
        roster = values["roster"]
        if values["company_list_id"]:
            lists = personal_digest.company_lists(feed_first.load_state(main.INBOX_DIR))
            selected = next((r for r in lists if r["id"] == values["company_list_id"]), None)
            if selected is None:
                raise ValueError("Choose an available saved company list")
            roster = "\n".join(str(by_id.get(key, {}).get("name") or key) for key in selected.get("company_ids", [])) + "\n" + roster
        if values["berry"] and values["berry"] not in main.BERRIES:
            raise ValueError("Choose a listed berry scope")
        snapshot = company_news.create_review(roster, entities=entities, from_date=values["from_date"], through_date=values["through_date"],
            berry_id=values["berry"] or None, topic=values["topic"], source_scope=values["source_scope"])
        record = reports_store.create_report(main.INBOX_DIR, title=values["title"] or "Company news review", report_type=jobs.REPORT_TYPE,
            scope={"report_type": jobs.REPORT_TYPE, "company_news_review": snapshot, "version": 1}, sections=[])
        schedule(tasks, record["id"])
    except ValueError as exc:
        return start_page(request, values=values, error=str(exc), status_code=422)
    return RedirectResponse(f"/reports/{record['id']}", status_code=303)


def workspace_page(request, record):
    main = main_module()
    ensure_output_allowed(record)
    from app.services.report_builder.company_report_reader import present_company_review, select_company_reader
    snapshot = record["scope"]["company_news_review"]
    reader = present_company_review(snapshot)
    for company in reader.get("companies", []):
        for story in company.get("stories", []):
            story["edit_href"] = f"/reports/{record['id']}/company-news/entry/{story['id']}"
    report = {**record, "href": f"/reports/{record['id']}", "subtitle": f"{snapshot['from_date']} to {snapshot['through_date']}",
        "published_date": snapshot["as_of"], "download_href": f"/reports/{record['id']}/export.pdf",
        "xlsx_download_href": f"/reports/{record['id']}/export.xlsx"}
    return main.templates.TemplateResponse(request=request, name="report_company_reader.html", context={
        "report": report, "reader": reader, "company_view": select_company_reader(reader, request.query_params.get("company")),
        "working_review": True, "research_progress": jobs.progress(main.INBOX_DIR, record),
        "authoring_mode": main.AUTHORING_MODE, "static_build": False,
    }, headers={"Cache-Control": "private, no-store"})


@router.get("/reports/{report_id}/company-news/progress")
def review_progress(report_id: str):
    main = main_module()
    record = review_or_404(report_id)
    return JSONResponse(jobs.progress(main.INBOX_DIR, record), headers={"Cache-Control": "private, no-store"})


@router.post("/reports/{report_id}/company-news/resume")
def resume_review(request: Request, report_id: str, tasks: BackgroundTasks):
    require_edit(request)
    review_or_404(report_id)
    try:
        schedule(tasks, report_id)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return RedirectResponse(f"/reports/{report_id}", status_code=303)


@router.post("/reports/{report_id}/company-news/pause")
def pause_review(request: Request, report_id: str):
    require_edit(request)
    review_or_404(report_id)
    jobs.pause_review(main_module().INBOX_DIR, report_id)
    return RedirectResponse(f"/reports/{report_id}", status_code=303)


@router.post("/reports/{report_id}/company-news/refresh")
def refresh_review(request: Request, report_id: str, tasks: BackgroundTasks):
    require_edit(request)
    main = main_module()
    old = review_or_404(report_id)
    previous = old["scope"]["company_news_review"]
    snapshot = company_news.create_review([r["requested_name"] for r in previous["companies"]], entities=main.living_catalog(),
        from_date=previous["from_date"], through_date=previous["through_date"], berry_id=previous.get("berry_id"),
        topic=previous.get("topic", ""), source_scope=previous["source_scope"])
    version = int(old["scope"].get("version", 1)) + 1
    record = reports_store.create_report(main.INBOX_DIR, title=old["title"], report_type=jobs.REPORT_TYPE,
        scope={"report_type": jobs.REPORT_TYPE, "company_news_review": snapshot, "version": version, "parent_report_id": report_id}, sections=[])
    schedule(tasks, record["id"])
    return RedirectResponse(f"/reports/{record['id']}", status_code=303)


@router.get("/reports/{report_id}/company-news/entry/{entry_id}", response_class=HTMLResponse)
def edit_page(request: Request, report_id: str, entry_id: str):
    record = review_or_404(report_id)
    ensure_output_allowed(record)
    entry = next((r for r in record["scope"]["company_news_review"]["entries"] if r["id"] == entry_id), None)
    if entry is None:
        raise HTTPException(404, "Development not found")
    return entry_edit_response(request, record, entry)


def entry_edit_response(request, record, entry, *, submitted=None, error="", status_code=200):
    main = main_module()
    effective = company_news.effective_entry(entry)
    raw = dict(entry)
    if submitted:
        effective.update({key: str(submitted.get(key) or "") for key in ("headline", "summary", "news_angle", "qualification", "published_date", "event_date", "review_status")})
        effective["included"] = submitted.get("included") == "true"
        raw["edit_revision"] = str(submitted.get("edit_revision") or "0")
    response = main.templates.TemplateResponse(request=request, name="company_news_entry_edit.html", status_code=status_code, context={
        "report": record, "entry": effective, "raw_entry": raw, "error": error,
        "can_include_lead": jobs.can_qualify_lead(record["scope"]["company_news_review"], entry),
        "authoring_mode": main.AUTHORING_MODE, "static_build": False,
    })
    response.headers["Cache-Control"] = "private, no-store"
    return response


@router.post("/reports/{report_id}/company-news/entry/{entry_id}")
async def save_entry(request: Request, report_id: str, entry_id: str):
    require_edit(request)
    record = review_or_404(report_id)
    ensure_output_allowed(record)
    form = await request.form()
    try:
        jobs.edit_entry(main_module().INBOX_DIR, report_id, entry_id,
            changes={key: str(form.get(key) or "").strip() for key in ("headline", "summary", "news_angle", "qualification", "published_date", "event_date")},
            included=form.get("included") == "true", review_status=str(form.get("review_status") or "unreviewed"),
            expected_revision=int(str(form.get("edit_revision") or "0")))
    except ValueError as exc:
        latest = review_or_404(report_id)
        entry = next((r for r in latest["scope"]["company_news_review"]["entries"] if r["id"] == entry_id), None)
        if entry is None:
            raise HTTPException(404, "Development not found") from exc
        return entry_edit_response(request, latest, entry, submitted=form, error=str(exc),
            status_code=409 if isinstance(exc, jobs.ReviewBusy) else 422)
    entry = next(r for r in record["scope"]["company_news_review"]["entries"] if r["id"] == entry_id)
    return RedirectResponse(f"/reports/{report_id}?{urlencode({'company': entry['company_key']})}#{entry_id}", status_code=303)


@router.get("/reports/{report_id}/export.xlsx")
def export_xlsx(report_id: str):
    main = main_module()
    record = review_or_404(report_id)
    ensure_output_allowed(record)
    from app.services.report_builder.company_news_export import render_company_news_xlsx
    try:
        content = render_company_news_xlsx(record["scope"]["company_news_review"], title=record["title"])
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return Response(content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{report_id}.xlsx"', "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})
