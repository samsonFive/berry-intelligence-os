"""Tests for the Perplexity external-AI gateway: transport, extraction
provider, credential handling, and qualification-identity binding.

Mirrors the fixture patterns in tests/test_ai_extraction_provider.py so the
local-provider and Perplexity-provider tests read the same way; no real
network calls are made anywhere in this file.
"""

from __future__ import annotations

import dataclasses
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
from app.services.ai_gateway.credentials import PERPLEXITY_API_KEY_ENV, MissingCredentialError, sanitize
from app.services.ai_gateway.errors import (
    GatewayAuthError,
    GatewayError,
    GatewayMalformedResponseError,
    GatewayModelNotFoundError,
    GatewayRateLimitError,
    GatewayStructuredResponseIncompatibleError,
    GatewayTimeoutError,
    GatewayUnavailableError,
)
from app.services.ai_gateway.perplexity_agent import (
    DEFAULT_PERPLEXITY_AGENT_BASE_URL,
    DEFAULT_PERPLEXITY_MODELS_URL,
    PerplexityAgentTransport,
    agent_compatible_response_format,
    list_agent_models,
    strip_unsupported_schema_keywords,
)
from app.services.ai_gateway.perplexity_chat import DEFAULT_PERPLEXITY_BASE_URL, PerplexityChatTransport
from app.services.ai_gateway.perplexity_extraction import (
    PerplexityAgentExtractionProvider,
    PerplexityExtractionProvider,
    PerplexityRouterExtractionProvider,
    agent_config_from_environment,
    perplexity_config_from_environment,
)
from app.services.ai_gateway.perplexity_research import PerplexityResearchClient
from app.services.ai_gateway.perplexity_search import PerplexitySearchClient
from app.services.ai_gateway.results import NormalizedChatResponse, ResearchCitation, ResearchResponse, SearchResponse
from app.services.extraction_evaluation import probe_provider, public_configuration
from app.services.model_qualification import provider_qualification_configuration, qualification_configuration_fingerprint
from app.services.transcript_evidence import ExtractionRequest, TranscriptArtifact


PARENT_ID = "ev-perplexity-gateway-parent"
FAKE_KEY = "pplx-test-secret-key-abc123"
TEST_BASE_URL = "https://perplexity.invalid/router/v1"


# ---------------------------------------------------------------------------
# Shared fixtures / fakes
# ---------------------------------------------------------------------------


class FakeResponse:
    """A successful OpenAI-compatible envelope, usable by both the local
    provider (which calls .raise_for_status()) and the Perplexity transport
    (which checks .status_code directly)."""

    def __init__(self, content, *, usage=None, finish_reason="stop", model="sonar", request_id="req-1"):
        self.status_code = 200
        self._payload = {
            "id": request_id,
            "model": model,
            "choices": [{"message": {"content": content}, "finish_reason": finish_reason}],
            "usage": usage or {},
        }

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._payload

    @property
    def text(self) -> str:
        return json.dumps(self._payload)


class FakeJsonResponse:
    def __init__(self, status_code: int, *, error_message: str = "failure", body: dict | None = None):
        self.status_code = status_code
        self._body = body if body is not None else {"error": {"message": error_message}}

    def json(self):
        return self._body

    @property
    def text(self) -> str:
        return json.dumps(self._body)


class SequencePost:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls: list[dict] = []

    def __call__(self, url, **kwargs):
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
        "title": "Perplexity gateway fixture",
        "source_name": "Fixture Publisher",
        "source_url": "https://example.invalid/perplexity-fixture",
        "published_date": "2026-01-01",
        "captured_date": "2026-08-16",
        "summary": "Synthetic parent.",
        "submitted_by": "fixture",
        "source_id": "source-perplexity-gateway-fixture",
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
            "transcript_id": "transcript-perplexity-fixture",
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
    repos.sources.create({"id": "source-perplexity-gateway-fixture", "name": "Fixture Publisher"})
    repos.evidence.create(_parent())
    return repos


def _request() -> ExtractionRequest:
    return ExtractionRequest(transcript=_transcript(), parent_evidence=_parent())


def _provider(repos, post, *, model: str = "sonar", base_url: str = TEST_BASE_URL, **overrides) -> PerplexityExtractionProvider:
    config = perplexity_config_from_environment(base_url=base_url, model=model, **overrides)
    return PerplexityExtractionProvider(config=config, repositories=repos, post=post)


@pytest.fixture
def perplexity_key(monkeypatch):
    monkeypatch.setenv(PERPLEXITY_API_KEY_ENV, FAKE_KEY)
    return FAKE_KEY


# ---------------------------------------------------------------------------
# 1: missing Perplexity key
# ---------------------------------------------------------------------------


