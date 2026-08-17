"""Perplexity Agent API transport: multi-provider structured inference.

The Agent API is Perplexity's multi-provider gateway: one `PERPLEXITY_API_KEY`
selects an exact routed model from OpenAI, Anthropic, Google, xAI, Perplexity,
and others. This module is the sole place that knows the Agent wire format for
structured, tool-free inference. It builds the request, normalizes the
OpenAI-Responses-shaped envelope into a `NormalizedChatResponse`, and maps every
failure onto the generic `app.services.ai_gateway.errors` taxonomy. Callers
receive a `NormalizedChatResponse` or a gateway error -- never a raw
`httpx.Response` or a Perplexity-shaped envelope. It also exposes a read-only
model-discovery helper over `GET /v1/models`.

Verified against docs.perplexity.ai (2026-08-17):

- Canonical endpoint `POST https://api.perplexity.ai/v1/agent`; the OpenAI
  Responses-compatible alias `POST /v1/responses` is accepted for SDK use. We
  post to the canonical `/v1/agent` since this is a hand-rolled transport.
- Request (for closed-book extraction): `{model, instructions, input,
  response_format:{type:"json_schema", json_schema:{name, strict, schema}},
  max_output_tokens}`. Exactly one `model`; NO `models` fallback array, NO
  `preset`, and NO `tools` -- so the model cannot search or use any tool.
- `max_output_tokens` is a shared optional Agent parameter but is REQUIRED for
  `anthropic/*` models (a request without it returns HTTP 400), so it is always
  sent as a positive integer.
- Response: `{id, model, status:"completed", output:[... a message item whose
  content holds output_text blocks ...], usage:{input_tokens, output_tokens,
  total_tokens}}`.
- `GET /v1/models` needs no auth and returns `{object:"list", data:[{id,
  object, created, owned_by}]}` with ids in `provider/model-name` form.
"""

from __future__ import annotations

from dataclasses import dataclass, field
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


DEFAULT_PERPLEXITY_AGENT_BASE_URL = "https://api.perplexity.ai/v1/agent"
DEFAULT_PERPLEXITY_MODELS_URL = "https://api.perplexity.ai/v1/models"
_STRUCTURED_FORMAT_MARKERS = ("response_format", "json_schema", "schema")


