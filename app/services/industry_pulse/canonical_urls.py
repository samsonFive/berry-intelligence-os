"""Prefer first-party publisher article URLs over wrappers and homepages.

Does not call an undocumented Google endpoint and does not fetch wrapper
HTML as an article. Local token decode (google_news_url) may recover a
publisher article path already encoded in a Google News RSS link.
"""

from __future__ import annotations

from urllib.parse import urlparse

from app.services.google_news_url import is_google_news_wrapper, resolve_google_news_url
from app.services.industry_pulse.models import DiscoveryHit
from app.services.recall_audit.classify import WRAPPER_HOSTS, hostname


def is_homepage(url: str | None) -> bool:
    if not url:
        return True
    parsed = urlparse(url if "://" in url else f"https://{url}")
    return parsed.path in {"", "/"}


def is_wrapper(url: str | None) -> bool:
    return bool(url) and hostname(url) in WRAPPER_HOSTS


def is_article_url(url: str | None) -> bool:
    return bool(url) and not is_wrapper(url) and not is_homepage(url)


def _decoded_article_url(url: str | None) -> str | None:
    if not url:
        return None
    resolved = resolve_google_news_url(url) if (is_wrapper(url) or is_google_news_wrapper(url)) else url
    return resolved if is_article_url(resolved) else None


def preferred_url(hit: DiscoveryHit) -> str:
    """Publisher article path, else decoded wrapper, else wrapper.

    Never returns a homepage when a wrapper exists. A homepage Google
    `<source>` tag is publisher identity, not the article.
    """
    origin = hit.origin_publisher_url or ""
    page = hit.url or ""
    wrapper = hit.wrapper_url or ""
    decoded = _decoded_article_url(wrapper) or _decoded_article_url(page) or _decoded_article_url(origin)
    for candidate in (origin, page, decoded or ""):
        if is_article_url(candidate):
            return candidate
    if decoded:
        return decoded
    if wrapper:
        return wrapper
    return origin or page or wrapper


def url_quality(hit: DiscoveryHit) -> int:
    """Higher is better. Used when collapsing the same story."""
    origin = hit.origin_publisher_url or hit.url
    score = 0
    if is_article_url(origin):
        score += 4
    if hit.provider == "specialist_rss":
        score += 2
    if not is_wrapper(hit.url) and not is_wrapper(origin):
        score += 1
    if is_homepage(origin) and is_wrapper(hit.wrapper_url or hit.url):
        score -= 1
    return score
