"""Hydrate intake only for explicit source-passage retrieval.

Inventory and global search keep their bounded previews. A topic query may
inspect accessible source bodies transiently, then retains only the matched
excerpt and its content fingerprint in its packet.
"""
from __future__ import annotations

import hashlib
from typing import Any, Callable, Iterable

from app.services.information_catalog import INACTIVE_STATES, information_flags
from app.services.publication_sources import source_preview
from app.services.topic_retrieval import record_passages

MAX_TOPIC_EXCERPT_CHARS = 12_000


def hydrate_topic_sources(
    records: Iterable[dict[str, Any]],
    load_record: Callable[[str], dict[str, Any] | None] | None,
) -> list[dict[str, Any]]:
    rows = []
    for preview in records:
        row = preview
        if load_record is not None and preview.get("_catalog_origin") == "inbox":
            full = load_record(str(preview["id"]))
            if full is not None and full.get("id") == preview.get("id"):
                if full.get("status") in INACTIVE_STATES or full.get("review_state") in INACTIVE_STATES:
                    continue
                row = {**preview, **full, "information": information_flags(full)}
        rows.append(row)
    return rows


def bounded_topic_match(record: dict[str, Any]) -> dict[str, Any]:
    """Project a matched source without carrying its article or transcript."""
    body = "\n\n".join(text for locator, text in record_passages(record) if locator not in {"title", "summary", "snippet"})
    row = source_preview(record)
    # Keep the selected passage, rather than any other source excerpts that
    # happen to have been stored alongside the original source document.
    for field in ("supporting_excerpt", "original_text_excerpt"):
        row.pop(field, None)
    row.update({key: record.get(key) for key in (
        "score", "passage_locator", "relevance", "support_status", "source_review_hold",
        "match_reason", "classification_evidence_ids", "_catalog_origin",
    )})
    row["passage"] = str(record.get("passage") or "")[:MAX_TOPIC_EXCERPT_CHARS]
    row["source_version"] = hashlib.sha256(body.encode()).hexdigest() if body else record.get("source_version")
    row["source_version_basis"] = "stored_source_passages" if body else record.get("source_version_basis")
    return row
