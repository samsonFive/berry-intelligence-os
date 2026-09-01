"""Authoritative-source and unknown-unknown labels for bake-off metrics.

Does not onboard domains. Does not mutate trust.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from app.services.coverage_assurance.classes import (
    BREEDER_GENETICS_OWNER,
    GOVERNMENT_STATISTICAL,
    GROWER_MARKETER_ORGANIZATION,
    NURSERY_PROPAGATION_CATALOGUE,
    PBR_PVP_REGISTRY,
    PEER_REVIEWED_ACADEMIC,
    TRADE_PRESS,
    UNIVERSITY_EXTENSION,
    source_class_of,
)
from app.services.industry_pulse.models import DiscoveryHit
from app.services.recall_audit.classify import hostname, publisher_hosts

TIER1_CLASSES = frozenset({PBR_PVP_REGISTRY, GOVERNMENT_STATISTICAL, BREEDER_GENETICS_OWNER})
TIER2_CLASSES = frozenset(
    {
        UNIVERSITY_EXTENSION,
        PEER_REVIEWED_ACADEMIC,
        TRADE_PRESS,
        GROWER_MARKETER_ORGANIZATION,
        NURSERY_PROPAGATION_CATALOGUE,
    }
)

_TIER1_HOST = re.compile(
    r"("
    r"\.gov(?:\.[a-z]{2})?$|"
    r"\.gov\.uk$|"
    r"europa\.eu$|"
    r"plantvarieties\.eu$|"
    r"cpvo\.|"
    r"usda\.gov$|"
    r"uspto\.gov$|"
    r"inspection\.gc\.ca$|"
    r"agriculture\.gov\.au$|"
    r"nda\.gov\.za$|"
    r"dalrrd\.gov\.za$|"
    r"gov\.za$"
    r")",
    re.IGNORECASE,
)
_ACADEMIC_HOST = re.compile(r"(\.edu$|\.ac\.uk$|\.ac\.za$|\.edu\.au$)", re.IGNORECASE)
_CULTIVAR_DENSE = re.compile(
    r"\b("
    r"cultivar|variety list|varieties|catalogue|catalog|portfolio|"
    r"registration|plant breeders|pbr|pvp|trial result|comparison table|"
    r"breeder list"
    r")\b",
    re.IGNORECASE,
)


def source_hosts(sources: Iterable[dict[str, Any]]) -> set[str]:
    hosts: set[str] = set()
    for source in sources:
        hosts.update(publisher_hosts(source))
        host = hostname(source.get("url") or source.get("value"))
        if host:
            hosts.add(host)
    return hosts


def universe_hosts(entries: Iterable[dict[str, Any]]) -> set[str]:
    hosts: set[str] = set()
    for row in entries:
        host = hostname(row.get("hostname") or row.get("domain") or row.get("url"))
        if host:
            hosts.add(host)
    return hosts


def evidence_hosts(rows: Iterable[dict[str, Any]]) -> set[str]:
    hosts: set[str] = set()
    for row in rows:
        for key in ("canonical_url", "url", "source_url", "origin_url"):
            host = hostname(row.get(key))
            if host:
                hosts.add(host)
    return hosts


def class_by_host(sources: Iterable[dict[str, Any]], entries: Iterable[dict[str, Any]]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for row in entries:
        host = hostname(row.get("hostname") or row.get("domain"))
        klass = str(row.get("source_class") or "")
        if host and klass:
            mapping[host] = klass
    for source in sources:
        klass = source_class_of(source)
        for host in publisher_hosts(source):
            mapping.setdefault(host, klass)
    return mapping


def authority_tier(host: str, *, class_map: dict[str, str]) -> str | None:
    klass = class_map.get(host, "")
    if klass in TIER1_CLASSES or _TIER1_HOST.search(host or ""):
        return "tier1"
    if klass in TIER2_CLASSES or _ACADEMIC_HOST.search(host or ""):
        return "tier2"
    return None


def is_unknown_unknown(
    host: str,
    *,
    known_sources: set[str],
    universe: set[str],
    cited: set[str],
) -> bool:
    if not host:
        return False
    return host not in known_sources and host not in universe and host not in cited


def is_cultivar_dense(hit: DiscoveryHit) -> bool:
    return bool(_CULTIVAR_DENSE.search(f"{hit.title} {hit.snippet}"))
