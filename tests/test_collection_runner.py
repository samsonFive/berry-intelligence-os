"""Offline tests for the human-gated recurring collection coordinator."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from app import main
from app.services.ai_extraction import EXTRACTION_VERSION
from app.services.collection_runner import (
    CollectionLockedError,
    CollectionRunLock,
    CollectionRunner,
    ExtractionGate,
    OperationalStateStore,
    resolve_extraction_gate,
)
from app.services.media_discovery import DiscoveryRunResult
from app.services.media_orchestration import OrchestrationResult, ParentResolution
from app.services.media_orchestration import MediaOrchestrationService, MediaTranscriptionAdapter
from app.services.media_transcription import load_transcript_artifact, transcript_cache_matches_request
from app.services.model_qualification import (
    QUALIFICATION_MARKER_SCHEMA_VERSION,
    QUALIFICATION_WORKFLOW_VERSION,
    file_sha256,
)
from app.services.transcript_evidence import StructuredCandidateProvider, TranscriptEvidenceExtractionService


UTC = timezone.utc
NOW = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)


def _source(source_id: str, *, discoverable: bool = True) -> dict:
    record = {"id": source_id, "name": source_id}
    if discoverable:
        record["discovery"] = {"adapter": "podcast_rss", "feed_url": f"https://example.invalid/{source_id}.xml"}
    return record


def _item(item_id: str, source_id: str, *, title: str | None = None) -> dict:
    return {
        "id": item_id,
        "record_type": "discovered_media_item",
        "staging_schema_version": 1,
        "source_id": source_id,
        "title": title or item_id,
        "description": "Synthetic fixture only.",
        "media_format": "podcast",
        "canonical_url": f"https://example.invalid/{item_id}",
        "published_date": "2026-08-15",
        "dedupe_strategy": "guid",
        "dedupe_key": item_id,
        "first_seen_at": "2026-08-16T00:00:00+00:00",
        "last_seen_at": "2026-08-16T00:00:00+00:00",
        "seen_count": 1,
        "transcript_availability": {"status": "not_detected"},
        "raw_metadata": {},
    }


def _stage(inbox: Path, item: dict) -> None:
    folder = inbox / "discovered_media"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{item['id']}.json").write_text(json.dumps(item), encoding="utf-8")


def _repos(tmp_path: Path):
    repos = main.get_repositories(tmp_path / "data", main.SCHEMAS_DIR)
    repos.sources.create(_source("source-a"))
    repos.sources.create(_source("source-b"))
    repos.sources.create(_source("source-manual", discoverable=False))
    return repos


def _result(
    item_id: str,
    state: str,
    *,
    transcript_status: str = "ready",
    error: str | None = None,
    created: bool = False,
    dry_run: bool = False,
) -> OrchestrationResult:
    if state in {"ready_for_extraction", "extraction_complete"}:
        parent = ParentResolution(status="trusted", evidence_id="ev-parent", message="Existing trusted publication artifact resolved.")
    elif state == "publication_rejected":
        parent = ParentResolution(status="rejected_draft", draft_id="ev-draft", message="Publication draft was rejected; operator disposition is required.")
    elif dry_run:
        parent = ParentResolution(status="would_create_draft", draft_id="ev-draft", message="Publication draft would be created.")
    else:
        parent = ParentResolution(
            status="pending_draft",
            draft_id="ev-draft",
            message="Publication draft created for review." if created else "Publication draft is awaiting human review.",
        )
    return OrchestrationResult(
        item_id=item_id,
        state=state,
        parent_resolution=parent,
        transcript_status=transcript_status,
        publication_draft_id=parent.draft_id,
        transcript_id="transcript-fixture" if transcript_status == "ready" else None,
        transcript_sha256="a" * 64 if transcript_status == "ready" else None,
        extraction={"proposal_ids": ["ev-proposal-fixture"], "accepted": 1} if state == "extraction_complete" else None,
        next_action="Synthetic next action.",
        dry_run=dry_run,
        errors=[error] if error else [],
    )


class FakeOrchestrator:
    def __init__(self, states: dict[str, OrchestrationResult], inbox: Path | None = None) -> None:
        self.states = states
        self.inbox = inbox
        self.calls: list[tuple[str, bool, bool, bool]] = []

    def __call__(self, item_id: str, allow_transcription: bool, run_extraction: bool, dry_run: bool):
        self.calls.append((item_id, allow_transcription, run_extraction, dry_run))
        if run_extraction:
            if self.inbox:
                proposal = {
                    "id": "ev-proposal-fixture", "record_type": "evidence", "status": "draft",
                    "review_state": "in_review", "evidence_role": "atomic_evidence",
                    "parent_evidence_id": "ev-parent",
                }
                folder = self.inbox / "evidence"
                folder.mkdir(parents=True, exist_ok=True)
                (folder / "ev-proposal-fixture.json").write_text(json.dumps(proposal), encoding="utf-8")
            return _result(item_id, "extraction_complete")
        result = self.states[item_id]
        if dry_run:
            result.dry_run = True
        return result


def _runner(
    tmp_path: Path,
    repos,
    orchestrator: FakeOrchestrator,
    *,
    discover=None,
    gate: ExtractionGate = ExtractionGate(),
    cache_ready=None,
    now=lambda: NOW,
    retry_limit: int = 3,
    retry_backoff: timedelta = timedelta(minutes=30),
) -> CollectionRunner:
    inbox = tmp_path / "inbox"
    return CollectionRunner(
        repositories=repos,
        inbox_dir=inbox,
        operations=OperationalStateStore(inbox / "operations"),
        discover=discover or (lambda source_id: DiscoveryRunResult(source_id=source_id, status="ok")),
        orchestrate=orchestrator,
        transcript_cache_ready=cache_ready or (lambda item: False),
        extraction_gate=gate,
        now=now,
        run_id_factory=lambda instant: "collection-fixture",
        retry_limit=retry_limit,
        retry_backoff=retry_backoff,
    )


def test_all_sources_iterate_generically_and_failure_isolated(tmp_path: Path) -> None:
    repos = _repos(tmp_path)
    inbox = tmp_path / "inbox"
    _stage(inbox, _item("item-a", "source-a"))
    _stage(inbox, _item("item-b", "source-b"))
    calls = []

    def discover(source_id: str):
        calls.append(source_id)
        if source_id == "source-b":
            return DiscoveryRunResult(source_id=source_id, status="error", error="temporary feed timeout")
        return DiscoveryRunResult(source_id=source_id, status="ok", found=1, already_known=1)

    orchestrator = FakeOrchestrator({
        "item-a": _result("item-a", "awaiting_publication_review"),
        "item-b": _result("item-b", "awaiting_publication_review"),
    })
    summary = _runner(tmp_path, repos, orchestrator, discover=discover).run()
    assert calls == ["source-a", "source-b"]
    assert {item.item_id for item in summary.items} == {"item-a", "item-b"}
    assert summary.counts["sources_succeeded"] == 1 and summary.counts["sources_failed"] == 1
    assert "source-manual" not in calls
    persisted = json.loads((inbox / "operations" / "runs" / "collection-fixture.json").read_text())
    assert persisted["counts"] == summary.counts


def test_registered_source_group_runs_only_selected_eligible_sources(tmp_path: Path) -> None:
    repos = _repos(tmp_path)
    calls: list[str] = []
    orchestrator = FakeOrchestrator({})
    summary = _runner(
        tmp_path,
        repos,
        orchestrator,
        discover=lambda source_id: calls.append(source_id) or DiscoveryRunResult(source_id=source_id, status="ok"),
    ).run(source_ids=["source-b"])
    assert calls == ["source-b"]
    assert summary.source_scope == "group"
    assert summary.counts["sources_checked"] == 1


def test_one_source_selection_and_discovery_rerun_are_idempotent(tmp_path: Path) -> None:
    repos = _repos(tmp_path)
    inbox = tmp_path / "inbox"
    discovery_calls = 0

    def discover(source_id: str):
        nonlocal discovery_calls
        discovery_calls += 1
        item = _item("stable-item", source_id)
        path = inbox / "discovered_media" / "stable-item.json"
        is_new = not path.exists()
        _stage(inbox, item)
        return DiscoveryRunResult(
            source_id=source_id,
            status="ok",
            found=1,
            new=int(is_new),
            already_known=int(not is_new),
            items=[item],
        )

    orchestrator = FakeOrchestrator({"stable-item": _result("stable-item", "awaiting_publication_review")})
    runner = _runner(tmp_path, repos, orchestrator, discover=discover)
    first = runner.run(source_id="source-a")
    second = runner.run(source_id="source-a")
    assert discovery_calls == 2
    assert first.counts["items_new"] == 1 and second.counts["items_new"] == 0
    assert len(list((inbox / "discovered_media").glob("*.json"))) == 1
    assert all(call[0] == "stable-item" for call in orchestrator.calls)


def test_offline_dry_run_has_no_network_or_writes_and_honors_max_items(tmp_path: Path) -> None:
    repos = _repos(tmp_path)
    inbox = tmp_path / "inbox"
    _stage(inbox, _item("item-a", "source-a"))
    _stage(inbox, _item("item-b", "source-a"))
    discover_calls = []
    orchestrator = FakeOrchestrator({
        "item-a": _result("item-a", "discovered", transcript_status="missing", dry_run=True),
        "item-b": _result("item-b", "discovered", transcript_status="missing", dry_run=True),
    })
    runner = _runner(
        tmp_path,
        repos,
        orchestrator,
        discover=lambda source_id: discover_calls.append(source_id),
    )
    summary = runner.run(source_id="source-a", dry_run=True, max_items=1)
    assert discover_calls == []
    assert summary.items[0].state == "would_create_publication_draft"
    assert orchestrator.calls == [("item-a", False, False, True)]
    assert not (inbox / "operations").exists()


def test_transcription_cache_skip_and_resource_limits(tmp_path: Path) -> None:
    repos = _repos(tmp_path)
    inbox = tmp_path / "inbox"
    for item_id in ("cached", "new-a", "new-b"):
        _stage(inbox, _item(item_id, "source-a"))
    states = {item_id: _result(item_id, "awaiting_publication_review") for item_id in ("cached", "new-a", "new-b")}
    orchestrator = FakeOrchestrator(states)
    runner = _runner(tmp_path, repos, orchestrator, cache_ready=lambda item: item["id"] == "cached")
    runner.run(source_id="source-a", max_transcriptions=1)
    by_id = {item_id: allow for item_id, allow, _extract, _dry in orchestrator.calls}
    assert by_id == {"cached": False, "new-a": True, "new-b": False}

    orchestrator.calls.clear()
    _runner(tmp_path, repos, orchestrator).run(source_id="source-a", skip_transcription=True)
    assert all(not allow for _item_id, allow, _extract, _dry in orchestrator.calls)


def test_publication_gate_states_and_later_approved_run_resumes(tmp_path: Path) -> None:
    repos = _repos(tmp_path)
    inbox = tmp_path / "inbox"
    _stage(inbox, _item("item-a", "source-a"))
    current = {"result": _result("item-a", "awaiting_publication_review", created=True)}

    class MutableOrchestrator(FakeOrchestrator):
        def __call__(self, item_id, allow_transcription, run_extraction, dry_run):
            self.calls.append((item_id, allow_transcription, run_extraction, dry_run))
            return current["result"]

    orchestrator = MutableOrchestrator({})
    runner = _runner(tmp_path, repos, orchestrator)
    pending = runner.run(source_id="source-a")
    assert pending.items[0].state == "awaiting_publication_review"
    assert pending.counts["publication_drafts_created"] == 1
    assert not any(call[2] for call in orchestrator.calls)

    current["result"] = _result("item-a", "ready_for_extraction")
    resumed = runner.run(source_id="source-a")
    assert resumed.items[0].state == "extraction_ready_but_disabled"
    assert resumed.items[0].parent_evidence_id == "ev-parent"


def test_rejected_publication_is_not_recreated_or_retried_by_default(tmp_path: Path) -> None:
    repos = _repos(tmp_path)
    inbox = tmp_path / "inbox"
    _stage(inbox, _item("item-a", "source-a"))
    orchestrator = FakeOrchestrator({"item-a": _result("item-a", "publication_rejected")})
    runner = _runner(tmp_path, repos, orchestrator)
    first = runner.run(source_id="source-a")
    second = runner.run(source_id="source-a")
    assert first.items[0].state == "publication_rejected"
    assert second.items[0].state == "retry_deferred"
    assert len(orchestrator.calls) == 1


def test_extraction_gate_requires_enablement_configuration_and_exact_qualification(tmp_path: Path) -> None:
    fingerprint = "f" * 64
    disabled = resolve_extraction_gate(
        enabled=False, provider="openai-compatible", model="model-a", base_url="http://local",
        prompt_version="atomic-ci-v1", qualification_path=None,
    )
    assert not disabled.runnable and "disabled by default" in disabled.reason
    unconfigured = resolve_extraction_gate(
        enabled=True, provider="openai-compatible", model=None, base_url=None,
        prompt_version="atomic-ci-v1", qualification_path=None,
    )
    assert not unconfigured.configured
    missing_qualification = resolve_extraction_gate(
        enabled=True, provider="openai-compatible", model="model-a", base_url="http://local",
        prompt_version="atomic-ci-v1", qualification_path=None,
    )
    assert missing_qualification.configured and not missing_qualification.qualified

    evaluation = tmp_path / "evaluation.json"
    evaluation.write_text(json.dumps({
        "run_id": "evaluation-fixture", "provider": "openai-compatible", "model": "model-a",
        "prompt_version": "atomic-ci-v1", "extraction_version": EXTRACTION_VERSION,
        "configuration_fingerprint": fingerprint, "complete": True,
        "benchmark_identity": {"id": "fixture", "version": 1, "sha256": "b" * 64},
        "gold_set_identity": {"id": "gold-fixture", "version": 1, "sha256": "g" * 64},
        "atomic_gold_set": {"passed": True},
    }))
    marker = tmp_path / "qualification.json"
    marker.write_text(json.dumps({
        "qualification_marker_schema_version": QUALIFICATION_MARKER_SCHEMA_VERSION,
        "workflow_version": QUALIFICATION_WORKFLOW_VERSION,
        "provider": "openai-compatible", "model": "model-a", "prompt_version": "atomic-ci-v1",
        "extraction_version": EXTRACTION_VERSION,
        "operator_qualified": True, "qualified_by": "fixture-operator", "qualified_at": "2026-08-16",
        "configuration_fingerprint": fingerprint, "evaluation_run_id": "evaluation-fixture",
        "evaluation_artifact": "evaluation.json", "evaluation_sha256": file_sha256(evaluation),
        "benchmark_id": "fixture", "benchmark_version": 1, "benchmark_sha256": "b" * 64,
        "gold_set_id": "gold-fixture", "gold_set_version": 1, "gold_set_sha256": "g" * 64,
    }))
    qualified = resolve_extraction_gate(
        enabled=True, provider="openai-compatible", model="model-a", base_url="http://local",
        prompt_version="atomic-ci-v1", qualification_path=marker, configuration_fingerprint=fingerprint,
        benchmark_sha256="b" * 64, gold_set_sha256="g" * 64,
    )
    assert qualified.runnable
    mismatch = resolve_extraction_gate(
        enabled=True, provider="openai-compatible", model="model-b", base_url="http://local",
        prompt_version="atomic-ci-v1", qualification_path=marker, configuration_fingerprint=fingerprint,
        benchmark_sha256="b" * 64, gold_set_sha256="g" * 64,
    )
    assert not mismatch.runnable and "does not match" in mismatch.reason


def test_qualified_extraction_uses_existing_boundary_and_leaves_untrusted_proposal(tmp_path: Path) -> None:
    repos = _repos(tmp_path)
    inbox = tmp_path / "inbox"
    _stage(inbox, _item("item-a", "source-a"))
    gate = ExtractionGate(
        enabled=True, configured=True, qualified=True, provider="openai-compatible",
        model="model-a", prompt_version="atomic-ci-v1", reason="qualified",
    )
    orchestrator = FakeOrchestrator({"item-a": _result("item-a", "ready_for_extraction")}, inbox=inbox)
    summary = _runner(tmp_path, repos, orchestrator, gate=gate).run(source_id="source-a")
    assert [call[2] for call in orchestrator.calls] == [False, True]
    assert summary.items[0].state == "extraction_complete"
    assert summary.counts["proposals_generated"] == 1
    proposal = json.loads((inbox / "evidence" / "ev-proposal-fixture.json").read_text())
    assert proposal["status"] == "draft" and proposal["review_state"] == "in_review"
    assert repos.facts.list() == []
    assert repos.relationships.list() == []
    assert repos.assessments.list() == []
    assert repos.recommendations.list() == []


def test_existing_atomic_review_state_prevents_extraction_regeneration(tmp_path: Path) -> None:
    repos = _repos(tmp_path)
    inbox = tmp_path / "inbox"
    _stage(inbox, _item("item-a", "source-a"))
    folder = inbox / "evidence"
    folder.mkdir(parents=True)
    proposal = {
        "id": "ev-existing-proposal", "record_type": "evidence", "status": "draft",
        "review_state": "in_review", "evidence_role": "atomic_evidence",
        "parent_evidence_id": "ev-parent",
        "transcript_provenance": {"transcript_id": "transcript-fixture", "transcript_sha256": "a" * 64},
    }
    (folder / "ev-existing-proposal.json").write_text(json.dumps(proposal))
    gate = ExtractionGate(enabled=True, configured=True, qualified=True, reason="qualified")
    orchestrator = FakeOrchestrator({"item-a": _result("item-a", "ready_for_extraction")})
    summary = _runner(tmp_path, repos, orchestrator, gate=gate).run(source_id="source-a")
    assert summary.items[0].state == "atomic_review_pending"
    assert summary.items[0].atomic_review["pending"] == 1
    assert not any(call[2] for call in orchestrator.calls)


def test_retryable_failure_backoff_and_limit_are_persisted(tmp_path: Path) -> None:
    repos = _repos(tmp_path)
    inbox = tmp_path / "inbox"
    _stage(inbox, _item("item-a", "source-a"))
    clock = {"now": NOW}
    orchestrator = FakeOrchestrator({
        "item-a": _result("item-a", "publication_approved", transcript_status="acquisition_failed", error="network timeout"),
    })
    runner = _runner(
        tmp_path, repos, orchestrator, now=lambda: clock["now"], retry_limit=2, retry_backoff=timedelta(minutes=10)
    )
    first = runner.run(source_id="source-a")
    deferred = runner.run(source_id="source-a")
    assert first.items[0].failure_class == "retryable"
    assert deferred.items[0].state == "retry_deferred" and len(orchestrator.calls) == 1
    clock["now"] += timedelta(minutes=11)
    runner.run(source_id="source-a")
    clock["now"] += timedelta(minutes=21)
    limited = runner.run(source_id="source-a")
    assert limited.items[0].state == "retry_deferred"
    state = json.loads((inbox / "operations" / "items" / "item-a.json").read_text())
    assert state["retry_count"] == 2


def test_lock_prevents_overlap_and_recovers_stale_lock(tmp_path: Path) -> None:
    lock_path = tmp_path / "operations" / "collection.lock"
    with CollectionRunLock(lock_path, run_id="run-a", now=lambda: NOW):
        with pytest.raises(CollectionLockedError, match="run-a"):
            with CollectionRunLock(lock_path, run_id="run-b", now=lambda: NOW):
                pass
    stale = {"run_id": "stale-run", "started_at": (NOW - timedelta(hours=7)).isoformat(), "pid": 1}
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(json.dumps(stale))
    with CollectionRunLock(
        lock_path, run_id="run-c", now=lambda: NOW, stale_after=timedelta(hours=6)
    ) as lock:
        assert lock.recovered_stale_lock
        assert json.loads(lock_path.read_text())["run_id"] == "run-c"
    assert not lock_path.exists()


def test_real_orchestration_reuses_cached_transcript_binds_parent_and_extracts_idempotently(
    tmp_path: Path,
) -> None:
    repos = main.get_repositories(tmp_path / "data", main.SCHEMAS_DIR)
    repos.sources.create(_source("source-a"))
    parent = {
        "id": "ev-parent", "record_type": "evidence", "status": "published",
        "review_state": "published", "source_type": "industry_podcast",
        "title": "Synthetic approved publication", "source_name": "source-a",
        "source_url": "https://example.invalid/item-a", "source_id": "source-a",
        "published_date": "2026-08-15", "captured_date": "2026-08-16",
        "summary": "Synthetic fixture.", "submitted_by": "human-reviewer",
        "evidence_role": "publication_artifact", "media_format": "podcast",
        "priority": {
            dimension: {"level": "none", "rationale": ""}
            for dimension in ("reading", "testing", "commercial_position", "monitoring")
        },
    }
    repos.evidence.create(parent)
    inbox = tmp_path / "inbox"
    item = _item("item-a", "source-a")
    item["possible_evidence_matches"] = [{"evidence_id": "ev-parent", "reasons": ["title_match"]}]
    _stage(inbox, item)
    transcript = {
        "item_id": "item-a", "transcript_id": "transcript-cached", "language": "en",
        "provenance": {"method": "auto_generated", "created_by": "fixture-whisper", "created_at": "2026-08-16"},
        "segments": [{"text": "The speaker may expand a synthetic trial.", "start_seconds": 10, "end_seconds": 20}],
        "acquisition": {
            "tier": "tier_3_local_speech_to_text", "model": "small", "language_requested": None,
            "source_fingerprint": {"kind": "canonical_url", "value": item["canonical_url"]},
        },
    }
    transcript_folder = inbox / "discovered_media" / "_normalized_transcripts"
    transcript_folder.mkdir(parents=True)
    (transcript_folder / "item-a.json").write_text(json.dumps(transcript))
    validator = main.get_validator("evidence.schema.json")
    extraction = TranscriptEvidenceExtractionService(
        repositories=repos,
        inbox_dir=inbox,
        evidence_errors=lambda record: [error.message for error in validator.iter_errors(record)],
        provider=StructuredCandidateProvider(
            [{"normalized_statement": "Speaker says a synthetic trial may expand.", "segment_indexes": [0], "entity_ids": [], "geography_ids": [], "berry_ids": []}],
            name="fixture-qualified-provider",
        ),
    )
    orchestration_calls = []

    def orchestrate(item_id: str, allow_transcription: bool, run_extraction: bool, dry_run: bool):
        orchestration_calls.append((allow_transcription, run_extraction))
        service = MediaOrchestrationService(
            repositories=repos,
            inbox_dir=inbox,
            evidence_errors=lambda record: [error.message for error in validator.iter_errors(record)],
            transcript_adapter=MediaTranscriptionAdapter(inbox, model="small", transcribe_missing=allow_transcription),
            extraction_service=extraction if run_extraction else None,
        )
        return service.process(item_id, dry_run=dry_run)

    gate = ExtractionGate(enabled=True, configured=True, qualified=True, reason="qualified")
    runner = CollectionRunner(
        repositories=repos,
        inbox_dir=inbox,
        operations=OperationalStateStore(inbox / "operations"),
        discover=lambda source_id: DiscoveryRunResult(source_id=source_id, status="ok", already_known=1),
        orchestrate=orchestrate,
        transcript_cache_ready=lambda current: bool(
            (payload := load_transcript_artifact(inbox, current["id"]))
            and transcript_cache_matches_request(inbox, payload, current, model="small", language=None)
        ),
        extraction_gate=gate,
        now=lambda: NOW,
        run_id_factory=lambda instant: "real-orchestration-fixture",
    )
    first = runner.run(source_id="source-a")
    assert orchestration_calls == [(False, False), (False, True)]
    assert first.items[0].state == "extraction_complete"
    assert first.items[0].transcription_attempted is False
    proposal_files = list((inbox / "evidence").glob("ev-proposal-atomic-*.json"))
    assert len(proposal_files) == 1
    proposal = json.loads(proposal_files[0].read_text())
    assert proposal["status"] == "draft" and proposal["review_state"] == "in_review"
    assert proposal["parent_evidence_id"] == "ev-parent"
    assert proposal["transcript_provenance"]["transcript_id"] == "transcript-cached"

    orchestration_calls.clear()
    second = runner.run(source_id="source-a")
    assert orchestration_calls == [(False, False)]
    assert second.items[0].state == "atomic_review_pending"
    assert len(list((inbox / "evidence").glob("ev-proposal-atomic-*.json"))) == 1
    assert repos.facts.list() == [] and repos.assessments.list() == [] and repos.recommendations.list() == []


def test_real_runner_creates_publication_draft_once_and_waits_for_human_review(tmp_path: Path) -> None:
    repos = main.get_repositories(tmp_path / "data", main.SCHEMAS_DIR)
    repos.sources.create(_source("source-a"))
    inbox = tmp_path / "inbox"
    _stage(inbox, _item("item-new", "source-a"))
    validator = main.get_validator("evidence.schema.json")

    def orchestrate(item_id: str, allow_transcription: bool, run_extraction: bool, dry_run: bool):
        assert run_extraction is False
        service = MediaOrchestrationService(
            repositories=repos,
            inbox_dir=inbox,
            evidence_errors=lambda record: [error.message for error in validator.iter_errors(record)],
            transcript_adapter=MediaTranscriptionAdapter(inbox, transcribe_missing=allow_transcription),
        )
        return service.process(item_id, dry_run=dry_run)

    runner = CollectionRunner(
        repositories=repos,
        inbox_dir=inbox,
        operations=OperationalStateStore(inbox / "operations"),
        discover=lambda source_id: DiscoveryRunResult(source_id=source_id, status="ok", already_known=1),
        orchestrate=orchestrate,
        transcript_cache_ready=lambda item: False,
        now=lambda: NOW,
        run_id_factory=lambda instant: "publication-draft-fixture",
    )
    first = runner.run(source_id="source-a", max_transcriptions=0)
    second = runner.run(source_id="source-a", max_transcriptions=0)
    draft_files = list((inbox / "evidence").glob("ev-media-*.json"))
    assert first.items[0].state == second.items[0].state == "awaiting_publication_review"
    assert first.counts["publication_drafts_created"] == 1
    assert second.counts["publication_drafts_created"] == 0
    assert len(draft_files) == 1
    draft = json.loads(draft_files[0].read_text())
    assert draft["status"] == "draft" and draft["review_state"] == "in_review"


# ---------------------------------------------------------------------------
# Continuous Intelligence Refresh (2026-08-18): post-run queue hygiene
# reporting -- direct-vs-adjacent review-ready counts, irrelevant-rejected,
# historical-backlog discovered/suppressed, transcript-needed. Requirement:
# a scheduled run's report must show what's genuinely new, not just a
# re-walk of the whole backlog.
# ---------------------------------------------------------------------------


def test_counts_report_direct_and_adjacent_review_ready_separately(tmp_path: Path) -> None:
    repos = _repos(tmp_path)
    inbox = tmp_path / "inbox"
    _stage(inbox, _item("item-direct", "source-a"))
    _stage(inbox, _item("item-adjacent", "source-a"))
    _stage(inbox, _item("item-no-tier", "source-a"))

    direct = _result("item-direct", "awaiting_publication_review", created=True)
    direct.relevance_tier = "direct"
    adjacent = _result("item-adjacent", "awaiting_publication_review", created=True)
    adjacent.relevance_tier = "adjacent"
    no_tier = _result("item-no-tier", "awaiting_publication_review", created=True)

    orchestrator = FakeOrchestrator({"item-direct": direct, "item-adjacent": adjacent, "item-no-tier": no_tier})
    summary = _runner(tmp_path, repos, orchestrator).run(source_id="source-a")
    assert summary.counts["direct_review_ready"] == 1
    assert summary.counts["adjacent_review_ready"] == 1
    item_by_id = {item.item_id: item for item in summary.items}
    assert item_by_id["item-direct"].relevance_tier == "direct"
    assert item_by_id["item-adjacent"].relevance_tier == "adjacent"
    assert item_by_id["item-no-tier"].relevance_tier is None


def test_counts_report_irrelevant_rejected_and_transcript_needed(tmp_path: Path) -> None:
    repos = _repos(tmp_path)
    inbox = tmp_path / "inbox"
    _stage(inbox, _item("item-irrelevant", "source-a"))
    _stage(inbox, _item("item-needs-transcript", "source-a"))

    irrelevant = _result("item-irrelevant", "skipped_irrelevant", transcript_status="deferred")
    needs_transcript = _result("item-needs-transcript", "awaiting_publication_review", transcript_status="missing")
    orchestrator = FakeOrchestrator({"item-irrelevant": irrelevant, "item-needs-transcript": needs_transcript})
    summary = _runner(tmp_path, repos, orchestrator).run(source_id="source-a")
    assert summary.counts["irrelevant_rejected"] == 1
    assert summary.counts["transcript_needed"] == 1


def test_counts_report_historical_backlog_discovered_and_suppressed(tmp_path: Path) -> None:
    """Mirrors run_collection.py's orchestrate(): a discovery pass that
    flagged spoken-media backlog reports it at the source level
    (historical_backlog_discovered), and an item whose orchestration was
    skipped as backlog reports it at the item level
    (historical_backlog_suppressed) -- distinct from a normal
    awaiting_publication_review outcome."""
    repos = _repos(tmp_path)
    inbox = tmp_path / "inbox"
    backlog_item = _item("item-backlog", "source-a")
    backlog_item["historical_backlog"] = True
    _stage(inbox, backlog_item)
    _stage(inbox, _item("item-current", "source-a"))

    def discover(source_id: str) -> DiscoveryRunResult:
        return DiscoveryRunResult(source_id=source_id, status="ok", found=5, new=5, historical_backlog=2)

    suppressed = OrchestrationResult(
        item_id="item-backlog",
        state="historical_backlog_suppressed",
        parent_resolution=ParentResolution(status="skipped", message="Historical backlog item."),
        transcript_status="deferred",
        next_action="No action; outside the source's bounded initial-discovery window.",
    )
    current = _result("item-current", "awaiting_publication_review", created=True)
    orchestrator = FakeOrchestrator({"item-backlog": suppressed, "item-current": current})
    summary = _runner(tmp_path, repos, orchestrator, discover=discover).run(source_id="source-a")
    assert summary.counts["historical_backlog_discovered"] == 2
    assert summary.counts["historical_backlog_suppressed"] == 1
    item_by_id = {item.item_id: item for item in summary.items}
    assert item_by_id["item-backlog"].historical_backlog is True
    assert item_by_id["item-current"].historical_backlog is False
