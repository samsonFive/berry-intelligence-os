"""Offline tests for repeatable provider/model extraction evaluation."""

from __future__ import annotations

from datetime import date, datetime, timezone
import json
from pathlib import Path

import httpx

from app import main
from app.services.ai_extraction import (
    PROMPT_VERSION,
    OpenAICompatibleExtractionConfig,
    OpenAICompatibleExtractionProvider,
)
from app.services.extraction_evaluation import (
    BenchmarkCase,
    ExtractionBenchmark,
    candidate_preview,
    deterministic_window_sample,
    load_benchmark,
    probe_provider,
    run_benchmark,
    run_transcript_preview,
    score_case,
    write_evaluation_artifact,
)
from app.services.transcript_evidence import ExtractionRequest, TranscriptArtifact, TranscriptEvidenceExtractionService


ROOT = Path(__file__).resolve().parents[1]
PARENT_ID = "ev-evaluation-parent"


class FakeResponse:
    def __init__(self, candidates: list[dict] | None = None, *, content: str | None = None, usage: dict | None = None):
        output = content if content is not None else json.dumps({"candidates": candidates or []})
        self.payload = {
            "choices": [{"message": {"content": output, "refusal": None}, "finish_reason": "stop"}],
            "usage": usage or {},
        }

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


class SequencePost:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls: list[dict] = []

    def __call__(self, url: str, **kwargs):
        self.calls.append({"url": url, **kwargs})
        response = self.responses[len(self.calls) - 1]
        if isinstance(response, Exception):
            raise response
        return response


def _candidate(statement: str, indexes: list[int], **links) -> dict:
    return {
        "normalized_statement": statement,
        "segment_indexes": indexes,
        "entity_ids": links.get("entity_ids", []),
        "geography_ids": links.get("geography_ids", []),
        "berry_ids": links.get("berry_ids", []),
    }


def _parent() -> dict:
    return {
        "id": PARENT_ID,
        "record_type": "evidence",
        "status": "published",
        "review_state": "published",
        "evidence_role": "publication_artifact",
        "source_type": "industry_podcast",
        "title": "Evaluation fixture",
        "source_name": "Fixture Publisher",
        "source_url": "https://example.invalid/evaluation",
        "published_date": "2026-01-01",
        "captured_date": "2026-08-16",
        "summary": "Synthetic evaluation parent.",
        "submitted_by": "fixture",
        "source_id": "source-evaluation-fixture",
        "priority": {
            dimension: {"level": "none", "rationale": ""}
            for dimension in ("reading", "testing", "commercial_position", "monitoring")
        },
    }


def _transcript(texts: list[str] | None = None) -> TranscriptArtifact:
    texts = texts or ["Welcome.", "We think production could reach approximately 200 tonnes."]
    return TranscriptArtifact.from_dict(
        {
            "transcript_id": "evaluation-transcript",
            "parent_evidence_id": PARENT_ID,
            "language": "en",
            "provenance": {"method": "human_provided", "created_by": "fixture", "created_at": "2026-08-16"},
            "segments": [
                {"text": text, "start_seconds": index * 10, "end_seconds": index * 10 + 9}
                for index, text in enumerate(texts)
            ],
        }
    )


def _setup(tmp_path: Path):
    repos = main.get_repositories(tmp_path / "data", main.SCHEMAS_DIR)
    repos.sources.create({"id": "source-evaluation-fixture", "name": "Fixture Publisher"})
    repos.evidence.create(_parent())
    return repos


def _provider(repos, post, *, model="fixture-model", api_key=None, window_chars=12_000, overlap=1):
    return OpenAICompatibleExtractionProvider(
        config=OpenAICompatibleExtractionConfig(
            base_url="http://model.invalid/v1",
            model=model,
            api_key=api_key,
            window_chars=window_chars,
            overlap_segments=overlap,
        ),
        repositories=repos,
        post=post,
    )


