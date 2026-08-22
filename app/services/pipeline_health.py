"""Read-only orchestration contract and health for every acquisition pipeline."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import shutil
from typing import Any


UTC = timezone.utc


def _read(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _pipeline_runs(inbox_dir: Path, pipeline: dict[str, Any]) -> list[dict[str, Any]]:
    state = str(pipeline.get("state") or "")
    path = inbox_dir / state
    if pipeline["id"] == "article_spoken_media":
        return [payload for candidate in sorted(path.glob("*.json")) if (payload := _read(candidate)) is not None] if path.is_dir() else []
    payload = _read(path)
    if payload is None:
        return []
    runs = payload.get("runs") or []
    return [run for run in runs if isinstance(run, dict)]


def _attempt_at(run: dict[str, Any]) -> str | None:
    return run.get("completed_at") or run.get("at") or run.get("started_at")


def _failures(pipeline_id: str, run: dict[str, Any]) -> list[Any]:
    if pipeline_id == "article_spoken_media":
        return [source for source in run.get("sources", []) if source.get("status") not in {"ok", "planned"}]
    return list(run.get("failures") or [])


def build_pipeline_health(*, data_dir: Path, inbox_dir: Path, config_path: Path, now: datetime | None = None) -> dict[str, Any]:
    instant = (now or datetime.now(UTC)).astimezone(UTC)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    reports: list[dict[str, Any]] = []
    for pipeline in config.get("pipelines", []):
        runs = _pipeline_runs(inbox_dir, pipeline)
        last = runs[-1] if runs else None
        attempt = _attempt_at(last or {})
        failures = _failures(pipeline["id"], last or {})
        successful = next((run for run in reversed(runs) if not _failures(pipeline["id"], run)), None)
        last_success = _attempt_at(successful or {})
        cadence = pipeline.get("cadence_seconds")
        next_due = None
        if last_success and isinstance(cadence, int):
            parsed = datetime.fromisoformat(last_success)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            next_due = (parsed.astimezone(UTC) + timedelta(seconds=cadence)).isoformat(timespec="seconds")
        counts = (last or {}).get("counts") or {}
        duration = None
        if last and last.get("started_at") and last.get("completed_at"):
            duration = max(0.0, (datetime.fromisoformat(last["completed_at"]) - datetime.fromisoformat(last["started_at"])).total_seconds())
        reports.append({
            "pipeline": pipeline["id"],
            "enabled": bool(pipeline.get("enabled")),
            "scheduled": bool(pipeline.get("scheduled")),
            "schedule_entrypoint": bool(pipeline.get("schedule_entrypoint")),
            "cadence_seconds": cadence,
            "last_attempt": attempt,
            "last_success": last_success,
            "next_due": next_due,
            "failure_state": failures or None,
            "duration_seconds": duration,
            "items_discovered": counts.get("items_new") or (last or {}).get("discovered") or 0,
            "drafts_created": counts.get("publication_drafts_created") or len((last or {}).get("created") or []),
            "runner": pipeline.get("runner"),
            "notes": pipeline.get("notes"),
        })
    usage_path = inbox_dir.resolve()
    while not usage_path.exists() and usage_path != usage_path.parent:
        usage_path = usage_path.parent
    usage = shutil.disk_usage(usage_path)
    free_percent = round(usage.free * 100 / usage.total, 1) if usage.total else 0
    return {
        "generated_at": instant.isoformat(timespec="seconds"),
        "runtime": {
            "data_dir": str(data_dir.resolve()),
            "inbox_dir": str(inbox_dir.resolve()),
            "persistent_runtime_configured": bool(__import__("os").environ.get("BIOS_RUNTIME_DIR") or __import__("os").environ.get("BIOS_INBOX_DIR")),
            "free_bytes": usage.free,
            "free_percent": free_percent,
            "storage_warning": free_percent < 10,
        },
        "pipelines": reports,
    }
