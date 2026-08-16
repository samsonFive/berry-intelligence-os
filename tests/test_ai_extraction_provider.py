"""Offline contract tests for long-transcript real-model extraction."""

from __future__ import annotations

from datetime import date
import json
from pathlib import Path

import httpx
import pytest

from app import main
from app.services.ai_extraction import (
    PROMPT_VERSION,
    ExtractionProviderError,
    OpenAICompatibleExtractionConfig,
    OpenAICompatibleExtractionProvider,
    build_transcript_windows,
)
from app.services.transcript_evidence import ExtractionRequest, TranscriptArtifact, TranscriptEvidenceExtractionService


PARENT_ID = "ev-ai-extraction-parent"


class FakeResponse:
    def __init__(
        self,
        content: str | None,
        *,
        usage: dict | None = None,
        finish_reason: str = "stop",
        refusal: str | None = None,
    ) -> None:
        self._payload = {
            "choices": [{"message": {"content": content, "refusal": refusal}, "finish_reason": finish_reason}],
            "usage": usage or {},
        }

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class SequencePost:
    def __init__(self, responses: list[FakeResponse | Exception]) -> None:
        self.responses = responses
        self.calls: list[dict] = []

    def __call__(self, url: str, **kwargs):
        self.calls.append({"url": url, **kwargs})
        response = self.responses[len(self.calls) - 1]
        if isinstance(response, Exception):
            raise response
        return response


def _candidate(statement: str, indexes: list[int], **extra) -> dict:
    candidate = {
        "normalized_statement": statement,
        "segment_indexes": indexes,
        "entity_ids": [],
        "geography_ids": [],
        "berry_ids": [],
    }
    candidate.update(extra)
    return candidate


def _content(candidates: list[dict]) -> str:
    return json.dumps({"candidates": candidates})


def _parent() -> dict:
    return {
        "id": PARENT_ID,
        "record_type": "evidence",
        "status": "published",
        "review_state": "published",
        "source_type": "industry_podcast",
        "title": "AI extraction fixture",
        "source_name": "Fixture Publisher",
        "source_url": "https://example.invalid/ai-fixture",
        "published_date": "2026-01-01",
        "captured_date": "2026-08-16",
        "summary": "Synthetic parent.",
        "submitted_by": "fixture",
        "source_id": "source-ai-extraction-fixture",
        "evidence_role": "publication_artifact",
        "media_format": "podcast",
        "priority": {
            dimension: {"level": "none", "rationale": ""}
            for dimension in ("reading", "testing", "commercial_position", "monitoring")
        },
    }


def _transcript(texts: list[str] | None = None) -> TranscriptArtifact:
    texts = texts or [
        "Welcome to the programme.",
        "We may expand the trial depending on early results.",
        "Approximately 20 hectares could be involved.",
        "Growers tell us flavor remains important.",
    ]
    return TranscriptArtifact.from_dict(
        {
            "transcript_id": "transcript-ai-fixture",
            "parent_evidence_id": PARENT_ID,
            "language": "en",
            "provenance": {"method": "auto_generated", "created_by": "fixture", "created_at": "2026-08-16"},
            "segments": [
                {"text": text, "start_seconds": index * 10, "end_seconds": index * 10 + 9}
                for index, text in enumerate(texts)
            ],
        }
    )


def _setup(tmp_path: Path):
    repos = main.get_repositories(tmp_path / "data", main.SCHEMAS_DIR)
    repos.sources.create({"id": "source-ai-extraction-fixture", "name": "Fixture Publisher"})
    repos.evidence.create(_parent())
    for entity in (
        {"id": "company-fixture", "record_type": "entity", "entity_type": "company", "name": "Fixture Company", "status": "active"},
        {"id": "geography-fixture", "record_type": "entity", "entity_type": "geography", "name": "Fixture Geography", "status": "active"},
        {"id": "berry-fixture", "record_type": "entity", "entity_type": "berry", "name": "Fixture Berry", "status": "active"},
    ):
        repos.entities.create(entity)
    return repos


def _provider(repos, post, **config_overrides) -> OpenAICompatibleExtractionProvider:
    config = OpenAICompatibleExtractionConfig(
        base_url="http://model.invalid/v1",
        model="fixture-model",
        window_chars=config_overrides.pop("window_chars", 12_000),
        overlap_segments=config_overrides.pop("overlap_segments", 1),
        response_format=config_overrides.pop("response_format", "json_schema"),
        **config_overrides,
    )
    return OpenAICompatibleExtractionProvider(config=config, repositories=repos, post=post)


def _request(transcript: TranscriptArtifact | None = None) -> ExtractionRequest:
    return ExtractionRequest(transcript=transcript or _transcript(), parent_evidence=_parent())


