"""Read-only private publication previews. Source review is never inferred."""
from __future__ import annotations

import json
from collections import OrderedDict
from copy import deepcopy
from pathlib import Path
from threading import RLock

import ijson
from ijson.common import ObjectBuilder

from app.services.feed_first import SAFE_ID_RE, safe_image_url

MAX_DRAFT_BYTES = 16_000_000
MAX_PREVIEW_BYTES = 256_000
_preview_cache = OrderedDict()
_preview_cache_lock = RLock()
_preview_cache_bytes = 0
MAX_PREVIEW_CACHE_BYTES = 16_000_000
PREVIEW_FIELDS = {
    "supporting_excerpt", "attribution", "classification", "original_text_excerpt",
    "id", "record_type", "status", "review_state", "evidence_role", "title", "summary", "why_it_matters",
    "source_type", "source_name", "source_id", "source_url", "published_date", "captured_date",
    "accessed_date", "published_at", "published_date_basis", "submitted_by", "reviewed_by", "reviewed_at",
    "created_at", "updated_at", "entity_ids", "company_ids", "berry_ids", "geography_ids", "geography_scope",
    "region", "country", "tags", "topics", "topic_ids", "priority", "source_authority", "verification_state",
    "trust_state", "live", "auto_captured", "validated", "media_type", "media_format", "content_kind",
    "source_language", "original_title", "translated", "translation_pending", "image_url", "image_source_url",
    "preview_image_url", "thumbnail_url", "source_image_url", "origin_publisher_url",
    "acquisition_lane", "discovery_provenance",
}


def inactive_publication_record(record: dict | None) -> bool:
    return (isinstance(record, dict) and record.get("evidence_role") == "publication_artifact"
            and any(isinstance(record.get(field), str) and record[field] in {"rejected", "archived"}
                    for field in ("status", "review_state")))


def active_publication_record(record: dict | None) -> dict | None:
    if (not isinstance(record, dict)
            or not SAFE_ID_RE.fullmatch(str(record.get("id") or ""))
            or record.get("evidence_role") != "publication_artifact"
            or inactive_publication_record(record)
            or not isinstance(record.get("status", "draft"), str)
            or record.get("status", "draft") not in {"draft", "in_review"}):
        return None
    label = str(record.get("source_name") or "").removeprefix("Site-restricted news search -- ")
    return {**record, "status": "unreviewed", "source_name": label}


def source_preview(record: dict) -> dict:
    """A feed card needs preview metadata and one image, never original bodies."""
    preview = {key: value for key, value in record.items() if key in PREVIEW_FIELDS}
    image = safe_image_url(record)
    if image:
        preview["image_url"] = image
    return preview


def _read_preview(path: Path) -> dict:
    # Streaming events inspect body scalars but do not build or retain an
    # article/transcript object. Unknown fields are not accepted into a preview.
    if path.stat().st_size > MAX_DRAFT_BYTES:
        raise ValueError("source-size-limit")
    preview: dict = {}
    builder = None
    field = ""
    depth = 0
    image = ""
    with path.open("rb") as handle:
        for prefix, event, value in ijson.parse(handle, use_float=True):
            if prefix == "" and event == "start_map":
                continue
            if prefix == "" and event == "map_key":
                field = value if value in PREVIEW_FIELDS else ""
                builder = ObjectBuilder() if field else None
                depth = 0
                continue
            if prefix in {"article.image_url", "images.item.url"} and event == "string" and not image:
                image = safe_image_url({"image_url": value})
            if builder is not None:
                builder.event(event, value)
                if event in {"start_map", "start_array"}:
                    depth += 1
                elif event in {"end_map", "end_array"}:
                    depth -= 1
                if depth == 0:
                    preview[field] = builder.value
                    builder = None
    if image and not safe_image_url(preview):
        preview["image_url"] = image
    if len(json.dumps(preview, ensure_ascii=False).encode("utf-8")) > MAX_PREVIEW_BYTES:
        raise ValueError("metadata-size-limit")
    return preview


def _current_preview(path: Path) -> dict:
    """Reuse bounded metadata only while this exact file is unchanged."""
    global _preview_cache_bytes
    stat = path.stat()
    key = str(path.resolve())
    signature = (stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
    with _preview_cache_lock:
        cached = _preview_cache.get(key)
        if cached and cached[0] == signature:
            _preview_cache.move_to_end(key)
            return deepcopy(cached[1])
    row = _read_preview(path)
    after = path.stat()
    if signature != (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
        return _read_preview(path)  # Concurrent write; don't cache this read.
    size = len(json.dumps(row, ensure_ascii=False).encode("utf-8"))
    with _preview_cache_lock:
        previous = _preview_cache.pop(key, None)
        if previous:
            _preview_cache_bytes -= previous[2]
        _preview_cache[key] = (signature, deepcopy(row), size)
        _preview_cache_bytes += size
        while _preview_cache_bytes > MAX_PREVIEW_CACHE_BYTES or len(_preview_cache) > 4096:
            _, removed = _preview_cache.popitem(last=False)
            _preview_cache_bytes -= removed[2]
    return row


def pending_source_previews(inbox_dir: Path) -> tuple[list[dict], list[dict]]:
    """Check every current file; cache only unchanged metadata in private memory.

    Includes terminal publication metadata so rejection can suppress an older
    retained feed cache. The caller applies active/terminal publication gates.
    """
    rows, issues = [], []
    for path in sorted((Path(inbox_dir) / "evidence").glob("*.json")):
        if path.is_symlink():
            issues.append({"id": path.stem, "reason": "linked-source"})
            continue
        try:
            row = _current_preview(path)
            if row.get("id") != path.stem or not SAFE_ID_RE.fullmatch(path.stem):
                raise ValueError("source-identity-mismatch")
            if row.get("evidence_role") == "publication_artifact":
                rows.append(row)
        except (OSError, ValueError, ijson.JSONError, OverflowError):
            issues.append({"id": path.stem, "reason": "source-unavailable"})
    return rows, issues
