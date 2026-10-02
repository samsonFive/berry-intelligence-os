"""Consolidated private monitoring navigation; existing state remains authoritative."""
from urllib.parse import urlencode
from fastapi import APIRouter, HTTPException, Request
from app.services import company_directory, feed_first, personal_digest, variety_navigation, watchlist
from app.services.watchtower.compose import compose_watchtower
from app.services.watchtower.present import present_watchtower
from app.services.map_regions import public_source_url

router = APIRouter()
VIEWS = {"watches": "Watches", "alerts": "Alerts", "activity": "Monitoring plans"}


def private_main():
    from app import main
    if not main.AUTHORING_MODE:
        raise HTTPException(403, "Monitor and Operations are available in the private analyst workspace")
    return main


@router.get("/monitor")
def monitor_home(request: Request):
    main = private_main()
    entities, relationships = main.entity_index(), main.all_relationships()
    state = feed_first.load_state(main.INBOX_DIR)
    companies = company_directory.catalog(entities, state=state)
    filters = {key: str(request.query_params.get(key) or "") for key in ("q", "type", "new", "sort", "favorites", "tier", "list", "company", "berry", "status", "completed")}
    selected_berries = list(dict.fromkeys(key for value in request.query_params.getlist("berry") for key in value.split(",") if key))
    if any(key not in main.BERRIES for key in selected_berries):
        raise HTTPException(422, "Choose the berries from the available options")
    filters["berry"] = ",".join(selected_berries)
    view = request.query_params.get("view") or "watches"
    if filters["completed"] not in {"", "1"} or view not in VIEWS or filters["type"] not in ("", *watchlist.WATCH_TYPES) or filters["new"] not in {"", "1"} or filters["sort"] not in {"", "new_first", "alphabetical"} or filters["favorites"] not in {"", "1"} or filters["tier"] and filters["tier"] not in company_directory.TIERS or filters["company"] and filters["company"] not in companies or filters["status"] not in {"", "open", "read", "dismissed", "snoozed"}:
        raise HTTPException(422, "Choose the monitoring filters from the available options")
    if filters["list"] and filters["list"] not in {row["id"] for row in personal_digest.company_lists(state)}:
        raise HTTPException(422, "The selected company list is unavailable; choose another list")
    origin = request.url.path + ("?" + request.url.query if request.url.query else "")
    query = {key: value for key, value in filters.items() if value}
    links = {key: "/monitor?" + urlencode({**query, "view": key}) for key in VIEWS}
    personal_filter = any(filters[key] for key in ("favorites", "tier", "list", "company"))
    questions = {row["id"]: row for row in main.load_strategic_questions()}
    def accepts(kind, key, name):
        subject = (questions if kind == "strategic_question" else entities).get(key) or {}
        actor_ids = {key} if kind == "company" else variety_navigation.company_actors(key, relationships, entities) if kind == "variety" else set()
        if filters["company"]:
            actor_ids &= {filters["company"]}
        if personal_filter and not any(company_directory.matches_marks({actor_id}, state, favorites=filters["favorites"], tier=filters["tier"], list_id=filters["list"]) for actor_id in actor_ids):
            return False
        if selected_berries and not (kind == "berry" and key in selected_berries or set(selected_berries).intersection(subject.get("berry_ids") or [])):
            return False
        return not filters["q"] or filters["q"].casefold() in name.casefold()
    context = {"view": view, "views": VIEWS, "view_links": links, "filters": filters, "return_to": origin,
        "companies": sorted(companies.values(), key=lambda row: row["name"].casefold()), "lists": personal_digest.company_lists(state),
        "tiers": company_directory.TIERS, "berries": main.BERRIES, "selected_berries": selected_berries, "authoring_mode": True, "static_build": False,
        "watch_types": watchlist.WATCH_TYPES, "personal_filter": personal_filter, "watch_error": "", "unresolved": []}
    try:
        records = main.published_evidence()
        raw = watchlist.load_watches(main.INBOX_DIR)
        if view == "watches":
            cards = watchlist.watchlist_index(inbox_dir=main.INBOX_DIR, entities=entities, published_evidence=records,
                signals=main.all_signals(), assessments=main.all_assessments(), recommendations=main.all_recommendations(),
                strategic_questions=main.load_strategic_questions(), sources=main.load_sources(), berry_labels=main.BERRIES,
                watch_type_filter=filters["type"], has_new_only=filters["new"] == "1", sort=filters["sort"] or "new_first")
            context["watches"] = [row for row in cards if accepts(row["watch_type"], row["object_id"], row["name"])]
            resolved = {(row["watch_type"], row["object_id"]) for row in watchlist.watchlist_index(inbox_dir=main.INBOX_DIR, entities=entities,
                published_evidence=[], signals=[], assessments=[], recommendations=[], strategic_questions=main.load_strategic_questions(), sources=[], berry_labels=main.BERRIES)}
            context["unresolved"] = [row for row in raw if (row["watch_type"], row["object_id"]) not in resolved]
        elif view == "alerts":
            data = compose_watchtower(inbox_dir=main.INBOX_DIR, published_evidence=records, strategic_questions=main.load_strategic_questions(),
                entities=entities, berry_labels=main.BERRIES, market_repo=main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR).market_observations, persist=False)
            page = present_watchtower(data)
            context["alerts"] = [row for row in data["alerts"] if accepts(row["subject_type"], row["subject_id"], row["title"] + " " + row["subject_label"]) and (not filters["type"] or row["subject_type"] == filters["type"]) and row["state"] == (filters["status"] or "open")]
            context["alerts"].sort(key=lambda row: str(row.get("event_at") or ""), reverse=True)
            for row in context["alerts"]:
                row["review_label"] = {"LIVE / UNREVIEWED DEVELOPMENT": "Unreviewed development", "LIVE / UNREVIEWED MOVE": "Unreviewed move", "REVIEWED EVIDENCE": "Reviewed source", "MARKET REALITY": "Market observation"}.get(row.get("trust_state"), row.get("trust_state") or "Review status not recorded")
                row["display_date"] = str(row.get("event_at") or "")[:10]
                row["display_sources"] = [{**source, "display_url": public_source_url(source.get("url"))} for source in row.get("sources") or []]
            context["alert_freshness"] = page["radar_freshness_label"]
            context["cache_status"] = page["cache_status"]
        else:
            page = main.build_dimension_page(dimension="monitoring", records=main.queue_items("monitoring"), inbox_dir=main.INBOX_DIR,
                entities=entities, berry_labels=main.BERRIES, signals=main.all_signals(), show_completed=request.query_params.get("completed") == "1")
            context.update(main.monitor_page_model(watch_items=page["items"], entities=entities, berry_labels=main.BERRIES, published=records,
                drafts=main.list_pending_drafts(), signals=main.all_signals(), candidates=main.load_candidates(main.INBOX_DIR), inbox_dir=main.INBOX_DIR,
                health_rows=main.failing_source_health_rows(main.load_sources(), inbox_dir=main.INBOX_DIR), include_drafts=True))
            # Inventory rows use explicit entity associations, never title guesses.
            context["watch_items"] = [row for row in context["watch_items"] if not any(filters[k] for k in ("favorites", "tier", "list", "company", "berry", "q", "type")) or any(accepts(actor["entity_type"], actor["id"], actor["name"]) and (not filters["type"] or actor["entity_type"] == filters["type"]) for actor in row.get("watched_entities") or [])]
            context["reviewer"] = main.session_username(request) or main.review_username() or ""
    except ValueError as exc:
        context["watch_error"] = str(exc)
    return main.templates.TemplateResponse(request=request, name="monitor_workspace.html", context=context)


@router.get("/operations")
def operations_home(request: Request):
    main = private_main()
    repositories = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    report = main.build_status_report(repositories=repositories, data_dir=main.DATA_DIR, inbox_dir=main.INBOX_DIR)
    sources = {row["id"]: row for row in main.load_sources() if row.get("id")}
    ops = main.build_review_operations(inbox_dir=main.INBOX_DIR, pending_service=main.get_pending_review_query_service(main.INBOX_DIR),
        entities=main.entity_index(), sources=sources, published=main.published_evidence(), atomic_drafts=main.list_drafts_metadata(),
        extraction_gate={"enabled": False, "runnable": False}, berry_labels=main.BERRIES)
    return main.templates.TemplateResponse(request=request, name="operations_workspace.html", context={
        "report": report, "ops": ops, "recent_runs": main.list_recent_runs(main.INBOX_DIR),
        "authoring_mode": True, "berries": main.BERRIES, "static_build": False})
