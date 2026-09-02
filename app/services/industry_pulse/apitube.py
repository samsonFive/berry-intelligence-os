"""APITube News API discovery adapter.

Sync search at GET/POST https://api.apitube.io/v1/news/everything.
Live only when APITUBE_API_KEY is set. Does not invent credentials.
Does not write Evidence. Public berry-industry query strings only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Callable

import httpx

from app.services.industry_pulse.credentials import APITUBE_API_KEY_ENV, env_key, has_apitube
from app.services.industry_pulse.errors import ProviderAuthError
from app.services.industry_pulse.http import map_transport, raise_for_status
from app.services.industry_pulse.matrix import PulseQuery
from app.services.industry_pulse.models import DiscoveryHit
from app.services.industry_pulse.providers import hits_from_web_rows
from app.services.industry_pulse.query_text import date_window_of, semantic_query_text, window_start

APITUBE_SEARCH_URL = "https://api.apitube.io/v1/news/everything"
APITUBE_SETUP = (
    f"SET {APITUBE_API_KEY_ENV} → provider becomes available. "
    "Operator setup: create an APITube account, copy the News API key (live keys start with "
    "api_live_), and set it in the process environment (never commit it). "
    "GET https://api.apitube.io/v1/news/everything with X-API-Key. "
    "Free plan: 100 req/day, 10/min, per_page<=10, first 5 pages, 200-char body "
    "preview. No documented embargo delay on the free plan. "
    "Commercial redistribution and full-text retention need vendor/counsel review."
)


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _published(row: dict[str, Any]) -> str | None:
    for key in ("published_at", "publishedAt", "published"):
        value = row.get(key)
        if isinstance(value, dict):
            value = value.get("date") or value.get("start") or value.get("value")
        if value:
            return str(value).strip()[:10]
    return None


@dataclass
class ApiTubeSearchProvider:
    """Keyword news search. Implements DiscoveryProvider. No Evidence writes."""

    name: str = "apitube"
    api_key: str | None = None
    timeout_seconds: float = 30.0
    per_page: int = 10
    get: Callable[..., Any] = httpx.get
    today: date | None = None

    def discover(self, query: PulseQuery) -> list[DiscoveryHit]:
        key = (self.api_key or env_key(APITUBE_API_KEY_ENV)).strip()
        if not key:
            raise ProviderAuthError(f"{APITUBE_API_KEY_ENV} is not configured. {APITUBE_SETUP}")
        window = date_window_of(query)
        today = self.today or _today()
        start = window_start(window, today=today).isoformat()
        params = {
            "query": semantic_query_text(query),
            "per_page": str(min(max(self.per_page, 1), 25)),
            "published_at.start": start,
            "published_at.end": today.isoformat(),
        }
        try:
            response = self.get(
                APITUBE_SEARCH_URL,
                headers={"X-API-Key": key, "Accept": "application/json"},
                params=params,
                timeout=self.timeout_seconds,
            )
        except Exception as exc:  # noqa: BLE001 -- map onto provider errors
            raise map_transport(exc) from exc
        status = getattr(response, "status_code", 0)
        if status >= 400:
            raise_for_status(status, detail=getattr(response, "text", "") or "")
        try:
            envelope = response.json()
        except (ValueError, TypeError) as exc:
            from app.services.industry_pulse.errors import ProviderUnavailableError

            raise ProviderUnavailableError("apitube returned a malformed response") from exc
        if not isinstance(envelope, dict):
            envelope = {}
        results = envelope.get("results") or envelope.get("articles") or envelope.get("data") or []
        rows: list[dict[str, Any]] = []
        for item in results:
            if not isinstance(item, dict):
                continue
            source = item.get("source") if isinstance(item.get("source"), dict) else {}
            url = item.get("url") or item.get("link") or ""
            if not url:
                continue
            rows.append(
                {
                    "title": item.get("title") or "",
                    "url": url,
                    "published_date": _published(item),
                    "snippet": str(item.get("description") or item.get("snippet") or item.get("summary") or "")[:500],
                    "origin_publisher_name": source.get("name") or source.get("domain") or item.get("source"),
                    "origin_publisher_url": url,
                    "provider_metadata": {"apitube_id": item.get("id")},
                }
            )
        return hits_from_web_rows(rows, query=query, provider_name=self.name)


def available() -> bool:
    return has_apitube()