def test_missing_key_raises_missing_credential_error(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv(PERPLEXITY_API_KEY_ENV, raising=False)
    repos = _setup(tmp_path)
    config = perplexity_config_from_environment(base_url=TEST_BASE_URL, model="sonar")
    with pytest.raises(MissingCredentialError) as exc_info:
        PerplexityExtractionProvider(config=config, repositories=repos)
    message = str(exc_info.value)
    assert PERPLEXITY_API_KEY_ENV in message
    assert '$env:PERPLEXITY_API_KEY = "<key>"' in message


# ---------------------------------------------------------------------------
# 2 & 3: key sanitization, key never logged/exposed
# ---------------------------------------------------------------------------


def test_error_messages_never_contain_raw_api_key(perplexity_key: str) -> None:
    transport = PerplexityChatTransport(
        api_key=perplexity_key,
        base_url=TEST_BASE_URL,
        post=SequencePost([FakeJsonResponse(401, error_message=f"invalid bearer token {perplexity_key}")]),
    )
    with pytest.raises(GatewayAuthError) as exc_info:
        transport.send(model="sonar", messages=[{"role": "user", "content": "hi"}])
    assert perplexity_key not in str(exc_info.value)
    assert "[REDACTED]" in str(exc_info.value)


def test_sanitize_helper_redacts_all_given_secrets() -> None:
    assert sanitize("token=abc123 and also abc123", "abc123") == "token=[REDACTED] and also [REDACTED]"
    assert sanitize("no secret here", None) == "no secret here"


def test_key_never_appears_in_repr_or_public_configuration(perplexity_key: str, tmp_path: Path) -> None:
    repos = _setup(tmp_path)
    provider = _provider(repos, SequencePost([]))
    assert perplexity_key not in repr(provider.config)
    assert perplexity_key not in json.dumps(public_configuration(provider))
    assert perplexity_key not in json.dumps(provider.provenance)
    assert perplexity_key not in json.dumps(provider_qualification_configuration(provider))


# ---------------------------------------------------------------------------
# 4: correct endpoint construction
# ---------------------------------------------------------------------------


def test_default_perplexity_base_url_is_router_api() -> None:
    assert DEFAULT_PERPLEXITY_BASE_URL == "https://api.perplexity.ai/router/v1"


def test_endpoint_appends_chat_completions_path(perplexity_key: str, tmp_path: Path) -> None:
    repos = _setup(tmp_path)
    provider = _provider(repos, SequencePost([FakeResponse(_content([]))]))
    assert provider.endpoint == f"{TEST_BASE_URL}/chat/completions"


def test_invalid_base_url_rejected() -> None:
    with pytest.raises(ValueError):
        PerplexityChatTransport(api_key="x", base_url="not-a-url")


# ---------------------------------------------------------------------------
# 5 & 6: structured response success, JSON schema preserved
# ---------------------------------------------------------------------------


def test_extract_returns_candidates_on_structured_success(perplexity_key: str, tmp_path: Path) -> None:
    repos = _setup(tmp_path)
    post = SequencePost([FakeResponse(_content([_candidate("The speaker may expand the trial.", [1])]))])
    provider = _provider(repos, post)
    assert provider.extract(_request()) == [_candidate("The speaker may expand the trial.", [1])]


def test_request_body_includes_atomic_ci_json_schema(perplexity_key: str, tmp_path: Path) -> None:
    repos = _setup(tmp_path)
    post = SequencePost([FakeResponse(_content([]))])
    provider = _provider(repos, post)
    provider.extract(_request())
    body = post.calls[0]["json"]
    assert body["response_format"]["type"] == "json_schema"
    schema = body["response_format"]["json_schema"]
    assert schema["name"] == "atomic_ci_candidates"
    assert set(schema["schema"]["properties"]["candidates"]["items"]["properties"]) == {
        "normalized_statement",
        "segment_indexes",
        "entity_ids",
        "geography_ids",
        "berry_ids",
    }


# ---------------------------------------------------------------------------
# 7 & 25: extraction tools disabled, search/research cannot activate
# ---------------------------------------------------------------------------


# The Router/Gateway "Create Chat Completion" endpoint accepts only a defined
# subset of the OpenAI Chat Completions schema and rejects any unrecognized
# top-level field with a 400 (docs.perplexity.ai). `disable_search` is NOT in
# that set -- it belongs to the Sonar/search endpoints -- so it must never be
# sent to the gateway. Search stays off because no `tools` entry is sent.
_GATEWAY_HONORED_TOP_LEVEL_FIELDS = {
    "model", "messages", "stream", "stream_options", "max_completion_tokens",
    "max_tokens", "temperature", "top_p", "stop", "reasoning_effort",
    "service_tier", "response_format", "tools", "tool_choice",
    "parallel_tool_calls", "prompt_cache_key", "user", "safety_identifier",
    "metadata", "n", "logprobs", "store", "presence_penalty", "frequency_penalty",
}


def test_request_body_is_search_free_and_uses_only_gateway_supported_fields(perplexity_key: str, tmp_path: Path) -> None:
    repos = _setup(tmp_path)
    post = SequencePost([FakeResponse(_content([]))])
    provider = _provider(repos, post)
    provider.extract(_request())
    body = post.calls[0]["json"]
    # Regression guard: the gateway 400s on unrecognized top-level fields, so
    # `disable_search` (a Sonar-only field) must not be present.
    assert "disable_search" not in body
    assert "tools" not in body
    unsupported = set(body) - _GATEWAY_HONORED_TOP_LEVEL_FIELDS
    assert unsupported == set(), f"gateway would 400 on unsupported fields: {sorted(unsupported)}"


def test_transport_send_omits_disable_search_field(perplexity_key: str) -> None:
    post = SequencePost([FakeResponse(_content([]))])
    transport = PerplexityChatTransport(api_key=perplexity_key, base_url=TEST_BASE_URL, post=post)
    transport.send(model="anthropic/claude-haiku-4-5", messages=[{"role": "user", "content": "hi"}])
    assert "disable_search" not in post.calls[0]["json"]


def test_extraction_provider_has_no_search_or_research_capability() -> None:
    assert not hasattr(PerplexityExtractionProvider, "search")
    assert not hasattr(PerplexityExtractionProvider, "research")


# ---------------------------------------------------------------------------
# 8 & 9: exact model ID passed, gateway/model identities normalized
# ---------------------------------------------------------------------------


def test_request_body_uses_exact_configured_model(perplexity_key: str, tmp_path: Path) -> None:
    repos = _setup(tmp_path)
    # The gateway echoes back the model it ran; a realistic fixture returns the
    # requested model (see the returned-model identity gate below).
    post = SequencePost([FakeResponse(_content([]), model="anthropic/claude-haiku-4-5")])
    provider = _provider(repos, post, model="anthropic/claude-haiku-4-5")
    provider.extract(_request())
    assert post.calls[0]["json"]["model"] == "anthropic/claude-haiku-4-5"


def test_provenance_separates_gateway_from_routed_model(perplexity_key: str, tmp_path: Path) -> None:
    repos = _setup(tmp_path)
    provider = _provider(repos, SequencePost([]), model="anthropic/claude-haiku-4-5")
    assert provider.provenance["provider"] == "perplexity-router"
    assert provider.provenance["model"] == "anthropic/claude-haiku-4-5"
    assert provider.provenance["provider"] != provider.provenance["model"]


# ---------------------------------------------------------------------------
# 10: token usage normalized
# ---------------------------------------------------------------------------


def test_usage_normalized_into_provider_run_report(perplexity_key: str, tmp_path: Path) -> None:
    repos = _setup(tmp_path)
    post = SequencePost(
        [FakeResponse(_content([]), usage={"prompt_tokens": 42, "completion_tokens": 8, "total_tokens": 50})]
    )
    provider = _provider(repos, post)
    provider.extract(_request())
    report = provider.last_run_report
    assert report is not None
    assert report.input_tokens == 42
    assert report.output_tokens == 8
    assert report.total_tokens == 50


# ---------------------------------------------------------------------------
# 11: timeout normalization
# ---------------------------------------------------------------------------


def test_transport_timeout_raises_gateway_timeout_error(perplexity_key: str) -> None:
    transport = PerplexityChatTransport(
        api_key=perplexity_key, base_url=TEST_BASE_URL, post=SequencePost([httpx.TimeoutException("timed out")])
    )
    with pytest.raises(GatewayTimeoutError):
        transport.send(model="sonar", messages=[{"role": "user", "content": "hi"}])


def test_call_translates_timeout_for_extraction_pipeline(perplexity_key: str, tmp_path: Path) -> None:
    repos = _setup(tmp_path)
    post = SequencePost([httpx.TimeoutException("timed out")])
    provider = _provider(repos, post)
    with pytest.raises(ExtractionProviderError, match="timed out"):
        provider.extract(_request())


# ---------------------------------------------------------------------------
# 12-16: auth failure, rate limit, model unavailable, malformed response,
# structured-response incompatibility
# ---------------------------------------------------------------------------


def test_401_raises_gateway_auth_error(perplexity_key: str) -> None:
    transport = PerplexityChatTransport(api_key=perplexity_key, base_url=TEST_BASE_URL, post=SequencePost([FakeJsonResponse(401)]))
    with pytest.raises(GatewayAuthError):
        transport.send(model="sonar", messages=[{"role": "user", "content": "hi"}])


def test_429_raises_gateway_rate_limit_error(perplexity_key: str) -> None:
    transport = PerplexityChatTransport(api_key=perplexity_key, base_url=TEST_BASE_URL, post=SequencePost([FakeJsonResponse(429)]))
    with pytest.raises(GatewayRateLimitError):
        transport.send(model="sonar", messages=[{"role": "user", "content": "hi"}])


def test_404_raises_gateway_model_not_found_error(perplexity_key: str) -> None:
    transport = PerplexityChatTransport(api_key=perplexity_key, base_url=TEST_BASE_URL, post=SequencePost([FakeJsonResponse(404)]))
    with pytest.raises(GatewayModelNotFoundError):
        transport.send(model="does-not-exist", messages=[{"role": "user", "content": "hi"}])


def test_malformed_envelope_raises_gateway_malformed_response_error(perplexity_key: str) -> None:
    class WeirdResponse:
        status_code = 200
        text = "{}"

        def json(self):
            return {"unexpected": "shape"}

    transport = PerplexityChatTransport(api_key=perplexity_key, base_url=TEST_BASE_URL, post=SequencePost([WeirdResponse()]))
    with pytest.raises(GatewayMalformedResponseError):
        transport.send(model="sonar", messages=[{"role": "user", "content": "hi"}])


def test_truncated_response_raises_gateway_malformed_response_error(perplexity_key: str) -> None:
    transport = PerplexityChatTransport(
        api_key=perplexity_key, base_url=TEST_BASE_URL, post=SequencePost([FakeResponse("{", finish_reason="length")])
    )
    with pytest.raises(GatewayMalformedResponseError):
        transport.send(model="sonar", messages=[{"role": "user", "content": "hi"}])


def test_400_with_schema_marker_raises_structured_incompatible_error(perplexity_key: str) -> None:
    transport = PerplexityChatTransport(
        api_key=perplexity_key,
        base_url=TEST_BASE_URL,
        post=SequencePost([FakeJsonResponse(400, error_message="response_format.json_schema is not supported for this model")]),
    )
    with pytest.raises(GatewayStructuredResponseIncompatibleError):
        transport.send(
            model="sonar",
            messages=[{"role": "user", "content": "hi"}],
            response_format={"type": "json_schema", "json_schema": {}},
        )


def test_5xx_raises_gateway_unavailable_error(perplexity_key: str) -> None:
    transport = PerplexityChatTransport(api_key=perplexity_key, base_url=TEST_BASE_URL, post=SequencePost([FakeJsonResponse(503)]))
    with pytest.raises(GatewayUnavailableError):
        transport.send(model="sonar", messages=[{"role": "user", "content": "hi"}])


def test_unrecognized_status_raises_generic_gateway_error(perplexity_key: str) -> None:
    transport = PerplexityChatTransport(api_key=perplexity_key, base_url=TEST_BASE_URL, post=SequencePost([FakeJsonResponse(418)]))
    with pytest.raises(GatewayError):
        transport.send(model="sonar", messages=[{"role": "user", "content": "hi"}])


# ---------------------------------------------------------------------------
# 17 & 18: local LM Studio provider still works; existing extraction
# provider (probe/evaluation harness) remains compatible with Perplexity
# ---------------------------------------------------------------------------


def test_local_openai_compatible_provider_unaffected(tmp_path: Path) -> None:
    repos = _setup(tmp_path)
    config = OpenAICompatibleExtractionConfig(base_url="http://model.invalid/v1", model="fixture-model")
    post = SequencePost([FakeResponse(_content([_candidate("Local still works.", [1])]))])
    provider = OpenAICompatibleExtractionProvider(config=config, repositories=repos, post=post)
    result = provider.extract(_request())
    assert result[0]["normalized_statement"] == "Local still works."
    assert provider.provenance["provider"] == "openai-compatible"


def test_perplexity_provider_works_with_probe_provider(perplexity_key: str, tmp_path: Path) -> None:
    repos = _setup(tmp_path)
    post = SequencePost([FakeResponse(_content([]))])
    provider = _provider(repos, post)
    report = probe_provider(provider)
    assert report["compatible_response_received"] is True
    assert report["provider"] == "perplexity-router"


# ---------------------------------------------------------------------------
# 19 & 20: qualification binds gateway + exact model; model switch
# invalidates qualification
# ---------------------------------------------------------------------------


def test_qualification_configuration_includes_gateway_and_model(perplexity_key: str, tmp_path: Path) -> None:
    repos = _setup(tmp_path)
    provider = _provider(repos, SequencePost([]), model="anthropic/claude-haiku-4-5")
    configuration = provider_qualification_configuration(provider)
    assert configuration["provider"] == "perplexity-router"
    assert configuration["model"] == "anthropic/claude-haiku-4-5"
    assert "endpoint_identity" in configuration


def test_changing_routed_model_changes_configuration_fingerprint(perplexity_key: str, tmp_path: Path) -> None:
    repos = _setup(tmp_path)
    provider_a = _provider(repos, SequencePost([]), model="sonar")
    provider_b = _provider(repos, SequencePost([]), model="anthropic/claude-haiku-4-5")
    fingerprint_a = qualification_configuration_fingerprint(
        provider="perplexity", model="sonar", base_url=provider_a.config.base_url,
        prompt_version=PROMPT_VERSION, generation=public_configuration(provider_a),
    )
    fingerprint_b = qualification_configuration_fingerprint(
        provider="perplexity", model="anthropic/claude-haiku-4-5", base_url=provider_b.config.base_url,
        prompt_version=PROMPT_VERSION, generation=public_configuration(provider_b),
    )
    assert fingerprint_a != fingerprint_b


def test_changing_gateway_alone_changes_configuration_fingerprint(perplexity_key: str, tmp_path: Path) -> None:
    repos = _setup(tmp_path)
    provider = _provider(repos, SequencePost([]), model="sonar")
    fingerprint_perplexity = qualification_configuration_fingerprint(
        provider="perplexity", model="sonar", base_url=provider.config.base_url,
        prompt_version=PROMPT_VERSION, generation=public_configuration(provider),
    )
    fingerprint_openai_compatible = qualification_configuration_fingerprint(
        provider="openai-compatible", model="sonar", base_url=provider.config.base_url,
        prompt_version=PROMPT_VERSION, generation=public_configuration(provider),
    )
    assert fingerprint_perplexity != fingerprint_openai_compatible


# ---------------------------------------------------------------------------
# 21 & 22: atomic-ci-v1 unchanged; transcript windowing unchanged
# ---------------------------------------------------------------------------


def test_prompt_version_unchanged_for_perplexity(perplexity_key: str, tmp_path: Path) -> None:
    repos = _setup(tmp_path)
    provider = _provider(repos, SequencePost([]))
    assert provider.provenance["prompt_version"] == "atomic-ci-v1" == PROMPT_VERSION


def test_windowing_and_prompt_methods_are_inherited_unmodified() -> None:
    """Proves by identity (not just behavior) that Perplexity reuses the
    exact same windowing/prompt/validation/dedup code as the local
    provider -- nothing here was reimplemented or reinterpreted."""

    shared_methods = (
        "extract_windows",
        "_validate_candidate",
        "_is_duplicate",
        "_system_prompt",
        "_window_prompt",
        "_allowed_links",
    )
    for name in shared_methods:
        assert getattr(PerplexityExtractionProvider, name) is getattr(OpenAICompatibleExtractionProvider, name)


def test_windowing_behavior_identical_between_providers(perplexity_key: str, tmp_path: Path) -> None:
    repos = _setup(tmp_path)
    transcript = _transcript([f"segment {index} " + "x" * 120 for index in range(10)])
    local_windows = build_transcript_windows(transcript, max_chars=500, overlap_segments=1)
    provider = _provider(repos, SequencePost([]), window_chars=500, overlap_segments=1)
    perplexity_windows = build_transcript_windows(
        transcript, max_chars=provider.config.window_chars, overlap_segments=provider.config.overlap_segments
    )
    assert local_windows == perplexity_windows


# ---------------------------------------------------------------------------
# 23 & 24: no network calls during construction/status; no Perplexity calls
# unless explicitly selected
# ---------------------------------------------------------------------------


def test_provider_construction_makes_no_network_call(perplexity_key: str, tmp_path: Path) -> None:
    repos = _setup(tmp_path)
    post = SequencePost([])  # any call would raise IndexError
    provider = _provider(repos, post)
    assert post.calls == []
    assert provider.provenance["provider"] == "perplexity-router"


def test_cli_defaults_to_openai_compatible_when_provider_unspecified() -> None:
    import scripts.qualify_extraction_model as qualify_extraction_model

    args = qualify_extraction_model._parser().parse_args(["probe"])
    assert args.provider == "openai-compatible"


# ---------------------------------------------------------------------------
# 26 & 27: static output / review UI contain no secrets or credential data
# ---------------------------------------------------------------------------


def test_static_status_configuration_excludes_key(perplexity_key: str, tmp_path: Path) -> None:
    repos = _setup(tmp_path)
    provider = _provider(repos, SequencePost([]))
    configuration = provider_qualification_configuration(provider)
    assert perplexity_key not in json.dumps(configuration)
    assert perplexity_key not in json.dumps(public_configuration(provider))


def test_review_workbench_module_has_no_perplexity_or_credential_coupling() -> None:
    import app.services.review_workbench as review_workbench

    source = Path(review_workbench.__file__).read_text(encoding="utf-8")
    assert "PERPLEXITY_API_KEY" not in source
    assert "perplexity" not in source.casefold()


# ---------------------------------------------------------------------------
# 28: provider-native objects do not leak into domain code
# ---------------------------------------------------------------------------


def test_call_returns_plain_dict_not_response_object(perplexity_key: str, tmp_path: Path) -> None:
    repos = _setup(tmp_path)
    post = SequencePost([FakeResponse(_content([_candidate("Plain dict returned.", [1])]))])
    provider = _provider(repos, post)
    windows = build_transcript_windows(
        _transcript(), max_chars=provider.config.window_chars, overlap_segments=provider.config.overlap_segments
    )
    result = provider._call(_request(), windows[0], {"entity_ids": {}, "geography_ids": {}, "berry_ids": {}})
    assert isinstance(result, dict)
    assert set(result) == {"candidates", "_usage"}


def test_normalized_results_are_plain_dataclasses() -> None:
    assert dataclasses.is_dataclass(NormalizedChatResponse)
    assert dataclasses.is_dataclass(SearchResponse)
    assert dataclasses.is_dataclass(ResearchResponse)


# ---------------------------------------------------------------------------
# Bonus coverage: search() and research() seams (not extraction-critical,
# but real shipped code -- exercised the same way, with fakes only)
# ---------------------------------------------------------------------------


def test_search_returns_normalized_ranked_results() -> None:
    envelope = {
        "id": "search-1",
        "results": [
            {"title": "Blueberry acreage report", "url": "https://example.invalid/a", "snippet": "...", "date": "2026-01-01"},
            {"title": "No URL here", "snippet": "should be dropped"},
        ],
    }
    post = SequencePost([FakeJsonResponse(200, body=envelope)])
    client = PerplexitySearchClient(api_key=FAKE_KEY, post=post)
    result = client.search("blueberry acreage")
    assert result.provider == "perplexity"
    assert len(result.hits) == 1
    assert result.hits[0].url == "https://example.invalid/a"


def test_search_auth_failure_raises_gateway_auth_error() -> None:
    post = SequencePost([FakeJsonResponse(401)])
    client = PerplexitySearchClient(api_key=FAKE_KEY, post=post)
    with pytest.raises(GatewayAuthError):
        client.search("anything")


def test_search_rejects_empty_query() -> None:
    client = PerplexitySearchClient(api_key=FAKE_KEY, post=SequencePost([]))
    with pytest.raises(ValueError):
        client.search("   ")


def test_research_returns_content_and_citations() -> None:
    envelope = {
        "id": "research-1",
        "model": "openai/gpt-5.4-mini",
        "output": [
            {"type": "web_search_call", "results": [{"url": "https://example.invalid/source", "title": "Source"}]},
            {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "Summary of findings."}]},
        ],
        "usage": {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
    }
    post = SequencePost([FakeJsonResponse(200, body=envelope)])
    client = PerplexityResearchClient(api_key=FAKE_KEY, post=post)
    result = client.research("what changed?", model="openai/gpt-5.4-mini", web_enabled=True)
    assert result.content == "Summary of findings."
    assert result.citations == (ResearchCitation(url="https://example.invalid/source", title="Source"),)
    assert result.web_enabled is True


