"""Bright Data SERP adapter.

Credentials are a zone plus API token. Without both, live search is
unavailable. This is an alternate index / blocked-page escalation, not a
default discovery backbone.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import quote

import httpx

from app.services.industry_pulse.credentials import (
    BRIGHTDATA_API_KEY_ENV,
    BRIGHTDATA_ZONE_ENV,
    env_key,
    has_brightdata,
)
from app.services.industry_pulse.errors import ProviderAuthError, ProviderUnavailableError
from app.services.industry_pulse.http import request_json
from app.services.industry_pulse.matrix import PulseQuery
from app.services.industry_pulse.models import DiscoveryHit
from app.services.industry_pulse.providers import hits_from_web_rows
from app.services.industry_pulse.query_text import date_window_of, semantic_query_text

BRIGHTDATA_REQUEST_URL = "https://api.brightdata.com/request"


@dataclass
class BrightDataSearchProvider:
    """SERP search via a Bright Data zone. Does not bypass robots by default."""

    name: str = "brightdata"
    api_key: str | None = None
    zone: str | None = None
    timeout_seconds: float = 45.0
    post: Callable[..., Any] = httpx.post

    def discover(self, query: PulseQuery) -> list[DiscoveryHit]:
        key = (self.api_key or env_key(BRIGHTDATA_API_KEY_ENV)).strip()
        zone = (self.zone or env_key(BRIGHTDATA_ZONE_ENV)).strip()
        if not key or not zone:
            raise ProviderAuthError("BRIGHTDATA_API_KEY and BRIGHTDATA_SERP_ZONE are not configured")
        text = semantic_query_text(query)
        window = date_window_of(query)
        # tbs is Google SERP date syntax, used only when a SERP zone is configured.
        tbs = {"24h": "qdr:d", "3d": "qdr:d3", "7d": "qdr:w"}.get(window, "qdr:w")
        target = f"https://www.google.com/search?q={quote(text)}&tbs={tbs}&hl=en&num=10"
        envelope = request_json(
            self.post,
            BRIGHTDATA_REQUEST_URL,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
            },
            body={"zone": zone, "url": target, "format": "json"},
            timeout_seconds=self.timeout_seconds,
        )
        organic = []
        if isinstance(envelope, dict):
            organic = envelope.get("organic") or envelope.get("organic_results") or []
        if not isinstance(organic, list):
            raise ProviderUnavailableError("Bright Data SERP response had no organic results list")
        rows = []
        for item in organic:
            if not isinstance(item, dict):
                continue
            url = item.get("link") or item.get("url")
            if not url:
                continue
            rows.append(
                {
                    "title": item.get("title") or "",
                    "url": url,
                    "published_date": item.get("date") or item.get("published_date"),
                    "snippet": item.get("description") or item.get("snippet") or "",
                    "provider_metadata": {"brightdata_rank": item.get("rank") or item.get("position")},
                }
            )
        return hits_from_web_rows(rows, query=query, provider_name=self.name)


def available() -> bool:
    return has_brightdata()
