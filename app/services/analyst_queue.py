"""Analyst workflow state for priority-tagged published Evidence.

Evidence.priority.* is inventory: why the item is on a page. This module
stores the analyst's resolution workflow in inbox/analyst_queue_state.json
and never mutates trusted Evidence records or deletes source history.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

STATE_FILENAME = "analyst_queue_state.json"

READING_DEFAULT = "unread"
READING_ACTIVE = {"unread", "saved"}
READING_OPEN = {"unread", "saved", "read"}
READING_RESOLVED = {"dismissed", "promoted"}
READING_ACTIONS = {
    "mark_read": "read",
    "keep": "saved",
    "dismiss": "dismissed",
    "promote": "promoted",
}

TESTING_DEFAULT = "needs_testing"
TESTING_ACTIVE = {"needs_testing"}
TESTING_RESOLVED = {"pass", "fail", "defer"}
TESTING_ACTIONS = {
    "pass": "pass",
    "fail": "fail",
    "defer": "defer",
    "reopen": "needs_testing",
}

MONITORING_DEFAULT = "active"
MONITORING_ACTIVE = {"active"}
MONITORING_VISIBLE = {"active", "snoozed"}
MONITORING_ACTIONS = {
    "pause": "snoozed",
    "resume": "active",
    "snooze": "snoozed",
    "stop": "stopped",
}
PROPOSAL_DEFAULT = "open"
PROPOSAL_ACTIONS = {"accept": "accepted", "reject": "rejected"}
PROPOSAL_LABELS = {"open": "Needs review", "accepted": "Accepted", "rejected": "Rejected"}
SIGNAL_ALERT_DEFAULT = "open"
SIGNAL_ALERT_ACTIONS = {"confirm": "confirmed", "dismiss": "dismissed"}
SIGNAL_ALERT_LABELS = {"open": "New", "confirmed": "Confirmed", "dismissed": "Dismissed"}

READING_LABELS = {
    "unread": "Unread",
    "saved": "Saved",
    "read": "Read",
    "dismissed": "Dismissed",
    "promoted": "Promoted",
}
TESTING_LABELS = {
    "needs_testing": "Needs testing",
    "pass": "Pass",
    "fail": "Fail",
    "defer": "Deferred",
}
MONITORING_LABELS = {
    "active": "Active",
    "snoozed": "Snoozed",
    "stopped": "Stopped",
}


def _empty_state() -> dict[str, dict[str, dict[str, Any]]]:
    return {"reading": {}, "testing": {}, "monitoring": {}, "proposals": {}, "signals": {}}


def state_path(inbox_dir: Path) -> Path:
    return Path(inbox_dir) / STATE_FILENAME


def load_state(inbox_dir: Path) -> dict[str, dict[str, dict[str, Any]]]:
    path = state_path(inbox_dir)
    if not path.is_file():
        return _empty_state()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty_state()
    if not isinstance(payload, dict):
        return _empty_state()
    out = _empty_state()
    for key in out:
        bucket = payload.get(key)
        if isinstance(bucket, dict):
            out[key] = {
                str(item_id): value
                for item_id, value in bucket.items()
                if isinstance(value, dict) and item_id
            }
    return out


def save_state(inbox_dir: Path, state: dict[str, dict[str, dict[str, Any]]]) -> None:
    path = state_path(inbox_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _entry(item_id: str, dimension: str, state: dict[str, dict[str, dict[str, Any]]]) -> dict[str, Any]:
    return (state.get(dimension) or {}).get(item_id) or {}


def reading_state(item_id: str, state: dict[str, dict[str, dict[str, Any]]]) -> str:
    value = str(_entry(item_id, "reading", state).get("state") or READING_DEFAULT)
    return value if value in READING_LABELS else READING_DEFAULT


def testing_state(item_id: str, state: dict[str, dict[str, dict[str, Any]]]) -> str:
    value = str(_entry(item_id, "testing", state).get("state") or TESTING_DEFAULT)
    return value if value in TESTING_LABELS else TESTING_DEFAULT


def monitoring_state(item_id: str, state: dict[str, dict[str, dict[str, Any]]]) -> str:
    entry = _entry(item_id, "monitoring", state)
    value = str(entry.get("state") or MONITORING_DEFAULT)
    if value == "snoozed":
        until = str(entry.get("snooze_until") or "")
        if until and until < date.today().isoformat():
            return MONITORING_DEFAULT
    return value if value in MONITORING_LABELS else MONITORING_DEFAULT


def proposal_state(item_id: str, state: dict[str, dict[str, dict[str, Any]]]) -> str:
    value = str(_entry(item_id, "proposals", state).get("state") or PROPOSAL_DEFAULT)
    return value if value in PROPOSAL_LABELS else PROPOSAL_DEFAULT


def signal_alert_state(item_id: str, state: dict[str, dict[str, dict[str, Any]]]) -> str:
    value = str(_entry(item_id, "signals", state).get("state") or SIGNAL_ALERT_DEFAULT)
    return value if value in SIGNAL_ALERT_LABELS else SIGNAL_ALERT_DEFAULT


def is_pending_proposal(record: dict[str, Any], state: dict[str, dict[str, dict[str, Any]]]) -> bool:
    if proposal_state(str(record.get("id") or ""), state) != PROPOSAL_DEFAULT:
        return False
    reviewer = str(record.get("reviewer") or "")
    return bool(record.get("ai_proposed")) or record.get("status") in {"proposed", "pending"} or "pending" in reviewer.casefold()


def is_open_signal_alert(record: dict[str, Any], state: dict[str, dict[str, dict[str, Any]]]) -> bool:
    return record.get("status") == "proposed" and signal_alert_state(str(record.get("id") or ""), state) == SIGNAL_ALERT_DEFAULT


def pending_position_proposals(
    recommendations: list[dict[str, Any]], inbox_dir: Path
) -> list[dict[str, Any]]:
    state = load_state(inbox_dir)
    return [record for record in recommendations if is_pending_proposal(record, state)]


def apply_action(
    inbox_dir: Path,
    *,
    dimension: str,
    item_id: str,
    action: str,
    reviewer: str = "",
) -> str:
    """Record an analyst decision. Returns the resulting workflow state."""

    state = load_state(inbox_dir)
    if dimension == "reading":
        if action == "bulk_read":
            action = "mark_read"
        next_state = READING_ACTIONS.get(action)
        if not next_state:
            raise ValueError(f"Unknown reading action: {action}")
        bucket = "reading"
    elif dimension == "testing":
        next_state = TESTING_ACTIONS.get(action)
        if not next_state:
            raise ValueError(f"Unknown testing action: {action}")
        bucket = "testing"
    elif dimension == "monitoring":
        next_state = MONITORING_ACTIONS.get(action)
        if not next_state:
            raise ValueError(f"Unknown monitoring action: {action}")
        bucket = "monitoring"
    elif dimension == "proposals":
        next_state = PROPOSAL_ACTIONS.get(action)
        if not next_state:
            raise ValueError(f"Unknown proposal action: {action}")
        bucket = "proposals"
    elif dimension == "signals":
        next_state = SIGNAL_ALERT_ACTIONS.get(action)
        if not next_state:
            raise ValueError(f"Unknown signal-alert action: {action}")
        bucket = "signals"
    else:
        raise ValueError(f"No workflow actions on {dimension}")
    payload: dict[str, Any] = {
        "state": next_state,
        "updated_at": _now(),
        "reviewer": reviewer,
        "action": action,
    }
    if dimension == "monitoring" and action in {"snooze", "pause"}:
        days = 7 if action == "snooze" else 1
        payload["snooze_until"] = (date.today() + timedelta(days=days)).isoformat()
    state.setdefault(bucket, {})[item_id] = payload
    save_state(inbox_dir, state)
    return next_state


def bulk_mark_read(inbox_dir: Path, item_ids: list[str], *, reviewer: str = "") -> int:
    count = 0
    for item_id in item_ids:
        if not item_id:
            continue
        apply_action(inbox_dir, dimension="reading", item_id=item_id, action="mark_read", reviewer=reviewer)
        count += 1
    return count


def _company_and_berry(
    record: dict[str, Any],
    entities: dict[str, dict[str, Any]],
    berry_labels: dict[str, str],
) -> tuple[str, str]:
    companies: list[str] = []
    berries: list[str] = []
    for entity_id in record.get("entity_ids") or []:
        entity = entities.get(entity_id) or {}
        name = str(entity.get("name") or entity_id)
        kind = entity.get("entity_type")
        if kind == "company" and name not in companies:
            companies.append(name)
        if kind == "berry" and name not in berries:
            berries.append(name)
    for berry_id in record.get("berry_ids") or []:
        name = berry_labels.get(berry_id) or berry_id
        if name not in berries:
            berries.append(name)
    return (", ".join(companies) or "—", ", ".join(berries) or "—")


def _signals_for_evidence(record_id: str, signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    linked = [signal for signal in signals if record_id in (signal.get("evidence_ids") or [])]
    linked.sort(key=lambda signal: str(signal.get("proposed_at") or signal.get("created_at") or ""), reverse=True)
    return linked


def present_queue_item(
    record: dict[str, Any],
    *,
    dimension: str,
    state: dict[str, dict[str, dict[str, Any]]],
    entities: dict[str, dict[str, Any]],
    berry_labels: dict[str, str],
    signals: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    item_id = str(record.get("id") or "")
    priority = (record.get("priority") or {}).get(dimension) or {}
    companies, berries = _company_and_berry(record, entities, berry_labels)
    linked = [
        str((entities.get(entity_id) or {}).get("name") or entity_id)
        for entity_id in (record.get("entity_ids") or [])
        if entity_id
    ]
    row: dict[str, Any] = {
        **record,
        "workflow_id": item_id,
        "why": priority.get("rationale") or record.get("why_it_matters") or "",
        "priority_level": priority.get("level") or "none",
        "linked_entity_names": [name for name in linked if name],
        "company_names": companies,
        "berry_names": berries,
        "href": f"/intelligence/{item_id}",
        "evidence_href": f"/evidence/{item_id}",
        "date": record.get("published_date") or record.get("captured_date") or "",
    }
    if dimension == "reading":
        status = reading_state(item_id, state)
        row["workflow_state"] = status
        row["workflow_label"] = READING_LABELS[status]
        row["is_active"] = status in READING_OPEN
        row["needs_consume"] = status in READING_ACTIVE
    elif dimension == "testing":
        status = testing_state(item_id, state)
        row["workflow_state"] = status
        row["workflow_label"] = TESTING_LABELS[status]
        row["is_active"] = status in TESTING_ACTIVE
        row["needs_consume"] = status in TESTING_ACTIVE
    elif dimension == "monitoring":
        status = monitoring_state(item_id, state)
        related = _signals_for_evidence(item_id, signals or [])
        latest = related[0] if related else None
        row["workflow_state"] = status
        row["workflow_label"] = MONITORING_LABELS[status]
        row["is_active"] = status in MONITORING_VISIBLE
        row["needs_consume"] = False
        row["last_signal"] = (latest or {}).get("title") or ""
        row["last_signal_at"] = (latest or {}).get("proposed_at") or (latest or {}).get("created_at") or ""
        row["related_signals"] = related[:3]
        row["watch_what"] = record.get("title") or item_id
        row["watch_why"] = row["why"]
        row["last_check"] = row["date"]
    else:
        row["workflow_state"] = "inventory"
        row["workflow_label"] = "Tagged evidence"
        row["is_active"] = True
        row["needs_consume"] = False
    return row


def work_counts(
    *,
    inbox_dir: Path,
    published: list[dict[str, Any]],
    signals: list[dict[str, Any]] | None = None,
) -> dict[str, int]:
    """Nav-facing counts: action vs inventory."""

    state = load_state(inbox_dir)
    tagged = {
        dimension: [record for record in published if (record.get("priority") or {}).get(dimension, {}).get("level", "none") != "none"]
        for dimension in ("reading", "testing", "commercial_position", "monitoring")
    }
    reading_action = sum(1 for record in tagged["reading"] if reading_state(str(record.get("id")), state) in READING_ACTIVE)
    testing_action = sum(1 for record in tagged["testing"] if testing_state(str(record.get("id")), state) in TESTING_ACTIVE)
    monitoring_active = sum(
        1 for record in tagged["monitoring"] if monitoring_state(str(record.get("id")), state) in MONITORING_ACTIVE
    )
    proposed_signals = [signal for signal in (signals or []) if is_open_signal_alert(signal, state)]
    return {
        "reading_action": reading_action,
        "testing_action": testing_action,
        "commercial_inventory": len(tagged["commercial_position"]),
        "monitoring_inventory": monitoring_active,
        "signal_alerts": len(proposed_signals),
        "tagged_reading": len(tagged["reading"]),
        "tagged_testing": len(tagged["testing"]),
        "tagged_monitoring": len(tagged["monitoring"]),
    }


def build_dimension_page(
    *,
    dimension: str,
    records: list[dict[str, Any]],
    inbox_dir: Path,
    entities: dict[str, dict[str, Any]],
    berry_labels: dict[str, str],
    signals: list[dict[str, Any]] | None = None,
    show_completed: bool = False,
) -> dict[str, Any]:
    state = load_state(inbox_dir)
    presented = [
        present_queue_item(
            record,
            dimension=dimension,
            state=state,
            entities=entities,
            berry_labels=berry_labels,
            signals=signals,
        )
        for record in records
    ]
    active = [item for item in presented if item.get("is_active")]
    completed = [item for item in presented if not item.get("is_active")]
    visible = presented if show_completed else active
    needs_consume_count = sum(1 for item in presented if item.get("needs_consume"))
    inventory_count = sum(1 for item in presented if item.get("workflow_state") == "active")
    if dimension == "reading":
        purpose = "Items you have not finished consuming. Marking read does not delete the source record."
        label = "Reading Queue"
        eyebrow = "UNREAD AND SAVED — THEN DISMISS OR PROMOTE"
    elif dimension == "testing":
        purpose = (
            "Independent verification of claims in trusted evidence — field, trial, or source-check work. "
            "This is not model-qualification or extraction testing."
        )
        label = "Claim testing"
        eyebrow = "SYSTEM QUALITY — VERIFY THE CLAIM"
    elif dimension == "commercial_position":
        purpose = (
            "Trusted evidence tagged for commercial-position thinking. This is an intelligence view, "
            "not a queue of tasks to clear. These records are not first-class Position objects."
        )
        label = "Commercial positions"
        eyebrow = "ACTIVE INTELLIGENCE — NOT A QUEUE"
        visible = presented
        active = presented
        completed = []
    else:
        purpose = (
            "Intentional watches on tagged evidence. The count is active monitors, "
            "not items you need to clear."
        )
        label = "Watches"
        eyebrow = "WHAT WE ARE WATCHING"
    return {
        "dimension": dimension,
        "label": label,
        "eyebrow": eyebrow,
        "purpose": purpose,
        "items": visible,
        "active_items": active,
        "completed_items": completed,
        "active_count": len(active),
        "completed_count": len(completed),
        "needs_consume_count": needs_consume_count,
        "inventory_count": inventory_count if dimension == "monitoring" else len(presented),
        "show_completed": show_completed,
        "tagged_count": len(presented),
    }