def test_research_web_disabled_sends_no_tools() -> None:
    envelope = {
        "id": "research-2",
        "model": "openai/gpt-5.4-mini",
        "output": [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "No web needed."}]}],
        "usage": {},
    }
    post = SequencePost([FakeJsonResponse(200, body=envelope)])
    client = PerplexityResearchClient(api_key=FAKE_KEY, post=post)
    client.research("anything", model="openai/gpt-5.4-mini", web_enabled=False)
    assert post.calls[0]["json"]["tools"] == []


def test_research_requires_explicit_model() -> None:
    client = PerplexityResearchClient(api_key=FAKE_KEY, post=SequencePost([]))
    with pytest.raises(ValueError):
        client.research("anything", model="")


# ---------------------------------------------------------------------------
# Hardening 1: Agent API research always sends a positive max_output_tokens
# (required for anthropic/* models; provider-neutral -- always sent).
# ---------------------------------------------------------------------------


def _research_ok_envelope() -> dict:
    return {
        "id": "research-x",
        "model": "anthropic/claude-haiku-4-5",
        "output": [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "ok"}]}],
        "usage": {},
    }


def test_research_sends_positive_max_output_tokens_for_anthropic_model() -> None:
    post = SequencePost([FakeJsonResponse(200, body=_research_ok_envelope())])
    client = PerplexityResearchClient(api_key=FAKE_KEY, post=post)
    client.research("what changed?", model="anthropic/claude-haiku-4-5")
    body = post.calls[0]["json"]
    assert isinstance(body["max_output_tokens"], int)
    assert body["max_output_tokens"] > 0


