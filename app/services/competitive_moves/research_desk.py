"""Research Desk read interface for Competitive Moves.

Ask Berry OS / Codex consumes this. Do not import their UI from here.

    from app.services.competitive_moves.research_desk import competitive_moves_for
    rows = competitive_moves_for(
        companies=["company-hortifrut"],
        geography="geography-peru",
        berries=["berry-blueberry"],
        move_types=["EXPANSION", "GENETICS_LAUNCH"],
        timeframe="30d",
    )
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from app.runtime_config import REPO_ROOT, resolve_inbox_dir
from app.services.competitive_moves.board import compose_moves_board
from app.services.competitive_moves.models import CompetitiveMove
from app.services.emerging_radar.models import Development, RADAR_WINDOW
from app.services.emerging_radar.research_desk import WINDOW_DAYS


def _parse_day(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _as_set(values: Iterable[str] | str | None) -> set[str]:
    if values is None or values == "":
        return set()
    if isinstance(values, str):
        return {values}
    return {str(item) for item in values if item}


def competitive_moves_for(
    companies: Iterable[str] | None = None,
    geography: Iterable[str] | str | None = None,
    berries: Iterable[str] | None = None,
    move_types: Iterable[str] | None = None,
    timeframe: str | None = None,
    *,
    inbox_dir: Path | None = None,
    developments: Iterable[Development] | None = None,
    moves: Iterable[CompetitiveMove] | None = None,
    today: date | None = None,
) -> list[dict[str, Any]]:
    """Read-only Competitive Moves derived from cached Radar Developments.

    Never fetches providers. Missing cache → empty list.
    """
    if moves is None:
        board = compose_moves_board(
            list(developments) if developments is not None else None,
            inbox_dir=inbox_dir or resolve_inbox_dir(REPO_ROOT),
        )
        rows = board.moves
    else:
        rows = list(moves)

    company_ids = _as_set(companies)
    geos = _as_set(geography)
    berry_ids = _as_set(berries)
    types = _as_set(move_types)
    days = WINDOW_DAYS.get(timeframe or "", WINDOW_DAYS.get(RADAR_WINDOW, 30))
    cutoff = (today or datetime.now(timezone.utc).date()) - timedelta(days=days)

    out: list[dict[str, Any]] = []
    for row in rows:
        if company_ids and row.company_id not in company_ids:
            continue
        if geos:
            from app.services.geography_hierarchy import geography_scope_match
            if not geography_scope_match(row.geography_ids, geos):
                continue
        if berry_ids and not berry_ids.intersection(row.berry_ids):
            continue
        if types and row.move_type not in types:
            continue
        stamp = _parse_day(row.latest_update or row.first_seen)
        if stamp is not None and stamp < cutoff:
            continue
        payload = row.as_dict()
        payload["trust_state"] = "LIVE / UNREVIEWED MOVE"
        out.append(payload)
    return out
