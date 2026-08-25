"""Deterministic collection freshness assurance built on Source Health/cadence.

This module does not define another fetch-health model.  It consumes the
existing per-Source discovery state and cadence policy, then adds the missing
system contract: attempt/success/new-intelligence clocks, overdue grace,
coverage rollups, and explainable operational alert conditions.
"""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from functools import lru_cache
import json
import math
from pathlib import Path
from typing import Any, Iterable

from app.services.media_discovery import read_source_discovery_state
from app.services.source_cadence import cadence_seconds, load_cadence_policy, load_json_objects, maximum_safe_interval_seconds
from app.services.source_freshness import BLOCKED as SOURCE_HEALTH_BLOCKED
from app.services.source_freshness import classify_source_freshness
from app.services.source_lifecycle import is_scheduled_coverage


UTC = timezone.utc

CURRENT_ACTIVE = "CURRENT_ACTIVE"
CURRENT_QUIET = "CURRENT_QUIET"
DUE = "DUE"
OVERDUE = "OVERDUE"
RETRYING = "RETRYING"
BLOCKED = "BLOCKED"
FAILING = "FAILING"
NEVER_RUN = "NEVER_RUN"
INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"

SYSTEM_CURRENT = "CURRENT"
SYSTEM_DEGRADED = "DEGRADED"

CURRENT_STATES = {CURRENT_ACTIVE, CURRENT_QUIET}
DEGRADED_STATES = {OVERDUE, FAILING, BLOCKED, NEVER_RUN, INSUFFICIENT_HISTORY}
DEFAULT_HISTORY_PER_SOURCE = 50
FAILURE_THRESHOLD = 2
ZERO_NEW_DRIFT_RUNS = 3
PRIOR_PRODUCTIVE_RUNS = 3
RICH_BODY_DRIFT_DRAFTS = 3

ALERT_CONDITION_NAMES = {
    "MULTIPLE_CONSECUTIVE_FAILURES": "SOURCE_FAILURE_STREAK",
    "COVERAGE_DEGRADED": "COLLECTION_COVERAGE_DEGRADED",
    "NO_SUCCESSFUL_COLLECTION_RUN": "NO_SUCCESSFUL_COLLECTION",
}


def _utc(value: datetime) -> datetime:
    """Normalize aware timestamps and treat schema-compatible naive values as UTC."""

    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _dt(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip())
    except ValueError:
        return None
    return _utc(parsed)


def _iso(value: datetime | None) -> str | None:
    return value.astimezone(UTC).isoformat(timespec="seconds") if value else None


def _run_at(run: dict[str, Any]) -> datetime | None:
    return _dt(run.get("completed_at")) or _dt(run.get("started_at")) or _dt(run.get("at"))


def _result_new(result: dict[str, Any]) -> int:
    new = int(result.get("new", 0) or 0)
    historical = int(result.get("historical_backlog", 0) or 0)
    return max(0, new - historical)


def _source_histories(
    run_records: Iterable[dict[str, Any]], *, limit: int = DEFAULT_HISTORY_PER_SOURCE,
) -> dict[str, list[tuple[datetime, dict[str, Any]]]]:
    histories: dict[str, list[tuple[datetime, dict[str, Any]]]] = defaultdict(list)
    for run in run_records:
        at = _run_at(run)
        if at is None:
            continue
        for result in run.get("sources") or []:
            if not isinstance(result, dict) or not isinstance(result.get("source_id"), str):
                continue
            histories[result["source_id"]].append((at, result))
    for source_id, rows in histories.items():
        rows.sort(key=lambda row: row[0])
        histories[source_id] = rows[-limit:]
    return dict(histories)


def _consecutive_failures(history: list[tuple[datetime, dict[str, Any]]]) -> int:
    count = 0
    for _at, result in reversed(history):
        if result.get("status") in {"ok", "planned"}:
            break
        count += 1
    return count