def test_research_forwards_custom_max_output_tokens_for_any_model() -> None:
    post = SequencePost([FakeJsonResponse(200, body=_research_ok_envelope())])
    client = PerplexityResearchClient(api_key=FAKE_KEY, post=post)
    client.research("q", model="openai/gpt-5.4-mini", max_output_tokens=256)
    assert post.calls[0]["json"]["max_output_tokens"] == 256


def test_research_rejects_nonpositive_max_output_tokens() -> None:
    client = PerplexityResearchClient(api_key=FAKE_KEY, post=SequencePost([]))
    with pytest.raises(ValueError):
        client.research("q", model="anthropic/claude-haiku-4-5", max_output_tokens=0)


# ---------------------------------------------------------------------------
# Hardening 2: Perplexity Router rejects json_object; fail closed before any
# HTTP request. The local/LM Studio provider is unaffected.
# ---------------------------------------------------------------------------


def test_perplexity_rejects_json_object_before_any_request(perplexity_key: str, tmp_path: Path) -> None:
    repos = _setup(tmp_path)
    post = SequencePost([])  # any HTTP attempt would raise IndexError
    with pytest.raises(ValueError, match="json_schema"):
        _provider(repos, post, response_format="json_object")
    assert post.calls == []


def test_local_provider_still_accepts_json_object(tmp_path: Path) -> None:
    repos = _setup(tmp_path)
    config = OpenAICompatibleExtractionConfig(
        base_url="http://model.invalid/v1", model="fixture-model", response_format="json_object"
    )
    post = SequencePost([FakeResponse(_content([_candidate("Local json_object still works.", [1])]))])
    provider = OpenAICompatibleExtractionProvider(config=config, repositories=repos, post=post)
    assert provider.extract(_request())[0]["normalized_statement"] == "Local json_object still works."


