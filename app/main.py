from __future__ import annotations

import json
import os
import re
import secrets
import shutil
from datetime import date, datetime
from pathlib import Path
from typing import Any

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

app = FastAPI(title="Berry Intelligence OS", version="0.1.0")
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


def filter_evidence(
    records: list[dict[str, Any]],
    q: str | None = None,
    berry: str | None = None,
    source: str | None = None,
    priority: str | None = None,
    competitor: str | None = None,
    geography: str | None = None,
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
        results = [r for r in results if geography in (r.get("geography_ids") or [])]

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
    competitors = sorted(
        ({"id": i, "name": entities[i]["name"]} for i in competitor_ids), key=lambda c: c["name"]
    )
    geographies = sorted(
        ({"id": i, "name": entities[i]["name"]} for i in geography_ids), key=lambda g: g["name"]
    )
    return {"berries": berries, "sources": sources, "competitors": competitors, "geographies": geographies}


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
) -> HTMLResponse:
    evidence = published_evidence()
    options = filter_options(evidence, entity_index())
    filtered = filter_evidence(
        evidence, q=q, berry=berry, source=source, priority=priority, competitor=competitor, geography=geography
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


@app.get("/entities/{entity_type}", response_class=HTMLResponse)
def entity_list(request: Request, entity_type: str) -> HTMLResponse:
    entities = sorted(
        (e for e in all_entities() if e.get("entity_type") == entity_type),
        key=lambda e: e.get("name", ""),
    )
    if not entities:
        raise HTTPException(status_code=404, detail=f"No entities found for type '{entity_type}'")
    return templates.TemplateResponse(
        request=request,
        name="entity_list.html",
        context={"entities": entities, "entity_type": entity_type, "authoring_mode": AUTHORING_MODE},
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
            return templates.TemplateResponse(
                request=request,
                name="entity.html",
                context={
                    "entity": entity,
                    "linked_evidence": linked_evidence,
                    "linked_facts": facts_for_entity(entity_id),
                    "evidence_count": len(linked_evidence),
                    "source_count": len(independent_sources),
                    "last_updated": last_updated,
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
def priority_queue(request: Request, dimension: str) -> HTMLResponse:
    if dimension not in PRIORITY_DIMENSIONS:
        raise HTTPException(status_code=404, detail="Unknown priority dimension")
    entities = entity_index()
    items = []
    for record in queue_items(dimension):
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
) -> list[dict[str, Any]]:
    return filter_evidence(
        published_evidence(), q=q, berry=berry, source=source, priority=priority, competitor=competitor, geography=geography
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
