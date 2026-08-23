"""Perplexity-routed extraction providers for atomic-ci-v1.

Two provider gateways route the *same* atomic-ci-v1 contract through Perplexity,
each subclassing `OpenAICompatibleExtractionProvider` and overriding only wire
transport (`_call`) and identity (`provenance`, `name`). Everything else --
transcript windowing, system/window prompt construction, candidate validation,
deduplication, the atomic-ci-v1 JSON schema, and the contiguous-segment
requirement -- is inherited unchanged, so neither provider can silently drift
from the qualified local-model contract.

- `PerplexityAgentExtractionProvider` (`provider = "perplexity-agent"`): the
  multi-provider Agent API path (OpenAI/Anthropic/Google/xAI/... via one key).
  This is the intended first external qualification path.
- `PerplexityRouterExtractionProvider` (`provider = "perplexity-router"`): the
  optional Router path for Perplexity-hosted open-weight models. Router is a
  private preview; ordinary API access does not imply Router access. Kept for
  operators who have preview access; not the default Perplexity route.

Both are closed-book for extraction: no web-search tool, no other tool, no
`models` fallback array. Each request names exactly one model, and a response
that identifies a different model fails closed (returned-model identity gate).
Structured output uses `json_schema` only; `json_object` fails closed before any
request. The local/LM Studio `OpenAICompatibleExtractionProvider` is unchanged.
"""

from __future__ import annotations

import os
import time
from typing import Any, Callable

import httpx

from app.services.ai_extraction import (
    EXTRACTION_VERSION,
    PROMPT_VERSION,
    ExtractionProviderError,
    ExtractionResponseError,
    OpenAICompatibleExtractionConfig,
    OpenAICompatibleExtractionProvider,
    TranscriptWindow,
    _extract_json,  # noqa: reused deliberately -- see module docstring
    _response_schema,  # noqa: reused deliberately -- see module docstring
)
from app.services.ai_gateway.credentials import PERPLEXITY_API_KEY_ENV, MissingCredentialError, sanitize
from app.services.ai_gateway.errors import GatewayError, GatewayMalformedResponseError, GatewayTimeoutError
from app.services.ai_gateway.perplexity_agent import (
    DEFAULT_PERPLEXITY_AGENT_BASE_URL,
    PerplexityAgentTransport,
    agent_compatible_response_format,
)
from app.services.ai_gateway.perplexity_chat import DEFAULT_PERPLEXITY_BASE_URL, PerplexityChatTransport
from app.services.transcript_evidence import ExtractionRequest


PERPLEXITY_ROUTER_BASE_URL_ENV = "BIOS_PERPLEXITY_BASE_URL"
PERPLEXITY_AGENT_BASE_URL_ENV = "BIOS_PERPLEXITY_AGENT_BASE_URL"
PERPLEXITY_MODEL_ENV = "BIOS_PERPLEXITY_MODEL"
PERPLEXITY_MAX_OUTPUT_TOKENS_ENV = "BIOS_PERPLEXITY_MAX_OUTPUT_TOKENS"
# A generous fixed safety cap for Agent extraction output. It is required by the
# Agent API for anthropic/* models and harmless for others. It is a truncation
# guard, not a generation knob: with temperature 0 and bounded candidate limits
# a large cap does not change deterministic output (and truncation fails closed).
DEFAULT_AGENT_MAX_OUTPUT_TOKENS = 8192


def _normalize_model_id(model_id: str) -> str:
    """Whitespace/case-normalized model identity for exact-match comparison."""

    return " ".join(model_id.strip().casefold().split())


def _require_json_schema(response_format: str, *, gateway_label: str) -> None:
    """Fail closed before any request if a non-`json_schema` format is set.

    Perplexity's Router and Agent structured output support `json_schema` (and
    `text`); `json_object` is rejected. The local provider is unaffected.
    """

    if response_format != "json_schema":
        raise ValueError(
            f"{gateway_label} does not support response_format '{response_format}'; "
            "only 'json_schema' is accepted (set BIOS_EXTRACT_RESPONSE_FORMAT=json_schema, "
            "which is the default)."
        )


def _guard_returned_model(*, requested: str, returned: str, api_key: str | None, gateway_label: str) -> None:
    """Fail closed when a response identifies a model other than the requested one."""

    if _normalize_model_id(returned) != _normalize_model_id(requested):
        raise ExtractionResponseError(
            sanitize(
                f"{gateway_label} returned model {returned!r} but {requested!r} was requested; "
                "refusing to extract from a substituted, unqualified model (no fallback is enabled).",
                api_key,
            )
        )