# ---------------------------------------------------------------------------
# Hardening 3: a returned model different from the requested model fails closed
# (no candidate extraction, no persistence) -- no automatic fallback.
# ---------------------------------------------------------------------------


def test_returned_model_mismatch_fails_closed(perplexity_key: str, tmp_path: Path) -> None:
    repos = _setup(tmp_path)
    # Requested haiku, but the response identifies sonnet -- a substitution.
    post = SequencePost([FakeResponse(_content([_candidate("Should never be extracted.", [1])]), model="anthropic/claude-sonnet-5")])
    provider = _provider(repos, post, model="anthropic/claude-haiku-4-5")
    with pytest.raises(ExtractionProviderError) as exc_info:
        provider.extract(_request())
    message = str(exc_info.value)
    assert "anthropic/claude-sonnet-5" in message and "anthropic/claude-haiku-4-5" in message
    assert perplexity_key not in message


def test_returned_model_matches_after_normalization(perplexity_key: str, tmp_path: Path) -> None:
    repos = _setup(tmp_path)
    # Same model, only whitespace/case differences -> must be treated as equal.
    post = SequencePost([FakeResponse(_content([_candidate("Extracted normally.", [1])]), model="  Anthropic/Claude-Haiku-4-5  ")])
    provider = _provider(repos, post, model="anthropic/claude-haiku-4-5")
    assert provider.extract(_request()) == [_candidate("Extracted normally.", [1])]