def _case(**expectation_changes) -> BenchmarkCase:
    expectations = {
        "candidate_count": {"min": 1, "max": 1},
        "required_phrase_groups": [["could", "200"]],
        "required_qualifiers": ["could", "approximately"],
        "prohibited_phrases": ["will reach"],
        "required_segment_sets": [[0]],
        "expected_atomic_claims": 1,
        "max_link_count": 0,
        "category": "forecast",
    }
    expectations.update(expectation_changes)
    return BenchmarkCase(
        "qualified-case",
        "Qualified case",
        ({"text": "We think production could reach approximately 200 tonnes.", "start_seconds": 0, "end_seconds": 5},),
        expectations,
    )


def _benchmark(case: BenchmarkCase | None = None) -> ExtractionBenchmark:
    return ExtractionBenchmark("fixture-benchmark", 1, "Fixture", (case or _case(),))


def test_endpoint_probe_success_reports_compatible_structured_response(tmp_path: Path) -> None:
    post = SequencePost([FakeResponse([])])
    report = probe_provider(_provider(_setup(tmp_path), post))
    assert report["endpoint_reachable"] is True
    assert report["compatible_response_received"] is True
    assert report["structured_output_capability"] is True
    assert report["model"] == "fixture-model"
    assert len(post.calls) == 1


def test_endpoint_probe_failure_is_operator_readable(tmp_path: Path) -> None:
    report = probe_provider(_provider(_setup(tmp_path), SequencePost([httpx.ReadTimeout("offline")])))
    assert report["endpoint_reachable"] is False
    assert report["compatible_response_received"] is False
    assert "timed out" in report["error"]


def test_probe_diagnostics_do_not_leak_secret(tmp_path: Path) -> None:
    secret = "private-evaluation-token"
    report = probe_provider(
        _provider(_setup(tmp_path), SequencePost([httpx.ConnectError(secret)]), api_key=secret)
    )
    assert secret not in json.dumps(report)
    assert "Authorization" not in json.dumps(report)


def test_committed_benchmark_fixture_parses_all_twelve_generic_cases() -> None:
    benchmark = load_benchmark(ROOT / "benchmarks" / "atomic-ci-v1.json")
    assert benchmark.benchmark_id == "atomic-ci-synthetic-v1"
    assert len(benchmark.cases) == 12
    assert {case.case_id for case in benchmark.cases} >= {"no-intelligence", "qualified-forecast"}
    assert all(case.expectations.get("max_link_count") == 0 for case in benchmark.cases)


def test_zero_candidate_expectation_scores_correctly() -> None:
    case = _case(
        candidate_count={"min": 0, "max": 0},
        required_phrase_groups=[],
        required_qualifiers=[],
        prohibited_phrases=[],
        required_segment_sets=[],
        expected_atomic_claims=0,
    )
    assert score_case(case, [])["passed"] is True


def test_qualifier_preservation_and_prohibited_inference_are_scored_separately() -> None:
    good = [_candidate("The speaker thinks production could reach approximately 200 tonnes.", [0])]
    bad = [_candidate("Production will reach 200 tonnes.", [0])]
    assert score_case(_case(), good)["passed"] is True
    bad_score = score_case(_case(), bad)
    assert bad_score["passed"] is False
    assert bad_score["checks"]["required_qualifiers"] == {"could": False, "approximately": False}
    assert bad_score["checks"]["prohibited_inference_hits"]


def test_expected_multi_claim_separation_is_measured() -> None:
    case = _case(
        candidate_count={"min": 2, "max": 2},
        required_phrase_groups=[["capacity"], ["cultivar"]],
        required_qualifiers=[],
        prohibited_phrases=[],
        required_segment_sets=[],
        expected_atomic_claims=2,
    )
    merged = [_candidate("Capacity increased and a cultivar will launch.", [0])]
    split = [_candidate("Capacity increased.", [0]), _candidate("A cultivar will launch.", [0])]
    assert score_case(case, merged)["checks"]["atomic_separation"] is False
    assert score_case(case, split)["passed"] is True


