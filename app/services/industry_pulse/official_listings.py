"""Bounded public Chile/Peru listings; metadata discovery, never source approval."""
from datetime import date
import re
from urllib.parse import quote, urljoin, urlsplit

import httpx
from lxml import html

from app.services.industry_pulse.models import DiscoveryHit


def official_listing_feeds():
    common = dict(geography='americas', adapter='official_listing', route='direct_listing',
                  source_type='government_document', hl='es-419')
    return [
        dict(common, id='feed:priority:chile-sag:listing', label='Chile SAG official news',
             host='sag.gob.cl', gl='CL', ceid='CL:es', feed_url='https://www.sag.gob.cl/noticias',
             access_note='Four native crop title filters, one page each (up to 12 cards per crop). Publisher listing dates; no complete archive or body-only discovery claim.'),
        dict(common, id='feed:priority:peru-senasa-news:listing', label='Peru SENASA official news',
             host='gob.pe', gl='PE', ceid='PE:es', feed_url='https://www.gob.pe/institucion/senasa/noticias',
             access_note='First two public listing pages. Original title, description and publisher day only; first-public visibility unknown.'),
        dict(common, id='feed:priority:peru-senasa-rules:listing', label='Peru SENASA legal records',
             host='gob.pe', gl='PE', ceid='PE:es', feed_url='https://www.gob.pe/institucion/senasa/normas-legales',
             access_note='First two public listing pages; crop-bearing descriptions retained beneath generic resolution titles. Publication day is not effective date or verified first-public visibility.'),
    ]


def _fetch(url):
    with httpx.stream('GET', url, timeout=8, follow_redirects=False,
                      headers={'User-Agent': 'BerryIntelligenceOS-Discovery/1.0'}) as response:
        response.raise_for_status()
        raw = bytearray()
        for chunk in response.iter_bytes(chunk_size=65536):
            raw.extend(chunk)
            if len(raw) > 2_000_000:
                raise ValueError('official-listing-response-limit')
    return bytes(raw)


def _text(node):
    return ' '.join(node.text_content().split()) if node is not None else ''


def _day(value):
    try:
        return date.fromisoformat(value[:10]).isoformat()
    except ValueError:
        return None


MONTHS = {name: i for i, names in enumerate((
    ('enero', 'january'), ('febrero', 'february'), ('marzo', 'march'),
    ('abril', 'april'), ('mayo', 'may'), ('junio', 'june'), ('julio', 'july'),
    ('agosto', 'august'), ('septiembre', 'september'), ('octubre', 'october'),
    ('noviembre', 'november'), ('diciembre', 'december')), 1) for name in names}


def _sag_day(value):
    match = re.fullmatch(r'(\d{1,2}) de (\w+) (\d{4})', value.casefold())
    if match and match[2] in MONTHS:
        try:
            return date(int(match[3]), MONTHS[match[2]], int(match[1])).isoformat()
        except ValueError:
            pass
    return None


def _safe_link(value, feed):
    url = urljoin(feed['feed_url'], value)
    try:
        parsed = urlsplit(url)
        if (parsed.scheme != 'https' or parsed.hostname != 'www.' + feed['host']
                or parsed.username or parsed.password or parsed.port not in {None, 443}
                or parsed.query or parsed.fragment):
            return None
    except ValueError:
        return None
    prefix = '/noticias/' if feed['host'] == 'sag.gob.cl' else urlsplit(feed['feed_url']).path + '/'
    slug = parsed.path.removeprefix(prefix)
    if not parsed.path.startswith(prefix) or not slug or '/' in slug:
        return None
    if feed['host'] == 'gob.pe' and not re.match(r'^\d+-', slug):
        return None
    return url


def parse_listing(raw, feed):
    """Associate each date/description with its own card, excluding navigation."""
    if len(raw) > 2_000_000:
        raise ValueError('official-listing-response-limit')
    root = html.fromstring(raw.decode('utf-8'), parser=html.HTMLParser(no_network=True))
    for junk in root.xpath('//script|//style|//noscript'):
        junk.drop_tree()
    rows = []
    if feed['host'] == 'sag.gob.cl':
        cards = root.xpath('//a[@role="article"]')
        for card in cards[:100]:
            title = card.xpath('.//h5')
            stamp = card.xpath('.//*[contains(concat(" ", normalize-space(@class), " "), " sag_title--date ")]')
            description = card.xpath('.//p')
            rows.append((card.get('href', ''), _text(title[0]) if title else '',
                         _text(description[0]) if description else '',
                         _sag_day(_text(stamp[0])) if stamp else None))
    else:
        cards = root.xpath('//time[@datetime]')
        for stamp in cards[:100]:
            # News cards and legal list rows have different wrappers. Stop at
            # the nearest ancestor containing a record link, never a whole page.
            for card in stamp.iterancestors():
                links = card.xpath('.//a[@href]')
                links = [link for link in links if _safe_link(link.get('href', ''), feed)]
                if not links:
                    continue
                title = next((link for link in links if _text(link) not in {'Leer más', ''}), None)
                if title is None:
                    break
                descriptions = card.xpath('.//*[@id and (starts-with(@id,"p-filter-item-") or substring(@id,string-length(@id)-11)="-description")]')
                rows.append((title.get('href', ''), _text(title),
                             _text(descriptions[0]) if descriptions else '', _day(stamp.get('datetime', ''))))
                break
    if not cards:
        # A login, challenge or changed layout must not masquerade as an empty
        # successful check. Native crop queries may legitimately return no rows.
        if feed['host'] != 'sag.gob.cl' or not root.xpath('//*[contains(@class,"view-empty")]'):
            raise ValueError('official-listing-record-structure-missing')
    unique = {}
    for target, title, snippet, published in rows:
        url = _safe_link(target, feed)
        if url and title:
            unique.setdefault(url, dict(url=url, title=title[:2000], snippet=snippet[:4000], published_date=published))
    if rows and not unique:
        raise ValueError('official-listing-no-valid-records')
    return list(unique.values())


def listing_hits(query, *, fetch=None):
    feed = next(row for row in official_listing_feeds() if row['id'] == query.id)
    if feed['host'] == 'sag.gob.cl':
        targets = [feed['feed_url'] + '?title=' + quote(crop)
                   for crop in ('arándano', 'frutilla', 'frambuesa', 'zarzamora')]
    else:
        targets = [feed['feed_url'], feed['feed_url'] + '?sheet=2']
    hits = {}
    # Fixed URLs only: no publisher-provided pagination or off-host redirects.
    # Fail the route if a bounded page fails; never report partial success as
    # a successful all-pages check.
    for target in targets:
        raw = (fetch or _fetch)(target)
        for row in parse_listing(raw, feed):
            hits.setdefault(row['url'], DiscoveryHit(**row, source_domain=feed['host'],
                query_id=query.id, query_text=query.text, geography=query.geography,
                berry=None, topic='specialist_feed', provider='specialist_rss',
                origin_publisher_name=feed['label'], origin_publisher_url=row['url'],
                provider_metadata={'publisher_route': 'direct_listing',
                    'publisher_source_type': 'government_document', 'query_edition': query.ceid,
                    'date_basis': 'publisher_listing_day' if row['published_date'] else 'unknown', 'listing_url': target,
                    'listing_page_limit': len(targets), 'first_public_visibility': 'unknown'}))
    return list(hits.values())