# ===========================================================================
# Perplexity AGENT API provider (multi-provider structured extraction).
# ===========================================================================

AGENT_TEST_URL = "https://perplexity.invalid/v1/agent"
AGENT_MODEL = "anthropic/claude-haiku-4-5"


def _agent_envelope(candidates, *, model=AGENT_MODEL, status="completed", usage=None):
    return {
        "id": "resp-agent-1",
        "model": model,
        "status": status,
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "status": "completed",
                "content": [{"type": "output_text", "text": _content(candidates)}],
            }
        ],
        "usage": usage or {},
    }


def _agent_response(candidates, *, model=AGENT_MODEL, status="completed", usage=None):
    return FakeJsonResponse(200, body=_agent_envelope(candidates, model=model, status=status, usage=usage))


def _agent_provider(repos, post, *, model=AGENT_MODEL, base_url=AGENT_TEST_URL, **overrides) -> PerplexityAgentExtractionProvider:
    config = agent_config_from_environment(base_url=base_url, model=model, **overrides)
    return PerplexityAgentExtractionProvider(config=config, repositories=repos, post=post)


def test_agent_default_base_url_and_endpoint_construction(perplexity_key: str, tmp_path: Path) -> None:
    assert DEFAULT_PERPLEXITY_AGENT_BASE_URL == "https://api.perplexity.ai/v1/agent"
    repos = _setup(tmp_path)
    provider = _agent_provider(repos, SequencePost([_agent_response([])]))
    assert provider.endpoint == AGENT_TEST_URL  # already ends with /agent, not doubled
    transport = PerplexityAgentTransport(api_key=perplexity_key, base_url="https://api.perplexity.ai/v1")
    assert transport.endpoint == "https://api.perplexity.ai/v1/agent"


def test_agent_request_shape_is_closed_book(perplexity_key: str, tmp_path: Path) -> None:
    repos = _setup(tmp_path)
    post = SequencePost([_agent_response([])])
    provider = _agent_provider(repos, post, model=AGENT_MODEL)
    provider.extract(_request())
    body = post.calls[0]["json"]
    assert body["model"] == AGENT_MODEL
    assert "instructions" in body and "input" in body
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["name"] == "atomic_ci_candidates"
    assert isinstance(body["max_output_tokens"], int) and body["max_output_tokens"] > 0
    # Closed-book: no tools, no fallback array, no preset.
    assert "tools" not in body
    assert "models" not in body
    assert "preset" not in body


def test_agent_structured_schema_properties_preserved(perplexity_key: str, tmp_path: Path) -> None:
    repos = _setup(tmp_path)
    post = SequencePost([_agent_response([])])
    provider = _agent_provider(repos, post)
    provider.extract(_request())
    schema = post.calls[0]["json"]["response_format"]["json_schema"]
    assert set(schema["schema"]["properties"]["candidates"]["items"]["properties"]) == {
        "normalized_statement", "segment_indexes", "entity_ids", "geography_ids", "berry_ids",
    }


def test_agent_extract_returns_candidates(perplexity_key: str, tmp_path: Path) -> None:
    repos = _setup(tmp_path)
    post = SequencePost([_agent_response([_candidate("The speaker may expand the trial.", [1])])])
    provider = _agent_provider(repos, post)
    assert provider.extract(_request()) == [_candidate("The speaker may expand the trial.", [1])]


def test_agent_provenance_is_perplexity_agent_with_exact_model(perplexity_key: str, tmp_path: Path) -> None:
    repos = _setup(tmp_path)
    provider = _agent_provider(repos, SequencePost([]), model=AGENT_MODEL)
    assert provider.provenance["provider"] == "perplexity-agent"
    assert provider.provenance["model"] == AGENT_MODEL
    assert provider.name == f"perplexity-agent:{AGENT_MODEL}:{PROMPT_VERSION}"


def test_agent_usage_normalized_into_report(perplexity_key: str, tmp_path: Path) -> None:
    repos = _setup(tmp_path)
    post = SequencePost([_agent_response([], usage={"input_tokens": 30, "output_tokens": 6, "total_tokens": 36})])
    provider = _agent_provider(repos, post)
    provider.extract(_request())
    report = provider.last_run_report
    assert (report.input_tokens, report.output_tokens, report.total_tokens) == (30, 6, 36)


