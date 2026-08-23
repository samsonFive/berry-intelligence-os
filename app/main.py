from __future__ import annotations

import asyncio
import difflib
import json
import os
import re
import secrets
import shutil
import sys
import time
from collections import Counter, defaultdict
from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode, urlparse, urlsplit

import feedparser
import httpx
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from jsonschema import Draft202012Validator, FormatChecker

from app.composition import (
    get_domain_services,
    get_pending_review_query_service,
    get_query_services,
    get_repositories,
    get_unit_of_work,
)
from app.queries.timeline import entity_activity, entity_intelligence_timeline, max_priority_level
from app.services.berries.geography import (
    REGIONS,
    REGION_LOOKUP,
    berry_label,
    entity_regions,
    evidence_regions,
    geography_region,
)
from app.services.berries.variety import (
    _normalize_patent_number,
    variety_patent_link,
    variety_trait_profile,
)
from app.repositories.base import DuplicateRecord
from app.services.deterministic_tagging import apply_known_name_matches, matchers_from_entities
from app.services.entity_alias_recall import linked_evidence_for_entity
from app.services.media_discovery import list_discovered_items, read_source_discovery_state
from app.services.review_publish import PublishRequest, ReviewPublishService
from app.services.publication_review_workspace import (
    apply_dossier_prefill,
    build_publication_review_dossier,
)
from app.services.html_text import decode_html_text
from app.services.review_events import append_review_event, remove_created_event
from app.services.source_freshness import (
    FRESHNESS_LABELS,
    SOURCE_CADENCE_DAYS,
    aggregate_source_coverage,
    classify_source_freshness,
    index_latest_item_dates,
)
from app.services.source_fidelity_recovery import (
    decide_recovery_artifact,
    load_recovery_artifacts,
    save_recovery_decision,
)
from app.services.ui_context import (
    apply_ui_cookies,
    matches_berry_context,
    parse_berry,
    parse_feed_view,
    persist_ui_prefs,
    read_ui_context,
)
from app.services.analyst_queue import (
    apply_action as apply_queue_action,
    build_dimension_page,
    bulk_dismiss_pending,
    bulk_mark_read,
    is_open_signal_alert,
    is_pending_dismissed,
    load_state as load_analyst_queue_state,
    pending_position_proposals,
    present_queue_item,
    proposal_state,
    signal_alert_state,
    work_counts,
)
from app.services.commercial_positions import commercial_page_model
from app.services.testing_workspace import enrich_testing_item, related_indexes, testing_page_model
from app.services.draft_attribution import attribute_draft, draft_matches_entity
from app.services.review_workbench import (
    analyst_transcript_label,
    attach_publication_card,
    build_review_workbench,
    build_scanner_summary,
    format_locator,
    load_publication_transcript_readiness,
    unknown_transcript_readiness,
)
from app.runtime_config import (
    credentials_match,
    remote_interactive_enabled,
    resolve_data_dir,
    resolve_inbox_dir,
    review_username,
    validate_remote_interactive_config,
)
from app.services.intelligence_feed import (
    annotate_feed_semantics,
    build_intelligence_feed,
    build_reader,
    present_feed_item,
)
from app.services.assessment_scope import (
    assessment_berry_scope,
    assessment_market_berry_ids,
    attach_assessment_scope,
    parse_assessment_market_ids,
)
from app.services.morning_brief import brief_last_seen, build_morning_brief
from app.services.monitor_workspace import (
    failing_source_health_rows,
    group_source_health,
    monitor_page_model,
    present_source_health_rows,
    retry_hints_by_source,
)
from app.services.variety_workspace import (
    VIEWS as VARIETY_VIEWS,
    COMPARE_MAX_VARIETIES,
    berry_inventory,
    present_competition,
    present_observation_workspace,
    present_variety_compare,
    present_variety_detail,
    present_variety_index,
)
from app.services.global_search import (
    GROUP_CAP_DEFAULT,
    SearchPools,
    build_search_documents,
    search_global,
)
from app.services.learner import (
    all_concepts as learn_all_concepts,
    concept_by_slug as learn_concept_by_slug,
    concepts_by_pillar as learn_concepts_by_pillar,
    learn_href_for_trait_id,
    related_concepts as learn_related_concepts,
    related_intelligence_for_concept,
    search_concepts as learn_search_concepts,
)
from app.services.signal_candidates import SignalCandidateError, load_candidates
from app.services.signal_review import (
    EMERGING_STATUSES,
    StaleSignalCandidateError,
    apply_and_persist_decision,
    candidate_by_id,
    candidates_for_thread,
    evidence_quality_for_record,
    lookup_candidate,
    open_signals_for_entity,
    present_candidates,
    present_review,
    triage_groups,
)
from app.services.story_threads import compress_recent_intelligence, expand_with_related, thread_for_item
from app.session_auth import (
    EnvSessionMiddleware,
    auth_template_context,
    clear_login_failures,
    clear_session,
    establish_session,
    login_is_throttled,
    record_login_failure,
    remote_auth_middleware,
    safe_next_path,
    session_username,
)

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = resolve_data_dir(BASE_DIR)
INBOX_DIR = resolve_inbox_dir(BASE_DIR)
SCHEMAS_DIR = BASE_DIR / "schemas"

# Authoring mode permits local writes (intake, review, publish). A future
# read-only / static deployment sets BIOS_MODE=readonly so write endpoints
# are unavailable.
AUTHORING_MODE = os.environ.get("BIOS_MODE", "authoring") == "authoring"

# Off by default on purpose: the poll loop fires an immediate check as soon
# as it starts (see source_polling_loop() below), so leaving this on by
# default meant every plain dev-server restart during iteration silently
# fired live network requests against every configured source and wrote
# real evidence into the dataset -- discovered the hard way after seeding
# ~40 keyword sources and restarting the app twice while testing a template
# change, which produced over 1000 auto-captured records in minutes. A real
# deployment that wants monitoring sets ENABLE_SOURCE_POLLING=true
# explicitly; nothing else changes that decision on its behalf.
SOURCE_POLLING_ENABLED = os.environ.get("ENABLE_SOURCE_POLLING", "").lower() in {"1", "true", "yes"}

INTAKE_TYPES = {
    "article_or_url": "Article or URL",
    "note_or_observation": "Note / Observation",
    "uploaded_report": "Upload Report",
    "standalone_fact": "Standalone Fact",
}

INTAKE_SOURCE_TYPES = {
    "article_or_url": "article",
    "note_or_observation": "note_observation",
    "uploaded_report": "uploaded_report",
    "standalone_fact": "standalone_fact",
}

# The multi-berry foundation declared in the PRD (section 1), not a
# privileged-entity assumption: every berry is offered identically.
BERRIES = {
    "berry-blueberry": "Blueberry",
    "berry-raspberry": "Raspberry",
    "berry-strawberry": "Strawberry",
    "berry-blackberry": "Blackberry",
}

ENTITY_FOLDER_OVERRIDES = {
    "company": "companies",
    "variety": "varieties",
    "geography": "geographies",
    "person": "people",
    "berry": "berries",
}

RELATIONSHIP_PREDICATES = [
    "owns", "develops", "licenses", "distributes", "grows",
    "trials", "sells", "carries", "partners_with", "operates_in",
]

FACT_CLASSIFICATIONS = ["fact", "claim"]
FACT_CONFIDENCE_LEVELS = ["low", "medium", "high"]
NUM_FACT_ROWS = 3
NUM_RELATIONSHIP_ROWS = 2

REJECTION_CATEGORIES = {
    "not_decision_relevant": "Not decision-relevant",
    "unsupported": "Unsupported by source/transcript",
    "overstates_source": "Overstates source",
    "duplicate": "Duplicate",
    "not_atomic": "Not atomic",
    "transcript_error": "Transcript error",
    "wrong_links": "Wrong links/entities",
    "other": "Other",
}

SIGNAL_DIRECTIONS = ["strengthening", "weakening", "emerging", "stable"]
SIGNAL_STRENGTHS = ["low", "medium", "high"]
SIGNAL_STATUSES = ["active", "watch", "resolved"]
PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2, "none": 3}

# Assessment and Recommendation are human-authored interpretation/action
# objects, downstream of Facts/Evidence and Signals respectively (see
# docs/v2/03-DOMAIN-MODEL.md's Recommendation -> Assessment/Signal -> Facts
# -> Evidence -> Source lineage chain). Both reuse FACT_CONFIDENCE_LEVELS'
# low/medium/high value set for their own confidence/priority scalars rather
# than redefining an identical list.
INTELLIGENCE_RECORD_STATUSES = ["active", "superseded", "withdrawn"]
RECOMMENDATION_PRIORITIES = ["low", "medium", "high"]

SOURCE_TYPES = {
    "rss": "RSS / Atom feed",
    "keyword": "Keyword search",
    "reference": "Reference (manually reviewed)",
}
SOURCE_POLL_INTERVAL_SECONDS = 15 * 60
SOURCE_FETCH_TIMEOUT_SECONDS = 15
SOURCE_USER_AGENT = "berry-intelligence-os-source-monitor/1.0"
SOURCE_MAX_NEW_ITEMS_PER_CHECK = 20

