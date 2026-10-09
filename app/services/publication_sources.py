"""Read-only private publication previews. Source review is never inferred."""
from __future__ import annotations

import json
from pathlib import Path

import ijson
from ijson.common import ObjectBuilder

from app.services.feed_first import SAFE_ID_RE, safe_image_url

MAX_DRAFT_BYTES = 16_000_000
MAX_PREVIEW_BYTES = 256_000
PREVIEW_FIELDS = {
    "id", "record_type", "status", "review_state", "evidence_role", "title", "summary", "why_it_matters",
    "source_type", "source_name", "source_id", "source_url", "published_date", "captured_date",
    "accessed_date", "published_at", "published_date_basis", "submitted_by", "reviewed_by", "reviewed_at",
    "created_at", "updated_at", "entity_ids", "company_ids", "berry_ids", "geography_ids", "geography_scope",
    "region", "country", "tags", "topics", "topic_ids", "priority", "source_authority", "verification_state",
    "trust_state", "live", "auto_captured", "validated", "media_type", "media_format", "content_kind",
    "source_language", "original_title", "translated", "translation_pending", "image_url", "image_source_url",
    "preview_image_url", "thumbnail_url", "source_image_url", "origin_publisher_url",
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


def pending_source_previews(inbox_dir: Path) -> tuple[list[dict], list[dict]]:
    """Fresh on every read: no stale cache, file mutation or acquisition.

    Includes terminal publication metadata so rejection can suppress an older
    retained feed cache. The caller applies active/terminal publication gates.
    """
    rows, issues = [], []
    for path in sorted((Path(inbox_dir) / "evidence").glob("*.json")):
        if path.is_symlink():
            issues.append({"id": path.stem, "reason": "linked-source"})
            continue
        try:
            row = _read_preview(path)
            if row.get("id") != path.stem or not SAFE_ID_RE.fullmatch(path.stem):
                raise ValueError("source-identity-mismatch")
            if row.get("evidence_role") == "publication_artifact":
                rows.append(row)
        except (OSError, ValueError, ijson.JSONError, OverflowError):
            issues.append({"id": path.stem, "reason": "source-unavailable"})
    return rows, issues
