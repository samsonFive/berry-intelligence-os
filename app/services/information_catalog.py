"""One information inventory; review and confidence are record attributes.

Legacy data/, intake and retained-web files remain persistence adapters, not
separate discovery datasets. Reading this catalog never publishes a record,
changes a review decision, or manufactures confidence from publication status.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable

INACTIVE_STATES = frozenset({"rejected", "archived", "withdrawn", "deleted"})


def information_flags(record: dict[str, Any]) -> dict[str, Any]:
    status = str(record.get("status") or "")
    review = str(record.get("review_state") or "")
    explicit = record.get("information") or {}
    if not isinstance(explicit, dict):
        explicit = {}
    if status in INACTIVE_STATES or review in INACTIVE_STATES:
        reviewed = "rejected"
    elif status == "unreviewed" or record.get("live"):
        reviewed = "unreviewed"
    elif explicit.get("review_status") in {"reviewed", "unreviewed"}:
        reviewed = explicit["review_status"]
    elif record.get("validated") is False or record.get("auto_captured") and not record.get("validated"):
        reviewed = "unreviewed"
    elif status == "published" or review == "published" or record.get("human_reviewed") is True:
        reviewed = "reviewed"
    else:
        reviewed = "unreviewed"
    confidence = deepcopy(explicit.get("confidence", record.get("information_confidence", record.get("confidence"))))
    if isinstance(confidence, dict):
        label = confidence.get("label") or confidence.get("level") or "Not assessed"
    elif confidence is None or confidence == "":
        label = "Not assessed"
    else:
        label = str(confidence)
    display_label = str(label).replace("_", " ")
    return {"review_status": reviewed, "confidence": confidence,
            "confidence_label": display_label[:1].upper() + display_label[1:],
            "verification_status": explicit.get("verification_status", record.get("verification_state") or ""),
            "caveats": deepcopy(explicit.get("caveats", record.get("does_not_prove") or [])),
            "publication_status": status or "unreviewed"}


def normalize_information(record: dict[str, Any], *, origin: str = "data") -> dict[str, Any]:
    return {**record, "information": information_flags(record), "_catalog_origin": origin}


def merge_information(evidence: Iterable[dict[str, Any]], drafts: Iterable[dict[str, Any]], *,
                      include_inactive: bool = False) -> list[dict[str, Any]]:
    """Exact-id union. Canonical records win, including explicit exclusions.

    Never fuzzy-merge independent claims, inherit a draft's review decision,
    or resurrect a rejected canonical record from an older cached version.
    """
    rows: dict[str, dict[str, Any]] = {}
    for pool, origin in ((drafts, "inbox"), (evidence, "data")):
        for record in pool:
            key = str(record.get("id") or "")
            if key:
                selected = normalize_information(record, origin=record.get("_catalog_origin") or origin)
                previous = rows.get(key)
                if previous and selected.get("source_url") and selected.get("source_url") == previous.get("source_url"):
                    from app.services.feed_first import safe_image_url
                    image = safe_image_url(previous) if not safe_image_url(selected) else ""
                    if image:
                        selected["image_url"] = image
                rows[key] = selected
    return sorted((row for row in rows.values() if include_inactive or not (
        str(row.get("status") or "") in INACTIVE_STATES
        or str(row.get("review_state") or "") in INACTIVE_STATES)),
        key=lambda row: (str(row.get("published_date") or row.get("captured_date") or ""), row["id"]),
        reverse=True)


def load_information(evidence: list[dict[str, Any]], inbox_dir, *, include_private: bool = True) -> list[dict[str, Any]]:
    if not include_private or inbox_dir is None:
        return merge_information(evidence, [])
    from app.services.personal_digest import retained_news
    from app.services.publication_sources import pending_source_previews
    # The streaming preview reader covers both publications and atomic claims.
    # It never constructs article/transcript bodies on inventory/search paths.
    drafts, issues = pending_source_previews(inbox_dir, publications_only=False)
    if issues:
        import logging
        logging.getLogger(__name__).warning("Information catalog: %d unavailable intake records", len(issues))
    cached = retained_news(inbox_dir)
    # Invalid current files must not expose an obsolete cache as current data.
    unavailable_ids = {issue["id"] for issue in issues}
    cached = [row for row in cached if row.get("id") not in unavailable_ids]
    private = merge_information(drafts, cached)
    private = [{**row, "_catalog_origin": "inbox"} for row in private]
    # Include inactive drafts as tombstones against older daily-cache entries.
    inactive = [row for row in drafts if str(row.get("status") or "") in INACTIVE_STATES
                or str(row.get("review_state") or "") in INACTIVE_STATES]
    return merge_information(evidence, [*private, *inactive])