def _last_success_result(history: list[tuple[datetime, dict[str, Any]]]) -> dict[str, Any] | None:
    return next((result for _at, result in reversed(history) if result.get("status") == "ok"), None)


def _source_type(source: dict[str, Any]) -> str:
    adapter = str((source.get("discovery") or {}).get("adapter") or "")
    entity_types = {str(value) for value in source.get("entity_types") or []}
    label = str(source.get("label") or "").casefold()
    if source.get("linked_competitor_ids") or "newsroom" in label:
        return "company_newsroom"
    if adapter in {"podcast_rss", "youtube_feed"}:
        return "spoken_video"
    if "government_regulatory" in entity_types or adapter in {
        "government_register_json", "government_recall_json", "government_alert_json", "sec_edgar_search_json",
    }:
        return "registry_government"
    if "trade_press" in entity_types:
        return "trade_publisher"
    if entity_types & {"trade_association", "industry_association"}:
        return "association"
    if entity_types & {"academic_journal", "research_institution", "breeding_program"}:
        return "academic_research"
    return "other"


def _new_by_source(discovered_items: Iterable[dict[str, Any]]) -> dict[str, datetime]:
    latest: dict[str, datetime] = {}
    for item in discovered_items:
        if item.get("historical_backlog"):
            continue
        source_id = item.get("source_id")
        captured = _dt(item.get("first_seen_at"))
        if not isinstance(source_id, str) or captured is None:
            continue
        if source_id not in latest or captured > latest[source_id]:
            latest[source_id] = captured
    return latest


def _historical_repair(record: dict[str, Any]) -> bool:
    if any(record.get(key) for key in ("historical_backlog", "reacquisition", "source_fidelity_recovery")):
        return True
    text = " ".join(str(record.get(key) or "") for key in ("workflow", "created_by", "acquisition_method"))
    return "reacquisition" in text.casefold() or "source_fidelity" in text.casefold()


def _draft_at(record: dict[str, Any]) -> datetime | None:
    return _dt(record.get("created_at")) or _dt(record.get("first_seen_at")) or _dt(record.get("captured_date"))


def _last_rich_draft(drafts: Iterable[dict[str, Any]]) -> datetime | None:
    timestamps = [
        at
        for record in drafts
        if record.get("evidence_role") == "publication_artifact"
        and (record.get("source_completeness") or {}).get("class") == "FULL_ARTICLE"
        and not _historical_repair(record)
        and (at := _draft_at(record)) is not None
    ]
    return max(timestamps) if timestamps else None


def _latest_successful_collection(run_records: Iterable[dict[str, Any]]) -> datetime | None:
    successful: list[datetime] = []
    for run in run_records:
        if not any(
            isinstance(result, dict) and result.get("status") == "ok"
            for result in run.get("sources") or []
        ):
            continue
        if (at := _run_at(run)) is not None:
            successful.append(at)
    return max(successful) if successful else None


def _latest_scheduler_run(scheduler_runs: Iterable[dict[str, Any]]) -> datetime | None:
    timestamps: list[datetime] = []
    for run in scheduler_runs:
        values = [run.get("generated_at"), run.get("completed_at"), run.get("started_at")]
        parsed = [_dt(value) for value in values]
        if (at := next((value for value in parsed if value is not None), None)) is not None:
            timestamps.append(at)
    return max(timestamps) if timestamps else None