def test_short_transcript_is_one_window_and_provider_receives_global_indexes(tmp_path: Path) -> None:
    repos = _setup(tmp_path)
    post = SequencePost([FakeResponse(_content([_candidate("The speaker may expand the trial.", [1])]))])
    provider = _provider(repos, post)
    assert provider.extract(_request()) == [_candidate("The speaker may expand the trial.", [1])]
    assert len(post.calls) == 1
    user_prompt = post.calls[0]["json"]["messages"][1]["content"]
    assert "[0] Welcome" in user_prompt and "[3] Growers" in user_prompt
    assert post.calls[0]["url"] == "http://model.invalid/v1/chat/completions"


def test_long_transcript_uses_overlapping_whole_segment_windows() -> None:
    transcript = _transcript([f"segment {index} " + "x" * 120 for index in range(10)])
    windows = build_transcript_windows(transcript, max_chars=500, overlap_segments=1)
    assert len(windows) > 1
    for left, right in zip(windows, windows[1:]):
        assert left.segment_indexes[-1] == right.segment_indexes[0]
    assert sorted({index for window in windows for index in window.segment_indexes}) == list(range(10))


def test_structured_output_records_usage_prompt_version_and_qualifiers(tmp_path: Path) -> None:
    repos = _setup(tmp_path)
    statement = "The speaker says approximately 20 hectares could be involved."
    post = SequencePost([FakeResponse(_content([_candidate(statement, [2])]), usage={"prompt_tokens": 50, "completion_tokens": 10, "total_tokens": 60})])
    provider = _provider(repos, post)
    assert provider.extract(_request())[0]["normalized_statement"] == statement
    report = provider.last_run_report
    assert report and report.prompt_version == PROMPT_VERSION
    assert report.total_tokens == 60 and report.candidates_after_validation == 1


@pytest.mark.parametrize(
    "candidate",
    [
        {**_candidate("Invented timestamp.", [1]), "start_seconds": 10},
        _candidate("Invented entity.", [1], entity_ids=["company-does-not-exist"]),
        {"normalized_statement": "Missing fields.", "segment_indexes": [1]},
        _candidate("Noncontiguous support.", [1, 3]),
    ],
)
def test_malformed_or_provider_owned_fields_fail_cleanly(tmp_path: Path, candidate: dict) -> None:
    repos = _setup(tmp_path)
    provider = _provider(repos, SequencePost([FakeResponse(_content([candidate]))]))
    with pytest.raises(ExtractionProviderError, match="all extraction windows failed"):
        provider.extract(_request())
    assert provider.last_run_report and provider.last_run_report.invalid_candidates == 1


def test_invalid_json_fails_without_semantic_repair(tmp_path: Path) -> None:
    provider = _provider(_setup(tmp_path), SequencePost([FakeResponse("not json")]))
    with pytest.raises(ExtractionProviderError, match="invalid JSON"):
        provider.extract(_request())


def test_single_markdown_json_fence_is_safely_unwrapped(tmp_path: Path) -> None:
    candidate = _candidate("Growers report flavor remains important.", [3])
    provider = _provider(_setup(tmp_path), SequencePost([FakeResponse(f"```json\n{_content([candidate])}\n```")]))
    assert provider.extract(_request()) == [candidate]


def test_overlap_duplicate_is_removed_but_distinct_nearby_claim_is_kept(tmp_path: Path) -> None:
    transcript = _transcript(["x" * 240, "Claim bridge " + "x" * 240, "Nearby claim " + "x" * 240])
    duplicate = _candidate("The speaker may expand.", [1])
    distinct = _candidate("The speaker says flavor matters.", [1])
    post = SequencePost([FakeResponse(_content([duplicate])), FakeResponse(_content([duplicate, distinct]))])
    provider = _provider(_setup(tmp_path), post, window_chars=550, overlap_segments=1)
    result = provider.extract(_request(transcript))
    assert result == [duplicate, distinct]
    assert provider.last_run_report and provider.last_run_report.duplicates_removed == 1


def test_same_words_at_materially_different_spans_are_not_deduped(tmp_path: Path) -> None:
    transcript = _transcript(["x" * 480, "middle " + "x" * 480, "x" * 480])
    first = _candidate("The source expects demand may rise.", [0])
    later = _candidate("The source expects demand may rise.", [2])
    post = SequencePost([FakeResponse(_content([first])), FakeResponse(_content([])), FakeResponse(_content([later]))])
    provider = _provider(_setup(tmp_path), post, window_chars=500, overlap_segments=0)
    assert provider.extract(_request(transcript)) == [first, later]


