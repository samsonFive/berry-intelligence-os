"""Collection Operations & Freshness Control V1 -- a thin view-model layer
over EXISTING collection runtime/status machinery (CollectionStatusService,
CollectionRunner, Source health), not a second implementation of any of it.

This module answers "is recurring collection enabled, is a run active, when
did it last run/succeed, what happened, which Sources are degraded, is
there a stale lock, what action is needed" entirely by reading data these
services already compute and persist -- it never recalculates freshness,
never re-derives Source health, and never introduces a new trust or
review concept. A "Run Now" action, when triggered, shells out to the
exact same `scripts/run_collection.py` CLI the production systemd timer
already uses (matching `app.services.pipeline_scheduler.run_due_pipelines`'s
own subprocess-invocation pattern) -- the heavy CollectionRunner wiring
(Whisper model, AI gateway completer, extraction-gate construction) stays
in that one already-proven entry point rather than being duplicated
in-process inside the always-on web server. Extraction is never opted
into by this module under any circumstance -- `--enable-extraction` is
never passed to the subprocess."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from app.services.ai_extraction import EXTRACTION_VERSION, PROMPT_VERSION
from app.services.collection_runner import ExtractionGate, OperationalStateStore, resolve_extraction_gate
from app.services.collection_status import CollectionStatusService
from app.services.model_qualification import file_sha256, qualification_configuration_fingerprint
from app.services.source_cadence import load_cadence_policy

RUN_HISTORY_LIMIT = 10
RUN_SIZE_CHOICES = (5, 10, 25)
DEFAULT_RUN_SIZE = 10
RUN_TIMEOUT_SECONDS = 180


def _extraction_gate_for_status() -> tuple[ExtractionGate, list[str]]:
    """Read-only mirror of scripts/collection_status.py's own
    _extraction_state() -- same env vars, same resolve_extraction_gate()
    call, so the status page never disagrees with what the CLI would
    report. When extraction is not configured (the case in every real
    deployment today), resolve_extraction_gate() returns immediately
    without touching any benchmark file, so this stays cheap."""
    base_url = os.environ.get("BIOS_EXTRACT_BASE_URL")
    model = os.environ.get("BIOS_EXTRACT_MODEL")
    enabled = os.environ.get("BIOS_COLLECTION_ENABLE_EXTRACTION", "").strip().casefold() in {"1", "true", "yes", "on"}
    qualification_path_raw = os.environ.get("BIOS_COLLECTION_QUALIFICATION_FILE")
    qualification_path = Path(qualification_path_raw) if qualification_path_raw else None

    fingerprint = None
    if base_url and model:
        from app.services.ai_extraction import OpenAICompatibleExtractionConfig, OpenAICompatibleExtractionProvider
        from app.services.extraction_evaluation import public_configuration

        config = OpenAICompatibleExtractionConfig.from_environment(
            api_key_env="BIOS_EXTRACT_API_KEY", base_url=base_url, model=model,
        )
        provider = OpenAICompatibleExtractionProvider(config=config, repositories=None)
        fingerprint = qualification_configuration_fingerprint(
            provider="openai-compatible", model=model, base_url=base_url,
            prompt_version=PROMPT_VERSION, generation=public_configuration(provider),
        )

    root = Path(__file__).resolve().parents[2]
    benchmark_sha = file_sha256(root / "benchmarks" / "atomic-ci-v1.json") if enabled else None
    gate = resolve_extraction_gate(
        enabled=enabled,
        provider="openai-compatible",
        model=model,
        base_url=base_url,
        prompt_version=PROMPT_VERSION,
        qualification_path=qualification_path,
        configuration_fingerprint=fingerprint,
        benchmark_sha256=benchmark_sha,
        extraction_version=EXTRACTION_VERSION,
    )
    blockers: list[str] = []
    if not enabled:
        blockers.append("extraction is disabled")
    elif not base_url or not model:
        blockers.append("extraction provider/model configuration is incomplete")
    elif qualification_path is None:
        blockers.append("no qualification marker is configured")
    elif not gate.runnable:
        blockers.append(gate.reason)
    return gate, blockers


def _evidence_errors_noop(record: dict[str, Any]) -> list[str]:
    # Status display never validates or writes a record -- this callback
    # exists only because CollectionStatusService's constructor requires
    # one (it's used deep inside the optional --audit-items path, which
    # this module never invokes via persisted_only=True).
    return []


def build_status_report(
    *, repositories: Any, data_dir: Path, inbox_dir: Path,
) -> dict[str, Any]:
    """The one persisted-only status read this whole page is built from --
    CollectionStatusService's existing fast path (no per-item scan, no
    orchestration dry-run), so opening /collection-ops costs the same as
    `scripts/collection_status.py` without --audit-items."""
    gate, blockers = _extraction_gate_for_status()
    cadence_policy_path = data_dir / "configuration" / "source_collection_cadence.json"
    cadence_policy = load_cadence_policy(cadence_policy_path) if cadence_policy_path.is_file() else {}
    service = CollectionStatusService(
        repositories=repositories,
        inbox_dir=inbox_dir,
        operations=OperationalStateStore(inbox_dir / "operations"),
        evidence_errors=_evidence_errors_noop,
        extraction_gate=gate,
        extraction_blockers=blockers,
        cadence_policy=cadence_policy,
    )
    return service.build(persisted_only=True).as_dict()


def list_recent_runs(inbox_dir: Path, *, limit: int = RUN_HISTORY_LIMIT) -> list[dict[str, Any]]:
    """Bounded recent-run history from the run summaries CollectionRunner
    already persists (inbox/operations/runs/*.json) -- no new persistence,
    no fake metrics. Each entry is trimmed to run-level metadata only
    (never the per-item `items` list) so this stays a compact, scannable
    history rather than a second detailed audit view."""
    runs_dir = Path(inbox_dir) / "operations" / "runs"
    if not runs_dir.is_dir():
        return []
    files = sorted(runs_dir.glob("*.json"), key=lambda p: p.name, reverse=True)[:limit]
    rows: list[dict[str, Any]] = []
    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        started = payload.get("started_at")
        completed = payload.get("completed_at")
        duration_seconds = None
        if started and completed:
            try:
                duration_seconds = (
                    datetime.fromisoformat(completed) - datetime.fromisoformat(started)
                ).total_seconds()
            except ValueError:
                duration_seconds = None
        rows.append(
            {
                "run_id": payload.get("run_id"),
                "started_at": started,
                "completed_at": completed,
                "duration_seconds": duration_seconds,
                "dry_run": bool(payload.get("dry_run")),
                "source_scope": payload.get("source_scope"),
                "counts": payload.get("counts") or {},
                "stale_lock_recovered": bool(payload.get("stale_lock_recovered")),
            }
        )
    return rows


def _default_run_executor(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, timeout=RUN_TIMEOUT_SECONDS)


def trigger_bounded_run(
    *,
    repositories: Any,
    data_dir: Path,
    inbox_dir: Path,
    max_items: int = DEFAULT_RUN_SIZE,
    executor: Callable[[list[str]], subprocess.CompletedProcess[str]] = _default_run_executor,
) -> dict[str, Any]:
    """POST-only bounded manual trigger. Refuses immediately (without
    spawning anything) if a run is already active. Never passes
    --enable-extraction. Shells out to the exact CLI the systemd timer
    already uses (scripts/run_collection.py), so this reuses
    CollectionRunner's real locking/retry/extraction-gate semantics
    rather than re-implementing any of them against a live web request."""
    if max_items not in RUN_SIZE_CHOICES:
        max_items = DEFAULT_RUN_SIZE

    pre_check = build_status_report(repositories=repositories, data_dir=data_dir, inbox_dir=inbox_dir)
    lock = pre_check.get("lock") or {}
    if lock.get("active") and not lock.get("stale"):
        return {
            "state": "refused",
            "reason": "A collection run is already active.",
            "run_id": lock.get("run_id"),
            "started_at": lock.get("started_at"),
        }

    root = Path(__file__).resolve().parents[2]
    command = [
        sys.executable, str(root / "scripts" / "run_collection.py"),
        "--all", "--max-items", str(max_items), "--json-summary",
        "--data-dir", str(data_dir), "--inbox-dir", str(inbox_dir),
        "--created-by", "collection-ops-run-now",
    ]
    try:
        result = executor(command)
    except subprocess.TimeoutExpired:
        return {"state": "error", "reason": f"Run did not complete within {RUN_TIMEOUT_SECONDS}s."}

    if result.returncode not in (0, 1):  # 1 = ran, but some Source failed -- still a completed summary
        return {"state": "error", "reason": (result.stderr or result.stdout or "Unknown failure").strip()[:2000]}

    try:
        summary = json.loads(result.stdout)
    except (json.JSONDecodeError, TypeError):
        return {"state": "error", "reason": "Run completed but its summary could not be parsed."}

    if "error" in summary and "counts" not in summary:
        return {"state": "error", "reason": str(summary.get("error"))}

    return {"state": "completed", "summary": summary}
