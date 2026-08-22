"""One persisted scheduler for every production collection/maintenance pipeline."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shlex
import subprocess
import sys
import time
from typing import Any, Callable

from app.services.pipeline_health import build_pipeline_health


UTC = timezone.utc


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _parse_output(stdout: str) -> dict[str, Any]:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _failure_shape(pipeline_id: str, payload: dict[str, Any]) -> tuple[int, int]:
    counts = payload.get("counts") if isinstance(payload.get("counts"), dict) else {}
    if pipeline_id in {"article_news", "spoken_media"}:
        return int(counts.get("sources_failed", 0) or 0), int(counts.get("sources_succeeded", 0) or 0)
    failed = payload.get("failed") if isinstance(payload.get("failed"), list) else []
    failure_count = len(failed)
    success_units = 0
    if isinstance(payload.get("queried"), int):
        success_units = max(0, payload["queried"] - failure_count)
    for key in ("lanes_with_data", "regions_with_data", "berry_relevant", "review_ready"):
        if isinstance(payload.get(key), int):
            success_units = max(success_units, payload[key])
    return failure_count, success_units


def classify_outcome(pipeline_id: str, payload: dict[str, Any], returncode: int) -> tuple[str, int]:
    if payload.get("state") == "error" or not payload:
        return "FAILED", 1
    failure_count, success_units = _failure_shape(pipeline_id, payload)
    if failure_count:
        return ("PARTIAL" if success_units else "FAILED"), failure_count
    if returncode:
        return "FAILED", 1
    return "SUCCESS", 0


def _compact_counts(payload: dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload.get("counts"), dict):
        return dict(payload["counts"])
    keys = (
        "queried", "berry_relevant_filings", "berry_relevant", "duplicates", "review_ready",
        "lanes_requested", "lanes_with_data", "regions_requested", "regions_with_data",
        "archives_valid", "archives_retained", "archives_removed",
    )
    return {key: payload[key] for key in keys if isinstance(payload.get(key), (int, float))}


def _drafts_created(payload: dict[str, Any]) -> int:
    counts = payload.get("counts") if isinstance(payload.get("counts"), dict) else {}
    if isinstance(counts.get("publication_drafts_created"), int):
        return counts["publication_drafts_created"]
    created = payload.get("created")
    return len(created) if isinstance(created, list) else 0


def _failure_sample(payload: dict[str, Any]) -> list[Any]:
    if isinstance(payload.get("failed"), list):
        return list(payload["failed"])[:10]
    if isinstance(payload.get("sources"), list):
        return [
            {
                "source_id": source.get("source_id"),
                "status": source.get("status"),
                "error": source.get("error"),
            }
            for source in payload["sources"]
            if isinstance(source, dict) and source.get("status") not in {"ok", "planned"}
        ][:10]
    return []


def _default_executor(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, capture_output=True, check=False)


def run_due_pipelines(
    *,
    data_dir: Path,
    inbox_dir: Path,
    config_path: Path,
    now: datetime | None = None,
    pipeline_id: str | None = None,
    force: bool = False,
    plan_only: bool = False,
    executor: Callable[[list[str]], subprocess.CompletedProcess[str]] = _default_executor,
) -> dict[str, Any]:
    instant = (now or datetime.now(UTC)).astimezone(UTC)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    pipelines = config.get("pipelines") or []
    if pipeline_id and pipeline_id not in {item.get("id") for item in pipelines}:
        raise ValueError(f"unknown pipeline: {pipeline_id}")
    health = build_pipeline_health(data_dir=data_dir, inbox_dir=inbox_dir, config_path=config_path, now=instant)
    health_by_id = {item["pipeline"]: item for item in health["pipelines"]}
    selected: list[dict[str, Any]] = []
    for pipeline in pipelines:
        if pipeline_id and pipeline.get("id") != pipeline_id:
            continue
        if not pipeline.get("enabled") or not pipeline.get("scheduled"):
            continue
        next_due = health_by_id[pipeline["id"]].get("next_due")
        due = next_due is None or datetime.fromisoformat(next_due).astimezone(UTC) <= instant
        if force or due:
            selected.append(pipeline)
    if plan_only:
        return {
            "state": "PLANNED",
            "generated_at": _iso(instant),
            "due": [pipeline["id"] for pipeline in selected],
            "pipelines": health["pipelines"],
        }

    results: list[dict[str, Any]] = []
    for pipeline in selected:
        started = datetime.now(UTC)
        monotonic_started = time.monotonic()
        command = [sys.executable, *shlex.split(str(pipeline["runner"]))]
        completed = executor(command)
        finished = datetime.now(UTC)
        payload = _parse_output(completed.stdout)
        outcome, failure_count = classify_outcome(pipeline["id"], payload, completed.returncode)
        record = {
            "pipeline": pipeline["id"],
            "started_at": _iso(started),
            "completed_at": _iso(finished),
            "duration_seconds": round(max(0.0, time.monotonic() - monotonic_started), 3),
            "outcome": outcome,
            "exit_code": completed.returncode,
            "failure_count": failure_count,
            "failure_sample": _failure_sample(payload),
            "counts": _compact_counts(payload),
            "drafts_created": _drafts_created(payload),
            "stderr": completed.stderr[-2000:] if completed.stderr else "",
        }
        stamp = started.strftime("%Y%m%dT%H%M%S%fZ")
        _write_json(inbox_dir / "operations" / "pipelines" / pipeline["id"] / "runs" / f"{stamp}.json", record)
        results.append(record)
    outcomes = {result["outcome"] for result in results}
    state = "IDLE" if not results else "FAILED" if "FAILED" in outcomes else "PARTIAL" if "PARTIAL" in outcomes else "SUCCESS"
    return {"state": state, "generated_at": _iso(instant), "results": results}
