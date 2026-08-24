"""Today: recency-first authenticated landing. Not a trust object."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.services.morning_brief import brief_last_seen, _parse_stamp as parse_brief_stamp
from app.services.pipeline_health import build_pipeline_health
from app.services.variety_workspace import SOURCE_TYPE_LABEL

LATEST_WINDOW_DAYS = 14
WORTH_REVISITING_LIMIT = 8
DEVELOPING_SIGNALS_LIMIT = 6
BANDS = (
    ("today", "TODAY / LAST 24H"),
    ("last_3_days", "LAST 3 DAYS"),
    ("last_7_days", "LAST 7 DAYS"),
    ("last_14_days", "LAST 14 DAYS"),
)
SOURCE_CLASS = {
    "company_press_release": "COMPANY-REPORTED",
    "company_website": "COMPANY-REPORTED",
    "trade_press": "TRADE PRESS",
    "news_search": "TRADE PRESS",
    "patent_record": "REGISTRY",
    "plant_breeders_rights_record": "REGISTRY",
    "academic": "ACADEMIC",
    "industry_podcast": "SPOKEN MEDIA",
    "discovered_media": "DISCOVERED MEDIA",
}
FORBIDDEN_FRESHNESS = ("reacquired_at", "recovered_at", "reviewed_at", "indexed_at")


def _parse(value: Any) -> datetime | None:
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


def development_stamp(record: dict[str, Any]) -> tuple[datetime | None, str]:
    """Publication/event date first. Captured date is fallback only.

    Reacquisition, recovery, review, and index timestamps never count.
    """
    for key in FORBIDDEN_FRESHNESS:
        record.get(key)  # explicit: do not use
    published = _parse(record.get("published_date"))
    if published:
        return published, "published"
    event = _parse(record.get("event_date"))
    if event:
        return event, "event"
    captured = _parse(record.get("captured_date"))
    if captured:
        return captured, "captured"
    return None, ""


def age_label(when: datetime, *, now: datetime) -> str:
    delta = now - when
    seconds = max(0, int(delta.total_seconds()))
    if seconds < 90:
        return "JUST NOW"
    if seconds < 3600:
        minutes = max(1, seconds // 60)
        return f"{minutes} MINUTE{'S' if minutes != 1 else ''} AGO"
    if seconds < 24 * 3600 and when.date() == now.date():
        hours = max(1, seconds // 3600)
        return f"{hours} HOUR{'S' if hours != 1 else ''} AGO"
    if when.date() == now.date():
        return "TODAY"
    if when.date() == (now.date() - timedelta(days=1)):
        return "YESTERDAY"
    days = max(1, (now.date() - when.date()).days)
    if days < 14:
        return f"{days} DAYS AGO"
    return when.strftime("%b %d").upper()


def recency_band(when: datetime, *, now: datetime) -> str | None:
    days = (now.date() - when.date()).days
    hours = (now - when).total_seconds() / 3600
    if hours <= 24 or days <= 0:
        return "today"
    if days <= 3:
        return "last_3_days"
    if days <= 7:
        return "last_7_days"
    if days <= 14:
        return "last_14_days"
    return None


def _source_class(record: dict[str, Any]) -> str:
    source_type = str(record.get("source_type") or "")
    if source_type in SOURCE_CLASS:
        return SOURCE_CLASS[source_type]
    label = SOURCE_TYPE_LABEL.get(source_type)
    if label:
        return label.upper()
    return source_type.replace("_", " ").upper() if source_type else "SOURCE NOT RECORDED"


def _priority_rank(record: dict[str, Any]) -> int:
    reading = ((record.get("priority") or {}).get("reading") or {}).get("level") or "none"
    return {"high": 0, "medium": 1, "low": 2, "none": 3}.get(str(reading), 3)


def _berry_ok(record: dict[str, Any], berry_id: str) -> bool:
    if not berry_id or berry_id == "global":
        return True
    return berry_id in (record.get("berry_ids") or []) or berry_id in (record.get("market_ids") or [])


def _present_evidence(record: dict[str, Any], *, now: datetime) -> dict[str, Any]:
    when, origin = development_stamp(record)
    return {
        "id": record.get("id"),
        "kind": "evidence",
        "kind_label": "EVIDENCE",
        "title": record.get("title") or record.get("id"),
        "source_name": record.get("source_name") or "",
        "source_type": record.get("source_type") or "",
        "source_class": _source_class(record),
        "href": f"/intelligence/{record.get('id')}",
        "open_reader": True,
        "when": when.isoformat() if when else "",
        "when_origin": origin,
        "age_label": age_label(when, now=now) if when else "",
        "exact_date": when.strftime("%b %d, %Y") if when else "",
        "band": recency_band(when, now=now) if when else None,
        "priority_rank": _priority_rank(record),
    }


def _present_signal(record: dict[str, Any], *, now: datetime) -> dict[str, Any] | None:
    when = _parse(record.get("first_seen") or record.get("last_updated"))
    if not when:
        return None
    return {
        "id": record.get("id"),
        "kind": "signal",
        "kind_label": "SIGNAL",
        "title": record.get("title") or record.get("id"),
        "source_name": "",
        "source_class": "SIGNAL",
        "href": f"/signals/{record.get('id')}",
        "open_reader": False,
        "when": when.isoformat(),
        "when_origin": "signal",
        "age_label": age_label(when, now=now),
        "exact_date": when.strftime("%b %d, %Y"),
        "band": recency_band(when, now=now),
        "priority_rank": 1,
        "status": record.get("status") or "",
    }


def _present_assessment(record: dict[str, Any], *, now: datetime) -> dict[str, Any] | None:
    when = _parse(record.get("created_at"))
    if not when:
        return None
    return {
        "id": record.get("id"),
        "kind": "assessment",
        "kind_label": "ANALYST ASSESSMENT",
        "title": record.get("title") or record.get("id"),
        "source_name": "",
        "source_class": "ANALYST ASSESSMENT",
        "href": f"/assessments/{record.get('id')}",
        "open_reader": False,
        "when": when.isoformat(),
        "when_origin": "assessment",
        "age_label": age_label(when, now=now),
        "exact_date": when.strftime("%b %d, %Y"),
        "band": recency_band(when, now=now),
        "priority_rank": 1,
    }


def _freshness(
    *,
    data_dir: Path,
    inbox_dir: Path,
    sources: list[dict[str, Any]],
    published: list[dict[str, Any]],
    now: datetime,
) -> dict[str, Any]:
    config = data_dir / "configuration" / "collection_pipelines.json"
    last_collection = None
    degraded = False
    if config.is_file():
        health = build_pipeline_health(data_dir=data_dir, inbox_dir=inbox_dir, config_path=config, now=now)
        successes = [_parse(row.get("last_success")) for row in health.get("pipelines") or []]
        successes = [item for item in successes if item]
        if successes:
            last_collection = max(successes)
        if any(str(row.get("outcome") or "") == "FAILED" for row in health.get("pipelines") or []):
            degraded = True
    captured = [_parse(row.get("captured_date")) for row in published]
    captured = [item for item in captured if item]
    last_captured = max(captured) if captured else None
    discoverable = sum(1 for row in sources if (row.get("discovery") or {}).get("adapter"))
    current_through = None if degraded else (last_collection or last_captured)
    return {
        "degraded": degraded,
        "last_collection_at": last_collection.isoformat() if last_collection else None,
        "last_captured_at": last_captured.isoformat() if last_captured else None,
        "current_through": current_through.isoformat() if current_through else None,
        "discoverable_sources": discoverable,
        "now": now.isoformat(),
    }


def build_today(
    *,
    published: list[dict[str, Any]],
    signals: list[dict[str, Any]],
    assessments: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    inbox_dir: Path,
    data_dir: Path,
    berry_id: str = "",
    now: datetime | None = None,
) -> dict[str, Any]:
    instant = (now or datetime.now(UTC)).astimezone(UTC)
    rows: list[dict[str, Any]] = []
    older: list[dict[str, Any]] = []
    by_id = {str(record.get("id") or ""): record for record in published}
    for record in published:
        if record.get("status") not in {None, "published"}:
            continue
        if not _berry_ok(record, berry_id):
            continue
        row = _present_evidence(record, now=instant)
        if row["band"]:
            rows.append(row)
        elif row["when"]:
            older.append(row)
    for record in assessments:
        if not _berry_ok(record, berry_id):
            continue
        row = _present_assessment(record, now=instant)
        if row and row["band"]:
            rows.append(row)
    rows.sort(key=lambda row: (row["when"], -row["priority_rank"]), reverse=True)
    banded = []
    for key, label in BANDS:
        items = [row for row in rows if row["band"] == key]
        if items:
            banded.append({"key": key, "label": label, "rows": items})
    last_seen = parse_brief_stamp(brief_last_seen(inbox_dir))
    new_since = []
    if last_seen:
        for row in rows:
            if row["kind"] != "evidence":
                continue
            captured_at = _parse((by_id.get(str(row["id"])) or {}).get("captured_date"))
            if captured_at and captured_at > last_seen and row["when_origin"] != "published":
                new_since.append(row)
            elif captured_at and captured_at > last_seen and row["band"]:
                new_since.append(row)
    worth = sorted(older, key=lambda row: (row["priority_rank"], row["when"]))[:WORTH_REVISITING_LIMIT]
    developing = []
    for record in signals:
        if not _berry_ok(record, berry_id):
            continue
        row = _present_signal(record, now=instant)
        if row and row["band"]:
            developing.append(row)
    developing = sorted(developing, key=lambda row: row["when"], reverse=True)[:DEVELOPING_SIGNALS_LIMIT]
    latest_evidence = [row for row in rows if row["kind"] == "evidence"]
    quiet = not latest_evidence
    return {
        "latest_bands": banded,
        "latest_count": len(latest_evidence),
        "quiet": quiet,
        "new_since_last_visit": new_since[:10],
        "last_seen_at": last_seen.isoformat() if last_seen else None,
        "developing_signals": developing,
        "worth_revisiting": worth,
        "freshness": _freshness(
            data_dir=data_dir, inbox_dir=inbox_dir, sources=sources, published=published, now=instant
        ),
        "berry_id": berry_id,
        "window_days": LATEST_WINDOW_DAYS,
    }
