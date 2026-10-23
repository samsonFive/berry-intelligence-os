"""Bounded, opt-in Packer retrieval through the operator's Firecrawl connection.

Selected stories only. No crawl, generated text, publication or trust changes.
"""
from datetime import UTC, datetime
import json
from urllib.parse import urlsplit, urlunsplit

import httpx
from lxml import etree, html as html_parser

from app.services.industry_pulse.credentials import env_key, FIRECRAWL_API_KEY_ENV
from app.services.publisher_link_resolution import publisher_article_link, publisher_headlines_match

ENDPOINT = "https://api.firecrawl.dev/v2/scrape"
PACKER_SECTION = "https://www.thepacker.com/topics/sustainability-insights"
MAX_RESPONSE_BYTES = 1_000_000


def _packer_url(url, *, article=False):
    from app.services.feed_first_reader import is_public_http_url
    if not is_public_http_url(str(url or "")):
        return ""
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname not in {"thepacker.com", "www.thepacker.com"}
            or parsed.port not in {None, 443}):
        return ""
    if article and (not parsed.path.startswith("/news/") or len(parsed.path.rstrip('/').split('/')) < 3):
        return ""
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def _scrape(http, url, key, *, fresh=False, listing=False, publisher_host=None):
    body = {"url": url, "formats": ["html"], "onlyMainContent": True,
            "timeout": 20000, "maxAge": 0 if fresh else 900000 if listing else 86400000}
    with http.stream("POST", ENDPOINT, json=body,
                     headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
                     timeout=25.0) as response:
        if response.status_code != 200:
            return None
        raw = bytearray()
        for chunk in response.iter_bytes(chunk_size=65536):
            raw.extend(chunk)
            if len(raw) > MAX_RESPONSE_BYTES:
                return None
    payload = json.loads(raw)
    if not isinstance(payload, dict) or payload.get("success") is not True:
        return None
    page = payload.get("data")
    if not isinstance(page, dict) or not isinstance(page.get("html"), str):
        return None
    metadata = page.get("metadata") or {}
    if not isinstance(metadata, dict) or metadata.get("statusCode") != 200:
        return None
    if not any(metadata.get(field) for field in ("sourceURL", "url", "ogUrl")):
        return None
    for field in ("sourceURL", "url", "ogUrl"):
        final = metadata.get(field)
        checked = _publisher_url(final, publisher_host) if publisher_host else _packer_url(final)
        if final and (not checked or urlsplit(checked).path.rstrip('/') != urlsplit(url).path.rstrip('/')
                      or urlsplit(checked).query != urlsplit(url).query):
            # The API must not silently return a homepage, redirect or another story.
            return None
    return page


