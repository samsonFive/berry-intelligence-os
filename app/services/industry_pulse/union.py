"""Union/dedup across discovery providers. Does not onboard Sources."""

from __future__ import annotations

from app.services.industry_pulse.dedup import identity_key
from app.services.industry_pulse.models import DiscoveryHit


def union_hits(
    left: list[DiscoveryHit],
    right: list[DiscoveryHit],
    *,
    left_name: str,
    right_name: str,
) -> dict[str, object]:
    left_map: dict[str, DiscoveryHit] = {}
    for hit in left:
        left_map.setdefault(identity_key(hit), hit)
    right_map: dict[str, DiscoveryHit] = {}
    for hit in right:
        right_map.setdefault(identity_key(hit), hit)
    both_keys = sorted(left_map.keys() & right_map.keys())
    only_left = sorted(left_map.keys() - right_map.keys())
    only_right = sorted(right_map.keys() - left_map.keys())
    left_hosts = {hit.source_domain for hit in left_map.values() if hit.source_domain}
    right_hosts = {hit.source_domain for hit in right_map.values() if hit.source_domain}
    both_hosts = sorted(left_hosts & right_hosts)
    return {
        "left_provider": left_name,
        "right_provider": right_name,
        "left_unique": len(left_map),
        "right_unique": len(right_map),
        "both": len(both_keys),
        "only_left": len(only_left),
        "only_right": len(only_right),
        "both_urls": [_hit_url(left_map[key]) for key in both_keys[:50]],
        "only_left_urls": [_hit_url(left_map[key]) for key in only_left[:50]],
        "only_right_urls": [_hit_url(right_map[key]) for key in only_right[:50]],
        "left_hosts": len(left_hosts),
        "right_hosts": len(right_hosts),
        "both_hosts": len(both_hosts),
        "only_left_hosts": len(left_hosts - right_hosts),
        "only_right_hosts": len(right_hosts - left_hosts),
        "both_host_names": both_hosts[:40],
    }


def _hit_url(hit: DiscoveryHit) -> str:
    for value in (hit.origin_publisher_url, hit.url, hit.wrapper_url):
        if value and "://" in str(value):
            return str(value)
    return hit.url or hit.source_domain
