"""Explicit learning research and private editable educational lessons."""
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.personal_digest_routes import require_edit
from app.services import learn_research, learner
from app.services.ai_gateway.credentials import MissingCredentialError, resolve_perplexity_api_key
from app.services.ai_gateway.perplexity_deep_research import DeepResearchClient, ResearchError

router = APIRouter()


def client_factory():
    try:
        key = resolve_perplexity_api_key()
    except MissingCredentialError as exc:
        raise ResearchError("Research is not connected in this workspace. Your topic has been saved; no provider request was sent.") from exc
    return DeepResearchClient(key)


def private_store():
    from app import main
    if not main.AUTHORING_MODE:
        raise HTTPException(403, "Learning drafts require the analyst workspace")
    try:
        return main, learn_research.load(main.INBOX_DIR)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


def get_job(key):
    main, store = private_store()
    row = store["jobs"].get(key)
    if not row:
        raise HTTPException(404, "This research run is unavailable")
    return main, row


@router.get("/learn/research/new")
def new_research(request: Request):
    main, store = private_store()
    topic = str(request.query_params.get("topic") or "")[:220]
    excerpt = str(request.query_params.get("excerpt") or "")[:2000]
    previous = store["lessons"].get(str(request.query_params.get("update_from") or ""))
    if request.query_params.get("update_from") and not previous:
        raise HTTPException(404, "The lesson to update is unavailable")
    if previous and not topic:
        topic = previous["request"]["topic"]
    matches = learner.search_concepts(topic) if topic else []
    lessons = [row for row in store["lessons"].values() if topic and topic.casefold() in row["title"].casefold()]
    return main.templates.TemplateResponse(request=request, name="learn_research_form.html", context={
        "topic": topic, "excerpt": excerpt, "token": uuid4().hex, "matches": matches, "lessons": lessons,
        "previous": previous, "generation": uuid4().hex if previous else "",
        "return_to": learn_research.return_path(request.query_params.get("return_to")),
        "selected_concept": str(request.query_params.get("concept_id") or (previous or {}).get("request", {}).get("concept_id") or ""),
        "selected_berry": str(request.query_params.get("berry") or (previous or {}).get("request", {}).get("berry") or ""),
        "selected_geography": str(request.query_params.get("geography") or (previous or {}).get("request", {}).get("geography") or ""),
        "selected_class": (previous or {}).get("request", {}).get("knowledge_class") or "current_technical_guidance",
        "selected_pillar": (previous or {}).get("request", {}).get("pillar") or "plant_biology_agronomy",
        "regions": sorted([row for row in main.all_entities() if row.get("entity_type") == "geography"], key=lambda row: row["name"]),
        "concepts": learner.all_concepts(), "pillars": learner.PILLAR_LABELS,
        "classes": learner.KNOWLEDGE_CLASS_LABELS, "berries": main.BERRIES,
    })


@router.post("/learn/research/start")
async def start_research(request: Request, background_tasks: BackgroundTasks):
    require_edit(request)
    from app import main
    form = await request.form()
    try:
        store = learn_research.load(main.INBOX_DIR)
        approved = learn_research.clean_request(form, berries=main.BERRIES,
            entities=main.entity_index(), concepts=learner.all_concepts(), lessons=store["lessons"])
        job, created = learn_research.reserve(main.INBOX_DIR, approved, str(form.get("token") or ""))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if created:
        background_tasks.add_task(learn_research.submit, main.INBOX_DIR, job["id"], client_factory)
    return RedirectResponse("/learn/research/jobs/" + job["id"], status_code=303)


@router.get("/learn/research/jobs/{key}")
def research_job(request: Request, key: str):
    main, row = get_job(key)
    return main.templates.TemplateResponse(request=request, name="learn_research_job.html", context={"job": row})


@router.post("/learn/research/jobs/{key}/check")
def check_research(request: Request, key: str):
    require_edit(request)
    main, row = get_job(key)
    if row["status"] not in learn_research.TERMINAL and row["provider_id"]:
        try:
            learn_research.apply_result(main.INBOX_DIR, key, client_factory().check(row["provider_id"]), expected_revision=row["revision"])
        except ResearchError as exc:
            learn_research.failure(main.INBOX_DIR, key, exc)
    return RedirectResponse("/learn/research/jobs/" + key, status_code=303)


@router.post("/learn/research/jobs/{key}/recover")
async def recover_research(request: Request, key: str):
    require_edit(request)
    main, row = get_job(key)
    if row["status"] not in {"submitting", "submission_uncertain", "requested"} or row["provider_id"]:
        raise HTTPException(409, "This run already has a provider reference")
    form = await request.form()
    if form.get("confirm_run") != "yes":
        raise HTTPException(422, "Confirm that the provider run matches this topic")
    try:
        # Retrieve only. This never submits a second paid research request.
        result = client_factory().check(str(form.get("provider_id") or "").strip())
        learn_research.apply_result(main.INBOX_DIR, key, result, expected_revision=row["revision"])
    except ResearchError as exc:
        raise HTTPException(422, str(exc)) from exc
    return RedirectResponse("/learn/research/jobs/" + key, status_code=303)


@router.post("/learn/research/jobs/{key}/cancel")
def cancel_research(request: Request, key: str):
    require_edit(request)
    main, row = get_job(key)
    if row["status"] not in learn_research.TERMINAL and row["provider_id"]:
        try:
            learn_research.apply_result(main.INBOX_DIR, key, client_factory().cancel(row["provider_id"]), expected_revision=row["revision"])
        except ResearchError as exc:
            learn_research.failure(main.INBOX_DIR, key, exc)
    return RedirectResponse("/learn/research/jobs/" + key, status_code=303)


@router.get("/learn/lessons/{key}")
def lesson_page(request: Request, key: str):
    main, store = private_store()
    row = store["lessons"].get(key)
    if not row:
        raise HTTPException(404, "This lesson is unavailable")
    return main.templates.TemplateResponse(request=request, name="learn_lesson.html", context={
        "lesson": row, "job": store["jobs"][row["job_id"]], "blocks": learn_research.reading_blocks(row["text"], row["citations"]),
        "teaching_concept": next((concept for concept in learner.all_concepts() if concept["id"] == row["request"].get("concept_id")), None),
        "pillar_label": learner.PILLAR_LABELS[row["request"]["pillar"]],
        "class_label": learner.KNOWLEDGE_CLASS_LABELS[row["request"]["knowledge_class"]],
        "return_to": learn_research.return_path(request.query_params.get("return_to") or row["request"]["return_to"]),
    })


@router.post("/learn/lessons/{key}/save")
async def save_lesson(request: Request, key: str):
    require_edit(request)
    main, _ = private_store()
    form = await request.form()
    try:
        learn_research.edit_lesson(main.INBOX_DIR, key, revision=form.get("revision"),
            title=str(form.get("title") or ""), text=str(form.get("text") or ""), review_by=str(form.get("review_by") or ""))
    except ValueError as exc:
        raise HTTPException(409 if "another window" in str(exc) else 422, str(exc)) from exc
    return RedirectResponse("/learn/lessons/" + key + "?saved=1", status_code=303)
