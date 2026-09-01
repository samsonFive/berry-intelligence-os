"""Provider-neutral Industry Pulse discovery adapters.

Product logic calls `discover(query, date_window, geography, berry, topic)`
and receives normalized hits. Google News RSS is the current live provider
because it already exists in-repo and needs no paid credentials.

Later bake-off plug-in point (do not couple product logic to these now):
- Exa: implement `DiscoveryProvider.discover` using Exa's search API; map
  title/url/published_date/snippet; set provider="exa".
- Firecrawl Search: same Protocol; provider="firecrawl".
- Bright Data: same Protocol; provider="brightdata".
- Direct Source collectors stay on the existing media_discovery adapters;
  they are not this catch-net.

A new paid vendor is a new class in this file plus a constructor argument
to `run_pulse()`. Do not put vendor URLs in qualify/novelty/matrix.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.services.article_dedup import normalize_canonical_url
from app.services.industry_pulse.matrix import (
    GEO_EDITIONS,
    PulseQuery,
    WINDOW_WHEN,
)
from app.services.industry_pulse.models import DiscoveryHit
from app.services.media_discovery import (
    _fetch_paginated_rss,
    _normalize_news_search_entry,
    _podcast_rss_entries,
)
from app.services.recall_audit.classify import WRAPPER_HOSTS, hostname


class DiscoveryProvider(Protocol):
    """Normalized catch-net search. Implementations must not write Evidence."""

    name: str

    def discover(self, query: PulseQuery) -> list[DiscoveryHit]:
        ...


def discover(
    query: str,
    *,
    date_window: str = "7d",
    geography: str = "global",
    berry: str | None = None,
    topic: str | None = None,
    provider: DiscoveryProvider,
) -> list[DiscoveryHit]:
    """Provider-neutral entry. `date_window` is 24h / 3d / 7d."""
    if date_window not in WINDOW_WHEN:
        raise ValueError(f"unsupported date_window: {date_window}")
    edition = GEO_EDITIONS.get(geography) or GEO_EDITIONS["global"]
    pulse = PulseQuery(
        id=f"ad-hoc:{berry or 'any'}:{geography}:{topic or 'any'}:{date_window}",
        text=query,
        berry=berry,
        geography=geography,
        topic=topic or "ad_hoc",
        kind="ad_hoc",
        hl=edition["hl"],
        gl=edition["gl"],
        ceid=edition["ceid"],
    ).with_window(date_window)
    return provider.discover(pulse)


def _host_from_url(value: str | None) -> str:
    host = hostname(value)
    if host in WRAPPER_HOSTS:
        return ""
    return host


def hits_from_news_search_items(
    items: list[Any],
    *,
    query: PulseQuery,
    provider_name: str,
) -> list[DiscoveryHit]:
    """Map media_discovery NormalizedItem rows to DiscoveryHit."""
    hits: list[DiscoveryHit] = []
    for item in items:
        raw = getattr(item, "raw_metadata", None) or {}
        if isinstance(item, dict):
            title = str(item.get("title") or "")
            wrapper = item.get("canonical_url") or item.get("url") or ""
            published = item.get("published_date")
            snippet = str(item.get("description") or item.get("snippet") or "")
            origin_name = item.get("origin_publisher_name") or raw.get("origin_publisher_name")
            origin_url = item.get("origin_publisher_url") or raw.get("origin_publisher_url")
        else:
            title = str(item.title or "")
            wrapper = item.canonical_url or ""
            published = item.published_date
            snippet = str(item.description or "")
            origin_name = raw.get("origin_publisher_name")
            origin_url = raw.get("origin_publisher_url")
        publisher_url = origin_url or wrapper
        domain = _host_from_url(origin_url) or _host_from_url(publisher_url) or hostname(wrapper)
        published_date = str(published).strip()[:10] if published else None
        if published_date == "":
            published_date = None
        hits.append(
            DiscoveryHit(
                title=title,
                url=normalize_canonical_url(publisher_url) or str(publisher_url or ""),
                source_domain=domain,
                published_date=published_date,
                snippet=snippet[:500],
                query_id=query.id,
                query_text=query.text,
                geography=query.geography,
                berry=query.berry,
                topic=query.topic,
                provider=provider_name,
                origin_publisher_name=origin_name,
                origin_publisher_url=origin_url,
                wrapper_url=wrapper or None,
            )
        )
    return hits


@dataclass
class GoogleNewsRssProvider:
    """Live Google News RSS using the existing news_search_rss fetch/normalize."""

    name: str = "google_news_rss"
    max_pages: int = 1
    fetch: Any = None

    def discover(self, query: PulseQuery) -> list[DiscoveryHit]:
        parsed, _raw = _fetch_paginated_rss(
            query.feed_url(),
            max_pages=self.max_pages,
            fetch=self.fetch,
        )
        entries = _podcast_rss_entries(parsed)
        items = [_normalize_news_search_entry(entry) for entry in entries]
        return hits_from_news_search_items(items, query=query, provider_name=self.name)


@dataclass
class MemoryProvider:
    """Deterministic provider for tests and adapter-substitution proofs."""

    name: str = "memory"
    hits_by_query_id: dict[str, list[DiscoveryHit]] | None = None
    hits: list[DiscoveryHit] | None = None

    def discover(self, query: PulseQuery) -> list[DiscoveryHit]:
        if self.hits_by_query_id is not None:
            selected = list(self.hits_by_query_id.get(query.id, []))
        elif self.hits:
            selected = [
                hit
                for hit in self.hits
                if (hit.geography == query.geography)
                and (query.berry is None or hit.berry == query.berry)
                and (
                    query.kind in {"ad_hoc", "berry_geography"}
                    or query.topic in {None, "industry_pulse", "ad_hoc"}
                    or hit.topic == query.topic
                )
            ]
        else:
            selected = []
        out: list[DiscoveryHit] = []
        for hit in selected:
            clone = DiscoveryHit(**hit.as_dict())
            clone.query_id = query.id
            clone.query_text = query.text
            clone.provider = self.name
            clone.geography = query.geography
            if query.berry:
                clone.berry = query.berry
            if query.topic:
                clone.topic = query.topic
            out.append(clone)
        return out