def capture_packer_article(record, *, client=None, refresh=False):
    """At most one approved listing and one exact article; failures stay honest."""
    from app.services.feed_first_reader import (
        classify_capture, extract_article_images, paragraphs_from_html, is_public_http_url,
    )
    from app.services.google_news_url import is_google_news_wrapper
    source = str(record.get("source_url") or "")
    origin = str(record.get("origin_publisher_url") or "")
    if not is_public_http_url(source):
        return None
    if not (_packer_url(source) or (is_google_news_wrapper(source) and _packer_url(origin))):
        return None
    key = env_key(FIRECRAWL_API_KEY_ENV)
    if not key or not publisher_headlines_match(record.get("title"), record.get("title"), "The Packer"):
        return None
    http = client or httpx.Client(follow_redirects=False)
    try:
        target = _packer_url(source, article=True) or _packer_url(origin, article=True)
        if not target:
            listing = _scrape(http, PACKER_SECTION, key, fresh=refresh, listing=True)
            if not listing:
                return None
            target = _packer_url(publisher_article_link(
                listing["html"], PACKER_SECTION, record.get("title"), "The Packer"), article=True)
        if not target:
            return None
        page = _scrape(http, target, key, fresh=refresh)
        if not page:
            return None
        tree = html_parser.fromstring(page["html"])
        headings = tree.xpath("//h1")
        headline = headings[0].text_content() if headings else (page.get("metadata") or {}).get("title", "")
        if not publisher_headlines_match(record.get("title"), headline, "The Packer"):
            return None
        roots = tree.xpath("//*[contains(concat(' ', normalize-space(@class), ' '), ' RichTextArticleBody ')]")
        article_html = html_parser.tostring(roots[0], encoding="unicode") if len(roots) == 1 else page["html"]
        passages = paragraphs_from_html(article_html, limit=None)
        uncertain_structure = len(roots) != 1
        limited = len(passages) > 256 or bool(page.get("warning")) or uncertain_structure
        passages = passages[:256]
        availability = classify_capture(passages, status_code=200)
        if availability not in {"full", "partial", "excerpt_only"}:
            return None
        if limited and availability == "full":
            availability = "partial"
        from app.services.article_structure import publisher_heading_levels
        levels = publisher_heading_levels(article_html, passages)
        return {"url": target, "ok": True, "availability": availability,
                "reason": "publisher-body-structure-uncertain" if uncertain_structure else "api-content-warning" if page.get("warning") else "article-text-limit" if limited else "", "truncated": limited,
                "headline": headline.strip(), "passages": passages,
                "heading_levels": {str(i): level for i, level in levels.items()},
                "images": extract_article_images(article_html), "content_kind": "article",
                "frame_allowed": False, "reader_modes": ["native", "structured_fallback"],
                "method": "firecrawl", "retrieved_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "status_code": 200}
    except (httpx.HTTPError, ValueError, TypeError, etree.ParserError):
        # Never expose provider errors, credentials or generated substitutes in the reader.
        return None
    finally:
        if client is None:
            http.close()


def _publisher_url(url, host, *, article=False):
    from app.services.feed_first_reader import is_public_http_url
    from app.services.article_dedup import normalize_canonical_url
    if not host or not is_public_http_url(str(url or '')):
        return ''
    p = urlsplit(url)
    if (p.scheme != 'https' or p.port not in {None, 443}
            or (p.hostname or '').removeprefix('www.') != host.removeprefix('www.')
            or (p.hostname or '').endswith('.google.com')
            or (article and (p.path in {'', '/'} or p.path.lower().endswith('.pdf')))):
        return ''
    return urlunsplit((p.scheme, p.netloc, p.path or '/', p.query, ''))


def capture_publisher_article(record, *, client=None, refresh=False):
    """Selected public publisher only; at most one listing and one article.

    Exact URL, publisher and headline must agree. No generated cleanup, guessed
    article, paywall/login text, cross-domain redirect or trust changes.
    """
    from app.services.feed_first_reader import (
        is_public_http_url, paragraphs_from_html, classify_capture, extract_article_images,
    )
    from app.services.google_news_url import is_google_news_wrapper
    source = str(record.get('source_url') or '')
    origin = str(record.get('origin_publisher_url') or '')
    if not is_public_http_url(source):
        return None
    if _packer_url(source) or (is_google_news_wrapper(source) and _packer_url(origin)):
        return capture_packer_article(record, client=client, refresh=refresh)
    home = origin if is_google_news_wrapper(source) else source
    if not is_public_http_url(home):
        return None
    host = urlsplit(home).hostname or ''
    target = _publisher_url(home, host, article=True)
    key = env_key(FIRECRAWL_API_KEY_ENV)
    if not key or not _publisher_url(home, host):
        return None
    name = str(record.get('source_name') or host)
    http = client or httpx.Client(follow_redirects=False)
    try:
        if not target:
            page = _scrape(http, home, key, listing=True, publisher_host=host)
            if not page:
                return None
            target = _publisher_url(publisher_article_link(page['html'], home, record.get('title'), name), host, article=True)
        if not target:
            return None
        page = _scrape(http, target, key, fresh=refresh, publisher_host=host)
        if not page:
            return None
        tree = html_parser.fromstring(page['html'])
        headings = tree.xpath('//h1')
        headline = headings[0].text_content() if headings else ''
        if not publisher_headlines_match(record.get('title'), headline, name, min_words=3):
            return None
        roots = tree.xpath('//article')
        if len(roots) != 1:
            roots = tree.xpath('//main')
        certain = len(roots) == 1
        body = roots[0] if certain else tree
        for node in body.xpath('.//nav|.//footer|.//aside|.//form|.//script|.//style|.//*[@role="dialog"]'):
            node.drop_tree()
        article_html = html_parser.tostring(body, encoding='unicode')
        passages = paragraphs_from_html(article_html, limit=None)
        limited = not certain or bool(page.get('warning')) or len(passages) > 256
        passages = passages[:256]
        availability = classify_capture(passages, status_code=200)
        if availability not in {'full', 'partial', 'excerpt_only'}:
            return None
        if limited and availability == 'full':
            availability = 'partial'
        from app.services.article_structure import publisher_heading_levels
        levels = publisher_heading_levels(article_html, passages)
        return {'url': target, 'ok': True, 'availability': availability,
            'reason': 'publisher-body-structure-uncertain' if not certain else 'api-content-warning' if limited else '',
            'truncated': limited, 'headline': headline.strip(), 'passages': passages,
            'heading_levels': {str(i): level for i, level in levels.items()},
            'images': extract_article_images(article_html), 'content_kind': 'article',
            'frame_allowed': False, 'reader_modes': ['native', 'structured_fallback'],
            'method': 'firecrawl', 'retrieved_at': datetime.now(UTC).isoformat(timespec='seconds'), 'status_code': 200}
    except (httpx.HTTPError, ValueError, TypeError, etree.ParserError):
        return None
    finally:
        if client is None:
            http.close()