def test_benchmark_reports_structural_metrics_invalid_output_and_token_usage(tmp_path: Path) -> None:
    invalid = {**_candidate("Bad model timestamp.", [0]), "start_seconds": 0}
    post = SequencePost([FakeResponse([invalid], usage={"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14})])
    report = run_benchmark(_provider(_setup(tmp_path), post), _benchmark())
    assert report["metrics"]["invalid_candidates"] == 1
    assert report["metrics"]["structurally_valid_response_rate"] == 0
    assert report["metrics"]["total_tokens"] == 14
    assert report["metrics"]["failure_modes"]["model_supplied_timestamp_rejections"] == 1
    assert isinstance(report["metrics"]["elapsed_seconds"], float)
    assert report["prompt_version"] == PROMPT_VERSION
    assert report["configuration"]["window_chars"] == 12_000


def test_benchmark_failure_modes_count_invalid_json_and_unsupported_ids(tmp_path: Path) -> None:
    benchmark = _benchmark()
    repos = _setup(tmp_path)
    invalid_json = run_benchmark(
        _provider(repos, SequencePost([FakeResponse(content="not json")])),
        benchmark,
    )
    unsupported = run_benchmark(
        _provider(
            repos,
            SequencePost([FakeResponse([_candidate("Unsupported link.", [0], entity_ids=["company-invented"])])]),
        ),
        benchmark,
    )
    assert invalid_json["metrics"]["failure_modes"]["invalid_json_responses"] == 1
    assert unsupported["metrics"]["failure_modes"]["unsupported_id_rejections"] == 1


def test_preview_contains_grounding_diagnostics_and_writes_no_evidence(tmp_path: Path) -> None:
    repos = _setup(tmp_path)
    candidate = _candidate("The speaker thinks production could reach approximately 200 tonnes.", [1])
    provider = _provider(repos, SequencePost([FakeResponse([candidate])]))
    report = run_transcript_preview(provider, _transcript(), _parent())
    assert report["candidates"][0]["transcript_excerpt"].startswith("We think")
    assert report["candidates"][0]["start_seconds"] == 10
    assert report["candidates"][0]["end_seconds"] == 19
    assert report["candidates"][0]["prompt_version"] == PROMPT_VERSION
    assert not (tmp_path / "inbox" / "evidence").exists()


def test_explicit_production_path_still_uses_existing_proposal_service(tmp_path: Path) -> None:
    repos = _setup(tmp_path)
    candidate = _candidate("The speaker thinks production could reach approximately 200 tonnes.", [1])
    provider = _provider(repos, SequencePost([FakeResponse([candidate])]))
    validator = main.get_validator("evidence.schema.json")
    service = TranscriptEvidenceExtractionService(
        repositories=repos,
        inbox_dir=tmp_path / "inbox",
        evidence_errors=lambda record: [error.message for error in validator.iter_errors(record)],
        provider=provider,
        today=lambda: date(2026, 8, 16),
    )
    result = service.run(_transcript())
    assert len(result.accepted) == 1
    draft = json.loads(next((tmp_path / "inbox" / "evidence").glob("*.json")).read_text(encoding="utf-8"))
    assert draft["status"] == "draft" and draft["review_state"] == "in_review"
    assert repos.evidence.get(draft["id"]) is None
    assert repos.facts.list() == [] and repos.relationships.list() == []
    assert repos.assessments.list() == [] and repos.recommendations.list() == []


def test_cli_persist_flag_delegates_to_existing_proposal_flow(tmp_path: Path, monkeypatch, capsys) -> None:
    repos = _setup(tmp_path)
    transcript_path = tmp_path / "transcript.json"
    transcript = _transcript()
    transcript_path.write_text(
        json.dumps(
            {
                "transcript_id": transcript.transcript_id,
                "parent_evidence_id": transcript.parent_evidence_id,
                "language": transcript.language,
                "provenance": {
                    "method": transcript.provenance.method,
                    "created_by": transcript.provenance.created_by,
                    "created_at": transcript.provenance.created_at,
                },
                "segments": [
                    {
                        "text": segment.text,
                        "start_seconds": segment.start_seconds,
                        "end_seconds": segment.end_seconds,
                    }
                    for segment in transcript.segments
                ],
            }
        ),
        encoding="utf-8",
    )
    candidate = _candidate("The speaker thinks production could reach approximately 200 tonnes.", [1])
    from scripts import evaluate_extraction

    monkeypatch.setattr(
        evaluate_extraction,
        "OpenAICompatibleExtractionProvider",
        lambda **kwargs: _provider(repos, SequencePost([FakeResponse([candidate])])),
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "evaluate_extraction.py",
            "--transcript",
            str(transcript_path),
            "--full",
            "--persist-proposals",
            "--extract-base-url",
            "http://model.invalid/v1",
            "--model",
            "fixture-model",
            "--data-dir",
            str(tmp_path / "data"),
            "--inbox-dir",
            str(tmp_path / "inbox"),
        ],
    )
    assert evaluate_extraction.main() == 0
    output = json.loads(capsys.readouterr().out)
    assert output["mode"] == "production_proposals"
    assert len(output["result"]["accepted_proposal_ids"]) == 1
    assert len(list((tmp_path / "inbox" / "evidence").glob("*.json"))) == 1
    assert len(list((tmp_path / "inbox" / "evaluations").glob("*.json"))) == 1


def test_deterministic_sampling_covers_beginning_middle_and_end() -> None:
    assert deterministic_window_sample(10, 5) == [0, 2, 4, 7, 9]
    assert deterministic_window_sample(3, 5) == [0, 1, 2]
    assert deterministic_window_sample(10, 1) == [0]


def test_sample_mode_calls_only_selected_production_windows(tmp_path: Path) -> None:
    transcript = _transcript([f"segment {index} " + "x" * 480 for index in range(10)])
    post = SequencePost([FakeResponse([]) for _ in range(3)])
    provider = _provider(_setup(tmp_path), post, window_chars=500, overlap=0)
    report = run_transcript_preview(provider, transcript, _parent(), sample_windows=3)
    assert report["transcript"]["sampled_window_numbers"] == [0, 4, 9]
    assert report["metrics"]["window_count"] == 3
    assert len(post.calls) == 3


def test_model_comparison_reports_distinguish_models(tmp_path: Path) -> None:
    candidate = _candidate("Production could reach approximately 200 tonnes.", [0])
    repos = _setup(tmp_path)
    first = run_benchmark(_provider(repos, SequencePost([FakeResponse([candidate])]), model="model-a"), _benchmark())
    second = run_benchmark(_provider(repos, SequencePost([FakeResponse([candidate])]), model="model-b"), _benchmark())
    assert first["model"] == "model-a" and second["model"] == "model-b"
    assert first["benchmark"] == second["benchmark"]


def test_evaluation_artifact_is_untrusted_and_outside_data(tmp_path: Path) -> None:
    report = {"mode": "benchmark", "model": "fixture", "benchmark": {"id": "x"}, "metrics": {}}
    instant = datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc)
    path = write_evaluation_artifact(report, tmp_path / "inbox", now=lambda: instant)
    assert path.parent == tmp_path / "inbox" / "evaluations"
    assert not path.is_relative_to(tmp_path / "data")
    artifact = json.loads(path.read_text(encoding="utf-8"))
    assert artifact["evaluation_schema_version"] == 1
    assert artifact["created_at"] == instant.isoformat()


def test_candidate_preview_uses_transcript_timestamps_not_model_fields(tmp_path: Path) -> None:
    provider = _provider(_setup(tmp_path), SequencePost([]))
    preview = candidate_preview(_transcript(), _candidate("Qualified claim.", [1]), provider=provider)
    assert preview["start_seconds"] == 10.0 and preview["end_seconds"] == 19.0
    assert set(preview) >= {"provider", "model", "prompt_version", "segment_indexes"}
