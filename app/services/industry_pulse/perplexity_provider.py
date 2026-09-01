"""Perplexity Search discovery adapter.

Uses the existing Search API client. Public berry-industry query strings
only. Does not send Assessments, Signals, Facts, or private report prose.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Callable

from app.services.ai_gateway.perplexity_search import PerplexitySearchClient
from app.services.industry_pulse.credentials import PERPLEXITY_API_KEY_ENV, env_key, has_perplexity
from app.services.industry_pulse.errors import ProviderAuthError
from app.services.industry_pulse.http import map_gateway
from app.services.industry_pulse.matrix import PulseQuery
from app.services.industry_pulse.models import DiscoveryHit
from app.services.industry_pulse.providers import hits_from_web_rows
from app.services.industry_pulse.query_text import (
    date_window_of,
    iso_country,
    perplexity_date_kwargs,
    semantic_query_text,
)


def _today() -> date:
    return datetime.now(timezone.utc).date()


@dataclass
class PerplexitySearchProvider:
    """Comparable web discovery via Perplexity Search, not Agent/Sonar."""

    name: str = "perplexity"
    api_key: str | None = None
    timeout_seconds: float = 30.0
    max_results: int = 10
    post: Callable[..., Any] | None = None
    today: date | None = None
    client: PerplexitySearchClient | None = None

    def discover(self, query: PulseQuery) -> list[DiscoveryHit]:
        key = (self.api_key or env_key(PERPLEXITY_API_KEY_ENV)).strip()
        if not key:
            raise ProviderAuthError("PERPLEXITY_API_KEY is not configured")
        client = self.client
        if client is None:
            kwargs: dict[str, Any] = {"api_key": key, "timeout_seconds": self.timeout_seconds}
            if self.post is not None:
                kwargs["post"] = self.post
            client = PerplexitySearchClient(**kwargs)
        window = date_window_of(query)
        today = self.today or _today()
        date_kwargs = perplexity_date_kwargs(window, today=today)
        country = iso_country(query.geography)
        try:
            result = client.search(
                semantic_query_text(query),
                max_results=min(max(self.max_results, 1), 20),
                country=country,
                **date_kwargs,
            )
        except Exception as exc:  # noqa: BLE001 — map gateway taxonomy
            mapped = map_gateway(exc)
            raise mapped from exc
        rows = [
            {
                "title": hit.title,
                "url": hit.url,
                "published_date": hit.published_date,
                "snippet": hit.snippet,
                "provider_metadata": {},
            }
            for hit in result.hits
        ]
        return hits_from_web_rows(rows, query=query, provider_name=self.name)


def available() -> bool:
    return has_perplexity()
