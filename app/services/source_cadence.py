"""Deterministic per-Source collection cadence and yield audit helpers.

The pipeline timer remains the single scheduler.  This module only decides
which Sources inside a due article/spoken pipeline are themselves due.  It
uses the existing discovery state and Source Health semantics; it never
polls a Source, changes trust, or makes a model call.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any, Iterable

from app.services.source_freshness import BLOCKED, FAILING, classify_source_freshness


UTC = timezone.utc
DEFAULT_POLICY_NAME = "source_collection_cadence.json"
DEFAULT_RETRY_SECONDS = 86400


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds")


def _instant(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def load_cadence_policy(path: Path | None) -> dict[str, Any]:
    if path is None or not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"cadence policy root must be an object: {path}")
    return payload


def _override(source_id: str, policy: dict[str, Any]) -> dict[str, Any]:
    overrides = policy.get("source_overrides")
    if not isinstance(overrides, dict):
        return {}
    value = overrides.get(source_id)
    return value if isinstance(value, dict) else {}


def cadence_seconds(source: dict[str, Any], policy: dict[str, Any]) -> int | None:
    """Resolve an actual collection interval without guessing from volume.

    Explicit source policy wins.  Otherwise the Source registry's existing
    update_cadence is mapped by the policy.  Discoverable event-driven
    Sources receive the policy's conservative fallback rather than silently
    starving inside a recurring pipeline.
    """

    selected = _override(str(source.get("id") or ""), policy)
    value = selected.get("cadence_seconds")
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    mapping = policy.get("cadence_by_update_cadence")
    if isinstance(mapping, dict):
        value = mapping.get(source.get("update_cadence"))
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            return value
    fallback = policy.get("discoverable_fallback_seconds")
    if isinstance(fallback, int) and not isinstance(fallback, bool) and fallback > 0:
        return fallback
    return None


def cadence_class(source: dict[str, Any], policy: dict[str, Any]) -> str:
    selected = _override(str(source.get("id") or ""), policy)
    explicit = selected.get("cadence_class")
    if isinstance(explicit, str) and explicit:
        return explicit
    seconds = cadence_seconds(source, policy)
    classes = policy.get("cadence_classes")
    if isinstance(classes, dict):
        for name, configured in classes.items():
            if isinstance(configured, int) and configured == seconds:
                return str(name)
    return "UNSCHEDULED"


@dataclass(frozen=True)
class SourceScheduleDecision:
    source_id: str
    due: bool
    cadence_seconds: int | None
    cadence_class: str
    health_state: str
    last_attempt_at: str | None
    last_success_at: str | None
    next_due: str | None
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def source_schedule_decision(
    source: dict[str, Any],
    *,
    discovery_state: dict[str, Any] | None,
    policy: dict[str, Any],
    now: datetime | None = None,
) -> SourceScheduleDecision:
    instant = (now or datetime.now(UTC)).astimezone(UTC)
    source_id = str(source.get("id") or "")
    interval = cadence_seconds(source, policy)
    health = classify_source_freshness(
        source,
        discovery_state=discovery_state,
        today=instant.date(),
    )
    last_attempt = _instant((discovery_state or {}).get("last_checked_at"))
    last_success = _instant((discovery_state or {}).get("last_success_at"))

    if health.state == BLOCKED:
        return SourceScheduleDecision(
            source_id, False, interval, "HEALTH_DEGRADED", health.state,
            _iso(last_attempt) if last_attempt else None,
            _iso(last_success) if last_success else None,
            None,
            "Source Health is BLOCKED; automatic polling is paused for operator resolution.",
        )
    if interval is None:
        return SourceScheduleDecision(
            source_id, False, None, "UNSCHEDULED", health.state,
            _iso(last_attempt) if last_attempt else None,
            _iso(last_success) if last_success else None,
            None,
            "No deterministic collection cadence is configured.",
        )

    if health.state == FAILING:
        retry = policy.get("retryable_failure_seconds", DEFAULT_RETRY_SECONDS)
        retry_seconds = retry if isinstance(retry, int) and retry > 0 else DEFAULT_RETRY_SECONDS
        effective = min(interval, retry_seconds)
        anchor = last_attempt
        reason_prefix = "Source Health is FAILING; bounded retry cadence applies"
        selected_class = "HEALTH_DEGRADED"
    else:
        effective = interval
        anchor = last_success
        reason_prefix = "Healthy Source cadence"
        selected_class = cadence_class(source, policy)

    if anchor is None:
        return SourceScheduleDecision(
            source_id, True, effective, selected_class, health.state,
            _iso(last_attempt) if last_attempt else None,
            _iso(last_success) if last_success else None,
            _iso(instant),
            f"{reason_prefix}; no completed cadence anchor exists, so the Source is due now.",
        )
    due_at = anchor + timedelta(seconds=effective)
    due = due_at <= instant
    return SourceScheduleDecision(
        source_id, due, effective, selected_class, health.state,
        _iso(last_attempt) if last_attempt else None,
        _iso(last_success) if last_success else None,
        _iso(due_at),
        f"{reason_prefix}; {'due now' if due else 'not due yet'}.",
    )


def select_due_sources(
    sources: Iterable[dict[str, Any]],
    *,
    discovery_states: dict[str, dict[str, Any] | None],
    policy: dict[str, Any],
    now: datetime | None = None,
) -> tuple[list[str], list[SourceScheduleDecision]]:
    decisions = [
        source_schedule_decision(
            source,
            discovery_state=discovery_states.get(str(source.get("id") or "")),
            policy=policy,
            now=now,
        )
        for source in sorted(sources, key=lambda row: str(row.get("id") or ""))
    ]
    return [decision.source_id for decision in decisions if decision.due], decisions


def maximum_safe_interval_seconds(
    *,
    observed_new_items: int,
    observation_seconds: float,
    feed_window_size: int | None,
    safety_factor: float = 2.0,
) -> int | None:
    """Return the feed-window ceiling, or None when evidence is insufficient.

    The first/backlog run must be excluded by the caller.  Capacity alone is
    never treated as publication frequency.  A factor of 2 means collection
    occurs before half of the visible window is expected to turn over.
    """

    if (
        observed_new_items <= 0
        or observation_seconds <= 0
        or not isinstance(feed_window_size, int)
        or isinstance(feed_window_size, bool)
        or feed_window_size <= 0
        or safety_factor <= 0
    ):
        return None
    items_per_second = observed_new_items / observation_seconds
    return max(1, int(feed_window_size / (items_per_second * safety_factor)))


def berry_coverage(sources: Iterable[dict[str, Any]], decisions: Iterable[SourceScheduleDecision]) -> dict[str, int]:
    """Count due-capable coverage without using observed berry volume.

    This is the explicit guard against lowering Raspberry/Blackberry cadence
    merely because Blueberry currently produces more records.
    """

    scheduled = {row.source_id for row in decisions if row.cadence_seconds is not None}
    coverage = {berry: 0 for berry in ("berry-blueberry", "berry-strawberry", "berry-raspberry", "berry-blackberry")}
    for source in sources:
        if source.get("id") not in scheduled:
            continue
        for berry in source.get("berry_ids") or []:
            if berry in coverage:
                coverage[berry] += 1
    return coverage


def request_attempts_per_day(sources: Iterable[dict[str, Any]], policy: dict[str, Any]) -> float:
    attempts = 0.0
    for source in sources:
        seconds = cadence_seconds(source, policy)
        if seconds is None:
            continue
        discovery = source.get("discovery") or {}
        request_count = len(discovery.get("feed_urls") or []) or (1 if discovery.get("feed_url") else 0)
        attempts += request_count * 86400 / seconds
    return attempts


def load_json_objects(folder: Path) -> list[dict[str, Any]]:
    if not folder.is_dir():
        return []
    records: list[dict[str, Any]] = []
    for path in sorted(folder.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            records.append(payload)
    return records


def build_cadence_audit(
    *,
    sources: list[dict[str, Any]],
    run_records: list[dict[str, Any]],
    drafts: list[dict[str, Any]],
    discovery_states: dict[str, dict[str, Any] | None],
    policy: dict[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build the evidence inventory; unavailable measurements stay unknown."""

    instant = (now or datetime.now(UTC)).astimezone(UTC)
    _, decisions = select_due_sources(
        sources, discovery_states=discovery_states, policy=policy, now=instant,
    )
    decision_by_id = {row.source_id: row for row in decisions}
    source_runs: dict[str, list[tuple[datetime | None, dict[str, Any]]]] = {}
    for run in run_records:
        at = _instant(run.get("started_at"))
        for result in run.get("sources") or []:
            if isinstance(result, dict) and isinstance(result.get("source_id"), str):
                source_runs.setdefault(result["source_id"], []).append((at, result))
    source_drafts: dict[str, list[dict[str, Any]]] = {}
    for draft in drafts:
        sid = draft.get("source_id")
        if isinstance(sid, str) and draft.get("evidence_role") == "publication_artifact":
            source_drafts.setdefault(sid, []).append(draft)

    rows: list[dict[str, Any]] = []
    evidence_sufficient = 0
    changed = 0
    for source in sorted(sources, key=lambda row: str(row.get("id") or "")):
        sid = str(source.get("id") or "")
        history = sorted(source_runs.get(sid, []), key=lambda pair: pair[0] or datetime.min.replace(tzinfo=UTC))
        repeats = history[1:] if history else []
        sufficient = len(history) >= 2
        evidence_sufficient += int(sufficient)
        observed_new = sum(int(result.get("new", 0) or 0) for _at, result in repeats)
        observed_known = sum(int(result.get("known", 0) or 0) for _at, result in history)
        observed_found = sum(int(result.get("found", 0) or 0) for _at, result in history)
        successful = sum(result.get("status") == "ok" for _at, result in history)
        failures = sum(result.get("status") not in {"ok", "planned"} for _at, result in history)
        duplicate_only = sum(int(result.get("new", 0) or 0) == 0 for _at, result in repeats)
        dated = [at for at, _result in history if at is not None]
        observation_seconds = (max(dated) - min(dated)).total_seconds() if len(dated) >= 2 else 0.0
        items_per_second = observed_new / observation_seconds if observation_seconds > 0 else None
        discovery = source.get("discovery") or {}
        state = discovery_states.get(sid) or {}
        feed_window = discovery.get("item_limit")
        if feed_window is None and isinstance(state.get("found"), int):
            feed_window = state["found"]
        safe_interval = maximum_safe_interval_seconds(
            observed_new_items=observed_new,
            observation_seconds=observation_seconds,
            feed_window_size=feed_window,
        )
        publication_drafts = source_drafts.get(sid, [])
        completeness: dict[str, int] = {}
        for draft in publication_drafts:
            value = (draft.get("source_completeness") or {}).get("class") or "UNKNOWN_NOT_RECORDED"
            completeness[value] = completeness.get(value, 0) + 1
        decision = decision_by_id[sid]
        override = _override(sid, policy)
        changed += int(bool(override.get("changes_current_cadence")))
        rows.append({
            "source_id": sid,
            "source": source.get("label") or source.get("name") or sid,
            "source_type": source.get("entity_types") or [],
            "berries": source.get("berry_ids") or [],
            "geographies": source.get("region_coverage") or [],
            "discovery_mechanism": discovery.get("adapter"),
            "current_cadence": source.get("update_cadence"),
            "recommended_cadence_seconds": decision.cadence_seconds,
            "cadence_class": decision.cadence_class,
            "recommendation_reason": override.get("reason") or "Retain the Source registry cadence; no stronger repeat-run evidence justifies a change.",
            "evidence_sufficient": sufficient,
            "recent_runs": len(history),
            "successful_runs": successful,
            "items_observed": observed_found,
            "new_items_excluding_initial_run": observed_new,
            "duplicate_items": observed_known,
            "new_items_per_repeat_run": round(observed_new / len(repeats), 3) if repeats else None,
            "observed_items_per_week": round(items_per_second * 604800, 3) if items_per_second is not None else None,
            "observed_items_per_30_days": round(items_per_second * 2592000, 3) if items_per_second is not None else None,
            "duplicate_only_repeat_run_rate": round(duplicate_only / len(repeats), 3) if repeats else None,
            "relevant_publication_drafts": len(publication_drafts),
            "relevant_publication_drafts_per_run": round(len(publication_drafts) / len(history), 3) if history else None,
            "rich_body": completeness,
            "failures": failures,
            "source_health": decision.health_state,
            "due": decision.due,
            "next_due": decision.next_due,
            "maximum_safe_interval_seconds": safe_interval,
            "feed_window_risk": bool(safe_interval and decision.cadence_seconds and decision.cadence_seconds > safe_interval),
        })

    return {
        "generated_at": _iso(instant),
        "sources_discoverable": len(sources),
        "sources_with_repeat_run_evidence": evidence_sufficient,
        "cadences_changed": changed,
        "cadences_unchanged": len(sources) - changed,
        "estimated_requests_per_day_after": round(request_attempts_per_day(sources, policy), 2),
        "berry_coverage": berry_coverage(sources, decisions),
        "sources": rows,
    }
