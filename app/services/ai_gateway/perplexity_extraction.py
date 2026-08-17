"""Perplexity-routed extraction provider for atomic-ci-v1.

Subclasses `OpenAICompatibleExtractionProvider` and overrides only wire
transport (`_call`) and identity (`provenance`, `name`). Everything else --
transcript windowing, system/window prompt construction, candidate
validation, deduplication, the atomic-ci-v1 JSON schema, and the
contiguous-segment requirement -- is inherited unchanged, so this provider
cannot silently drift from the qualified local-model contract. No prompt,
schema, or windowing behavior is reinterpreted for this provider.

Web search is never enabled here: every call sets `disable_search=True` on
the underlying transport, and no `tools` parameter is ever sent. Extraction
never grants a Perplexity-routed model network access.
"""

from __future__ import annotations

import os
import time
from typing import Any, Callable

import httpx

from app.services.ai_extraction import (
    PROMPT_VERSION,
    ExtractionProviderError,
    ExtractionResponseError,
    OpenAICompatibleExtractionConfig,
    OpenAICompatibleExtractionProvider,
    TranscriptWindow,
    _extract_json,  # noqa: reused deliberately -- see module docstring
    _response_schema,  # noqa: reused deliberately -- see module docstring
)
from app.services.ai_gateway.credentials import PERPLEXITY_API_KEY_ENV, MissingCredentialError
from app.services.ai_gateway.errors import GatewayError, GatewayMalformedResponseError, GatewayTimeoutError
from app.services.ai_gateway.perplexity_chat import DEFAULT_PERPLEXITY_BASE_URL, PerplexityChatTransport
from app.services.transcript_evidence import ExtractionRequest


PERPLEXITY_BASE_URL_ENV = "BIOS_PERPLEXITY_BASE_URL"
PERPLEXITY_MODEL_ENV = "BIOS_PERPLEXITY_MODEL"


def perplexity_config_from_environment(**overrides: Any) -> OpenAICompatibleExtractionConfig:
    """Builds the same config shape the local provider uses, sourced from
    Perplexity-specific env vars. `PERPLEXITY_API_KEY` is read directly --
    it is never duplicated into `BIOS_EXTRACT_API_KEY` or any other name."""

    base_url = overrides.pop("base_url", None) or os.environ.get(PERPLEXITY_BASE_URL_ENV) or DEFAULT_PERPLEXITY_BASE_URL
    model = overrides.pop("model", None) or os.environ.get(PERPLEXITY_MODEL_ENV, "")
    return OpenAICompatibleExtractionConfig.from_environment(
        api_key_env=PERPLEXITY_API_KEY_ENV,
        base_url=base_url,
        model=model,
        **overrides,
    )


class PerplexityExtractionProvider(OpenAICompatibleExtractionProvider):
    """Extraction provider routed through Perplexity's Router API.

    Identity keeps gateway and routed model separate:
    `provenance["provider"] == "perplexity"`, `provenance["model"]` is the
    exact routed model id. Qualification binds to both, so switching the
    routed model behind Perplexity invalidates any existing qualification --
    the same rule that already applies to the local provider.
    """

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
        self.provenance = {
            "provider": "perplexity",
            "model": config.model,
            "prompt_version": PROMPT_VERSION,
        }
        self.name = f"perplexity:{config.model}:{PROMPT_VERSION}"
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
        if self.config.response_format == "json_schema":
            response_format: dict[str, Any] = {
                "type": "json_schema",
                "json_schema": _response_schema(self.config.max_candidates_per_window),
            }
        else:
            response_format = {"type": "json_object"}
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
                disable_search=True,
            )
        except GatewayTimeoutError as exc:
            raise ExtractionProviderError("model request timed out") from exc
        except GatewayError as exc:
            raise ExtractionProviderError(str(exc)) from exc
        except GatewayMalformedResponseError as exc:
            raise ExtractionResponseError(str(exc)) from exc

        if result.model:
            self.last_response_models.append(result.model)
        parsed = _extract_json(result.content)
        parsed["_usage"] = {
            "prompt_tokens": result.usage.input_tokens,
            "completion_tokens": result.usage.output_tokens,
            "total_tokens": result.usage.total_tokens,
        }
        return parsed