def test_agent_missing_key_fails_before_network(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv(PERPLEXITY_API_KEY_ENV, raising=False)
    repos = _setup(tmp_path)
    config = agent_config_from_environment(base_url=AGENT_TEST_URL, model=AGENT_MODEL)
    with pytest.raises(MissingCredentialError):
        PerplexityAgentExtractionProvider(config=config, repositories=repos)


def test_agent_rejects_json_object_before_any_request(perplexity_key: str, tmp_path: Path) -> None:
    repos = _setup(tmp_path)
    post = SequencePost([])
    with pytest.raises(ValueError, match="json_schema"):
        _agent_provider(repos, post, response_format="json_object")
    assert post.calls == []


def test_agent_returned_model_mismatch_fails_closed(perplexity_key: str, tmp_path: Path) -> None:
    repos = _setup(tmp_path)
    post = SequencePost([_agent_response([_candidate("Should not extract.", [1])], model="anthropic/claude-sonnet-5")])
    provider = _agent_provider(repos, post, model=AGENT_MODEL)
    with pytest.raises(ExtractionProviderError) as exc_info:
        provider.extract(_request())
    message = str(exc_info.value)
    assert "anthropic/claude-sonnet-5" in message and AGENT_MODEL in message
    assert perplexity_key not in message


def test_agent_transport_error_mapping(perplexity_key: str) -> None:
    def transport(response):
        return PerplexityAgentTransport(api_key=perplexity_key, base_url=AGENT_TEST_URL, post=SequencePost([response]))

    with pytest.raises(GatewayAuthError):
        transport(FakeJsonResponse(401)).complete(model=AGENT_MODEL, instructions="s", input_text="u", response_format=None, max_output_tokens=64)
    with pytest.raises(GatewayRateLimitError):
        transport(FakeJsonResponse(429)).complete(model=AGENT_MODEL, instructions="s", input_text="u", response_format=None, max_output_tokens=64)
    with pytest.raises(GatewayModelNotFoundError):
        transport(FakeJsonResponse(404)).complete(model="does/not-exist", instructions="s", input_text="u", response_format=None, max_output_tokens=64)


def test_agent_timeout_maps_to_extraction_error(perplexity_key: str, tmp_path: Path) -> None:
    repos = _setup(tmp_path)
    post = SequencePost([httpx.TimeoutException("timed out")])
    provider = _agent_provider(repos, post)
    with pytest.raises(ExtractionProviderError, match="timed out"):
        provider.extract(_request())


def test_agent_non_completed_status_is_malformed(perplexity_key: str) -> None:
    transport = PerplexityAgentTransport(api_key=perplexity_key, base_url=AGENT_TEST_URL, post=SequencePost([_agent_response([], status="failed")]))
    with pytest.raises(GatewayMalformedResponseError):
        transport.complete(model=AGENT_MODEL, instructions="s", input_text="u", response_format=None, max_output_tokens=64)


def test_agent_error_message_sanitizes_key(perplexity_key: str) -> None:
    transport = PerplexityAgentTransport(
        api_key=perplexity_key, base_url=AGENT_TEST_URL,
        post=SequencePost([FakeJsonResponse(401, error_message=f"bad token {perplexity_key}")]),
    )
    with pytest.raises(GatewayAuthError) as exc_info:
        transport.complete(model=AGENT_MODEL, instructions="s", input_text="u", response_format=None, max_output_tokens=64)
    assert perplexity_key not in str(exc_info.value) and "[REDACTED]" in str(exc_info.value)


def test_agent_changing_model_changes_fingerprint(perplexity_key: str, tmp_path: Path) -> None:
    repos = _setup(tmp_path)
    a = _agent_provider(repos, SequencePost([]), model="anthropic/claude-haiku-4-5")
    b = _agent_provider(repos, SequencePost([]), model="openai/gpt-5.6-sol")
    fp_a = qualification_configuration_fingerprint(
        provider="perplexity-agent", model=a.config.model, base_url=a.config.base_url,
        prompt_version=PROMPT_VERSION, generation=public_configuration(a),
    )
    fp_b = qualification_configuration_fingerprint(
        provider="perplexity-agent", model=b.config.model, base_url=b.config.base_url,
        prompt_version=PROMPT_VERSION, generation=public_configuration(b),
    )
    assert fp_a != fp_b


def test_agent_provider_has_no_search_or_research_capability() -> None:
    assert not hasattr(PerplexityAgentExtractionProvider, "search")
    assert not hasattr(PerplexityAgentExtractionProvider, "research")


def test_agent_and_router_are_separate_gateways(perplexity_key: str, tmp_path: Path) -> None:
    repos = _setup(tmp_path)
    agent = _agent_provider(repos, SequencePost([]))
    router = _provider(repos, SequencePost([]), model=AGENT_MODEL)
    assert agent.provenance["provider"] == "perplexity-agent"
    assert router.provenance["provider"] == "perplexity-router"
    assert agent.endpoint.endswith("/agent")
    assert router.endpoint.endswith("/chat/completions")
    assert PerplexityExtractionProvider is PerplexityRouterExtractionProvider


def test_router_403_classified_as_auth_signals_private_preview(perplexity_key: str) -> None:
    # A Router 403 typically means the account lacks private-preview access,
    # not that the API key is invalid. It maps to a gateway auth error whose
    # (sanitized) message preserves the 403 so operators can tell them apart.
    transport = PerplexityChatTransport(api_key=perplexity_key, base_url=TEST_BASE_URL, post=SequencePost([FakeJsonResponse(403)]))
    with pytest.raises(GatewayAuthError) as exc_info:
        transport.send(model="perplexity/sonar", messages=[{"role": "user", "content": "hi"}])
    assert "403" in str(exc_info.value)
    assert perplexity_key not in str(exc_info.value)


# ---------------------------------------------------------------------------
# Model discovery: GET /v1/models normalized, no persistence, no auth required.
# ---------------------------------------------------------------------------


def test_list_agent_models_normalizes_and_sorts_without_auth() -> None:
    captured = {}

    def fake_get(url, **kwargs):
        captured["url"] = url
        captured["headers"] = kwargs.get("headers", {})
        return FakeJsonResponse(200, body={
            "object": "list",
            "data": [
                {"id": "openai/gpt-5.6-sol", "object": "model", "created": 0, "owned_by": "openai"},
                {"id": "anthropic/claude-haiku-4-5", "object": "model", "created": 0, "owned_by": "anthropic"},
                {"id": "", "object": "model", "owned_by": "broken"},
            ],
        })

    models = list_agent_models(get=fake_get)
    assert captured["url"] == DEFAULT_PERPLEXITY_MODELS_URL
    assert "Authorization" not in captured["headers"]  # no key supplied -> no auth header
    assert [m["id"] for m in models] == ["anthropic/claude-haiku-4-5", "openai/gpt-5.6-sol"]
    assert models[0] == {"id": "anthropic/claude-haiku-4-5", "owned_by": "anthropic"}


def test_list_agent_models_sends_key_when_supplied() -> None:
    captured = {}

    def fake_get(url, **kwargs):
        captured["headers"] = kwargs.get("headers", {})
        return FakeJsonResponse(200, body={"object": "list", "data": []})

    list_agent_models(api_key=FAKE_KEY, get=fake_get)
    assert captured["headers"].get("Authorization") == f"Bearer {FAKE_KEY}"


def test_ai_models_cli_defaults_to_perplexity_agent() -> None:
    import scripts.ai_models as ai_models

    args = ai_models._parser().parse_args([])
    assert args.provider == "perplexity-agent"


# ---------------------------------------------------------------------------
# Live-contract regression: the Agent strict json_schema validator rejects
# constraint keywords (maxItems/minItems). Reproduces the real 400 and proves
# the schema is now Agent-compatible while atomic-ci-v1 stays unchanged.
# ---------------------------------------------------------------------------


def test_strip_unsupported_schema_keywords_removes_constraints_keeps_structure() -> None:
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["candidates"],
        "properties": {
            "candidates": {
                "type": "array",
                "maxItems": 12,
                "minItems": 1,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["x"],
                    "properties": {"x": {"type": "string", "maxLength": 5, "pattern": "^a"}},
                },
            }
        },
    }
    cleaned = strip_unsupported_schema_keywords(schema)
    blob = json.dumps(cleaned)
    for unsupported in ("maxItems", "minItems", "maxLength", "pattern"):
        assert unsupported not in blob
    # Structure preserved.
    assert cleaned["additionalProperties"] is False
    assert cleaned["required"] == ["candidates"]
    assert cleaned["properties"]["candidates"]["items"]["additionalProperties"] is False
    assert cleaned["properties"]["candidates"]["items"]["required"] == ["x"]
    assert cleaned["properties"]["candidates"]["items"]["properties"]["x"]["type"] == "string"


