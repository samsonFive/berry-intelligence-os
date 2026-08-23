"""Offline tests for the read-only collection operations status model."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from app import main
from app.services import media_discovery, media_transcription
from app.services.ai_extraction import (
    EXTRACTION_VERSION,
    PROMPT_VERSION,
    OpenAICompatibleExtractionConfig,
    OpenAICompatibleExtractionProvider,
)
from app.services.collection_runner import ExtractionGate, OperationalStateStore
from app.services.collection_status import CollectionStatusService
from app.services.extraction_evaluation import public_configuration
from app.services.media_orchestration import publication_draft_id
from app.services.model_qualification import (
    QUALIFICATION_ARTIFACT_SCHEMA_VERSION,
    QUALIFICATION_WORKFLOW_VERSION,
    approve_qualification,
    file_sha256,
    qualification_configuration_fingerprint,
    safe_endpoint_identity,
)
from app.services.transcript_evidence import TranscriptArtifact
from scripts import collection_status as status_cli


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc)
SOURCE_A = "source-status-a"
SOURCE_B = "source-status-b"


def _source(source_id: str, *, discoverable: bool = True) -> dict:
    record = {"id": source_id, "name": f"Status {source_id}"}
    if discoverable:
        record["discovery"] = {"adapter": "podcast_rss", "feed_url": f"https://example.invalid/{source_id}.xml"}
    return record


def _item(item_id: str, source_id: str = SOURCE_A) -> dict:
    return {
        "id": item_id,
        "record_type": "discovered_media_item",
        "staging_schema_version": 1,
        "source_id": source_id,
        "title": f"Status item {item_id}",
        "description": "Synthetic status fixture.",
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


def _stage(inbox: Path, item: dict) -> Path:
    folder = inbox / "discovered_media"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{item['id']}.json"
    path.write_text(json.dumps(item), encoding="utf-8")
    return path


def _draft(inbox: Path, item: dict, *, rejected: bool = False) -> dict:
    record = {
        "id": publication_draft_id(item),
        "record_type": "evidence",
        "status": "rejected" if rejected else "draft",
        "review_state": "rejected" if rejected else "in_review",
        "evidence_role": "publication_artifact",
        "discovered_item_id": item["id"],
        "source_id": item["source_id"],
        "title": item["title"],
    }
    folder = inbox / "evidence"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{record['id']}.json").write_text(json.dumps(record), encoding="utf-8")
    return record


def _parent(item: dict, *, parent_id: str = "ev-status-parent") -> dict:
    priority = {
        key: {"level": "none", "rationale": "Synthetic status fixture."}
        for key in ("reading", "testing", "commercial_position", "monitoring")
    }
    return {
        "id": parent_id,
        "record_type": "evidence",
        "status": "published",
        "review_state": "published",
        "evidence_role": "publication_artifact",
        "source_type": "industry_podcast",
        "source_id": item["source_id"],
        "title": item["title"],
        "source_name": "Status Publisher",
        "source_url": item["canonical_url"],
        "captured_date": "2026-08-16",
        "summary": "Human-reviewed fixture.",
        "submitted_by": "fixture",
        "priority": priority,
    }


def _trust_parent(repos, item: dict, *, parent_id: str = "ev-status-parent") -> dict:
    parent = _parent(item, parent_id=parent_id)
    repos.evidence.create(parent)
    item["possible_evidence_matches"] = [{"evidence_id": parent_id, "reasons": ["fixture"]}]
    return parent


def _transcript(inbox: Path, item: dict, *, parent_id: str | None = None, transcript_id: str = "transcript-status") -> dict:
    payload = {
        "item_id": item["id"],
        "transcript_id": transcript_id,
        "language": "en",
        "provenance": {"method": "auto_generated", "created_by": "fixture-whisper", "created_at": "2026-08-16"},
        "segments": [{"text": "The speaker may expand a synthetic trial.", "start_seconds": 10, "end_seconds": 20}],
        "acquisition": {
            "tier": "tier_3_local_speech_to_text",
            "model": "small",
            "language_requested": None,
            "source_fingerprint": {"kind": "canonical_url", "value": item["canonical_url"]},
        },
    }
    if parent_id:
        payload["parent_evidence_id"] = parent_id
    folder = inbox / "discovered_media" / "_normalized_transcripts"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{item['id']}.json").write_text(json.dumps(payload), encoding="utf-8")
    return payload


def _atomic(inbox: Path, parent_id: str, *, state: str, transcript_id: str = "transcript-status") -> dict:
    record = {
        "id": f"ev-atomic-{state}",
        "record_type": "evidence",
        "status": "rejected" if state == "rejected" else "draft",
        "review_state": "rejected" if state == "rejected" else "in_review",
        "evidence_role": "atomic_evidence",
        "parent_evidence_id": parent_id,
        "title": "Synthetic atomic proposal",
        "summary": "Speaker may expand a synthetic trial.",
        "transcript_provenance": {"transcript_id": transcript_id, "transcript_sha256": "fixture"},
    }
    folder = inbox / "evidence"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{record['id']}.json").write_text(json.dumps(record), encoding="utf-8")
    return record


def _operation(inbox: Path, item: dict, **values) -> Path:
    payload = {"item_id": item["id"], "source_id": item["source_id"], **values}
    folder = inbox / "operations" / "items"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{item['id']}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _setup(tmp_path: Path):
    repos = main.get_repositories(tmp_path / "data", main.SCHEMAS_DIR)
    repos.sources.create(_source(SOURCE_A))
    repos.sources.create(_source(SOURCE_B))
    repos.sources.create(_source("source-manual", discoverable=False))
    return repos, tmp_path / "inbox"


def _service(tmp_path: Path, repos, inbox: Path, *, gate=None, blockers=None, now=lambda: NOW):
    return CollectionStatusService(
        repositories=repos,
        inbox_dir=inbox,
        operations=OperationalStateStore(inbox / "operations"),
        evidence_errors=lambda _record: [],
        extraction_gate=gate or ExtractionGate(reason="extraction disabled"),
        extraction_blockers=blockers if blockers is not None else ["extraction is disabled", "no qualification marker is configured"],
        now=now,
        retry_limit=3,
        lock_stale_after=timedelta(hours=6),
    )


def _one(report):
    assert len(report.items) == 1
    return report.items[0]


def test_empty_runtime_reports_configured_sources_and_separate_pilot_readiness(tmp_path):
    repos, inbox = _setup(tmp_path)
    report = _service(tmp_path, repos, inbox).build()
    assert report.sources_configured == 3 and report.sources_discoverable == 2
    assert report.counts["ready_to_advance"] == 0
    assert report.pilot_readiness["collection_only"]["state"] == "READY"
    assert report.pilot_readiness["extraction_enabled"]["state"] == "BLOCKED"
    assert report.recommended_next_action == "run collection"
    assert {source.source_id for source in report.sources} == {SOURCE_A, SOURCE_B}


def test_live_source_repository_includes_all_onboarded_sources_generically(tmp_path):
    repos = main.get_repositories(ROOT / "data", main.SCHEMAS_DIR)
    report = _service(tmp_path, repos, tmp_path / "inbox").build()
    expected = {
        "source-the-packer-podcast", "source-fresh-takes-on-tech-podcast", "source-produce-buzzers-podcast",
        "source-global-fresh-series-podcast", "source-fresh-cred-podcast", "source-lubera-edibles-podcast",
        "source-blueberries-tv-youtube",
    }
    # 53 = 50 plus 3 new discoverable sources added for the Blackberry/
    # Raspberry Vertical V1 mission (2026-08-22): source-news-search-
    # caneberry-global, source-news-search-mexico-zarzamora, and
    # source-news-search-chile-frambuesa, all with real news_search_rss
    # discovery.adapter blocks. 174 = 171 plus those same 3 sources.
    # 50 = 47 plus 3 new discoverable sources added for the Unknown-Event
    # Discovery + Query Coverage V3 mission (2026-08-23): FreshPlaza and
    # Fruitnet global article_rss feeds, and a new sec_edgar_search_json
    # adapter (SEC EDGAR full-text search, CIK-scoped to Mission Produce),
    # all with real discovery.adapter blocks. 171 = 168 plus those same 3
    # sources.
    # 47 = 43 plus 4 new discoverable sources added for the Global
    # Qualitative Coverage Expansion V2 mission (2026-08-22): the UK Food
    # Standards Agency's food-alerts API (a new government_alert_json
    # adapter type, also discoverable) and 3 Google News news_search_rss
    # searches, all with real discovery.adapter blocks. 168 = 164 plus
    # those same 4 sources.
    # 43 = 29 plus 14 new discoverable sources added for the Global
    # Qualitative Coverage Expansion V1 mission (2026-08-21): 13 Google
    # News news_search_rss searches (geography/language/topic/retailer-
    # scoped, all with real discovery.adapter blocks) and 1 openFDA
    # government_recall_json source (a new adapter type, also
    # discoverable). 164 = 150 plus those same 14 sources.
    # 150 = 149 plus source-nasa-power-daily-point, added for the Weather /
    # Climate Context V1 mission (2026-08-21) -- no discovery.adapter, runs
    # via scripts/monitor_weather_intelligence.py instead, so it never
    # counted toward sources_discoverable. 149 = 148 plus
    # source-un-comtrade-public-preview, added for the Global Trade /
    # Customs Intelligence V1 mission (2026-08-21). 148 = 147 plus
    # source-cpvo-public-register, added for the Variety Intelligence
    # Backbone V1 mission (2026-08-21). 147 = 142 plus 5 sources added for
    # the Mainstream News + Regulatory Coverage Recall Benchmark V1 mission
    # (2026-08-21): 2 Federal Register government_register_json sources
    # and 3 Google News news_search_rss sources, all with real
    # discovery.adapter blocks, proven against real network traffic.
    assert report.sources_configured == 174 and report.sources_discoverable == 53
    assert expected <= {source.source_id for source in report.sources}


def test_ready_to_advance_and_source_filter(tmp_path):
    repos, inbox = _setup(tmp_path)
    _stage(inbox, _item("item-ready"))
    report = _service(tmp_path, repos, inbox).build(source_id=SOURCE_A)
    item = _one(report)
    assert item.category == "ready_to_advance" and item.recommended_action == "run collection"
    assert len(report.sources) == 1 and report.sources[0].discovered_items == 1


def test_publication_review_wait_has_human_gate_precedence(tmp_path):
    repos, inbox = _setup(tmp_path)
    item = _item("item-review")
    _stage(inbox, item)
    _draft(inbox, item)
    report = _service(tmp_path, repos, inbox).build()
    assert _one(report).category == "human_publication_review_required"
    assert report.recommended_next_action == "review publication"


def test_rejected_publication_is_completed_no_action(tmp_path):
    repos, inbox = _setup(tmp_path)
    item = _item("item-rejected")
    _stage(inbox, item)
    _draft(inbox, item, rejected=True)
    assert _one(_service(tmp_path, repos, inbox).build()).category == "completed_no_action"


@pytest.mark.parametrize(
    "gate,blockers,expected_reason",
    [
        (ExtractionGate(reason="extraction disabled"), ["extraction is disabled"], "disabled"),
        (ExtractionGate(enabled=True, configured=True, reason="no qualification marker"), ["no qualification marker is configured"], "qualification"),
        (ExtractionGate(enabled=True, configured=True, reason="qualification marker is stale or incompatible"), ["qualification marker is stale or incompatible"], "stale"),
    ],
)
def test_trusted_transcript_reports_specific_extraction_block(gate, blockers, expected_reason, tmp_path):
    repos, inbox = _setup(tmp_path)
    item = _item("item-blocked")
    _trust_parent(repos, item)
    _stage(inbox, item)
    _transcript(inbox, item, parent_id="ev-status-parent")
    status = _one(_service(tmp_path, repos, inbox, gate=gate, blockers=blockers).build())
    assert status.category == "extraction_blocked"
    assert expected_reason in status.reason


def test_valid_qualification_makes_trusted_transcript_extraction_ready(tmp_path):
    repos, inbox = _setup(tmp_path)
    item = _item("item-qualified")
    _trust_parent(repos, item)
    _stage(inbox, item)
    _transcript(inbox, item, parent_id="ev-status-parent")
    gate = ExtractionGate(enabled=True, configured=True, qualified=True, reason="exact configuration qualified")
    report = _service(tmp_path, repos, inbox, gate=gate, blockers=[]).build()
    assert _one(report).category == "extraction_ready"
    assert report.pilot_readiness["extraction_enabled"]["state"] == "READY"


def test_cli_uses_exact_qualification_integrity_and_configuration_gate(tmp_path):
    base_url = "http://model.invalid/v1"
    model = "fixture-model"
    config = OpenAICompatibleExtractionConfig.from_environment(base_url=base_url, model=model)
    provider = OpenAICompatibleExtractionProvider(config=config, repositories=None)
    fingerprint = qualification_configuration_fingerprint(
        provider="openai-compatible",
        model=model,
        base_url=base_url,
        prompt_version=PROMPT_VERSION,
        generation=public_configuration(provider),
    )
    evaluation = tmp_path / "qualification" / "evaluation.json"
    evaluation.parent.mkdir(parents=True)
    benchmark_sha = file_sha256(ROOT / "benchmarks" / "atomic-ci-v1.json")
    gold_set_file = tmp_path / "qualification" / "gold-set.json"
    gold_set_file.write_text('{"fixture": true}', encoding="utf-8")
    gold_set_sha = file_sha256(gold_set_file)
    artifact = {
        "qualification_artifact_schema_version": QUALIFICATION_ARTIFACT_SCHEMA_VERSION,
        "workflow_version": QUALIFICATION_WORKFLOW_VERSION,
        "run_id": "qualification-status-fixture",
        "complete": True,
        "stage_completion": {"probe": True, "synthetic_benchmark": True, "atomic_gold_set": True, "real_transcript_sample": True},
        "provider": "openai-compatible",
        "model": model,
        "prompt_version": PROMPT_VERSION,
        "extraction_version": EXTRACTION_VERSION,
        "configuration_fingerprint": fingerprint,
        "configuration": {"endpoint_identity": safe_endpoint_identity(base_url)},
        "benchmark_identity": {"id": "atomic-ci-v1", "version": 1, "sha256": benchmark_sha},
        "gold_set_identity": {"id": "gold-fixture", "version": 1, "sha256": gold_set_sha},
        "atomic_gold_set": {"passed": True},
    }
    evaluation.write_text(json.dumps(artifact), encoding="utf-8")
    (evaluation.parent / "evaluation.sha256").write_text(f"{file_sha256(evaluation)}  evaluation.json\n")
    marker = approve_qualification(evaluation, operator="status-fixture", expected_model=model)
    args = status_cli._parser().parse_args([
        "--enable-extraction", "--extract-base-url", base_url, "--extract-model", model,
        "--qualification-file", str(marker),
        "--qualification-gold-set-file", str(gold_set_file),
    ])
    gate, blockers = status_cli._extraction_state(args)
    assert gate.runnable is True and blockers == []

    artifact["model"] = "post-approval-tamper"
    evaluation.write_text(json.dumps(artifact), encoding="utf-8")
    stale_gate, stale_blockers = status_cli._extraction_state(args)
    assert stale_gate.runnable is False
    assert any("integrity" in blocker for blocker in stale_blockers)


def test_pending_atomic_proposal_requires_human_review(tmp_path):
    repos, inbox = _setup(tmp_path)
    item = _item("item-atomic")
    _trust_parent(repos, item)
    _stage(inbox, item)
    _transcript(inbox, item, parent_id="ev-status-parent")
    _atomic(inbox, "ev-status-parent", state="pending")
    report = _service(tmp_path, repos, inbox).build()
    status = _one(report)
    assert status.category == "human_atomic_evidence_review_required"
    assert status.pending_atomic_proposals == 1
    assert report.recommended_next_action == "review atomic evidence"


def test_rejected_atomic_proposal_is_completed_no_action(tmp_path):
    repos, inbox = _setup(tmp_path)
    item = _item("item-atomic-rejected")
    _trust_parent(repos, item)
    _stage(inbox, item)
    _transcript(inbox, item, parent_id="ev-status-parent")
    _atomic(inbox, "ev-status-parent", state="rejected")
    status = _one(_service(tmp_path, repos, inbox).build())
    assert status.category == "completed_no_action" and status.rejected_atomic_proposals == 1


def test_zero_candidate_extraction_completion_is_terminal(tmp_path):
    repos, inbox = _setup(tmp_path)
    item = _item("item-zero")
    _trust_parent(repos, item)
    _stage(inbox, item)
    payload = _transcript(inbox, item, parent_id="ev-status-parent")
    probe = dict(payload)
    probe.pop("item_id")
    content_hash = TranscriptArtifact.from_dict(probe).content_sha256()
    _operation(inbox, item, extraction_completed_transcript_sha256=content_hash)
    status = _one(_service(tmp_path, repos, inbox).build())
    assert status.category == "completed_no_action" and "zero-candidate" in status.reason


def test_retryable_and_intervention_failures_and_precedence(tmp_path):
    repos, inbox = _setup(tmp_path)
    retry = _item("item-retry")
    operator = _item("item-operator")
    _stage(inbox, retry)
    _stage(inbox, operator)
    _operation(inbox, retry, failure_class="retryable", retry_count=1, last_error="temporary timeout", next_eligible_retry_at="2026-08-16T13:00:00+00:00")
    _operation(inbox, operator, failure_class="operator", retry_count=0, last_error="parent mismatch")
    report = _service(tmp_path, repos, inbox).build()
    by_id = {item.item_id: item for item in report.items}
    assert by_id["item-retry"].category == "retryable_failure"
    assert by_id["item-operator"].category == "operator_intervention_required"
    assert report.recommended_next_action == "resolve operator-action failure"


def test_retry_limit_exhaustion_becomes_operator_intervention(tmp_path):
    repos, inbox = _setup(tmp_path)
    item = _item("item-exhausted")
    _stage(inbox, item)
    _operation(inbox, item, failure_class="retryable", retry_count=3, last_error="temporary timeout")
    assert _one(_service(tmp_path, repos, inbox).build()).category == "operator_intervention_required"


def test_active_and_stale_lock_are_reported_without_mutation(tmp_path):
    repos, inbox = _setup(tmp_path)
    lock = inbox / "operations" / "collection.lock"
    lock.parent.mkdir(parents=True)
    active_payload = {"run_id": "active-run", "started_at": "2026-08-16T11:00:00+00:00", "pid": 1}
    lock.write_text(json.dumps(active_payload))
    active = _service(tmp_path, repos, inbox).build()
    assert active.lock["state"] == "active" and active.pilot_readiness["collection_only"]["state"] == "BLOCKED"
    assert json.loads(lock.read_text()) == active_payload
    stale_payload = {"run_id": "stale-run", "started_at": "2026-08-16T01:00:00+00:00", "pid": 1}
    lock.write_text(json.dumps(stale_payload))
    stale = _service(tmp_path, repos, inbox).build()
    assert stale.lock["state"] == "stale" and stale.pilot_readiness["collection_only"]["state"] == "READY"
    assert json.loads(lock.read_text()) == stale_payload


def test_aggregate_and_per_source_counts_are_exact(tmp_path):
    repos, inbox = _setup(tmp_path)
    ready = _item("item-a-ready", SOURCE_A)
    review = _item("item-b-review", SOURCE_B)
    _stage(inbox, ready)
    _stage(inbox, review)
    _draft(inbox, review)
    report = _service(tmp_path, repos, inbox).build()
    assert report.counts["ready_to_advance"] == 1
    assert report.counts["human_publication_review_required"] == 1
    by_source = {source.source_id: source for source in report.sources}
    assert by_source[SOURCE_A].discovered_items == 1
    assert by_source[SOURCE_B].pending_publication_review == 1
    assert report.counts["discovered"] == 2
    assert "publication_review_ready" in report.counts
    assert "trusted_publication" in report.counts
    assert "skipped_irrelevant" in report.counts


def test_persisted_irrelevant_screening_is_counted(tmp_path):
    repos, inbox = _setup(tmp_path)
    item = _item("item-skip")
    item["title"] = "Celebrity gossip roundup"
    item["description"] = "Awards night fashion recap."
    item["relevance_screening"] = {
        "score": 0,
        "decision": "skip",
        "reason": "score 0 <= skip threshold 3 and no strong berry signal",
        "likely_berry_ids": [],
        "screener_provenance": {"screener": "deterministic-relevance-v1", "trust_state": "untrusted_triage"},
    }
    _stage(inbox, item)
    report = _service(tmp_path, repos, inbox).build(source_id=SOURCE_A)
    assert report.counts["skipped_irrelevant"] == 1
    assert report.items[0].category == "completed_no_action"


def test_malformed_item_and_operation_degrade_gracefully(tmp_path):
    repos, inbox = _setup(tmp_path)
    _stage(inbox, _item("item-good"))
    folder = inbox / "discovered_media"
    (folder / "item-bad.json").write_text("{bad json")
    operations = inbox / "operations" / "items"
    operations.mkdir(parents=True)
    (operations / "orphan.json").write_text("not json")
    report = _service(tmp_path, repos, inbox).build()
    assert any(item.item_id == "item-good" for item in report.items)
    assert report.counts["operator_intervention_required"] >= 2
    assert {problem.kind for problem in report.problems} >= {"discovered item", "operational item state"}
    assert report.pilot_readiness["collection_only"]["state"] == "BLOCKED"


def test_json_shape_is_stable_and_sorted(tmp_path):
    repos, inbox = _setup(tmp_path)
    _stage(inbox, _item("item-z", SOURCE_B))
    _stage(inbox, _item("item-a", SOURCE_A))
    first = _service(tmp_path, repos, inbox).build().as_dict()
    second = _service(tmp_path, repos, inbox).build().as_dict()
    assert first == second
    assert [source["source_id"] for source in first["sources"]] == [SOURCE_A, SOURCE_B]
    assert [item["item_id"] for item in first["items"]] == ["item-a", "item-z"]


def test_status_is_strictly_read_only_and_never_calls_network_transcription_or_model(tmp_path, monkeypatch):
    repos, inbox = _setup(tmp_path)
    _stage(inbox, _item("item-readonly"))
    monkeypatch.setattr(media_discovery, "discover_source", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("network discovery called")))
    monkeypatch.setattr(media_transcription, "transcribe_discovered_item", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("transcription called")))
    monkeypatch.setattr(OpenAICompatibleExtractionProvider, "extract", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("model called")))
    before = {path.relative_to(tmp_path): path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    report = _service(tmp_path, repos, inbox).build()
    after = {path.relative_to(tmp_path): path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    assert report.items and before == after
    assert not (inbox / "operations" / "collection.lock").exists()


def test_status_is_not_connected_to_public_static_generation():
    assert "collection_status" not in (ROOT / "scripts" / "build_static.py").read_text(encoding="utf-8")
    assert "collection_status" not in (ROOT / "app" / "main.py").read_text(encoding="utf-8")


def test_persisted_operator_status_does_not_recompute_item_orchestration(tmp_path, monkeypatch):
    repos, inbox = _setup(tmp_path)
    item = _item("item-persisted")
    _stage(inbox, item)
    _draft(inbox, item)
    runs = inbox / "operations" / "runs"
    runs.mkdir(parents=True)
    (runs / "collection-20260816T120000Z.json").write_text(json.dumps({
        "run_id": "collection-persisted",
        "started_at": "2026-08-16T12:00:00+00:00",
        "completed_at": "2026-08-16T12:00:05+00:00",
        "sources": [{"source_id": SOURCE_A, "status": "ok", "found": 1, "new": 1}],
        "counts": {
            "items_processed": 1,
            "publication_drafts_created": 1,
            "awaiting_publication_review": 1,
            "sources_failed": 0,
            "sources_succeeded": 1,
        },
        "items": [{"item_id": item["id"], "state": "awaiting_publication_review"}],
    }), encoding="utf-8")
    monkeypatch.setattr(
        "app.services.collection_status._StatusOrchestrationService.process",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("broad item recomputation called")),
    )
    report = _service(tmp_path, repos, inbox).build(persisted_only=True)
    assert report.detail_mode == "persisted" and report.items == []
    assert report.counts["human_publication_review_required"] == 1
    assert report.review_backlog["publication_review"] == 1
