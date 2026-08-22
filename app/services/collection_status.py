"""Read-only operational status for the recurring collection pipeline.

The service composes existing Source, orchestration, review, runner, and
qualification semantics.  It performs no network or model calls and writes no
state.  Per-file defensive reads are limited to gitignored runtime folders,
which do not have repository abstractions.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
from typing import Any, Callable

from app.services.collection_runner import (
    CollectionRunner,
    ExtractionGate,
    OperationalStateStore,
)
from app.services.media_discovery import list_discovered_items, read_source_discovery_state
from app.services.media_orchestration import (
    MediaOrchestrationError,
    MediaOrchestrationService,
    MediaTranscriptionAdapter,
)
from app.services.review_workbench import build_review_workbench
from app.services.source_freshness import classify_source_freshness, latest_item_dates


UTC = timezone.utc
STATUS_CATEGORIES = (
    "ready_to_advance",
    "human_publication_review_required",
    "extraction_ready",
    "extraction_blocked",
    "human_atomic_evidence_review_required",
    "retryable_failure",
    "operator_intervention_required",
    "completed_no_action",
)
@dataclass(frozen=True)
class StatusProblem:
    kind: str
    identity: str
    message: str
    source_id: str | None = None
    category: str = "operator_intervention_required"
    recommended_action: str = "resolve operator-action failure"


@dataclass
class ItemStatus:
    item_id: str
    source_id: str | None
    title: str
    category: str
    recommended_action: str
    reason: str
    publication_state: str | None = None
    transcript_state: str | None = None
    parent_evidence_id: str | None = None
    publication_draft_id: str | None = None
    pending_atomic_proposals: int = 0
    approved_atomic_evidence: int = 0
    rejected_atomic_proposals: int = 0
    retry_count: int = 0
    next_eligible_retry_at: str | None = None
    error: str | None = None


@dataclass
class SourceStatus:
    source_id: str
    name: str
    adapter: str | None
    discoverable: bool
    discovered_items: int = 0
    pending_publication_review: int = 0
    trusted_publications: int = 0
    extraction_ready: int = 0
    extraction_blocked: int = 0
    pending_atomic_review: int = 0
    retryable_failures: int = 0
    operator_intervention: int = 0
    completed_no_action: int = 0
    last_discovery_status: str | None = None
    last_discovery_new: int | None = None
    recommended_next_action: str = "run collection"
    freshness: dict[str, Any] = field(default_factory=dict)


@dataclass
class CollectionStatusReport:
    generated_at: str
    source_filter: str | None
    sources_configured: int
    sources_discoverable: int
    lock: dict[str, Any]
    extraction: dict[str, Any]
    pilot_readiness: dict[str, Any]
    counts: dict[str, int]
    sources: list[SourceStatus] = field(default_factory=list)
    items: list[ItemStatus] = field(default_factory=list)
    problems: list[StatusProblem] = field(default_factory=list)
    last_run: dict[str, Any] | None = None
    review_backlog: dict[str, Any] = field(default_factory=dict)
    detail_mode: str = "audit"
    recommended_next_action: str = "no action"

    def as_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "source_filter": self.source_filter,
            "sources_configured": self.sources_configured,
            "sources_discoverable": self.sources_discoverable,
            "lock": self.lock,
            "extraction": self.extraction,
            "pilot_readiness": self.pilot_readiness,
            "counts": self.counts,
            "recommended_next_action": self.recommended_next_action,
            "sources": [asdict(source) for source in self.sources],
            "items": [asdict(item) for item in self.items],
            "problems": [asdict(problem) for problem in self.problems],
            "last_run": self.last_run,
            "review_backlog": self.review_backlog,
            "detail_mode": self.detail_mode,
        }


class _StatusOrchestrationService(MediaOrchestrationService):
    """Use production parent resolution against one defensively loaded draft set."""

    def __init__(self, *, runtime_drafts: list[dict[str, Any]], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._runtime_drafts = runtime_drafts

    def _publication_drafts_for(self, item: dict[str, Any], deterministic_id: str) -> list[dict[str, Any]]:
        return [
            draft
            for draft in self._runtime_drafts
            if draft.get("evidence_role") == "publication_artifact"
            and (draft.get("id") == deterministic_id or draft.get("discovered_item_id") == item.get("id"))
        ]


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds")


def _source_name(source: dict[str, Any]) -> str:
    return source.get("label") or source.get("name") or source.get("value") or source.get("id") or "Unknown Source"


def _safe_runtime_records(
    folder: Path,
    *,
    kind: str,
    problems: list[StatusProblem],
) -> list[dict[str, Any]]:
    if not folder.exists():
        return []
    records: list[dict[str, Any]] = []
    for path in sorted(folder.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("JSON root must be an object")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            problems.append(StatusProblem(kind=kind, identity=path.name, message=f"Malformed {kind}: {exc}"))
            continue
        records.append(payload)
    return records


def _load_discovered_items(inbox_dir: Path, problems: list[StatusProblem]) -> list[dict[str, Any]]:
    """Prefer the discovery service; isolate files only when its bulk read fails."""

    try:
        return list_discovered_items(inbox_dir)
    except (OSError, ValueError, json.JSONDecodeError):
        return _safe_runtime_records(
            inbox_dir / "discovered_media",
            kind="discovered item",
            problems=problems,
        )


def _operation_states(
    operations: OperationalStateStore,
    items: list[dict[str, Any]],
    problems: list[StatusProblem],
) -> dict[str, dict[str, Any]]:
    states: dict[str, dict[str, Any]] = {}
    known_paths: set[Path] = set()
    for item in items:
        item_id = item.get("id")
        if not isinstance(item_id, str):
            continue
        path = operations.operations_dir / "items" / f"{_slug(item_id)}.json"
        known_paths.add(path.resolve())
        try:
            state = operations.item_state(item_id)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            problems.append(StatusProblem(
                kind="operational item state",
                identity=item_id,
                source_id=item.get("source_id"),
                message=f"Malformed operational item state: {exc}",
            ))
            continue
        if state:
            states[item_id] = state
    folder = operations.operations_dir / "items"
    if folder.exists():
        for path in sorted(folder.glob("*.json")):
            if path.resolve() in known_paths:
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(payload, dict) or not isinstance(payload.get("item_id"), str):
                    raise ValueError("orphan operational record requires item_id")
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                problems.append(StatusProblem(
                    kind="operational item state",
                    identity=path.name,
                    message=f"Malformed or orphan operational state: {exc}",
                ))
                continue
            problems.append(StatusProblem(
                kind="orphan operational item state",
                identity=payload["item_id"],
                source_id=payload.get("source_id"),
                message="Operational state has no corresponding discovered item.",
            ))
    return states


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", value.casefold()).strip("-") or "unknown"


def _lock_status(
    lock_path: Path,
    *,
    now: datetime,
    stale_after: timedelta,
    problems: list[StatusProblem],
) -> dict[str, Any]:
    if not lock_path.exists():
        return {"state": "none", "active": False, "stale": False, "run_id": None, "started_at": None}
    try:
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("lock root must be an object")
        started_raw = payload.get("started_at")
        started = datetime.fromisoformat(started_raw) if isinstance(started_raw, str) else None
        if started is None:
            raise ValueError("lock started_at is required")
        if started.tzinfo is None:
            started = started.replace(tzinfo=UTC)
        stale = now.astimezone(UTC) - started.astimezone(UTC) > stale_after
        return {
            "state": "stale" if stale else "active",
            "active": not stale,
            "stale": stale,
            "run_id": payload.get("run_id"),
            "started_at": started_raw,
            "age_seconds": max(0, int((now.astimezone(UTC) - started.astimezone(UTC)).total_seconds())),
        }
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        problems.append(StatusProblem(kind="runner lock", identity=lock_path.name, message=f"Malformed runner lock: {exc}"))
        return {"state": "malformed", "active": False, "stale": False, "run_id": None, "started_at": None}


def _last_run(operations_dir: Path, problems: list[StatusProblem]) -> dict[str, Any] | None:
    folder = operations_dir / "runs"
    candidates = sorted(folder.glob("*.json")) if folder.is_dir() else []
    if not candidates:
        return None
    path = candidates[-1]
    try:
        selected = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(selected, dict):
            raise ValueError("JSON root must be an object")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        problems.append(StatusProblem(
            kind="collection run",
            identity=path.name,
            message=f"Malformed collection run: {exc}",
        ))
        return None
    return {
        "run_id": selected.get("run_id"),
        "started_at": selected.get("started_at"),
        "completed_at": selected.get("completed_at"),
        "dry_run": selected.get("dry_run"),
        "counts": selected.get("counts") if isinstance(selected.get("counts"), dict) else {},
        "sources": selected.get("sources") if isinstance(selected.get("sources"), list) else [],
    }


def _draft_backlog(drafts: list[dict[str, Any]]) -> tuple[dict[str, int], dict[str, int]]:
    by_source: dict[str, int] = {}
    counts = {
        "publication_review": 0,
        "atomic_review": 0,
        "enrichment_ready": 0,
    }
    for draft in drafts:
        rejected = draft.get("status") == "rejected" or draft.get("review_state") == "rejected"
        if rejected:
            continue
        role = draft.get("evidence_role")
        if role == "publication_artifact":
            counts["publication_review"] += 1
            source_id = draft.get("source_id")
            if isinstance(source_id, str):
                by_source[source_id] = by_source.get(source_id, 0) + 1
            if (draft.get("ai_enrichment") or {}).get("model_provenance", {}).get("status") == "ok":
                counts["enrichment_ready"] += 1
        elif role == "atomic_evidence":
            counts["atomic_review"] += 1
    return counts, by_source


def _atomic_by_parent(
    *,
    drafts: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    entities: list[dict[str, Any]],
) -> dict[tuple[str, str], dict[str, int]]:
    workbench = build_review_workbench(
        drafts=drafts,
        evidence=evidence,
        sources=sources,
        entities=entities,
        berry_labels={},
        filters={"kind": "atomic", "state": "all", "sort": "timestamp"},
    )
    totals: dict[tuple[str, str], dict[str, int]] = {}
    for group in workbench["groups"]:
        key = (group["parent_id"], group["transcript_id"])
        bucket = totals.setdefault(key, {"pending": 0, "approved": 0, "rejected": 0})
        progress = group["progress"]
        bucket["pending"] += progress["remaining"]
        bucket["approved"] += progress["approved"]
        bucket["rejected"] += progress["rejected"]
    return totals


def _classify_item(
    *,
    item: dict[str, Any],
    result: Any,
    operation: dict[str, Any],
    atomic: dict[str, int],
    extraction_gate: ExtractionGate,
    retry_limit: int,
) -> ItemStatus:
    item_id = item.get("id") or "unknown-item"
    source_id = item.get("source_id")
    base = dict(
        item_id=item_id,
        source_id=source_id,
        title=item.get("title") or item_id,
        publication_state=result.parent_resolution.status,
        transcript_state=result.transcript_status,
        parent_evidence_id=result.parent_resolution.evidence_id,
        publication_draft_id=result.publication_draft_id,
        pending_atomic_proposals=atomic.get("pending", 0),
        approved_atomic_evidence=atomic.get("approved", 0),
        rejected_atomic_proposals=atomic.get("rejected", 0),
        retry_count=int(operation.get("retry_count", 0) or 0),
        next_eligible_retry_at=operation.get("next_eligible_retry_at"),
        error=operation.get("last_error") or ("; ".join(result.errors) if result.errors else None),
    )
    screening = item.get("relevance_screening") or {}
    if screening.get("decision") == "skip" and result.parent_resolution.status in {"none", "skipped", "would_create_draft"}:
        return ItemStatus(
            **base,
            category="completed_no_action",
            recommended_action="no action",
            reason=screening.get("reason") or "Screened as clearly irrelevant before transcription.",
        )
    if result.state == "skipped_irrelevant":
        return ItemStatus(**base, category="completed_no_action", recommended_action="no action", reason=base["error"] or "Screened as clearly irrelevant before transcription.")
    if result.state == "publication_rejected":
        return ItemStatus(**base, category="completed_no_action", recommended_action="no action", reason="Publication was rejected by human review.")
    failure = operation.get("failure_class")
    if failure == "operator" or (failure == "retryable" and base["retry_count"] >= retry_limit):
        return ItemStatus(**base, category="operator_intervention_required", recommended_action="resolve operator-action failure", reason=base["error"] or "Operator correction is required before retry.")
    if failure == "retryable":
        return ItemStatus(**base, category="retryable_failure", recommended_action="run collection", reason=base["error"] or "Runner retry is pending under bounded backoff.")
    if atomic.get("pending", 0):
        return ItemStatus(**base, category="human_atomic_evidence_review_required", recommended_action="review atomic evidence", reason=f"{atomic['pending']} untrusted Atomic Evidence proposal(s) await review.")
    if result.state == "awaiting_publication_review":
        return ItemStatus(**base, category="human_publication_review_required", recommended_action="review publication", reason="Publication draft awaits human review.")
    if result.state == "ready_for_extraction":
        transcript_hash = result.transcript_sha256
        if atomic.get("approved", 0) or atomic.get("rejected", 0):
            return ItemStatus(**base, category="completed_no_action", recommended_action="no action", reason="Atomic Evidence review outcomes already exist; extraction is not repeated.")
        if transcript_hash and operation.get("extraction_completed_transcript_sha256") == transcript_hash:
            return ItemStatus(**base, category="completed_no_action", recommended_action="no action", reason="Extraction completion, including a possible zero-candidate result, is recorded.")
        if extraction_gate.runnable:
            return ItemStatus(**base, category="extraction_ready", recommended_action="run collection", reason="Trusted publication and transcript are eligible for qualified extraction.")
        return ItemStatus(**base, category="extraction_blocked", recommended_action="qualify extraction model", reason=extraction_gate.reason)
    if result.transcript_status == "malformed" or result.parent_resolution.status == "ambiguous" or result.errors:
        return ItemStatus(**base, category="operator_intervention_required", recommended_action="resolve operator-action failure", reason="; ".join(result.errors) or result.parent_resolution.message)
    return ItemStatus(**base, category="ready_to_advance", recommended_action="run collection", reason=result.next_action)


def _action_for_counts(counts: dict[str, int], *, lock: dict[str, Any]) -> str:
    if lock.get("active"):
        return "no action"
    rules = (
        ("operator_intervention_required", "resolve operator-action failure"),
        ("human_atomic_evidence_review_required", "review atomic evidence"),
        ("human_publication_review_required", "review publication"),
        ("extraction_blocked", "qualify extraction model"),
        ("extraction_ready", "run collection"),
        ("retryable_failure", "run collection"),
        ("ready_to_advance", "run collection"),
    )
    for category, action in rules:
        if counts.get(category, 0):
            return action
    return "no action"


class CollectionStatusService:
    def __init__(
        self,
        *,
        repositories: Any,
        inbox_dir: Path,
        operations: OperationalStateStore,
        evidence_errors: Callable[[dict[str, Any]], list[str]],
        extraction_gate: ExtractionGate,
        extraction_blockers: list[str],
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        retry_limit: int = 3,
        lock_stale_after: timedelta = timedelta(hours=6),
    ) -> None:
        self._repos = repositories
        self._inbox = inbox_dir
        self._operations = operations
        self._evidence_errors = evidence_errors
        self._gate = extraction_gate
        self._extraction_blockers = list(extraction_blockers)
        self._now = now
        self._retry_limit = retry_limit
        self._lock_stale_after = lock_stale_after

    def build(
        self,
        *,
        source_id: str | None = None,
        persisted_only: bool = False,
    ) -> CollectionStatusReport:
        if persisted_only and source_id is None:
            report = self._build_persisted()
            if report is not None:
                return report
        return self._build_audit(source_id=source_id)

    def _build_persisted(self) -> CollectionStatusReport | None:
        """Build the operator view from persisted run and review state only.

        The scheduled runner already persisted the expensive orchestration
        decisions. Replaying MediaOrchestrationService for every discovered
        item made the read-only status command quadratic in Evidence/draft
        files and exceeded 35 minutes in production. This path intentionally
        does not derive per-item decisions; ``_build_audit`` remains available
        for an explicit deep audit.
        """

        now = self._now().astimezone(UTC)
        problems: list[StatusProblem] = []
        last_run = _last_run(self._operations.operations_dir, problems)
        if last_run is None:
            return None
        sources = sorted(self._repos.sources.list(), key=lambda source: source.get("id", ""))
        source_index = {source["id"]: source for source in sources if source.get("id")}
        eligibility_probe = CollectionRunner(
            repositories=self._repos,
            inbox_dir=self._inbox,
            operations=self._operations,
            discover=lambda _source_id: None,
            orchestrate=lambda *_args: None,
            transcript_cache_ready=lambda _item: False,
        )
        discoverable_ids = eligibility_probe.eligible_source_ids()
        drafts = _safe_runtime_records(self._inbox / "evidence", kind="Evidence draft", problems=problems)
        backlog, backlog_by_source = _draft_backlog(drafts)
        evidence = self._repos.evidence.list()
        trusted_by_source: dict[str, int] = {}
        for record in evidence:
            if record.get("evidence_role") == "publication_artifact" and record.get("status") == "published":
                sid = record.get("source_id")
                if isinstance(sid, str):
                    trusted_by_source[sid] = trusted_by_source.get(sid, 0) + 1

        lock = _lock_status(
            self._operations.lock_path,
            now=now,
            stale_after=self._lock_stale_after,
            problems=problems,
        )
        run_counts = dict(last_run.get("counts") or {})
        failed_sources = [
            result
            for result in last_run.get("sources", [])
            if isinstance(result, dict) and result.get("status") not in {"ok", "planned"}
        ]
        for result in failed_sources:
            problems.append(StatusProblem(
                kind="source collection",
                identity=str(result.get("source_id") or "unknown-source"),
                source_id=result.get("source_id") if isinstance(result.get("source_id"), str) else None,
                message=str(result.get("error") or result.get("status") or "source collection failed"),
            ))

        item_total = int(run_counts.get("items_processed", 0) or 0)
        retryable = int(run_counts.get("retryable_failures", 0) or 0)
        intervention = int(run_counts.get("operator_action_items", 0) or 0)
        skipped = int(run_counts.get("irrelevant_rejected", 0) or 0)
        extraction_ready = int(run_counts.get("ready_for_extraction", 0) or 0)
        completed = max(0, item_total - backlog["publication_review"] - retryable - intervention - extraction_ready)
        counts = {
            "sources_configured": len(sources),
            "sources_discoverable": len(discoverable_ids),
            "ready_to_advance": 0,
            "human_publication_review_required": backlog["publication_review"],
            "extraction_ready": extraction_ready if self._gate.runnable else 0,
            "extraction_blocked": extraction_ready if not self._gate.runnable else 0,
            "human_atomic_evidence_review_required": backlog["atomic_review"],
            "retryable_failure": retryable,
            "operator_intervention_required": intervention,
            "completed_no_action": completed,
            "pending_atomic_proposals": backlog["atomic_review"],
            "discovered": item_total,
            "relevant": int(run_counts.get("direct_review_ready", 0) or 0) + int(run_counts.get("adjacent_review_ready", 0) or 0),
            "skipped_irrelevant": skipped,
            "transcript_ready": int(run_counts.get("transcripts_ready", 0) or 0),
            "enrichment_ready": backlog["enrichment_ready"],
            "publication_review_ready": backlog["publication_review"],
            "trusted_publication": sum(trusted_by_source.values()),
            "atomic_proposals": backlog["atomic_review"],
            "intervention": intervention,
        }
        latest_source_results = {
            result.get("source_id"): result
            for result in last_run.get("sources", [])
            if isinstance(result, dict) and isinstance(result.get("source_id"), str)
        }
        source_reports: list[SourceStatus] = []
        for sid in discoverable_ids:
            source = source_index[sid]
            result = latest_source_results.get(sid, {})
            failed = result.get("status") not in {None, "ok", "planned"}
            source_reports.append(SourceStatus(
                source_id=sid,
                name=_source_name(source),
                adapter=(source.get("discovery") or {}).get("adapter"),
                discoverable=True,
                discovered_items=int(result.get("found", 0) or 0),
                pending_publication_review=backlog_by_source.get(sid, 0),
                trusted_publications=trusted_by_source.get(sid, 0),
                retryable_failures=0,
                operator_intervention=1 if failed else 0,
                last_discovery_status=result.get("status"),
                last_discovery_new=result.get("new") if isinstance(result.get("new"), int) else None,
                recommended_next_action="resolve operator-action failure" if failed else "no action",
            ))

        collection_blockers: list[str] = []
        if lock.get("active"):
            collection_blockers.append("a collection run currently owns the runner lock")
        if lock.get("state") == "malformed":
            collection_blockers.append("runner lock is malformed and requires operator inspection")
        readiness = {
            "collection_only": {
                "state": "READY" if not collection_blockers else "BLOCKED",
                "blockers": collection_blockers,
                "note": "A qualified semantic extraction model is not required for collection-only operation.",
            },
            "extraction_enabled": {
                "state": "READY" if not collection_blockers and self._gate.runnable else "BLOCKED",
                "blockers": [*collection_blockers, *self._extraction_blockers],
                "note": "Even when ready, extraction creates only untrusted Atomic Evidence proposals.",
            },
        }
        if lock.get("active"):
            recommended = "no action"
        elif intervention or failed_sources:
            recommended = "resolve operator-action failure"
        elif backlog["atomic_review"]:
            recommended = "review atomic evidence"
        elif backlog["publication_review"]:
            recommended = "review publication"
        else:
            recommended = "no action"
        created = int(run_counts.get("publication_drafts_created", 0) or 0)
        return CollectionStatusReport(
            generated_at=_iso(now),
            source_filter=None,
            sources_configured=len(sources),
            sources_discoverable=len(discoverable_ids),
            lock=lock,
            extraction={**self._gate.as_dict(), "blockers": list(self._extraction_blockers)},
            pilot_readiness=readiness,
            counts=counts,
            sources=source_reports,
            items=[],
            problems=problems,
            last_run=last_run,
            review_backlog={
                "publication_review": backlog["publication_review"],
                "atomic_review": backlog["atomic_review"],
                "drafts_created_last_run": created,
                "backlog_to_last_run_created_ratio": round(backlog["publication_review"] / created, 2) if created else None,
                "trend": "growth_pressure" if created > 0 else "flat_or_unknown",
            },
            detail_mode="persisted",
            recommended_next_action=recommended,
        )

    def _build_audit(self, *, source_id: str | None = None) -> CollectionStatusReport:
        now = self._now().astimezone(UTC)
        problems: list[StatusProblem] = []
        sources = sorted(self._repos.sources.list(), key=lambda source: source.get("id", ""))
        source_index = {source["id"]: source for source in sources if source.get("id")}
        if source_id and source_id not in source_index:
            raise ValueError(f"Source not found: {source_id}")
        eligibility_probe = CollectionRunner(
            repositories=self._repos,
            inbox_dir=self._inbox,
            operations=self._operations,
            discover=lambda _source_id: None,
            orchestrate=lambda *_args: None,
            transcript_cache_ready=lambda _item: False,
        )
        discoverable_ids = eligibility_probe.eligible_source_ids()
        selected_source_ids = [source_id] if source_id else discoverable_ids
        selected_set = set(selected_source_ids)

        all_items = _load_discovered_items(self._inbox, problems)
        items = [item for item in all_items if item.get("source_id") in selected_set]
        drafts = _safe_runtime_records(self._inbox / "evidence", kind="Evidence draft", problems=problems)
        operations = _operation_states(self._operations, items, problems)
        lock = _lock_status(
            self._operations.lock_path,
            now=now,
            stale_after=self._lock_stale_after,
            problems=problems,
        )
        last_run = _last_run(self._operations.operations_dir, problems)
        evidence = self._repos.evidence.list()
        entities = self._repos.entities.list()
        atomic_by_parent = _atomic_by_parent(
            drafts=drafts,
            evidence=evidence,
            sources=sources,
            entities=entities,
        )
        orchestrator = _StatusOrchestrationService(
            repositories=self._repos,
            inbox_dir=self._inbox,
            evidence_errors=self._evidence_errors,
            transcript_adapter=MediaTranscriptionAdapter(self._inbox, transcribe_missing=False),
            extraction_service=None,
            runtime_drafts=drafts,
        )

        item_statuses: list[ItemStatus] = []
        for item in sorted(items, key=lambda value: (value.get("source_id", ""), value.get("id", ""))):
            item_id = item.get("id")
            if not isinstance(item_id, str):
                problems.append(StatusProblem(kind="discovered item", identity="unknown", message="Discovered item has no string id."))
                continue
            try:
                result = orchestrator.process(item_id, dry_run=True)
            except (OSError, ValueError, MediaOrchestrationError, json.JSONDecodeError) as exc:
                problems.append(StatusProblem(
                    kind="discovered item",
                    identity=item_id,
                    source_id=item.get("source_id"),
                    message=f"Could not derive item status: {exc}",
                ))
                continue
            parent_id = result.parent_resolution.evidence_id
            atomic = atomic_by_parent.get(
                (parent_id or "", result.transcript_id or "unknown-transcript"),
                {"pending": 0, "approved": 0, "rejected": 0},
            )
            item_statuses.append(_classify_item(
                item=item,
                result=result,
                operation=operations.get(item_id, {}),
                atomic=atomic,
                extraction_gate=self._gate,
                retry_limit=self._retry_limit,
            ))

        relevant_problems = [
            problem for problem in problems
            if source_id is None or problem.source_id in {None, source_id}
        ]
        category_counts = {category: sum(item.category == category for item in item_statuses) for category in STATUS_CATEGORIES}
        category_counts["operator_intervention_required"] += len(relevant_problems)
        category_counts["pending_atomic_proposals"] = sum(item.pending_atomic_proposals for item in item_statuses)

        trusted_by_source: dict[str, int] = {}
        for record in evidence:
            if record.get("evidence_role") == "publication_artifact" and record.get("status") == "published":
                sid = record.get("source_id")
                if isinstance(sid, str):
                    trusted_by_source[sid] = trusted_by_source.get(sid, 0) + 1
        latest_source_results = {
            value.get("source_id"): value
            for value in (last_run or {}).get("sources", [])
            if isinstance(value, dict) and isinstance(value.get("source_id"), str)
        }
        source_reports: list[SourceStatus] = []
        for sid in selected_source_ids:
            source = source_index[sid]
            statuses = [item for item in item_statuses if item.source_id == sid]
            source_problems = [problem for problem in relevant_problems if problem.source_id == sid]
            last_source = latest_source_results.get(sid, {})
            discovery_state = read_source_discovery_state(self._inbox, sid)
            published_at, captured_at = latest_item_dates(
                discovered_items=all_items, published_evidence=evidence, source_id=sid,
            )
            freshness = classify_source_freshness(
                source,
                discovery_state=discovery_state,
                latest_item_published_at=published_at,
                latest_item_captured_at=captured_at,
                today=now.date(),
            )
            report = SourceStatus(
                source_id=sid,
                name=_source_name(source),
                adapter=(source.get("discovery") or {}).get("adapter"),
                discoverable=sid in discoverable_ids,
                discovered_items=len([item for item in items if item.get("source_id") == sid]),
                pending_publication_review=sum(item.category == "human_publication_review_required" for item in statuses),
                trusted_publications=trusted_by_source.get(sid, 0),
                extraction_ready=sum(item.category == "extraction_ready" for item in statuses),
                extraction_blocked=sum(item.category == "extraction_blocked" for item in statuses),
                pending_atomic_review=sum(item.pending_atomic_proposals for item in statuses),
                retryable_failures=sum(item.category == "retryable_failure" for item in statuses),
                operator_intervention=sum(item.category == "operator_intervention_required" for item in statuses) + len(source_problems),
                completed_no_action=sum(item.category == "completed_no_action" for item in statuses),
                last_discovery_status=last_source.get("status"),
                last_discovery_new=last_source.get("new") if isinstance(last_source.get("new"), int) else None,
                freshness=freshness.as_dict(),
            )
            local_counts = {category: sum(item.category == category for item in statuses) for category in STATUS_CATEGORIES}
            local_counts["operator_intervention_required"] += len(source_problems)
            report.recommended_next_action = _action_for_counts(local_counts, lock=lock)
            if report.recommended_next_action == "no action" and report.discovered_items == 0 and report.discoverable:
                report.recommended_next_action = (
                    "no action" if report.last_discovery_status == "ok" and report.last_discovery_new == 0 else "run collection"
                )
            source_reports.append(report)

        collection_blockers: list[str] = []
        if not selected_source_ids or any(sid not in discoverable_ids for sid in selected_source_ids):
            collection_blockers.append("no usable discovery configuration in the selected scope")
        if lock.get("active"):
            collection_blockers.append("a collection run currently owns the runner lock")
        if lock.get("state") == "malformed":
            collection_blockers.append("runner lock is malformed and requires operator inspection")
        malformed_items = [problem for problem in relevant_problems if problem.kind == "discovered item"]
        if malformed_items:
            collection_blockers.append("one or more staged discovery items are malformed")
        collection_ready = not collection_blockers
        extraction_blockers = list(self._extraction_blockers)
        if not collection_ready:
            extraction_blockers = [*collection_blockers, *extraction_blockers]
        extraction_ready = collection_ready and self._gate.runnable and not extraction_blockers
        readiness = {
            "collection_only": {
                "state": "READY" if collection_ready else "BLOCKED",
                "blockers": collection_blockers,
                "note": "A qualified semantic extraction model is not required for collection-only operation.",
            },
            "extraction_enabled": {
                "state": "READY" if extraction_ready else "BLOCKED",
                "blockers": extraction_blockers,
                "note": "Even when ready, extraction creates only untrusted Atomic Evidence proposals.",
            },
        }
        screening_by_id = {
            item.get("id"): (item.get("relevance_screening") or {})
            for item in items
            if isinstance(item.get("id"), str)
        }
        skipped_irrelevant = sum(
            1
            for status in item_statuses
            if (screening_by_id.get(status.item_id) or {}).get("decision") == "skip"
            or "irrelevant" in (status.reason or "").casefold()
        )
        relevant = sum(
            1
            for status in item_statuses
            if (screening_by_id.get(status.item_id) or {}).get("decision") == "process"
        )
        counts = {
            "sources_configured": len(sources),
            "sources_discoverable": len(discoverable_ids),
            **category_counts,
            "discovered": len(item_statuses),
            "relevant": relevant,
            "skipped_irrelevant": skipped_irrelevant,
            "transcript_ready": sum(1 for item in item_statuses if item.transcript_state == "ready"),
            "enrichment_ready": sum(
                1
                for draft in drafts
                if draft.get("evidence_role") == "publication_artifact"
                and (draft.get("ai_enrichment") or {}).get("model_provenance", {}).get("status") == "ok"
            ),
            "publication_review_ready": category_counts.get("human_publication_review_required", 0),
            "trusted_publication": sum(trusted_by_source.values()),
            "atomic_proposals": category_counts.get("pending_atomic_proposals", 0),
            "retryable_failure": category_counts.get("retryable_failure", 0),
            "intervention": category_counts.get("operator_intervention_required", 0),
        }
        recommended = _action_for_counts(category_counts, lock=lock)
        if recommended == "no action" and collection_ready and any(source.recommended_next_action == "run collection" for source in source_reports):
            recommended = "run collection"
        return CollectionStatusReport(
            generated_at=_iso(now),
            source_filter=source_id,
            sources_configured=len(sources),
            sources_discoverable=len(discoverable_ids),
            lock=lock,
            extraction={**self._gate.as_dict(), "blockers": list(self._extraction_blockers)},
            pilot_readiness=readiness,
            counts=counts,
            sources=source_reports,
            items=item_statuses,
            problems=relevant_problems,
            last_run=last_run,
            recommended_next_action=recommended,
        )
