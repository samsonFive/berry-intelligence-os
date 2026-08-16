"""Scheduler-friendly coordination for the existing spoken-word pipeline.

This module owns operational iteration, locking, retry eligibility, and run
reporting. It deliberately delegates every domain transition to the existing
discovery, transcription, orchestration, and extraction services. Operational
records live under gitignored ``inbox/operations`` and never become trusted
intelligence.
"""

from __future__ import annotations

from contextlib import nullcontext
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
from typing import Any, Callable, ContextManager

from app.services.media_discovery import DiscoveryError, DiscoveryRunResult, list_discovered_items


UTC = timezone.utc
RETRYABLE_MARKERS = (
    "timeout",
    "timed out",
    "temporar",
    "transport",
    "connection",
    "rate limit",
    "http 429",
    "http 5",
    "endpoint unavailable",
    "fetch failed",
)
TERMINAL_MARKERS = (
    "no speech",
    "unsupported media",
    "malformed transcript",
    "parent mismatch",
    "ambiguous publication",
    "does not resolve",
)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds")


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", value.casefold()).strip("-") or "unknown"


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"operational record must be a JSON object: {path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


class CollectionLockedError(RuntimeError):
    """Another non-stale recurring run owns the local workspace lock."""


class CollectionRunLock:
    def __init__(
        self,
        path: Path,
        *,
        run_id: str,
        now: Callable[[], datetime] = _utc_now,
        stale_after: timedelta = timedelta(hours=6),
    ) -> None:
        self.path = path
        self.run_id = run_id
        self._now = now
        self._stale_after = stale_after
        self.recovered_stale_lock = False

    def __enter__(self) -> "CollectionRunLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            existing = _read_json(self.path) or {}
            started_raw = existing.get("started_at")
            try:
                started = datetime.fromisoformat(started_raw) if isinstance(started_raw, str) else None
                if started is not None and started.tzinfo is None:
                    started = started.replace(tzinfo=UTC)
            except ValueError:
                started = None
            if started is not None and self._now() - started.astimezone(UTC) <= self._stale_after:
                raise CollectionLockedError(
                    f"collection run already active: {existing.get('run_id', 'unknown')} since {started_raw}"
                )
            self.path.unlink()
            self.recovered_stale_lock = True
        payload = {"run_id": self.run_id, "started_at": _iso(self._now()), "pid": os.getpid()}
        try:
            with self.path.open("x", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
                handle.write("\n")
        except FileExistsError as exc:
            raise CollectionLockedError("another collection run acquired the lock") from exc
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        try:
            current = _read_json(self.path)
        except (OSError, ValueError, json.JSONDecodeError):
            current = None
        if current and current.get("run_id") == self.run_id:
            self.path.unlink(missing_ok=True)


@dataclass(frozen=True)
class ExtractionQualification:
    provider: str
    model: str
    prompt_version: str
    operator_qualified: bool
    qualified_by: str
    qualified_at: str

    @classmethod
    def load(cls, path: Path) -> "ExtractionQualification":
        payload = _read_json(path)
        if payload is None:
            raise ValueError(f"qualification file not found: {path}")
        required = ("provider", "model", "prompt_version", "qualified_by", "qualified_at")
        missing = [key for key in required if not isinstance(payload.get(key), str) or not payload[key].strip()]
        if missing or payload.get("operator_qualified") is not True:
            detail = ", ".join(missing) if missing else "operator_qualified=true"
            raise ValueError(f"invalid model qualification marker; required: {detail}")
        try:
            datetime.fromisoformat(payload["qualified_at"])
        except ValueError as exc:
            raise ValueError("invalid model qualification marker; qualified_at must be ISO-8601") from exc
        return cls(
            provider=payload["provider"],
            model=payload["model"],
            prompt_version=payload["prompt_version"],
            operator_qualified=True,
            qualified_by=payload["qualified_by"],
            qualified_at=payload["qualified_at"],
        )

    def matches(self, *, provider: str, model: str, prompt_version: str) -> bool:
        return (
            self.operator_qualified
            and self.provider == provider
            and self.model == model
            and self.prompt_version == prompt_version
        )


@dataclass(frozen=True)
class ExtractionGate:
    enabled: bool = False
    configured: bool = False
    qualified: bool = False
    provider: str | None = None
    model: str | None = None
    prompt_version: str | None = None
    reason: str = "extraction disabled"

    @property
    def runnable(self) -> bool:
        return self.enabled and self.configured and self.qualified

    def as_dict(self) -> dict[str, Any]:
        return asdict(self) | {"runnable": self.runnable}


def resolve_extraction_gate(
    *,
    enabled: bool,
    provider: str,
    model: str | None,
    base_url: str | None,
    prompt_version: str,
    qualification_path: Path | None,
) -> ExtractionGate:
    if not enabled:
        return ExtractionGate(
            enabled=False,
            provider=provider,
            model=model,
            prompt_version=prompt_version,
            reason="extraction disabled by default; pass --enable-extraction to opt in",
        )
    if not model or not base_url:
        return ExtractionGate(
            enabled=True,
            configured=False,
            provider=provider,
            model=model,
            prompt_version=prompt_version,
            reason="extraction enabled but endpoint/model configuration is incomplete",
        )
    if qualification_path is None:
        return ExtractionGate(
            enabled=True,
            configured=True,
            provider=provider,
            model=model,
            prompt_version=prompt_version,
            reason="extraction ready but no operator qualification marker was supplied",
        )
    try:
        qualification = ExtractionQualification.load(qualification_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return ExtractionGate(
            enabled=True,
            configured=True,
            provider=provider,
            model=model,
            prompt_version=prompt_version,
            reason=f"extraction ready but model is not qualified: {exc}",
        )
    if not qualification.matches(provider=provider, model=model, prompt_version=prompt_version):
        return ExtractionGate(
            enabled=True,
            configured=True,
            provider=provider,
            model=model,
            prompt_version=prompt_version,
            reason="qualification marker does not match the exact provider/model/prompt version",
        )
    return ExtractionGate(
        enabled=True,
        configured=True,
        qualified=True,
        provider=provider,
        model=model,
        prompt_version=prompt_version,
        reason="exact provider/model/prompt version is operator-qualified",
    )


@dataclass
class SourceResult:
    source_id: str
    status: str
    found: int = 0
    new: int = 0
    known: int = 0
    error: str | None = None


@dataclass
class ItemResult:
    item_id: str
    source_id: str
    state: str
    transcript_status: str = "unknown"
    transcription_attempted: bool = False
    publication_draft_id: str | None = None
    publication_draft_created: bool = False
    parent_evidence_id: str | None = None
    proposals_created: int = 0
    atomic_review: dict[str, int] = field(default_factory=dict)
    failure_class: str | None = None
    error: str | None = None
    next_action: str = ""


@dataclass
class CollectionRunSummary:
    run_id: str
    started_at: str
    completed_at: str | None = None
    dry_run: bool = False
    source_scope: str = "all"
    extraction_gate: dict[str, Any] = field(default_factory=dict)
    sources: list[SourceResult] = field(default_factory=list)
    items: list[ItemResult] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    stale_lock_recovered: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "dry_run": self.dry_run,
            "source_scope": self.source_scope,
            "extraction_gate": self.extraction_gate,
            "sources": [asdict(result) for result in self.sources],
            "items": [asdict(result) for result in self.items],
            "counts": self.counts,
            "stale_lock_recovered": self.stale_lock_recovered,
        }


class OperationalStateStore:
    """Small JSON operational store; domain records remain authoritative."""

    def __init__(self, operations_dir: Path) -> None:
        self.operations_dir = operations_dir

    @property
    def lock_path(self) -> Path:
        return self.operations_dir / "collection.lock"

    def item_state(self, item_id: str) -> dict[str, Any]:
        return _read_json(self.operations_dir / "items" / f"{_slug(item_id)}.json") or {}

    def save_item_state(self, item_id: str, state: dict[str, Any]) -> None:
        _write_json(self.operations_dir / "items" / f"{_slug(item_id)}.json", state)

    def save_run(self, summary: CollectionRunSummary) -> Path:
        path = self.operations_dir / "runs" / f"{summary.run_id}.json"
        _write_json(path, summary.as_dict())
        return path


class CollectionRunner:
    """Coordinate one bounded, resumable recurring collection run."""

    def __init__(
        self,
        *,
        repositories: Any,
        inbox_dir: Path,
        operations: OperationalStateStore,
        discover: Callable[[str], DiscoveryRunResult],
        orchestrate: Callable[[str, bool, bool, bool], Any],
        transcript_cache_ready: Callable[[dict[str, Any]], bool],
        extraction_gate: ExtractionGate = ExtractionGate(),
        now: Callable[[], datetime] = _utc_now,
        run_id_factory: Callable[[datetime], str] | None = None,
        retry_limit: int = 3,
        retry_backoff: timedelta = timedelta(minutes=30),
        lock_stale_after: timedelta = timedelta(hours=6),
    ) -> None:
        self._repos = repositories
        self._inbox_dir = inbox_dir
        self._operations = operations
        self._discover = discover
        self._orchestrate = orchestrate
        self._transcript_cache_ready = transcript_cache_ready
        self._gate = extraction_gate
        self._now = now
        self._run_id_factory = run_id_factory or (
            lambda instant: "collection-" + instant.astimezone(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        )
        self._retry_limit = max(0, retry_limit)
        self._retry_backoff = retry_backoff
        self._lock_stale_after = lock_stale_after

    def eligible_source_ids(self) -> list[str]:
        ids = []
        for source in self._repos.sources.list():
            discovery = source.get("discovery") or {}
            if discovery.get("adapter") and (discovery.get("feed_url") or discovery.get("feed_urls")):
                ids.append(source["id"])
        return sorted(ids)

    def run(
        self,
        *,
        source_id: str | None = None,
        dry_run: bool = False,
        skip_transcription: bool = False,
        max_transcriptions: int | None = None,
        max_items: int | None = None,
        retry_operator_items: bool = False,
    ) -> CollectionRunSummary:
        started = self._now()
        run_id = self._run_id_factory(started)
        eligible = self.eligible_source_ids()
        if source_id is not None:
            if source_id not in eligible:
                raise DiscoveryError(f"source {source_id!r} has no usable discovery configuration")
            source_ids = [source_id]
        else:
            source_ids = eligible
        summary = CollectionRunSummary(
            run_id=run_id,
            started_at=_iso(started),
            dry_run=dry_run,
            source_scope=source_id or "all",
            extraction_gate=self._gate.as_dict(),
        )
        lock: ContextManager[Any]
        lock = nullcontext() if dry_run else CollectionRunLock(
            self._operations.lock_path,
            run_id=run_id,
            now=self._now,
            stale_after=self._lock_stale_after,
        )
        with lock as acquired_lock:
            if acquired_lock is not None:
                summary.stale_lock_recovered = acquired_lock.recovered_stale_lock
            self._run_sources(summary, source_ids, dry_run=dry_run)
            self._run_items(
                summary,
                source_ids,
                dry_run=dry_run,
                skip_transcription=skip_transcription,
                max_transcriptions=max_transcriptions,
                max_items=max_items,
                retry_operator_items=retry_operator_items,
            )
            summary.completed_at = _iso(self._now())
            summary.counts = self._counts(summary)
            if not dry_run:
                self._operations.save_run(summary)
        return summary

    def _run_sources(self, summary: CollectionRunSummary, source_ids: list[str], *, dry_run: bool) -> None:
        for source_id in source_ids:
            if dry_run:
                summary.sources.append(SourceResult(source_id=source_id, status="planned"))
                continue
            try:
                result = self._discover(source_id)
            except DiscoveryError as exc:
                summary.sources.append(SourceResult(source_id=source_id, status="operator_error", error=str(exc)))
                continue
            except Exception as exc:  # one source never aborts the whole run
                summary.sources.append(SourceResult(source_id=source_id, status="failed", error=str(exc)))
                continue
            summary.sources.append(
                SourceResult(
                    source_id=source_id,
                    status=result.status,
                    found=result.found,
                    new=result.new,
                    known=result.already_known,
                    error=result.error,
                )
            )

    def _run_items(
        self,
        summary: CollectionRunSummary,
        source_ids: list[str],
        *,
        dry_run: bool,
        skip_transcription: bool,
        max_transcriptions: int | None,
        max_items: int | None,
        retry_operator_items: bool,
    ) -> None:
        items = sorted(
            [item for source_id in source_ids for item in list_discovered_items(self._inbox_dir, source_id)],
            key=lambda item: (item.get("source_id", ""), item.get("published_date") or "", item["id"]),
        )
        if max_items is not None:
            items = items[: max(0, max_items)]
        transcription_attempts = 0
        for item in items:
            prior = self._operations.item_state(item["id"])
            retry_block = self._retry_block(prior, retry_operator_items=retry_operator_items)
            if retry_block:
                prior_class = prior.get("failure_class")
                exhausted = int(prior.get("retry_count", 0)) >= self._retry_limit
                summary.items.append(
                    ItemResult(
                        item_id=item["id"],
                        source_id=item["source_id"],
                        state="retry_deferred",
                        failure_class="operator" if prior_class == "operator" or exhausted else "retryable",
                        error=prior.get("last_error"),
                        next_action=retry_block,
                    )
                )
                continue
            cached = self._transcript_cache_ready(item)
            allow_transcription = not cached and not dry_run and not skip_transcription
            if not cached and max_transcriptions is not None and transcription_attempts >= max(0, max_transcriptions):
                allow_transcription = False
            if allow_transcription and not cached:
                transcription_attempts += 1
            try:
                result = self._orchestrate(item["id"], allow_transcription, False, dry_run)
            except Exception as exc:
                item_result = self._failure_result(item, "orchestration_error", str(exc))
                summary.items.append(item_result)
                self._persist_item_result(item_result, prior, dry_run=dry_run)
                continue
            item_result = self._from_orchestration(item, result)
            item_result.transcription_attempted = allow_transcription
            if result.state == "ready_for_extraction":
                atomic = self._atomic_review_state(
                    result.parent_resolution.evidence_id,
                    result.transcript_id,
                    result.transcript_sha256,
                )
                item_result.atomic_review = atomic
                prior_complete = prior.get("extraction_completed_transcript_sha256") == result.transcript_sha256
                if sum(atomic.values()) > 0:
                    item_result.state = "atomic_review_pending" if atomic.get("pending", 0) else "atomic_review_recorded"
                    item_result.next_action = "Review existing atomic Evidence outcomes; extraction will not be repeated."
                elif prior_complete:
                    item_result.state = "extraction_already_completed"
                    item_result.next_action = "Prior zero/complete extraction is recorded; no rerun needed."
                elif not self._gate.runnable:
                    item_result.state = (
                        "extraction_ready_but_disabled"
                        if not self._gate.enabled
                        else "extraction_ready_but_model_not_qualified"
                    )
                    item_result.next_action = self._gate.reason
                elif dry_run:
                    item_result.state = "extraction_would_run"
                    item_result.next_action = "Qualified extraction would run outside offline plan mode."
                else:
                    extraction_result = self._orchestrate(item["id"], False, True, False)
                    item_result = self._from_orchestration(item, extraction_result)
                    item_result.transcription_attempted = allow_transcription
                    if extraction_result.state == "extraction_complete":
                        item_result.proposals_created = len((extraction_result.extraction or {}).get("proposal_ids", []))
                        prior["extraction_completed_transcript_sha256"] = extraction_result.transcript_sha256
            summary.items.append(item_result)
            self._persist_item_result(item_result, prior, dry_run=dry_run)

    def _retry_block(self, prior: dict[str, Any], *, retry_operator_items: bool) -> str | None:
        if prior.get("failure_class") == "operator" and not retry_operator_items:
            return "operator intervention required; use --retry-operator-items after correcting the underlying state"
        if prior.get("failure_class") != "retryable":
            return None
        retry_count = int(prior.get("retry_count", 0))
        if retry_count >= self._retry_limit:
            return f"retry limit reached ({retry_count}); operator intervention required"
        next_raw = prior.get("next_eligible_retry_at")
        if not isinstance(next_raw, str):
            return None
        try:
            next_at = datetime.fromisoformat(next_raw)
            if next_at.tzinfo is None:
                next_at = next_at.replace(tzinfo=UTC)
        except ValueError:
            return None
        if self._now() < next_at.astimezone(UTC):
            return f"retry deferred until {next_raw}"
        return None

    def _from_orchestration(self, item: dict[str, Any], result: Any) -> ItemResult:
        error = "; ".join(result.errors) if result.errors else None
        failure_class = self._classify_failure(result.state, result.transcript_status, error)
        state = result.state
        if result.dry_run and result.parent_resolution.status == "would_create_draft":
            state = "would_create_publication_draft"
        return ItemResult(
            item_id=item["id"],
            source_id=item["source_id"],
            state=state,
            transcript_status=result.transcript_status,
            publication_draft_id=result.publication_draft_id,
            publication_draft_created=(
                not result.dry_run
                and result.parent_resolution.status == "pending_draft"
                and result.parent_resolution.message == "Publication draft created for review."
            ),
            parent_evidence_id=result.parent_resolution.evidence_id,
            failure_class=failure_class,
            error=error,
            next_action=result.next_action,
        )

    def _failure_result(self, item: dict[str, Any], state: str, error: str) -> ItemResult:
        return ItemResult(
            item_id=item["id"],
            source_id=item["source_id"],
            state=state,
            failure_class=self._classify_failure(state, "unknown", error) or "operator",
            error=error,
            next_action="Inspect the operational error before retrying.",
        )

    @staticmethod
    def _classify_failure(state: str, transcript_status: str, error: str | None) -> str | None:
        if state == "publication_rejected" or transcript_status == "malformed":
            return "operator"
        if not error:
            return None
        normalized = error.casefold()
        if any(marker in normalized for marker in TERMINAL_MARKERS):
            return "operator"
        if transcript_status == "acquisition_failed" or any(marker in normalized for marker in RETRYABLE_MARKERS):
            return "retryable"
        return "operator"

    def _persist_item_result(self, result: ItemResult, prior: dict[str, Any], *, dry_run: bool) -> None:
        if dry_run:
            return
        now = self._now()
        state = dict(prior)
        state.update(
            {
                "item_id": result.item_id,
                "source_id": result.source_id,
                "last_attempted_stage": result.state,
                "last_attempted_at": _iso(now),
                "failure_class": result.failure_class,
                "last_error": result.error,
            }
        )
        if result.failure_class == "retryable":
            retries = int(prior.get("retry_count", 0)) + 1
            state["retry_count"] = retries
            state["next_eligible_retry_at"] = _iso(now + self._retry_backoff * max(1, retries))
        elif result.failure_class == "operator":
            state["retry_count"] = int(prior.get("retry_count", 0))
            state["next_eligible_retry_at"] = None
        else:
            state["retry_count"] = 0
            state["next_eligible_retry_at"] = None
            state["last_success"] = result.state
            state["last_success_at"] = _iso(now)
        self._operations.save_item_state(result.item_id, state)

    def _atomic_review_state(
        self,
        parent_id: str | None,
        transcript_id: str | None,
        transcript_sha256: str | None,
    ) -> dict[str, int]:
        counts = {"pending": 0, "approved": 0, "rejected": 0}
        if not parent_id:
            return counts
        records = list(self._repos.evidence.list())
        inbox = self._inbox_dir / "evidence"
        if inbox.exists():
            for path in inbox.glob("*.json"):
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                if isinstance(payload, dict):
                    records.append(payload)
        for record in records:
            if record.get("evidence_role") != "atomic_evidence" or record.get("parent_evidence_id") != parent_id:
                continue
            provenance = record.get("transcript_provenance") or {}
            if transcript_id and provenance.get("transcript_id") != transcript_id:
                continue
            if transcript_sha256 and provenance.get("transcript_sha256") != transcript_sha256:
                continue
            if record.get("status") == "published" or record.get("review_state") == "published":
                counts["approved"] += 1
            elif record.get("status") == "rejected" or record.get("review_state") == "rejected":
                counts["rejected"] += 1
            else:
                counts["pending"] += 1
        return counts

    @staticmethod
    def _counts(summary: CollectionRunSummary) -> dict[str, int]:
        states = [item.state for item in summary.items]
        failures = [item.failure_class for item in summary.items]
        return {
            "sources_checked": len(summary.sources),
            "sources_succeeded": sum(result.status in {"ok", "planned"} for result in summary.sources),
            "sources_failed": sum(result.status not in {"ok", "planned"} for result in summary.sources),
            "items_discovered": sum(result.found for result in summary.sources),
            "items_new": sum(result.new for result in summary.sources),
            "items_known": sum(result.known for result in summary.sources),
            "items_processed": len(summary.items),
            "publication_drafts_created": sum(item.publication_draft_created for item in summary.items),
            "awaiting_publication_review": states.count("awaiting_publication_review"),
            "publication_rejected": states.count("publication_rejected"),
            "transcripts_ready": sum(item.transcript_status == "ready" for item in summary.items),
            "transcriptions_attempted": sum(item.transcription_attempted for item in summary.items),
            "ready_for_extraction": sum(state.startswith("extraction_ready") or state == "ready_for_extraction" for state in states),
            "extraction_skipped": sum(
                state in {
                    "extraction_ready_but_disabled",
                    "extraction_ready_but_model_not_qualified",
                    "atomic_review_pending",
                    "atomic_review_recorded",
                    "extraction_already_completed",
                }
                for state in states
            ),
            "atomic_reviews_waiting": sum((item.atomic_review or {}).get("pending", 0) for item in summary.items),
            "proposals_generated": sum(item.proposals_created for item in summary.items),
            "retryable_failures": failures.count("retryable"),
            "operator_action_items": failures.count("operator"),
        }
