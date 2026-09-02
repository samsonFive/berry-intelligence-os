"""Exa search adapter. Live only when EXA_API_KEY is set."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Callable

import httpx

from app.services.industry_pulse.credentials import EXA_API_KEY_ENV, env_key, has_exa
from app.services.industry_pulse.errors import ProviderAuthError
from app.services.industry_pulse.http import request_json
from app.services.industry_pulse.matrix import PulseQuery
from app.services.industry_pulse.models import DiscoveryHit
from app.services.industry_pulse.providers import hits_from_web_rows
from app.services.industry_pulse.query_text import (
    date_window_of,
    exa_start_published,
    iso_country,
    semantic_query_text,
)

EXA_SEARCH_URL = "https://api.exa.ai/search"
EXA_SETUP = (
    "SET EXA_API_KEY → provider becomes available. "
    "Create a key at https://dashboard.exa.ai/api-keys and set it in the "
    "process environment (never commit it). POST https://api.exa.ai/search "
    "with Authorization: Bearer. Not required at app boot. "
    "2026 list price: $7/1k searches (10 results included); $10 free credits/month. "
    "Unknown-unknown queries use type=auto and do not require the crop name in the title."
)


def _today() -> date:
    return datetime.now(timezone.utc).date()


@dataclass
class ExaSearchProvider:
    """Neural/keyword web search. Does not write Evidence."""

    name: str = "exa"
    api_key: str | None = None
    timeout_seconds: float = 30.0
    num_results: int = 10
    post: Callable[..., Any] = httpx.post
    today: date | None = None

    def discover(self, query: PulseQuery) -> list[DiscoveryHit]:
        key = (self.api_key or env_key(EXA_API_KEY_ENV)).strip()
        if not key:
            raise ProviderAuthError(f"EXA_API_KEY is not configured. {EXA_SETUP}")
        window = date_window_of(query)
        today = self.today or _today()
        text = semantic_query_text(query)
        search_type = "auto"
        body: dict[str, Any] = {
            "query": text,
            "type": search_type,
            "numResults": min(max(self.num_results, 1), 100),
            "startPublishedDate": exa_start_published(window, today=today),
            "contents": {"text": False, "highlights": {"maxCharacters": 400}},
        }
        if query.kind == "unknown_unknown":
            body["category"] = "news"
        country = iso_country(query.geography)
        if country:
            body["userLocation"] = country
        envelope = request_json(
            self.post,
            EXA_SEARCH_URL,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
            body=body,
            timeout_seconds=self.timeout_seconds,
        )
        rows = []
        for item in envelope.get("results") or []:
            if not isinstance(item, dict) or not item.get("url"):
                continue
            highlights = item.get("highlights") or []
            snippet = ""
            if isinstance(highlights, list) and highlights:
                snippet = " ".join(str(part) for part in highlights if part)
            rows.append(
                {
                    "title": item.get("title") or "",
                    "url": item.get("url"),
                    "published_date": item.get("publishedDate"),
                    "snippet": snippet[:500],
                    "origin_publisher_name": item.get("author"),
                    "provider_metadata": {
                        "exa_id": item.get("id"),
                        "exa_score": item.get("score"),
                    },
                }
            )
        return hits_from_web_rows(rows, query=query, provider_name=self.name)


def available() -> bool:
    return has_exa()