def _json_schema_response_format(max_candidates: int) -> dict[str, Any]:
    return {"type": "json_schema", "json_schema": _response_schema(max_candidates)}


def router_config_from_environment(**overrides: Any) -> OpenAICompatibleExtractionConfig:
    """Build the config for the Router extraction path from Perplexity env vars.

    `PERPLEXITY_API_KEY` is read directly -- never duplicated into
    `BIOS_EXTRACT_API_KEY` or any other name.
    """

    base_url = overrides.pop("base_url", None) or os.environ.get(PERPLEXITY_ROUTER_BASE_URL_ENV) or DEFAULT_PERPLEXITY_BASE_URL
    model = overrides.pop("model", None) or os.environ.get(PERPLEXITY_MODEL_ENV, "")
    return OpenAICompatibleExtractionConfig.from_environment(
        api_key_env=PERPLEXITY_API_KEY_ENV,
        base_url=base_url,
        model=model,
        **overrides,
    )


def agent_config_from_environment(**overrides: Any) -> OpenAICompatibleExtractionConfig:
    """Build the config for the Agent extraction path from Perplexity env vars."""

    base_url = overrides.pop("base_url", None) or os.environ.get(PERPLEXITY_AGENT_BASE_URL_ENV) or DEFAULT_PERPLEXITY_AGENT_BASE_URL
    model = overrides.pop("model", None) or os.environ.get(PERPLEXITY_MODEL_ENV, "")
    return OpenAICompatibleExtractionConfig.from_environment(
        api_key_env=PERPLEXITY_API_KEY_ENV,
        base_url=base_url,
        model=model,
        **overrides,
    )


# Backward-compatible alias: the original single-gateway name mapped to Router.
perplexity_config_from_environment = router_config_from_environment


def _resolve_agent_max_output_tokens() -> int:
    raw = os.environ.get(PERPLEXITY_MAX_OUTPUT_TOKENS_ENV)
    if raw in (None, ""):
        return DEFAULT_AGENT_MAX_OUTPUT_TOKENS
    value = int(raw)
    if value < 1:
        raise ValueError(f"{PERPLEXITY_MAX_OUTPUT_TOKENS_ENV} must be a positive integer")
    return value


