"""Inbox cache for the Emerging Developments Radar.

LIVE plane only. Never Evidence. Freshness is explicit.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.runtime_config import REPO_ROOT, resolve_inbox_dir
from app.services.emerging_radar.models import (
    CACHE_TTL_SECONDS,
    RadarEdition,
    development_from_dict,
)

CACHE_RELATIVE = Path("operations") / "radar" / "cache.json"
WATCH_EVENTS_RELATIVE = Path("operations") / "radar" / "watchlist_events.jsonl"


def cache_path(inbox_dir: Path | None = None) -> Path:
    root = inbox_dir or resolve_inbox_dir(REPO_ROOT)
    return root / CACHE_RELATIVE


def watch_events_path(inbox_dir: Path | None = None) -> Path:
    root = inbox_dir or resolve_inbox_dir(REPO_ROOT)
    return root / WATCH_EVENTS_RELATIVE


def _iso(moment: datetime | None = None) -> str:
    return (moment or datetime.now(timezone.utc)).isoformat(timespec="seconds")


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def empty_cache() -> dict[str, Any]:
    return {
        "schema": "emerging-radar-cache-v1",
        "generated_at": None,
        "expires_at": None,
        "status": "empty",
        "reason": "Radar has not been refreshed yet",
        "edition": None,
    }


def load_cache(inbox_dir: Path | None = None) -> dict[str, Any]:
    path = cache_path(inbox_dir)
    if not path.is_file():
        return empty_cache()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty_cache()
    return payload if isinstance(payload, dict) else empty_cache()


def write_cache(edition: RadarEdition, *, inbox_dir: Path | None = None, ttl_seconds: int = CACHE_TTL_SECONDS) -> Path:
    generated = _parse(edition.generated_at) or datetime.now(timezone.utc)
    expires = generated + timedelta(seconds=ttl_seconds)
    edition.expires_at = expires.isoformat(timespec="seconds")
    edition.cache_status = "fresh"
    path = cache_path(inbox_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {
        "schema": "emerging-radar-cache-v1",
        "generated_at": edition.generated_at,
        "expires_at": edition.expires_at,
        "status": "fresh",
        "edition": edition.as_dict(),
    }
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(body, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)
    return path


def cache_is_fresh(payload: dict[str, Any] | None = None, *, now: datetime | None = None, inbox_dir: Path | None = None) -> bool:
    row = payload if payload is not None else load_cache(inbox_dir)
    expires = _parse(row.get("expires_at"))
    generated = _parse(row.get("generated_at"))
    if expires is None or generated is None or not row.get("edition"):
        return False
    current = now or datetime.now(timezone.utc)
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current < expires


def edition_from_cache(payload: dict[str, Any] | None = None, *, inbox_dir: Path | None = None, now: datetime | None = None) -> RadarEdition | None:
    row = payload if payload is not None else load_cache(inbox_dir)
    raw = row.get("edition")
    if not isinstance(raw, dict):
        return None
    from app.services.emerging_radar.models import Development, RadarEdition as Edition

    developments = [development_from_dict(item) for item in raw.get("developments") or []]
    from app.services.emerging_radar.tag_audit import rehydrate_developments

    rehydrate_developments(developments)
    current = now or datetime.now(timezone.utc)
    fresh = cache_is_fresh(row, now=current)
    status = "fresh" if fresh else "stale"
    generated = raw.get("generated_at") or row.get("generated_at") or ""
    freshness = f"Refreshed {str(generated).replace('T', ' ')[:16]} UTC"
    if not fresh:
        freshness += " · cache stale — refresh in progress or overdue"
    return Edition(
        generated_at=str(generated),
        window=str(raw.get("window") or "30d"),
        latency_seconds=float(raw.get("latency_seconds") or 0),
        freshness_label=freshness,
        cache_status=status,
        expires_at=row.get("expires_at"),
        trust_label=str(raw.get("trust_label") or "LIVE / UNREVIEWED DEVELOPMENT"),
        developments=developments,
        sections=list(raw.get("sections") or []),
        stats=dict(raw.get("stats") or {}),
        query_failures=list(raw.get("query_failures") or []),
        provider_telemetry=dict(raw.get("provider_telemetry") or {}),
    )


def append_watch_events(events: list[dict[str, Any]], *, inbox_dir: Path | None = None) -> Path | None:
    if not events:
        return None
    path = watch_events_path(inbox_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: set[tuple[str, str, str]] = set()
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            existing.add((str(row.get("development_id")), str(row.get("watch_type")), str(row.get("object_id"))))
    with path.open("a", encoding="utf-8") as handle:
        for event in events:
            key = (str(event.get("development_id")), str(event.get("watch_type")), str(event.get("object_id")))
            if key in existing:
                continue
            event = {**event, "emitted_at": event.get("emitted_at") or _iso()}
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
            existing.add(key)
    return path


def previous_developments(inbox_dir: Path | None = None) -> list:
    edition = edition_from_cache(inbox_dir=inbox_dir)
    return list(edition.developments) if edition else []
