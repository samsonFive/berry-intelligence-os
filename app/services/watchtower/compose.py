"""Top-level composition entrypoint -- the one function routes call.

Reads the existing Radar cache (never fetches a provider itself -- refresh
`/radar/live` first if it's empty/stale, same as `/moves` already
requires), derives the Moves board from it, generates alerts, persists
them (idempotent upsert-by-id), and merges in read/dismiss/snooze state.
Cheap by construction: no live network fetch anywhere in this call chain,
so callers may call it directly rather than needing a second cache tier
(main.py wraps it in a short TTL guard purely to avoid redundant disk
writes under rapid repeated navigation -- see `_watchtower_cached()`)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from app.services.competitive_moves.board import compose_moves_board
from app.services.emerging_radar.cache import edition_from_cache
from app.services.watchlist import load_watches
from app.services.watchtower.digest import build_digest
from app.services.watchtower.generate import generate_alerts
from app.services.watchtower.store import load_alert_state, persist_alerts, with_state


def compose_watchtower(
    *,
    inbox_dir: Path,
    published_evidence: list[dict[str, Any]],
    strategic_questions: list[dict[str, Any]],
    entities: dict[str, dict[str, Any]],
    berry_labels: dict[str, str],
    market_repo: Any | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    watches = load_watches(inbox_dir)
    edition = edition_from_cache(inbox_dir=inbox_dir)
    developments = list(edition.developments) if edition else []
    board = compose_moves_board(developments, inbox_dir=inbox_dir)
    alerts = generate_alerts(
        watches=watches,
        developments=developments,
        board=board,
        market_repo=market_repo,
        published_evidence=published_evidence,
        strategic_questions=strategic_questions,
        entities=entities,
        berry_labels=berry_labels,
        now=now,
    )
    stored = persist_alerts(inbox_dir, alerts)
    stored = with_state(stored, load_alert_state(inbox_dir))
    return {
        "alerts": stored,
        "digest": build_digest(stored),
        "cache_status": edition.cache_status if edition else "empty",
        "radar_freshness_label": (
            edition.freshness_label if edition else "No Radar cache yet — open /radar to load emerging developments, then return here."
        ),
        "watch_count": len(watches),
        "watches": watches,
    }