def test_no_intelligence_transcript_may_return_zero_candidates(tmp_path: Path) -> None:
    provider = _provider(_setup(tmp_path), SequencePost([FakeResponse(_content([]))]))
    assert provider.extract(_request(_transcript(["Hello and welcome.", "This message is sponsored."]))) == []


def test_timeout_is_explicit(tmp_path: Path) -> None:
    timeout = httpx.ReadTimeout("timed out")
    provider = _provider(_setup(tmp_path), SequencePost([timeout]))
    with pytest.raises(ExtractionProviderError, match="timed out"):
        provider.extract(_request())


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (FakeResponse("{}", finish_reason="length"), "truncated"),
        (FakeResponse(None, refusal="cannot comply"), "refused"),
    ],
)
def test_truncation_and_model_refusal_are_explicit(tmp_path: Path, response: FakeResponse, message: str) -> None:
    provider = _provider(_setup(tmp_path), SequencePost([response]))
    with pytest.raises(ExtractionProviderError, match=message):
        provider.extract(_request())


def test_one_failed_window_preserves_successful_window_and_reports_partial_state(tmp_path: Path) -> None:
    transcript = _transcript(["x" * 480, "y" * 480])
    candidate = _candidate("The source may expand.", [1])
    post = SequencePost([httpx.ReadTimeout("timed out"), FakeResponse(_content([candidate]))])
    provider = _provider(_setup(tmp_path), post, window_chars=500, overlap_segments=0)
    assert provider.extract(_request(transcript)) == [candidate]
    assert provider.last_run_report and len(provider.last_run_report.errors) == 1


def test_prompt_guards_against_strengthening_and_allows_zero_output(tmp_path: Path) -> None:
    transcript = _transcript([
        "We haven't announced any expansion plans.",
        "Some people have suggested demand may increase.",
    ])
    post = SequencePost([FakeResponse(_content([]))])
    provider = _provider(_setup(tmp_path), post)
    assert provider.extract(_request(transcript)) == []
    system = post.calls[0]["json"]["messages"][0]["content"]
    assert "does not support \"Company plans to expand.\"" in system
    assert "does not support \"Demand is increasing.\"" in system


def test_service_derives_timestamps_persists_untrusted_provenance_and_is_idempotent(tmp_path: Path) -> None:
    repos = _setup(tmp_path)
    transcript = _transcript()
    candidate = _candidate("The speaker may expand the trial depending on early results.", [1])
    post = SequencePost([FakeResponse(_content([candidate])), FakeResponse(_content([candidate]))])
    provider = _provider(repos, post)
    validator = main.get_validator("evidence.schema.json")
    service = TranscriptEvidenceExtractionService(
        repositories=repos,
        inbox_dir=tmp_path / "inbox",
        evidence_errors=lambda record: [error.message for error in validator.iter_errors(record)],
        provider=provider,
        today=lambda: date(2026, 8, 16),
    )
    first = service.run(transcript)
    second = service.run(transcript)
    assert len(first.accepted) == 1 and second.accepted == [] and len(second.duplicates) == 1
    proposal_path = next((tmp_path / "inbox" / "evidence").glob("*.json"))
    proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
    assert proposal["artifact_locator"] == {"start_seconds": 10.0, "end_seconds": 19.0}
    assert proposal["status"] == "draft" and proposal["review_state"] == "in_review"
    assert proposal["transcript_provenance"]["transcript_sha256"] == transcript.content_sha256()
    assert proposal["extraction_provenance"]["prompt_version"] == PROMPT_VERSION
    assert proposal["extraction_provenance"]["model"] == "fixture-model"
    assert repos.evidence.get(proposal["id"]) is None
    for folder in ("facts", "relationships", "assessments", "recommendations"):
        assert not list((tmp_path / "data" / folder).glob("*.json"))


def test_known_links_are_supplied_and_validated_without_special_company_logic(tmp_path: Path) -> None:
    repos = _setup(tmp_path)
    transcript = _transcript(["Fixture Company is working in Fixture Geography on Fixture Berry."])
    candidate = _candidate(
        "Fixture Company says it is working in Fixture Geography on Fixture Berry.",
        [0],
        entity_ids=["company-fixture"],
        geography_ids=["geography-fixture"],
        berry_ids=["berry-fixture"],
    )
    post = SequencePost([FakeResponse(_content([candidate]))])
    assert _provider(repos, post).extract(_request(transcript)) == [candidate]
    prompt = post.calls[0]["json"]["messages"][1]["content"]
    assert "company-fixture" in prompt and "geography-fixture" in prompt and "berry-fixture" in prompt
