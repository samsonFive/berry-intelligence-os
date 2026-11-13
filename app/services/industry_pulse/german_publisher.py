"""Bounded Fruchthandel public listing and article publication metadata."""
from datetime import datetime
import re
from urllib.parse import urljoin, urlsplit

import httpx
from lxml import html

from app.services.industry_pulse.models import DiscoveryHit
from app.services.industry_pulse.regional_news import regional_crop_ids

FEED = dict(id='feed:priority:fruchthandel:listing', label='Fruchthandel',
            host='fruchthandel.de', feed_url='https://www.fruchthandel.de/',
            geography='europe', hl='de-DE', gl='DE', ceid='DE:de',
            adapter='german_listing', route='direct_listing', source_type='trade_press',
            access_note='One public homepage plus publication metadata for at most four crop-headline links. No complete archive, body-only discovery or first-public timestamp claim.')


def _fetch(url):
    with httpx.stream('GET', url, timeout=8, follow_redirects=False,
                      headers={'User-Agent': 'BerryIntelligenceOS-Discovery/1.0'}) as response:
        response.raise_for_status()
        raw = bytearray()
        for chunk in response.iter_bytes(chunk_size=65536):
            raw.extend(chunk)
            if len(raw) > 2_000_000:
                raise ValueError('german-listing-response-limit')
    return bytes(raw)


def _text(node):
    return ' '.join(node.text_content().split())


def listing_rows(raw):
    root = html.fromstring(raw)
    rows = {}
    structure = False
    for anchor in root.xpath('//a[@href]')[:1500]:
        url = urljoin(FEED['feed_url'], anchor.get('href'))
        parsed = urlsplit(url)
        if (parsed.scheme != 'https' or parsed.netloc not in {'www.fruchthandel.de', 'fruchthandel.de'}
                or parsed.query or parsed.fragment or not re.fullmatch(r'/news/[a-z0-9-]{3,300}', parsed.path)):
            continue
        title = _text(anchor)
        structure = True
        if regional_crop_ids(title) and 15 <= len(title) <= 2000:
            rows.setdefault(url, dict(url=url, title=title))
    if not structure:
        raise ValueError('german-listing-record-structure-missing')
    return list(rows.values())[:4]


def publication_time(raw, title):
    """Only the matching main article's time, never sidebar publication dates."""
    root = html.fromstring(raw)
    for heading in root.xpath('//h1'):
        if _text(heading) != title:
            continue
        articles = heading.xpath('ancestor::article[1]')
        if not articles:
            continue
        values = articles[0].xpath('.//time/@datetime')
        if len(set(values)) != 1:
            continue
        try:
            stamp = datetime.fromisoformat(values[0].replace('Z', '+00:00'))
            if stamp.tzinfo is not None:
                return stamp.isoformat()
        except ValueError:
            pass
    return None


def listing_hits(query, *, fetch=None):
    getter = fetch or _fetch
    rows = listing_rows(getter(FEED['feed_url']))
    hits = []
    # A failed metadata request fails the route; do not report partial success.
    for row in rows:
        published = publication_time(getter(row['url']), row['title'])
        hits.append(DiscoveryHit(**row, snippet='', published_date=published,
            source_domain=FEED['host'], query_id=query.id, query_text=query.text,
            geography=query.geography, berry=None, topic='specialist_feed', provider='specialist_rss',
            origin_publisher_name=FEED['label'], origin_publisher_url=row['url'],
            provider_metadata={'publisher_route': 'direct_listing', 'publisher_source_type': 'trade_press',
                'query_edition': query.ceid, 'listing_url': FEED['feed_url'], 'listing_page_limit': 1,
                'article_metadata_limit': 4, 'date_basis': 'publisher_article_time' if published else 'unknown',
                'publisher_publication_time': published,
                'first_public_visibility': 'unknown'}))
    return hits
