"""Executive Who is moving board — counts, recency, and move types. No scores."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.runtime_config import REPO_ROOT, resolve_inbox_dir
from app.services.competitive_moves.derive import derive_moves
from app.services.competitive_moves.models import (
    BOARD_SECTIONS,
    TRUST_LIVE_MOVE,
    CompanyMomentum,
    CompetitiveMove,
    MovesBoard,
)
from app.services.competitive_moves.patterns import detect_patterns
from app.services.emerging_radar.cache import edition_from_cache
from app.services.emerging_radar.models import Development


def _momentum(moves: list[CompetitiveMove]) -> list[CompanyMomentum]:
    grouped: dict[str, list[CompetitiveMove]] = {}
    for move in moves:
        grouped.setdefault(move.company_id, []).append(move)
    rows: list[CompanyMomentum] = []
    for company_id, items in grouped.items():
        types = tuple(dict.fromkeys(item.move_type for item in items))
        geos = tuple(dict.fromkeys(label for item in items for label in item.geography_labels))
        berries = tuple(dict.fromkeys(label for item in items for label in item.berry_labels))
        latest = max((item.latest_update for item in items), default="")
        rows.append(
            CompanyMomentum(
                company_id=company_id,
                company_name=items[0].company_name,
                move_count=len(items),
                move_types=types,
                latest_update=latest,
                geographies=geos[:6],
                berries=berries[:4],
                href=f"/moves/{company_id}",
            )
        )
    rows.sort(key=lambda row: (row.latest_update, row.move_count, len(row.move_types)), reverse=True)
    return rows


def _sections(moves: list[CompetitiveMove], momentum: list[CompanyMomentum]) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    for key, title, kicker, types in BOARD_SECTIONS:
        if key == "most_active":
            items = [row.as_dict() for row in momentum[:8] if row.move_count >= 1]
            if not items:
                continue
            sections.append({"key": key, "title": title, "kicker": kicker, "kind": "momentum", "rows": items})
            continue
        chosen = [move for move in moves if move.move_type in types][:8]
        if not chosen:
            continue
        sections.append(
            {
                "key": key,
                "title": title,
                "kicker": kicker,
                "kind": "moves",
                "rows": [move.as_dict() for move in chosen],
            }
        )
    return sections


def compose_moves_board(
    developments: list[Development] | None = None,
    *,
    inbox_dir: Path | None = None,
) -> MovesBoard:
    edition = None
    if developments is None:
        edition = edition_from_cache(inbox_dir=inbox_dir or resolve_inbox_dir(REPO_ROOT))
        developments = list(edition.developments) if edition else []
    moves = derive_moves(developments)
    patterns = detect_patterns(moves)
    momentum = _momentum(moves)
    featured = None
    if momentum:
        lead = momentum[0]
        featured_moves = [move for move in moves if move.company_id == lead.company_id]
        timeline = [row.as_dict() for move in featured_moves for row in move.timeline]
        timeline.sort(key=lambda row: row.get("date") or "", reverse=True)
        featured = {
            "company_id": lead.company_id,
            "company_name": lead.company_name,
            "href": lead.href,
            "entity_href": f"/entities/company/{lead.company_id}",
            "rows": timeline[:12],
        }
    generated = edition.generated_at if edition else datetime.now(timezone.utc).isoformat(timespec="seconds")
    freshness = edition.freshness_label if edition else "No Radar cache — open /radar to refresh live developments."
    return MovesBoard(
        generated_at=generated,
        freshness_label=freshness,
        cache_status=edition.cache_status if edition else "empty",
        trust_label=TRUST_LIVE_MOVE,
        moves=moves,
        patterns=patterns,
        momentum=momentum,
        sections=_sections(moves, momentum),
        featured_timeline=featured,
        stats={
            "moves": len(moves),
            "companies": len(momentum),
            "patterns": len(patterns),
            "developments": len(developments),
        },
    )


def moves_for_company(
    company_id: str,
    *,
    inbox_dir: Path | None = None,
    developments: list[Development] | None = None,
) -> list[CompetitiveMove]:
    board = compose_moves_board(developments, inbox_dir=inbox_dir)
    return [row for row in board.moves if row.company_id == company_id]