def _coverage_summary(source_rows: list[dict[str, Any]]) -> dict[str, Any]:
    states = defaultdict(int)
    successes: list[datetime] = []
    new_items: list[datetime] = []
    for row in source_rows:
        states[row["state"]] += 1
        if (at := _dt(row.get("last_successful_collection"))) is not None:
            successes.append(at)
        if (at := _dt(row.get("last_new_intelligence"))) is not None:
            new_items.append(at)
    return {
        "scheduled_sources": len(source_rows),
        "current": sum(states[state] for state in CURRENT_STATES),
        "current_active": states[CURRENT_ACTIVE],
        "current_quiet": states[CURRENT_QUIET],
        "due": sum(bool(row.get("due")) and not bool(row.get("overdue")) for row in source_rows),
        "overdue": sum(bool(row.get("overdue")) for row in source_rows),
        "retrying": states[RETRYING],
        "failing": states[FAILING],
        "blocked": states[BLOCKED],
        "never_run": states[NEVER_RUN],
        "insufficient_history": states[INSUFFICIENT_HISTORY],
        "unhealthy": sum(
            row["state"] in DEGRADED_STATES or bool(row.get("overdue"))
            for row in source_rows
        ),
        "last_successful_collection": _iso(max(successes)) if successes else None,
        "last_new_intelligence": _iso(max(new_items)) if new_items else None,
    }


