"""Deduplicate pulse hits without collapsing distinct reporting.

Same canonical URL, Google News wrapper of the same publisher URL, and
same origin+title+date across queries are one story. Different publishers
with similar titles stay separate. When the same story is found by both a
global query and a regional query, keep the regional attribution.
"""

from __future__ import annotations

from urllib.parse import urlparse

from app.services.article_dedup import normalize_canonical_url, normalize_title
from app.services.industry_pulse.canonical_urls import is_article_url, is_homepage, is_wrapper, url_quality
from app.services.industry_pulse.models import DiscoveryHit
from app.services.recall_audit.classify import WRAPPER_HOSTS, hostname


def _is_homepage(url: str) -> bool:
    parsed = urlparse(url if "://" in url else f"https://{url}")
    return parsed.path in {"", "/"}

GEO_SPECIFICITY = {
    "global": 0,
    "americas": 1,
    "europe": 1,
    "africa": 1,
    "apac": 1,
}


def identity_key(hit: DiscoveryHit) -> str:
    publisher = normalize_canonical_url(hit.origin_publisher_url or "")
    if publisher and hostname(publisher) not in WRAPPER_HOSTS and not _is_homepage(publisher):
        return f"url:{publisher}"
    canonical = normalize_canonical_url(hit.url)
    if canonical and hostname(canonical) not in WRAPPER_HOSTS and not _is_homepage(canonical):
        return f"url:{canonical}"
    wrapper = normalize_canonical_url(hit.wrapper_url or "")
    if wrapper:
        return f"wrapper:{wrapper}"
    title = normalize_title(hit.title)
    domain = (hit.source_domain or "").lower().removeprefix("www.")
    day = (hit.published_date or "")[:10]
    if title and domain and day:
        return f"story:{domain}:{title}:{day}"
    return f"loose:{domain}:{title}:{canonical or wrapper or hit.title}"


def _more_specific(left: DiscoveryHit, right: DiscoveryHit) -> bool:
    left_quality = url_quality(left)
    right_quality = url_quality(right)
    if left_quality != right_quality:
        return left_quality > right_quality
    return GEO_SPECIFICITY.get(left.geography, 0) > GEO_SPECIFICITY.get(right.geography, 0)


def dedupe_hits(hits: list[DiscoveryHit]) -> list[DiscoveryHit]:
    """Collapse identical stories. Prefer a regional geography over global."""
    best: dict[str, DiscoveryHit] = {}
    for hit in hits:
        key = identity_key(hit)
        prior = best.get(key)
        if prior is None:
            hit.duplicate_of = None
            best[key] = hit
            continue
        if _more_specific(hit, prior):
            prior.duplicate_of = key
            hit.duplicate_of = None
            best[key] = hit
        else:
            hit.duplicate_of = key
    return hits


def _story_key(hit: DiscoveryHit) -> str | None:
    title = normalize_title(hit.title)
    domain = hostname(hit.origin_publisher_url or "") or (hit.source_domain or "").lower().removeprefix("www.")
    if domain in WRAPPER_HOSTS:
        domain = (hit.source_domain or "").lower().removeprefix("www.")
    day = (hit.published_date or "")[:10]
    if title and domain and day and domain not in WRAPPER_HOSTS:
        return f"story:{domain}:{title}:{day}"
    return None


def _weak_url(hit: DiscoveryHit) -> bool:
    origin = hit.origin_publisher_url or hit.url
    return is_homepage(origin) or is_wrapper(origin) or is_wrapper(hit.url) or is_wrapper(hit.wrapper_url)


def unique_hits(hits: list[DiscoveryHit]) -> list[DiscoveryHit]:
    """Keep distinct first-party articles. Collapse only wrapper/homepage twins."""
    survivors = [hit for hit in hits if not hit.duplicate_of]
    best: dict[str, DiscoveryHit] = {}
    leftover: list[DiscoveryHit] = []
    for hit in survivors:
        key = _story_key(hit)
        if not key:
            leftover.append(hit)
            continue
        prior = best.get(key)
        if prior is None:
            best[key] = hit
            continue
        if is_article_url(hit.origin_publisher_url or hit.url) and is_article_url(
            prior.origin_publisher_url or prior.url
        ):
            leftover.append(hit)
            continue
        if not (_weak_url(hit) or _weak_url(prior)):
            leftover.append(hit)
            continue
        if _more_specific(hit, prior):
            prior.duplicate_of = key
            best[key] = hit
        else:
            hit.duplicate_of = key
    return [hit for hit in [*best.values(), *leftover] if not hit.duplicate_of]
