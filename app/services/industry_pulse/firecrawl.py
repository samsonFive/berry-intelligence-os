"""Firecrawl Search adapter. Live only when FIRECRAWL_API_KEY is set."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Callable

import httpx

from app.services.industry_pulse.credentials import FIRECRAWL_API_KEY_ENV, env_key, has_firecrawl
from app.services.industry_pulse.errors import ProviderAuthError
from app.services.industry_pulse.http import request_json
from app.services.industry_pulse.matrix import PulseQuery
from app.services.industry_pulse.models import DiscoveryHit
from app.services.industry_pulse.providers import hits_from_web_rows
from app.services.industry_pulse.query_text import date_window_of, firecrawl_tbs, semantic_query_text

FIRECRAWL_SEARCH_URL = "https://api.firecrawl.dev/v2/search"
FIRECRAWL_SCRAPE_URL = "https://api.firecrawl.dev/v2/scrape"


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _web_rows(envelope: dict[str, Any]) -> list[dict[str, Any]]:
    data = envelope.get("data") if isinstance(envelope.get("data"), dict) else envelope
    web = data.get("web") if isinstance(data, dict) else None
    if isinstance(web, list):
        return [row for row in web if isinstance(row, dict)]
    results = envelope.get("results") or (data.get("results") if isinstance(data, dict) else None) or []
    return [row for row in results if isinstance(row, dict)]


@dataclass
class FirecrawlSearchProvider:
    """Web search via Firecrawl. Optional scrape is a separate method."""

    name: str = "firecrawl"
    api_key: str | None = None
    timeout_seconds: float = 30.0
    limit: int = 10
    post: Callable[..., Any] = httpx.post
    today: date | None = None

    def _key(self) -> str:
        key = (self.api_key or env_key(FIRECRAWL_API_KEY_ENV)).strip()
        if not key:
            raise ProviderAuthError("FIRECRAWL_API_KEY is not configured")
        return key

    def discover(self, query: PulseQuery) -> list[DiscoveryHit]:
        key = self._key()
        window = date_window_of(query)
        today = self.today or _today()
        body: dict[str, Any] = {
            "query": semantic_query_text(query),
            "limit": min(max(self.limit, 1), 100),
            "tbs": firecrawl_tbs(window, today=today),
            "sources": ["web"],
        }
        envelope = request_json(
            self.post,
            FIRECRAWL_SEARCH_URL,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
            body=body,
            timeout_seconds=self.timeout_seconds,
        )
        rows = []
        for item in _web_rows(envelope if isinstance(envelope, dict) else {}):
            url = item.get("url")
            if not url:
                continue
            rows.append(
                {
                    "title": item.get("title") or "",
                    "url": url,
                    "published_date": item.get("publishedTime") or item.get("date") or item.get("published_date"),
                    "snippet": item.get("description") or item.get("snippet") or "",
                    "provider_metadata": {
                        "firecrawl_position": item.get("position"),
                    },
                }
            )
        return hits_from_web_rows(rows, query=query, provider_name=self.name)

    def scrape(self, url: str) -> dict[str, Any]:
        """Bounded single-page acquisition probe. Never crawls a site."""
        key = self._key()
        envelope = request_json(
            self.post,
            FIRECRAWL_SCRAPE_URL,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
            body={"url": url, "formats": ["markdown"]},
            timeout_seconds=self.timeout_seconds,
        )
        data = envelope.get("data") if isinstance(envelope, dict) else None
        if not isinstance(data, dict):
            data = envelope if isinstance(envelope, dict) else {}
        metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
        markdown = str(data.get("markdown") or "")
        return {
            "url": url,
            "success": bool(markdown or metadata.get("title")),
            "title": metadata.get("title") or data.get("title"),
            "published_date": metadata.get("publishedTime") or metadata.get("published_date"),
            "markdown_chars": len(markdown),
            "has_table": "|" in markdown and "---" in markdown,
            "metadata_keys": sorted(str(key) for key in metadata.keys()),
        }


def available() -> bool:
    return has_firecrawl()
