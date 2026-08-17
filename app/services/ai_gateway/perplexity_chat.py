"""Perplexity Router API transport for structured, non-search chat calls.

This is the sole place that knows Perplexity's wire format for structured
inference. It builds the request, disables web search by default (this
project's extraction use never enables it), parses the response envelope,
and maps every failure onto the generic `app.services.ai_gateway.errors`
taxonomy. Callers receive a `NormalizedChatResponse` or a `GatewayError`/
`GatewayMalformedResponseError` -- never a raw `httpx.Response` or a
Perplexity-shaped envelope.

Verified against Perplexity's own documentation (docs.perplexity.ai) as of
2026-08-16: the Router API at `https://api.perplexity.ai/router/v1` serves
an OpenAI-Chat-Completions-compatible `/chat/completions` endpoint distinct
from the legacy Sonar chat-completions path (which Perplexity has announced
sunsetting 2026-09-27), and accepts `disable_search` and a JSON-schema
`response_format`.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import time
from typing import Any, Callable
from urllib.parse import urlsplit

import httpx

from app.services.ai_gateway.credentials import sanitize
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
from app.services.ai_gateway.results import NormalizedChatResponse, NormalizedUsage


DEFAULT_PERPLEXITY_BASE_URL = "https://api.perplexity.ai/router/v1"
_STRUCTURED_FORMAT_MARKERS = ("response_format", "json_schema", "schema")


def _validate_base_url(base_url: str) -> str:
    parsed = urlsplit(base_url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError(f"gateway base URL must be an http(s) URL with a host: {base_url!r}")
    return base_url.strip().rstrip("/")


@dataclass
class PerplexityChatTransport:
    """Low-level, provider-specific transport. Not exposed to domain code --
    only `PerplexityExtractionProvider` (and future Perplexity-backed
    capabilities) call this directly."""

    api_key: str
    base_url: str = DEFAULT_PERPLEXITY_BASE_URL
    timeout_seconds: float = 120.0
    post: Callable[..., Any] = httpx.post
    clock: Callable[[], float] = time.monotonic

    def __post_init__(self) -> None:
        self.base_url = _validate_base_url(self.base_url)

    @property
    def endpoint(self) -> str:
        base = self.base_url.rstrip("/")
        return base if base.endswith("/chat/completions") else f"{base}/chat/completions"

    def send(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        response_format: dict[str, Any] | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        disable_search: bool = True,
    ) -> NormalizedChatResponse:
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "disable_search": disable_search,
        }
        if response_format is not None:
            body["response_format"] = response_format
        if max_tokens is not None:
            body["max_tokens"] = max_tokens

        started = self.clock()
        try:
            response = self.post(self.endpoint, headers=headers, json=body, timeout=self.timeout_seconds)
        except httpx.TimeoutException as exc:
            raise GatewayTimeoutError(sanitize("perplexity request timed out", self.api_key)) from exc
        except httpx.HTTPError as exc:
            raise GatewayUnavailableError(
                sanitize(f"perplexity transport failure ({type(exc).__name__})", self.api_key)
            ) from exc
        latency = round(self.clock() - started, 3)

        if response.status_code >= 400:
            self._raise_for_status(response)

        try:
            envelope = response.json()
        except ValueError as exc:
            raise GatewayMalformedResponseError(
                sanitize(f"could not parse perplexity response as JSON: {exc}", self.api_key)
            ) from exc
        try:
            choice = envelope["choices"][0]
            message = choice["message"]
            content = message["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise GatewayMalformedResponseError(
                sanitize(f"malformed perplexity response envelope: missing {exc}", self.api_key)
            ) from exc
        if not isinstance(content, str):
            raise GatewayMalformedResponseError("perplexity response content must be text")
        if choice.get("finish_reason") == "length":
            raise GatewayMalformedResponseError("perplexity response was truncated")

        usage_raw = envelope.get("usage")
        usage_raw = usage_raw if isinstance(usage_raw, dict) else {}
        usage = NormalizedUsage(
            input_tokens=usage_raw.get("prompt_tokens"),
            output_tokens=usage_raw.get("completion_tokens"),
            total_tokens=usage_raw.get("total_tokens"),
        )
        returned_model = envelope.get("model")
        return NormalizedChatResponse(
            content=content,
            provider="perplexity",
            model=returned_model.strip() if isinstance(returned_model, str) and returned_model.strip() else None,
            usage=usage,
            latency_seconds=latency,
            request_id=envelope.get("id") if isinstance(envelope.get("id"), str) else None,
        )

    def _raise_for_status(self, response: Any) -> None:
        status = response.status_code
        detail = self._error_detail(response)
        message = sanitize(f"perplexity HTTP failure ({status}): {detail}", self.api_key)
        if status in (401, 403):
            raise GatewayAuthError(message)
        if status == 429:
            raise GatewayRateLimitError(message)
        if status == 404:
            raise GatewayModelNotFoundError(message)
        if status in (400, 422) and any(marker in detail.casefold() for marker in _STRUCTURED_FORMAT_MARKERS):
            raise GatewayStructuredResponseIncompatibleError(message)
        if status >= 500:
            raise GatewayUnavailableError(message)
        raise GatewayError(message)

    @staticmethod
    def _error_detail(response: Any) -> str:
        try:
            payload = response.json()
        except ValueError:
            return (response.text or "")[:300]
        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict):
                return str(error.get("message") or error)
            if isinstance(error, str):
                return error
            message = payload.get("message")
            if isinstance(message, str):
                return message
        return json.dumps(payload)[:300]
