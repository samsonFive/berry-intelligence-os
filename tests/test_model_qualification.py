"""Offline tests for explicit, integrity-linked extraction-model qualification."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import httpx
import pytest

from app import main
from app.services.ai_extraction import PROMPT_VERSION, OpenAICompatibleExtractionConfig, OpenAICompatibleExtractionProvider
from app.services.collection_runner import resolve_extraction_gate
from app.services.extraction_evaluation import BenchmarkCase, ExtractionBenchmark, probe_provider, public_configuration
from app.services.model_qualification import (
    QualificationError,
    approve_qualification,
    file_sha256,
    load_cached_transcript,
    provider_qualification_configuration,
    qualification_configuration_fingerprint,
    run_qualification_evaluation,
    safe_endpoint_identity,
)
from app.services.transcript_evidence import TranscriptArtifact


NOW = datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc)
PARENT_ID = "ev-qualification-parent"


class FakeResponse:
    def __init__(self, candidates=None, *, content=None, model="returned-fixture-model"):
        self.payload = {
            "model": model,
            "choices": [{
                "message": {"content": content if content is not None else json.dumps({"candidates": candidates or []}), "refusal": None},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
        }

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class SequencePost:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        response = self.responses[len(self.calls) - 1]
        if isinstance(response, Exception):
            raise response
        return response


def _parent():
    return {
        "id": PARENT_ID,
        "record_type": "evidence",
        "status": "published",
        "review_state": "published",
        "evidence_role": "publication_artifact",
        "source_type": "industry_podcast",
        "title": "Company-neutral qualification fixture",
        "source_name": "Fixture Publisher",
        "source_url": "https://example.invalid/episode",
        "published_date": "2026-01-01",
        "captured_date": "2026-08-16",
        "summary": "Synthetic fixture.",
        "submitted_by": "fixture",
        "source_id": "source-qualification-fixture",
        "priority": {dimension: {"level": "none", "rationale": ""} for dimension in ("reading", "testing", "commercial_position", "monitoring")},
    }


def _repos(tmp_path):
    repos = main.get_repositories(tmp_path / "data", main.SCHEMAS_DIR)
    repos.sources.create({"id": "source-qualification-fixture", "name": "Fixture Publisher"})
    repos.evidence.create(_parent())
    return repos


def _transcript(segment_count=4):
    return TranscriptArtifact.from_dict({
        "transcript_id": "qualification-transcript",
        "parent_evidence_id": PARENT_ID,
        "language": "en",
        "provenance": {"method": "auto_generated", "created_by": "fixture:small", "created_at": "2026-08-16"},
        "segments": [
            {"text": f"Neutral transcript segment {index}.", "start_seconds": index * 10, "end_seconds": index * 10 + 9, "speaker_label": "Speaker" if index == 1 else None}
            for index in range(segment_count)
        ],
    })


def _benchmark():
    return ExtractionBenchmark(
        "qualification-fixture-v1",
        1,
        "One zero-intelligence fixture; production qualification uses the committed 12-case benchmark.",
        (BenchmarkCase(
            "no-intelligence",
            "No intelligence",
            ({"text": "Welcome to the show.", "start_seconds": 0, "end_seconds": 2},),
            {"candidate_count": {"min": 0, "max": 0}, "required_phrase_groups": [], "required_qualifiers": [], "prohibited_phrases": [], "required_segment_sets": [], "expected_atomic_claims": 0, "max_link_count": 0, "category": "no intelligence"},
        ),),
    )


def _provider(repos, responses, *, model="fixture-model", api_key=None, base_url="http://model.invalid/v1?token=hidden"):
    return OpenAICompatibleExtractionProvider(
        config=OpenAICompatibleExtractionConfig(
            base_url=base_url,
            model=model,
            api_key=api_key,
            window_chars=12_000,
            overlap_segments=1,
        ),
        repositories=repos,
        post=SequencePost(responses),
    )


def _evaluate(tmp_path, responses=None, *, provider=None):
    repos = provider._repos if provider is not None else _repos(tmp_path)
    provider = provider or _provider(repos, responses or [FakeResponse(), FakeResponse(), FakeResponse()])
    return (*run_qualification_evaluation(
        provider=provider,
        benchmark=_benchmark(),
        transcript=_transcript(),
        parent_evidence=_parent(),
        repositories=repos,
        output_dir=tmp_path / "inbox" / "qualifications",
        sample_windows=1,
        benchmark_sha256="b" * 64,
        transcript_cache_path=tmp_path / "inbox" / "cached-transcript.json",
        now=lambda: NOW,
    ), provider, repos)


def test_endpoint_probe_success_captures_returned_model_and_safe_endpoint(tmp_path):
    repos = _repos(tmp_path)
    provider = _provider(repos, [FakeResponse()])
    report = probe_provider(provider)
    assert report["compatible_response_received"] is True
    assert report["returned_model_identities"] == ["returned-fixture-model"]
    assert report["failure_category"] is None
    identity = safe_endpoint_identity(provider.config.base_url)
    assert identity["display"] == "http://model.invalid/v1"
    assert "hidden" not in json.dumps(identity)


def test_endpoint_probe_failure_is_not_qualification(tmp_path):
    repos = _repos(tmp_path)
    provider = _provider(repos, [httpx.ReadTimeout("offline")])
    artifact_path, _packet, _provider_used, _repos_used = _evaluate(tmp_path, provider=provider)
    artifact = json.loads(artifact_path.read_text())
    assert artifact["complete"] is False
    assert artifact["stage_completion"] == {"probe": False, "synthetic_benchmark": False, "real_transcript_sample": False}
    with pytest.raises(QualificationError, match="incomplete"):
        approve_qualification(artifact_path, operator="reviewer", expected_model="fixture-model")


def test_credentials_are_absent_from_evaluation_packet_and_marker(tmp_path):
    secret = "private-qualification-secret"
    repos = _repos(tmp_path)
    provider = _provider(repos, [FakeResponse(), FakeResponse(), FakeResponse()], api_key=secret)
    artifact_path, packet_path, _provider_used, _repos_used = _evaluate(tmp_path, provider=provider)
    marker = approve_qualification(artifact_path, operator="reviewer", expected_model="fixture-model", now=lambda: NOW)
    combined = artifact_path.read_text() + packet_path.read_text() + marker.read_text()
    assert secret not in combined and "Authorization" not in combined and "token=hidden" not in combined


def test_workflow_reuses_existing_benchmark_and_preview_harness(tmp_path, monkeypatch):
    calls = {"benchmark": 0, "preview": 0}
    from app.services import model_qualification
    real_benchmark = model_qualification.run_benchmark
    real_preview = model_qualification.run_transcript_preview

    def benchmark(provider, fixture):
        calls["benchmark"] += 1
        assert isinstance(fixture, ExtractionBenchmark)
        return real_benchmark(provider, fixture)

    def preview(provider, transcript, parent, *, sample_windows):
        calls["preview"] += 1
        return real_preview(provider, transcript, parent, sample_windows=sample_windows)

    monkeypatch.setattr(model_qualification, "run_benchmark", benchmark)
    monkeypatch.setattr(model_qualification, "run_transcript_preview", preview)
    artifact_path, _packet, _provider_used, _repos_used = _evaluate(tmp_path)
    assert json.loads(artifact_path.read_text())["complete"] is True
    assert calls == {"benchmark": 1, "preview": 1}


def test_cached_transcript_loading_is_read_only_and_deterministic(tmp_path):
    inbox = tmp_path / "inbox"
    path = inbox / "discovered_media" / "_normalized_transcripts" / "item-fixture.json"
    path.parent.mkdir(parents=True)
    transcript = _transcript(12)
    payload = {
        "item_id": "item-fixture", "transcript_id": transcript.transcript_id,
        "parent_evidence_id": PARENT_ID, "language": transcript.language,
        "provenance": {"method": transcript.provenance.method, "created_by": transcript.provenance.created_by, "created_at": transcript.provenance.created_at},
        "segments": [segment.__dict__ for segment in transcript.segments],
    }
    path.write_text(json.dumps(payload))
    before = path.read_bytes()
    first, first_path = load_cached_transcript(inbox, parent_evidence_id=PARENT_ID)
    second, second_path = load_cached_transcript(inbox, parent_evidence_id=PARENT_ID)
    assert first.content_sha256() == second.content_sha256()
    assert first_path == second_path == path and path.read_bytes() == before


def test_complete_artifact_has_reproducible_identity_and_human_packet(tmp_path):
    artifact_path, packet_path, provider, repos = _evaluate(tmp_path)
    artifact = json.loads(artifact_path.read_text())
    expected = provider_qualification_configuration(provider)
    assert artifact["complete"] is True
    assert artifact["configuration"] == expected
    assert artifact["benchmark_identity"]["sha256"] == "b" * 64
    assert artifact["real_sample_identity"]["semantic_stratification"] is False
    assert artifact["real_transcript_sample"]["transcript"]["sampled_window_numbers"] == [0]
    assert "Human rubric" in packet_path.read_text()
    assert not (tmp_path / "inbox" / "evidence").exists()
    assert repos.facts.list() == [] and repos.assessments.list() == [] and repos.recommendations.list() == []


def test_partial_benchmark_and_malformed_real_sample_cannot_be_approved(tmp_path):
    partial, _packet, _provider_used, _repos_used = _evaluate(
        tmp_path / "partial", [FakeResponse(), FakeResponse(content="not-json"), FakeResponse()]
    )
    malformed, _packet, _provider_used, _repos_used = _evaluate(
        tmp_path / "malformed", [FakeResponse(), FakeResponse(), FakeResponse(content="not-json")]
    )
    for artifact_path in (partial, malformed):
        assert json.loads(artifact_path.read_text())["complete"] is False
        with pytest.raises(QualificationError, match="incomplete"):
            approve_qualification(artifact_path, operator="reviewer", expected_model="fixture-model")


def test_explicit_operator_action_is_required_and_marker_is_runner_compatible(tmp_path):
    artifact_path, _packet, provider, _repos_used = _evaluate(tmp_path)
    marker_path = artifact_path.with_name("qualification-marker.json")
    assert not marker_path.exists()
    with pytest.raises(QualificationError, match="operator identity"):
        approve_qualification(artifact_path, operator=" ", expected_model="fixture-model")
    marker = approve_qualification(artifact_path, operator="human-reviewer", expected_model="fixture-model", now=lambda: NOW)
    payload = json.loads(marker.read_text())
    fingerprint = qualification_configuration_fingerprint(
        provider="openai-compatible", model="fixture-model", base_url=provider.config.base_url,
        prompt_version=PROMPT_VERSION, generation=public_configuration(provider),
    )
    assert payload["operator_qualified"] is True and payload["evaluation_sha256"] == file_sha256(artifact_path)
    gate = resolve_extraction_gate(
        enabled=True, provider="openai-compatible", model="fixture-model", base_url=provider.config.base_url,
        prompt_version=PROMPT_VERSION, qualification_path=marker, configuration_fingerprint=fingerprint,
        benchmark_sha256="b" * 64,
    )
    assert gate.runnable is True


@pytest.mark.parametrize(
    "kwargs,match",
    [
        ({"expected_provider": "different"}, "provider"),
        ({"expected_model": "different"}, "model"),
        ({"expected_prompt_version": "atomic-ci-v2"}, "prompt_version"),
    ],
)
def test_approval_identity_mismatch_blocks_marker(tmp_path, kwargs, match):
    artifact_path, _packet, _provider_used, _repos_used = _evaluate(tmp_path)
    with pytest.raises(QualificationError, match=match):
        approve_qualification(artifact_path, operator="reviewer", **kwargs)


def test_tampered_evaluation_and_changed_runtime_configuration_are_rejected(tmp_path):
    artifact_path, _packet, provider, _repos_used = _evaluate(tmp_path)
    original = artifact_path.read_text()
    artifact_path.write_text(original.replace("fixture-model", "tampered-model", 1))
    with pytest.raises(QualificationError, match="integrity"):
        approve_qualification(artifact_path, operator="reviewer", expected_model="fixture-model")
    artifact_path.write_text(original)
    artifact_path.with_name("evaluation.sha256").write_text(f"{file_sha256(artifact_path)}  evaluation.json\n")
    marker = approve_qualification(artifact_path, operator="reviewer", expected_model="fixture-model")
    changed = qualification_configuration_fingerprint(
        provider="openai-compatible", model="fixture-model", base_url="http://different.invalid/v1",
        prompt_version=PROMPT_VERSION, generation=public_configuration(provider),
    )
    gate = resolve_extraction_gate(
        enabled=True, provider="openai-compatible", model="fixture-model", base_url="http://different.invalid/v1",
        prompt_version=PROMPT_VERSION, qualification_path=marker, configuration_fingerprint=changed,
        benchmark_sha256="b" * 64,
    )
    assert gate.runnable is False and "does not match" in gate.reason

    artifact_path.write_text(original.replace("fixture-model", "post-approval-tamper", 1))
    tampered_gate = resolve_extraction_gate(
        enabled=True, provider="openai-compatible", model="fixture-model", base_url=provider.config.base_url,
        prompt_version=PROMPT_VERSION, qualification_path=marker,
        configuration_fingerprint=json.loads(marker.read_text())["configuration_fingerprint"],
        benchmark_sha256="b" * 64,
    )
    assert tampered_gate.runnable is False and "integrity" in tampered_gate.reason


def test_repeated_approval_does_not_overwrite_history_and_artifacts_stay_outside_data(tmp_path):
    artifact_path, packet_path, _provider_used, _repos_used = _evaluate(tmp_path)
    marker = approve_qualification(artifact_path, operator="reviewer", expected_model="fixture-model")
    before = marker.read_bytes()
    with pytest.raises(QualificationError, match="already exists"):
        approve_qualification(artifact_path, operator="reviewer", expected_model="fixture-model")
    assert marker.read_bytes() == before
    assert artifact_path.is_relative_to(tmp_path / "inbox")
    assert packet_path.is_relative_to(tmp_path / "inbox")
    assert not artifact_path.is_relative_to(tmp_path / "data")


def test_approve_cli_issues_marker_only_after_explicit_command(tmp_path, capsys):
    artifact_path, _packet, _provider_used, _repos_used = _evaluate(tmp_path)
    from scripts import qualify_extraction_model
    assert qualify_extraction_model.main([
        "approve", "--evaluation", str(artifact_path), "--model", "fixture-model", "--operator", "reviewer",
    ]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["state"] == "qualified"
    assert Path(output["marker"]).exists()
