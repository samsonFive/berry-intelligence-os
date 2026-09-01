"""Classify pulse hits with the canonical recall taxonomy.

Does not invent a tenth miss class. NOT QUALIFYING maps to
UNSUPPORTED_NOT_QUALIFYING. Wrapper hosts are not treated as the publisher.
"""

from __future__ import annotations

from typing import Any

from app.services.industry_pulse.models import DiscoveryHit
from app.services.recall_audit.classify import (
    FULLY_REPRESENTED,
    MISS_CLASSES,
    MISS_LABELS,
    SOURCE_COLLECTED_ITEM_MISSED,
    SOURCE_KNOWN_NOT_COLLECTED,
    SOURCE_UNKNOWN,
    WRAPPER_HOSTS,
    classify_result,
    hostname,
)


def classify_hit(
    hit: DiscoveryHit,
    *,
    sources: list[dict[str, Any]],
    published_evidence: list[dict[str, Any]],
    varieties: list[dict[str, Any]] | None = None,
) -> DiscoveryHit:
    domain = hit.source_domain if hit.source_domain not in WRAPPER_HOSTS else hostname(hit.origin_publisher_url)
    result = classify_result(
        {
            "qualification": "qualifying" if hit.qualifying else "not_qualifying",
            "url": hit.origin_publisher_url or hit.url,
            "domain": domain,
            "title": hit.title,
        },
        sources=sources,
        published_evidence=published_evidence,
        varieties=varieties or [],
    )
    miss = str(result.get("miss_classification") or SOURCE_UNKNOWN)
    if miss not in MISS_CLASSES:
        miss = SOURCE_UNKNOWN
    hit.miss_classification = miss
    hit.miss_label = MISS_LABELS[miss]
    hit.collection_status = str(result.get("collection_status") or "")
    hit.already_represented = miss == FULLY_REPRESENTED
    hit.known_source = miss in {
        SOURCE_KNOWN_NOT_COLLECTED,
        SOURCE_COLLECTED_ITEM_MISSED,
        FULLY_REPRESENTED,
    } or str(result.get("collection_status") or "") in {"COLLECTED", SOURCE_KNOWN_NOT_COLLECTED}
    hit.collected = str(result.get("collection_status") or "") == "COLLECTED"
    hit.novel_domain = miss == SOURCE_UNKNOWN
    return hit


def empty_miss_counts() -> dict[str, int]:
    return {key: 0 for key in MISS_CLASSES}