def _validate_base_url(base_url: str) -> str:
    parsed = urlsplit(base_url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError(f"gateway base URL must be an http(s) URL with a host: {base_url!r}")
    return base_url.strip().rstrip("/")


def agent_auth_headers(api_key: str) -> dict[str, str]:
    return {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}


def _error_detail(response: Any) -> str:
    try:
        payload = response.json()
    except ValueError:
        return (getattr(response, "text", "") or "")[:300]
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


def raise_for_agent_status(response: Any, api_key: str) -> None:
    """Map an Agent/Responses HTTP error onto the generic gateway taxonomy."""

    status = response.status_code
    detail = _error_detail(response)
    message = sanitize(f"perplexity agent HTTP failure ({status}): {detail}", api_key)
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


def extract_output_text(output: list[Any]) -> str | None:
    """Concatenate the output_text blocks of the response's message item."""

    for item in output:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        texts = [
            block.get("text")
            for block in content
            if isinstance(block, dict) and block.get("type") == "output_text" and isinstance(block.get("text"), str)
        ]
        if texts:
            return "\n".join(texts)
    return None


def normalize_responses_usage(usage_raw: Any) -> NormalizedUsage:
    usage_raw = usage_raw if isinstance(usage_raw, dict) else {}
    input_tokens = usage_raw.get("input_tokens")
    output_tokens = usage_raw.get("output_tokens")
    total_tokens = usage_raw.get("total_tokens")
    if total_tokens is None and isinstance(input_tokens, int) and isinstance(output_tokens, int):
        total_tokens = input_tokens + output_tokens
    return NormalizedUsage(input_tokens=input_tokens, output_tokens=output_tokens, total_tokens=total_tokens)


@dataclass
class PerplexityAgentTransport:
    """Low-level Agent API transport for structured, tool-free inference.

    Not exposed to domain code -- only the Agent-backed extraction provider (and
    future Agent-backed capabilities) call this directly.
    """

    api_key: str
    base_url: str = DEFAULT_PERPLEXITY_AGENT_BASE_URL
    timeout_seconds: float = 120.0
    post: Callable[..., Any] = httpx.post
    clock: Callable[[], float] = field(default=time.monotonic)

    def __post_init__(self) -> None:
        self.base_url = _validate_base_url(self.base_url)

    @property
    def endpoint(self) -> str:
        base = self.base_url.rstrip("/")
        if base.endswith("/agent") or base.endswith("/responses"):
            return base
        return f"{base}/agent"

    def complete(
        self,
        *,
        model: str,
        instructions: str,
        input_text: str,
        response_format: dict[str, Any] | None,
        max_output_tokens: int,
    ) -> NormalizedChatResponse:
        if not isinstance(max_output_tokens, int) or isinstance(max_output_tokens, bool) or max_output_tokens < 1:
            raise ValueError("max_output_tokens must be a positive integer")
        # Closed-book, single-model structured inference. Deliberately no
        # `tools`, no `preset`, and no `models` fallback array: the model cannot
        # search or call any tool, and the platform cannot substitute a
        # different model behind a fallback chain.
        body: dict[str, Any] = {
            "model": model,
            "instructions": instructions,
            "input": input_text,
            "max_output_tokens": max_output_tokens,
        }
        if response_format is not None:
            body["response_format"] = response_format

        started = self.clock()
        try:
            response = self.post(self.endpoint, headers=agent_auth_headers(self.api_key), json=body, timeout=self.timeout_seconds)
        except httpx.TimeoutException as exc:
            raise GatewayTimeoutError(sanitize("perplexity agent request timed out", self.api_key)) from exc
        except httpx.HTTPError as exc:
            raise GatewayUnavailableError(
                sanitize(f"perplexity agent transport failure ({type(exc).__name__})", self.api_key)
            ) from exc
        latency = round(self.clock() - started, 3)

        if response.status_code >= 400:
            raise_for_agent_status(response, self.api_key)

        try:
            envelope = response.json()
        except ValueError as exc:
            raise GatewayMalformedResponseError(
                sanitize(f"could not parse perplexity agent response as JSON: {exc}", self.api_key)
            ) from exc
        if not isinstance(envelope, dict):
            raise GatewayMalformedResponseError("perplexity agent response envelope must be an object")

        status = envelope.get("status")
        if status != "completed":
            # A 200 can still carry a non-terminal or failed status (queued,
            # in_progress, incomplete, failed). None of those yield usable
            # structured output for a synchronous extraction call.
            raise GatewayMalformedResponseError(
                sanitize(f"perplexity agent response status was {status!r}, not 'completed'", self.api_key)
            )

        output = envelope.get("output")
        if not isinstance(output, list):
            raise GatewayMalformedResponseError("perplexity agent response 'output' must be a list")
        content = extract_output_text(output)
        if not isinstance(content, str) or not content:
            raise GatewayMalformedResponseError("perplexity agent response contained no message text")

        returned_model = envelope.get("model")
        return NormalizedChatResponse(
            content=content,
            provider="perplexity",
            model=returned_model.strip() if isinstance(returned_model, str) and returned_model.strip() else None,
            usage=normalize_responses_usage(envelope.get("usage")),
            latency_seconds=latency,
            request_id=envelope.get("id") if isinstance(envelope.get("id"), str) else None,
        )


def list_agent_models(
    *,
    api_key: str | None = None,
    base_url: str = DEFAULT_PERPLEXITY_MODELS_URL,
    get: Callable[..., Any] = httpx.get,
    timeout_seconds: float = 30.0,
) -> list[dict[str, str]]:
    """Read-only discovery of current Agent models via `GET /v1/models`.

    Returns normalized ``[{"id", "owned_by"}]`` sorted by id. No auth is
    required by the endpoint; a key is sent only if supplied. Nothing is
    persisted -- the catalog is live provider state, not trusted repository data.
    """

    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        response = get(base_url, headers=headers, timeout=timeout_seconds)
    except httpx.TimeoutException as exc:
        raise GatewayTimeoutError(sanitize("perplexity models request timed out", api_key)) from exc
    except httpx.HTTPError as exc:
        raise GatewayUnavailableError(
            sanitize(f"perplexity models transport failure ({type(exc).__name__})", api_key)
        ) from exc
    if response.status_code >= 400:
        raise_for_agent_status(response, api_key or "")
    try:
        envelope = response.json()
        data = envelope["data"]
    except (ValueError, KeyError, TypeError) as exc:
        raise GatewayMalformedResponseError(
            sanitize(f"malformed perplexity models response: {exc}", api_key)
        ) from exc
    if not isinstance(data, list):
        raise GatewayMalformedResponseError("perplexity models response 'data' must be a list")
    models: list[dict[str, str]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        model_id = item.get("id")
        if not isinstance(model_id, str) or not model_id:
            continue
        owned_by = item.get("owned_by")
        models.append({"id": model_id, "owned_by": owned_by if isinstance(owned_by, str) else ""})
    return sorted(models, key=lambda entry: entry["id"])
