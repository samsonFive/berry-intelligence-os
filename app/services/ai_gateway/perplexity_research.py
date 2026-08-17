"""Grounded research via Perplexity's Agent API.

`research(prompt, web_enabled=True, citations=True, model=...)` -> a
normalized response with citations. This is a separate capability from
plain structured extraction: it explicitly opts into web access (extraction
never does), and it never bypasses Evidence trust gates -- nothing in this
module writes Evidence, entities, or any repository record. It exists as a
seam for a future, separately scoped research/synthesis workflow; no consuming
workflow is built here.

It shares the Agent transport primitives (auth headers, error mapping, output
text extraction, usage normalization) with `perplexity_agent`, but keeps its
own request body (which lists `tools`) and citation parsing, so research and
extraction never collapse into one code path.

Verified against docs.perplexity.ai (2026-08-17): `POST
https://api.perplexity.ai/v1/agent`, bearer auth, request `{"model", "input",
"tools", "max_output_tokens"}` (`max_output_tokens` is required for anthropic/*
models, so it is always sent as a positive integer), response `{"id", "model",
"status", "output": [...], "usage": {...}}` where the message-type output item's
`content` holds `output_text` blocks and tool-result output items (when
`web_search` is enabled) carry citation URLs. Citations parse defensively -- an
unrecognized shape yields an empty list rather than raising.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any, Callable

import httpx

from app.services.ai_gateway.credentials import sanitize
from app.services.ai_gateway.errors import (
    GatewayMalformedResponseError,
    GatewayTimeoutError,
    GatewayUnavailableError,
)
from app.services.ai_gateway.perplexity_agent import (
    DEFAULT_PERPLEXITY_AGENT_BASE_URL,
    _validate_base_url,
    agent_auth_headers,
    extract_output_text,
    normalize_responses_usage,
    raise_for_agent_status,
)
from app.services.ai_gateway.results import ResearchCitation, ResearchResponse


DEFAULT_PERPLEXITY_AGENT_URL = DEFAULT_PERPLEXITY_AGENT_BASE_URL
# See perplexity_agent for why max_output_tokens is always sent (required for
# anthropic/* Agent models; provider-neutral).
DEFAULT_RESEARCH_MAX_OUTPUT_TOKENS = 4096


@dataclass
class PerplexityResearchClient:
    api_key: str
    base_url: str = DEFAULT_PERPLEXITY_AGENT_URL
    timeout_seconds: float = 120.0
    post: Callable[..., Any] = httpx.post
    clock: Callable[[], float] = field(default=time.monotonic)

    def __post_init__(self) -> None:
        self.base_url = _validate_base_url(self.base_url)

    def research(
        self,
        prompt: str,
        *,
        model: str,
        web_enabled: bool = True,
        citations: bool = True,
        max_output_tokens: int = DEFAULT_RESEARCH_MAX_OUTPUT_TOKENS,
    ) -> ResearchResponse:
        if not prompt.strip():
            raise ValueError("prompt must be nonempty")
        if not model.strip():
            raise ValueError("model must be specified explicitly; it is never hardcoded here")
        if not isinstance(max_output_tokens, int) or isinstance(max_output_tokens, bool) or max_output_tokens < 1:
            raise ValueError("max_output_tokens must be a positive integer")
        body: dict[str, Any] = {
            "model": model,
            "input": prompt,
            # Research MAY use tools; extraction never does. This is the
            # structural distinction between the two Agent-backed capabilities.
            "tools": [{"type": "web_search"}] if web_enabled else [],
            "max_output_tokens": max_output_tokens,
        }
        started = self.clock()
        try:
            response = self.post(self.base_url, headers=agent_auth_headers(self.api_key), json=body, timeout=self.timeout_seconds)
        except httpx.TimeoutException as exc:
            raise GatewayTimeoutError(sanitize("perplexity research request timed out", self.api_key)) from exc
        except httpx.HTTPError as exc:
            raise GatewayUnavailableError(
                sanitize(f"perplexity research transport failure ({type(exc).__name__})", self.api_key)
            ) from exc
        latency = round(self.clock() - started, 3)

        if response.status_code >= 400:
            raise_for_agent_status(response, self.api_key)

        try:
            envelope = response.json()
            output = envelope["output"]
        except (ValueError, KeyError, TypeError) as exc:
            raise GatewayMalformedResponseError(
                sanitize(f"malformed perplexity research response: {exc}", self.api_key)
            ) from exc
        if not isinstance(output, list):
            raise GatewayMalformedResponseError("perplexity research response 'output' must be a list")

        text = extract_output_text(output)
        if text is None:
            raise GatewayMalformedResponseError("perplexity research response contained no message text")
        found_citations = self._extract_citations(output) if citations else ()

        returned_model = envelope.get("model")
        return ResearchResponse(
            provider="perplexity",
            model=returned_model.strip() if isinstance(returned_model, str) and returned_model.strip() else None,
            content=text,
            citations=found_citations,
            web_enabled=web_enabled,
            usage=normalize_responses_usage(envelope.get("usage")),
            latency_seconds=latency,
            request_id=envelope.get("id") if isinstance(envelope.get("id"), str) else None,
        )

    @staticmethod
    def _extract_citations(output: list[Any]) -> tuple[ResearchCitation, ...]:
        citations: list[ResearchCitation] = []
        seen: set[str] = set()
        for item in output:
            if not isinstance(item, dict):
                continue
            candidates = item.get("results") if isinstance(item.get("results"), list) else []
            for candidate in candidates:
                if not isinstance(candidate, dict):
                    continue
                url = candidate.get("url")
                if isinstance(url, str) and url and url not in seen:
                    seen.add(url)
                    title = candidate.get("title")
                    citations.append(ResearchCitation(url=url, title=title if isinstance(title, str) else None))
        return tuple(citations)
