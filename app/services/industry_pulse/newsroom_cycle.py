"""One full newsroom-intake cycle: discovery+qualification (run_pulse)
followed by the pulse-to-Publication intake bridge (intake_qualified_hits).

Lock-protected and run-history-recorded using the exact same primitives
CollectionRunner already established (CollectionRunLock,
CollectionLockedError) at a SEPARATE lock path from the main collection
lock -- pulse discovery/intake and per-Source RSS polling are independent
resources with no shared state, so they should not block each other, only
themselves (one newsroom cycle at a time).

Does not fork run_pulse() or qualify.py -- reconstructs DiscoveryHit
objects from run_pulse()'s own already-qualified/deduped/classified
`hits` (the 7d-window qualifying set it already returns) rather than
re-deriving anything.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.services.collection_runner import CollectionLockedError, CollectionRunLock
from app.services.industry_pulse.intake import intake_qualified_hits
from app.services.industry_pulse.models import DiscoveryHit
from app.services.industry_pulse.providers import DiscoveryProvider, GoogleNewsRssProvider
from app.services.industry_pulse.run import run_pulse

LOCK_PATH_PARTS = ("operations", "industry_pulse_intake.lock")
RUNS_DIR_PARTS = ("operations", "industry_pulse_runs")


def _hits_from_report(report: dict[str, Any]) -> list[DiscoveryHit]:
    fields = {f for f in DiscoveryHit.__dataclass_fields__}
    hits = []
    for row in report.get("hits") or []:
        clean = {k: v for k, v in row.items() if k in fields}
        hits.append(DiscoveryHit(**clean))
    return hits


def run_newsroom_cycle(
    *,
    sources: list[dict[str, Any]],
    published_evidence: list[dict[str, Any]],
    drafts: list[dict[str, Any]],
    entities: list[dict[str, Any]],
    varieties: list[dict[str, Any]] | None = None,
    publications: list[dict[str, Any]] | None = None,
    discovered_items: list[dict[str, Any]] | None = None,
    inbox_dir: Path,
    data_dir: Path,
    provider: DiscoveryProvider | None = None,
    catch_net_provider: DiscoveryProvider | None = None,
    max_acquisitions: int = 20,
    fetch: Any = None,
    now: datetime | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    run_id = f"pulse-intake-{now.strftime('%Y%m%dT%H%M%SZ')}"
    lock_path = inbox_dir.joinpath(*LOCK_PATH_PARTS)

    try:
        lock = CollectionRunLock(lock_path, run_id=run_id, now=lambda: now)
        with lock:
            pulse_report = run_pulse(
                provider=provider or GoogleNewsRssProvider(),
                catch_net_provider=catch_net_provider,
                sources=sources,
                published_evidence=published_evidence,
                varieties=varieties,
                entities=entities,
                publications=publications,
                discovered_items=discovered_items,
                today=now.date(),
                persist_dir=inbox_dir if persist else None,
            )
            hits = _hits_from_report(pulse_report)
            intake_kwargs: dict[str, Any] = dict(
                sources=sources,
                published_evidence=published_evidence,
                drafts=drafts,
                entities=entities,
                inbox_dir=inbox_dir,
                max_acquisitions=max_acquisitions,
                now=now,
                dry_run=not persist,
            )
            if fetch is not None:
                intake_kwargs["fetch"] = fetch
            intake_summary = intake_qualified_hits(hits, **intake_kwargs)
            refused = False
            recovered_stale_lock = lock.recovered_stale_lock
    except CollectionLockedError as exc:
        return {
            "run_id": run_id,
            "as_of": now.isoformat(),
            "refused": True,
            "refusal_reason": str(exc),
            "discovery": None,
            "intake": None,
        }

    result = {
        "run_id": run_id,
        "as_of": now.isoformat(),
        "refused": refused,
        "recovered_stale_lock": recovered_stale_lock,
        "discovery": {
            "provider": pulse_report["provider"],
            "catch_net_provider": pulse_report["catch_net_provider"],
            "provider_telemetry": pulse_report["provider_telemetry"],
            "union_unique_count": pulse_report["union_unique_count"],
            "overlap_qualifying_count": pulse_report["overlap_qualifying_count"],
            "windows": {
                window: {"discovered": row["discovered"], "qualifying": row["qualifying"], "novel": row["novel"]}
                for window, row in pulse_report["windows"].items()
            },
            "rejected_7d": pulse_report.get("rejected_7d", 0),
            "query_failures": len(pulse_report["query_failures"]),
        },
        "intake": intake_summary.as_dict(),
    }
    if persist:
        _persist_run(inbox_dir, result)
    return result


def _persist_run(inbox_dir: Path, result: dict[str, Any]) -> Path:
    folder = inbox_dir.joinpath(*RUNS_DIR_PARTS)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{result['run_id']}.json"
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def load_recent_runs(inbox_dir: Path, *, limit: int = 10) -> list[dict[str, Any]]:
    folder = inbox_dir.joinpath(*RUNS_DIR_PARTS)
    if not folder.is_dir():
        return []
    paths = sorted(folder.glob("*.json"), key=lambda p: p.name, reverse=True)[:limit]
    out = []
    for path in paths:
        try:
            out.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return out


def newsroom_lock_status(inbox_dir: Path, *, now: datetime | None = None, stale_after_hours: float = 6.0) -> dict[str, Any]:
    """Read-only lock inspection -- mirrors collection_status.py's
    `_lock_status` pattern for the main collection lock, applied to this
    module's own separate lock file."""
    now = now or datetime.now(UTC)
    path = inbox_dir.joinpath(*LOCK_PATH_PARTS)
    if not path.is_file():
        return {"state": "none", "active": False, "stale": False}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"state": "malformed", "active": False, "stale": False}
    started_raw = payload.get("started_at")
    try:
        started = datetime.fromisoformat(started_raw) if isinstance(started_raw, str) else None
        if started is not None and started.tzinfo is None:
            started = started.replace(tzinfo=UTC)
    except ValueError:
        started = None
    if started is None:
        return {"state": "malformed", "active": False, "stale": False}
    age_seconds = (now - started.astimezone(UTC)).total_seconds()
    stale = age_seconds > stale_after_hours * 3600
    return {
        "state": "stale" if stale else "active",
        "active": not stale,
        "stale": stale,
        "run_id": payload.get("run_id"),
        "started_at": started_raw,
        "age_seconds": age_seconds,
    }
