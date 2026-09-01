"""NewsCatcher CatchAll discovery adapter.

CatchAll is an asynchronous event-enumeration API (typically 10-15 minutes
per job), not a synchronous news RSS substitute. This adapter implements
DiscoveryProvider for bake-off compatibility.

Live jobs are NEVER started from Industry Pulse `run_pulse()` or the
default bake-off slice loop. A single optional probe runs only when
CATCHALL_LIVE_PROBE is set and a key is present.

Monitors are not created from this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from app.services.industry_pulse.credentials import (
    CATCHALL_API_KEY_ENV,
    NEWSCATCHER_API_KEY_ENV,
    catchall_key,
    has_catchall,
)
from app.services.industry_pulse.errors import ProviderAuthError
from app.services.industry_pulse.matrix import PulseQuery
from app.services.industry_pulse.models import DiscoveryHit
from app.services.industry_pulse.providers import hits_from_web_rows
from app.services.industry_pulse.query_text import date_window_of, semantic_query_text

CATCHALL_BASE = "https://catchall.newscatcherapi.com"
SUBMIT_PATH = "/catchAll/submit"
PULL_PATH = "/catchAll/pull/{job_id}"
STATUS_PATH = "/catchAll/status/{job_id}"
LIVE_PROBE_ENV = "CATCHALL_LIVE_PROBE"
DEFAULT_LIMIT = 5


@dataclass
class CatchAllDiscoveryProvider:
    """Event records → DiscoveryHit. Does not write Evidence or create monitors."""

    name: str = "newscatcher_catchall"
    api_key: str | None = None
    timeout_seconds: float = 30.0
    limit: int = DEFAULT_LIMIT
    submit: Callable[..., Any] | None = None
    pull: Callable[..., Any] | None = None
    prefetched_records: list[dict[str, Any]] = field(default_factory=list)

    def discover(self, query: PulseQuery) -> list[DiscoveryHit]:
        key = (self.api_key or catchall_key()).strip()
        if not key:
            raise ProviderAuthError(
                f"{NEWSCATCHER_API_KEY_ENV} / {CATCHALL_API_KEY_ENV} is not configured"
            )
        records = list(self.prefetched_records)
        if not records and self.pull is not None:
            records = list(self.pull(query) or [])
        if not records and self.submit is not None:
            # Explicit injected submit only — default bake-off must not
            # enqueue a 10-15 minute paid job per slice.
            payload = self.submit(
                {
                    "query": semantic_query_text(query),
                    "limit": min(max(self.limit, 1), 25),
                    "window": date_window_of(query),
                }
            )
            records = list((payload or {}).get("records") or [])
        return records_to_hits(records, query=query, provider_name=self.name)


def records_to_hits(
    records: list[dict[str, Any]],
    *,
    query: PulseQuery,
    provider_name: str = "newscatcher_catchall",
) -> list[DiscoveryHit]:
    rows: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        citations = record.get("citations") or []
        first = citations[0] if citations and isinstance(citations[0], dict) else {}
        url = (
            record.get("url")
            or first.get("url")
            or first.get("link")
            or ""
        )
        if not url:
            continue
        enrichment = record.get("enrichment") if isinstance(record.get("enrichment"), dict) else {}
        snippet = str(
            record.get("snippet")
            or enrichment.get("summary")
            or record.get("record_title")
            or ""
        )
        rows.append(
            {
                "title": record.get("record_title") or record.get("title") or "",
                "url": url,
                "published_date": record.get("published_date")
                or first.get("published_date")
                or enrichment.get("event_date"),
                "snippet": snippet[:500],
                "origin_publisher_name": first.get("name") or first.get("publisher"),
                "provider_metadata": {
                    "record_id": record.get("record_id"),
                    "catchall_event": True,
                },
            }
        )
    return hits_from_web_rows(rows, query=query, provider_name=provider_name)


def available() -> bool:
    return has_catchall()


def live_probe_enabled() -> bool:
    from os import environ

    return environ.get(LIVE_PROBE_ENV, "").lower() in {"1", "true", "yes"}