def _group_coverage(
    sources: list[dict[str, Any]], rows_by_id: dict[str, dict[str, Any]], key: str,
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for source in sources:
        values = source.get(key) or []
        for value in sorted({str(item) for item in values if item}):
            grouped[value].append(rows_by_id[str(source.get("id") or "")])
    return {name: _coverage_summary(rows) for name, rows in sorted(grouped.items())}


def _source_type_coverage(
    sources: list[dict[str, Any]], rows_by_id: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for source in sources:
        grouped[_source_type(source)].append(rows_by_id[str(source.get("id") or "")])
    return {name: _coverage_summary(rows) for name, rows in sorted(grouped.items())}


def _actor_coverage(
    sources: list[dict[str, Any]], rows_by_id: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for source in sources:
        for actor_id in source.get("linked_competitor_ids") or []:
            grouped[str(actor_id)].append(rows_by_id[str(source.get("id") or "")])
    output: dict[str, dict[str, Any]] = {}
    for actor_id, rows in sorted(grouped.items()):
        summary = _coverage_summary(rows)
        summary["direct_monitoring_gap"] = any(
            row["state"] in DEGRADED_STATES or bool(row.get("overdue"))
            for row in rows
        )
        summary["source_ids"] = sorted(row["source_id"] for row in rows)
        output[actor_id] = summary
    return output


def _coverage_degraded(summary: dict[str, Any]) -> bool:
    scheduled = int(summary.get("scheduled_sources", 0) or 0)
    unhealthy = int(summary.get("unhealthy", 0) or 0)
    return bool(scheduled and (unhealthy == scheduled or unhealthy >= max(2, math.ceil(scheduled * 0.25))))


def build_freshness_assurance(
    *,
    sources: list[dict[str, Any]],
    discovery_states: dict[str, dict[str, Any] | None],
    run_records: list[dict[str, Any]],
    discovered_items: list[dict[str, Any]],
    drafts: list[dict[str, Any]],
    scheduler_runs: list[dict[str, Any]],
    policy: dict[str, Any],
    now: datetime | None = None,
    grace_multiplier: float = 1.0,
) -> dict[str, Any]:
    """Build one body-free, reusable operational freshness contract.

    A Source becomes due after one configured interval and overdue after an
    additional interval of grace.  This preserves the pre-existing Source
    Health convention that a full missed cadence cycle separates DUE from
    stale/overdue, while using the exact second-level cadence policy.
    """

    instant = _utc(now or datetime.now(UTC))
    if grace_multiplier < 0:
        raise ValueError("grace_multiplier must be non-negative")
    sources = [source for source in sources if is_scheduled_coverage(source)]
    histories = _source_histories(run_records)
    new_by_source = _new_by_source(discovered_items)
    source_rows: list[dict[str, Any]] = []
    alerts: list[dict[str, Any]] = []

    for source in sorted(sources, key=lambda row: str(row.get("id") or "")):
        source_id = str(source.get("id") or "")
        state_record = discovery_states.get(source_id)
        history = histories.get(source_id, [])
        interval = cadence_seconds(source, policy)
        attempt = _dt((state_record or {}).get("last_checked_at"))
        success = _dt((state_record or {}).get("last_success_at"))
        if attempt is None and history:
            attempt = history[-1][0]
        if success is None:
            success = next((at for at, result in reversed(history) if result.get("status") == "ok"), None)
        existing_health = classify_source_freshness(
            source, discovery_state=state_record, today=instant.date(),
        )
        failures = _consecutive_failures(history)
        last_success_result = _last_success_result(history)
        latest_new_count = (
            _result_new(last_success_result) if last_success_result is not None
            else max(0, int((state_record or {}).get("new", 0) or 0) - int((state_record or {}).get("historical_backlog", 0) or 0))
        )
        due_at = success + timedelta(seconds=interval) if success and interval else None
        overdue_at = due_at + timedelta(seconds=interval * grace_multiplier) if due_at and interval else None
        is_due = bool(due_at and instant >= due_at)
        is_overdue = bool(overdue_at and instant > overdue_at)

        if existing_health.state == SOURCE_HEALTH_BLOCKED:
            freshness_state = BLOCKED
            reason = "Source Health is BLOCKED; automatic collection remains paused for operator resolution."
        elif (state_record or {}).get("status") == "error":
            if failures >= FAILURE_THRESHOLD or success is None:
                freshness_state = FAILING
                reason = f"Most recent collection failed; {max(1, failures)} consecutive failure(s) are retained."
            else:
                freshness_state = RETRYING
                reason = "Most recent collection failed once; existing bounded retry policy applies."
        elif state_record is None and not history:
            freshness_state = NEVER_RUN
            reason = "No collection attempt has been retained for this discoverable Source."
        elif success is None:
            freshness_state = INSUFFICIENT_HISTORY
            reason = "Collection was attempted, but no successful cadence anchor is retained."
        elif not history:
            freshness_state = INSUFFICIENT_HISTORY
            reason = "A successful discovery state exists, but bounded operation history is unavailable."
        elif is_overdue:
            freshness_state = OVERDUE
            reason = "Last successful collection is more than one grace cycle past its configured cadence."
        elif is_due:
            freshness_state = DUE
            reason = "Configured cadence has elapsed, but the Source remains inside its one-cycle grace window."
        elif latest_new_count > 0:
            freshness_state = CURRENT_ACTIVE
            reason = "Successfully collected within cadence and the latest successful run found new intelligence."
        else:
            freshness_state = CURRENT_QUIET
            reason = "Successfully collected within cadence; the latest successful run found no new intelligence."

        source_row = {
            "source_id": source_id,
            "source": source.get("label") or source_id,
            "source_type": _source_type(source),
            "berry_ids": list(source.get("berry_ids") or []),
            "geographies": list(source.get("region_coverage") or []),
            "actor_ids": list(source.get("linked_competitor_ids") or []),
            "state": freshness_state,
            "reason": reason,
            "cadence_seconds": interval,
            "grace_seconds": int(interval * grace_multiplier) if interval else None,
            "last_collection_attempt": _iso(attempt),
            "last_successful_collection": _iso(success),
            "last_new_intelligence": _iso(new_by_source.get(source_id)),
            "next_due": _iso(due_at),
            "overdue_after": _iso(overdue_at),
            "due": is_due,
            "overdue": is_overdue,
            "consecutive_failures": failures,
            "history_runs": len(history),
        }
        source_rows.append(source_row)

        if is_overdue:
            alerts.append({
                "code": "SOURCE_OVERDUE",
                "source_id": source_id,
                "reason": "Last successful collection is more than one grace cycle past its configured cadence.",
            })
        if failures >= FAILURE_THRESHOLD:
            alerts.append({
                "code": "MULTIPLE_CONSECUTIVE_FAILURES", "source_id": source_id,
                "reason": f"{failures} consecutive retained collection failures.",
            })

        successful_history = [(at, result) for at, result in history if result.get("status") == "ok"]
        if len(successful_history) >= ZERO_NEW_DRIFT_RUNS + PRIOR_PRODUCTIVE_RUNS:
            recent = successful_history[-ZERO_NEW_DRIFT_RUNS:]
            prior = successful_history[:-ZERO_NEW_DRIFT_RUNS]
            productive_runs = sum(_result_new(result) > 0 for _at, result in prior)
            if productive_runs >= PRIOR_PRODUCTIVE_RUNS and all(
                _result_new(result) == 0 for _at, result in recent
            ):
                alerts.append({
                    "code": "NEW_ITEM_YIELD_DEGRADED", "source_id": source_id,
                    "reason": f"Source had {productive_runs} prior productive successful runs, then {ZERO_NEW_DRIFT_RUNS} consecutive zero-new successful runs; acquisition yield changed, not inferred market activity.",
                })

        repeats = successful_history[1:]
        observed_new = sum(_result_new(result) for _at, result in repeats)
        observation_seconds = (repeats[-1][0] - successful_history[0][0]).total_seconds() if repeats else 0.0
        discovery = source.get("discovery") or {}
        feed_window = discovery.get("item_limit")
        if feed_window is None and isinstance((state_record or {}).get("found"), int):
            feed_window = state_record["found"]
        safe_interval = maximum_safe_interval_seconds(
            observed_new_items=observed_new,
            observation_seconds=observation_seconds,
            feed_window_size=feed_window,
        )
        source_row["maximum_safe_interval_seconds"] = safe_interval
        source_row["feed_window_risk"] = bool(interval and safe_interval and interval > safe_interval)
        if source_row["feed_window_risk"]:
            alerts.append({
                "code": "FEED_WINDOW_RISK", "source_id": source_id,
                "reason": f"Configured {interval}s cadence exceeds measured {safe_interval}s safe feed-window interval; CADENCE_REVIEW_RECOMMENDED.",
            })

    rows_by_id = {row["source_id"]: row for row in source_rows}
    berry = _group_coverage(sources, rows_by_id, "berry_ids")
    geography = _group_coverage(sources, rows_by_id, "region_coverage")
    source_type = _source_type_coverage(sources, rows_by_id)
    actors = _actor_coverage(sources, rows_by_id)

    for dimension, groups in (("berry", berry), ("geography", geography), ("source_type", source_type)):
        for name, summary in groups.items():
            if _coverage_degraded(summary):
                alerts.append({
                    "code": "COVERAGE_DEGRADED", "dimension": dimension, "value": name,
                    "reason": "Operationally unhealthy Sources cross the deterministic coverage threshold; this does not imply weak market activity.",
                })

    drafts_by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for draft in drafts:
        source_id = draft.get("source_id")
        if (
            isinstance(source_id, str)
            and draft.get("evidence_role") == "publication_artifact"
            and not _historical_repair(draft)
        ):
            drafts_by_source[source_id].append(draft)
    for source_id, source_drafts in drafts_by_source.items():
        ordered = sorted(source_drafts, key=lambda row: _draft_at(row) or datetime.min.replace(tzinfo=UTC))
        if len(ordered) < RICH_BODY_DRIFT_DRAFTS + 3:
            continue
        recent = ordered[-RICH_BODY_DRIFT_DRAFTS:]
        prior_full = sum((row.get("source_completeness") or {}).get("class") == "FULL_ARTICLE" for row in ordered[:-RICH_BODY_DRIFT_DRAFTS])
        recent_classes = [(row.get("source_completeness") or {}).get("class") for row in recent]
        if prior_full >= 3 and all(value in {"THIN_DESCRIPTION", "ACQUISITION_FAILED"} for value in recent_classes):
            alerts.append({
                "code": "RICH_BODY_YIELD_DEGRADED", "source_id": source_id,
                "reason": f"Previously rich-body productive Source has {RICH_BODY_DRIFT_DRAFTS} consecutive explicit thin/failure outcomes.",
            })

    counts = _coverage_summary(source_rows)
    last_successful_collection = _latest_successful_collection(run_records)
    last_scheduler_run = _latest_scheduler_run(scheduler_runs)
    attempts = [_dt(row.get("last_collection_attempt")) for row in source_rows]
    attempts = [value for value in attempts if value is not None]
    last_collection_attempt = max(attempts) if attempts else None
    last_new = max(new_by_source.values()) if new_by_source else None
    last_rich = _last_rich_draft(drafts)
    if last_successful_collection is None:
        alerts.append({
            "code": "NO_SUCCESSFUL_COLLECTION_RUN",
            "reason": "No successful collection operation is retained; a current-through claim is not permitted.",
        })
    system_state = SYSTEM_DEGRADED if any(
        counts[key] for key in ("overdue", "failing", "blocked", "never_run", "insufficient_history")
    ) or last_successful_collection is None else SYSTEM_CURRENT
    current_through = _iso(last_successful_collection)
    for alert in alerts:
        alert["condition"] = ALERT_CONDITION_NAMES.get(str(alert.get("code")), alert.get("code"))
    alert_conditions = sorted({str(alert["condition"]) for alert in alerts})

    return {
        "generated_at": _iso(instant),
        "system_state": system_state,
        "status_label": "INTELLIGENCE CURRENT" if system_state == SYSTEM_CURRENT else "COLLECTION PARTIALLY DEGRADED",
        "can_claim_current": system_state == SYSTEM_CURRENT and current_through is not None,
        "current_through": current_through,
        "last_collection_attempt": _iso(last_collection_attempt),
        "last_scheduler_run": _iso(last_scheduler_run),
        "last_successful_collection": _iso(last_successful_collection),
        "last_new_intelligence": _iso(last_new),
        "last_new_rich_draft": _iso(last_rich),
        "overdue_count": counts["overdue"],
        "failing_count": counts["failing"],
        "blocked_count": counts["blocked"],
        "due_count": counts["due"],
        "retrying_count": counts["retrying"],
        "discoverable_source_count": counts["scheduled_sources"],
        "current_source_count": counts["current"],
        "due_source_count": counts["due"],
        "overdue_source_count": counts["overdue"],
        "failing_source_count": counts["failing"],
        "blocked_source_count": counts["blocked"],
        "current_quiet_source_count": counts["current_quiet"],
        "retrying_source_count": counts["retrying"],
        "counts": counts,
        "berry_coverage": berry,
        "geography_coverage": geography,
        "actor_coverage": actors,
        "source_type_coverage": source_type,
        "alerts": sorted(alerts, key=lambda row: (str(row.get("code")), str(row.get("source_id") or row.get("value") or ""))),
        "alert_conditions": alert_conditions,
        "sources": source_rows,
        "contract": {
            "current_through": "Completion time of the most recent collection operation with at least one successful Source; displayed as current only when no Source is overdue, failing, blocked, never-run, or missing sufficient history.",
            "last_new_intelligence": "Latest first_seen_at among genuinely new discovered items, excluding historical_backlog; duplicates, review actions, reindexing, and Source Fidelity/reacquisition artifacts cannot advance it.",
            "grace": "A Source is DUE after one configured cadence interval and OVERDUE after one additional cadence interval of grace.",
        },
    }


def _newest_json(folder: Path, limit: int) -> list[dict[str, Any]]:
    """Read a bounded newest-file window; invalid records are skipped."""

    if not folder.is_dir() or limit <= 0:
        return []
    paths = sorted(folder.glob("*.json"), key=lambda path: path.stat().st_mtime_ns)[-limit:]
    records: list[dict[str, Any]] = []
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            records.append(payload)
    return records


def _folder_signature(folder: Path) -> tuple[int, int, int]:
    if not folder.is_dir():
        return (0, 0, 0)
    count = 0
    newest = 0
    total_size = 0
    for path in folder.glob("*.json"):
        try:
            stat = path.stat()
        except OSError:
            continue
        count += 1
        newest = max(newest, stat.st_mtime_ns)
        total_size += stat.st_size
    return (count, newest, total_size)


def _runtime_signature(inbox_dir: Path, policy_file: Path) -> tuple[Any, ...]:
    folders = (
        inbox_dir / "operations" / "runs",
        inbox_dir / "operations" / "cron-logs",
        inbox_dir / "discovered_media",
        inbox_dir / "discovered_media" / "_state",
        inbox_dir / "evidence",
    )
    try:
        policy_stat = policy_file.stat()
        policy_signature = (policy_stat.st_mtime_ns, policy_stat.st_size)
    except OSError:
        policy_signature = (0, 0)
    return (*(_folder_signature(folder) for folder in folders), policy_signature)


def _build_runtime_uncached(
    *,
    data_dir: Path,
    inbox_dir: Path,
    sources: list[dict[str, Any]],
    policy_file: Path,
    history_limit: int,
    now: datetime,
) -> dict[str, Any]:
    return build_freshness_assurance(
        sources=sources,
        discovery_states={
            source["id"]: read_source_discovery_state(inbox_dir, source["id"])
            for source in sources
        },
        run_records=_newest_json(inbox_dir / "operations" / "runs", history_limit),
        discovered_items=load_json_objects(inbox_dir / "discovered_media"),
        drafts=load_json_objects(inbox_dir / "evidence"),
        scheduler_runs=_newest_json(inbox_dir / "operations" / "cron-logs", history_limit),
        policy=load_cadence_policy(policy_file),
        now=now,
    )


@lru_cache(maxsize=8)
def _cached_runtime_freshness(
    data_dir_text: str,
    inbox_dir_text: str,
    policy_file_text: str,
    history_limit: int,
    sources_json: str,
    minute_bucket: str,
    _signature: tuple[Any, ...],
) -> dict[str, Any]:
    return _build_runtime_uncached(
        data_dir=Path(data_dir_text),
        inbox_dir=Path(inbox_dir_text),
        sources=json.loads(sources_json),
        policy_file=Path(policy_file_text),
        history_limit=history_limit,
        now=datetime.fromisoformat(minute_bucket),
    )


def clear_freshness_cache() -> None:
    """Explicit test/operator invalidation; runtime signatures normally suffice."""

    _cached_runtime_freshness.cache_clear()


def build_runtime_freshness(
    *,
    data_dir: Path,
    inbox_dir: Path,
    sources: list[dict[str, Any]],
    policy_path: Path | None = None,
    history_limit: int = 500,
    now: datetime | None = None,
    use_cache: bool = True,
) -> dict[str, Any]:
    """Reusable runtime adapter for Today, Review Operations, and CLIs.

    It performs bounded metadata reads only.  It never fetches a Source,
    reads external services, mutates trust/review state, or returns bodies.
    Explicit ``now`` values can bypass the minute cache with
    ``use_cache=False`` when a caller needs exact boundary evaluation.
    """

    discoverable = [source for source in sources if is_scheduled_coverage(source)]
    policy_file = policy_path or data_dir / "configuration" / "source_collection_cadence.json"
    if now is not None and not use_cache:
        return _build_runtime_uncached(
            data_dir=data_dir,
            inbox_dir=inbox_dir,
            sources=discoverable,
            policy_file=policy_file,
            history_limit=history_limit,
            now=_utc(now),
        )
    cache_instant = now or datetime.now(UTC)
    if cache_instant.tzinfo is None:
        cache_instant = cache_instant.replace(tzinfo=UTC)
    minute = cache_instant.astimezone(UTC).replace(second=0, microsecond=0)
    payload = _cached_runtime_freshness(
        str(data_dir.resolve()),
        str(inbox_dir.resolve()),
        str(policy_file.resolve()),
        history_limit,
        json.dumps(discoverable, sort_keys=True, ensure_ascii=False),
        minute.isoformat(),
        _runtime_signature(inbox_dir, policy_file),
    )
    return deepcopy(payload)
