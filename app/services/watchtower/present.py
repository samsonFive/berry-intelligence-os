"""Page-shaping for /watchtower -- pure grouping/sorting over the alerts
`compose_watchtower()` already generated. No detection logic lives here.

Named states (mission section 7), all honestly computable from what's
already tracked: "new since last review" is deliberately folded into the
"needs attention" count rather than given its own section -- this V1 does
not track a separate per-user "last review" timestamp distinct from each
alert's own read/dismiss state, so a second freshness axis here would be
invented, not measured.
"""

from __future__ import annotations

from typing import Any

from app.services.watchtower.digest import needs_attention


def present_watchtower(data: dict[str, Any]) -> dict[str, Any]:
    alerts = data["alerts"]
    open_alerts = needs_attention(alerts)
    reviewed = sorted(
        (a for a in alerts if a.get("state", "open") != "open"),
        key=lambda a: str(a.get("generated_at") or ""),
        reverse=True,
    )
    return {
        "digest": data["digest"],
        "needs_attention": open_alerts,
        "market_moves": [a for a in open_alerts if a.get("trigger_type") == "MARKET_REALITY_CHANGE"],
        "competitor_moves": [a for a in open_alerts if a.get("group") == "competitor_moves"],
        "genetics_ip": [a for a in open_alerts if a.get("group") == "genetics_ip"],
        "watched_questions": [a for a in open_alerts if a.get("group") == "watched_questions"],
        "recently_reviewed": reviewed[:20],
        "cache_status": data["cache_status"],
        "radar_freshness_label": data["radar_freshness_label"],
        "watch_count": data["watch_count"],
        "watches": data["watches"],
        "total_alerts": len(alerts),
    }
