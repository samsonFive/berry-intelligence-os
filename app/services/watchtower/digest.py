"""Digest composition -- "YOUR WATCHTOWER: N things needing attention."

One shared function backs the /watchtower page's top block, Today's
restrained "Needs your attention" section, and (mission section 12/13) is
the same plain-data shape a future email/Teams/Slack delivery channel
would format -- no second synthesis architecture, no HTML baked in here.
"""

from __future__ import annotations

from typing import Any

from app.services.watchtower.models import PRIORITY_ATTENTION, PRIORITY_FYI, PRIORITY_HIGH

_PRIORITY_RANK = {PRIORITY_HIGH: 2, PRIORITY_ATTENTION: 1, PRIORITY_FYI: 0}


def _sort_key(alert: dict[str, Any]) -> tuple[int, str]:
    return (_PRIORITY_RANK.get(alert.get("priority"), 0), str(alert.get("event_at") or alert.get("generated_at") or ""))


def needs_attention(alerts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Open, un-snoozed alerts only -- read/dismissed/snoozed alerts are a
    stakeholder's own explicit call and never resurface here (mission
    section 11: alert state != intelligence trust state, but it IS the
    thing that decides whether this alert asks for attention again)."""
    return sorted((a for a in alerts if a.get("state", "open") == "open"), key=_sort_key, reverse=True)


def build_digest(alerts: list[dict[str, Any]], *, limit: int = 5) -> dict[str, Any]:
    open_alerts = needs_attention(alerts)
    top = open_alerts[:limit]
    return {
        "title": "Your Watchtower",
        "headline": (
            f"{len(open_alerts)} thing{'s' if len(open_alerts) != 1 else ''} needing attention"
            if open_alerts else "Nothing needs your attention right now"
        ),
        "total_open": len(open_alerts),
        "items": top,
        "high_count": sum(1 for a in open_alerts if a.get("priority") == PRIORITY_HIGH),
    }
