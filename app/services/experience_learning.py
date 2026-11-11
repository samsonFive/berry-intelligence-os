"""Read-only native Learn projections; education never acquires intelligence trust.

The metadata cache contains neither lesson bodies nor provider/job payloads. Its
key includes the actual runtime paths and file identities. Existing private
drafts remain in learn_research.json and are never rewritten by these readers.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import date
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
from threading import RLock
from urllib.parse import urlencode, urlsplit

import ijson

from app.services import learner, learner_visuals
from app.services.ai_gateway.perplexity_deep_research import safe_url
from app.session_auth import is_investigation_path, safe_next_path

MAX_CONCEPTS = 512
MAX_LESSONS = 2048
MAX_CONCEPT_BYTES = 2_000_000
MAX_STORE_BYTES = 64_000_000
MAX_SELECTED_TEXT = 2_000_000
SAFE_ID = re.compile(r"[A-Za-z0-9_-]{1,180}\Z")
BOUNDARY = {"label": "Educational knowledge", "competitive_evidence": False,
            "note": "Educational knowledge and research drafts are not Fact, Atomic Evidence, Signal, or Assessment and do not increase Signal confidence."}
_LOCK = RLock()
_SCALARS = {"id", "slug", "name", "title", "summary", "pillar", "knowledge_class",
            "reviewed_at", "review_by", "created_at", "updated_at", "revision",
            "education_status", "partial", "job_id"}
_REQUEST = {"topic", "berry", "berry_label", "geography", "geography_label", "concept_id", "pillar", "knowledge_class"}
_MEDIA = {"kind", "title", "publisher", "caption", "alt", "license", "attribution",
          "reuse_basis", "verified_at", "attribution_required"}
_URLS = {"url", "image_url", "license_url", "source_page"}


def _issue(field, message):
    return {"code": "learning_unavailable", "field": field, "message": message}


def normalize_selection(params):
    if str(params.get("ctx_v") or "1") != "1":
        raise ValueError("This learning API supports investigation context version 1.")
    selection = {key: str(params.get(key) or "").strip() for key in ("q", "pillar", "knowledge_class")}
    selection["kind"] = str(params.get("kind") or "all")
    if len(selection["q"]) > 200:
        raise ValueError("Search the learning catalog with up to 200 characters.")
    for key, choices in (("pillar", learner.PILLAR_LABELS), ("knowledge_class", learner.KNOWLEDGE_CLASS_LABELS)):
        if selection[key] and selection[key] not in choices:
            raise ValueError("Choose an available learning " + key.replace("_", " ") + ".")
    if selection["kind"] not in {"all", "concept", "lesson"}:
        raise ValueError("Choose concepts, lessons, or all learning entries.")
    for key, default, maximum in (("offset", "0", 100_000), ("limit", "40", 100)):
        raw = str(params.get(key, default))
        if not raw.isdigit() or len(raw) > 6 or int(raw) > maximum or (key == "limit" and int(raw) < 1):
            raise ValueError("Choose a bounded learning catalog page.")
        selection[key] = int(raw)
    return selection


def scope_key(selection):
    return hashlib.sha256(json.dumps(selection, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:20]


def applied_scope(selection):
    return {"module": "learning", "filters": selection,
            "applicability": "Learning catalog filters apply here. Investigation geography, focus, cohorts and news dates are navigation context, not automatic educational filters."}


def _signature(path, maximum):
    if path.is_symlink():
        raise ValueError("Learning stores must be regular local files.")
    stat = path.stat()
    if not path.is_file() or stat.st_size > maximum:
        raise ValueError("The learning store exceeds the bounded reader.")
    return (str(path.resolve()), stat.st_mtime_ns, stat.st_size, stat.st_ino)


def _unchanged(signature, maximum):
    if _signature(Path(signature[0]), maximum) != signature:
        raise ValueError("Learning changed while it was being read. Reload the catalog.")


def _concept_header(signature):
    row = {"aliases": [], "berry_ids": [], "source_count": 0, "media_count": 0}
    with Path(signature[0]).open("rb") as handle:
        for prefix, event, value in ijson.parse(handle):
            if prefix in _SCALARS and event in {"string", "number", "boolean"}:
                row[prefix] = value
            elif prefix == "aliases.item" and event == "string":
                row["aliases"].append(value)
            elif prefix == "berry_notes.item.berry_id" and event == "string":
                row["berry_ids"].append(value)
            elif prefix in {"sources.item", "media.item"} and event == "start_map":
                row["source_count" if prefix == "sources.item" else "media_count"] += 1
    if not SAFE_ID.fullmatch(str(row.get("id") or "")) or not SAFE_ID.fullmatch(str(row.get("slug") or "")) or not row.get("name"):
        raise ValueError("A learning concept has an invalid identity.")
    if row.get("pillar") not in learner.PILLAR_LABELS or row.get("knowledge_class") not in learner.KNOWLEDGE_CLASS_LABELS:
        raise ValueError("A learning concept has an unsupported classification.")
    if len(row.get("aliases", [])) > 64 or any(len(str(value)) > 4_000 for key, value in row.items() if key not in {"aliases", "berry_ids"}):
        raise ValueError("A concept header exceeds the bounded catalog.")
    row.update(kind="concept", _file=signature, education_status="educational_knowledge")
    _unchanged(signature, MAX_CONCEPT_BYTES)
    return row


def _lesson_headers(signature):
    """One streaming pass. Text/history/configuration scalars are not retained."""
    jobs, lessons, containers = {}, {}, set()
    version = None
    with Path(signature[0]).open("rb") as handle:
        for prefix, event, value in ijson.parse(handle):
            if prefix == "version" and event == "number":
                version = value
            if prefix in {"jobs", "lessons"} and event == "start_map":
                containers.add(prefix)
            parts = prefix.split(".")
            if len(parts) < 2 or parts[0] not in {"jobs", "lessons"}:
                continue
            kind, key = parts[:2]
            target = jobs if kind == "jobs" else lessons
            if len(parts) == 2 and event not in {"start_map", "end_map", "map_key"}:
                raise ValueError("Saved learning work cannot be read.")
            if len(parts) == 2 and event == "start_map":
                if key in target or not SAFE_ID.fullmatch(key) or len(target) >= MAX_LESSONS:
                    raise ValueError("The learning store exceeds the bounded catalog.")
                target[key] = {"request": {}, "source_count": 0, "history_count": 0, "_valid": set()}
            row = target.get(key)
            if row is None:
                continue
            field = ".".join(parts[2:])
            if len(parts) == 3 and field in _SCALARS | {"status"} and event in {"string", "number", "boolean"}:
                if isinstance(value, str) and len(value) > 4_000:
                    raise ValueError("A saved lesson header exceeds the bounded catalog.")
                row[field] = value
            elif len(parts) == 4 and parts[2] == "request" and parts[3] in _REQUEST and event == "string":
                if len(value) > 4_000:
                    raise ValueError("A saved lesson header exceeds the bounded catalog.")
                row["request"][parts[3]] = value
            if field == "request" and event == "start_map":
                row["_valid"].add("request")
            if field in {"text", "original_text", "token", "fingerprint"} and event == "string":
                row["_valid"].add(field)
            if field in {"citations", "history"} and event == "start_array":
                row["_valid"].add(field)
            if field == "citations.item" and event == "start_map":
                row["source_count"] += 1
            elif field == "citations.item" and event not in {"end_map", "map_key"}:
                raise ValueError("A saved citation has an unsupported shape.")
            if field == "history.item" and event == "start_map":
                row["history_count"] += 1
    if version != 1 or containers != {"jobs", "lessons"}:
        raise ValueError("Saved learning work cannot be read.")
    for kind, records in (("jobs", jobs), ("lessons", lessons)):
        for key, row in records.items():
            required = {"request", "token", "fingerprint"} if kind == "jobs" else {"request", "text", "original_text", "citations", "history"}
            if row.get("id") != key or type(row.get("revision")) is not int or row["revision"] < 1 or not isinstance(row.get("created_at"), str) or not required <= row["_valid"]:
                raise ValueError("Saved learning work cannot be read.")
            if kind == "jobs" and row.get("status") not in {"requested", "submitting", "submission_uncertain", "running", "cancelling", "ready", "partial", "failed", "cancelled"}:
                raise ValueError("Saved learning work cannot be read.")
            if kind == "lessons" and row.get("job_id") not in jobs:
                raise ValueError("A saved lesson has no recorded research origin.")
    _unchanged(signature, MAX_STORE_BYTES)
    return [{key: value for key, value in row.items() if key != "_valid"} | {"kind": "lesson", "_file": signature}
            for row in lessons.values()]


@lru_cache(maxsize=4)
def _cached_headers(concept_signatures, lesson_signature):
    issues, concepts, lessons = [], [], []
    try:
        concepts = [_concept_header(signature) for signature in concept_signatures]
        if len({row["id"] for row in concepts}) != len(concepts) or len({row["slug"] for row in concepts}) != len(concepts):
            raise ValueError("Duplicate learning concept identities need attention.")
    except (OSError, ValueError, ijson.JSONError):
        concepts = []
        issues.append(_issue("concepts", "The concept library could not be read. Existing records were left unchanged."))
    if lesson_signature:
        try:
            lessons = _lesson_headers(lesson_signature)
        except (OSError, ValueError, ijson.JSONError):
            issues.append(_issue("lessons", "Saved learning work could not be read. Existing drafts were left unchanged."))
    return {"concepts": concepts, "lessons": lessons, "issues": issues}


def load_catalog(inbox_dir, *, concepts_dir=None):
    """Read finite metadata once per runtime file snapshot; never load the world."""
    root = Path(concepts_dir) if concepts_dir is not None else learner.CONCEPTS_DIR
    issues, concept_signatures, lesson_signature = [], (), None
    try:
        paths = sorted(root.glob("concept-*.json"))
        if len(paths) > MAX_CONCEPTS:
            raise ValueError("Too many concepts for the bounded catalog.")
        concept_signatures = tuple(_signature(path, MAX_CONCEPT_BYTES) for path in paths)
    except (OSError, ValueError):
        issues.append(_issue("concepts", "The concept library exceeds the bounded reader or is unavailable."))
    try:
        path = Path(inbox_dir) / "learn_research.json"
        if path.exists() or path.is_symlink():
            lesson_signature = _signature(path, MAX_STORE_BYTES)
    except (OSError, ValueError):
        issues.append(_issue("lessons", "The saved lesson library exceeds the bounded reader or is unavailable."))
    with _LOCK:
        result = deepcopy(_cached_headers(concept_signatures, lesson_signature))
        # A transient local read failure must be recoverable on the next read
        # without requiring an edit to the underlying library.
        if result["issues"]:
            _cached_headers.cache_clear()
    result["issues"].extend(issues)
    return result


def _return_path(value):
    candidate = safe_next_path(value or "/app/learn")
    return candidate if is_investigation_path(urlsplit(candidate).path) else "/app/learn"


def metadata(row, *, return_to=""):
    request = row.get("request") or {}
    pillar = row.get("pillar") or request.get("pillar") or ""
    classification = row.get("knowledge_class") or request.get("knowledge_class") or ""
    kind, key = row["kind"], row["id"]
    legacy = "/learn/" + (row["slug"] if kind == "concept" else "lessons/" + key)
    review_by = str(row.get("review_by") or "")
    status = row.get("education_status") or ("educational_knowledge" if kind == "concept" else "ai_draft")
    result = {"kind": kind, "id": key, "title": row.get("name") or row.get("title") or key,
              "pillar": pillar, "pillar_label": learner.PILLAR_LABELS.get(pillar, pillar),
              "knowledge_class": classification, "knowledge_class_label": learner.KNOWLEDGE_CLASS_LABELS.get(classification, classification),
              "education_status": status,
              "status_label": {"educational_knowledge": "Educational knowledge", "ai_draft": "AI-researched educational draft", "analyst_edited": "Edited educational draft"}.get(status, "Educational draft"),
              "partial": bool(row.get("partial")), "reviewed_at": str(row.get("reviewed_at") or ""),
              "review_by": review_by, "is_stale": bool(review_by and review_by < date.today().isoformat()),
              "needs_review_cadence": classification in learner.FRESHNESS_CLASSES,
              "source_count": row.get("source_count", 0), "media_count": row.get("media_count", 0),
              "scope": {"berry_id": request.get("berry", ""), "berry_label": request.get("berry_label", ""),
                        "geography_id": request.get("geography", ""), "geography_label": request.get("geography_label", ""),
                        "berry_ids": row.get("berry_ids", [])},
              "href": f"/app/learn/{kind}/{key}",
              "expand_href": legacy + "?" + urlencode({"return_to": _return_path(return_to or f"/app/learn/{kind}/{key}")})}
    for field in ("slug", "summary", "updated_at", "revision"):
        if field in row:
            result[field] = row[field]
    return result


def _matches(row, selection):
    request = row.get("request") or {}
    if selection["kind"] != "all" and row["kind"] != selection["kind"]:
        return False
    for field in ("pillar", "knowledge_class"):
        if selection[field] and selection[field] != (row.get(field) or request.get(field)):
            return False
    haystack = " ".join(str(value) for value in [row.get("name", ""), row.get("title", ""), row.get("summary", ""), request.get("topic", ""), *(row.get("aliases") or [])])
    return selection["q"].casefold() in haystack.casefold()


def learning_data(catalog, selection, *, return_to=""):
    rows = catalog["concepts"] + catalog["lessons"]
    projected = [metadata(row, return_to=return_to) for row in rows]
    unavailable = {issue["field"] for issue in catalog["issues"]}
    collections = {}
    for field in ("concepts", "lessons"):
        all_rows = catalog[field]
        matched = sorted((row for row in all_rows if _matches(row, selection)), key=lambda row: str(row.get("name") or row.get("title") or "").casefold())
        start, limit = selection["offset"], selection["limit"]
        collections[field] = {"status": "unavailable" if field in unavailable else ("available" if all_rows else "empty"),
                              "total": None if field in unavailable else len(all_rows), "matched_count": None if field in unavailable else len(matched),
                              "items": [metadata(row, return_to=return_to) for row in matched[start:start + limit]],
                              "has_more": start + limit < len(matched)}
    facets = {}
    for field, labels in (("pillars", learner.PILLAR_LABELS), ("knowledge_classes", learner.KNOWLEDGE_CLASS_LABELS)):
        source_field = "pillar" if field == "pillars" else "knowledge_class"
        counts = Counter(row[source_field] for row in projected)
        facets[field] = [{"id": key, "label": label, "count": None if unavailable else counts[key]} for key, label in labels.items()]
    return {"education_boundary": BOUNDARY, "collections": collections, "facets": facets,
            "counts": {"concepts": collections["concepts"]["total"], "lessons": collections["lessons"]["total"],
                       "stale": None if unavailable else sum(row["is_stale"] for row in projected),
                       "partial": None if unavailable else sum(row["partial"] for row in projected)},
            "selection": selection}


def _resource(row):
    result = {key: value for key, value in row.items() if key in _MEDIA and isinstance(value, (str, bool))}
    for key in _URLS:
        if row.get(key):
            result[key] = safe_url(row[key])
    if isinstance(row.get("reference_ids"), list):
        if len(row["reference_ids"]) > 128:
            raise ValueError("This lesson exceeds the bounded native citation reader. Open its retained Learn page.")
        result["reference_ids"] = [value for value in row["reference_ids"] if isinstance(value, str)]
    return result


def _teaching(concept):
    diagram = concept.get("teaching_diagram")
    if diagram:
        diagram = {key: diagram.get(key) for key in ("title", "intro", "limit", "checked_on", "mode", "illustration") if diagram.get(key) is not None} | {
            "sources": [_resource(row) for row in concept["teaching_diagram"].get("sources", [])],
            "steps": [{key: row.get(key, "") for key in ("title", "icon", "caption", "detail")} for row in concept["teaching_diagram"].get("steps", [])],
            "illustrative": True, "attribution": "Original schematic by Berry Intelligence; no publisher graphics copied."}
    return {"figure": _resource(concept["teaching_figure"]) if concept.get("teaching_figure") else None,
            "diagram": diagram, "cane_diagram": bool(concept.get("cane_diagram")),
            "legacy_visual_href": f"/learn/{concept['slug']}#cane-calendar" if concept.get("cane_diagram") else ""}


def _selected_lesson(signature, key):
    row, citation, reading = {"citations": []}, None, False
    target = "lessons." + key
    with Path(signature[0]).open("rb") as handle:
        for prefix, event, value in ijson.parse(handle):
            if prefix == target and event == "start_map":
                reading = True
            if not reading:
                continue
            field = prefix.removeprefix(target + ".")
            if field == "text" and event == "string":
                if len(value) > MAX_SELECTED_TEXT:
                    raise ValueError("This lesson exceeds the bounded native reader. Open its retained Learn page.")
                row["text"] = value
            if field == "citations.item" and event == "start_map":
                citation = {}
            elif citation is not None and field.startswith("citations.item."):
                prop = field.removeprefix("citations.item.")
                if prop in _MEDIA | _URLS and event in {"string", "boolean"}:
                    citation[prop] = value
                elif prop == "reference_ids.item" and event == "string":
                    citation.setdefault("reference_ids", []).append(value)
            if field == "citations.item" and event == "end_map":
                if len(row["citations"]) >= 512:
                    raise ValueError("This lesson exceeds the bounded native citation reader. Open its retained Learn page.")
                row["citations"].append(_resource(citation))
                citation = None
            if prefix == target and event == "end_map":
                break
    _unchanged(signature, MAX_STORE_BYTES)
    if "text" not in row:
        raise LookupError("This learning lesson is unavailable.")
    return row


def selected_data(catalog, kind, key, *, return_to=""):
    if kind not in {"concept", "lesson"} or not SAFE_ID.fullmatch(key):
        raise LookupError("This learning entry is unavailable.")
    field = "concepts" if kind == "concept" else "lessons"
    if any(issue["field"] == field for issue in catalog["issues"]):
        raise ValueError("This learning library needs attention before its entries can be opened.")
    row = next((row for row in catalog[field] if row["id"] == key), None)
    if not row:
        raise LookupError("This learning entry is unavailable.")
    result = {"item": metadata(row, return_to=return_to), "education_boundary": BOUNDARY,
              "sections": [], "citations": [], "media": [], "teaching": None, "berry_notes": [], "related": [],
              "provenance": {"education_boundary": BOUNDARY}}
    if kind == "concept":
        _unchanged(row["_file"], MAX_CONCEPT_BYTES)
        with Path(row["_file"][0]).open(encoding="utf-8") as handle:
            concept = learner_visuals.presentation(json.load(handle))
        _unchanged(row["_file"], MAX_CONCEPT_BYTES)
        clarification = concept.get("lesson_clarification") or {}
        result["item"]["summary"] = clarification.get("summary") or concept.get("summary", "")
        result["sections"] = [{"id": key, "title": label, "text": clarification.get(key) or concept.get(key, "")}
                              for key, label in (("what_is_it", "What is it?"), ("why_it_matters", "Why does it matter?"),
                                  ("how_evaluated", "How is it evaluated / observed?"), ("what_affects_it", "What can affect it?"),
                                  ("how_to_interpret", "When you see this in intelligence"))]
        if clarification:
            result["clarification"] = {"retained_original": {key: concept.get(key, "") for key in ("summary", "what_is_it")}}
        result["citations"] = [_resource(source) for source in concept.get("sources", [])]
        result["media"] = [_resource(media) | {"display": "source_link"} for media in concept.get("media", [])]
        result["teaching"] = _teaching(concept)
        result["berry_notes"] = learner.berry_notes_for_display(concept, "")["in_context"]
        related_ids = set(concept.get("related_concept_ids") or [])
        result["related"] = [{key: value for key, value in metadata(related).items() if key in {"kind", "id", "title", "href"}}
                             for related in catalog["concepts"] if related["id"] in related_ids]
        result["provenance"]["knowledge_class_note"] = learner.KNOWLEDGE_CLASS_NOTES.get(row.get("knowledge_class"), "")
    else:
        selected = _selected_lesson(row["_file"], key)
        result["content_markdown"] = selected["text"]
        result["citations"] = selected["citations"]
        result["provenance"].update({key: row.get(key, "") for key in ("job_id", "revision", "created_at", "updated_at", "history_count")})
        concept_id = row["request"].get("concept_id")
        companion = next((item for item in catalog["concepts"] if item["id"] == concept_id), None)
        if companion:
            # Only the explicit authored concept binding supplies a companion.
            _unchanged(companion["_file"], MAX_CONCEPT_BYTES)
            with Path(companion["_file"][0]).open(encoding="utf-8") as handle:
                concept = learner_visuals.presentation(json.load(handle))
            _unchanged(companion["_file"], MAX_CONCEPT_BYTES)
            result["teaching"] = _teaching(concept) | {"companion": {"id": companion["id"], "title": companion["name"], "href": f"/app/learn/concept/{companion['id']}"},
                                                       "note": "Visual companion from the existing concept and its sources; separate from the research draft."}
    result["expand_href"] = result["item"]["expand_href"]
    return result
