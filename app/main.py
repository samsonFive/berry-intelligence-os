from __future__ import annotations

import asyncio
import json
import os
import re
import secrets
import shutil
import sys
from contextlib import asynccontextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import feedparser
import httpx
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from jsonschema import Draft202012Validator, FormatChecker

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
INBOX_DIR = BASE_DIR / "inbox"
SCHEMAS_DIR = BASE_DIR / "schemas"

# Authoring mode permits local writes (intake, review, publish). A future
# read-only / static deployment sets BIOS_MODE=readonly so write endpoints
# are unavailable.
AUTHORING_MODE = os.environ.get("BIOS_MODE", "authoring") == "authoring"

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

SOURCE_TYPES = {"rss": "RSS / Atom feed", "keyword": "Keyword search"}
SOURCE_POLL_INTERVAL_SECONDS = 15 * 60
SOURCE_FETCH_TIMEOUT_SECONDS = 15
SOURCE_USER_AGENT = "berry-intelligence-os-source-monitor/1.0"
SOURCE_MAX_NEW_ITEMS_PER_CHECK = 20


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Never poll external sources during tests -- pytest importing this
    # module must not trigger real network calls. Real deployments always
    # have "pytest" absent from sys.modules.
    task = None
    if "pytest" not in sys.modules and AUTHORING_MODE:
        task = asyncio.create_task(source_polling_loop())
    yield
    if task is not None:
        task.cancel()


