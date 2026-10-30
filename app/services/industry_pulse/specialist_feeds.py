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
from urllib.parse import quote_plus

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
        "id": "feed:trellis-sustainability", "label": "Trellis",
        "source_id": "source-trellis-sustainability", "host": "trellis.net",
        "feed_url": "https://trellis.net/feed/", "adapter": "article_rss",
        "geography": "global", "coverage": "sustainability",
    },
    {
        "id": "feed:watershed-blog", "label": "Watershed Blog",
        "source_id": "source-watershed-blog", "host": "watershed.com",
        "feed_url": "https://news.google.com/rss/search?q=" + quote_plus("site:watershed.com/blog") + "&hl=en-US&gl=US&ceid=US:en",
        "adapter": "news_search_rss", "geography": "global", "coverage": "sustainability",
    },
    {
        "id": "feed:packer-sustainability-insights", "label": "The Packer — Sustainability Insights",
        "source_id": "source-packer-sustainability-insights", "host": "thepacker.com",
        "feed_url": "https://news.google.com/rss/search?q=" + quote_plus('site:thepacker.com "Sustainability Insights"') + "&hl=en-US&gl=US&ceid=US:en",
        "adapter": "news_search_rss", "geography": "americas", "coverage": "sustainability",
        "access_note": "Publisher rejects server requests (403); indexed discovery only, no bypass.",
    },
    {
        "id": "feed:agfunder-climate-sustainability", "label": "AgFunderNews — Climate & Sustainability",
        "source_id": "source-agfunder-climate-sustainability", "host": "agfundernews.com",
        "feed_url": "https://agfundernews.com/category/climate-sustainability/feed/",
        "adapter": "article_rss", "geography": "global", "coverage": "sustainability",
    },
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
    for feed in configured_feeds():
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
    for feed in configured_feeds():
        if query_id == feed["id"] or query_id.startswith(feed["id"] + ":"):
            return feed
    return None


def requested_sustainability_hit(hit: DiscoveryHit) -> bool:
    """Only the operator-selected feeds expand beyond berry-only discovery."""
    feed = feed_by_query_id(hit.query_id)
    return bool(
        hit.provider == "specialist_rss" and feed
        and feed.get("coverage") == "sustainability"
        and hit.source_domain.removeprefix("www.") == feed["host"]
        and _sustainability_article_title(hit.title)
    )


def _sustainability_article_title(title: str) -> bool:
    """Indexed section homepages are discovery surfaces, not reader stories."""
    value = title.strip().casefold()
    suffixes = (" - the packer", " - watershed.com", " - agfundernews", " - trellis")
    while any(value.endswith(suffix) for suffix in suffixes):
        value = next(value[:-len(suffix)].strip() for suffix in suffixes if value.endswith(suffix))
    return value not in {
        "news", "fresh produce industry news", "sustainability insights",
        "the latest climate tech news", "watershed blog", "climate & sustainability archives",
    }


def requested_sustainability_record(record: dict[str, Any]) -> bool:
    if record.get("acquisition_lane") != "specialist_rss":
        return False
    provenance = record.get("discovery_provenance") or {}
    feed = feed_by_query_id(str(provenance.get("query_id") or ""))
    if not feed or feed.get("coverage") != "sustainability":
        return False
    if not _sustainability_article_title(str(record.get("title") or "")):
        return False
    hosts = {hostname(record.get(key) or "") for key in ("source_url", "origin_publisher_url")}
    return feed["host"] in hosts


@dataclass
class SpecialistRssProvider:
    """Generic RSS / news-search-RSS adapter. No publisher-specific scrape."""

    name: str = "specialist_rss"
    feeds: tuple[dict[str, str], ...] | None = None
    fetch: Any = None
    max_pages: int = 1
    coverage_dir: Any = None

    def discover(self, query: PulseQuery) -> list[DiscoveryHit]:
        feed = feed_by_query_id(query.id)
        if feed is None:
            for row in (self.feeds if self.feeds is not None else configured_feeds()):
                if row["id"] == query.id or query.text == row["feed_url"]:
                    feed = row
                    break
        if feed is None:
            return []
        from app.services.publisher_coverage import cached_articles
        direct = cached_articles(self.coverage_dir, query.id)
        try:
            parsed, _raw = _fetch_paginated_rss(
                feed["feed_url"], max_pages=self.max_pages, fetch=self.fetch,
            )
            entries = _podcast_rss_entries(parsed)
        except Exception:
            if not direct:
                raise
            entries = []  # Verified publisher discovery survives an index outage.
        if feed.get("adapter") == "news_search_rss":
            items = [_normalize_news_search_entry(entry) for entry in entries]
        else:
            items = [_normalize_article_rss_entry(entry) for entry in entries]
        hits = hits_from_news_search_items(items, query=query, provider_name=self.name)
        if direct:
            import re
            from app.services.industry_pulse.models import DiscoveryHit
            def identity(title, date):
                text = re.sub(r' - (?:The Packer|watershed\.com|Watershed)$', '', title, flags=re.I)
                return (' '.join(re.findall(r'\w+', text.casefold())), str(date or '')[:10])
            known = {identity(row['title'], row['published_date']) for row in direct}
            hits = [hit for hit in hits if identity(hit.title, hit.published_date) not in known]
            hits = [DiscoveryHit(title=row['title'], url=row['url'], source_domain=feed['host'],
                published_date=row['published_date'], snippet=row.get('snippet') or '',
                query_id=query.id, query_text=query.text, geography=query.geography,
                berry=None, topic='specialist_feed', provider=self.name,
                origin_publisher_name=feed['label'], origin_publisher_url=row['url'],
                provider_metadata={'coverage_source': 'publisher_listing', 'date_basis': row['date_basis']})
                for row in direct] + hits
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


def configured_feeds():
    from app.services.collection_settings import effective_feeds
    return effective_feeds((*WEEK_SPECIALIST_FEEDS, *registry_breeder_feeds()))


BREEDER_SOURCE_IDS = frozenset({
    'source-20260824-global-plant-genetics-newsroom', 'source-20260824-james-hutton-news',
    'source-20260824-nc-state-cals-news', 'source-20260824-uf-ifas-news', 'source-20260819-planasa-newsroom',
    'source-nc-state-rubus-portal', 'source-inhort-berry-breeding', 'source-embrapa-berry-research',
})


def registry_breeder_feeds(data_dir=None):
    """Reuse current registry URLs and lifecycle, without a copied feed catalog."""
    from app.runtime_config import resolve_data_dir
    from app.repositories.json.sources import JsonSourceRepository
    from app.services.source_lifecycle import is_collection_eligible
    rows = []
    for source in JsonSourceRepository(data_dir or resolve_data_dir()).list():
        if source['id'] not in BREEDER_SOURCE_IDS or not source.get('enabled', True) or not is_collection_eligible(source):
            continue
        discovery = source.get('discovery') or {}
        if discovery.get('adapter') not in {'article_rss', 'news_search_rss'}:
            continue
        urls = discovery.get('feed_urls') or [discovery.get('feed_url')]
        for index, url in enumerate(urls[:2]):
            if url:
                rows.append(dict(id='feed:' + source['id'] + (f':{index}' if index else ''),
                    source_id=source['id'], label=source.get('name') or source.get('label') or source['id'],
                    host=urlparse(source.get('url') or url).hostname.removeprefix('www.'), feed_url=url, adapter=discovery['adapter'],
                    geography='global', coverage='breeder_extension', registry_managed=True))
    return rows
