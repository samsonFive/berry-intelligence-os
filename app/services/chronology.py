"""Canonical meaningful-date chronology for trusted intelligence surfaces.

World chronology prefers real-world dates over pipeline timestamps.
Reacquisition, recovery, review, and index stamps never count as the
event/publication moment — capture/review must not masquerade as
published/event.

Semantic origins map to UI labels: Published / Captured / Filed / Observed
(plus Event date and kind-specific bases). Generic "Date" is not a label.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

FORBIDDEN_FRESHNESS = ("reacquired_at", "recovered_at", "reviewed_at", "indexed_at")

ChronologyMode = Literal["default", "feed", "timeline_evidence", "commercial", "patent"]

ORIGIN_LABELS = {
    "published": "Published",
    "event": "Event date",
    "captured": "Captured",
    "observed": "Observed",
    "filed": "Filed",
    "effective_date": "Effective",
    "first_seen": "First seen",
    "created_at": "Recorded",
    "granted": "Granted",
}


def parse_stamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = datetime.strptime(text[:10], "%Y-%m-%d")
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def date_label(origin: str) -> str:
    """Human label for a chronology origin. Never returns generic 'Date'."""
    if not origin:
        return ""
    return ORIGIN_LABELS.get(origin, origin.replace("_", " ").title())


def _first_parsed(record: dict[str, Any], *keys: str) -> tuple[datetime | None, str]:
    for key in keys:
        parsed = parse_stamp(record.get(key))
        if parsed:
            return parsed, key
    return None, ""


def _is_commercial_observation(record: dict[str, Any]) -> bool:
    if record.get("commercial_observation") or record.get("observed_at"):
        return True
    source_type = str(record.get("source_type") or "")
    return source_type in {"retail_listing", "commercial_observation"}


def _is_patentish(record: dict[str, Any]) -> bool:
    source_type = str(record.get("source_type") or "")
    if source_type in {"patent_record", "plant_breeders_rights_record", "government_registry"}:
        return True
    if record.get("filing_date") or record.get("grant_date") or record.get("publication_date"):
        return True
    return False


def meaningful_stamp(
    record: dict[str, Any],
    *,
    mode: ChronologyMode = "default",
) -> tuple[datetime | None, str]:
    """Newest-meaningful chronology for one record.

    Returns ``(when, origin)`` where origin is a semantic key suitable for
    ``date_label``. Forbidden freshness keys are never consulted.
    """
    # Document intent: callers must not use pipeline freshness for world time.
    for key in FORBIDDEN_FRESHNESS:
        record.get(key)

    if mode == "commercial" or (mode == "default" and _is_commercial_observation(record)):
        observed = parse_stamp(
            (record.get("commercial_observation") or {}).get("observed_at")
            if isinstance(record.get("commercial_observation"), dict)
            else None
        ) or parse_stamp(record.get("observed_at"))
        if observed:
            return observed, "observed"
        published = parse_stamp(record.get("published_date"))
        if published:
            return published, "published"
        captured = parse_stamp(record.get("captured_date"))
        if captured:
            return captured, "captured"
        return None, ""

    if mode == "timeline_evidence":
        published = parse_stamp(record.get("published_date"))
        if published:
            return published, "published"
        return None, ""

    if mode == "patent" or (mode == "default" and _is_patentish(record) and not record.get("published_date")):
        filed = parse_stamp(record.get("filing_date"))
        if filed and not record.get("grant_date") and not record.get("publication_date"):
            return filed, "filed"
        granted = parse_stamp(record.get("grant_date"))
        if granted:
            return granted, "granted"
        published = parse_stamp(record.get("publication_date") or record.get("published_date"))
        if published:
            return published, "published"
        if filed:
            return filed, "filed"

    published = parse_stamp(record.get("published_date"))
    if published:
        # Filing stored as published_date for patents: prefer Filed when only filing exists upstream.
        if mode == "patent" and record.get("filing_date") and not record.get("grant_date"):
            filed = parse_stamp(record.get("filing_date"))
            if filed and filed == published:
                return filed, "filed"
        return published, "published"

    event = parse_stamp(record.get("event_date"))
    if event:
        return event, "event"

    filed = parse_stamp(record.get("filing_date"))
    if filed:
        return filed, "filed"

    if mode != "timeline_evidence":
        captured = parse_stamp(record.get("captured_date"))
        if captured:
            return captured, "captured"

    return None, ""


def meaningful_date_text(record: dict[str, Any], *, mode: ChronologyMode = "default") -> str:
    """ISO-ish string for sort keys (newest first via reverse string sort)."""
    when, _origin = meaningful_stamp(record, mode=mode)
    if when is None:
        return ""
    return when.date().isoformat()


def development_stamp(record: dict[str, Any]) -> tuple[datetime | None, str]:
    """Compatibility alias used by Today / Landscape — default chronology."""
    return meaningful_stamp(record, mode="default")


def sort_key_newest_first(record: dict[str, Any], *, mode: ChronologyMode = "default") -> str:
    return meaningful_date_text(record, mode=mode)
