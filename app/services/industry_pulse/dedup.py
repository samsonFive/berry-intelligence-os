"""Deduplicate pulse hits without collapsing distinct reporting.

Same canonical URL, Google News wrapper of the same publisher URL, and
same origin+title+date across queries are one story. Different publishers
with similar titles stay separate. When the same story is found by both a
global query and a regional query, keep the regional attribution.
"""

from __future__ import annotations

from app.services.article_dedup import normalize_canonical_url, normalize_title
from app.services.industry_pulse.models import DiscoveryHit
from app.services.recall_audit.classify import WRAPPER_HOSTS, hostname

GEO_SPECIFICITY = {
    "global": 0,
    "americas": 1,
    "europe": 1,
    "africa": 1,
    "apac": 1,
}


def identity_key(hit: DiscoveryHit) -> str:
    publisher = normalize_canonical_url(hit.origin_publisher_url or "")
    if publisher and hostname(publisher) not in WRAPPER_HOSTS:
        return f"url:{publisher}"
    canonical = normalize_canonical_url(hit.url)
    if canonical and hostname(canonical) not in WRAPPER_HOSTS:
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


def unique_hits(hits: list[DiscoveryHit]) -> list[DiscoveryHit]:
    return [hit for hit in hits if not hit.duplicate_of]
