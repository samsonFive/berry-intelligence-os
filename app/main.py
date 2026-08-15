from __future__ import annotations

import asyncio
import difflib
import json
import os
import re
import secrets
import shutil
import sys
from collections import Counter, defaultdict
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

import feedparser
import httpx
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from jsonschema import Draft202012Validator, FormatChecker

from app.composition import get_domain_services, get_query_services, get_repositories, get_unit_of_work
from app.queries.timeline import entity_activity, max_priority_level
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
from app.services.review_publish import PublishRequest, ReviewPublishService

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
INBOX_DIR = BASE_DIR / "inbox"
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
SOURCE_CADENCE_DAYS = {
    "realtime": 1,
    "weekly": 7,
    "biweekly": 14,
    "monthly": 30,
    "quarterly": 90,
    "annual": 365,
    # event_driven has no fixed schedule -- never "due", only checked manually.
}


@asynccontextmanager
async def lifespan(app: FastAPI):
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
app.mount("/static", StaticFiles(directory=BASE_DIR / "app" / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "app" / "templates")
templates.env.globals["pending_review_count"] = lambda: len(list_drafts()) + len(unvalidated_auto_captured_evidence())
templates.env.globals["queue_counts"] = lambda: queue_counts()


_JSON_FOLDER_CACHE: dict[Path, tuple[tuple[tuple[str, int], ...], list[dict[str, Any]]]] = {}


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
    is picked up on the very next call. No dirty flag to forget to set."""
    if not folder.exists():
        return []
    paths = sorted(folder.rglob("*.json"))
    signature = tuple((str(p), p.stat().st_mtime_ns) for p in paths)
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
                    str(attrs.get("patent_number", "")),
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


def get_draft(draft_id: str) -> dict[str, Any] | None:
    path = INBOX_DIR / "evidence" / f"{draft_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


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
    entities = entities if entities is not None else entity_index()
    matchers: list[tuple[str, "re.Pattern[str]"]] = []
    for entity in entities.values():
        if entity.get("entity_type") != entity_type:
            continue
        for name in [entity.get("name", "")] + list(entity.get("aliases") or []):
            name = name.strip()
            if len(name) < 4:
                continue
            matchers.append((entity["id"], re.compile(r"\b" + re.escape(name) + r"\b", re.IGNORECASE)))
    return matchers


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
    matched_geo = {eid for eid, pattern in geo_matchers if pattern.search(haystack)}
    matched_ent = {eid for eid, pattern in company_matchers if pattern.search(haystack)}

    if matched_geo:
        record["geography_ids"] = sorted(set(record.get("geography_ids") or []) | matched_geo)
    if matched_ent:
        record["entity_ids"] = sorted(set(record.get("entity_ids") or []) | matched_ent)
    if matched_geo or matched_ent:
        record["auto_tagged"] = True
    return record


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
) -> HTMLResponse:
    all_of_type = sorted(
        (e for e in all_entities() if e.get("entity_type") == entity_type),
        key=lambda e: e.get("name", ""),
    )
    if not all_of_type:
        raise HTTPException(status_code=404, detail=f"No entities found for type '{entity_type}'")

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
    return templates.TemplateResponse(
        request=request,
        name="entity_list.html",
        context={
            "entities": filtered,
            "total_count": len(all_of_type),
            "entity_type": entity_type,
            "berries": BERRIES,
            "regions": REGIONS,
            "companies": companies,
            "filters": {"q": q or "", "berry": berry or "", "region": region or "", "company": company or ""},
            "authoring_mode": AUTHORING_MODE,
        },
    )


def entity_synthesis_context(entity: dict[str, Any], entities: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """The generic, entity-type-agnostic synthesis fields added in Phase
    1.5B (BL-027/BL-028): intelligence objects touching this entity, its
    relationships to other entities as directed/evidenced edges, and the
    Strategic Questions it bears on. Shared by the live entity_detail()
    route and scripts/build_static.py so both stay in sync by construction."""
    entity_id = entity["id"]
    linked_evidence = [r for r in published_evidence() if entity_id in (r.get("entity_ids") or [])]
    entity_signals = signals_for_entity(entity_id)
    entity_assessments = assessments_for_entity(entity_id)
    entity_recommendations = recommendations_for_entity(entity_id)
    context: dict[str, Any] = {
        "entity_signals": entity_signals,
        "entity_assessments": entity_assessments,
        "entity_recommendations": entity_recommendations,
        "entity_strategic_questions": strategic_questions_for_entity(
            entity_id, linked_evidence, entity_signals, entity_assessments, entity_recommendations
        ),
        "grouped_relationships": grouped_relationships_for_entity(entity_id, all_relationships(), entities),
    }
    if entity.get("entity_type") == "variety":
        all_patents = [e for e in entities.values() if e.get("entity_type") == "patent"]
        breeding_program_id = (entity.get("attributes") or {}).get("breeding_program_id")
        context["variety_trait_profile"] = variety_trait_profile(entity, entities)
        context["variety_patent_link"] = variety_patent_link(entity, all_patents)
        context["variety_breeding_program"] = entities.get(breeding_program_id) if breeding_program_id else None
    return context


@app.get("/entities/{entity_type}/{entity_id}", response_class=HTMLResponse)
def entity_detail(request: Request, entity_type: str, entity_id: str) -> HTMLResponse:
    for entity in all_entities():
        if entity.get("id") == entity_id and entity.get("entity_type") == entity_type:
            linked_evidence = [
                r for r in published_evidence() if entity_id in (r.get("entity_ids") or [])
            ]
            independent_sources = {r.get("source_name") for r in linked_evidence if r.get("source_name")}
            last_updated = linked_evidence[0].get("published_date") or linked_evidence[0].get("captured_date") if linked_evidence else None
            entities = entity_index()
            regions = sorted(entity_regions(entity, entities, linked_evidence))
            entity_facts = facts_for_entity(entity_id)
            entity_relationships = relationships_for_entity(entity_id, all_relationships())
            evidence_idx = {r["id"]: r for r in all_evidence() if r.get("id")}
            activity = entity_activity(linked_evidence, entity_facts, entity_relationships, entities, evidence_idx)
            return templates.TemplateResponse(
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
                    **entity_synthesis_context(entity, entities),
                },
            )
    raise HTTPException(status_code=404, detail="Entity record not found")


@app.get("/work-queue", response_class=HTMLResponse)
def work_queue(request: Request) -> HTMLResponse:
    evidence = published_evidence()
    high_priority = [
        r for r in evidence if any(v.get("level") == "high" for v in (r.get("priority") or {}).values())
    ]
    return templates.TemplateResponse(
        request=request,
        name="work_queue.html",
        context={
            "recent_evidence": evidence[:5],
            "drafts": list_drafts(),
            "unresolved_entities": unresolved_entities(),
            "high_priority": high_priority[:5],
            "recent_signals": all_signals()[:5],
            "queue_summary": queue_counts(),
            "authoring_mode": AUTHORING_MODE,
        },
    )


PRIORITY_QUEUE_LABELS = {
    "reading": "Reading Queue",
    "testing": "Testing Queue",
    "commercial_position": "Commercial Position Queue",
    "monitoring": "Monitoring Queue",
}


@app.get("/queues/{dimension}", response_class=HTMLResponse)
def priority_queue(request: Request, dimension: str, region: str | None = None) -> HTMLResponse:
    if dimension not in PRIORITY_DIMENSIONS:
        raise HTTPException(status_code=404, detail="Unknown priority dimension")
    entities = entity_index()
    all_items = queue_items(dimension)
    if region:
        all_items = [r for r in all_items if region in evidence_regions(r, entities)]
    items = []
    for record in all_items:
        linked = [entities[e]["name"] for e in record.get("entity_ids", []) if e in entities]
        items.append({**record, "linked_entity_names": linked})
    return templates.TemplateResponse(
        request=request,
        name="queue.html",
        context={
            "dimension": dimension,
            "label": PRIORITY_QUEUE_LABELS[dimension],
            "items": items,
            "berry_label": berry_label,
            "regions": REGIONS,
            "filters": {"region": region or ""},
            "authoring_mode": AUTHORING_MODE,
        },
    )


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


@app.get("/landscapes/berries/blueberry", response_class=HTMLResponse)
def landscape_blueberry(
    request: Request, region: str = "global", intelligence_state: str = "all"
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="landscape.html",
        context={
            **landscape_context("berry-blueberry", region, intelligence_state),
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
        },
    )


@app.get("/assessments", response_class=HTMLResponse)
def assessment_list(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="assessment_list.html",
        context={"assessments": all_assessments(), "authoring_mode": AUTHORING_MODE},
    )


def _default_assessment_values() -> dict[str, Any]:
    return {
        "title": "",
        "rationale": "",
        "status": "active",
        "confidence": "medium",
        "fact_ids": "",
        "evidence_ids": "",
        "entity_ids": "",
        "strategic_question_ids": "",
        "counterevidence_ids": "",
        "reviewer": "",
    }


@app.get("/assessments/new", response_class=HTMLResponse)
def assessment_new(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="assessment_form.html",
        context={
            "values": _default_assessment_values(),
            "statuses": INTELLIGENCE_RECORD_STATUSES,
            "confidence_levels": FACT_CONFIDENCE_LEVELS,
            "error": None,
            "authoring_mode": AUTHORING_MODE,
        },
    )


@app.post("/assessments", response_model=None)
def assessment_create(
    request: Request,
    title: str = Form(""),
    rationale: str = Form(""),
    status: str = Form("active"),
    confidence: str = Form(""),
    fact_ids: str = Form(""),
    evidence_ids: str = Form(""),
    entity_ids: str = Form(""),
    strategic_question_ids: str = Form(""),
    counterevidence_ids: str = Form(""),
    reviewer: str = Form(""),
) -> HTMLResponse | RedirectResponse:
    if not AUTHORING_MODE:
        raise HTTPException(status_code=403, detail="Creating assessments is only available in authoring mode")

    values = {
        "title": title,
        "rationale": rationale,
        "status": status or "active",
        "confidence": confidence or "medium",
        "fact_ids": fact_ids,
        "evidence_ids": evidence_ids,
        "entity_ids": entity_ids,
        "strategic_question_ids": strategic_question_ids,
        "counterevidence_ids": counterevidence_ids,
        "reviewer": reviewer,
    }

    fact_id_list = split_list(fact_ids)
    evidence_id_list = split_list(evidence_ids)
    entity_id_list = split_list(entity_ids)
    counterevidence_id_list = split_list(counterevidence_ids)

    known_facts = {f["id"] for f in all_facts()}
    published_ids = {r["id"] for r in published_evidence()}
    entity_ids_known = set(entity_index().keys())

    errors: list[str] = []
    if not title.strip():
        errors.append("Title is required.")
    if not rationale.strip():
        errors.append("Rationale is required.")
    if not reviewer.strip():
        errors.append("Reviewer is required.")
    if not fact_id_list:
        errors.append("At least one supporting fact id is required.")
    unknown_facts = [f for f in fact_id_list if f not in known_facts]
    if unknown_facts:
        errors.append(f"Unknown fact id(s): {', '.join(unknown_facts)}.")
    unknown_evidence = [e for e in evidence_id_list if e not in published_ids]
    if unknown_evidence:
        errors.append(f"Unknown published evidence id(s): {', '.join(unknown_evidence)}.")
    unknown_entities = [e for e in entity_id_list if e not in entity_ids_known]
    if unknown_entities:
        errors.append(f"Unknown entity id(s): {', '.join(unknown_entities)}.")
    unknown_counterevidence = [e for e in counterevidence_id_list if e not in known_facts and e not in published_ids]
    if unknown_counterevidence:
        errors.append(f"Unknown counterevidence id(s): {', '.join(unknown_counterevidence)}.")

    if errors:
        return templates.TemplateResponse(
            request=request,
            name="assessment_form.html",
            context={
                "values": values,
                "statuses": INTELLIGENCE_RECORD_STATUSES,
                "confidence_levels": FACT_CONFIDENCE_LEVELS,
                "error": " ".join(errors),
                "authoring_mode": AUTHORING_MODE,
            },
            status_code=400,
        )

    assessment_id = new_assessment_id(title)
    record = {
        "id": assessment_id,
        "record_type": "assessment",
        "title": title.strip(),
        "rationale": rationale.strip(),
        "status": values["status"],
        "confidence": values["confidence"],
        "fact_ids": fact_id_list,
        "evidence_ids": evidence_id_list,
        "entity_ids": entity_id_list,
        "strategic_question_ids": resolve_strategic_question_ids(strategic_question_ids),
        "counterevidence_ids": counterevidence_id_list,
        "reviewer": reviewer.strip(),
        "created_at": date.today().isoformat(),
    }

    schema_errors = [e.message for e in get_validator("assessment.schema.json").iter_errors(record)]
    if schema_errors:
        return templates.TemplateResponse(
            request=request,
            name="assessment_form.html",
            context={
                "values": values,
                "statuses": INTELLIGENCE_RECORD_STATUSES,
                "confidence_levels": FACT_CONFIDENCE_LEVELS,
                "error": "This assessment could not be saved: " + "; ".join(schema_errors),
                "authoring_mode": AUTHORING_MODE,
            },
            status_code=400,
        )

    save_assessment(record)
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
            "linked_facts": lineage.resolve_linked_facts(assessment.get("fact_ids")),
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
    return {
        "sources": filtered,
        "total_count": len(all_sources),
        "grouped_sources": group_sources(filtered, group_by),
        "gaps_count": len([s for s in all_sources if source_has_coverage_gap(s)]),
        "due_count": len([s for s in all_sources if source_is_due(s)]),
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


@app.get("/review", response_class=HTMLResponse)
def review_queue(request: Request) -> HTMLResponse:
    entities = entity_index()
    return templates.TemplateResponse(
        request=request,
        name="review_queue.html",
        context={
            "drafts": list_drafts(),
            "unvalidated_evidence": unvalidated_auto_captured_evidence(),
            "entities": entities,
            "authoring_mode": AUTHORING_MODE,
        },
    )


def _default_review_values(draft: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": draft.get("title", ""),
        "source_type": draft.get("source_type", ""),
        "source_name": draft.get("source_name", ""),
        "source_url": draft.get("source_url", ""),
        "published_date": draft.get("published_date") or "",
        "captured_date": draft.get("captured_date", ""),
        "summary": draft.get("summary", ""),
        "why_it_matters": draft.get("why_it_matters", ""),
        "tags": "",
        "companies": ", ".join(draft.get("suggested_competitors", [])),
        "varieties": ", ".join(draft.get("suggested_varieties", [])),
        "retailers": "",
        "geographies": "",
        "berries": [],
        "strategic_questions": "",
        "reviewer": "",
        "facts": [{"statement": "", "classification": "fact", "confidence": "medium"} for _ in range(NUM_FACT_ROWS)],
        "relationships": [
            {"subject": "", "predicate": RELATIONSHIP_PREDICATES[0], "object": "", "effective_date": ""}
            for _ in range(NUM_RELATIONSHIP_ROWS)
        ],
        "priority": {dim: {"level": "none", "rationale": ""} for dim in PRIORITY_DIMENSIONS},
    }


def _review_context(draft: dict[str, Any], values: dict[str, Any], error: str | None) -> dict[str, Any]:
    return {
        "draft": draft,
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
    }


@app.get("/review/{draft_id}", response_class=HTMLResponse)
def review_form(request: Request, draft_id: str) -> HTMLResponse:
    draft = get_draft(draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    return templates.TemplateResponse(
        request=request,
        name="review.html",
        context=_review_context(draft, _default_review_values(draft), None),
    )


@app.post("/review/{draft_id}/publish", response_model=None)
async def review_publish(request: Request, draft_id: str) -> HTMLResponse | RedirectResponse:
    if not AUTHORING_MODE:
        raise HTTPException(status_code=403, detail="Publishing is only available in authoring mode")

    draft = get_draft(draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")

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
    selected_berries = [b for b in form.getlist("berries") if isinstance(b, str)]

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
            context=_review_context(draft, values, " ".join(errors)),
            status_code=400,
        )

    # Persistence orchestration (entity match/create/update, Facts,
    # Relationships, Evidence, the transactional boundary, and the
    # Draft-success handoff) lives in ReviewPublishService, not here -- see
    # app/services/review_publish.py. This route stays limited to HTTP
    # concerns: parsing the form (above) and turning the service's result
    # into a response (below).
    service = ReviewPublishService(
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
    )
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
        )
    )

    if not result.ok:
        return templates.TemplateResponse(
            request=request,
            name="review.html",
            context=_review_context(
                draft, values, "This record could not be published: " + "; ".join(result.schema_errors)
            ),
            status_code=400,
        )

    return RedirectResponse(url=f"/evidence/{result.evidence_id}", status_code=303)


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