def test_agent_request_schema_omits_maxitems_and_keeps_atomic_ci_shape(perplexity_key: str, tmp_path: Path) -> None:
    repos = _setup(tmp_path)
    post = SequencePost([_agent_response([])])
    provider = _agent_provider(repos, post)
    provider.extract(_request())
    json_schema = post.calls[0]["json"]["response_format"]["json_schema"]
    schema = json_schema["schema"]
    # The demonstrated 400 cause -- maxItems -- must not be sent to the Agent API.
    assert "maxItems" not in json.dumps(schema)
    # atomic-ci-v1 candidate shape and strictness are preserved.
    assert json_schema["name"] == "atomic_ci_candidates"
    assert json_schema["strict"] is True
    item = schema["properties"]["candidates"]["items"]
    assert item["additionalProperties"] is False
    assert set(item["properties"]) == {
        "normalized_statement", "segment_indexes", "entity_ids", "geography_ids", "berry_ids",
    }
    assert sorted(item["required"]) == sorted(item["properties"])


def test_shared_response_schema_unchanged_router_and_local_still_emit_maxitems() -> None:
    # atomic-ci-v1 itself is untouched: only the Agent wire representation is
    # adapted, so the shared schema (used by local + Router) still carries the cap.
    from app.services.ai_extraction import _response_schema

    assert "maxItems" in json.dumps(_response_schema(12))
    # agent_compatible_response_format leaves a non-dict / schema-less format alone.
    assert agent_compatible_response_format({"type": "json_object"}) == {"type": "json_object"}


def test_agent_still_enforces_candidate_cap_after_response(perplexity_key: str, tmp_path: Path) -> None:
    # With maxItems no longer in the wire schema, the per-window candidate cap is
    # still enforced client-side: a response exceeding it fails closed.
    repos = _setup(tmp_path)
    too_many = [_candidate(f"Synthetic claim {i}.", [1]) for i in range(3)]
    post = SequencePost([_agent_response(too_many)])
    provider = _agent_provider(repos, post, max_candidates_per_window=2)
    with pytest.raises(ExtractionProviderError):
        provider.extract(_request())


def test_agent_400_validation_detail_is_retained_and_sanitized(perplexity_key: str) -> None:
    body = {"error": {
        "message": "invalid request",
        "param": "response_format.json_schema.schema.properties.candidates.maxItems",
        "type": "invalid_request_error",
    }}
    transport = PerplexityAgentTransport(
        api_key=perplexity_key, base_url=AGENT_TEST_URL,
        post=SequencePost([FakeJsonResponse(400, body=body)]),
    )
    with pytest.raises(GatewayStructuredResponseIncompatibleError) as exc_info:
        transport.complete(model=AGENT_MODEL, instructions="s", input_text="u",
                           response_format={"type": "json_schema", "json_schema": {"name": "n", "schema": {}}},
                           max_output_tokens=64)
    message = str(exc_info.value)
    assert "maxItems" in message and "param=" in message
    assert perplexity_key not in message
