"""Today: recency-first authenticated landing. Not a trust object."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.services.chronology import (
    FORBIDDEN_FRESHNESS,
    date_label,
    development_stamp,
    parse_stamp as _parse,
)
from app.services.morning_brief import brief_last_seen, _parse_stamp as parse_brief_stamp
from app.services.freshness_assurance import build_runtime_freshness
from app.services.guided_analyst import freshness_clock_label
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

# Re-export for callers/tests that imported these from today.
__all__ = [
    "FORBIDDEN_FRESHNESS",
    "build_today",
    "date_label",
    "development_stamp",
]


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


def _date_fields(when: datetime | None, origin: str, *, now: datetime) -> dict[str, Any]:
    basis = date_label(origin) if origin else ""
    if when is None:
        return {
            "when": "",
            "when_origin": origin,
            "age_label": "Date unknown",
            "exact_date": "",
            "date_basis_label": basis or "Date unknown",
            "band": None,
        }
    return {
        "when": when.isoformat(),
        "when_origin": origin,
        "age_label": age_label(when, now=now),
        "exact_date": when.strftime("%b %d, %Y"),
        "date_basis_label": basis or "Date unknown",
        "band": recency_band(when, now=now),
    }


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
        **_date_fields(when, origin, now=now),
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
        **_date_fields(when, "first_seen", now=now),
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
        **_date_fields(when, "created_at", now=now),
        "priority_rank": 1,
    }


def _freshness(
    *,
    data_dir: Path,
    inbox_dir: Path,
    sources: list[dict[str, Any]],
    now: datetime,
) -> dict[str, Any]:
    contract = build_runtime_freshness(
        data_dir=data_dir,
        inbox_dir=inbox_dir,
        sources=sources,
        now=now,
    )
    # Compatibility aliases keep the Today template presentation-only while
    # its authoritative values come from the shared operational contract.
    contract.update({
        "degraded": contract["system_state"] != "CURRENT",
        "last_collection_at": contract["last_successful_collection"],
        "last_captured_at": contract["last_new_intelligence"],
        "last_run_at": contract.get("last_collection_attempt") or contract.get("last_scheduler_run"),
        "discoverable_sources": contract["counts"]["scheduled_sources"],
        "now": now.isoformat(),
        "current_through_label": freshness_clock_label(contract.get("current_through")),
        "last_collection_label": freshness_clock_label(contract.get("last_successful_collection")),
        "last_captured_label": freshness_clock_label(contract.get("last_new_intelligence")),
        "last_run_label": freshness_clock_label(
            contract.get("last_collection_attempt") or contract.get("last_scheduler_run")
        ),
    })
    return contract


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
    if last_seen and last_seen.tzinfo is None:
        # morning_brief._parse_stamp deliberately returns a naive stamp
        # (its own callers compare it against other naive values); _parse
        # (chronology.parse_stamp) below always returns UTC-aware. Only
        # this local comparison needs the two reconciled -- attach UTC
        # here rather than changing either shared parser's return type,
        # which other callers rely on.
        last_seen = last_seen.replace(tzinfo=UTC)
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
            data_dir=data_dir, inbox_dir=inbox_dir, sources=sources, now=instant
        ),
        "berry_id": berry_id,
        "window_days": LATEST_WINDOW_DAYS,
    }