# A source's own coverage-taxonomy fields (entity type, region, priority,
# cadence). Deliberately separate from the entity/evidence system's own
# taxonomies below:
# - SOURCE_REGIONS is a coarser, self-declared "what does this outlet cover"
#   tag (North America / South America / Europe / Asia-Pacific / Africa /
#   Global), not the finer Americas/Europe/Oceania/Middle East & Africa
#   REGIONS used for evidence/entities (derived from actual geography
#   linkage via entity_regions()/evidence_regions()). Forcing sources onto
#   that taxonomy would either lose the Americas-Africa/Asia-Pacific split
#   this list needs or require reworking region filtering everywhere else
#   for a directory feature that doesn't need that precision.
SOURCE_ENTITY_TYPES = {
    "breeding_program": "Breeding Program",
    "genetics_company": "Genetics Company / IP Licensor",
    "grower_marketer": "Grower-Marketer / Large-Scale Producer",
    "nursery_propagator": "Nursery / Propagator",
    "trade_association": "Trade Association / Industry Council",
    "government_regulatory": "Government / Regulatory / Statistical Agency",
    "trade_press": "Trade Press / News Outlet",
    "market_research": "Market Research / Data Analytics",
    "retailer_foodservice": "Retailer / Foodservice Buyer",
    "academic_journal": "Academic Journal / Conference Proceeding",
}
SOURCE_REGIONS = {
    "north_america": "North America",
    "south_america": "South America",
    "europe": "Europe",
    "asia_pacific": "Asia-Pacific",
    "africa": "Africa",
    "global": "Global",
}
SOURCE_PRIORITIES = {"high": "High", "medium": "Medium", "low": "Low"}
SOURCE_CADENCES = {
    "realtime": "Real-time Filing",
    "weekly": "Weekly News",
    "biweekly": "Biweekly",
    "monthly": "Monthly",
    "quarterly": "Quarterly Data Release",
    "annual": "Annual Report",
    "event_driven": "Event-driven",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fail closed before serving if remote interactive mode is on without
    # credentials. Skip the hard startup raise under pytest so request-level
    # tests can observe the 503; uvicorn production still refuses to boot.
    if "pytest" not in sys.modules:
        validate_remote_interactive_config()
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    (INBOX_DIR / "evidence").mkdir(parents=True, exist_ok=True)
    # Never poll external sources during tests -- pytest importing this
    # module must not trigger real network calls. Real deployments always
    # have "pytest" absent from sys.modules. Also gated on
    # SOURCE_POLLING_ENABLED, off by default -- see its definition above.
    task = None
    if "pytest" not in sys.modules and AUTHORING_MODE and SOURCE_POLLING_ENABLED:
        task = asyncio.create_task(source_polling_loop())
    yield
    if task is not None:
        task.cancel()


app = FastAPI(title="Berry Intelligence OS", version="0.1.0", lifespan=lifespan)
app.middleware("http")(remote_auth_middleware)
app.add_middleware(EnvSessionMiddleware)
app.mount("/static", StaticFiles(directory=BASE_DIR / "app" / "static"), name="static")


def _assemble_morning_brief(
    *,
    mark_seen: bool = False,
    include_coverage: bool = False,
    mode: str = "full",
    include_signal_candidates: bool | None = None,
    drafts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    published = published_evidence()
    coverage = {}
    freshness = {}
    discovered: list[dict[str, Any]] = []
    recommendations: list[dict[str, Any]] = []
    if include_coverage:
        sources_ctx = sources_page_context(None, None, None, None, None, "entity_type", None)
        coverage = sources_ctx.get("source_coverage") or {}
        freshness = sources_ctx.get("freshness_by_source") or {}
        discovered = list_discovered_items(INBOX_DIR)
        recommendations = all_recommendations()
    return build_morning_brief(
        inbox_dir=INBOX_DIR,
        published=published,
        drafts=list_pending_drafts() if drafts is None else drafts,
        unvalidated=unvalidated_auto_captured_evidence() if drafts is None else [],
        signals=[] if mode == "pending" else all_signals(),
        entities=entity_index(),
        sources=load_sources(),
        berry_labels=BERRIES,
        source_coverage=coverage,
        freshness_by_source=freshness,
        discovered=discovered,
        recommendations=recommendations,
        mark_seen=mark_seen,
        include_signal_candidates=True if include_signal_candidates is None else include_signal_candidates,
        mode=mode,
    )


_NAV_WORK_CACHE: dict[str, Any] = {"key": None, "value": None}
_SEARCH_DOC_CACHE: dict[str, Any] = {"key": None, "docs": None}
COMPANY_BERRY_ORDER = ("berry-strawberry", "berry-blueberry", "berry-raspberry", "berry-blackberry")
COMPANY_WHAT_CHANGED_DAYS = 30


def _path_sig(path: Path) -> tuple[str, int, int]:
    try:
        st = path.stat()
    except OSError:
        return (str(path), 0, 0)
    return (str(path), int(st.st_mtime_ns), int(st.st_size))


def _json_folder_sig(folder: Path) -> tuple[tuple[str, int, int], ...]:
    if not folder.is_dir():
        return ()
    rows: list[tuple[str, int, int]] = []
    for path in folder.glob("*.json"):
        try:
            st = path.stat()
        except OSError:
            continue
        rows.append((path.name, int(st.st_mtime_ns), int(st.st_size)))
    return tuple(sorted(rows))


def _json_tree_sig(folder: Path) -> tuple[tuple[str, int, int], ...]:
    if not folder.is_dir():
        return ()
    rows: list[tuple[str, int, int]] = []
    for path in folder.rglob("*.json"):
        try:
            st = path.stat()
        except OSError:
            continue
        rows.append((str(path.relative_to(folder)), int(st.st_mtime_ns), int(st.st_size)))
    return tuple(sorted(rows))


def _nav_work_cache_key() -> tuple[Any, ...]:
    return (
        str(INBOX_DIR),
        str(DATA_DIR),
        _json_folder_sig(INBOX_DIR / "evidence"),
        _path_sig(INBOX_DIR / "analyst_queue_state.json"),
        _json_folder_sig(INBOX_DIR / "signal_candidates"),
        _json_folder_sig(DATA_DIR / "evidence"),
        _json_folder_sig(DATA_DIR / "signals"),
    )


# Landscape (V2) recomputes an O(companies x evidence) + O(varieties x
# evidence) aggregation per request (see BerriesLandscapeService docstring);
# uncached this was 2-3s per berry and 4-8s for the cross-berry ALL view --
# the exact "old Pending Review mistake" this mission was told not to
# repeat. Trusted data/ only changes between deploys/publications, so a
# folder-signature-keyed cache (same pattern as _NAV_WORK_CACHE above) is
# safe and correct: a publish/promotion changes file mtimes, invalidating
# the key automatically.
_LANDSCAPE_CACHE: dict[str, Any] = {"key": None, "value": {}}


def _landscape_cache_key() -> tuple[Any, ...]:
    return (
        _json_tree_sig(DATA_DIR / "entities"),
        _json_folder_sig(DATA_DIR / "evidence"),
        _json_folder_sig(DATA_DIR / "relationships"),
        _json_folder_sig(DATA_DIR / "signals"),
        _json_folder_sig(DATA_DIR / "assessments"),
        _json_folder_sig(DATA_DIR / "recommendations"),
        _json_folder_sig(DATA_DIR / "strategic-questions"),
    )


def _cached_landscape_context(berry_id: str, region: str, intelligence_state: str) -> dict[str, Any]:
    key = _landscape_cache_key()
    cache_key = (key, "berry", berry_id, region, intelligence_state)
    if _LANDSCAPE_CACHE["key"] != key:
        _LANDSCAPE_CACHE["key"] = key
        _LANDSCAPE_CACHE["value"] = {}
    if cache_key not in _LANDSCAPE_CACHE["value"]:
        _LANDSCAPE_CACHE["value"][cache_key] = landscape_context(berry_id, region, intelligence_state)
    return _LANDSCAPE_CACHE["value"][cache_key]


def _cached_landscape_context_all() -> dict[str, Any]:
    key = _landscape_cache_key()
    cache_key = (key, "all")
    if _LANDSCAPE_CACHE["key"] != key:
        _LANDSCAPE_CACHE["key"] = key
        _LANDSCAPE_CACHE["value"] = {}
    if cache_key not in _LANDSCAPE_CACHE["value"]:
        _LANDSCAPE_CACHE["value"][cache_key] = get_domain_services(DATA_DIR).landscape.landscape_context_all_berries(BERRIES)
    return _LANDSCAPE_CACHE["value"][cache_key]


def _record_activity_stamp(record: dict[str, Any]) -> str:
    return str(
        record.get("captured_date")
        or record.get("published_date")
        or record.get("reviewed_at")
        or record.get("created_at")
        or ""
    )


def _compute_nav_work_counts() -> dict[str, Any]:
    """Cheap HTML-nav badges. Ranked Brief / Pending work stays on those pages."""

    published = published_evidence()
    signals = all_signals()
    counts = work_counts(inbox_dir=INBOX_DIR, published=published, signals=signals)
    state = load_analyst_queue_state(INBOX_DIR)
    pending_rows = list(list_pending_drafts())
    pending_rows.extend(
        record
        for record in published
        if record.get("auto_captured") and not record.get("validated")
    )
    pending_open = 0
    for record in pending_rows:
        item_id = str(record.get("id") or "")
        if item_id and not is_pending_dismissed(item_id, state):
            pending_open += 1
    counts["pending_open"] = pending_open
    # Nav Pending is uncleared decisions, not ranked Review-now.
    counts["review_now"] = pending_open
    last_seen = brief_last_seen(INBOX_DIR)
    if last_seen:
        seen_ids: set[str] = set()
        brief_action = 0
        for record in [*published, *pending_rows]:
            item_id = str(record.get("id") or "")
            if not item_id or item_id in seen_ids:
                continue
            seen_ids.add(item_id)
            stamp = _record_activity_stamp(record)
            if stamp and stamp > last_seen and not is_pending_dismissed(item_id, state):
                brief_action += 1
        counts["brief_action"] = brief_action
    else:
        counts["brief_action"] = int(counts.get("reading_action") or 0)
    counts["emerging_signals"] = sum(
        1 for candidate in load_candidates(INBOX_DIR) if candidate.get("status") in EMERGING_STATUSES
    )
    return counts


def nav_work_template_context(request: Request) -> dict[str, Any]:
    """Nav action counts for HTML pages. Overlay fragments skip nav work entirely."""

    ui_context = read_ui_context(request, BERRIES, inbox_dir=INBOX_DIR)
    if str(getattr(request.url, "path", "") or "").startswith("/api/"):
        return {
            "nav_work_counts": {},
            "ui_context": ui_context,
            "berries": BERRIES,
        }
    key = _nav_work_cache_key()
    if _NAV_WORK_CACHE["key"] != key or _NAV_WORK_CACHE["value"] is None:
        _NAV_WORK_CACHE["key"] = key
        _NAV_WORK_CACHE["value"] = _compute_nav_work_counts()
    return {
        "nav_work_counts": _NAV_WORK_CACHE["value"],
        "ui_context": ui_context,
        "berries": BERRIES,
    }


templates = Jinja2Templates(
    directory=BASE_DIR / "app" / "templates",
    context_processors=[auth_template_context, nav_work_template_context],
)
templates.env.globals["pending_review_count"] = lambda: len(list_pending_drafts()) + len(unvalidated_auto_captured_evidence())
templates.env.globals["queue_counts"] = lambda: queue_counts()
templates.env.globals["learn_href_for_trait"] = learn_href_for_trait_id
templates.env.globals["nav_work"] = lambda: work_counts(
    inbox_dir=INBOX_DIR,
    published=published_evidence(),
    signals=all_signals(),
)


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    """Liveness probe. Unauthenticated even in remote interactive mode."""

    return {
        "ok": True,
        "remote_interactive": remote_interactive_enabled(),
    }


def _source_fidelity_folder() -> Path:
    return INBOX_DIR / "source_fidelity" / "artifacts"


@app.get("/source-fidelity", response_class=HTMLResponse)
def source_fidelity_queue(request: Request, state: str = "pending") -> HTMLResponse:
    trusted_by_id = {row["id"]: row for row in published_evidence()}
    rows = []
    for artifact in load_recovery_artifacts(_source_fidelity_folder()):
        trusted = trusted_by_id.get(artifact.get("evidence_id"))
        if not trusted:
            continue
        review_state = (artifact.get("review") or {}).get("status") or "pending"
        if state != "all" and review_state != state:
            continue
        berries = set(trusted.get("berry_ids") or [])
        rows.append({"artifact": artifact, "trusted": trusted, "review_state": review_state, "caneberry": bool(berries & {"berry-raspberry", "berry-blackberry"})})
    match_rank = {"EXACT_IDENTITY_MATCH": 0, "EXACT_URL_MATCH": 1, "LINEAGE_MATCH": 2}
    rows.sort(key=lambda row: (match_rank.get(row["artifact"].get("match_class"), 9), row["artifact"].get("artifact_type") != "article", not row["caneberry"], -int(row["artifact"].get("source_chars") or 0), row["trusted"]["id"]))
    return templates.TemplateResponse(request=request, name="source_fidelity_queue.html", context={"rows": rows, "state": state})


@app.get("/source-fidelity/{evidence_id}", response_class=HTMLResponse)
def source_fidelity_detail(request: Request, evidence_id: str) -> HTMLResponse:
    trusted = get_repositories(DATA_DIR, SCHEMAS_DIR).evidence.get(evidence_id)
    path = _source_fidelity_folder() / f"{evidence_id}.json"
    if not trusted or trusted.get("status") != "published" or not path.is_file():
        raise HTTPException(status_code=404, detail="source-fidelity recovery not found")
    artifact = json.loads(path.read_text(encoding="utf-8"))
    return templates.TemplateResponse(request=request, name="source_fidelity_detail.html", context={"trusted": trusted, "artifact": artifact, "reviewer": session_username(request) or review_username() or ""})


@app.post("/source-fidelity/{evidence_id}/decision")
def source_fidelity_decision(
    request: Request,
    evidence_id: str,
    decision: str = Form(...),
    reviewer: str = Form(""),
) -> RedirectResponse:
    trusted = get_repositories(DATA_DIR, SCHEMAS_DIR).evidence.get(evidence_id)
    path = _source_fidelity_folder() / f"{evidence_id}.json"
    if not trusted or trusted.get("status") != "published" or not path.is_file():
        raise HTTPException(status_code=404, detail="source-fidelity recovery not found")
    before = json.loads(path.read_text(encoding="utf-8"))
    actor = session_username(request) or reviewer.strip() or review_username() or ""
    prior_state = str((before.get("review") or {}).get("status") or "pending")
    event = None
    try:
        after = decide_recovery_artifact(before, trusted, decision=decision, reviewer=actor)
        event = append_review_event(
            INBOX_DIR,
            workflow="source_fidelity_review",
            object_id=evidence_id,
            object_type="source_artifact",
            action=decision,
            prior_state=prior_state,
            new_state=decision,
            actor=actor,
            subject=trusted,
        )
        save_recovery_decision(path, before, after)
    except ValueError as exc:
        if event is not None:
            remove_created_event(event)
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception:
        if event is not None:
            remove_created_event(event)
        raise
    return RedirectResponse(url=f"/source-fidelity/{evidence_id}", status_code=303)


LOGIN_ERROR = "Username or password is incorrect."
LOGIN_THROTTLED = "Too many sign-in attempts. Try again in a few minutes."


def _login_page(
    request: Request,
    *,
    next_path: str,
    username: str = "",
    error: str | None = None,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "next_path": safe_next_path(next_path),
            "username": username,
            "error": error,
        },
    )


@app.get("/login", response_class=HTMLResponse, response_model=None)
def login_form(request: Request, next: str = "") -> HTMLResponse | RedirectResponse:
    destination = safe_next_path(next)
    if session_username(request):
        return RedirectResponse(url=destination, status_code=303)
    return _login_page(request, next_path=destination)


@app.post("/login", response_model=None)
async def login_submit(
    request: Request,
    username: str = Form(""),
    password: str = Form(""),
    next: str = Form(""),
) -> HTMLResponse | RedirectResponse:
    destination = safe_next_path(next)
    presented_username = username.strip()
    if login_is_throttled(request):
        return _login_page(
            request,
            next_path=destination,
            username=presented_username,
            error=LOGIN_THROTTLED,
        )
    if credentials_match(presented_username, password):
        establish_session(request, presented_username)
        clear_login_failures(request)
        return RedirectResponse(url=destination, status_code=303)
    record_login_failure(request)
    return _login_page(
        request,
        next_path=destination,
        username=presented_username,
        error=LOGIN_ERROR,
    )


@app.post("/logout")
async def logout(request: Request) -> RedirectResponse:
    clear_session(request)
    return RedirectResponse(url="/login", status_code=303)


@app.post("/ui/context")
async def set_ui_context(
    request: Request,
    berry: str = Form(default="global"),
    view: str = Form(default=""),
    next: str = Form(default="/brief"),
) -> RedirectResponse:
    current = read_ui_context(request, BERRIES, inbox_dir=INBOX_DIR)
    berry_id = parse_berry(berry, BERRIES)
    feed_view = parse_feed_view(view or current["feed_view"])
    persist_ui_prefs(INBOX_DIR, berry=berry_id, feed_view=feed_view)
    response = RedirectResponse(url=safe_next_path(next), status_code=303)
    apply_ui_cookies(response, berry=berry_id, feed_view=feed_view)
    return response


_JSON_FOLDER_CACHE: dict[Path, tuple[tuple[tuple[str, int, int], ...], list[dict[str, Any]]]] = {}


def load_json_files(folder: Path) -> list[dict[str, Any]]:
    """Read every *.json file in a folder, cached against a signature of
    (filename, mtime) for every file currently in it.

    At the record volumes this project now runs at (1500+ evidence files
    from a single auto-capture session), re-reading and re-parsing every
    file on every call -- which this function did unconditionally before,
    and which every route calls at least once per request, often more --
    measured at 0.6-1.1s per call and made the whole app close to unusable.
    stat()-ing every file is still O(n), but a stat is microseconds versus
    milliseconds for a full read+parse, so this is a ~100-1000x speedup for
    the common case where nothing changed between calls.

    Correct by construction rather than by remembering to invalidate: the
    signature is recomputed from the actual filesystem state on every call,
    so any write through any code path -- save_evidence(), a direct
    path.write_text() elsewhere, even hand-editing a file outside the app --
    is picked up on the very next call. No dirty flag to forget to set.

    The signature includes st_size, not just mtime: some filesystems
    (notably overlayfs, used by many containers/CI) give coarse mtime
    granularity, so two writes to the same file within one tick can share an
    identical st_mtime_ns. Keying on mtime alone silently returned a stale
    cached read after a same-tick rewrite (e.g. saving a draft then
    re-listing in the same request). Including the byte size detects every
    content-length change through any code path; the only remaining blind
    spot is a same-size rewrite landing in the same mtime tick, which a
    content hash would close at the cost of the read this cache exists to
    avoid."""
    if not folder.exists():
        return []
    paths = sorted(folder.rglob("*.json"))

    def _signature_entry(path: Path) -> tuple[str, int, int]:
        stat_result = path.stat()
        return (str(path), stat_result.st_mtime_ns, stat_result.st_size)

    signature = tuple(_signature_entry(p) for p in paths)
    cached = _JSON_FOLDER_CACHE.get(folder)
    if cached is not None and cached[0] == signature:
        return cached[1]
    records: list[dict[str, Any]] = []
    for path in paths:
        with path.open("r", encoding="utf-8") as handle:
            records.append(json.load(handle))
    _JSON_FOLDER_CACHE[folder] = (signature, records)
    return records


def all_evidence() -> list[dict[str, Any]]:
    return get_repositories(DATA_DIR, SCHEMAS_DIR).evidence.list()


def published_evidence() -> list[dict[str, Any]]:
    records = [r for r in all_evidence() if r.get("status") == "published"]
    return sorted(records, key=lambda r: r.get("published_date") or r.get("captured_date", ""), reverse=True)


def _evidence_index() -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for record in published_evidence() + list_pending_drafts() + unvalidated_auto_captured_evidence():
        record_id = str(record.get("id") or "")
        if record_id:
            rows[record_id] = record
    return rows


def unvalidated_auto_captured_evidence() -> list[dict[str, Any]]:
    """Auto-captured evidence still awaiting a human validate/purge decision
    -- already live in the newsfeed (see the "AUTO-CAPTURED -- UNVALIDATED"
    banner there), but also surfaced here so there's one place that shows
    everything waiting on a review decision, not just intake drafts.
    Excludes the pre-auto-capture seed dataset, which predates the
    `validated` field and was never part of this workflow.

    Sorted by the source's own monitoring_priority (the same field shown on
    the Sources page) so the most important items surface first -- a
    transparent, human-set signal, not an inferred score."""
    records = [r for r in all_evidence() if r.get("auto_captured") and not r.get("validated")]
    priority_by_source = {s["id"]: s.get("monitoring_priority") for s in load_sources()}
    return sorted(
        records,
        key=lambda r: (
            SOURCE_PRIORITY_RANK.get(priority_by_source.get(r.get("source_id")), 3),
            r.get("captured_date", ""),
        ),
    )


def all_entities() -> list[dict[str, Any]]:
    return get_repositories(DATA_DIR, SCHEMAS_DIR).entities.list()


def entity_index() -> dict[str, dict[str, Any]]:
    return {entity["id"]: entity for entity in all_entities() if entity.get("id")}


# berry_label() lives in app/services/berries/geography.py (V2 Phase 2B.2)
# and is imported above; re-exported under this name for every existing
# caller (templates, scripts/build_static.py, tests).


def us_date(value: str | None) -> str:
    """Render a stored ISO YYYY-MM-DD date as US-style M/D/YYYY for display.
    Storage stays ISO everywhere (sorting, form inputs); this is display-only.
    Anything that isn't a plain ISO date (None, "—", partial/free text) is
    passed through unchanged rather than raising."""
    if not value or not isinstance(value, str):
        return value
    try:
        year, month, day = value.split("-")
        return f"{int(month)}/{int(day)}/{year}"
    except (ValueError, TypeError):
        return value


SENTENCE_SPLIT = re.compile(r'(?<=[a-z0-9)])([.!?])\s+(?=[A-Z"\'])')


def as_bullets(text: str | None) -> list[str]:
    """Split a prose field (evidence.summary, fact.statement, etc.) into its
    individual sentences for bullet-point display, without altering a single
    word of the stored text -- display-only, same as us_date.

    Imported evidence/fact text is dense (multiple distinct claims chained
    with commas and "and" into one paragraph) but not padded with literal
    filler; verified against every stored summary/why_it_matters/statement
    that this split point -- lowercase/digit/close-paren, then . ! or ?,
    then whitespace, then an uppercase letter or quote -- never lands mid
    sentence. The obvious naive regex (any ". " before a capital) would
    wrongly break mid-sentence on a person's middle initial ("David M.
    Brazelton"); requiring a non-capital before the punctuation avoids that
    without an abbreviation exception list."""
    if not text:
        return []
    parts = SENTENCE_SPLIT.split(text)
    sentences: list[str] = []
    buf = ""
    for i, part in enumerate(parts):
        if i % 2 == 0:
            buf = part
        else:
            sentences.append(buf + part)
            buf = ""
    if buf:
        sentences.append(buf)
    return [s.strip() for s in sentences if s.strip()]


def is_redundant_summary(summary: str | None, title: str | None) -> bool:
    """True when a "summary" carries no information beyond the headline --
    Google News search results always look like this, since their RSS
    <description> repeats "<headline>&nbsp;&nbsp;<publisher>" (no dash)
    while the matching title is "<headline> - <publisher>" (confirmed
    against the actual capture backlog). Showing that text as if it were a
    summary is worse than showing nothing: it looks like context was
    provided when none was. A direct publisher RSS feed's description is a
    real excerpt and won't match this.

    Compares against the headline portion of the title (before the last
    " - ") rather than the whole title, since the two fields use different
    headline/publisher delimiters -- a straight full-string comparison
    would miss the redundancy entirely."""
    def normalize(text: str | None) -> str:
        return re.sub(r"\s+", " ", (text or "").replace("&nbsp;", " ")).strip().lower()

    headline = title.rsplit(" - ", 1)[0] if title and " - " in title else title
    normalized_headline = normalize(headline)
    normalized_summary = normalize(summary)
    return bool(normalized_headline) and normalized_summary.startswith(normalized_headline)


templates.env.filters["us_date"] = us_date
templates.env.filters["as_bullets"] = as_bullets
templates.env.filters["is_redundant_summary"] = is_redundant_summary


# REGIONS, REGION_LOOKUP, geography_region(), evidence_regions(),
# entity_regions() moved to app/services/berries/geography.py (V2 Phase
# 2B.2) and imported above -- re-exported under these names for every
# existing caller (templates, scripts/build_static.py, tests).


def related_entity_ids(entity_id: str, relationships: list[dict[str, Any]]) -> set[str]:
    related: set[str] = set()
    for rel in relationships:
        if rel.get("subject_id") == entity_id and rel.get("object_id"):
            related.add(rel["object_id"])
        elif rel.get("object_id") == entity_id and rel.get("subject_id"):
            related.add(rel["subject_id"])
    return related


def text_matches(needle: str, haystack: str) -> bool:
    """Case-insensitive search matching shared by the newsfeed, entity list,
    and global search. Tries an exact substring match first (fast path,
    preserves exact behavior for phrase queries like "example blue"). If
    that fails, falls back to per-word matching -- each query word must
    either appear as a substring somewhere in the haystack, or fuzzy-match
    one of its words -- so a near-miss spelling ("hortifruit", "hortifrit")
    still finds "Hortifrut". This is needed because, unlike the static
    build's Pagefind search, the live app has no other typo tolerance.
    Words under 4 characters are excluded from the fuzzy fallback: fuzzy
    matching on short strings produces too many unrelated near-hits to be
    useful ("cost" vs "costa" scores high on similarity but isn't a typo)."""
    needle = needle.strip().lower()
    if not needle:
        return True
    haystack = haystack.lower()
    if needle in haystack:
        return True

    haystack_words = re.findall(r"[a-z0-9]+", haystack)
    query_words = re.findall(r"[a-z0-9]+", needle)
    if not query_words:
        return False
    for word in query_words:
        if word in haystack:
            continue
        if len(word) < 4 or not difflib.get_close_matches(word, haystack_words, n=1, cutoff=0.82):
            return False
    return True


def filter_evidence(
    records: list[dict[str, Any]],
    q: str | None = None,
    berry: str | None = None,
    source: str | None = None,
    priority: str | None = None,
    competitor: str | None = None,
    geography: str | None = None,
    region: str | None = None,
    media_format: str | None = None,
    entities: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    results = records

    if q:
        needle = q.strip().lower()
        if needle:
            def matches_text(record: dict[str, Any]) -> bool:
                haystack = " ".join(
                    [
                        record.get("title", ""),
                        record.get("summary", ""),
                        record.get("why_it_matters", ""),
                        " ".join(record.get("tags", [])),
                    ]
                )
                return text_matches(needle, haystack)

            results = [r for r in results if matches_text(r)]

    if berry:
        results = [r for r in results if berry in (r.get("berry_ids") or [])]

    if source:
        results = [r for r in results if r.get("source_type") == source]

    if media_format:
        results = [r for r in results if r.get("media_format") == media_format]

    if competitor:
        results = [r for r in results if competitor in (r.get("entity_ids") or [])]

    if geography:
        # Same dual convention as evidence_regions(): a geography may only
        # appear in entity_ids, not the dedicated geography_ids array.
        results = [
            r for r in results
            if geography in (r.get("geography_ids") or []) or geography in (r.get("entity_ids") or [])
        ]

    if region:
        region_entities = entities if entities is not None else entity_index()
        results = [r for r in results if region in evidence_regions(r, region_entities)]

    if priority:
        dimension, _, level = priority.partition(":")
        if dimension and level:
            def matches_priority(record: dict[str, Any]) -> bool:
                value = (record.get("priority") or {}).get(dimension) or {}
                return value.get("level") == level

            results = [r for r in results if matches_priority(r)]

    return results


def filter_options(records: list[dict[str, Any]], entities: dict[str, dict[str, Any]]) -> dict[str, Any]:
    berries = sorted({b for r in records for b in (r.get("berry_ids") or [])})
    sources = sorted({r.get("source_type") for r in records if r.get("source_type")})
    media_formats = sorted({r.get("media_format") for r in records if r.get("media_format")})
    competitor_ids = {
        e for r in records for e in (r.get("entity_ids") or []) if entities.get(e, {}).get("entity_type") == "company"
    }
    geography_ids = {g for r in records for g in (r.get("geography_ids") or []) if g in entities}
    geography_ids |= {
        e for r in records for e in (r.get("entity_ids") or []) if entities.get(e, {}).get("entity_type") == "geography"
    }
    competitors = sorted(
        ({"id": i, "name": entities[i]["name"]} for i in competitor_ids), key=lambda c: c["name"]
    )
    geographies = sorted(
        ({"id": i, "name": entities[i]["name"]} for i in geography_ids), key=lambda g: g["name"]
    )
    return {
        "berries": berries,
        "sources": sources,
        "media_formats": media_formats,
        "competitors": competitors,
        "geographies": geographies,
        "regions": REGIONS,
    }


def filter_entities(
    records: list[dict[str, Any]],
    all_entities_idx: dict[str, dict[str, Any]],
    all_evidence_list: list[dict[str, Any]],
    all_relationships_list: list[dict[str, Any]],
    q: str | None = None,
    berry: str | None = None,
    region: str | None = None,
    company: str | None = None,
) -> list[dict[str, Any]]:
    results = records

    if q:
        needle = q.strip().lower()

        def matches_text(entity: dict[str, Any]) -> bool:
            attrs = entity.get("attributes") or {}
            haystack = " ".join(
                [
                    entity.get("name", ""),
                    " ".join(entity.get("aliases", [])),
                    entity.get("description", ""),
                    str(attrs.get("selection_code", "")),
                    str(attrs.get("breeder_code", "")),
                    str(attrs.get("patent_number", "")),
                    str(attrs.get("trade_name", "")),
                    str(attrs.get("commercial_name", "")),
                    str(attrs.get("denomination", "")),
                ]
            )
            return text_matches(needle, haystack)

        results = [e for e in results if matches_text(e)]

    if berry:
        results = [e for e in results if berry in (e.get("berry_ids") or [])]

    if region:
        results = [e for e in results if region in entity_regions(e, all_entities_idx, all_evidence_list)]

    if company:
        related = related_entity_ids(company, all_relationships_list)
        results = [e for e in results if e["id"] in related]

    return results


PRIORITY_DIMENSIONS = ["reading", "testing", "commercial_position", "monitoring"]
PRIORITY_LEVELS = ["high", "medium", "low", "none"]


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return re.sub(r"-{2,}", "-", text).strip("-")


def new_draft_id(title: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    suffix = secrets.token_hex(2)
    slug = slugify(title)[:40] or "draft"
    return f"ev-{stamp}-{suffix}-{slug}"


def safe_filename(name: str) -> str:
    name = Path(name).name
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    return name or "attachment"


def list_drafts() -> list[dict[str, Any]]:
    records = load_json_files(INBOX_DIR / "evidence")
    return sorted(records, key=lambda r: r.get("captured_date", ""), reverse=True)


def list_pending_drafts() -> list[dict[str, Any]]:
    """Active review queue only; list_drafts() remains the complete audit set.

    Static leak checks and duplicate detection must still see rejected drafts,
    even though an explicit decision removes them from the active queue.
    """
    return [record for record in list_drafts() if record.get("status", "draft") != "rejected"]


def get_draft(draft_id: str) -> dict[str, Any] | None:
    path = INBOX_DIR / "evidence" / f"{draft_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def pending_publication_drafts() -> list[dict[str, Any]]:
    drafts = [
        record
        for record in list_pending_drafts()
        if record.get("evidence_role") == "publication_artifact"
    ]
    # Recency first within a tier, but direct berry intelligence must
    # outrank adjacent stories (agtech/trade/labor/weather with only an
    # incidental berry mention) by default -- two stable sorts achieve
    # "tier first, recency second" without a mixed asc/desc sort key.
    # Podcast/video drafts carry no relevance_tier at all (that screen is
    # article-specific) and are treated as tier-neutral, same rank as direct.
    drafts.sort(
        key=lambda record: record.get("published_date") or record.get("captured_date") or "",
        reverse=True,
    )
    drafts.sort(key=lambda record: 1 if record.get("relevance_tier") == "adjacent" else 0)
    return drafts


def adjacent_publication_draft_id(draft_id: str, *, step: int = 1) -> str | None:
    ids = [record["id"] for record in pending_publication_drafts() if record.get("id")]
    if not ids:
        return None
    try:
        index = ids.index(draft_id)
    except ValueError:
        return ids[0]
    next_index = index + step
    if 0 <= next_index < len(ids):
        return ids[next_index]
    return None


def save_draft(record: dict[str, Any]) -> None:
    folder = INBOX_DIR / "evidence"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{record['id']}.json"
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def save_attachment(draft_id: str, upload: UploadFile) -> dict[str, str]:
    folder = INBOX_DIR / "attachments" / draft_id
    folder.mkdir(parents=True, exist_ok=True)
    filename = safe_filename(upload.filename or "attachment")
    path = folder / filename
    with path.open("wb") as handle:
        handle.write(upload.file.read())
    return {
        "filename": filename,
        "content_type": upload.content_type or "",
        "url": f"/intake/{draft_id}/attachments/{filename}",
    }


def split_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def append_unique(items: list[str], value: str) -> list[str]:
    return items if value in items else [*items, value]


def entity_folder(entity_type: str) -> str:
    return ENTITY_FOLDER_OVERRIDES.get(entity_type, f"{entity_type}s")


def all_facts() -> list[dict[str, Any]]:
    return get_repositories(DATA_DIR, SCHEMAS_DIR).facts.list()


def all_relationships() -> list[dict[str, Any]]:
    return get_repositories(DATA_DIR, SCHEMAS_DIR).relationships.list()


def facts_for_evidence(evidence_id: str) -> list[dict[str, Any]]:
    return get_query_services(DATA_DIR, SCHEMAS_DIR).reference.facts_for_evidence(evidence_id)


def relationships_for_evidence(evidence_id: str) -> list[dict[str, Any]]:
    return get_query_services(DATA_DIR, SCHEMAS_DIR).reference.relationships_for_evidence(evidence_id)


def facts_for_entity(entity_id: str) -> list[dict[str, Any]]:
    return get_query_services(DATA_DIR, SCHEMAS_DIR).entity_intelligence.facts_for_entity(entity_id)


def relationships_for_entity(entity_id: str, relationships: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in relationships if entity_id in (r.get("subject_id"), r.get("object_id"))]


def grouped_relationships_for_entity(
    entity_id: str, relationships: list[dict[str, Any]], entities: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """An entity's relationships as directed, evidence-linked edges to the
    *other* entity on each one -- generic and entity-type-agnostic (V2 Phase
    1.5B, BL-027/BL-028). Renders honestly: the predicate itself (owns,
    licenses, develops, sells, ...) is shown as recorded, never collapsed
    into a stronger/weaker implied relationship (e.g. a 'licenses' edge is
    never displayed or treated as if it were 'owns'). 'direction' lets a
    template phrase it naturally ("X owns Y" vs "Y is owned by X") without
    guessing which side is more important."""
    rows = []
    for rel in relationships_for_entity(entity_id, relationships):
        if rel.get("subject_id") == entity_id:
            other_id, direction = rel.get("object_id"), "outgoing"
        else:
            other_id, direction = rel.get("subject_id"), "incoming"
        other = entities.get(other_id)
        if other is None:
            continue
        rows.append(
            {
                "predicate": rel.get("predicate"),
                "direction": direction,
                "other": other,
                "status": rel.get("status"),
                "confidence": rel.get("confidence"),
                "effective_date": rel.get("effective_date"),
                "notes": rel.get("notes"),
                "evidence_ids": rel.get("evidence_ids") or [],
            }
        )
    return rows


def signals_for_entity(entity_id: str) -> list[dict[str, Any]]:
    return get_query_services(DATA_DIR, SCHEMAS_DIR).entity_intelligence.signals_for_entity(entity_id)


def assessments_for_entity(entity_id: str) -> list[dict[str, Any]]:
    return get_query_services(DATA_DIR, SCHEMAS_DIR).entity_intelligence.assessments_for_entity(entity_id)


def recommendations_for_entity(entity_id: str) -> list[dict[str, Any]]:
    return get_query_services(DATA_DIR, SCHEMAS_DIR).entity_intelligence.recommendations_for_entity(entity_id)


def strategic_questions_for_entity(
    entity_id: str,
    linked_evidence: list[dict[str, Any]],
    entity_signals: list[dict[str, Any]],
    entity_assessments: list[dict[str, Any]],
    entity_recommendations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Strategic Questions this entity actually bears on -- the union of SQs
    named on its own linked Evidence and on any Signal/Assessment/
    Recommendation that touches it. Generic and core: the mechanism is
    entity-type-agnostic, it just follows the strategic_question_ids field
    every one of these record types already carries. entity_id is unused
    (kept for call-site compatibility -- it always was)."""
    return get_query_services(DATA_DIR, SCHEMAS_DIR).entity_intelligence.strategic_questions_for_entity(
        linked_evidence, entity_signals, entity_assessments, entity_recommendations
    )


# variety_trait_profile(), _normalize_patent_number(), variety_patent_link()
# moved to app/services/berries/variety.py (V2 Phase 2B.2) and imported
# above -- re-exported under these names for every existing caller.

# SEED_FIXTURE_ENTITY_IDS, SEED_FIXTURE_EVIDENCE_IDS, PRIMARY_SOURCE_TYPES,
# and every landscape_*() helper moved to app/services/berries/landscape.py's
# BerriesLandscapeService (V2 Phase 2B.2). landscape_context() below is now
# a thin route-facing wrapper -- tests and scripts/build_static.py call
# main.landscape_context() exactly as before; only its internals changed.


def landscape_context(
    berry_id: str, region: str = "global", intelligence_state: str = "all"
) -> dict[str, Any]:
    allowed_regions = {"global", "americas", "emea", "australia-nz", "asia"}
    allowed_states = {"all", "observed", "tested"}
    region = region if region in allowed_regions else "global"
    intelligence_state = intelligence_state if intelligence_state in allowed_states else "all"
    return {
        **get_domain_services(DATA_DIR).landscape.landscape_context(berry_id),
        "berry_label": berry_label(berry_id),
        "selected_region": region,
        "selected_intelligence_state": intelligence_state,
    }


# max_priority_level() and entity_activity() moved to app/queries/timeline.py
# (V2 Phase 2B.2) and imported above -- re-exported under these names for
# every existing caller.


def load_strategic_questions() -> list[dict[str, Any]]:
    return get_repositories(DATA_DIR, SCHEMAS_DIR).strategic_questions.list()


def strategic_question_by_id(sq_id: str) -> dict[str, Any] | None:
    for sq in load_strategic_questions():
        if sq.get("id") == sq_id:
            return sq
    return None


def evidence_for_strategic_question(sq_id: str) -> list[dict[str, Any]]:
    return get_query_services(DATA_DIR, SCHEMAS_DIR).reference.evidence_for_strategic_question(sq_id)


def resolve_strategic_question_ids(text: str) -> list[str]:
    """Same matching rule as the Signal create route: each comma-separated
    entry may be an existing strategic question's id or its title."""
    sq_ids: list[str] = []
    strategic_questions = load_strategic_questions()
    for entry in split_list(text):
        needle = entry.strip().lower()
        for sq in strategic_questions:
            if sq.get("id", "").lower() == needle or sq.get("title", "").lower() == needle:
                sq_ids.append(sq["id"])
                break
    return sq_ids


def all_signals() -> list[dict[str, Any]]:
    return get_repositories(DATA_DIR, SCHEMAS_DIR).signals.list()


def signal_by_id(signal_id: str) -> dict[str, Any] | None:
    for signal in all_signals():
        if signal.get("id") == signal_id:
            return signal
    return None


def save_signal(record: dict[str, Any]) -> None:
    get_repositories(DATA_DIR, SCHEMAS_DIR).signals.create(record)


def new_signal_id(title: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    suffix = secrets.token_hex(2)
    slug = slugify(title)[:40] or "signal"
    return f"signal-{stamp}-{suffix}-{slug}"


def all_assessments() -> list[dict[str, Any]]:
    return get_repositories(DATA_DIR, SCHEMAS_DIR).assessments.list()


def assessment_by_id(assessment_id: str) -> dict[str, Any] | None:
    for record in all_assessments():
        if record.get("id") == assessment_id:
            return record
    return None


def save_assessment(record: dict[str, Any]) -> None:
    get_repositories(DATA_DIR, SCHEMAS_DIR).assessments.create(record)


def update_assessment(record: dict[str, Any]) -> None:
    get_repositories(DATA_DIR, SCHEMAS_DIR).assessments.update(record["id"], record)


def new_assessment_id(title: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    suffix = secrets.token_hex(2)
    slug = slugify(title)[:40] or "assessment"
    return f"assessment-{stamp}-{suffix}-{slug}"


def all_recommendations() -> list[dict[str, Any]]:
    return get_repositories(DATA_DIR, SCHEMAS_DIR).recommendations.list()


def recommendation_by_id(recommendation_id: str) -> dict[str, Any] | None:
    for record in all_recommendations():
        if record.get("id") == recommendation_id:
            return record
    return None


def save_recommendation(record: dict[str, Any]) -> None:
    get_repositories(DATA_DIR, SCHEMAS_DIR).recommendations.create(record)


def new_recommendation_id(title: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    suffix = secrets.token_hex(2)
    slug = slugify(title)[:40] or "recommendation"
    return f"recommendation-{stamp}-{suffix}-{slug}"


def queue_items(dimension: str) -> list[dict[str, Any]]:
    items = [r for r in published_evidence() if (r.get("priority") or {}).get(dimension, {}).get("level", "none") != "none"]
    # Two stable sorts compose: newest-first within a level, levels ordered high -> low.
    items = sorted(items, key=lambda r: r.get("published_date") or r.get("captured_date", ""), reverse=True)
    items = sorted(
        items,
        key=lambda r: PRIORITY_RANK.get((r.get("priority") or {}).get(dimension, {}).get("level"), 9),
    )
    return items


def queue_counts() -> dict[str, int]:
    return {dim: len(queue_items(dim)) for dim in PRIORITY_DIMENSIONS}


def unresolved_entities() -> list[dict[str, Any]]:
    return [e for e in all_entities() if e.get("status") == "unverified"]


def sources_file() -> Path:
    return DATA_DIR / "configuration" / "sources.json"


def load_sources() -> list[dict[str, Any]]:
    return get_repositories(DATA_DIR, SCHEMAS_DIR).sources.list()


def save_sources(sources: list[dict[str, Any]]) -> None:
    repository = get_repositories(DATA_DIR, SCHEMAS_DIR).sources
    desired = {source["id"]: source for source in sources}
    existing_ids = {source["id"] for source in repository.list()}
    for source_id in existing_ids - desired.keys():
        repository.delete(source_id)
    for source_id, source in desired.items():
        if source_id in existing_ids:
            repository.update(source_id, source)
        else:
            repository.create(source)


def bump_source_tally(source_id: str | None, field: str) -> None:
    """Record a human Validate/Purge decision against the source that
    captured the item -- the transparent, inspectable feedback signal this
    project uses instead of a black-box relevance model: every count here
    traces back to an actual reviewer decision on an actual item, visible
    on the Sources page, not a learned score nobody can audit."""
    if not source_id:
        return
    sources = load_sources()
    for source in sources:
        if source["id"] == source_id:
            source[field] = source.get(field, 0) + 1
            save_sources(sources)
            return


def blocked_domains_file() -> Path:
    return DATA_DIR / "configuration" / "blocked_domains.json"


def load_blocked_domains() -> list[str]:
    path = blocked_domains_file()
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def save_blocked_domains(domains: list[str]) -> None:
    path = blocked_domains_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sorted(set(domains)), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def domain_of(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


# Never a legitimate block target: it's Google News's own redirect host,
# not a publisher. Records captured before origin_domain existed (or any
# future bug that fails to resolve a real publisher) fall back to this
# domain -- blocking it would silently disable every keyword source at
# once, not just one noisy outlet. block_domain() below is the only place
# that's allowed to add to the blocklist, specifically so this guard can't
# be bypassed by a new call site forgetting to check it.
UNBLOCKABLE_DOMAINS = {"news.google.com"}


def add_blocked_domain(domain: str) -> bool:
    """Add a domain to the blocklist. Returns False (no-op) for a domain in
    UNBLOCKABLE_DOMAINS or empty, True if it was actually added."""
    if not domain or domain in UNBLOCKABLE_DOMAINS:
        return False
    domains = load_blocked_domains()
    domains.append(domain)
    save_blocked_domains(domains)
    return True


def new_source_id(label: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    suffix = secrets.token_hex(2)
    slug = slugify(label)[:40] or "source"
    return f"source-{stamp}-{suffix}-{slug}"


def google_news_rss_url(term: str) -> str:
    return f"https://news.google.com/rss/search?q={quote(term)}&hl=en-US&gl=US&ceid=US:en"


def next_check_due(source: dict[str, Any]) -> str | None:
    """When a source is next due for review, derived from update_cadence +
    last_checked_at rather than stored -- so it's never stale relative to
    whatever "today" actually is. None means "never due" (event-driven
    cadence, or no cadence set), not "overdue"."""
    cadence = source.get("update_cadence")
    days = SOURCE_CADENCE_DAYS.get(cadence)
    if days is None:
        return None
    last_checked = source.get("last_checked_at")
    if not last_checked:
        return date.today().isoformat()
    try:
        last_date = datetime.fromisoformat(last_checked).date()
    except ValueError:
        return date.today().isoformat()
    return (last_date + timedelta(days=days)).isoformat()


def source_is_due(source: dict[str, Any]) -> bool:
    due = next_check_due(source)
    return bool(due and due <= date.today().isoformat())


def source_has_coverage_gap(source: dict[str, Any]) -> bool:
    return not source.get("berry_ids") or not source.get("region_coverage")


def filter_sources(
    sources: list[dict[str, Any]],
    entity_type: str | None = None,
    berry: str | None = None,
    region: str | None = None,
    priority: str | None = None,
    view: str | None = None,
) -> list[dict[str, Any]]:
    results = sources
    if entity_type:
        results = [s for s in results if entity_type in (s.get("entity_types") or [])]
    if berry:
        results = [s for s in results if berry in (s.get("berry_ids") or [])]
    if region:
        results = [s for s in results if region in (s.get("region_coverage") or [])]
    if priority:
        results = [s for s in results if s.get("monitoring_priority") == priority]
    if view == "gaps":
        results = [s for s in results if source_has_coverage_gap(s)]
    elif view == "due":
        results = [s for s in results if source_is_due(s)]
    return results


SOURCE_PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}


def group_sources(sources: list[dict[str, Any]], group_by: str) -> list[tuple[str, list[dict[str, Any]]]]:
    """Group already-filtered sources for display, sorted High-priority-first
    within each group (per the spec's grouped views). A source with several
    values for the grouping field (e.g. covers three berries) legitimately
    appears in each of those groups -- that's the multi-select tagging
    working as intended, not a duplicate bug."""
    labels = {"berry": BERRIES, "region": SOURCE_REGIONS, "entity_type": SOURCE_ENTITY_TYPES}.get(
        group_by, SOURCE_ENTITY_TYPES
    )
    key_field = {"berry": "berry_ids", "region": "region_coverage", "entity_type": "entity_types"}.get(
        group_by, "entity_types"
    )
    sorted_sources = sorted(sources, key=lambda s: SOURCE_PRIORITY_RANK.get(s.get("monitoring_priority"), 3))

    groups: dict[str, list[dict[str, Any]]] = {}
    for source in sorted_sources:
        keys = source.get(key_field) or []
        if not keys:
            groups.setdefault("Untagged", []).append(source)
        for key in keys:
            groups.setdefault(labels.get(key, key), []).append(source)
    return sorted(groups.items(), key=lambda item: (item[0] == "Untagged", item[0]))


def source_feed_url(source: dict[str, Any]) -> str:
    if source.get("type") == "keyword":
        return google_news_rss_url(source.get("value", ""))
    return source.get("value", "")


def existing_evidence_source_urls() -> set[str]:
    return {r["source_url"] for r in all_evidence() if r.get("source_url")}


_HTML_TAG_RE = re.compile(r"<[^>]+>")


def strip_html(text: str) -> str:
    return _HTML_TAG_RE.sub("", text or "").strip()


def entry_published_date(entry: Any) -> str | None:
    parsed = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if not parsed:
        return None
    try:
        return date(parsed.tm_year, parsed.tm_mon, parsed.tm_mday).isoformat()
    except (TypeError, ValueError):
        return None


def build_auto_evidence(entry: Any, source: dict[str, Any]) -> dict[str, Any]:
    title = strip_html(getattr(entry, "title", "") or "(untitled)")
    summary = strip_html(getattr(entry, "summary", "") or getattr(entry, "description", ""))
    evidence_id = new_draft_id(title)
    rationale = f"Auto-captured from source '{source.get('label')}'; not yet reviewed."

    # A keyword source's link is a Google News redirect (news.google.com),
    # never the publisher's own domain -- every keyword-captured item would
    # otherwise report the same fake domain, which both mislabels who
    # actually published it and makes the domain blocklist useless (blocking
    # "news.google.com" would block every keyword source at once). Google
    # News RSS entries carry the real outlet in entry.source.{href,title};
    # a plain RSS feed entry has no .source at all because it IS already the
    # publisher's own feed, so the feed's own link/label are already correct.
    origin = getattr(entry, "source", None)
    publisher_name = (origin.get("title") if origin else None) or source.get("label", "")
    publisher_url = (origin.get("href") if origin else None) or getattr(entry, "link", "") or ""

    return {
        "id": evidence_id,
        "record_type": "evidence",
        "status": "published",
        "source_type": "rss_feed" if source.get("type") == "rss" else "news_search",
        "title": title,
        "source_name": publisher_name,
        "source_id": source.get("id"),
        "source_url": getattr(entry, "link", "") or "",
        "origin_domain": domain_of(publisher_url),
        "published_date": entry_published_date(entry),
        "captured_date": date.today().isoformat(),
        "summary": summary[:2000],
        "why_it_matters": "",
        "submitted_by": f"source-monitor:{source.get('label', source.get('id', ''))}",
        "berry_ids": list(source.get("berry_ids") or []),
        "geography_ids": [],
        "entity_ids": [],
        "fact_ids": [],
        "relationship_ids": [],
        "strategic_question_ids": [],
        "tags": [t for t in [source.get("label")] if t],
        "auto_captured": True,
        "validated": False,
        "priority": {
            dim: {"level": "none", "rationale": rationale}
            for dim in PRIORITY_DIMENSIONS
        },
    }


def name_matchers_for_type(entity_type: str, entities: dict[str, dict[str, Any]] | None = None) -> list[tuple[str, "re.Pattern[str]"]]:
    """(entity_id, compiled word-boundary regex) for every name/alias of the
    given entity type, at least 4 characters. The length floor exists
    because this project's actual geography/company names are all >=4
    chars (shortest is "Peru") -- a shorter floor would risk matching
    common words as false positives (an unfiltered "US" would match the
    pronoun "us" in ordinary prose)."""
    records = entities if entities is not None else entity_index()
    return matchers_from_entities(records, entity_type)


def auto_tag_geography_and_entities(
    record: dict[str, Any],
    geo_matchers: list[tuple[str, "re.Pattern[str]"]] | None = None,
    company_matchers: list[tuple[str, "re.Pattern[str]"]] | None = None,
) -> dict[str, Any]:
    """Best-effort, deterministic name/alias matching against known
    geography and company entities, applied only to still-unreviewed
    auto-captured evidence -- never touches a record a human has already
    validated. This is pattern matching, not verification: it exists so a
    newsfeed card isn't blank on region/company where the real answer is
    knowable from the text, not to assert the match is correct. Records it
    tags get auto_tagged: true so every display surface can show that
    distinction rather than presenting an inferred tag as a reviewed one.

    Pass precomputed matchers when tagging many records in a loop (e.g. a
    backfill pass) -- name_matchers_for_type() rebuilds its list from every
    entity on each call, wasteful to redo per record."""
    if not record.get("auto_captured") or record.get("validated"):
        return record
    if geo_matchers is None:
        geo_matchers = name_matchers_for_type("geography")
    if company_matchers is None:
        company_matchers = name_matchers_for_type("company")

    haystack = f"{record.get('title', '')} {record.get('summary', '')}"
    return apply_known_name_matches(
        record,
        haystack,
        geo_matchers=geo_matchers,
        company_matchers=company_matchers,
    )


def fetch_source_entries(source: dict[str, Any]) -> list[Any]:
    url = source_feed_url(source)
    if not url:
        return []
    response = httpx.get(
        url,
        timeout=SOURCE_FETCH_TIMEOUT_SECONDS,
        headers={"User-Agent": SOURCE_USER_AGENT},
        follow_redirects=True,
    )
    response.raise_for_status()
    parsed = feedparser.parse(response.content)
    return list(parsed.entries or [])


def check_source(source: dict[str, Any], seen_urls: set[str], blocked_domains: set[str] | None = None) -> int:
    """Fetch one source, write genuinely new evidence (capped per check), return count written.

    A broad first-time source (especially a keyword search) can match dozens
    of historical items at once; writing all of them in one pass would flood
    the feed. Anything past the cap is simply left unwritten and picked up
    on a later check, since it's still "new" until it's actually written.

    Reference sources (annual reports, government statistics portals,
    association reports -- most of the seeded source registry) have no feed
    to fetch at all; they're tracked for review cadence, not polled.
    """
    if source.get("type") == "reference":
        return 0
    entries = fetch_source_entries(source)
    blocked = load_blocked_domains() if blocked_domains is None else blocked_domains
    geo_matchers = name_matchers_for_type("geography")
    company_matchers = name_matchers_for_type("company")
    written = 0
    for entry in entries:
        if written >= SOURCE_MAX_NEW_ITEMS_PER_CHECK:
            break
        link = getattr(entry, "link", "") or ""
        if not link or link in seen_urls:
            continue
        record = build_auto_evidence(entry, source)
        if blocked and record["origin_domain"] in blocked:
            continue
        record = auto_tag_geography_and_entities(record, geo_matchers, company_matchers)
        save_evidence(record)
        seen_urls.add(link)
        written += 1
    return written


def check_all_sources() -> dict[str, Any]:
    sources = load_sources()
    seen_urls = existing_evidence_source_urls()
    blocked_domains = set(load_blocked_domains())
    total_written = 0
    checked = 0
    for source in sources:
        if not source.get("enabled", True) or source.get("type") == "reference":
            # Reference sources have nothing to fetch; last_checked_at for
            # them means "a human reviewed it", set only by the manual
            # mark-checked action, never by the automated poll loop.
            continue
        checked += 1
        source["last_checked_at"] = datetime.now().isoformat(timespec="seconds")
        try:
            written = check_source(source, seen_urls, blocked_domains)
            source["last_status"] = f"ok: {written} new item(s)" if written else "ok: no new items"
            total_written += written
        except Exception as exc:                       # noqa: BLE001
            source["last_status"] = f"error: {exc}"
    save_sources(sources)
    return {"sources_checked": checked, "items_written": total_written}


async def source_polling_loop() -> None:
    while True:
        try:
            await asyncio.to_thread(check_all_sources)
        except Exception:                               # noqa: BLE001
            pass
        await asyncio.sleep(SOURCE_POLL_INTERVAL_SECONDS)


def normalize_title(text: str) -> str:
    text = text.lower().strip()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def find_possible_duplicates(title: str, exclude_id: str | None = None) -> list[dict[str, Any]]:
    needle = normalize_title(title)
    if not needle:
        return []
    matches = []
    candidates = all_evidence() + list_drafts()
    seen_ids: set[str] = set()
    for record in candidates:
        record_id = record.get("id")
        if not record_id or record_id == exclude_id or record_id in seen_ids:
            continue
        haystack = normalize_title(record.get("title", ""))
        if not haystack:
            continue
        if haystack == needle or needle in haystack or haystack in needle:
            matches.append(record)
            seen_ids.add(record_id)
    return matches


def unique_entity_id(entity_type: str, name: str, existing_ids: set[str]) -> str:
    base = f"{entity_type}-{slugify(name)}" or f"{entity_type}-entity"
    candidate = base
    suffix = 2
    while candidate in existing_ids:
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def save_entity(record: dict[str, Any]) -> None:
    repository = get_repositories(DATA_DIR, SCHEMAS_DIR).entities
    if repository.get(record["id"]) is None:
        repository.create(record)
    else:
        repository.update(record["id"], record)


def save_fact(record: dict[str, Any]) -> None:
    get_repositories(DATA_DIR, SCHEMAS_DIR).facts.create(record)


def save_relationship(record: dict[str, Any]) -> None:
    get_repositories(DATA_DIR, SCHEMAS_DIR).relationships.create(record)


def save_evidence(record: dict[str, Any]) -> None:
    get_repositories(DATA_DIR, SCHEMAS_DIR).evidence.create(record)


def delete_draft(draft_id: str) -> None:
    path = INBOX_DIR / "evidence" / f"{draft_id}.json"
    if path.exists():
        path.unlink()


def move_draft_attachments(draft_id: str, evidence_id: str, attachments: list[dict[str, str]]) -> list[dict[str, str]]:
    source_dir = INBOX_DIR / "attachments" / draft_id
    if not source_dir.exists() or not attachments:
        return []
    target_dir = DATA_DIR / "attachments" / evidence_id
    target_dir.mkdir(parents=True, exist_ok=True)
    moved: list[dict[str, str]] = []
    for attachment in attachments:
        filename = attachment["filename"]
        source_path = source_dir / filename
        if not source_path.exists():
            continue
        shutil.move(str(source_path), str(target_dir / filename))
        moved.append(
            {
                "filename": filename,
                "content_type": attachment.get("content_type", ""),
                "url": f"/evidence/{evidence_id}/attachments/{filename}",
            }
        )
    if source_dir.exists() and not any(source_dir.iterdir()):
        source_dir.rmdir()
    return moved


def restore_draft_attachments(draft_id: str, evidence_id: str, attachments: list[dict[str, str]]) -> None:
    """Reverse move_draft_attachments() -- used only when a structured-data
    publish transaction that already moved attachment files out of inbox/
    subsequently fails and rolls back (ReviewPublishService), so a retry's
    own move_draft_attachments() call finds the files back where it
    expects them instead of silently publishing with no attachments."""
    if not attachments:
        return
    source_dir = DATA_DIR / "attachments" / evidence_id
    if not source_dir.exists():
        return
    target_dir = INBOX_DIR / "attachments" / draft_id
    target_dir.mkdir(parents=True, exist_ok=True)
    for attachment in attachments:
        filename = attachment["filename"]
        source_path = source_dir / filename
        if source_path.exists():
            shutil.move(str(source_path), str(target_dir / filename))
    if source_dir.exists() and not any(source_dir.iterdir()):
        source_dir.rmdir()


_SCHEMA_CACHE: dict[str, Draft202012Validator] = {}


def get_validator(schema_name: str) -> Draft202012Validator:
    if schema_name not in _SCHEMA_CACHE:
        schema = json.loads((SCHEMAS_DIR / schema_name).read_text(encoding="utf-8"))
        _SCHEMA_CACHE[schema_name] = Draft202012Validator(schema, format_checker=FormatChecker())
    return _SCHEMA_CACHE[schema_name]


@app.get("/", response_class=HTMLResponse)
def home(
    request: Request,
    q: str | None = None,
    berry: str | None = None,
    source: str | None = None,
    priority: str | None = None,
    competitor: str | None = None,
    geography: str | None = None,
    region: str | None = None,
    media_format: str | None = None,
) -> HTMLResponse:
    evidence = published_evidence()
    entities = entity_index()
    options = filter_options(evidence, entities)
    filtered = filter_evidence(
        evidence,
        q=q, berry=berry, source=source, priority=priority,
        competitor=competitor, geography=geography, region=region,
        media_format=media_format, entities=entities,
    )
    return templates.TemplateResponse(
        request=request,
        name="feed.html",
        context={
            "evidence": filtered,
            "total_count": len(evidence),
            "berry_label": berry_label,
            "options": options,
            "entities": entities,
            "filters": {
                "q": q or "",
                "berry": berry or "",
                "source": source or "",
                "priority": priority or "",
                "competitor": competitor or "",
                "geography": geography or "",
                "region": region or "",
                "media_format": media_format or "",
            },
            "priority_dimensions": PRIORITY_DIMENSIONS,
            "priority_levels": PRIORITY_LEVELS,
            "authoring_mode": AUTHORING_MODE,
        },
    )


@app.get("/evidence/{record_id}", response_class=HTMLResponse)
def evidence_detail(request: Request, record_id: str) -> HTMLResponse:
    for record in all_evidence():
        if record.get("id") == record_id:
            entities = entity_index()
            linked_entities = [entities[e] for e in record.get("entity_ids", []) if e in entities]
            facts = facts_for_evidence(record_id)
            relationships = []
            for rel in relationships_for_evidence(record_id):
                relationships.append(
                    {
                        **rel,
                        "subject": entities.get(rel.get("subject_id"), {}).get("name", rel.get("subject_id")),
                        "object": entities.get(rel.get("object_id"), {}).get("name", rel.get("object_id")),
                    }
                )
            return templates.TemplateResponse(
                request=request,
                name="evidence.html",
                context={
                    "record": record,
                    "linked_entities": linked_entities,
                    "facts": facts,
                    "relationships": relationships,
                    "berry_label": berry_label,
                    "authoring_mode": AUTHORING_MODE,
                },
            )
    raise HTTPException(status_code=404, detail="Evidence record not found")


@app.get("/evidence/{record_id}/attachments/{filename}")
def evidence_attachment(record_id: str, filename: str) -> FileResponse:
    directory = (DATA_DIR / "attachments" / record_id).resolve()
    target = (directory / filename).resolve()
    if not target.is_file() or not target.is_relative_to(directory):
        raise HTTPException(status_code=404, detail="Attachment not found")
    return FileResponse(target)


_ALLOWED_EVIDENCE_ACTION_REDIRECTS = {"/", "/review"}


@app.post("/evidence/{record_id}/validate")
def evidence_validate(record_id: str, redirect_to: str = Form("")) -> RedirectResponse:
    if not AUTHORING_MODE:
        raise HTTPException(status_code=403, detail="Validating evidence is only available in authoring mode")
    repository = get_repositories(DATA_DIR, SCHEMAS_DIR).evidence
    record = repository.get(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Evidence record not found")
    record["validated"] = True
    repository.update(record_id, record)
    if record.get("auto_captured"):
        bump_source_tally(record.get("source_id"), "validated_count")
    # Only ever redirects to a fixed, known-safe in-app path -- never the raw
    # form value -- so this can't be turned into an open redirect.
    destination = redirect_to if redirect_to in _ALLOWED_EVIDENCE_ACTION_REDIRECTS else f"/evidence/{record_id}"
    return RedirectResponse(url=destination, status_code=303)


@app.post("/evidence/{record_id}/purge")
def evidence_purge(record_id: str, block_domain: bool = Form(False), redirect_to: str = Form("")) -> RedirectResponse:
    if not AUTHORING_MODE:
        raise HTTPException(status_code=403, detail="Purging evidence is only available in authoring mode")
    repository = get_repositories(DATA_DIR, SCHEMAS_DIR).evidence
    record = repository.get(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Evidence record not found")
    if not record.get("auto_captured"):
        raise HTTPException(status_code=400, detail="Purge is only available for auto-captured evidence")
    if record.get("source_id"):
        bump_source_tally(record["source_id"], "purged_count")
    if block_domain:
        # origin_domain is the real publisher (e.g. freshplaza.com); older
        # records captured before that field existed fall back to
        # source_url, which is only correct for direct-RSS sources -- a
        # keyword-captured record's source_url is a Google News redirect,
        # not a real domain. add_blocked_domain() refuses to add that
        # redirect host itself, which would otherwise silently disable
        # every keyword source instead of just one noisy outlet.
        domain = record.get("origin_domain") or domain_of(record.get("source_url", ""))
        add_blocked_domain(domain)
    repository.delete(record_id)
    destination = redirect_to if redirect_to in _ALLOWED_EVIDENCE_ACTION_REDIRECTS else "/"
    return RedirectResponse(url=destination, status_code=303)


@app.get("/entities/{entity_type}", response_class=HTMLResponse)
def entity_list(
    request: Request,
    entity_type: str,
    q: str | None = None,
    berry: str | None = None,
    region: str | None = None,
    company: str | None = None,
    view: str | None = None,
    has_rights: str | None = None,
    has_observation: str | None = None,
    has_product_evidence: str | None = None,
    has_signal: str | None = None,
    market: str | None = None,
    ip_and_observation: str | None = None,
) -> HTMLResponse:
    all_of_type = sorted(
        (e for e in all_entities() if e.get("entity_type") == entity_type),
        key=lambda e: e.get("name", ""),
    )
    if not all_of_type:
        raise HTTPException(status_code=404, detail=f"No entities found for type '{entity_type}'")

    ui = read_ui_context(request, BERRIES, inbox_dir=INBOX_DIR)
    if entity_type == "variety" and "berry" not in request.query_params and ui["berry"] != "global":
        berry = ui["berry"]

    entities_idx = entity_index()
    evidence = published_evidence()
    relationships = all_relationships()
    filtered = filter_entities(
        all_of_type, entities_idx, evidence, relationships, q=q, berry=berry, region=region, company=company
    )
    companies = sorted(
        ({"id": e["id"], "name": e["name"]} for e in all_entities() if e.get("entity_type") == "company"),
        key=lambda c: c["name"],
    )
    context: dict[str, Any] = {
        "entities": filtered,
        "total_count": len(all_of_type),
        "entity_type": entity_type,
        "berries": BERRIES,
        "regions": REGIONS,
        "companies": companies,
        "filters": {
            "q": q or "",
            "berry": berry or "",
            "region": region or "",
            "company": company or "",
            "has_rights": has_rights or "",
            "has_observation": has_observation or "",
            "has_product_evidence": has_product_evidence or "",
            "has_signal": has_signal or "",
            "market": market or "",
            "ip_and_observation": ip_and_observation or "",
        },
        "authoring_mode": AUTHORING_MODE,
        "ui_context": ui,
        "variety_view": "index",
        "variety_cards": [],
        "berry_inventory": [],
        "unnamed_observation_count": 0,
        "observation_total_count": 0,
        "observation_workspace": {},
        "competition": {},
        "geographies": [],
    }
    if entity_type == "variety":
        variety_view = view if view in VARIETY_VIEWS else "index"
        drafts = list_pending_drafts()
        geographies = sorted(
            ({"id": e["id"], "name": e["name"]} for e in entities_idx.values() if e.get("entity_type") == "geography"),
            key=lambda row: row["name"],
        )
        context.update(
            {
                "variety_view": variety_view,
                "berry_inventory": berry_inventory(all_of_type, BERRIES),
                "geographies": geographies,
            }
        )
        if variety_view == "index":
            index_model = present_variety_index(
                varieties=filtered,
                entities=list(entities_idx.values()),
                relationships=relationships,
                published_evidence=evidence,
                berry_labels=BERRIES,
                inbox_drafts=drafts,
                signals=all_signals(),
                candidates=load_candidates(INBOX_DIR) if INBOX_DIR else [],
                facts=all_facts(),
                filters={
                    "has_rights": has_rights or "",
                    "has_observation": has_observation or "",
                    "has_product_evidence": has_product_evidence or "",
                    "has_signal": has_signal or "",
                },
            )
            context["variety_cards"] = index_model["cards"]
            context["unnamed_observation_count"] = index_model["unnamed_observation_count"]
            context["observation_total_count"] = index_model["observation_total_count"]
        elif variety_view == "observations":
            context["observation_workspace"] = present_observation_workspace(
                entities=list(entities_idx.values()),
                published_evidence=evidence,
                inbox_drafts=drafts,
                berry_labels=BERRIES,
                berry_id=berry,
            )
        elif variety_view == "compete":
            context["competition"] = present_competition(
                berry_id=berry,
                country_geo_id=market,
                entities=list(entities_idx.values()),
                relationships=relationships,
                published_evidence=evidence,
                inbox_drafts=drafts,
                berry_labels=BERRIES,
                ip_and_observation=ip_and_observation in {"1", "true", "yes", "on"},
            )
    response = templates.TemplateResponse(
        request=request,
        name="entity_list.html",
        context=context,
    )
    apply_ui_cookies(response, berry=ui["berry"], feed_view=ui["feed_view"])
    return response


def recent_intelligence_for_entity(
    entity_id: str,
    *,
    linked_evidence: list[dict[str, Any]],
    include_pending: bool,
    limit: int = 8,
) -> list[dict[str, Any]]:
    """Recency-first feed of what's actually known about this entity,
    trusted Evidence first-class and (live app only, never on the public
    static build -- see entity_synthesis_context()'s include_pending) any
    pending-review discoveries that already name it, each item clearly
    marked TRUSTED or PENDING REVIEW so an unreviewed article can never be
    mistaken for trusted intelligence. Sorted by real publication date,
    falling back to capture date only when no publication date exists --
    the same date-preference convention published_evidence() and
    pending_publication_drafts() already use, so recency ordering is
    consistent everywhere in the app, not just here."""
    items: list[dict[str, Any]] = [
        {
            "kind": "trusted",
            "record": record,
            "date": record.get("published_date") or record.get("captured_date"),
            "date_is_published": bool(record.get("published_date")),
        }
        for record in linked_evidence
    ]
    pending_items: list[dict[str, Any]] = []
    if include_pending:
        entities = entity_index()
        source_index = {str(source.get("id")): source for source in load_sources() if source.get("id")}
        entity = entities.get(entity_id) or {"id": entity_id}
        pending_items = [
            {
                "kind": "pending",
                "record": record,
                "date": record.get("published_date") or record.get("captured_date"),
                "date_is_published": bool(record.get("published_date")),
            }
            for record in pending_publication_drafts()
            if draft_matches_entity(record, entity, entities, sources=source_index)
        ]
        pending_items.sort(key=lambda item: item["date"] or "", reverse=True)
        for row in pending_items:
            record = row["record"]
            attribution = attribute_draft(record, entities, sources=source_index)
            primary = attribution.get("primary") or {}
            if primary.get("id") or primary.get("name"):
                record["primary_subject"] = primary
    items.sort(key=lambda item: item["date"] or "", reverse=True)
    if include_pending and pending_items:
        pinned = pending_items[:6]
        seen = {str((row.get("record") or {}).get("id")) for row in pinned}
        rest = [row for row in items if str((row.get("record") or {}).get("id")) not in seen]
        return compress_recent_intelligence((pinned + rest)[: limit + 6])[:limit]
    return items[:limit]


def company_berry_portfolio(entity: dict[str, Any]) -> list[dict[str, str]]:
    ids = [str(value) for value in (entity.get("berry_ids") or []) if value]
    ordered = [berry_id for berry_id in COMPANY_BERRY_ORDER if berry_id in ids]
    ordered.extend(berry_id for berry_id in ids if berry_id not in ordered)
    return [
        {
            "id": berry_id,
            "label": berry_label(berry_id).upper(),
            "slug": berry_id.removeprefix("berry-"),
        }
        for berry_id in ordered
    ]


def _matches_company_berry(item: dict[str, Any], berry: str) -> bool:
    if berry == "global":
        return True
    if matches_berry_context(item, berry):
        return True
    record = item.get("record")
    if isinstance(record, dict) and matches_berry_context(record, berry):
        return True
    thread = item.get("thread") if isinstance(item.get("thread"), dict) else {}
    for member in thread.get("members") or []:
        if isinstance(member, dict) and matches_berry_context(member, berry):
            return True
    return False


def _filter_recent_by_berry(items: list[dict[str, Any]], berry: str) -> list[dict[str, Any]]:
    if berry == "global":
        return list(items)
    return [item for item in items if _matches_company_berry(item, berry)]


def _filter_open_signals_by_berry(
    open_signals: dict[str, list[dict[str, Any]]], berry: str
) -> dict[str, list[dict[str, Any]]]:
    if berry == "global":
        return open_signals
    return {
        key: [row for row in (open_signals.get(key) or []) if matches_berry_context(row, berry)]
        for key in ("emerging", "confirmed", "deferred")
    }


def _filter_relationships_by_berry(
    rows: list[dict[str, Any]], berry: str
) -> list[dict[str, Any]]:
    if berry == "global":
        return list(rows)
    out: list[dict[str, Any]] = []
    for row in rows:
        other = row.get("other") or {}
        if matches_berry_context(other, berry) or not (other.get("berry_ids") or []):
            out.append(row)
    return out


def _company_is_watched(linked_evidence: list[dict[str, Any]]) -> bool:
    for record in linked_evidence:
        level = ((record.get("priority") or {}).get("monitoring") or {}).get("level")
        if level and str(level) != "none":
            return True
    return False


def _company_feed_cards(
    items: list[dict[str, Any]],
    entities: dict[str, dict[str, Any]],
    *,
    include_candidates: bool,
) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for item in items:
        record = item.get("record") or {}
        if not record.get("id"):
            continue
        card = present_feed_item(record, entities=entities, berry_labels=BERRIES)
        if item.get("is_thread"):
            card["is_thread"] = True
            card["story_thread"] = item.get("thread")
            card["title"] = item.get("developing_label") or card["title"]
        cards.append(card)
    candidates = load_candidates(INBOX_DIR) if include_candidates and INBOX_DIR else []
    annotate_feed_semantics(cards, signals=all_signals(), candidates=candidates)
    return cards


def company_profile_context(
    entity: dict[str, Any],
    entities: dict[str, dict[str, Any]],
    *,
    recent_intelligence: list[dict[str, Any]],
    grouped_relationships: list[dict[str, Any]],
    open_signals: dict[str, list[dict[str, Any]]],
    linked_evidence: list[dict[str, Any]],
    berry: str = "global",
    include_candidates: bool = True,
) -> dict[str, Any]:
    recent = _filter_recent_by_berry(recent_intelligence, berry)
    cutoff = (date.today() - timedelta(days=COMPANY_WHAT_CHANGED_DAYS)).isoformat()
    what_changed = [item for item in recent if str(item.get("date") or "") >= cutoff]
    varieties = _filter_relationships_by_berry(
        [
            row
            for row in grouped_relationships
            if row.get("predicate") == "develops" and (row.get("other") or {}).get("entity_type") == "variety"
        ],
        berry,
    )
    geos = _filter_relationships_by_berry(
        [
            row
            for row in grouped_relationships
            if row.get("predicate") == "operates_in" and (row.get("other") or {}).get("entity_type") == "geography"
        ],
        berry,
    )
    variety_ids = {str((row.get("other") or {}).get("id") or "") for row in varieties}
    geo_ids = {str((row.get("other") or {}).get("id") or "") for row in geos}
    network = [
        row
        for row in grouped_relationships
        if str((row.get("other") or {}).get("id") or "") not in variety_ids
        and str((row.get("other") or {}).get("id") or "") not in geo_ids
    ]
    return {
        "company_portfolio": company_berry_portfolio(entity),
        "company_what_changed": _company_feed_cards(
            what_changed, entities, include_candidates=include_candidates
        ),
        "company_recent_cards": _company_feed_cards(
            recent, entities, include_candidates=include_candidates
        ),
        "open_signals": _filter_open_signals_by_berry(open_signals, berry),
        "company_varieties": varieties,
        "company_geographies": geos,
        "company_network": network,
        "company_watched": _company_is_watched(linked_evidence),
        "company_berry_filter": berry,
    }


def entity_synthesis_context(
    entity: dict[str, Any],
    entities: dict[str, dict[str, Any]],
    *,
    include_pending: bool = True,
    linked_evidence: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """The generic, entity-type-agnostic synthesis fields added in Phase
    1.5B (BL-027/BL-028): intelligence objects touching this entity, its
    relationships to other entities as directed/evidenced edges, and the
    Strategic Questions it bears on. Shared by the live entity_detail()
    route and scripts/build_static.py so both stay in sync by construction.
    `include_pending` gates the "Recent Intelligence" pending-review feed
    (added for cross-object freshness/recall): the live app defaults to
    True, but scripts/build_static.py must always pass False -- pending
    drafts live in gitignored inbox/ and must never appear in the public
    GitHub Pages build alongside trusted intelligence. `linked_evidence`
    lets static generation deliberately supply its structured-only set and
    lets the live route reuse its already-computed conservative recall set."""
    entity_id = entity["id"]
    if linked_evidence is None:
        linked_evidence = linked_evidence_for_entity(entity, published_evidence(), entities=entities)
    entity_signals = signals_for_entity(entity_id)
    entity_assessments = attach_assessment_scope(assessments_for_entity(entity_id), BERRIES)
    entity_recommendations = recommendations_for_entity(entity_id)
    context: dict[str, Any] = {
        "entity_signals": entity_signals,
        "entity_assessments": entity_assessments,
        "entity_recommendations": entity_recommendations,
        "entity_strategic_questions": strategic_questions_for_entity(
            entity_id, linked_evidence, entity_signals, entity_assessments, entity_recommendations
        ),
        "grouped_relationships": grouped_relationships_for_entity(entity_id, all_relationships(), entities),
        "recent_intelligence": recent_intelligence_for_entity(
            entity_id, linked_evidence=linked_evidence, include_pending=include_pending
        ),
        "open_signals": {"emerging": [], "confirmed": [], "deferred": []},
    }
    if entity.get("entity_type") == "variety":
        all_patents = [e for e in entities.values() if e.get("entity_type") == "patent"]
        breeding_program_id = (entity.get("attributes") or {}).get("breeding_program_id")
        context["variety_trait_profile"] = variety_trait_profile(entity, entities)
        context["variety_patent_link"] = variety_patent_link(entity, all_patents)
        context["variety_breeding_program"] = entities.get(breeding_program_id) if breeding_program_id else None
    if entity.get("entity_type") == "company":
        context.update(
            company_profile_context(
                entity,
                entities,
                recent_intelligence=context["recent_intelligence"],
                grouped_relationships=context["grouped_relationships"],
                open_signals=context["open_signals"],
                linked_evidence=linked_evidence,
                berry="global",
                include_candidates=include_pending,
            )
        )
    return context


@app.get("/learn", response_class=HTMLResponse)
def learn_home(request: Request, q: str = "") -> HTMLResponse:
    """Learner Mode V1 home -- deterministic browse/glossary over the
    starter concept set (data/learn/concepts/*.json). Search is a plain
    substring match over name/alias/pillar/summary, not semantic search,
    per Learner Mode governance (docs/v2/feature-requests/LEARNER-MODE.md,
    INTELLIGENCE-EXPANSION-BUILD-GUIDE.md section 12a). Educational
    knowledge, not Competitive Intelligence -- no Evidence/Fact/Signal
    objects are created or implied here."""
    search_results = learn_search_concepts(q) if q.strip() else None
    ui = read_ui_context(request, BERRIES, inbox_dir=INBOX_DIR)
    response = templates.TemplateResponse(
        request=request,
        name="learn_home.html",
        context={
            "pillars": learn_concepts_by_pillar(),
            "concept_count": len(learn_all_concepts()),
            "search_query": q,
            "search_results": search_results,
            "static_build": False,
            "ui_context": ui,
            "berries": BERRIES,
        },
    )
    apply_ui_cookies(response, berry=ui["berry"], feed_view=ui["feed_view"])
    return response


@app.get("/learn/{slug}", response_class=HTMLResponse)
def learn_concept_detail(request: Request, slug: str) -> HTMLResponse:
    """Learner Mode V1 concept page. related_intelligence_for_concept()
    reuses only already-loaded, trusted Facts/Evidence -- the same recall
    mechanism Variety Intelligence V2 uses -- and never touches inbox/
    drafts or Signal Candidates."""
    concept = learn_concept_by_slug(slug)
    if not concept:
        raise HTTPException(status_code=404, detail="Learner Mode concept not found")
    entities = entity_index()
    related_intel = related_intelligence_for_concept(
        concept,
        facts=all_facts(),
        entities=entities,
        evidence_by_id={r["id"]: r for r in all_evidence() if r.get("id")},
    )
    ui = read_ui_context(request, BERRIES, inbox_dir=INBOX_DIR)
    response = templates.TemplateResponse(
        request=request,
        name="learn_concept.html",
        context={
            "concept": concept,
            "related": learn_related_concepts(concept),
            "related_intelligence": related_intel,
            "static_build": False,
            "ui_context": ui,
            "berries": BERRIES,
        },
    )
    apply_ui_cookies(response, berry=ui["berry"], feed_view=ui["feed_view"])
    return response


@app.get("/entities/variety/compare", response_class=HTMLResponse)
def variety_compare_page(request: Request, ids: str = "") -> HTMLResponse:
    """Variety Compare V1 -- side-by-side trusted intelligence for up to
    COMPARE_MAX_VARIETIES varieties. Registered before the generic
    /entities/{entity_type}/{entity_id} route so "compare" is never
    matched as an entity_id. Canonical-ID-only query string (?ids=a,b,c)
    is the entire selection state -- reloading or sharing the URL
    reproduces the same comparison, no private runtime state involved."""
    requested_ids = [part.strip() for part in ids.split(",") if part.strip()]
    entities = entity_index()
    result = present_variety_compare(
        requested_ids,
        entities=entities,
        relationships=all_relationships(),
        published_evidence=published_evidence(),
        facts=all_facts(),
        evidence_by_id={r["id"]: r for r in all_evidence() if r.get("id")},
        signals=all_signals(),
        assessments=all_assessments(),
        berry_labels=BERRIES,
    )
    ui = read_ui_context(request, BERRIES, inbox_dir=INBOX_DIR)
    response = templates.TemplateResponse(
        request=request,
        name="variety_compare.html",
        context={
            "compare": result,
            "ids_param": ids,
            "berries": BERRIES,
            "compare_max": COMPARE_MAX_VARIETIES,
            "authoring_mode": AUTHORING_MODE,
            "ui_context": ui,
        },
    )
    apply_ui_cookies(response, berry=ui["berry"], feed_view=ui["feed_view"])
    return response


@app.get("/entities/{entity_type}/{entity_id}", response_class=HTMLResponse)
def entity_detail(request: Request, entity_type: str, entity_id: str) -> HTMLResponse:
    for entity in all_entities():
        if entity.get("id") == entity_id and entity.get("entity_type") == entity_type:
            entities = entity_index()
            linked_evidence = linked_evidence_for_entity(entity, published_evidence(), entities=entities)
            independent_sources = {r.get("source_name") for r in linked_evidence if r.get("source_name")}
            last_updated = linked_evidence[0].get("published_date") or linked_evidence[0].get("captured_date") if linked_evidence else None
            regions = sorted(entity_regions(entity, entities, linked_evidence))
            entity_facts = facts_for_entity(entity_id)
            entity_relationships = relationships_for_entity(entity_id, all_relationships())
            evidence_idx = {r["id"]: r for r in all_evidence() if r.get("id")}
            activity = entity_activity(linked_evidence, entity_facts, entity_relationships, entities, evidence_idx)
            presented_candidates = present_candidates(
                INBOX_DIR,
                evidence_by_id=_evidence_index(),
                entities=entities,
            )
            synthesis = entity_synthesis_context(entity, entities, linked_evidence=linked_evidence)
            open_signals = open_signals_for_entity(entity_id, presented_candidates)
            ui = read_ui_context(request, BERRIES, inbox_dir=INBOX_DIR)
            if entity.get("entity_type") in ("company", "variety"):
                synthesis["intelligence_timeline"] = entity_intelligence_timeline(
                    entity_id=entity_id,
                    entities=entities,
                    linked_evidence=linked_evidence,
                    entity_facts=entity_facts,
                    entity_relationships=entity_relationships,
                    entity_signals=synthesis["entity_signals"],
                    entity_assessments=synthesis["entity_assessments"],
                    evidence_idx=evidence_idx,
                )
            if entity.get("entity_type") == "company":
                synthesis.update(
                    company_profile_context(
                        entity,
                        entities,
                        recent_intelligence=synthesis["recent_intelligence"],
                        grouped_relationships=synthesis["grouped_relationships"],
                        open_signals=open_signals,
                        linked_evidence=linked_evidence,
                        berry=ui["berry"],
                    )
                )
            elif entity.get("entity_type") == "variety":
                synthesis["open_signals"] = open_signals
                story_threads = [
                    item["thread"]
                    for item in synthesis.get("recent_intelligence") or []
                    if item.get("is_thread") and item.get("thread")
                ]
                synthesis.update(
                    present_variety_detail(
                        entity,
                        entities=entities,
                        relationships=all_relationships(),
                        published_evidence=published_evidence(),
                        grouped_relationships=synthesis["grouped_relationships"],
                        recent_intelligence=synthesis["recent_intelligence"],
                        berry_labels=BERRIES,
                        inbox_drafts=list_pending_drafts(),
                        story_threads=story_threads,
                        signals=all_signals(),
                        facts=entity_facts,
                        evidence_by_id=evidence_idx,
                    )
                )
            else:
                synthesis["open_signals"] = open_signals
            response = templates.TemplateResponse(
                request=request,
                name="entity.html",
                context={
                    "entity": entity,
                    "linked_evidence": linked_evidence,
                    "linked_facts": entity_facts,
                    "activity": activity,
                    "evidence_count": len(linked_evidence),
                    "source_count": len(independent_sources),
                    "last_updated": last_updated,
                    "regions": regions,
                    "berry_label": berry_label,
                    "authoring_mode": AUTHORING_MODE,
                    **synthesis,
                },
            )
            apply_ui_cookies(response, berry=ui["berry"], feed_view=ui["feed_view"])
            return response
    raise HTTPException(status_code=404, detail="Entity record not found")


def _overlay_attribution_companies(values: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    if str(values.get("companies") or "").strip():
        return values
    names: list[str] = []
    primary = item.get("primary_subject") or {}
    if primary.get("entity_type") == "company" and primary.get("name"):
        names.append(str(primary["name"]))
    for company in item.get("title_companies") or []:
        name = str(company.get("name") or "")
        if name and name not in names:
            names.append(name)
    if names:
        values["companies"] = ", ".join(names)
    return values


def _attach_pending_decision_actions(items: list[dict[str, Any]], reviewer: str) -> None:
    for item in items:
        if item.get("is_thread"):
            _attach_pending_decision_actions(item.get("members") or [], reviewer)
            if item.get("primary"):
                _attach_pending_decision_actions([item["primary"]], reviewer)
            continue
        if item.get("status") == "published" or not item.get("id"):
            continue
        values = _default_review_values(item)
        values["reviewer"] = reviewer
        item["review_values"] = _overlay_attribution_companies(values, item)
        item["show_pending_actions"] = True


def _filter_items_for_berry(items: list[dict[str, Any]] | None, berry: str) -> list[dict[str, Any]]:
    return [item for item in (items or []) if matches_berry_context(item, berry)]


def _filter_brief_for_berry(brief: dict[str, Any], berry: str) -> dict[str, Any]:
    if berry == "global":
        return brief
    brief["new_developments"] = _filter_items_for_berry(brief.get("new_developments"), berry)
    brief["important"] = _filter_items_for_berry(brief.get("important"), berry)
    brief["emerging_signals"] = _filter_items_for_berry(brief.get("emerging_signals"), berry)
    brief["top_developments"] = _filter_items_for_berry(brief.get("top_developments"), berry)
    pending = dict(brief.get("pending_triage") or {})
    buckets = []
    for group in pending.get("buckets") or []:
        entries = _filter_items_for_berry(group.get("entries"), berry)
        buckets.append({**group, "entries": entries, "count": len(entries)})
    pending["buckets"] = buckets
    pending_counts = dict(pending.get("counts") or {})
    for group in buckets:
        pending_counts[str(group.get("key") or "")] = int(group.get("count") or 0)
    pending["counts"] = pending_counts
    brief["pending_triage"] = pending
    counts = dict(brief.get("counts") or {})
    counts["new_developments"] = len(brief.get("new_developments") or [])
    counts["emerging_signals"] = len(brief.get("emerging_signals") or [])
    counts["review_now"] = int(pending_counts.get("review_now") or 0)
    brief["counts"] = counts
    return brief


@app.get("/brief", response_class=HTMLResponse)
def morning_brief_page(request: Request) -> HTMLResponse:
    brief = _assemble_morning_brief(mark_seen=True, include_coverage=True, mode="full")
    reviewer = session_username(request) or review_username() or ""
    ui = read_ui_context(request, BERRIES, inbox_dir=INBOX_DIR)
    brief = _filter_brief_for_berry(brief, ui["berry"])
    for group in (brief.get("pending_triage") or {}).get("buckets") or []:
        _attach_pending_decision_actions(group.get("entries") or [], reviewer)
    return templates.TemplateResponse(
        request=request,
        name="morning_brief.html",
        context={
            "brief": brief,
            "authoring_mode": AUTHORING_MODE,
            "static_build": False,
            "reviewer": reviewer,
            "return_to": "/brief#pending-triage",
        },
    )


@app.get("/pending", response_class=HTMLResponse)
def pending_review_page(request: Request) -> HTMLResponse:
    """Decision workspace for pending publication drafts. Not a Feed clone."""

    ids_param = (request.query_params.get("ids") or "").strip()
    selected_ids = [part.strip() for part in ids_param.split(",") if part.strip()]
    berry = (request.query_params.get("berry") or "").strip()
    berry_id = berry if berry.startswith("berry-") else (f"berry-{berry}" if berry else "")
    source = (request.query_params.get("source") or "").strip()
    entities = entity_index()
    source_rows = load_sources()
    source_index = {str(row.get("id") or ""): row for row in source_rows if row.get("id")}
    pending_snapshot = get_pending_review_query_service(INBOX_DIR).list_pending(
        entities=entities,
        sources=source_index,
        ids=set(selected_ids),
        berry_id=berry_id,
        source=source,
    )
    brief = _assemble_morning_brief(
        mark_seen=False,
        include_coverage=False,
        mode="pending",
        include_signal_candidates=False,
        drafts=pending_snapshot.records,
    )
    brief["pending_query"] = {
        "inventory_count": pending_snapshot.inventory_count,
        "selected_count": len(pending_snapshot.records),
        "parsed_records": pending_snapshot.parsed_records,
        "reused_records": pending_snapshot.reused_records,
        "body_records_omitted": pending_snapshot.body_records_omitted,
    }
    reviewer = session_username(request) or review_username() or ""
    ui = read_ui_context(request, BERRIES, inbox_dir=INBOX_DIR)
    brief = _filter_brief_for_berry(brief, ui["berry"])
    for group in (brief.get("pending_triage") or {}).get("buckets") or []:
        _attach_pending_decision_actions(group.get("entries") or [], reviewer)
        for item in group.get("entries") or []:
            item["pending"] = True
    return templates.TemplateResponse(
        request=request,
        name="pending_review.html",
        context={
            "brief": brief,
            "authoring_mode": AUTHORING_MODE,
            "static_build": False,
            "reviewer": reviewer,
            "return_to": "/pending",
            "ui_context": ui,
        },
    )


@app.get("/work-queue", response_class=HTMLResponse)
def work_queue(request: Request, filter: str = "all") -> HTMLResponse:
    evidence = published_evidence()
    high_priority = [
        r for r in evidence if any(v.get("level") == "high" for v in (r.get("priority") or {}).values())
    ]
    readiness = load_publication_transcript_readiness(INBOX_DIR)
    feed = build_intelligence_feed(
        drafts=list_drafts(),
        published=evidence,
        entities=entity_index(),
        berry_labels=BERRIES,
        transcript_readiness=readiness,
        filter_key=filter,
        limit=48,
    )
    reviewer = session_username(request) or review_username() or ""
    entities = entity_index()
    source_index = {str(source.get("id")): source for source in load_sources() if source.get("id")}
    for item in feed["entries"]:
        if not item.get("pending"):
            continue
        attribution = attribute_draft(item["record"], entities, sources=source_index)
        item["primary_subject"] = attribution.get("primary")
        item["title_companies"] = [
            hit for hit in (attribution.get("suggested") or [])
            if hit.get("entity_type") == "company" and hit.get("location") in {"title", "source"}
        ]
        values = _default_review_values(item["record"])
        values["reviewer"] = reviewer
        item["review_values"] = _overlay_attribution_companies(values, item)
    ui = read_ui_context(request, BERRIES, inbox_dir=INBOX_DIR)
    if request.query_params.get("view") or request.query_params.get("berry"):
        persist_ui_prefs(INBOX_DIR, berry=ui["berry"], feed_view=ui["feed_view"])
    feed["entries"] = [item for item in feed["entries"] if matches_berry_context(item, ui["berry"])]
    annotate_feed_semantics(
        feed["entries"],
        signals=all_signals(),
        candidates=load_candidates(INBOX_DIR) if INBOX_DIR else [],
    )
    return_filter = "" if filter in {"", "all"} else f"?filter={filter}"
    response = templates.TemplateResponse(
        request=request,
        name="work_queue.html",
        context={
            "recent_evidence": evidence[:5],
            "drafts": list_pending_drafts(),
            "review_cards": [],
            "feed": feed,
            "feed_view": ui["feed_view"],
            "reviewer": reviewer,
            "return_filter": return_filter,
            "promoted_id": request.query_params.get("promoted") or "",
            "promoted_title": request.query_params.get("promoted_title") or "",
            "promoted_date": request.query_params.get("promoted_date") or "",
            "saved": request.query_params.get("saved") == "1",
            "scanner": build_scanner_summary(
                inbox_dir=INBOX_DIR,
                drafts=list_drafts(),
                published=evidence,
                transcript_readiness=readiness,
            ),
            "unresolved_entities": unresolved_entities(),
            "high_priority": high_priority[:5],
            "recent_signals": all_signals()[:5],
            "queue_summary": queue_counts(),
            "authoring_mode": AUTHORING_MODE,
            "static_build": False,
        },
    )
    apply_ui_cookies(response, berry=ui["berry"], feed_view=ui["feed_view"])
    return response


def _load_intelligence_record(item_id: str) -> dict[str, Any] | None:
    draft = get_draft(item_id)
    if draft is not None and draft.get("status") != "rejected":
        return draft
    record = get_repositories(DATA_DIR, SCHEMAS_DIR).evidence.get(item_id)
    if record is not None and record.get("status") == "published":
        return record
    return None


def _default_reader_reviewer(request: Request, values: dict[str, Any]) -> str:
    return (
        str(values.get("reviewer") or "").strip()
        or session_username(request)
        or review_username()
        or ""
    )


def _source_index() -> dict[str, dict[str, Any]]:
    return {str(source.get("id")): source for source in load_sources() if source.get("id")}


def _related_signal_rows(item_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    related_signals = [
        {
            "id": signal.get("id"),
            "title": signal.get("title") or signal.get("label") or signal.get("id"),
            "href": f"/signals/{signal.get('id')}",
            "status": signal.get("status") or "",
        }
        for signal in all_signals()
        if item_id and item_id in (signal.get("evidence_ids") or [])
    ]
    related_candidates = [
        {
            "id": candidate.get("id"),
            "title": candidate.get("label") or candidate.get("pattern_type") or candidate.get("id"),
            "href": f"/signals/candidates/{candidate.get('id')}",
            "status": candidate.get("status") or "",
        }
        for candidate in (load_candidates(INBOX_DIR) if INBOX_DIR else [])
        if item_id and item_id in (candidate.get("supporting_evidence_ids") or [])
    ]
    return related_signals, related_candidates


def _intelligence_page_context(
    request: Request,
    record: dict[str, Any],
    *,
    error: str | None = None,
    values: dict[str, Any] | None = None,
    overlay: bool = False,
) -> dict[str, Any]:
    entities = entity_index()
    source_index = _source_index()
    if overlay:
        readiness = unknown_transcript_readiness()
        published: list[dict[str, Any]] = []
        atomic_drafts: list[dict[str, Any]] = []
    else:
        readiness_map = load_publication_transcript_readiness(INBOX_DIR)
        readiness = deepcopy(readiness_map.get(record.get("id")) or unknown_transcript_readiness())
        published = published_evidence()
        atomic_drafts = list_drafts()
    reader = build_reader(
        record,
        entities=entities,
        berry_labels=BERRIES,
        inbox_dir=INBOX_DIR,
        published=published,
        atomic_drafts=atomic_drafts,
        transcript_readiness=readiness,
    )
    if values is None:
        values = {} if record.get("status") == "published" else _default_review_values(record)
    reviewer = _default_reader_reviewer(request, values)
    values = {**values, "reviewer": reviewer}
    attribution = attribute_draft(record, entities, sources=source_index)
    if record.get("status") != "published":
        values = _overlay_attribution_companies(values, {"primary_subject": attribution.get("primary"), "title_companies": [
            hit for hit in (attribution.get("suggested") or []) if hit.get("entity_type") == "company" and hit.get("location") == "title"
        ]})
    story_thread = None
    if not overlay and record.get("id"):
        universe = [row for row in list_pending_drafts() if row.get("id")]
        if record.get("status") == "published":
            universe.append(record)
        elif not any(str(row.get("id")) == str(record.get("id")) for row in universe):
            universe.append(record)
        for row in universe:
            if row.get("primary_subject"):
                continue
            row_attr = attribute_draft(row, entities, sources=source_index)
            if row_attr.get("primary"):
                row["primary_subject"] = row_attr["primary"]
        found = thread_for_item(str(record.get("id")), universe)
        if found and int(found.get("source_count") or 0) > 1:
            story_thread = found
    item_id = str(record.get("id") or "")
    related_signals, related_candidates = _related_signal_rows(item_id)
    quality = evidence_quality_for_record(record)
    return {
        **reader,
        "record": record,
        "values": values,
        "reviewer": reviewer,
        "authoring_mode": AUTHORING_MODE,
        "promoted": request.query_params.get("promoted") == "1",
        "saved": request.query_params.get("saved") == "1",
        "error": error,
        "attribution": attribution,
        "story_thread": story_thread,
        "related_signals": related_signals,
        "related_candidates": related_candidates,
        "evidence_quality": quality,
        "limited_evidence": bool(quality.get("limited")),
        "overlay": overlay,
    }


@app.get("/intelligence/{item_id}", response_class=HTMLResponse)
def intelligence_reader(request: Request, item_id: str) -> HTMLResponse:
    record = _load_intelligence_record(item_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Intelligence item not found")
    return templates.TemplateResponse(
        request=request,
        name="intelligence_reader.html",
        context=_intelligence_page_context(request, record),
    )


@app.get("/api/intelligence/{item_id}/reader", response_class=HTMLResponse)
def intelligence_reader_fragment(request: Request, item_id: str) -> HTMLResponse:
    record = _load_intelligence_record(item_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Intelligence item not found")
    return templates.TemplateResponse(
        request=request,
        name="_reader_panel.html",
        context={
            **_intelligence_page_context(request, record, overlay=True),
            "authoring_mode": AUTHORING_MODE,
            "static_build": False,
        },
    )


@app.get("/threads/{item_id}", response_class=HTMLResponse)
def story_thread_reader(request: Request, item_id: str) -> HTMLResponse:
    seed = _load_intelligence_record(item_id)
    if seed is None:
        raise HTTPException(status_code=404, detail="Story thread not found")
    source_index = {str(source.get("id")): source for source in load_sources() if source.get("id")}
    entities = entity_index()
    universe = [row for row in list_pending_drafts() if row.get("id")]
    if seed.get("status") == "published" or not any(str(row.get("id")) == item_id for row in universe):
        universe.append(seed)
    for row in universe:
        attribution = attribute_draft(row, entities, sources=source_index)
        if attribution.get("primary"):
            row["primary_subject"] = attribution["primary"]
        row["href"] = f"/intelligence/{row.get('id')}"
        row["date"] = row.get("published_date") or row.get("captured_date") or ""
        row["trust"] = "trusted" if row.get("status") == "published" else "pending"
        row["trust_label"] = "Trusted" if row.get("status") == "published" else "Pending"
    published_rows = []
    for rec in published_evidence():
        rec = dict(rec)
        for entity_id in rec.get("entity_ids") or []:
            entity = entities.get(entity_id) or {}
            if entity.get("entity_type") in {"company", "variety"}:
                rec["primary_subject"] = {
                    "id": entity_id,
                    "name": entity.get("name") or entity_id,
                    "entity_type": entity.get("entity_type"),
                }
                break
        rec["href"] = f"/intelligence/{rec.get('id')}"
        rec["date"] = rec.get("published_date") or rec.get("captured_date") or ""
        rec["trust"] = "trusted"
        rec["trust_label"] = "Trusted"
        published_rows.append(rec)
    universe = expand_with_related(universe, published_rows)
    for row in universe:
        if not row.get("href"):
            row["href"] = f"/intelligence/{row.get('id')}"
    thread = thread_for_item(item_id, universe)
    if thread is None:
        raise HTTPException(status_code=404, detail="Story thread not found")
    if int(thread.get("source_count") or 0) <= 1:
        return RedirectResponse(url=f"/intelligence/{item_id}", status_code=303)
    reviewer = session_username(request) or review_username() or ""
    state = load_analyst_queue_state(INBOX_DIR)
    for member in thread.get("members") or []:
        if is_pending_dismissed(str(member.get("id") or ""), state):
            member["dismissed_redundant"] = True
            member["trust_label"] = "Dismissed (kept)"
    _attach_pending_decision_actions(
        [member for member in (thread.get("members") or []) if not member.get("dismissed_redundant")],
        reviewer,
    )
    presented_candidates = present_candidates(
        INBOX_DIR,
        evidence_by_id=_evidence_index(),
        entities=entities,
    )
    member_ids = {str(member.get("id") or "") for member in (thread.get("members") or [])}
    return templates.TemplateResponse(
        request=request,
        name="story_thread.html",
        context={
            "thread": thread,
            "authoring_mode": AUTHORING_MODE,
            "static_build": False,
            "reviewer": reviewer,
            "supporting_signals": candidates_for_thread(member_ids, presented_candidates),
        },
    )


PRIORITY_QUEUE_LABELS = {
    "reading": "Reading Queue",
    "testing": "Claim testing",
    "commercial_position": "Commercial positions",
    "monitoring": "Watches",
}


@app.get("/queues/{dimension}", response_class=HTMLResponse)
def priority_queue(
    request: Request,
    dimension: str,
    region: str | None = None,
    show_completed: str | None = None,
    berry: str | None = None,
    company: str | None = None,
    variety: str | None = None,
    geography: str | None = None,
    status: str | None = None,
) -> HTMLResponse:
    if dimension not in PRIORITY_DIMENSIONS:
        raise HTTPException(status_code=404, detail="Unknown priority dimension")
    entities = entity_index()
    all_items = queue_items(dimension)
    if region:
        all_items = [r for r in all_items if region in evidence_regions(r, entities)]
    completed = show_completed in {"1", "true", "on", "yes"}
    page = build_dimension_page(
        dimension=dimension,
        records=all_items,
        inbox_dir=INBOX_DIR,
        entities=entities,
        berry_labels=BERRIES,
        signals=all_signals(),
        show_completed=completed,
    )
    proposals = pending_position_proposals(all_recommendations(), INBOX_DIR) if dimension == "commercial_position" else []
    alerts = (
        [signal for signal in all_signals() if is_open_signal_alert(signal, load_analyst_queue_state(INBOX_DIR))]
        if dimension == "monitoring"
        else []
    )
    reading_buckets: list[dict[str, Any]] = []
    reading_bucket_counts: dict[str, int] = {}
    monitor = {
        "watch_items": page["items"],
        "monitor_alerts": [],
        "alert_action_count": 0,
        "last_seen_at": None,
    }
    if dimension == "reading" and not completed:
        brief = _assemble_morning_brief(mark_seen=False, include_coverage=False, mode="nav")
        reading_buckets = [group for group in brief.get("reading_buckets") or [] if group.get("key") != "needs_review"]
        if region:
            allowed = {record["id"] for record in all_items if record.get("id")}
            for group in reading_buckets:
                group["entries"] = [item for item in group.get("entries") or [] if item.get("id") in allowed]
                group["count"] = len(group["entries"])
        reading_bucket_counts = {group["key"]: group["count"] for group in reading_buckets}
        candidates = load_candidates(INBOX_DIR) if INBOX_DIR else []
        for group in reading_buckets:
            annotate_feed_semantics(
                group.get("entries") or [],
                signals=all_signals(),
                candidates=candidates,
            )
            for item in group.get("entries") or []:
                item["show_reading_actions"] = bool(item.get("is_active"))
                item["reading_open"] = bool(item.get("needs_consume"))
    elif dimension == "monitoring":
        candidates = load_candidates(INBOX_DIR) if INBOX_DIR else []
        monitor = monitor_page_model(
            watch_items=page["items"],
            entities=entities,
            berry_labels=BERRIES,
            published=published_evidence(),
            drafts=list_pending_drafts(),
            signals=all_signals(),
            candidates=candidates,
            inbox_dir=INBOX_DIR,
            health_rows=failing_source_health_rows(load_sources(), inbox_dir=INBOX_DIR),
            include_drafts=True,
        )
    testing_workspace: dict[str, Any] = {}
    if dimension == "testing":
        repos = get_repositories(DATA_DIR, SCHEMAS_DIR)
        evidence_by_id, facts_by_id = related_indexes(
            all_items,
            get_evidence=repos.evidence.get,
            get_fact=repos.facts.get,
        )
        testing_workspace = testing_page_model(
            records=all_items,
            inbox_dir=INBOX_DIR,
            entities=entities,
            berry_labels=BERRIES,
            evidence_by_id=evidence_by_id,
            facts_by_id=facts_by_id,
            show_completed=completed,
            static_build=False,
            filters={
                "berry": berry or "",
                "company": company or "",
                "variety": variety or "",
                "geography": geography or "",
                "state": status or "",
            },
        )
        page = {**page, **testing_workspace}
    position_workspace: dict[str, Any] = {}
    if dimension == "commercial_position":
        repos = get_repositories(DATA_DIR, SCHEMAS_DIR)
        position_workspace = commercial_page_model(
            records=all_items,
            inbox_dir=INBOX_DIR,
            entities=entities,
            berry_labels=BERRIES,
            facts=repos.facts.list(),
            signals=all_signals(),
            assessments=repos.assessments.list(),
            static_build=False,
            filters={
                "berry": berry or "",
                "company": company or "",
                "variety": variety or "",
                "geography": geography or "",
            },
        )
        page = {**page, **position_workspace}
    return templates.TemplateResponse(
        request=request,
        name="queue.html",
        context={
            **page,
            "berry_label": berry_label,
            "regions": REGIONS,
            "filters": {"region": region or ""},
            "authoring_mode": AUTHORING_MODE,
            "static_build": False,
            "reviewer": session_username(request) or review_username() or "",
            "position_proposals": proposals,
            "signal_alerts": alerts,
            "reading_buckets": reading_buckets,
            "reading_bucket_counts": reading_bucket_counts,
            "return_to": f"/queues/{dimension}",
            **monitor,
            **testing_workspace,
            **position_workspace,
        },
    )


@app.post("/queues/reading/bulk-read")
async def reading_bulk_read(request: Request) -> RedirectResponse:
    if not AUTHORING_MODE:
        raise HTTPException(status_code=403, detail="Queue actions are only available in authoring mode")
    form = await request.form()
    reviewer = str(form.get("reviewer") or "").strip() or session_username(request) or review_username() or ""
    region = str(form.get("region") or "")
    return_to = safe_next_path(str(form.get("return_to") or ""))
    subjects = {record["id"]: record for record in queue_items("reading") if record.get("id")}
    allowed = set(subjects)
    ids = [value for value in form.getlist("item_id") if isinstance(value, str) and value in allowed]
    bulk_mark_read(INBOX_DIR, ids, reviewer=reviewer, subjects=subjects, sources=_source_index())
    if return_to and return_to.startswith("/brief"):
        return RedirectResponse(url="/brief", status_code=303)
    suffix = f"?region={region}" if region else ""
    return RedirectResponse(url=f"/queues/reading{suffix}", status_code=303)


@app.post("/queues/pending/bulk-dismiss")
async def pending_bulk_dismiss(request: Request) -> RedirectResponse:
    if not AUTHORING_MODE:
        raise HTTPException(status_code=403, detail="Queue actions are only available in authoring mode")
    form = await request.form()
    reviewer = str(form.get("reviewer") or "").strip() or session_username(request) or review_username() or ""
    return_to = safe_next_path(str(form.get("return_to") or "")) or "/brief#pending-triage"
    subjects = {record["id"]: record for record in list_pending_drafts() if record.get("id")}
    allowed = set(subjects)
    ids = [value for value in form.getlist("item_id") if isinstance(value, str) and value in allowed]
    bulk_dismiss_pending(INBOX_DIR, ids, reviewer=reviewer, subjects=subjects, sources=_source_index())
    return RedirectResponse(
        url=return_to if return_to.startswith(("/brief", "/pending")) else "/pending",
        status_code=303,
    )


@app.post("/queues/pending/{item_id}")
def pending_item_action(
    request: Request,
    item_id: str,
    action: str = Form(...),
    reviewer: str = Form(""),
    return_to: str = Form(""),
) -> RedirectResponse:
    if not AUTHORING_MODE:
        raise HTTPException(status_code=403, detail="Queue actions are only available in authoring mode")
    allowed = {record["id"]: record for record in list_pending_drafts() if record.get("id")}
    if item_id not in allowed:
        raise HTTPException(status_code=404, detail="Pending draft not found")
    try:
        apply_queue_action(
            INBOX_DIR,
            dimension="pending",
            item_id=item_id,
            action=action,
            reviewer=reviewer.strip() or session_username(request) or review_username() or "",
            subject=allowed[item_id],
            source=_source_index().get(str(allowed[item_id].get("source_id") or "")),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    next_url = safe_next_path(return_to) or "/pending"
    return RedirectResponse(url=next_url, status_code=303)


@app.get("/queues/testing/{item_id}", response_class=HTMLResponse)
def testing_claim_review(request: Request, item_id: str) -> HTMLResponse:
    entities = entity_index()
    records = queue_items("testing")
    record = next((row for row in records if row.get("id") == item_id), None)
    if record is None:
        raise HTTPException(status_code=404, detail="Claim is not in the testing queue")
    state = load_analyst_queue_state(INBOX_DIR)
    repos = get_repositories(DATA_DIR, SCHEMAS_DIR)
    evidence_by_id, facts_by_id = related_indexes(
        [record],
        get_evidence=repos.evidence.get,
        get_fact=repos.facts.get,
    )
    item = enrich_testing_item(
        record,
        state=state,
        entities=entities,
        berry_labels=BERRIES,
        evidence_by_id=evidence_by_id,
        facts_by_id=facts_by_id,
        static_build=False,
    )
    return templates.TemplateResponse(
        request=request,
        name="testing_detail.html",
        context={
            "item": item,
            "authoring_mode": AUTHORING_MODE,
            "static_build": False,
            "reviewer": session_username(request) or review_username() or "",
        },
    )


@app.post("/queues/{dimension}/{item_id}")
def queue_item_action(
    request: Request,
    dimension: str,
    item_id: str,
    action: str = Form(...),
    reviewer: str = Form(""),
    show_completed: str = Form(""),
    region: str = Form(""),
    return_to: str = Form(""),
) -> RedirectResponse:
    if dimension not in {"reading", "testing", "monitoring"}:
        raise HTTPException(status_code=404, detail="Unknown queue workflow")
    if not AUTHORING_MODE:
        raise HTTPException(status_code=403, detail="Queue actions are only available in authoring mode")
    allowed = {record["id"]: record for record in queue_items(dimension) if record.get("id")}
    if item_id not in allowed:
        raise HTTPException(status_code=404, detail="Item is not in this queue")
    try:
        apply_queue_action(
            INBOX_DIR,
            dimension=dimension,
            item_id=item_id,
            action=action,
            reviewer=reviewer.strip() or session_username(request) or review_username() or "",
            subject=allowed[item_id],
            source=_source_index().get(str(allowed[item_id].get("source_id") or "")),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if dimension == "reading" and action == "promote":
        return RedirectResponse(url=f"/intelligence/{item_id}", status_code=303)
    destination = safe_next_path(return_to) if return_to else ""
    if destination and destination not in {"/brief"} and not destination.startswith("/queues/"):
        destination = ""
    if destination:
        return RedirectResponse(url=destination, status_code=303)
    params = []
    if region:
        params.append(f"region={region}")
    if show_completed:
        params.append("show_completed=1")
    suffix = ("?" + "&".join(params)) if params else ""
    return RedirectResponse(url=f"/queues/{dimension}{suffix}", status_code=303)


@app.post("/recommendations/{recommendation_id}/proposal-decision")
def recommendation_proposal_decision(
    request: Request,
    recommendation_id: str,
    action: str = Form(...),
    reviewer: str = Form(""),
) -> RedirectResponse:
    if not AUTHORING_MODE:
        raise HTTPException(status_code=403, detail="Proposal decisions are only available in authoring mode")
    recommendation = recommendation_by_id(recommendation_id)
    if recommendation is None:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    try:
        apply_queue_action(
            INBOX_DIR,
            dimension="proposals",
            item_id=recommendation_id,
            action=action,
            reviewer=reviewer.strip() or session_username(request) or review_username() or "",
            subject=recommendation,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(url="/queues/commercial_position", status_code=303)


@app.post("/signals/{signal_id}/alert-decision")
def signal_alert_decision(
    request: Request,
    signal_id: str,
    action: str = Form(...),
    reviewer: str = Form(""),
) -> RedirectResponse:
    if not AUTHORING_MODE:
        raise HTTPException(status_code=403, detail="Signal-alert decisions are only available in authoring mode")
    signal = signal_by_id(signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found")
    try:
        apply_queue_action(
            INBOX_DIR,
            dimension="signals",
            item_id=signal_id,
            action=action,
            reviewer=reviewer.strip() or session_username(request) or review_username() or "",
            subject=signal,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(url="/queues/monitoring#alerts", status_code=303)


@app.get("/strategic-questions", response_class=HTMLResponse)
def strategic_question_list(request: Request) -> HTMLResponse:
    questions = load_strategic_questions()
    counts = {sq["id"]: len(evidence_for_strategic_question(sq["id"])) for sq in questions if sq.get("id")}
    return templates.TemplateResponse(
        request=request,
        name="strategic_question_list.html",
        context={"questions": questions, "counts": counts, "authoring_mode": AUTHORING_MODE},
    )


@app.get("/strategic-questions/{sq_id}", response_class=HTMLResponse)
def strategic_question_detail(request: Request, sq_id: str) -> HTMLResponse:
    sq = strategic_question_by_id(sq_id)
    if sq is None:
        raise HTTPException(status_code=404, detail="Strategic question not found")
    return templates.TemplateResponse(
        request=request,
        name="strategic_question_detail.html",
        context={
            "sq": sq,
            "linked_evidence": evidence_for_strategic_question(sq_id),
            "berry_label": berry_label,
            "authoring_mode": AUTHORING_MODE,
        },
    )


@app.get("/landscapes", response_class=HTMLResponse)
def landscape_all(request: Request) -> HTMLResponse:
    """Landscape V2's ALL BERRIES executive overview -- registered as its
    own literal path, not a "/landscapes/{berry_slug}" catch-all, so it
    never risks being swallowed by or swallowing the existing per-berry
    route."""
    context = _cached_landscape_context_all()
    return templates.TemplateResponse(
        request=request,
        name="landscape_all.html",
        context={**context, "authoring_mode": AUTHORING_MODE},
    )


@app.get("/landscapes/berries/{berry_slug}", response_class=HTMLResponse)
def landscape_berry(
    request: Request, berry_slug: str, region: str = "global", intelligence_state: str = "all"
) -> HTMLResponse:
    berry_id = f"berry-{berry_slug}"
    if berry_id not in BERRIES:
        raise HTTPException(status_code=404, detail="Unknown berry")
    return templates.TemplateResponse(
        request=request,
        name="landscape.html",
        context={
            **_cached_landscape_context(berry_id, region, intelligence_state),
            "authoring_mode": AUTHORING_MODE,
        },
    )


@app.get("/signals", response_class=HTMLResponse)
def signal_list(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="signal_list.html",
        context={"signals": all_signals(), "authoring_mode": AUTHORING_MODE},
    )


@app.get("/signals/review", response_class=HTMLResponse)
def signal_candidate_review(request: Request) -> HTMLResponse:
    presented = present_candidates(
        INBOX_DIR,
        evidence_by_id=_evidence_index(),
        entities=entity_index(),
    )
    ui = read_ui_context(request, BERRIES, inbox_dir=INBOX_DIR)
    presented = [row for row in presented if matches_berry_context(row, ui["berry"])]
    return templates.TemplateResponse(
        request=request,
        name="signal_candidate_review.html",
        context={
            "triage": triage_groups(presented),
            "authoring_mode": AUTHORING_MODE,
            "static_build": False,
            "reviewer": session_username(request) or review_username() or "",
        },
    )


@app.get("/signals/candidates/{candidate_id}", response_class=HTMLResponse)
def signal_candidate_page(request: Request, candidate_id: str) -> HTMLResponse:
    candidate, location = lookup_candidate(INBOX_DIR, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Signal candidate not found")
    if location == "audit":
        return templates.TemplateResponse(
            request=request,
            name="signal_candidate_gone.html",
            context={
                "candidate_id": candidate_id,
                "status": candidate.get("status") or "",
                "reviewer": candidate.get("reviewer") or "",
                "reviewed_at": candidate.get("reviewed_at") or "",
                "review_notes": candidate.get("review_notes") or "",
                "authoring_mode": AUTHORING_MODE,
            },
            status_code=410,
        )
    evidence_by_id = _evidence_index()
    review = present_review(
        candidate,
        evidence_by_id=evidence_by_id,
        entities=entity_index(),
        extra_records=list(evidence_by_id.values()),
    )
    return templates.TemplateResponse(
        request=request,
        name="signal_candidate.html",
        context={
            "review": review,
            "authoring_mode": AUTHORING_MODE,
            "static_build": False,
            "reviewer": session_username(request) or review_username() or "",
            "return_to": request.query_params.get("return_to") or "/brief#emerging-signals",
        },
    )


@app.post("/signals/candidates/{candidate_id}/decision")
def signal_candidate_decision(
    request: Request,
    candidate_id: str,
    decision: str = Form(...),
    reviewer: str = Form(""),
    notes: str = Form(""),
    return_to: str = Form("/brief#emerging-signals"),
) -> RedirectResponse:
    if not AUTHORING_MODE:
        raise HTTPException(status_code=403, detail="Signal-candidate decisions are only available in authoring mode")
    candidate = candidate_by_id(INBOX_DIR, candidate_id)
    if candidate is None:
        _archived, location = lookup_candidate(INBOX_DIR, candidate_id)
        if location == "audit":
            raise HTTPException(
                status_code=410,
                detail="This candidate is no longer in the live review set. The prior decision was preserved and was not applied to any regenerated candidate.",
            )
        raise HTTPException(status_code=404, detail="Signal candidate not found")
    actor = reviewer.strip() or session_username(request) or review_username() or ""
    try:
        apply_and_persist_decision(
            candidate,
            decision=decision,
            reviewer=actor,
            notes=notes,
            inbox_dir=INBOX_DIR,
            expected_id=candidate_id,
        )
    except StaleSignalCandidateError as exc:
        raise HTTPException(status_code=410, detail=str(exc)) from exc
    except SignalCandidateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    target = safe_next_path(return_to)
    return RedirectResponse(url=target, status_code=303)


def _default_signal_values() -> dict[str, Any]:
    return {
        "title": "",
        "description": "",
        "direction": SIGNAL_DIRECTIONS[0],
        "strength": "medium",
        "confidence": "medium",
        "status": "active",
        "evidence_ids": "",
        "fact_ids": "",
        "entity_ids": "",
        "strategic_question_ids": "",
        "first_seen": date.today().isoformat(),
        "last_updated": date.today().isoformat(),
        "reviewer": "",
    }


@app.get("/signals/new", response_class=HTMLResponse)
def signal_new(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="signal_form.html",
        context={
            "values": _default_signal_values(),
            "directions": SIGNAL_DIRECTIONS,
            "strengths": SIGNAL_STRENGTHS,
            "statuses": SIGNAL_STATUSES,
            "error": None,
            "authoring_mode": AUTHORING_MODE,
        },
    )


@app.post("/signals", response_model=None)
def signal_create(
    request: Request,
    title: str = Form(""),
    description: str = Form(""),
    direction: str = Form(""),
    strength: str = Form(""),
    confidence: str = Form(""),
    status: str = Form("active"),
    evidence_ids: str = Form(""),
    fact_ids: str = Form(""),
    entity_ids: str = Form(""),
    strategic_question_ids: str = Form(""),
    first_seen: str = Form(""),
    last_updated: str = Form(""),
    reviewer: str = Form(""),
) -> HTMLResponse | RedirectResponse:
    if not AUTHORING_MODE:
        raise HTTPException(status_code=403, detail="Creating signals is only available in authoring mode")

    values = {
        "title": title,
        "description": description,
        "direction": direction or SIGNAL_DIRECTIONS[0],
        "strength": strength or "medium",
        "confidence": confidence or "medium",
        "status": status or "active",
        "evidence_ids": evidence_ids,
        "fact_ids": fact_ids,
        "entity_ids": entity_ids,
        "strategic_question_ids": strategic_question_ids,
        "first_seen": first_seen.strip() or date.today().isoformat(),
        "last_updated": last_updated.strip() or date.today().isoformat(),
        "reviewer": reviewer,
    }

    evidence_id_list = split_list(evidence_ids)
    fact_id_list = split_list(fact_ids)
    entity_id_list = split_list(entity_ids)

    published_ids = {r["id"] for r in published_evidence()}
    fact_ids_known = {f["id"] for f in all_facts()}
    entity_ids_known = set(entity_index().keys())

    errors: list[str] = []
    if not title.strip():
        errors.append("Title is required.")
    if not reviewer.strip():
        errors.append("Reviewer is required.")
    if not evidence_id_list:
        errors.append("At least one supporting evidence id is required.")
    unknown_evidence = [e for e in evidence_id_list if e not in published_ids]
    if unknown_evidence:
        errors.append(f"Unknown published evidence id(s): {', '.join(unknown_evidence)}.")
    unknown_facts = [f for f in fact_id_list if f not in fact_ids_known]
    if unknown_facts:
        errors.append(f"Unknown fact id(s): {', '.join(unknown_facts)}.")
    unknown_entities = [e for e in entity_id_list if e not in entity_ids_known]
    if unknown_entities:
        errors.append(f"Unknown entity id(s): {', '.join(unknown_entities)}.")

    if errors:
        return templates.TemplateResponse(
            request=request,
            name="signal_form.html",
            context={
                "values": values,
                "directions": SIGNAL_DIRECTIONS,
                "strengths": SIGNAL_STRENGTHS,
                "statuses": SIGNAL_STATUSES,
                "error": " ".join(errors),
                "authoring_mode": AUTHORING_MODE,
            },
            status_code=400,
        )

    strategic_questions = load_strategic_questions()
    sq_ids: list[str] = []
    for text in split_list(strategic_question_ids):
        needle = text.strip().lower()
        for sq in strategic_questions:
            if sq.get("id", "").lower() == needle or sq.get("title", "").lower() == needle:
                sq_ids.append(sq["id"])
                break

    signal_id = new_signal_id(title)
    record = {
        "id": signal_id,
        "record_type": "signal",
        "title": title.strip(),
        "description": description.strip(),
        "direction": values["direction"],
        "strength": values["strength"],
        "confidence": values["confidence"],
        "status": values["status"],
        "evidence_ids": evidence_id_list,
        "fact_ids": fact_id_list,
        "entity_ids": entity_id_list,
        "strategic_question_ids": sq_ids,
        "first_seen": values["first_seen"],
        "last_updated": values["last_updated"],
        "reviewer": reviewer.strip(),
    }

    schema_errors = [e.message for e in get_validator("signal.schema.json").iter_errors(record)]
    if schema_errors:
        return templates.TemplateResponse(
            request=request,
            name="signal_form.html",
            context={
                "values": values,
                "directions": SIGNAL_DIRECTIONS,
                "strengths": SIGNAL_STRENGTHS,
                "statuses": SIGNAL_STATUSES,
                "error": "This signal could not be saved: " + "; ".join(schema_errors),
                "authoring_mode": AUTHORING_MODE,
            },
            status_code=400,
        )

    save_signal(record)
    return RedirectResponse(url=f"/signals/{signal_id}", status_code=303)


@app.get("/signals/{signal_id}", response_class=HTMLResponse)
def signal_detail(request: Request, signal_id: str) -> HTMLResponse:
    signal = signal_by_id(signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found")
    entities = entity_index()
    lineage = get_query_services(DATA_DIR, SCHEMAS_DIR).lineage
    return templates.TemplateResponse(
        request=request,
        name="signal_detail.html",
        context={
            "signal": signal,
            "linked_evidence": lineage.resolve_linked_evidence(signal.get("evidence_ids")),
            "linked_facts": lineage.resolve_linked_facts(signal.get("fact_ids")),
            "linked_entities": lineage.resolve_linked_entities(signal.get("entity_ids"), entities),
            "linked_strategic_questions": lineage.resolve_linked_strategic_questions(
                signal.get("strategic_question_ids")
            ),
            "authoring_mode": AUTHORING_MODE,
            "alert_state": signal_alert_state(signal_id, load_analyst_queue_state(INBOX_DIR)),
        },
    )


@app.get("/assessments", response_class=HTMLResponse)
def assessment_list(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="assessment_list.html",
        context={
            "assessments": attach_assessment_scope(all_assessments(), BERRIES),
            "authoring_mode": AUTHORING_MODE,
        },
    )


def _join_ids(values: list[str] | None) -> str:
    return ", ".join(item for item in (values or []) if item)


def _default_assessment_values() -> dict[str, Any]:
    return {
        "title": "",
        "rationale": "",
        "status": "active",
        "confidence": "medium",
        "fact_ids": "",
        "signal_ids": "",
        "evidence_ids": "",
        "entity_ids": "",
        "strategic_question_ids": "",
        "counterevidence_ids": "",
        "reviewer": "",
        "market_ids": [],
    }


def _assessment_values_from_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": record.get("title") or "",
        "rationale": record.get("rationale") or "",
        "status": record.get("status") or "active",
        "confidence": record.get("confidence") or "medium",
        "fact_ids": _join_ids(record.get("fact_ids")),
        "signal_ids": _join_ids(record.get("signal_ids")),
        "evidence_ids": _join_ids(record.get("evidence_ids")),
        "entity_ids": _join_ids(record.get("entity_ids")),
        "strategic_question_ids": _join_ids(record.get("strategic_question_ids")),
        "counterevidence_ids": _join_ids(record.get("counterevidence_ids")),
        "reviewer": record.get("reviewer") or "",
        "market_ids": assessment_market_berry_ids(record),
    }


def _assessment_form_response(
    request: Request,
    *,
    values: dict[str, Any],
    error: str | None = None,
    status_code: int = 200,
    form_action: str = "/assessments",
    form_title: str = "New Assessment",
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="assessment_form.html",
        context={
            "values": values,
            "statuses": INTELLIGENCE_RECORD_STATUSES,
            "confidence_levels": FACT_CONFIDENCE_LEVELS,
            "error": error,
            "authoring_mode": AUTHORING_MODE,
            "form_action": form_action,
            "form_title": form_title,
            "berries": BERRIES,
        },
        status_code=status_code,
    )


def _assessment_form_errors(values: dict[str, Any]) -> str | None:
    fact_id_list = split_list(values.get("fact_ids") or "")
    signal_id_list = split_list(values.get("signal_ids") or "")
    evidence_id_list = split_list(values.get("evidence_ids") or "")
    entity_id_list = split_list(values.get("entity_ids") or "")
    counterevidence_id_list = split_list(values.get("counterevidence_ids") or "")

    known_facts = {f["id"] for f in all_facts()}
    known_signals = {s["id"] for s in all_signals()}
    published_ids = {r["id"] for r in published_evidence()}
    entity_ids_known = set(entity_index().keys())

    errors: list[str] = []
    if not str(values.get("title") or "").strip():
        errors.append("Title is required.")
    if not str(values.get("rationale") or "").strip():
        errors.append("Rationale is required.")
    if not str(values.get("reviewer") or "").strip():
        errors.append("Reviewer is required.")
    if not fact_id_list:
        errors.append("At least one supporting fact id is required.")
    unknown_facts = [item for item in fact_id_list if item not in known_facts]
    if unknown_facts:
        errors.append(f"Unknown fact id(s): {', '.join(unknown_facts)}.")
    unknown_signals = [item for item in signal_id_list if item not in known_signals]
    if unknown_signals:
        errors.append(f"Unknown signal id(s): {', '.join(unknown_signals)}.")
    unknown_evidence = [item for item in evidence_id_list if item not in published_ids]
    if unknown_evidence:
        errors.append(f"Unknown published evidence id(s): {', '.join(unknown_evidence)}.")
    unknown_entities = [item for item in entity_id_list if item not in entity_ids_known]
    if unknown_entities:
        errors.append(f"Unknown entity id(s): {', '.join(unknown_entities)}.")
    unknown_counterevidence = [
        item for item in counterevidence_id_list if item not in known_facts and item not in published_ids
    ]
    if unknown_counterevidence:
        errors.append(f"Unknown counterevidence id(s): {', '.join(unknown_counterevidence)}.")
    return " ".join(errors) if errors else None


def _assessment_record_from_values(
    values: dict[str, Any],
    *,
    assessment_id: str,
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = dict(existing or {})
    record.update(
        {
            "id": assessment_id,
            "record_type": "assessment",
            "title": str(values.get("title") or "").strip(),
            "rationale": str(values.get("rationale") or "").strip(),
            "status": values.get("status") or "active",
            "confidence": values.get("confidence") or "medium",
            "fact_ids": split_list(values.get("fact_ids") or ""),
            "signal_ids": split_list(values.get("signal_ids") or ""),
            "evidence_ids": split_list(values.get("evidence_ids") or ""),
            "entity_ids": split_list(values.get("entity_ids") or ""),
            "strategic_question_ids": resolve_strategic_question_ids(values.get("strategic_question_ids") or ""),
            "counterevidence_ids": split_list(values.get("counterevidence_ids") or ""),
            "reviewer": str(values.get("reviewer") or "").strip(),
        }
    )
    market_ids = parse_assessment_market_ids(values.get("market_ids") or [])
    if market_ids:
        record["market_ids"] = market_ids
    else:
        record.pop("market_ids", None)
    if existing is None:
        record["created_at"] = date.today().isoformat()
        record.pop("updated_at", None)
    else:
        record["created_at"] = existing.get("created_at") or date.today().isoformat()
        record["updated_at"] = date.today().isoformat()
    return record


def _assessment_schema_error(record: dict[str, Any]) -> str | None:
    schema_errors = [error.message for error in get_validator("assessment.schema.json").iter_errors(record)]
    if not schema_errors:
        return None
    return "This assessment could not be saved: " + "; ".join(schema_errors)


@app.get("/assessments/new", response_class=HTMLResponse)
def assessment_new(request: Request) -> HTMLResponse:
    return _assessment_form_response(request, values=_default_assessment_values())


@app.post("/assessments", response_model=None)
def assessment_create(
    request: Request,
    title: str = Form(""),
    rationale: str = Form(""),
    status: str = Form("active"),
    confidence: str = Form(""),
    fact_ids: str = Form(""),
    signal_ids: str = Form(""),
    evidence_ids: str = Form(""),
    entity_ids: str = Form(""),
    strategic_question_ids: str = Form(""),
    counterevidence_ids: str = Form(""),
    reviewer: str = Form(""),
    market_ids: list[str] = Form(default=[]),
) -> HTMLResponse | RedirectResponse:
    if not AUTHORING_MODE:
        raise HTTPException(status_code=403, detail="Creating assessments is only available in authoring mode")

    values = {
        "title": title,
        "rationale": rationale,
        "status": status or "active",
        "confidence": confidence or "medium",
        "fact_ids": fact_ids,
        "signal_ids": signal_ids,
        "evidence_ids": evidence_ids,
        "entity_ids": entity_ids,
        "strategic_question_ids": strategic_question_ids,
        "counterevidence_ids": counterevidence_ids,
        "reviewer": reviewer,
        "market_ids": parse_assessment_market_ids(market_ids),
    }
    error = _assessment_form_errors(values)
    if error:
        return _assessment_form_response(request, values=values, error=error, status_code=400)

    assessment_id = new_assessment_id(title)
    record = _assessment_record_from_values(values, assessment_id=assessment_id)
    schema_error = _assessment_schema_error(record)
    if schema_error:
        return _assessment_form_response(request, values=values, error=schema_error, status_code=400)

    save_assessment(record)
    return RedirectResponse(url=f"/assessments/{assessment_id}", status_code=303)


@app.get("/assessments/{assessment_id}/edit", response_class=HTMLResponse)
def assessment_edit(request: Request, assessment_id: str) -> HTMLResponse:
    assessment = assessment_by_id(assessment_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return _assessment_form_response(
        request,
        values=_assessment_values_from_record(assessment),
        form_action=f"/assessments/{assessment_id}",
        form_title="Edit Assessment",
    )


@app.post("/assessments/{assessment_id}", response_model=None)
def assessment_update(
    request: Request,
    assessment_id: str,
    title: str = Form(""),
    rationale: str = Form(""),
    status: str = Form("active"),
    confidence: str = Form(""),
    fact_ids: str = Form(""),
    signal_ids: str = Form(""),
    evidence_ids: str = Form(""),
    entity_ids: str = Form(""),
    strategic_question_ids: str = Form(""),
    counterevidence_ids: str = Form(""),
    reviewer: str = Form(""),
    market_ids: list[str] = Form(default=[]),
) -> HTMLResponse | RedirectResponse:
    if not AUTHORING_MODE:
        raise HTTPException(status_code=403, detail="Editing assessments is only available in authoring mode")
    existing = assessment_by_id(assessment_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Assessment not found")

    values = {
        "title": title,
        "rationale": rationale,
        "status": status or "active",
        "confidence": confidence or "medium",
        "fact_ids": fact_ids,
        "signal_ids": signal_ids,
        "evidence_ids": evidence_ids,
        "entity_ids": entity_ids,
        "strategic_question_ids": strategic_question_ids,
        "counterevidence_ids": counterevidence_ids,
        "reviewer": reviewer,
        "market_ids": parse_assessment_market_ids(market_ids),
    }
    form_action = f"/assessments/{assessment_id}"
    error = _assessment_form_errors(values)
    if error:
        return _assessment_form_response(
            request,
            values=values,
            error=error,
            status_code=400,
            form_action=form_action,
            form_title="Edit Assessment",
        )

    record = _assessment_record_from_values(values, assessment_id=assessment_id, existing=existing)
    schema_error = _assessment_schema_error(record)
    if schema_error:
        return _assessment_form_response(
            request,
            values=values,
            error=schema_error,
            status_code=400,
            form_action=form_action,
            form_title="Edit Assessment",
        )

    update_assessment(record)
    return RedirectResponse(url=f"/assessments/{assessment_id}", status_code=303)


@app.get("/assessments/{assessment_id}", response_class=HTMLResponse)
def assessment_detail(request: Request, assessment_id: str) -> HTMLResponse:
    assessment = assessment_by_id(assessment_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    entities = entity_index()
    lineage = get_query_services(DATA_DIR, SCHEMAS_DIR).lineage
    return templates.TemplateResponse(
        request=request,
        name="assessment_detail.html",
        context={
            "assessment": assessment,
            "berry_scope": assessment_berry_scope(assessment, BERRIES),
            "linked_facts": lineage.resolve_linked_facts(assessment.get("fact_ids")),
            "linked_signals": lineage.resolve_linked_signals(assessment.get("signal_ids")),
            "linked_evidence": lineage.resolve_linked_evidence(assessment.get("evidence_ids")),
            "linked_entities": lineage.resolve_linked_entities(assessment.get("entity_ids"), entities),
            "linked_strategic_questions": lineage.resolve_linked_strategic_questions(
                assessment.get("strategic_question_ids")
            ),
            # counterevidence_ids may reference a fact id or an evidence id
            # (see the create route's validation) but this view has only
            # ever resolved the fact half -- preserved exactly, not fixed.
            "counterevidence": lineage.resolve_linked_facts(assessment.get("counterevidence_ids")),
            "authoring_mode": AUTHORING_MODE,
        },
    )


@app.get("/recommendations", response_class=HTMLResponse)
def recommendation_list(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="recommendation_list.html",
        context={"recommendations": all_recommendations(), "authoring_mode": AUTHORING_MODE},
    )


def _default_recommendation_values() -> dict[str, Any]:
    return {
        "title": "",
        "rationale": "",
        "action_type": "",
        "status": "active",
        "priority": "medium",
        "assessment_ids": "",
        "signal_ids": "",
        "fact_ids": "",
        "evidence_ids": "",
        "entity_ids": "",
        "strategic_question_ids": "",
        "reviewer": "",
    }


@app.get("/recommendations/new", response_class=HTMLResponse)
def recommendation_new(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="recommendation_form.html",
        context={
            "values": _default_recommendation_values(),
            "statuses": INTELLIGENCE_RECORD_STATUSES,
            "priorities": RECOMMENDATION_PRIORITIES,
            "error": None,
            "authoring_mode": AUTHORING_MODE,
        },
    )


@app.post("/recommendations", response_model=None)
def recommendation_create(
    request: Request,
    title: str = Form(""),
    rationale: str = Form(""),
    action_type: str = Form(""),
    status: str = Form("active"),
    priority: str = Form(""),
    assessment_ids: str = Form(""),
    signal_ids: str = Form(""),
    fact_ids: str = Form(""),
    evidence_ids: str = Form(""),
    entity_ids: str = Form(""),
    strategic_question_ids: str = Form(""),
    reviewer: str = Form(""),
) -> HTMLResponse | RedirectResponse:
    if not AUTHORING_MODE:
        raise HTTPException(status_code=403, detail="Creating recommendations is only available in authoring mode")

    values = {
        "title": title,
        "rationale": rationale,
        "action_type": action_type,
        "status": status or "active",
        "priority": priority or "medium",
        "assessment_ids": assessment_ids,
        "signal_ids": signal_ids,
        "fact_ids": fact_ids,
        "evidence_ids": evidence_ids,
        "entity_ids": entity_ids,
        "strategic_question_ids": strategic_question_ids,
        "reviewer": reviewer,
    }

    assessment_id_list = split_list(assessment_ids)
    signal_id_list = split_list(signal_ids)
    fact_id_list = split_list(fact_ids)
    evidence_id_list = split_list(evidence_ids)
    entity_id_list = split_list(entity_ids)

    known_assessments = {a["id"] for a in all_assessments()}
    known_signals = {s["id"] for s in all_signals()}
    known_facts = {f["id"] for f in all_facts()}
    published_ids = {r["id"] for r in published_evidence()}
    entity_ids_known = set(entity_index().keys())

    errors: list[str] = []
    if not title.strip():
        errors.append("Title is required.")
    if not rationale.strip():
        errors.append("Rationale is required.")
    if not action_type.strip():
        errors.append("Action type is required.")
    if not reviewer.strip():
        errors.append("Reviewer is required.")
    if not assessment_id_list and not signal_id_list:
        errors.append("At least one linked assessment id or signal id is required.")
    unknown_assessments = [a for a in assessment_id_list if a not in known_assessments]
    if unknown_assessments:
        errors.append(f"Unknown assessment id(s): {', '.join(unknown_assessments)}.")
    unknown_signals = [s for s in signal_id_list if s not in known_signals]
    if unknown_signals:
        errors.append(f"Unknown signal id(s): {', '.join(unknown_signals)}.")
    unknown_facts = [f for f in fact_id_list if f not in known_facts]
    if unknown_facts:
        errors.append(f"Unknown fact id(s): {', '.join(unknown_facts)}.")
    unknown_evidence = [e for e in evidence_id_list if e not in published_ids]
    if unknown_evidence:
        errors.append(f"Unknown published evidence id(s): {', '.join(unknown_evidence)}.")
    unknown_entities = [e for e in entity_id_list if e not in entity_ids_known]
    if unknown_entities:
        errors.append(f"Unknown entity id(s): {', '.join(unknown_entities)}.")

    if errors:
        return templates.TemplateResponse(
            request=request,
            name="recommendation_form.html",
            context={
                "values": values,
                "statuses": INTELLIGENCE_RECORD_STATUSES,
                "priorities": RECOMMENDATION_PRIORITIES,
                "error": " ".join(errors),
                "authoring_mode": AUTHORING_MODE,
            },
            status_code=400,
        )

    recommendation_id = new_recommendation_id(title)
    record = {
        "id": recommendation_id,
        "record_type": "recommendation",
        "title": title.strip(),
        "rationale": rationale.strip(),
        "action_type": action_type.strip(),
        "status": values["status"],
        "priority": values["priority"],
        "assessment_ids": assessment_id_list,
        "signal_ids": signal_id_list,
        "fact_ids": fact_id_list,
        "evidence_ids": evidence_id_list,
        "entity_ids": entity_id_list,
        "strategic_question_ids": resolve_strategic_question_ids(strategic_question_ids),
        "reviewer": reviewer.strip(),
        "created_at": date.today().isoformat(),
    }

    schema_errors = [e.message for e in get_validator("recommendation.schema.json").iter_errors(record)]
    if schema_errors:
        return templates.TemplateResponse(
            request=request,
            name="recommendation_form.html",
            context={
                "values": values,
                "statuses": INTELLIGENCE_RECORD_STATUSES,
                "priorities": RECOMMENDATION_PRIORITIES,
                "error": "This recommendation could not be saved: " + "; ".join(schema_errors),
                "authoring_mode": AUTHORING_MODE,
            },
            status_code=400,
        )

    save_recommendation(record)
    return RedirectResponse(url=f"/recommendations/{recommendation_id}", status_code=303)


@app.get("/recommendations/{recommendation_id}", response_class=HTMLResponse)
def recommendation_detail(request: Request, recommendation_id: str) -> HTMLResponse:
    recommendation = recommendation_by_id(recommendation_id)
    if recommendation is None:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    entities = entity_index()
    lineage = get_query_services(DATA_DIR, SCHEMAS_DIR).lineage
    return templates.TemplateResponse(
        request=request,
        name="recommendation_detail.html",
        context={
            "recommendation": recommendation,
            "linked_assessments": lineage.resolve_linked_assessments(recommendation.get("assessment_ids")),
            "linked_signals": lineage.resolve_linked_signals(recommendation.get("signal_ids")),
            "linked_facts": lineage.resolve_linked_facts(recommendation.get("fact_ids")),
            "linked_evidence": lineage.resolve_linked_evidence(recommendation.get("evidence_ids")),
            "linked_entities": lineage.resolve_linked_entities(recommendation.get("entity_ids"), entities),
            "linked_strategic_questions": lineage.resolve_linked_strategic_questions(
                recommendation.get("strategic_question_ids")
            ),
            "authoring_mode": AUTHORING_MODE,
            "proposal_state": proposal_state(recommendation_id, load_analyst_queue_state(INBOX_DIR)),
        },
    )


def sources_page_context(
    entity_type: str | None,
    berry: str | None,
    region: str | None,
    priority: str | None,
    view: str | None,
    group_by: str,
    error: str | None,
) -> dict[str, Any]:
    all_sources = load_sources()
    filtered = filter_sources(all_sources, entity_type=entity_type, berry=berry, region=region, priority=priority, view=view)
    companies = sorted(
        ({"id": e["id"], "name": e["name"]} for e in all_entities() if e.get("entity_type") == "company"),
        key=lambda c: c["name"],
    )
    # Cadence-aware automated-discovery freshness, distinct from the
    # human-review last_checked_at/next_check_due above -- "no new stories"
    # (CURRENT/DUE) is a different fact from "we haven't successfully
    # checked this source lately" (STALE/FAILING), and an analyst needs to
    # tell them apart. Cheap: reads small per-source JSON state files, no
    # network calls or per-item orchestration dry-run.
    discovered_items = list_discovered_items(INBOX_DIR)
    published = published_evidence()
    latest_by_source = index_latest_item_dates(discovered_items=discovered_items, published_evidence=published)

    def _freshness_for(source: dict[str, Any]) -> dict[str, Any]:
        published_at, captured_at = latest_by_source.get(source["id"], (None, None))
        return classify_source_freshness(
            source,
            discovery_state=read_source_discovery_state(INBOX_DIR, source["id"]),
            latest_item_published_at=published_at,
            latest_item_captured_at=captured_at,
        ).as_dict()

    freshness_by_source = {source["id"]: _freshness_for(source) for source in all_sources if source.get("id")}
    health_rows = present_source_health_rows(
        filtered,
        freshness_by_source=freshness_by_source,
        entity_type_labels=SOURCE_ENTITY_TYPES,
        berry_labels=BERRIES,
        region_labels=SOURCE_REGIONS,
        cadence_labels=SOURCE_CADENCES,
        retry_hints=retry_hints_by_source(INBOX_DIR),
    )
    return {
        "sources": filtered,
        "total_count": len(all_sources),
        "grouped_sources": group_sources(filtered, group_by),
        "health_groups": group_source_health(health_rows),
        "gaps_count": len([s for s in all_sources if source_has_coverage_gap(s)]),
        "due_count": len([s for s in all_sources if source_is_due(s)]),
        "freshness_by_source": freshness_by_source,
        "source_coverage": aggregate_source_coverage(freshness_by_source),
        "freshness_states": FRESHNESS_LABELS,
        "source_types": SOURCE_TYPES,
        "source_entity_types": SOURCE_ENTITY_TYPES,
        "source_regions": SOURCE_REGIONS,
        "source_priorities": SOURCE_PRIORITIES,
        "source_cadences": SOURCE_CADENCES,
        "berries": BERRIES,
        "companies": companies,
        "next_check_due": next_check_due,
        "source_is_due": source_is_due,
        "source_has_coverage_gap": source_has_coverage_gap,
        "blocked_domains": load_blocked_domains(),
        "filters": {
            "entity_type": entity_type or "",
            "berry": berry or "",
            "region": region or "",
            "priority": priority or "",
            "view": view or "",
            "group_by": group_by,
        },
        "poll_interval_minutes": SOURCE_POLL_INTERVAL_SECONDS // 60,
        "source_polling_enabled": SOURCE_POLLING_ENABLED,
        "error": error,
        "authoring_mode": AUTHORING_MODE,
    }


@app.get("/sources", response_class=HTMLResponse)
def sources_list(
    request: Request,
    entity_type: str | None = None,
    berry: str | None = None,
    region: str | None = None,
    priority: str | None = None,
    view: str | None = None,
    group_by: str = "entity_type",
    error: str | None = None,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="sources.html",
        context=sources_page_context(entity_type, berry, region, priority, view, group_by, error),
    )


@app.post("/sources", response_model=None)
def sources_add(
    request: Request,
    type: str = Form(...),
    label: str = Form(""),
    value: str = Form(""),
    url: str = Form(""),
    why_it_matters: str = Form(""),
    monitoring_priority: str = Form(""),
    update_cadence: str = Form(""),
    entity_types: list[str] = Form([]),
    berry_ids: list[str] = Form([]),
    region_coverage: list[str] = Form([]),
    linked_competitor_ids: list[str] = Form([]),
) -> HTMLResponse | RedirectResponse:
    if not AUTHORING_MODE:
        raise HTTPException(status_code=403, detail="Adding sources is only available in authoring mode")
    if type not in SOURCE_TYPES or not label.strip() or not value.strip():
        return templates.TemplateResponse(
            request=request,
            name="sources.html",
            context=sources_page_context(
                None, None, None, None, None, "entity_type",
                "Type, label, and value (feed URL or search term) are all required.",
            ),
            status_code=400,
        )
    sources = load_sources()
    sources.append(
        {
            "id": new_source_id(label),
            "type": type,
            "label": label.strip(),
            "value": value.strip(),
            "url": url.strip(),
            "why_it_matters": why_it_matters.strip(),
            "entity_types": [t for t in entity_types if t in SOURCE_ENTITY_TYPES],
            "berry_ids": [b for b in berry_ids if b in BERRIES],
            "region_coverage": [r for r in region_coverage if r in SOURCE_REGIONS],
            "monitoring_priority": monitoring_priority if monitoring_priority in SOURCE_PRIORITIES else None,
            "update_cadence": update_cadence if update_cadence in SOURCE_CADENCES else None,
            "linked_competitor_ids": linked_competitor_ids,
            "enabled": True,
            "created_at": date.today().isoformat(),
            "last_checked_at": None,
            "last_status": None,
        }
    )
    save_sources(sources)
    return RedirectResponse(url="/sources", status_code=303)


@app.post("/sources/{source_id}/toggle")
def sources_toggle(source_id: str) -> RedirectResponse:
    if not AUTHORING_MODE:
        raise HTTPException(status_code=403, detail="Managing sources is only available in authoring mode")
    sources = load_sources()
    for source in sources:
        if source["id"] == source_id:
            source["enabled"] = not source.get("enabled", True)
            break
    else:
        raise HTTPException(status_code=404, detail="Source not found")
    save_sources(sources)
    return RedirectResponse(url="/sources", status_code=303)


@app.post("/sources/{source_id}/delete")
def sources_delete(source_id: str) -> RedirectResponse:
    if not AUTHORING_MODE:
        raise HTTPException(status_code=403, detail="Managing sources is only available in authoring mode")
    sources = [s for s in load_sources() if s["id"] != source_id]
    save_sources(sources)
    return RedirectResponse(url="/sources", status_code=303)


@app.post("/sources/{source_id}/check-now")
def sources_check_now(source_id: str) -> RedirectResponse:
    if not AUTHORING_MODE:
        raise HTTPException(status_code=403, detail="Managing sources is only available in authoring mode")
    sources = load_sources()
    for source in sources:
        if source["id"] == source_id:
            seen_urls = existing_evidence_source_urls()
            source["last_checked_at"] = datetime.now().isoformat(timespec="seconds")
            try:
                written = check_source(source, seen_urls)
                source["last_status"] = f"ok: {written} new item(s)" if written else "ok: no new items"
            except Exception as exc:                    # noqa: BLE001
                source["last_status"] = f"error: {exc}"
            break
    else:
        raise HTTPException(status_code=404, detail="Source not found")
    save_sources(sources)
    return RedirectResponse(url="/sources", status_code=303)


@app.post("/sources/{source_id}/mark-checked")
def sources_mark_checked(source_id: str) -> RedirectResponse:
    """For reference-type sources: record that a human reviewed it, since
    there's nothing to auto-fetch. Distinct from /check-now, which actually
    fetches and writes evidence for rss/keyword sources."""
    if not AUTHORING_MODE:
        raise HTTPException(status_code=403, detail="Managing sources is only available in authoring mode")
    sources = load_sources()
    for source in sources:
        if source["id"] == source_id:
            source["last_checked_at"] = datetime.now().isoformat(timespec="seconds")
            source["last_status"] = "reviewed"
            break
    else:
        raise HTTPException(status_code=404, detail="Source not found")
    save_sources(sources)
    return RedirectResponse(url="/sources", status_code=303)


@app.post("/sources/blocked-domains/{domain}/remove")
def sources_unblock_domain(domain: str) -> RedirectResponse:
    if not AUTHORING_MODE:
        raise HTTPException(status_code=403, detail="Managing sources is only available in authoring mode")
    save_blocked_domains([d for d in load_blocked_domains() if d != domain])
    return RedirectResponse(url="/sources", status_code=303)


@app.get("/intake", response_class=HTMLResponse)
def intake_form(
    request: Request,
    type: str = "article_or_url",
    created: str | None = None,
) -> HTMLResponse:
    if type not in INTAKE_TYPES:
        type = "article_or_url"
    return templates.TemplateResponse(
        request=request,
        name="intake.html",
        context={
            "intake_types": INTAKE_TYPES,
            "active_type": type,
            "drafts": list_drafts(),
            "created_id": created,
            "error": None,
            "form_values": None,
            "authoring_mode": AUTHORING_MODE,
        },
    )


@app.post("/intake", response_model=None)
def intake_submit(
    request: Request,
    intake_type: str = Form(...),
    title: str = Form(""),
    source_url: str = Form(""),
    source_name: str = Form(""),
    published_date: str = Form(""),
    captured_date: str = Form(""),
    summary: str = Form(""),
    why_it_matters: str = Form(""),
    submitted_by: str = Form(""),
    suggested_competitors: str = Form(""),
    suggested_varieties: str = Form(""),
    attachment: UploadFile | None = File(None),
) -> HTMLResponse | RedirectResponse:
    if not AUTHORING_MODE:
        raise HTTPException(status_code=403, detail="Intake is only available in authoring mode")

    if intake_type not in INTAKE_TYPES:
        intake_type = "article_or_url"

    errors: list[str] = []
    if not title.strip():
        errors.append("Title is required.")
    if not summary.strip():
        errors.append("Summary / notes is required.")
    if not submitted_by.strip():
        errors.append("Submitted by is required.")
    if intake_type == "article_or_url" and not source_url.strip():
        errors.append("Source URL is required for an article or URL submission.")
    if intake_type == "uploaded_report" and (attachment is None or not attachment.filename):
        errors.append("A file attachment is required for an uploaded report.")

    if errors:
        return templates.TemplateResponse(
            request=request,
            name="intake.html",
            context={
                "intake_types": INTAKE_TYPES,
                "active_type": intake_type,
                "drafts": list_drafts(),
                "created_id": None,
                "error": " ".join(errors),
                "authoring_mode": AUTHORING_MODE,
                "form_values": {
                    "title": title,
                    "source_url": source_url,
                    "source_name": source_name,
                    "published_date": published_date,
                    "summary": summary,
                    "why_it_matters": why_it_matters,
                    "submitted_by": submitted_by,
                    "suggested_competitors": suggested_competitors,
                    "suggested_varieties": suggested_varieties,
                },
            },
            status_code=400,
        )

    draft_id = new_draft_id(title)
    attachments = []
    if attachment is not None and attachment.filename:
        attachments.append(save_attachment(draft_id, attachment))

    record = {
        "id": draft_id,
        "record_type": "evidence",
        "status": "draft",
        "intake_type": intake_type,
        "source_type": INTAKE_SOURCE_TYPES[intake_type],
        "title": title.strip(),
        "source_name": source_name.strip(),
        "source_url": source_url.strip(),
        "published_date": published_date.strip() or None,
        "captured_date": captured_date.strip() or date.today().isoformat(),
        "summary": summary.strip(),
        "why_it_matters": why_it_matters.strip(),
        "submitted_by": submitted_by.strip(),
        "suggested_competitors": split_list(suggested_competitors),
        "suggested_varieties": split_list(suggested_varieties),
        "attachments": attachments,
        "berry_ids": [],
        "entity_ids": [],
        "fact_ids": [],
        "relationship_ids": [],
        "strategic_question_ids": [],
        "tags": [],
        "priority": None,
    }
    save_draft(record)
    return RedirectResponse(url=f"/intake?type={intake_type}&created={draft_id}", status_code=303)


@app.get("/intake/{draft_id}", response_class=HTMLResponse)
def intake_detail(request: Request, draft_id: str) -> HTMLResponse:
    draft = get_draft(draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    return templates.TemplateResponse(request=request, name="intake_detail.html", context={"draft": draft})


@app.get("/intake/{draft_id}/attachments/{filename}")
def intake_attachment(draft_id: str, filename: str) -> FileResponse:
    directory = (INBOX_DIR / "attachments" / draft_id).resolve()
    target = (directory / filename).resolve()
    if not target.is_file() or not target.is_relative_to(directory):
        raise HTTPException(status_code=404, detail="Attachment not found")
    return FileResponse(target)


def _safe_review_return(value: str | None, *, fallback: str = "/review") -> str:
    if not value:
        return fallback
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc:
        return fallback
    path = parsed.path or ""
    if not path.startswith("/") or ".." in path or path.startswith("//"):
        return fallback
    parts = [segment for segment in path.split("/") if segment]
    allowed = False
    if path == "/review" or path.startswith("/review/"):
        allowed = len(parts) <= 2
    elif path == "/work-queue":
        allowed = True
    elif path.startswith("/intelligence/") or path.startswith("/evidence/"):
        allowed = len(parts) == 2
    if not allowed:
        return fallback
    return path + (f"?{parsed.query}" if parsed.query else "")


def _review_publish_service() -> ReviewPublishService:
    return ReviewPublishService(
        repositories=get_repositories(DATA_DIR, SCHEMAS_DIR),
        unit_of_work_factory=lambda: get_unit_of_work(
            DATA_DIR, SCHEMAS_DIR, "entities", "facts", "relationships", "evidence"
        ),
        get_validator=get_validator,
        unique_entity_id=unique_entity_id,
        append_unique=append_unique,
        move_draft_attachments=move_draft_attachments,
        restore_draft_attachments=restore_draft_attachments,
        delete_draft=delete_draft,
        review_events_inbox=INBOX_DIR,
    )


@app.get("/review", response_class=HTMLResponse)
def review_queue(
    request: Request,
    kind: str | None = None,
    state: str | None = None,
    source: str | None = None,
    parent: str | None = None,
    media_format: str | None = None,
    berry: str | None = None,
    geography: str | None = None,
    model: str | None = None,
    version: str | None = None,
    sort: str | None = None,
    enrichment: str | None = None,
    current: str | None = None,
) -> HTMLResponse:
    repositories = get_repositories(DATA_DIR, SCHEMAS_DIR)
    drafts = list_drafts()
    filters = {
        "kind": kind,
        "state": state,
        "source": source,
        "parent": parent,
        "media_format": media_format,
        "berry": berry,
        "geography": geography,
        "model": model,
        "version": version,
        "sort": sort,
        "enrichment": enrichment,
    }
    workbench = build_review_workbench(
        drafts=drafts,
        evidence=repositories.evidence.list(),
        sources=repositories.sources.list(),
        entities=repositories.entities.list(),
        berry_labels=BERRIES,
        publication_transcript_readiness=load_publication_transcript_readiness(INBOX_DIR),
        filters=filters,
    )
    stable_params = {
        key: value for key, value in workbench["filters"].items()
        if value and not (key == "state" and value == "pending")
    }
    for group in workbench["groups"]:
        pending_cards = [card for card in group["cards"] if card["state"] == "pending"]
        for index, card in enumerate(pending_cards):
            return_params = {**stable_params, "parent": group["parent_id"]}
            if index + 1 < len(pending_cards):
                return_params["current"] = pending_cards[index + 1]["record"]["id"]
            card["return_to"] = "/review?" + urlencode(return_params)
            card["edit_url"] = f"/review/{card['record']['id']}?return_to={quote(card['return_to'], safe='')}"

    entities = {record["id"]: record for record in repositories.entities.list() if record.get("id")}
    return templates.TemplateResponse(
        request=request,
        name="review_queue.html",
        context={
            "drafts": workbench["generic_drafts"],
            "workbench": workbench,
            "current_id": current,
            "rejection_categories": REJECTION_CATEGORIES,
            "unvalidated_evidence": unvalidated_auto_captured_evidence(),
            "entities": entities,
            "scanner": build_scanner_summary(
                inbox_dir=INBOX_DIR,
                drafts=drafts,
                published=repositories.evidence.list(),
                transcript_readiness=load_publication_transcript_readiness(INBOX_DIR),
            ),
            "authoring_mode": AUTHORING_MODE,
        },
    )


def _default_review_values(draft: dict[str, Any]) -> dict[str, Any]:
    enrichment = draft.get("ai_enrichment") or {}
    concise = (enrichment.get("concise_summary") or "").strip()
    why = (draft.get("why_it_matters") or enrichment.get("why_it_matters") or "").strip()
    summary = (draft.get("summary") or "").strip()
    publisher = (draft.get("publisher_description") or "").strip()
    if concise and (not summary or summary == publisher):
        summary = concise
    tags = list(draft.get("tags") or [])
    for tag in enrichment.get("suggested_tags") or []:
        if tag and tag not in tags:
            tags.append(tag)
    berries = list(draft.get("berry_ids") or [])
    for berry_id in enrichment.get("suggested_berry_ids") or []:
        if berry_id and berry_id not in berries:
            berries.append(berry_id)
    return {
        "title": decode_html_text(draft.get("title", "")),
        "source_type": draft.get("source_type", ""),
        "source_name": draft.get("source_name", ""),
        "source_url": draft.get("source_url", ""),
        "published_date": draft.get("published_date") or "",
        "captured_date": draft.get("captured_date", ""),
        "summary": decode_html_text(summary),
        "why_it_matters": decode_html_text(why),
        "tags": ", ".join(tags),
        "companies": ", ".join(draft.get("suggested_competitors", [])),
        "varieties": ", ".join(draft.get("suggested_varieties", [])),
        "retailers": ", ".join(draft.get("suggested_retailers", [])),
        "geographies": ", ".join(draft.get("suggested_geographies", [])),
        "berries": berries,
        "strategic_questions": "",
        "reviewer": "",
        "facts": [{"statement": "", "classification": "fact", "confidence": "medium"} for _ in range(NUM_FACT_ROWS)],
        "relationships": [
            {"subject": "", "predicate": RELATIONSHIP_PREDICATES[0], "object": "", "effective_date": ""}
            for _ in range(NUM_RELATIONSHIP_ROWS)
        ],
        "priority": {dim: {"level": "none", "rationale": ""} for dim in PRIORITY_DIMENSIONS},
    }


def _review_context(
    draft: dict[str, Any],
    values: dict[str, Any],
    error: str | None,
    *,
    return_to: str = "/review",
    publish_outcome: str | None = None,
    conflicts: list[str] | None = None,
) -> dict[str, Any]:
    repositories = get_repositories(DATA_DIR, SCHEMAS_DIR)
    parent = repositories.evidence.get(draft.get("parent_evidence_id")) if draft.get("parent_evidence_id") else None
    entities = {record["id"]: record for record in repositories.entities.list() if record.get("id")}
    if draft.get("evidence_role") == "atomic_evidence":
        field_by_type = {
            "company": "companies",
            "variety": "varieties",
            "retailer": "retailers",
            "geography": "geographies",
        }
        linked_by_field: dict[str, list[str]] = {value: [] for value in field_by_type.values()}
        for entity_id in draft.get("entity_ids") or []:
            entity = entities.get(entity_id) or {}
            field_name = field_by_type.get(entity.get("entity_type"))
            if field_name:
                linked_by_field[field_name].append(entity.get("name", entity_id))
        for field_name, names in linked_by_field.items():
            if names and not values.get(field_name):
                values[field_name] = ", ".join(names)
    elif draft.get("evidence_role") == "publication_artifact":
        def _names(ids: list[str], entity_type: str | None = None) -> list[str]:
            names: list[str] = []
            for entity_id in ids:
                entity = entities.get(entity_id) or {}
                if entity_type and entity.get("entity_type") != entity_type:
                    continue
                name = entity.get("name")
                if name and name not in names:
                    names.append(name)
            return names

        if not values.get("companies"):
            values["companies"] = ", ".join(_names(list(draft.get("entity_ids") or []), "company"))
        if not values.get("geographies"):
            values["geographies"] = ", ".join(
                _names(list(draft.get("geography_ids") or []) + list(draft.get("entity_ids") or []), "geography")
            )
        if not values.get("varieties"):
            values["varieties"] = ", ".join(_names(list(draft.get("entity_ids") or []), "variety"))
        if not values.get("retailers"):
            values["retailers"] = ", ".join(_names(list(draft.get("entity_ids") or []), "retailer"))
    transcript_readiness = None
    if draft.get("evidence_role") == "publication_artifact":
        transcript_readiness = load_publication_transcript_readiness(INBOX_DIR).get(
            draft["id"], unknown_transcript_readiness()
        )
        transcript_readiness["analyst_label"] = analyst_transcript_label(transcript_readiness)
    trusted_existing = None
    if draft.get("id"):
        trusted_existing = repositories.evidence.get(draft["id"])
    publication_card = None
    publication_dossier = None
    if draft.get("evidence_role") == "publication_artifact":
        presentation = deepcopy(draft)
        presentation["transcript_readiness"] = transcript_readiness or unknown_transcript_readiness()
        attach_publication_card(presentation, entities=entities, berry_labels=BERRIES)
        publication_card = presentation.get("card")
        publication_dossier = build_publication_review_dossier(
            draft,
            entities=entities,
            berry_labels=BERRIES,
            sources=load_sources(),
        )
        values = apply_dossier_prefill(values, publication_dossier)
    return {
        "draft": draft,
        "parent": parent,
        "linked_entities": [entities[value] for value in (draft.get("entity_ids") or []) if value in entities],
        "locator_label": format_locator(draft.get("artifact_locator")),
        "duplicates": find_possible_duplicates(values["title"] or draft.get("title", ""), exclude_id=draft["id"]),
        "berries": BERRIES,
        "predicates": RELATIONSHIP_PREDICATES,
        "fact_classifications": FACT_CLASSIFICATIONS,
        "fact_confidence_levels": FACT_CONFIDENCE_LEVELS,
        "num_fact_rows": NUM_FACT_ROWS,
        "num_relationship_rows": NUM_RELATIONSHIP_ROWS,
        "priority_dimensions": PRIORITY_DIMENSIONS,
        "priority_levels": PRIORITY_LEVELS,
        "values": values,
        "error": error,
        "authoring_mode": AUTHORING_MODE,
        "return_to": _safe_review_return(return_to),
        "rejection_categories": REJECTION_CATEGORIES,
        "transcript_readiness": transcript_readiness,
        "publish_outcome": publish_outcome,
        "conflicts": conflicts or [],
        "trusted_existing": trusted_existing,
        "publication_card": publication_card,
        "publication_dossier": publication_dossier,
        "next_draft_id": adjacent_publication_draft_id(draft.get("id") or ""),
        "prev_draft_id": adjacent_publication_draft_id(draft.get("id") or "", step=-1),
    }


@app.get("/review/{draft_id}", response_class=HTMLResponse)
def review_form(request: Request, draft_id: str) -> HTMLResponse:
    draft = get_draft(draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    return templates.TemplateResponse(
        request=request,
        name="review.html",
        context=_review_context(
            draft,
            _default_review_values(draft),
            None,
            return_to=request.query_params.get("return_to", "/review"),
        ),
    )


@app.post("/review/{draft_id}/publish", response_model=None)
async def review_publish(request: Request, draft_id: str) -> HTMLResponse | RedirectResponse:
    if not AUTHORING_MODE:
        raise HTTPException(status_code=403, detail="Publishing is only available in authoring mode")

    draft = get_draft(draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    if draft.get("status") == "rejected":
        raise HTTPException(status_code=400, detail="Rejected drafts cannot be published")

    form = await request.form()

    def field(name: str, default: str = "") -> str:
        value = form.get(name, default)
        return value if isinstance(value, str) else default

    title = field("title").strip()
    source_type = field("source_type").strip() or draft.get("source_type", "article")
    source_name = field("source_name").strip()
    source_url = field("source_url").strip()
    published_date = field("published_date").strip() or None
    captured_date = field("captured_date").strip() or draft.get("captured_date", date.today().isoformat())
    summary = field("summary").strip()
    why_it_matters = field("why_it_matters").strip()
    tags = split_list(field("tags"))
    companies = split_list(field("companies"))
    varieties = split_list(field("varieties"))
    retailers = split_list(field("retailers"))
    geographies = split_list(field("geographies"))
    strategic_question_text = split_list(field("strategic_questions"))
    reviewer = field("reviewer").strip()
    return_to = _safe_review_return(field("return_to"), fallback="")
    selected_berries = [b for b in form.getlist("berries") if isinstance(b, str)]
    if draft.get("evidence_role") == "atomic_evidence" and summary:
        title = summary[:160]
        # Reviewers may edit the proposed statement and supported links, but
        # the publication/transcript lineage is not form-editable.
        source_type = draft.get("source_type", source_type)
        source_name = draft.get("source_name", source_name)
        source_url = draft.get("source_url", source_url)
        published_date = draft.get("published_date")
        captured_date = draft.get("captured_date", captured_date)
        why_it_matters = draft.get("why_it_matters", "")
        tags = list(draft.get("tags") or [])

    facts_input = []
    for i in range(1, NUM_FACT_ROWS + 1):
        statement = field(f"fact_statement_{i}").strip()
        if statement:
            facts_input.append(
                {
                    "statement": statement,
                    "classification": field(f"fact_classification_{i}", "fact"),
                    "confidence": field(f"fact_confidence_{i}", "medium"),
                }
            )

    relationships_input = []
    for i in range(1, NUM_RELATIONSHIP_ROWS + 1):
        subject = field(f"rel_subject_{i}").strip()
        obj = field(f"rel_object_{i}").strip()
        if subject and obj:
            relationships_input.append(
                {
                    "subject": subject,
                    "predicate": field(f"rel_predicate_{i}", RELATIONSHIP_PREDICATES[0]),
                    "object": obj,
                    "effective_date": field(f"rel_effective_date_{i}").strip() or None,
                }
            )

    priority = {
        dim: {
            "level": field(f"priority_{dim}_level", "none"),
            "rationale": field(f"priority_{dim}_rationale").strip(),
        }
        for dim in PRIORITY_DIMENSIONS
    }
    if draft.get("evidence_role") == "atomic_evidence":
        priority = deepcopy(draft.get("priority") or priority)

    values = {
        "title": title,
        "source_type": source_type,
        "source_name": source_name,
        "source_url": source_url,
        "published_date": published_date or "",
        "captured_date": captured_date,
        "summary": summary,
        "why_it_matters": why_it_matters,
        "tags": field("tags"),
        "companies": field("companies"),
        "varieties": field("varieties"),
        "retailers": field("retailers"),
        "geographies": field("geographies"),
        "berries": selected_berries,
        "strategic_questions": field("strategic_questions"),
        "reviewer": reviewer,
        "facts": [
            {
                "statement": field(f"fact_statement_{i}"),
                "classification": field(f"fact_classification_{i}", "fact"),
                "confidence": field(f"fact_confidence_{i}", "medium"),
            }
            for i in range(1, NUM_FACT_ROWS + 1)
        ],
        "relationships": [
            {
                "subject": field(f"rel_subject_{i}"),
                "predicate": field(f"rel_predicate_{i}", RELATIONSHIP_PREDICATES[0]),
                "object": field(f"rel_object_{i}"),
                "effective_date": field(f"rel_effective_date_{i}"),
            }
            for i in range(1, NUM_RELATIONSHIP_ROWS + 1)
        ],
        "priority": priority,
    }

    errors: list[str] = []
    if not title:
        errors.append("Title is required.")
    if not summary:
        errors.append("Summary is required.")
    if not reviewer:
        errors.append("Reviewer is required.")
    for dim in PRIORITY_DIMENSIONS:
        if priority[dim]["level"] != "none" and not priority[dim]["rationale"]:
            errors.append(f"A rationale is required for {dim.replace('_', ' ')} priority.")

    all_entity_names_by_type = {
        "company": companies,
        "variety": varieties,
        "retailer": retailers,
        "geography": geographies,
    }
    linked_names = {name for names in all_entity_names_by_type.values() for name in names}
    for rel in relationships_input:
        if rel["subject"] not in linked_names:
            errors.append(f"Relationship subject '{rel['subject']}' must match a linked company, variety, retailer, or geography name above.")
        if rel["object"] not in linked_names:
            errors.append(f"Relationship object '{rel['object']}' must match a linked company, variety, retailer, or geography name above.")

    if errors:
        return templates.TemplateResponse(
            request=request,
            name="review.html",
            context=_review_context(draft, values, " ".join(errors), return_to=return_to or "/review"),
            status_code=400,
        )

    # Persistence orchestration (entity match/create/update, Facts,
    # Relationships, Evidence, the transactional boundary, and the
    # Draft-success handoff) lives in ReviewPublishService, not here -- see
    # app/services/review_publish.py. This route stays limited to HTTP
    # concerns: parsing the form (above) and turning the service's result
    # into a response (below).
    service = _review_publish_service()
    editable_entity_types = {"company", "variety", "retailer", "geography"}
    entity_index_for_preservation = {
        entity["id"]: entity for entity in get_repositories(DATA_DIR, SCHEMAS_DIR).entities.list()
        if entity.get("id")
    }
    preserved_entity_ids = [
        entity_id for entity_id in (draft.get("entity_ids") or [])
        if (entity_index_for_preservation.get(entity_id) or {}).get("entity_type") not in editable_entity_types
    ]
    try:
        result = service.publish(
            PublishRequest(
                draft=draft,
                draft_id=draft_id,
                title=title,
                source_type=source_type,
                source_name=source_name,
                source_url=source_url,
                published_date=published_date,
                captured_date=captured_date,
                summary=summary,
                why_it_matters=why_it_matters,
                tags=tags,
                selected_berries=selected_berries,
                all_entity_names_by_type=all_entity_names_by_type,
                facts_input=facts_input,
                relationships_input=relationships_input,
                priority=priority,
                strategic_question_text=strategic_question_text,
                reviewer=reviewer,
                existing_entity_ids=preserved_entity_ids,
            )
        )
    except DuplicateRecord:
        return templates.TemplateResponse(
            request=request,
            name="review.html",
            context=_review_context(
                draft,
                values,
                "This id already exists as a trusted publication. The trusted record was not changed.",
                return_to=return_to or "/review",
                publish_outcome="conflict",
                conflicts=[f"a trusted record with id {draft_id!r} already exists"],
            ),
            status_code=409,
        )

    advance = field("advance").strip() == "next"
    next_id = adjacent_publication_draft_id(draft_id) if advance else None

    if result.outcome == "conflict":
        return templates.TemplateResponse(
            request=request,
            name="review.html",
            context=_review_context(
                draft,
                values,
                "This id already exists as a trusted publication with conflicting identity fields. The trusted record was not changed.",
                return_to=return_to or "/review",
                publish_outcome="conflict",
                conflicts=result.conflicts,
            ),
            status_code=409,
        )

    if result.outcome == "already_published":
        if next_id:
            return RedirectResponse(url=f"/review/{next_id}", status_code=303)
        remaining = get_draft(draft_id)
        if remaining is None:
            return RedirectResponse(url=return_to or f"/evidence/{result.evidence_id}", status_code=303)
        return templates.TemplateResponse(
            request=request,
            name="review.html",
            context=_review_context(
                remaining,
                values,
                None,
                return_to=return_to or "/review",
                publish_outcome="already_published",
            ),
            status_code=200,
        )

    if not result.ok:
        return templates.TemplateResponse(
            request=request,
            name="review.html",
            context=_review_context(
                draft,
                values,
                "This record could not be published: " + "; ".join(result.schema_errors),
                return_to=return_to or "/review",
            ),
            status_code=400,
        )

    if next_id:
        return RedirectResponse(url=f"/review/{next_id}", status_code=303)
    return RedirectResponse(url=return_to or f"/evidence/{result.evidence_id}", status_code=303)


@app.post("/review/{draft_id}/approve-atomic")
def review_approve_atomic(
    draft_id: str,
    reviewer: str = Form(""),
    confirm_individual_review: bool = Form(False),
    return_to: str = Form("/review"),
) -> RedirectResponse:
    """Compact approval action that reuses the normal publish transaction."""
    if not AUTHORING_MODE:
        raise HTTPException(status_code=403, detail="Publishing is only available in authoring mode")
    draft = get_draft(draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    if draft.get("evidence_role") != "atomic_evidence" or draft.get("status") == "rejected":
        raise HTTPException(status_code=400, detail="Compact approval is only available for pending atomic Evidence")
    if not reviewer.strip() or not confirm_individual_review:
        raise HTTPException(status_code=400, detail="Reviewer and individual-review confirmation are required")
    priority = draft.get("priority") or {
        dimension: {"level": "none", "rationale": ""} for dimension in PRIORITY_DIMENSIONS
    }
    result = _review_publish_service().publish(
        PublishRequest(
            draft=draft,
            draft_id=draft_id,
            title=(draft.get("summary") or draft.get("title") or "")[:160],
            source_type=draft.get("source_type", ""),
            source_name=draft.get("source_name", ""),
            source_url=draft.get("source_url", ""),
            published_date=draft.get("published_date"),
            captured_date=draft.get("captured_date") or date.today().isoformat(),
            summary=draft.get("summary") or draft.get("title") or "",
            why_it_matters=draft.get("why_it_matters", ""),
            tags=list(draft.get("tags") or []),
            selected_berries=list(draft.get("berry_ids") or []),
            all_entity_names_by_type={},
            facts_input=[],
            relationships_input=[],
            priority=priority,
            strategic_question_text=[],
            reviewer=reviewer.strip(),
            existing_entity_ids=list(dict.fromkeys(draft.get("entity_ids") or [])),
        )
    )
    if not result.ok:
        raise HTTPException(status_code=400, detail="Atomic Evidence could not be published: " + "; ".join(result.schema_errors))
    return RedirectResponse(url=_safe_review_return(return_to), status_code=303)


@app.post("/review/{draft_id}/save", response_model=None)
async def review_save(request: Request, draft_id: str) -> HTMLResponse | RedirectResponse:
    """Persist reviewer edits on the untrusted draft without publishing."""

    if not AUTHORING_MODE:
        raise HTTPException(status_code=403, detail="Saving drafts is only available in authoring mode")
    draft = get_draft(draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    if draft.get("status") == "rejected":
        raise HTTPException(status_code=400, detail="Rejected drafts cannot be edited")
    form = await request.form()

    def field(name: str, default: str = "") -> str:
        value = form.get(name, default)
        return value if isinstance(value, str) else default

    draft["title"] = field("title").strip() or draft.get("title")
    draft["summary"] = field("summary").strip() or draft.get("summary")
    draft["why_it_matters"] = field("why_it_matters").strip()
    draft["tags"] = split_list(field("tags"))
    berries = [value for value in form.getlist("berries") if isinstance(value, str)]
    if berries:
        draft["berry_ids"] = berries
    save_draft(draft)
    return_to = _safe_review_return(field("return_to"), fallback=f"/review/{draft_id}")
    if field("advance").strip() == "next":
        next_id = adjacent_publication_draft_id(draft_id)
        if next_id:
            return RedirectResponse(url=f"/review/{next_id}", status_code=303)
    return RedirectResponse(url=return_to, status_code=303)


@app.post("/review/{draft_id}/reject")
def review_reject(
    draft_id: str,
    reviewer: str = Form(""),
    rejection_reason: str = Form(""),
    rejection_category: str = Form("other"),
    return_to: str = Form("/review"),
    advance: str = Form(""),
) -> RedirectResponse:
    """Record an independent human rejection without publishing Evidence.

    Rejected proposals stay in inbox as audit material but leave the active
    queue. No parent artifact, sibling proposal, Entity, Fact, or trusted
    Evidence record is changed.
    """
    if not AUTHORING_MODE:
        raise HTTPException(status_code=403, detail="Rejecting drafts is only available in authoring mode")
    draft = get_draft(draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    if not reviewer.strip() or not rejection_reason.strip():
        raise HTTPException(status_code=400, detail="Reviewer and rejection reason are required")
    if rejection_category not in REJECTION_CATEGORIES:
        raise HTTPException(status_code=400, detail="Rejection category is invalid")
    if draft.get("review_state") == "rejected" or draft.get("status") == "rejected":
        return RedirectResponse(url=_safe_review_return(return_to), status_code=303)
    repositories = get_repositories(DATA_DIR, SCHEMAS_DIR)
    source = repositories.sources.get(draft.get("source_id")) if draft.get("source_id") else None
    event = append_review_event(
        INBOX_DIR, workflow="publication_review", object_id=draft_id,
        object_type="publication_draft", action="reject",
        prior_state=str(draft.get("review_state") or draft.get("status") or "pending"),
        new_state="rejected", actor=reviewer.strip(), subject=draft, source=source,
        reason_category=rejection_category,
    )
    draft.update(
        {
            "status": "rejected",
            "review_state": "rejected",
            "reviewed_by": reviewer.strip(),
            "reviewed_at": str(event.event["occurred_at"])[:10],
            "rejection_reason": rejection_reason.strip(),
            "rejection_category": rejection_category,
            "review_outcome": {
                "decision": "rejected",
                "edited_before_approval": False,
                "original_normalized_statement": draft.get("summary") or draft.get("title") or "",
            },
        }
    )
    try:
        save_draft(draft)
    except Exception:
        remove_created_event(event)
        raise
    if advance.strip() == "next":
        next_id = adjacent_publication_draft_id(draft_id)
        if next_id:
            return RedirectResponse(url=f"/review/{next_id}", status_code=303)
    return RedirectResponse(url=_safe_review_return(return_to), status_code=303)


@app.get("/api/feed")
def api_feed(
    q: str | None = None,
    berry: str | None = None,
    source: str | None = None,
    priority: str | None = None,
    competitor: str | None = None,
    geography: str | None = None,
    region: str | None = None,
    media_format: str | None = None,
) -> list[dict[str, Any]]:
    return filter_evidence(
        published_evidence(),
        q=q, berry=berry, source=source, priority=priority,
        competitor=competitor, geography=geography, region=region,
        media_format=media_format,
    )


@app.get("/api/entities/{entity_type}/{entity_id}")
def api_entity_detail(entity_type: str, entity_id: str) -> dict[str, Any]:
    for entity in all_entities():
        if entity.get("id") == entity_id and entity.get("entity_type") == entity_type:
            return entity
    raise HTTPException(status_code=404, detail="Entity record not found")


@app.get("/api/search")
def api_search(q: str = "") -> dict[str, Any]:
    needle = q.strip().lower()
    evidence_matches = filter_evidence(published_evidence(), q=needle) if needle else []
    entity_matches = [
        e
        for e in all_entities()
        if needle
        and text_matches(
            needle,
            " ".join([e.get("name", ""), " ".join(e.get("aliases", [])), e.get("description", "")]),
        )
    ]
    return {"evidence": evidence_matches, "entities": entity_matches}


def _search_index_key(*, include_private: bool) -> tuple[Any, ...]:
    parts: list[Any] = [
        include_private,
        _json_folder_sig(DATA_DIR / "evidence"),
        _json_folder_sig(DATA_DIR / "signals"),
        _json_folder_sig(DATA_DIR / "assessments"),
        _path_sig(DATA_DIR / "configuration" / "sources.json"),
        _json_tree_sig(DATA_DIR / "entities"),
        _json_tree_sig(DATA_DIR / "relationships"),
    ]
    if include_private:
        parts.extend(
            [
                _json_folder_sig(INBOX_DIR / "evidence"),
                _json_folder_sig(INBOX_DIR / "signal_candidates"),
            ]
        )
    return tuple(parts)


def _search_pools(*, include_private: bool) -> SearchPools:
    return SearchPools(
        entities=all_entities(),
        relationships=all_relationships(),
        published_evidence=published_evidence(),
        sources=load_sources(),
        signals=all_signals(),
        assessments=all_assessments(),
        pending_drafts=list_pending_drafts() if include_private else [],
        signal_candidates=load_candidates(INBOX_DIR) if include_private else [],
    )


def _cached_search_documents(*, include_private: bool):
    key = _search_index_key(include_private=include_private)
    if _SEARCH_DOC_CACHE["key"] != key or _SEARCH_DOC_CACHE["docs"] is None:
        _SEARCH_DOC_CACHE["key"] = key
        _SEARCH_DOC_CACHE["docs"] = build_search_documents(
            _search_pools(include_private=include_private),
            include_private=include_private,
        )
    return _SEARCH_DOC_CACHE["docs"]


def run_global_search(
    query: str,
    *,
    berry: str = "global",
    include_private: bool = False,
    include_global: bool = True,
    limit_per_group: int = GROUP_CAP_DEFAULT,
) -> dict[str, Any]:
    started = time.perf_counter()
    payload = search_global(
        query,
        _search_pools(include_private=include_private),
        berry=berry,
        include_private=include_private,
        include_global=include_global,
        limit_per_group=limit_per_group,
        documents=_cached_search_documents(include_private=include_private),
    )
    payload["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 2)
    return payload


@app.get("/search", response_class=HTMLResponse)
def global_search_page(
    request: Request,
    q: str = "",
    berry: str | None = None,
    include_global: str | None = None,
) -> HTMLResponse:
    ui = read_ui_context(request, BERRIES, inbox_dir=INBOX_DIR)
    berry_id = parse_berry(berry or ui.get("berry"), BERRIES)
    broaden = str(include_global or "1").strip() not in {"0", "false", "no"}
    results = run_global_search(
        q,
        berry=berry_id,
        include_private=True,
        include_global=broaden,
        limit_per_group=25,
    )
    return templates.TemplateResponse(
        request=request,
        name="search.html",
        context={
            "search_query": q,
            "search_results": results,
            "search_berry": berry_id,
            "search_include_global": broaden,
            "authoring_mode": AUTHORING_MODE,
        },
    )


@app.get("/api/search/global")
def api_global_search(
    request: Request,
    q: str = "",
    berry: str = "",
    include_global: str = "1",
    include_private: str = "1",
    limit: int = GROUP_CAP_DEFAULT,
) -> dict[str, Any]:
    ui = read_ui_context(request, BERRIES, inbox_dir=INBOX_DIR)
    berry_id = parse_berry(berry or ui.get("berry"), BERRIES)
    private = str(include_private).strip() not in {"0", "false", "no"}
    broaden = str(include_global).strip() not in {"0", "false", "no"}
    cap = max(1, min(int(limit or GROUP_CAP_DEFAULT), 25))
    return run_global_search(
        q,
        berry=berry_id,
        include_private=private,
        include_global=broaden,
        limit_per_group=cap,
    )
