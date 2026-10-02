"""Restart-safe, idempotent alert persistence.

Two small shared JSON files, same atomic-write discipline as
`watchlist_state.json` (see AGENTS.md: "one shared, private, atomically
written JSON file, not a second per-object trust schema"):

- `alerts.json` -- current alert set, keyed by id (content, not read state).
  Regenerated in full on every `persist_alerts()` call and merged against
  what's on disk so a stable real-world (trigger, subject, related-thing)
  keeps the same id and its original `first_generated_at` forever -- this
  is what makes "ALERT UPDATED" (mission section 5) fall out for free: the
  same id just gets fresher content, never a duplicate row. An id that no
  longer appears (the underlying Development/Move fell out of the Radar
  cache) is dropped -- Watchtower reflects current live state, it doesn't
  accumulate forever.
- `alert_state.json` -- read/dismiss/snooze state, keyed by the same id.
  Never touched by regeneration; alert state != intelligence trust state
  (mission section 11), and it survives content updates on the same id.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.services.watchtower.models import ALERT_ACTIONS, ALERT_STATE_OPEN, Alert
from app.services.analyst_state_io import atomic_json, serialized_write

ALERTS_RELATIVE = Path("watchtower") / "alerts.json"
STATE_RELATIVE = Path("watchtower") / "alert_state.json"


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _alerts_path(inbox_dir: Path) -> Path:
    return Path(inbox_dir) / ALERTS_RELATIVE


def _state_path(inbox_dir: Path) -> Path:
    return Path(inbox_dir) / STATE_RELATIVE


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Saved alerts cannot be read. They have been left unchanged.") from exc
    if not isinstance(payload, dict):
        raise ValueError("Saved alerts cannot be read. They have been left unchanged.")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_json(path, {**_read_json(path), **payload})


def _read_alerts(inbox_dir: Path) -> dict[str, dict[str, Any]]:
    payload = _read_json(_alerts_path(inbox_dir))
    rows = payload.get("alerts")
    if "alerts" in payload and (not isinstance(rows, dict) or any(not isinstance(row, dict) or row.get("id") != key for key, row in rows.items())):
        raise ValueError("Saved alerts cannot be read. They have been left unchanged.")
    return rows or {}


def load_alerts(inbox_dir: Path) -> list[dict[str, Any]]:
    return list(_read_alerts(inbox_dir).values())


@serialized_write
def persist_alerts(inbox_dir: Path, alerts: list[Alert], *, now: str | None = None) -> list[dict[str, Any]]:
    existing = _read_alerts(inbox_dir)
    merged: dict[str, dict[str, Any]] = {}
    for alert in alerts:
        payload = alert.as_dict()
        prior = existing.get(payload["id"])
        if prior and prior.get("first_generated_at"):
            payload["first_generated_at"] = prior["first_generated_at"]
        merged[payload["id"]] = payload
    _write_json(_alerts_path(inbox_dir), {"alerts": merged, "generated_at": now or _now()})
    return list(merged.values())


def load_alert_state(inbox_dir: Path) -> dict[str, dict[str, Any]]:
    payload = _read_json(_state_path(inbox_dir))
    rows = payload.get("state")
    if "state" in payload and (not isinstance(rows, dict) or any(not isinstance(row, dict) for row in rows.values())):
        raise ValueError("Saved alert decisions cannot be read. They have been left unchanged.")
    return rows or {}


def alert_state_for(alert_id: str, state_map: dict[str, dict[str, Any]]) -> str:
    entry = state_map.get(alert_id) or {}
    value = str(entry.get("state") or ALERT_STATE_OPEN)
    return value


@serialized_write
def apply_alert_action(inbox_dir: Path, alert_id: str, action: str) -> dict[str, dict[str, Any]]:
    """Explicit-only, same discipline as `watchlist.mark_watch_seen`:
    called by a real user action, never as a side effect of rendering the
    Watchtower page. Unknown alert ids are accepted (idempotent no-op
    target) so a stale link never raises."""
    if action not in ALERT_ACTIONS:
        raise ValueError(f"unsupported alert action: {action!r}")
    state = load_alert_state(inbox_dir)
    prior = state.get(alert_id) or {}
    if "history" in prior and (not isinstance(prior["history"], list) or any(not isinstance(row, dict) for row in prior["history"])):
        raise ValueError("Saved alert history cannot be read. It has been left unchanged.")
    history = list(prior.get("history") or [])
    if prior:
        history.append({key: value for key, value in prior.items() if key != "history"})
    state[alert_id] = {**prior, "state": ALERT_ACTIONS[action], "updated_at": _now(), "history": history}
    _write_json(_state_path(inbox_dir), {"state": state})
    return state


def with_state(alerts: list[dict[str, Any]], state_map: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    for alert in alerts:
        alert["state"] = alert_state_for(alert["id"], state_map)
    return alerts