app = FastAPI(title="Berry Intelligence OS", version="0.1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE_DIR / "app" / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "app" / "templates")
templates.env.globals["pending_review_count"] = lambda: len(list_drafts())
templates.env.globals["queue_counts"] = lambda: queue_counts()


def load_json_files(folder: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not folder.exists():
        return records
    for path in sorted(folder.rglob("*.json")):
        with path.open("r", encoding="utf-8") as handle:
            records.append(json.load(handle))
    return records


def all_evidence() -> list[dict[str, Any]]:
    return load_json_files(DATA_DIR / "evidence")


def published_evidence() -> list[dict[str, Any]]:
    records = [r for r in all_evidence() if r.get("status") == "published"]
    return sorted(records, key=lambda r: r.get("published_date") or r.get("captured_date", ""), reverse=True)


def all_entities() -> list[dict[str, Any]]:
    return load_json_files(DATA_DIR / "entities")


def entity_index() -> dict[str, dict[str, Any]]:
    return {entity["id"]: entity for entity in all_entities() if entity.get("id")}


def berry_label(berry_id: str) -> str:
    return berry_id.removeprefix("berry-").replace("_", " ").replace("-", " ").title()


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


templates.env.filters["us_date"] = us_date


REGIONS = ["Americas", "Europe", "Oceania", "Middle East & Africa"]

# Default region assignment by geography name. Deliberately not exhaustive --
# anything not listed here (e.g. China, present in real imported data) has no
# default region rather than being guessed into the wrong bucket. Always
# overridable per-geography via attributes.region (see geography_region()).
REGION_LOOKUP = {
    "united states": "Americas", "canada": "Americas", "mexico": "Americas",
    "peru": "Americas", "chile": "Americas", "colombia": "Americas",
    "brazil": "Americas", "argentina": "Americas", "uruguay": "Americas",
    "north america": "Americas", "south america": "Americas",
    "europe": "Europe", "spain": "Europe", "portugal": "Europe",
    "germany": "Europe", "netherlands": "Europe", "france": "Europe",
    "poland": "Europe", "italy": "Europe", "united kingdom": "Europe", "uk": "Europe",
    "australia": "Oceania", "new zealand": "Oceania", "oceania": "Oceania",
    "morocco": "Middle East & Africa", "south africa": "Middle East & Africa",
    "zambia": "Middle East & Africa", "zimbabwe": "Middle East & Africa",
    "egypt": "Middle East & Africa", "kenya": "Middle East & Africa",
    "nigeria": "Middle East & Africa", "israel": "Middle East & Africa",
    "saudi arabia": "Middle East & Africa", "uae": "Middle East & Africa",
    "united arab emirates": "Middle East & Africa",
}


def geography_region(geography_entity: dict[str, Any]) -> str | None:
    """A geography's region: an explicit attributes.filter_region override
    always wins (so a wrong or missing default is one edit away to fix),
    otherwise the fixed lookup table by name.

    Deliberately namespaced as "filter_region", not "region": real imported
    geography entities already carry their own attributes.region using a
    different taxonomy (e.g. "Asia-Pacific", "Latin America") for their own
    purposes. Reusing that key silently adopted their values as if they were
    corrections to this app's four-bucket scheme, which they were never
    intended to be -- found by checking Australia's derived region live and
    getting "Asia-Pacific" back instead of "Oceania"."""
    override = (geography_entity.get("attributes") or {}).get("filter_region")
    if override:
        return override
    return REGION_LOOKUP.get(geography_entity.get("name", "").strip().lower())


def evidence_regions(record: dict[str, Any], entities: dict[str, dict[str, Any]]) -> set[str]:
    """A geography can be associated with evidence two ways: the dedicated
    geography_ids array, or just as one of the general entity_ids -- real
    imported data (predating the geography_ids field) only ever does the
    latter, so both are checked rather than trusting one convention."""
    geo_ids = set(record.get("geography_ids") or [])
    for eid in record.get("entity_ids") or []:
        entity = entities.get(eid)
        if entity and entity.get("entity_type") == "geography":
            geo_ids.add(eid)
    regions = set()
    for gid in geo_ids:
        geo = entities.get(gid)
        if geo:
            region = geography_region(geo)
            if region:
                regions.add(region)
    return regions


def entity_regions(
    entity: dict[str, Any],
    entities: dict[str, dict[str, Any]],
    evidence: list[dict[str, Any]],
) -> set[str]:
    """Which regions an entity touches. A geography entity has its own
    region. Any other entity's regions are derived, not stored: the union of
    regions from every geography linked (via geography_ids) to evidence that
    also links this entity -- so a variety grown/tested/reported on across
    three continents shows all three automatically, with no extra field to
    keep in sync."""
    if entity.get("entity_type") == "geography":
        region = geography_region(entity)
        return {region} if region else set()
    regions: set[str] = set()
    for record in evidence:
        if entity.get("id") in (record.get("entity_ids") or []):
            regions |= evidence_regions(record, entities)
    return regions


def related_entity_ids(entity_id: str, relationships: list[dict[str, Any]]) -> set[str]:
    related: set[str] = set()
    for rel in relationships:
        if rel.get("subject_id") == entity_id and rel.get("object_id"):
            related.add(rel["object_id"])
        elif rel.get("object_id") == entity_id and rel.get("subject_id"):
            related.add(rel["subject_id"])
    return related


def filter_evidence(
    records: list[dict[str, Any]],
    q: str | None = None,
    berry: str | None = None,
    source: str | None = None,
    priority: str | None = None,
    competitor: str | None = None,
    geography: str | None = None,
    region: str | None = None,
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
                ).lower()
                return needle in haystack

            results = [r for r in results if matches_text(r)]

    if berry:
        results = [r for r in results if berry in (r.get("berry_ids") or [])]

    if source:
        results = [r for r in results if r.get("source_type") == source]

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
            ).lower()
            return needle in haystack

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
    return load_json_files(DATA_DIR / "facts")


def all_relationships() -> list[dict[str, Any]]:
    return load_json_files(DATA_DIR / "relationships")


def facts_for_evidence(evidence_id: str) -> list[dict[str, Any]]:
    return [f for f in all_facts() if evidence_id in (f.get("evidence_ids") or [])]


def relationships_for_evidence(evidence_id: str) -> list[dict[str, Any]]:
    return [r for r in all_relationships() if evidence_id in (r.get("evidence_ids") or [])]


def facts_for_entity(entity_id: str) -> list[dict[str, Any]]:
    return [f for f in all_facts() if entity_id in (f.get("entity_ids") or [])]


def relationships_for_entity(entity_id: str, relationships: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in relationships if entity_id in (r.get("subject_id"), r.get("object_id"))]


def max_priority_level(record: dict[str, Any]) -> str:
    levels_present = {v.get("level") for v in (record.get("priority") or {}).values()}
    for level in ("high", "medium", "low"):
        if level in levels_present:
            return level
    return "none"


def entity_activity(
    linked_evidence: list[dict[str, Any]],
    entity_facts: list[dict[str, Any]],
    entity_relationships: list[dict[str, Any]],
    entities: dict[str, dict[str, Any]],
    evidence_idx: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """A single chronological feed for one entity, merging evidence, facts,
    and relationships -- the "what's new with company X" view the original
    approved mockup showed (assets/platform-visual-language.png, panel 4)
    but was never actually built.

    Only items with a genuine date make the cut. Roughly half of imported
    evidence (mostly reference material -- company/registry/catalog pages,
    patent records) has no real published_date, only a captured_date marking
    when it was pulled into the system. Falling back to captured_date would
    make evergreen reference pages look like breaking news at the top of the
    feed, defeating the entire point of a "what's new" view. Undated items
    are simply excluded here; they remain visible in the Linked Evidence /
    Facts sections below, just not misrepresented as recent activity.

    Facts use event_date (the real-world date the underlying development
    happened, backfilled from evidence text) when available, falling back to
    created_at (when the fact was authored) since that's still a real date --
    just not necessarily *the* newsworthy one."""
    items: list[dict[str, Any]] = []

    for record in linked_evidence:
        date = record.get("published_date")
        if not date:
            continue
        items.append(
            {
                "date": date,
                "type": "evidence",
                "type_label": record.get("source_type", "evidence").replace("_", " ").title(),
                "title": record.get("title", ""),
                "detail": record.get("summary", ""),
                "url": f"/evidence/{record['id']}",
                "priority": max_priority_level(record),
            }
        )

    for fact in entity_facts:
        evidence_id = (fact.get("evidence_ids") or [None])[0]
        evidence = evidence_idx.get(evidence_id) if evidence_id else None
        fallback_date = evidence.get("published_date") if evidence else None
        date = fact.get("event_date") or fact.get("created_at") or fallback_date
        if not date:
            continue
        detail = f"{fact.get('confidence', '')} confidence"
        if fact.get("status") and fact.get("status") != "active":
            detail += f" · {fact['status']}"
        items.append(
            {
                "date": date,
                "type": "fact",
                "type_label": (fact.get("classification") or "fact").title(),
                "title": fact.get("statement", ""),
                "detail": detail,
                "url": f"/evidence/{evidence_id}" if evidence_id else "",
                "priority": None,
            }
        )

    for rel in entity_relationships:
        evidence_id = (rel.get("evidence_ids") or [None])[0]
        evidence = evidence_idx.get(evidence_id) if evidence_id else None
        fallback_date = evidence.get("published_date") if evidence else None
        date = rel.get("effective_date") or fallback_date
        if not date:
            continue
        subject_name = entities.get(rel.get("subject_id"), {}).get("name", rel.get("subject_id"))
        object_name = entities.get(rel.get("object_id"), {}).get("name", rel.get("object_id"))
        predicate = (rel.get("predicate") or "").replace("_", " ")
        items.append(
            {
                "date": date,
                "type": "relationship",
                "type_label": predicate.title(),
                "title": f"{subject_name} {predicate} {object_name}",
                "detail": rel.get("notes", ""),
                "url": f"/evidence/{evidence_id}" if evidence_id else "",
                "priority": None,
            }
        )

    items.sort(key=lambda item: item["date"], reverse=True)
    return items


def load_strategic_questions() -> list[dict[str, Any]]:
    return load_json_files(DATA_DIR / "strategic-questions")


def strategic_question_by_id(sq_id: str) -> dict[str, Any] | None:
    for sq in load_strategic_questions():
        if sq.get("id") == sq_id:
            return sq
    return None


def evidence_for_strategic_question(sq_id: str) -> list[dict[str, Any]]:
    return [r for r in published_evidence() if sq_id in (r.get("strategic_question_ids") or [])]


def all_signals() -> list[dict[str, Any]]:
    records = load_json_files(DATA_DIR / "signals")
    return sorted(records, key=lambda r: r.get("last_updated", ""), reverse=True)


def signal_by_id(signal_id: str) -> dict[str, Any] | None:
    for signal in all_signals():
        if signal.get("id") == signal_id:
            return signal
    return None


def save_signal(record: dict[str, Any]) -> None:
    folder = DATA_DIR / "signals"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{record['id']}.json"
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def new_signal_id(title: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    suffix = secrets.token_hex(2)
    slug = slugify(title)[:40] or "signal"
    return f"signal-{stamp}-{suffix}-{slug}"


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
    path = sources_file()
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def save_sources(sources: list[dict[str, Any]]) -> None:
    path = sources_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sources, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def new_source_id(label: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    suffix = secrets.token_hex(2)
    slug = slugify(label)[:40] or "source"
    return f"source-{stamp}-{suffix}-{slug}"


def google_news_rss_url(term: str) -> str:
    return f"https://news.google.com/rss/search?q={quote(term)}&hl=en-US&gl=US&ceid=US:en"


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
    return {
        "id": evidence_id,
        "record_type": "evidence",
        "status": "published",
        "source_type": "rss_feed" if source.get("type") == "rss" else "news_search",
        "title": title,
        "source_name": source.get("label", ""),
        "source_url": getattr(entry, "link", "") or "",
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


def check_source(source: dict[str, Any], seen_urls: set[str]) -> int:
    """Fetch one source, write genuinely new evidence (capped per check), return count written.

    A broad first-time source (especially a keyword search) can match dozens
    of historical items at once; writing all of them in one pass would flood
    the feed. Anything past the cap is simply left unwritten and picked up
    on a later check, since it's still "new" until it's actually written.
    """
    entries = fetch_source_entries(source)
    written = 0
    for entry in entries:
        if written >= SOURCE_MAX_NEW_ITEMS_PER_CHECK:
            break
        link = getattr(entry, "link", "") or ""
        if not link or link in seen_urls:
            continue
        record = build_auto_evidence(entry, source)
        save_evidence(record)
        seen_urls.add(link)
        written += 1
    return written


def check_all_sources() -> dict[str, Any]:
    sources = load_sources()
    seen_urls = existing_evidence_source_urls()
    total_written = 0
    for source in sources:
        if not source.get("enabled", True):
            continue
        source["last_checked_at"] = datetime.now().isoformat(timespec="seconds")
        try:
            written = check_source(source, seen_urls)
            source["last_status"] = f"ok: {written} new item(s)" if written else "ok: no new items"
            total_written += written
        except Exception as exc:                       # noqa: BLE001
            source["last_status"] = f"error: {exc}"
    save_sources(sources)
    return {"sources_checked": len(sources), "items_written": total_written}


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
    folder = DATA_DIR / "entities" / entity_folder(record["entity_type"])
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{record['id']}.json"
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def save_fact(record: dict[str, Any]) -> None:
    folder = DATA_DIR / "facts"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{record['id']}.json"
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def save_relationship(record: dict[str, Any]) -> None:
    folder = DATA_DIR / "relationships"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{record['id']}.json"
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def save_evidence(record: dict[str, Any]) -> None:
    folder = DATA_DIR / "evidence"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{record['id']}.json"
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


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
) -> HTMLResponse:
    evidence = published_evidence()
    entities = entity_index()
    options = filter_options(evidence, entities)
    filtered = filter_evidence(
        evidence,
        q=q, berry=berry, source=source, priority=priority,
        competitor=competitor, geography=geography, region=region, entities=entities,
    )
    return templates.TemplateResponse(
        request=request,
        name="feed.html",
        context={
            "evidence": filtered,
            "total_count": len(evidence),
            "berry_label": berry_label,
            "options": options,
            "filters": {
                "q": q or "",
                "berry": berry or "",
                "source": source or "",
                "priority": priority or "",
                "competitor": competitor or "",
                "geography": geography or "",
                "region": region or "",
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


@app.post("/evidence/{record_id}/validate")
def evidence_validate(record_id: str) -> RedirectResponse:
    if not AUTHORING_MODE:
        raise HTTPException(status_code=403, detail="Validating evidence is only available in authoring mode")
    path = DATA_DIR / "evidence" / f"{record_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Evidence record not found")
    record = json.loads(path.read_text(encoding="utf-8"))
    record["validated"] = True
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return RedirectResponse(url=f"/evidence/{record_id}", status_code=303)


@app.post("/evidence/{record_id}/purge")
def evidence_purge(record_id: str) -> RedirectResponse:
    if not AUTHORING_MODE:
        raise HTTPException(status_code=403, detail="Purging evidence is only available in authoring mode")
    path = DATA_DIR / "evidence" / f"{record_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Evidence record not found")
    record = json.loads(path.read_text(encoding="utf-8"))
    if not record.get("auto_captured"):
        raise HTTPException(status_code=400, detail="Purge is only available for auto-captured evidence")
    path.unlink()
    return RedirectResponse(url="/", status_code=303)


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
    return templates.TemplateResponse(
        request=request,
        name="signal_detail.html",
        context={
            "signal": signal,
            "linked_evidence": [r for r in published_evidence() if r["id"] in (signal.get("evidence_ids") or [])],
            "linked_facts": [f for f in all_facts() if f["id"] in (signal.get("fact_ids") or [])],
            "linked_entities": [entities[e] for e in (signal.get("entity_ids") or []) if e in entities],
            "authoring_mode": AUTHORING_MODE,
        },
    )


@app.get("/sources", response_class=HTMLResponse)
def sources_list(request: Request, error: str | None = None) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="sources.html",
        context={
            "sources": load_sources(),
            "source_types": SOURCE_TYPES,
            "poll_interval_minutes": SOURCE_POLL_INTERVAL_SECONDS // 60,
            "error": error,
            "authoring_mode": AUTHORING_MODE,
        },
    )


@app.post("/sources", response_model=None)
def sources_add(
    request: Request,
    type: str = Form(...),
    label: str = Form(""),
    value: str = Form(""),
) -> HTMLResponse | RedirectResponse:
    if not AUTHORING_MODE:
        raise HTTPException(status_code=403, detail="Adding sources is only available in authoring mode")
    if type not in SOURCE_TYPES or not label.strip() or not value.strip():
        return templates.TemplateResponse(
            request=request,
            name="sources.html",
            context={
                "sources": load_sources(),
                "source_types": SOURCE_TYPES,
                "poll_interval_minutes": SOURCE_POLL_INTERVAL_SECONDS // 60,
                "error": "Type, label, and value (feed URL or search term) are all required.",
                "authoring_mode": AUTHORING_MODE,
            },
            status_code=400,
        )
    sources = load_sources()
    sources.append(
        {
            "id": new_source_id(label),
            "type": type,
            "label": label.strip(),
            "value": value.strip(),
            "berry_ids": [],
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
    return templates.TemplateResponse(
        request=request,
        name="review_queue.html",
        context={"drafts": list_drafts(), "authoring_mode": AUTHORING_MODE},
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

    # --- entity match-or-create ---
    idx = entity_index()
    by_name_type = {(e.get("name", "").strip().lower(), e.get("entity_type")): e for e in idx.values()}
    existing_ids = set(idx.keys())
    entity_ids: list[str] = []
    entities_to_save: list[dict[str, Any]] = []
    name_to_id: dict[str, str] = {}
    entities_by_id: dict[str, dict[str, Any]] = dict(idx)

    for entity_type, names in all_entity_names_by_type.items():
        for name in names:
            key = (name.strip().lower(), entity_type)
            existing = by_name_type.get(key)
            if existing:
                name_to_id[name] = existing["id"]
                entity_ids.append(existing["id"])
                continue
            entity_id = unique_entity_id(entity_type, name, existing_ids)
            existing_ids.add(entity_id)
            new_entity = {
                "id": entity_id,
                "record_type": "entity",
                "entity_type": entity_type,
                "name": name,
                "aliases": [],
                "status": "unverified",
                "description": "",
                "roles": [],
                "berry_ids": list(selected_berries),
                "evidence_ids": [],
                "fact_ids": [],
                "relationship_ids": [],
                "attributes": {},
            }
            by_name_type[key] = new_entity
            entities_by_id[entity_id] = new_entity
            entities_to_save.append(new_entity)
            name_to_id[name] = entity_id
            entity_ids.append(entity_id)

    evidence_id = draft_id

    fact_ids: list[str] = []
    facts_to_save: list[dict[str, Any]] = []
    for i, fact_input in enumerate(facts_input, start=1):
        fact_id = f"fact-{evidence_id[3:]}-{i}"
        facts_to_save.append(
            {
                "id": fact_id,
                "record_type": "fact",
                "statement": fact_input["statement"],
                "classification": fact_input["classification"],
                "confidence": fact_input["confidence"],
                "status": "active",
                "reviewer": reviewer,
                "created_at": date.today().isoformat(),
                "evidence_ids": [evidence_id],
                "entity_ids": list(entity_ids),
            }
        )
        fact_ids.append(fact_id)

    relationship_ids: list[str] = []
    relationships_to_save: list[dict[str, Any]] = []
    for i, rel_input in enumerate(relationships_input, start=1):
        rel_id = f"rel-{evidence_id[3:]}-{i}"
        relationships_to_save.append(
            {
                "id": rel_id,
                "record_type": "relationship",
                "subject_id": name_to_id[rel_input["subject"]],
                "predicate": rel_input["predicate"],
                "object_id": name_to_id[rel_input["object"]],
                "status": "active",
                "evidence_ids": [evidence_id],
                "effective_date": rel_input["effective_date"],
                "notes": "",
            }
        )
        relationship_ids.append(rel_id)

    strategic_questions = load_strategic_questions()
    sq_ids: list[str] = []
    for text in strategic_question_text:
        needle = text.strip().lower()
        for sq in strategic_questions:
            if sq.get("id", "").lower() == needle or sq.get("title", "").lower() == needle:
                sq_ids.append(sq["id"])
                break

    evidence_record = {
        "id": evidence_id,
        "record_type": "evidence",
        "status": "published",
        "source_type": source_type,
        "title": title,
        "source_name": source_name,
        "source_url": source_url,
        "published_date": published_date,
        "captured_date": captured_date,
        "summary": summary,
        "why_it_matters": why_it_matters,
        "submitted_by": draft.get("submitted_by", ""),
        "berry_ids": list(selected_berries),
        "geography_ids": [eid for eid in entity_ids if entities_by_id[eid]["entity_type"] == "geography"],
        "entity_ids": entity_ids,
        "fact_ids": fact_ids,
        "relationship_ids": relationship_ids,
        "strategic_question_ids": sq_ids,
        "tags": tags,
        "attachments": [],
        "priority": priority,
    }

    schema_errors = [e.message for e in get_validator("evidence.schema.json").iter_errors(evidence_record)]
    if schema_errors:
        return templates.TemplateResponse(
            request=request,
            name="review.html",
            context=_review_context(draft, values, "This record could not be published: " + "; ".join(schema_errors)),
            status_code=400,
        )

    # All validation passed: link entities to this evidence/facts/relationships,
    # then persist everything together so a failed publish leaves no orphans.
    for entity_id in set(entity_ids):
        entity = entities_by_id[entity_id]
        entity["evidence_ids"] = append_unique(entity.get("evidence_ids", []), evidence_id)
        entity["fact_ids"] = list(dict.fromkeys([*entity.get("fact_ids", []), *fact_ids]))
        related_rel_ids = [
            r["id"] for r in relationships_to_save if r["subject_id"] == entity_id or r["object_id"] == entity_id
        ]
        entity["relationship_ids"] = list(dict.fromkeys([*entity.get("relationship_ids", []), *related_rel_ids]))
        save_entity(entity)

    for fact in facts_to_save:
        save_fact(fact)
    for relationship in relationships_to_save:
        save_relationship(relationship)

    evidence_record["attachments"] = move_draft_attachments(draft_id, evidence_id, draft.get("attachments", []))
    save_evidence(evidence_record)
    delete_draft(draft_id)

    return RedirectResponse(url=f"/evidence/{evidence_id}", status_code=303)


@app.get("/api/feed")
def api_feed(
    q: str | None = None,
    berry: str | None = None,
    source: str | None = None,
    priority: str | None = None,
    competitor: str | None = None,
    geography: str | None = None,
    region: str | None = None,
) -> list[dict[str, Any]]:
    return filter_evidence(
        published_evidence(),
        q=q, berry=berry, source=source, priority=priority,
        competitor=competitor, geography=geography, region=region,
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
        and (
            needle in e.get("name", "").lower()
            or any(needle in alias.lower() for alias in e.get("aliases", []))
            or needle in e.get("description", "").lower()
        )
    ]
    return {"evidence": evidence_matches, "entities": entity_matches}
