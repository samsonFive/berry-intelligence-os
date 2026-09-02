"""Prefer first-party publisher article URLs over wrappers and homepages.

Does not fetch Google redirect targets (that would depend on wrapper
behavior and can violate publisher terms). Uses only URLs already present
on the DiscoveryHit.
"""

from __future__ import annotations

from urllib.parse import urlparse

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


def preferred_url(hit: DiscoveryHit) -> str:
    """First-party article path, else wrapper (clickable), else any URL."""
    origin = hit.origin_publisher_url or ""
    page = hit.url or ""
    wrapper = hit.wrapper_url or ""
    for candidate in (origin, page):
        if is_article_url(candidate):
            return candidate
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