class PerplexityRouterExtractionProvider(OpenAICompatibleExtractionProvider):
    """Extraction routed through Perplexity's Router API (open-weight models).

    Identity keeps gateway and routed model separate:
    `provenance["provider"] == "perplexity-router"`, `provenance["model"]` is the
    exact routed model id. Qualification binds to both, so switching the routed
    model invalidates any existing qualification. Router is a private preview.
    """

    gateway_label = "perplexity-router"

    def __init__(
        self,
        *,
        config: OpenAICompatibleExtractionConfig,
        repositories: Any,
        post: Callable[..., Any] = httpx.post,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not config.api_key:
            raise MissingCredentialError(
                f"{PERPLEXITY_API_KEY_ENV} is not set in this environment. "
                "Set it for this PowerShell session with:\n"
                f'  $env:{PERPLEXITY_API_KEY_ENV} = "<key>"'
            )
        super().__init__(config=config, repositories=repositories, post=post, clock=clock)
        _require_json_schema(self.config.response_format, gateway_label="Perplexity Router")
        self.provenance = {
            "provider": self.gateway_label,
            "model": config.model,
            "endpoint_family": "perplexity-router-chat-completions",
            "prompt_version": PROMPT_VERSION,
            "extraction_version": EXTRACTION_VERSION,
        }
        self.name = f"{self.gateway_label}:{config.model}:{PROMPT_VERSION}"
        self._transport = PerplexityChatTransport(
            api_key=config.api_key,
            base_url=config.base_url,
            timeout_seconds=config.timeout_seconds,
            post=post,
            clock=clock,
        )

    @property
    def endpoint(self) -> str:
        return self._transport.endpoint

    def _call(
        self, request: ExtractionRequest, window: TranscriptWindow, allowed: dict[str, dict[str, str]]
    ) -> dict[str, Any]:
        response_format = _json_schema_response_format(self.config.max_candidates_per_window)
        messages = [
            {"role": "system", "content": self._system_prompt()},
            {"role": "user", "content": self._window_prompt(request, window, allowed)},
        ]
        try:
            result = self._transport.send(
                model=self.config.model,
                messages=messages,
                response_format=response_format,
                temperature=self.config.temperature,
            )
        except GatewayTimeoutError as exc:
            raise ExtractionProviderError("model request timed out") from exc
        except GatewayError as exc:
            raise ExtractionProviderError(str(exc)) from exc
        except GatewayMalformedResponseError as exc:
            raise ExtractionResponseError(str(exc)) from exc

        if result.model:
            self.last_response_models.append(result.model)
            _guard_returned_model(
                requested=self.config.model, returned=result.model,
                api_key=self.config.api_key, gateway_label="Perplexity Router",
            )
        usage = {
            "prompt_tokens": result.usage.input_tokens,
            "completion_tokens": result.usage.output_tokens,
            "total_tokens": result.usage.total_tokens,
        }
        self._record_raw_output(window=window, content=result.content, returned_model=result.model, usage=usage)
        parsed = _extract_json(result.content)
        parsed["_usage"] = usage
        return parsed


# Backward-compatible alias for the original single-gateway class name.
PerplexityExtractionProvider = PerplexityRouterExtractionProvider


class PerplexityAgentExtractionProvider(OpenAICompatibleExtractionProvider):
    """Extraction routed through Perplexity's Agent API (multi-provider).

    Identity: `provenance["provider"] == "perplexity-agent"`, `provenance["model"]`
    is the exact routed model id (e.g. `openai/...`, `anthropic/...`,
    `google/...`). Qualification binds to both, so switching the routed model
    invalidates any existing qualification. This is the intended first external
    qualification path. Extraction is closed-book: no tools, no fallback array.
    """

    gateway_label = "perplexity-agent"

    def __init__(
        self,
        *,
        config: OpenAICompatibleExtractionConfig,
        repositories: Any,
        post: Callable[..., Any] = httpx.post,
        clock: Callable[[], float] = time.monotonic,
        max_output_tokens: int | None = None,
    ) -> None:
        if not config.api_key:
            raise MissingCredentialError(
                f"{PERPLEXITY_API_KEY_ENV} is not set in this environment. "
                "Set it for this PowerShell session with:\n"
                f'  $env:{PERPLEXITY_API_KEY_ENV} = "<key>"'
            )
        super().__init__(config=config, repositories=repositories, post=post, clock=clock)
        _require_json_schema(self.config.response_format, gateway_label="Perplexity Agent")
        self._max_output_tokens = max_output_tokens if max_output_tokens is not None else _resolve_agent_max_output_tokens()
        if self._max_output_tokens < 1:
            raise ValueError("max_output_tokens must be a positive integer")
        self.provenance = {
            "provider": self.gateway_label,
            "model": config.model,
            "endpoint_family": "perplexity-agent-responses",
            "prompt_version": PROMPT_VERSION,
            "extraction_version": EXTRACTION_VERSION,
        }
        self.name = f"{self.gateway_label}:{config.model}:{PROMPT_VERSION}"
        self._transport = PerplexityAgentTransport(
            api_key=config.api_key,
            base_url=config.base_url,
            timeout_seconds=config.timeout_seconds,
            post=post,
            clock=clock,
        )

    @property
    def endpoint(self) -> str:
        return self._transport.endpoint

    def _call(
        self, request: ExtractionRequest, window: TranscriptWindow, allowed: dict[str, dict[str, str]]
    ) -> dict[str, Any]:
        # The atomic-ci-v1 schema is unchanged; only the wire representation is
        # adapted for the Agent endpoint, which rejects constraint keywords like
        # `maxItems`. The per-window candidate cap is still enforced after the
        # response by the inherited extract_windows() logic.
        response_format = agent_compatible_response_format(
            _json_schema_response_format(self.config.max_candidates_per_window)
        )
        try:
            result = self._transport.complete(
                model=self.config.model,
                instructions=self._system_prompt(),
                input_text=self._window_prompt(request, window, allowed),
                response_format=response_format,
                max_output_tokens=self._max_output_tokens,
            )
        except GatewayTimeoutError as exc:
            raise ExtractionProviderError("model request timed out") from exc
        except GatewayError as exc:
            raise ExtractionProviderError(str(exc)) from exc
        except GatewayMalformedResponseError as exc:
            raise ExtractionResponseError(str(exc)) from exc

        if result.model:
            self.last_response_models.append(result.model)
            _guard_returned_model(
                requested=self.config.model, returned=result.model,
                api_key=self.config.api_key, gateway_label="Perplexity Agent",
            )
        usage = {
            "prompt_tokens": result.usage.input_tokens,
            "completion_tokens": result.usage.output_tokens,
            "total_tokens": result.usage.total_tokens,
        }
        self._record_raw_output(window=window, content=result.content, returned_model=result.model, usage=usage)
        parsed = _extract_json(result.content)
        parsed["_usage"] = usage
        return parsed
