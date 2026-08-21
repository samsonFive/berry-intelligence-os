"""Explicit Assessment berry scope from stored lineage.

D-012: `market_ids` holds berry ids when declared. Absent or empty means
scope has not been declared — not that the Assessment applies to every
berry. Do not infer berry from title, rationale, or linked company names.
"""

from __future__ import annotations

from typing import Any

SCOPE_UNSCOPED = "unscoped"
SCOPE_BERRY_SPECIFIC = "berry_specific"
SCOPE_MULTI_BERRY = "multi_berry"

SCOPE_LABELS = {
    SCOPE_UNSCOPED: "Company-wide / unscoped",
    SCOPE_BERRY_SPECIFIC: "Berry-specific",
    SCOPE_MULTI_BERRY: "Multi-berry",
}


def assessment_market_berry_ids(record: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    for value in record.get("market_ids") or []:
        text = str(value or "").strip()
        if not text.startswith("berry-") or text in seen:
            continue
        seen.add(text)
        ids.append(text)
    return ids


def assessment_berry_scope(
    record: dict[str, Any],
    berry_labels: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Classify from stored `market_ids` only."""

    labels = berry_labels or {}
    berry_ids = assessment_market_berry_ids(record)
    if not berry_ids:
        return {
            "kind": SCOPE_UNSCOPED,
            "label": SCOPE_LABELS[SCOPE_UNSCOPED],
            "berry_ids": [],
            "berry_names": [],
        }
    names = [labels.get(berry_id) or berry_id.removeprefix("berry-").title() for berry_id in berry_ids]
    if len(berry_ids) == 1:
        return {
            "kind": SCOPE_BERRY_SPECIFIC,
            "label": names[0],
            "berry_ids": berry_ids,
            "berry_names": names,
        }
    return {
        "kind": SCOPE_MULTI_BERRY,
        "label": SCOPE_LABELS[SCOPE_MULTI_BERRY],
        "berry_ids": berry_ids,
        "berry_names": names,
    }


def attach_assessment_scope(
    records: list[dict[str, Any]],
    berry_labels: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    attached: list[dict[str, Any]] = []
    for record in records:
        row = dict(record)
        row["berry_scope"] = assessment_berry_scope(record, berry_labels)
        attached.append(row)
    return attached
