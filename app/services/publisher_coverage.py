"""Bounded publisher-first discovery, private cache, no trusted-data writes.

Watershed: declared blog cards plus article JSON-LD publication dates.
Packer: exact Sustainability Insights section through configured Firecrawl,
at most two declared listing pages every six hours. No generated article text.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
import json
import hashlib
from pathlib import Path
import re
from urllib.parse import urljoin, urlsplit

import httpx
from lxml import html, etree

from app.services.analyst_state_io import atomic_json
from app.services.firecrawl_reader import PACKER_SECTION, _scrape, _publisher_url
from app.services.industry_pulse.credentials import env_key, FIRECRAWL_API_KEY_ENV

CONFIG = {
    'feed:watershed-blog': ('watershed.com', 'https://watershed.com/blog', 3600),
    'feed:packer-sustainability-insights': ('thepacker.com', PACKER_SECTION, 21600),
}


def _read(path):
    try:
        if path.stat().st_size > 1_000_000:
            return {}
        row = json.loads(path.read_text(encoding='utf-8'))
        return row if isinstance(row, dict) else {}
    except (OSError, ValueError):
        return {}


def cache_path(inbox_dir, query_id):
    return Path(inbox_dir) / 'operations/publisher_coverage' / (CONFIG[query_id][0] + '.json')


def cached_articles(inbox_dir, query_id):
    if inbox_dir is None or query_id not in CONFIG:
        return []
    data = _read(cache_path(inbox_dir, query_id))
    try:
        age = (datetime.now(UTC) - datetime.fromisoformat(data['last_success_at'])).total_seconds()
    except (KeyError, ValueError, TypeError):
        return []
    if data.get('version') != 1 or not 0 <= age <= 86400:
        return []
    host = CONFIG[query_id][0]
    return [row for row in data.get('articles', []) if _publisher_url(row.get('url'), host, article=True)]


def fetch_html(http, url):
    with http.stream('GET', url, timeout=12, follow_redirects=False,
                     headers={'User-Agent': 'BerryIntelligenceOS-Discovery/1.0'}) as response:
        response.raise_for_status()
        raw = bytearray()
        for part in response.iter_bytes(chunk_size=65536):
            raw.extend(part)
            if len(raw) > 2_000_000:
                raise ValueError('publisher-response-limit')
    return raw.decode('utf-8', errors='replace')


def watershed_links(markup):
    return list(watershed_cards(markup))


def watershed_cards(markup):
    tree = html.fromstring(markup)
    links = {}
    for anchor in tree.xpath('//a[@href]'):
        url = urljoin(CONFIG['feed:watershed-blog'][1], anchor.get('href'))
        p = urlsplit(url)
        headings = anchor.xpath('.//h2|.//h3')
        if p.hostname != 'watershed.com' or not re.fullmatch(r'/blog/[^/?#]+', p.path) or not headings:
            continue
        if url not in links and len(links) < 24:
            stamp = ' '.join(anchor.xpath('.//time/@datetime')) + anchor.text_content()
            links[url] = hashlib.sha256(stamp.encode('utf-8')).hexdigest()
    return links


def article_metadata(markup, url):
    tree = html.fromstring(markup)
    for node in tree.xpath('//script[@type="application/ld+json"]'):
        try:
            data = json.loads(node.text or '')
        except ValueError:
            continue
        rows = data if isinstance(data, list) else [data]
        rows = [r for r in rows if isinstance(r, dict)]
        rows += [r for row in list(rows) for r in row.get('@graph', []) if isinstance(r, dict)]
        for row in rows:
            types = row.get('@type') or []
            if isinstance(types, str):
                types = [types]
            if not set(types).intersection({'Article', 'BlogPosting', 'NewsArticle'}):
                continue
            main = row.get('mainEntityOfPage') or {}
            declared = row.get('url') or (main.get('@id') if isinstance(main, dict) else main)
            if _publisher_url(declared, 'watershed.com', article=True) != url:
                continue
            try:
                day = datetime.fromisoformat(str(row.get('datePublished') or '').replace('Z', '+00:00')).date().isoformat()
            except ValueError:
                continue
            title = str(row.get('headline') or '').strip()
            if title:
                return {'url': url, 'title': title, 'published_date': day,
                    'date_basis': 'publisher_jsonld_datePublished', 'snippet': str(row.get('description') or '')[:2000]}
    return None


def packer_cards(markup):
    tree = html.fromstring(markup)
    rows = {}
    for card in tree.xpath('//*[contains(concat(" ",normalize-space(@class)," ")," PagePromo ")]'):
        links = card.xpath('.//*[contains(@class,"PagePromo-title")]//a[@href]')
        dates = card.xpath('.//*[contains(@class,"PagePromo-date")]')
        if not links or not dates:
            continue
        url = _publisher_url(urljoin(PACKER_SECTION, links[0].get('href')), 'thepacker.com', article=True)
        if not url or not urlsplit(url).path.startswith('/news/'):
            continue
        stamp = dates[0].text_content().strip()
        try:
            day = datetime.strptime(stamp, '%B %d, %Y %I:%M %p').date().isoformat()
        except ValueError:
            continue
        title = links[0].text_content().strip()
        descriptions = card.xpath('.//*[contains(@class,"PagePromo-description")]')
        if title:
            rows[url] = {'url': url, 'title': title, 'published_date': day,
                'date_basis': 'publisher_section_display_date',
                'snippet': descriptions[0].text_content().strip()[:2000] if descriptions else ''}
    next_url = ''
    for anchor in tree.xpath('//a[@href]'):
        label = ' '.join([anchor.get('rel') or '', anchor.get('aria-label') or '', anchor.text_content().strip()]).casefold()
        if label not in {'next', 'next page'}:
            continue
        target = _publisher_url(urljoin(PACKER_SECTION, anchor.get('href')), 'thepacker.com')
        if target and urlsplit(target).path == urlsplit(PACKER_SECTION).path:
            next_url = target
            break
    return list(rows.values())[:80], next_url


def refresh_publisher_coverage(inbox_dir, *, client=None, force=False):
    http = client or httpx.Client(follow_redirects=False)
    reports = []
    try:
        for query_id, (host, listing, cadence) in CONFIG.items():
            path = cache_path(inbox_dir, query_id)
            prior = _read(path)
            now = datetime.now(UTC)
            try:
                age = (now - datetime.fromisoformat(prior['checked_at'])).total_seconds()
            except (KeyError, ValueError):
                age = cadence
            if not force and prior.get('version') == 1 and 0 <= age < cadence:
                reports.append(prior)
                continue
            report = {**prior, 'version': 1, 'query_id': query_id, 'checked_at': now.isoformat(), 'listing_url': listing}
            try:
                failures = 0
                if host == 'watershed.com':
                    cards = watershed_cards(fetch_html(http, listing))
                    known = {r['url']: r for r in prior.get('articles', [])}
                    def metadata(url):
                        if known.get(url, {}).get('listing_signature') == cards[url]:
                            return known[url]
                        try:
                            row = article_metadata(fetch_html(http, url), url)
                            return {**row, 'listing_signature': cards[url]} if row else None
                        except (httpx.HTTPError, ValueError, TypeError, etree.ParserError):
                            return None
                    with ThreadPoolExecutor(max_workers=4) as pool:
                        found = list(pool.map(metadata, cards))
                    failures = sum(row is None for row in found)
                    articles = [row for row in found if row]
                else:
                    key = env_key(FIRECRAWL_API_KEY_ENV)
                    if not key:
                        raise ValueError('connection-not-configured')
                    articles, target, seen = [], listing, set()
                    for _ in range(2):
                        if not target or target in seen:
                            break
                        seen.add(target)
                        page = _scrape(http, target, key, listing=True, publisher_host=host)
                        if not page:
                            failures += 1
                            break
                        rows, target = packer_cards(page['html'])
                        articles.extend(rows)
                if not articles:
                    raise ValueError('no-verified-publisher-articles')
                merged = {r['url']: r for r in prior.get('articles', []) if _publisher_url(r.get('url'), host, article=True)}
                merged.update({r['url']: r for r in articles})
                report.update(status='partial' if failures else 'ready', last_success_at=now.isoformat(),
                    articles=sorted(merged.values(), key=lambda r: r['published_date'], reverse=True)[:80],
                    failure_count=failures, error_class=None, coverage_limit='Bounded publisher listing, not exhaustive archive recall.')
            except (httpx.HTTPError, ValueError, TypeError, etree.ParserError) as exc:
                report.update(status='failed', failure_count=1, error_class=type(exc).__name__)
            atomic_json(path, report)
            reports.append(report)
    finally:
        if client is None:
            http.close()
    return reports


def cached_publisher_target(inbox_dir, record):
    """Resolve one recorded Google title against verified publisher discovery."""
    from app.services.publisher_link_resolution import publisher_headlines_match
    from app.services.google_news_url import is_google_news_wrapper
    if not is_google_news_wrapper(record.get('source_url') or ''):
        return ''
    from app.services.feed_first_reader import is_public_http_url
    if not is_public_http_url(record.get('origin_publisher_url') or ''):
        return ''
    host = (urlsplit(record.get('origin_publisher_url') or '').hostname or '').removeprefix('www.')
    found = set()
    for query_id, (domain, _, _) in CONFIG.items():
        if host != domain:
            continue
        for row in cached_articles(inbox_dir, query_id):
            if any(publisher_headlines_match(record.get('title'), row['title'], name, min_words=3)
                   for name in ('The Packer', 'watershed.com', 'Watershed', record.get('source_name') or '')):
                found.add(row['url'])
    return next(iter(found)) if len(found) == 1 else ''
