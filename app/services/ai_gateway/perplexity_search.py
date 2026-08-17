"""Raw web search via Perplexity's Search API.

`search(query)` -> normalized ranked results. This is a separate capability
from structured inference and grounded research: it returns ranked
URLs/snippets only, with no model generation involved, and is not wired
into any discovery or extraction workflow. It exists so a later, explicitly
scoped task can build a consuming workflow without inventing this transport.

Verified against docs.perplexity.ai as of 2026-08-16: `POST
https://api.perplexity.ai/search` with `{"query": ..., "max_results": ...}`,
bearer auth, returning `{"id", "results": [{"title", "url", "snippet",
"date"}]}`.
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
    GatewayRateLimitError,
    GatewayUnavailableError,
    GatewayTimeoutError,
)
from app.services.ai_gateway.perplexity_chat import _validate_base_url
from app.services.ai_gateway.results import SearchHit, SearchResponse


DEFAULT_PERPLEXITY_SEARCH_URL = "https://api.perplexity.ai/search"


@dataclass
class PerplexitySearchClient:
    api_key: str
    base_url: str = DEFAULT_PERPLEXITY_SEARCH_URL
    timeout_seconds: float = 30.0
    post: Callable[..., Any] = httpx.post
    clock: Callable[[], float] = field(default=time.monotonic)

    def __post_init__(self) -> None:
        self.base_url = _validate_base_url(self.base_url)

    def search(self, query: str, *, max_results: int = 10) -> SearchResponse:
        if not query.strip():
            raise ValueError("query must be nonempty")
        if not (1 <= max_results <= 20):
            raise ValueError("max_results must be between 1 and 20")
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}
        body = {"query": query, "max_results": max_results}
        started = self.clock()
        try:
            response = self.post(self.base_url, headers=headers, json=body, timeout=self.timeout_seconds)
        except httpx.TimeoutException as exc:
            raise GatewayTimeoutError(sanitize("perplexity search request timed out", self.api_key)) from exc
        except httpx.HTTPError as exc:
            raise GatewayUnavailableError(
                sanitize(f"perplexity search transport failure ({type(exc).__name__})", self.api_key)
            ) from exc
        latency = round(self.clock() - started, 3)

        if response.status_code >= 400:
            self._raise_for_status(response)

        try:
            envelope = response.json()
            raw_results = envelope["results"]
        except (ValueError, KeyError, TypeError) as exc:
            raise GatewayMalformedResponseError(
                sanitize(f"malformed perplexity search response: {exc}", self.api_key)
            ) from exc
        if not isinstance(raw_results, list):
            raise GatewayMalformedResponseError("perplexity search response 'results' must be a list")
        hits = tuple(
            SearchHit(
                title=str(item.get("title") or ""),
                url=str(item.get("url") or ""),
                snippet=str(item.get("snippet") or ""),
                published_date=item.get("date") if isinstance(item.get("date"), str) else None,
            )
            for item in raw_results
            if isinstance(item, dict) and item.get("url")
        )
        return SearchResponse(
            provider="perplexity",
            query=query,
            hits=hits,
            latency_seconds=latency,
            request_id=envelope.get("id") if isinstance(envelope.get("id"), str) else None,
        )

    def _raise_for_status(self, response: Any) -> None:
        status = response.status_code
        detail = (response.text or "")[:300]
        message = sanitize(f"perplexity search HTTP failure ({status}): {detail}", self.api_key)
        if status in (401, 403):
            raise GatewayAuthError(message)
        if status == 429:
            raise GatewayRateLimitError(message)
        if status >= 500:
            raise GatewayUnavailableError(message)
        raise GatewayError(message)
