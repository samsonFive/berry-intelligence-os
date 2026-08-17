"""Grounded research via Perplexity's Agent API.

`research(prompt, web_enabled=True, citations=True, model=...)` -> a
normalized response with citations. This is a separate capability from
plain structured inference: it explicitly opts into web access (the Agent
API disables all tools, including search, unless a caller lists them), and
it never bypasses Evidence trust gates -- nothing in this module writes
Evidence, entities, or any repository record. It exists as a seam for a
future, separately scoped research/synthesis workflow; no consuming
workflow is built here.

Verified against docs.perplexity.ai as of 2026-08-16 to the extent the
documentation summarizes it: `POST https://api.perplexity.ai/v1/agent`,
bearer auth, request `{"model", "input", "tools"}`, response
`{"id", "model", "status", "output": [...], "usage": {...}}` where the
final message-type output item's `content` holds `output_text` blocks and
tool-result output items (when `web_search` is enabled) carry citation
URLs. Because Perplexity's own docs do not fully enumerate the Agent API's
citation shape, this parses defensively -- an unrecognized shape yields an
empty citation list rather than raising, since citations here are
supplementary provenance, not the primary content.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any, Callable

import httpx

from app.services.ai_gateway.credentials import sanitize
from app.services.ai_gateway.errors import (
    GatewayAuthError,
    GatewayError,
    GatewayMalformedResponseError,
    GatewayModelNotFoundError,
    GatewayRateLimitError,
    GatewayTimeoutError,
    GatewayUnavailableError,
)
from app.services.ai_gateway.perplexity_chat import _validate_base_url
from app.services.ai_gateway.results import NormalizedUsage, ResearchCitation, ResearchResponse


DEFAULT_PERPLEXITY_AGENT_URL = "https://api.perplexity.ai/v1/agent"


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
    ) -> ResearchResponse:
        if not prompt.strip():
            raise ValueError("prompt must be nonempty")
        if not model.strip():
            raise ValueError("model must be specified explicitly; it is never hardcoded here")
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}
        body: dict[str, Any] = {
            "model": model,
            "input": prompt,
            "tools": [{"type": "web_search"}] if web_enabled else [],
        }
        started = self.clock()
        try:
            response = self.post(self.base_url, headers=headers, json=body, timeout=self.timeout_seconds)
        except httpx.TimeoutException as exc:
            raise GatewayTimeoutError(sanitize("perplexity research request timed out", self.api_key)) from exc
        except httpx.HTTPError as exc:
            raise GatewayUnavailableError(
                sanitize(f"perplexity research transport failure ({type(exc).__name__})", self.api_key)
            ) from exc
        latency = round(self.clock() - started, 3)

        if response.status_code >= 400:
            self._raise_for_status(response)

        try:
            envelope = response.json()
            output = envelope["output"]
        except (ValueError, KeyError, TypeError) as exc:
            raise GatewayMalformedResponseError(
                sanitize(f"malformed perplexity research response: {exc}", self.api_key)
            ) from exc
        if not isinstance(output, list):
            raise GatewayMalformedResponseError("perplexity research response 'output' must be a list")

        text = self._extract_text(output)
        if text is None:
            raise GatewayMalformedResponseError("perplexity research response contained no message text")
        found_citations = self._extract_citations(output) if citations else ()

        usage_raw = envelope.get("usage")
        usage_raw = usage_raw if isinstance(usage_raw, dict) else {}
        usage = NormalizedUsage(
            input_tokens=usage_raw.get("input_tokens"),
            output_tokens=usage_raw.get("output_tokens"),
            total_tokens=usage_raw.get("total_tokens"),
        )
        returned_model = envelope.get("model")
        return ResearchResponse(
            provider="perplexity",
            model=returned_model.strip() if isinstance(returned_model, str) and returned_model.strip() else None,
            content=text,
            citations=found_citations,
            web_enabled=web_enabled,
            usage=usage,
            latency_seconds=latency,
            request_id=envelope.get("id") if isinstance(envelope.get("id"), str) else None,
        )

    @staticmethod
    def _extract_text(output: list[Any]) -> str | None:
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

    def _raise_for_status(self, response: Any) -> None:
        status = response.status_code
        detail = (response.text or "")[:300]
        message = sanitize(f"perplexity research HTTP failure ({status}): {detail}", self.api_key)
        if status in (401, 403):
            raise GatewayAuthError(message)
        if status == 429:
            raise GatewayRateLimitError(message)
        if status == 404:
            raise GatewayModelNotFoundError(message)
        if status >= 500:
            raise GatewayUnavailableError(message)
        raise GatewayError(message)
