"""Research Desk read interface for Emerging Developments.

Ask Berry OS / Codex consumes this. Do not import their UI from here.

    from app.services.emerging_radar.research_desk import developments_for
    rows = developments_for(
        company_ids=["company-driscolls"],
        berry_ids=["berry-strawberry"],
        timeframe="7d",
        event_types=["PARTNERSHIP", "LICENSING"],
    )
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from app.runtime_config import REPO_ROOT, resolve_inbox_dir
from app.services.emerging_radar.cache import edition_from_cache
from app.services.emerging_radar.models import Development, RADAR_WINDOW

WINDOW_DAYS = {"24h": 1, "7d": 7, "30d": 30, "90d": 90}


def _parse_day(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def developments_for(
    company_ids: Iterable[str] | None = None,
    berry_ids: Iterable[str] | None = None,
    geography_ids: Iterable[str] | None = None,
    timeframe: str | None = None,
    event_types: Iterable[str] | None = None,
    *,
    inbox_dir: Path | None = None,
    developments: Iterable[Development] | None = None,
    today: date | None = None,
) -> list[dict[str, Any]]:
    """Read-only filter over cached LIVE Developments. Never fetches providers.

    Missing cache → empty list (not an error). Callers that need a live
    refresh should use run_radar_intelligence explicitly.
    """
    rows: list[Development]
    if developments is not None:
        rows = list(developments)
    else:
        edition = edition_from_cache(inbox_dir=inbox_dir or resolve_inbox_dir(REPO_ROOT))
        rows = list(edition.developments) if edition else []

    companies = {str(value) for value in (company_ids or []) if value}
    berries = {str(value) for value in (berry_ids or []) if value}
    geos = {str(value) for value in (geography_ids or []) if value}
    types = {str(value) for value in (event_types or []) if value}
    days = WINDOW_DAYS.get(timeframe or "", WINDOW_DAYS.get(RADAR_WINDOW, 30))
    cutoff = (today or datetime.now(timezone.utc).date()) - timedelta(days=days)

    out: list[dict[str, Any]] = []
    for row in rows:
        if companies and not companies.intersection(row.company_ids):
            continue
        if berries and not berries.intersection(row.berry_ids):
            continue
        if geos and not geos.intersection(row.geography_ids):
            continue
        if types and row.event_type not in types:
            continue
        stamp = _parse_day(row.event_date or row.latest_update)
        if stamp is not None and stamp < cutoff:
            continue
        payload = row.as_dict() if hasattr(row, "as_dict") else dict(row)
        payload["trust_state"] = "LIVE / UNREVIEWED DEVELOPMENT"
        out.append(payload)
    return out
