"""Reusable specialist-publication feeds for the live research plane.

These are existing Source RSS / site-search paths, not one-off scrapers.
`SpecialistRssProvider` implements DiscoveryProvider so /week (and any
other live plane) can ingest current specialist items without waiting for
Publication Review or a collection run.

A Source record existing in sources.json is not the same as this provider
being invoked. /week V1 never called these feeds. That is why a same-day
Fruitnet Fresh Produce Journal story could exist in the Source registry
and still be absent from the weekly edition.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import urlparse

from app.services.industry_pulse.matrix import GEO_EDITIONS, PulseQuery
from app.services.industry_pulse.models import DiscoveryHit
from app.services.industry_pulse.providers import hits_from_news_search_items
from app.services.media_discovery import (
    _fetch_paginated_rss,
    _normalize_article_rss_entry,
    _normalize_news_search_entry,
    _podcast_rss_entries,
)
from app.services.recall_audit.classify import hostname

# Bounded first-class specialist catalog. Prefer publisher RSS, then the
# already-verified site-restricted Google News search path. No HTML scrape.
WEEK_SPECIALIST_FEEDS: tuple[dict[str, str], ...] = (
    {
        "id": "feed:fruitnet",
        "label": "Fruitnet",
        "source_id": "source-fruitnet-produce-plus",
        "host": "fruitnet.com",
        "feed_url": "https://www.fruitnet.com/45.rss",
        "adapter": "article_rss",
        "geography": "global",
    },
    {
        "id": "feed:fruitnet-search",
        "label": "Fruitnet",
        "source_id": "source-fruitnet-produce-plus",
        "host": "fruitnet.com",
        "feed_url": (
            "https://news.google.com/rss/search?"
            "q=site:fruitnet.com+(berry+OR+blueberry+OR+strawberry+OR+raspberry+OR+blackberry+OR+harvest)"
            "&hl=en-GB&gl=GB&ceid=GB:en"
        ),
        "adapter": "news_search_rss",
        "geography": "global",
    },
    {
        "id": "feed:freshplaza",
        "label": "FreshPlaza",
        "source_id": "source-freshplaza-global",
        "host": "freshplaza.com",
        "feed_url": "https://www.freshplaza.com/rss.xml",
        "adapter": "article_rss",
        "geography": "global",
    },
    {
        "id": "feed:hortidaily",
        "label": "HortiDaily",
        "source_id": "source-20260819-hortidaily",
        "host": "hortidaily.com",
        "feed_url": "https://www.hortidaily.com/rss.xml",
        "adapter": "article_rss",
        "geography": "global",
    },
    {
        "id": "feed:freshfruitportal",
        "label": "FreshFruitPortal",
        "source_id": "source-20260806173428-c710-fresh-fruit-portal-73",
        "host": "freshfruitportal.com",
        "feed_url": "https://www.freshfruitportal.com/tag/berries/feed/",
        "adapter": "article_rss",
        "geography": "americas",
    },
    {
        "id": "feed:produce-report",
        "label": "Produce Report",
        "source_id": "source-20260806173428-1f0b-produce-report-79",
        "host": "producereport.com",
        "feed_url": "https://www.producereport.com/rss.xml",
        "adapter": "article_rss",
        "geography": "apac",
    },
    {
        "id": "feed:perishable-news",
        "label": "Perishable News",
        "source_id": "source-20260824-perishable-news-produce",
        "host": "perishablenews.com",
        "feed_url": "https://perishablenews.com/category/produce/feed/",
        "adapter": "article_rss",
        "geography": "americas",
    },
    {
        "id": "feed:italian-berry",
        "label": "Italian Berry",
        "source_id": "source-news-search-italian-berry",
        "host": "italianberry.it",
        "feed_url": "https://news.google.com/rss/search?q=site:italianberry.it&hl=en-US&gl=US&ceid=US:en",
        "adapter": "news_search_rss",
        "geography": "europe",
    },
    {
        "id": "feed:eastfruit",
        "label": "EastFruit",
        "source_id": "source-20260806173428-c725-eastfruit-80",
        "host": "east-fruit.com",
        "feed_url": "https://east-fruit.com/en/feed/",
        "adapter": "article_rss",
        "geography": "europe",
    },
    {
        "id": "feed:the-packer",
        "label": "The Packer",
        "source_id": "source-20260806173428-47f6-the-packer-72",
        "host": "thepacker.com",
        "feed_url": "https://news.google.com/rss/search?q=site:thepacker.com+(berry+OR+blueberry+OR+strawberry+OR+raspberry+OR+blackberry)&hl=en-US&gl=US&ceid=US:en",
        "adapter": "news_search_rss",
        "geography": "americas",
        "access_note": "First-party /rss.xml and /feed return 403. Google site-search only. Do not scrape.",
    },
    {
        "id": "feed:hortifrut-newsroom",
        "label": "Hortifrut",
        "source_id": "source-20260819-hortifrut-newsroom",
        "host": "hortifrut.com",
        "feed_url": "https://www.hortifrut.com/feed/",
        "adapter": "article_rss",
        "geography": "americas",
    },
    {
        "id": "feed:berries-australia",
        "label": "Berries Australia",
        "source_id": "source-20260824-berries-australia",
        "host": "berries.net.au",
        "feed_url": "https://berries.net.au/feed/",
        "adapter": "article_rss",
        "geography": "apac",
    },
    {
        "id": "feed:british-berry-growers",
        "label": "British Berry Growers",
        "source_id": "source-20260824-british-berry-growers-news",
        "host": "britishberrygrowers.org.uk",
        "feed_url": "https://britishberrygrowers.org.uk/feed/",
        "adapter": "article_rss",
        "geography": "europe",
    },
)

SPECIALIST_SITE_HOSTS: tuple[tuple[str, str, str], ...] = (
    ("fruitnet.com", "fruitnet", "global"),
    ("freshplaza.com", "freshplaza", "global"),
    ("hortidaily.com", "hortidaily", "global"),
    ("freshfruitportal.com", "freshfruitportal", "americas"),
    ("thepacker.com", "the-packer", "americas"),
    ("italianberry.it", "italian-berry", "europe"),
    ("east-fruit.com", "eastfruit", "europe"),
    ("producereport.com", "produce-report", "apac"),
    ("perishablenews.com", "perishable-news", "americas"),
)


def week_specialist_feed_queries() -> list[PulseQuery]:
    """One PulseQuery per specialist feed. Not part of the Pulse 32."""
    edition = GEO_EDITIONS["global"]
    rows: list[PulseQuery] = []
    for feed in WEEK_SPECIALIST_FEEDS:
        geo = feed.get("geography") or "global"
        geo_edition = GEO_EDITIONS.get(geo) or edition
        rows.append(
            PulseQuery(
                id=feed["id"],
                text=feed["feed_url"],
                berry=None,
                geography=geo,
                topic="specialist_feed",
                kind="specialist_feed",
                hl=geo_edition["hl"],
                gl=geo_edition["gl"],
                ceid=geo_edition["ceid"],
            )
        )
    return rows


def week_specialist_site_queries() -> list[PulseQuery]:
    """Google News site: rows so specialist hosts are searched, not hoped-for."""
    berry = (
        "(blueberry OR blueberries OR strawberry OR strawberries OR raspberry "
        "OR raspberries OR blackberry OR blackberries OR berry OR berries "
        "OR cultivar OR harvest OR grower)"
    )
    rows: list[PulseQuery] = []
    for host, slug, geography in SPECIALIST_SITE_HOSTS:
        edition = GEO_EDITIONS.get(geography) or GEO_EDITIONS["global"]
        rows.append(
            PulseQuery(
                id=f"site:{slug}",
                text=f"site:{host} {berry}",
                berry=None,
                geography=geography,
                topic="specialist_site",
                kind="specialist_site",
                hl=edition["hl"],
                gl=edition["gl"],
                ceid=edition["ceid"],
            )
        )
    return rows


def feed_by_query_id(query_id: str) -> dict[str, str] | None:
    for feed in WEEK_SPECIALIST_FEEDS:
        if query_id == feed["id"] or query_id.startswith(feed["id"] + ":"):
            return feed
    return None


@dataclass
class SpecialistRssProvider:
    """Generic RSS / news-search-RSS adapter. No publisher-specific scrape."""

    name: str = "specialist_rss"
    feeds: tuple[dict[str, str], ...] = WEEK_SPECIALIST_FEEDS
    fetch: Any = None
    max_pages: int = 1

    def discover(self, query: PulseQuery) -> list[DiscoveryHit]:
        feed = feed_by_query_id(query.id)
        if feed is None:
            for row in self.feeds:
                if row["id"] == query.id or query.text == row["feed_url"]:
                    feed = row
                    break
        if feed is None:
            return []
        parsed, _raw = _fetch_paginated_rss(
            feed["feed_url"],
            max_pages=self.max_pages,
            fetch=self.fetch,
        )
        entries = _podcast_rss_entries(parsed)
        if feed.get("adapter") == "news_search_rss":
            items = [_normalize_news_search_entry(entry) for entry in entries]
        else:
            items = [_normalize_article_rss_entry(entry) for entry in entries]
        hits = hits_from_news_search_items(items, query=query, provider_name=self.name)
        host = feed.get("host") or hostname(feed.get("feed_url"))
        for hit in hits:
            hit.origin_publisher_name = hit.origin_publisher_name or feed.get("label")
            if not hit.source_domain or hit.source_domain in {"news.google.com", "news.google"}:
                origin = hit.origin_publisher_url or hit.url
                resolved = hostname(origin)
                if resolved and resolved not in {"news.google.com"}:
                    hit.source_domain = resolved
                elif host:
                    hit.source_domain = host
            if not hit.origin_publisher_url and hit.url:
                hit.origin_publisher_url = hit.url
            hit.provider_metadata = {
                **(hit.provider_metadata or {}),
                "specialist_source_id": feed.get("source_id"),
                "specialist_adapter": feed.get("adapter"),
            }
        return hits


def hosts_from_feeds(feeds: Iterable[dict[str, str]] = WEEK_SPECIALIST_FEEDS) -> set[str]:
    return {str(row.get("host") or urlparse(row.get("feed_url") or "").netloc).removeprefix("www.") for row in feeds}
