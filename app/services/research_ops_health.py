"""Research Ops health — inspectable coverage without secret values.

Lane errors are reduced to provider + exception class. Watch counts come
from the seed roster. Cluster stats come from the cached Today bundle.
"""

from __future__ import annotations

import re
from typing import Any

_SECRETISH = re.compile(
    r"(?i)(api[_-]?key|token|secret|password|bearer|authorization)\s*[:=]\s*\S+"
)
_CLASS_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]+$")


def public_lane_errors(errors: list[dict[str, Any]] | None) -> list[dict[str, str]]:
    """Provider + error class only. Never echo key material."""
    rows: list[dict[str, str]] = []
    for raw in errors or []:
        if not isinstance(raw, dict):
            continue
        provider = str(raw.get("provider") or "unknown")[:64]
        explicit = str(raw.get("error_class") or "").strip()
        message = _SECRETISH.sub("[redacted]", str(raw.get("error") or ""))
        parsed = message.split(":", 1)[0].strip()
        error_class = explicit or parsed or "Error"
        if not _CLASS_RE.match(error_class):
            error_class = "Error"
        rows.append({"provider": provider, "error_class": error_class})
    return rows


def cluster_stats(records: list[dict[str, Any]] | None) -> dict[str, int]:
    rows = [row for row in (records or []) if isinstance(row, dict)]
    clustered = [row for row in rows if int(row.get("cluster_size") or 1) > 1]
    extra = sum(max(int(row.get("cluster_size") or 1) - 1, 0) for row in clustered)
    return {
        "stories": len(rows),
        "clustered_stories": len(clustered),
        "extra_lane_hits": extra,
    }


def watch_coverage(
    counts: dict[str, Any],
    *,
    fetched_at: str = "",
    lane_errors: list[dict[str, str]] | None = None,
    lanes: list[str] | None = None,
) -> dict[str, Any]:
    errors = {row["provider"]: row["error_class"] for row in (lane_errors or []) if row.get("provider")}
    lane_rows = []
    for name in lanes or []:
        lane_rows.append(
            {
                "provider": name,
                "last_attempt_at": fetched_at,
                "last_success_at": "" if name in errors else fetched_at,
                "last_error_class": errors.get(name, ""),
                "coverage_state": "error" if name in errors else ("fetched" if fetched_at else "idle"),
            }
        )
    for provider, error_class in errors.items():
        if provider in {row["provider"] for row in lane_rows}:
            continue
        lane_rows.append(
            {
                "provider": provider,
                "last_attempt_at": fetched_at,
                "last_success_at": "",
                "last_error_class": error_class,
                "coverage_state": "error",
            }
        )
    any_success = any(row["coverage_state"] == "fetched" for row in lane_rows)
    return {
        "official_site_watches": int(counts.get("official_site_watches") or 0),
        "mention_watches": int(counts.get("mention_watches") or 0),
        "tracked_companies": int(counts.get("tracked_companies") or 0),
        "last_attempt_at": fetched_at,
        "last_success_at": fetched_at if any_success or (fetched_at and not errors) else "",
        "coverage_state": "inspectable",
        "lanes": lane_rows,
    }


def research_ops_health(
    *,
    bundle: dict[str, Any] | None,
    counts: dict[str, Any],
) -> dict[str, Any]:
    payload = bundle or {}
    records = [row for row in (payload.get("records") or []) if isinstance(row, dict)]
    errors = public_lane_errors(payload.get("lane_errors") or [])
    stats = payload.get("stats") if isinstance(payload.get("stats"), dict) else {}
    return {
        "lane_errors": errors,
        "clusters": cluster_stats(records),
        "watches": watch_coverage(
            counts,
            fetched_at=str(payload.get("fetched_at") or ""),
            lane_errors=errors,
            lanes=[str(name) for name in (payload.get("lanes") or [])],
        ),
        "same_day": int(stats.get("same_day") or 0),
        "week": int(stats.get("week") or 0),
    }
