"""Independent missed-intelligence recall classification.

A coverage *test*, not a monitor. Does not write Sources, Evidence, or
trusted Varieties. Miss labels are derived from the live corpus plus
explicit match pointers on each benchmark result.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from app.services.source_lifecycle import is_collection_eligible

WRAPPER_HOSTS = frozenset({"news.google.com"})

SOURCE_UNKNOWN = "SOURCE_UNKNOWN"
SOURCE_KNOWN_NOT_COLLECTED = "SOURCE_KNOWN_NOT_COLLECTED"
SOURCE_COLLECTED_ITEM_MISSED = "SOURCE_COLLECTED_ITEM_MISSED"
ITEM_COLLECTED_ENTITY_MISSED = "ITEM_COLLECTED_ENTITY_MISSED"
ENTITY_FOUND_IDENTITY_UNRESOLVED = "ENTITY_FOUND_IDENTITY_UNRESOLVED"
DATE_CHRONOLOGY_FAILURE = "DATE_CHRONOLOGY_FAILURE"
GEOGRAPHY_LINKAGE_FAILURE = "GEOGRAPHY_LINKAGE_FAILURE"
FULLY_REPRESENTED = "FULLY_REPRESENTED"
UNSUPPORTED_NOT_QUALIFYING = "UNSUPPORTED_NOT_QUALIFYING"

MISS_CLASSES = (
    SOURCE_UNKNOWN,
    SOURCE_KNOWN_NOT_COLLECTED,
    SOURCE_COLLECTED_ITEM_MISSED,
    ITEM_COLLECTED_ENTITY_MISSED,
    ENTITY_FOUND_IDENTITY_UNRESOLVED,
    DATE_CHRONOLOGY_FAILURE,
    GEOGRAPHY_LINKAGE_FAILURE,
    FULLY_REPRESENTED,
    UNSUPPORTED_NOT_QUALIFYING,
)

MISS_LABELS = {
    SOURCE_UNKNOWN: "SOURCE UNKNOWN",
    SOURCE_KNOWN_NOT_COLLECTED: "SOURCE KNOWN, NOT COLLECTED",
    SOURCE_COLLECTED_ITEM_MISSED: "SOURCE COLLECTED, ITEM MISSED",
    ITEM_COLLECTED_ENTITY_MISSED: "ITEM COLLECTED, ENTITY MISSED",
    ENTITY_FOUND_IDENTITY_UNRESOLVED: "ENTITY FOUND, IDENTITY UNRESOLVED",
    DATE_CHRONOLOGY_FAILURE: "DATE/CHRONOLOGY FAILURE",
    GEOGRAPHY_LINKAGE_FAILURE: "GEOGRAPHY LINKAGE FAILURE",
    FULLY_REPRESENTED: "FULLY REPRESENTED",
    UNSUPPORTED_NOT_QUALIFYING: "UNSUPPORTED / NOT QUALIFYING",
}


def hostname(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if "://" not in text:
        text = f"https://{text}"
    return urlparse(text).netloc.lower().removeprefix("www.")


def publisher_hosts(source: dict[str, Any]) -> set[str]:
    discovery = source.get("discovery") or {}
    values = [source.get("url"), source.get("value"), discovery.get("feed_url")]
    feed_urls = discovery.get("feed_urls") or []
    if isinstance(feed_urls, list):
        values.extend(feed_urls)
    hosts = {hostname(item) for item in values if item}
    return {host for host in hosts if host and host not in WRAPPER_HOSTS}


def collected_publisher_hosts(sources: list[dict[str, Any]]) -> set[str]:
    return {
        host
        for source in sources
        if is_collection_eligible(source)
        for host in publisher_hosts(source)
    }


def registered_publisher_hosts(sources: list[dict[str, Any]]) -> set[str]:
    return {host for source in sources for host in publisher_hosts(source)}


def _normalize_name(value: str | None) -> str:
    text = str(value or "").strip().strip("'\"").lower()
    return text.replace("®", "").replace("™", "").replace("  ", " ")


def entity_names(entity: dict[str, Any] | None) -> set[str]:
    if not entity:
        return set()
    values = [entity.get("name"), *((entity.get("aliases") or []) if isinstance(entity.get("aliases"), list) else [])]
    return {_normalize_name(item) for item in values if item}


def cited_publisher_hosts(evidence: list[dict[str, Any]]) -> set[str]:
    hosts: set[str] = set()
    for row in evidence:
        if row.get("status") not in {None, "published"}:
            continue
        host = hostname(row.get("source_url") or row.get("canonical_url"))
        if host and host not in WRAPPER_HOSTS:
            hosts.add(host)
        origin = str(row.get("origin_domain") or "").strip().lower().removeprefix("www.")
        if origin and origin not in WRAPPER_HOSTS:
            hosts.add(origin)
    return hosts


def collection_status_for_host(
    host: str,
    *,
    collected_hosts: set[str],
    known_hosts: set[str],
    excluded_hosts: set[str] | None = None,
) -> str:
    host = hostname(host)
    if not host:
        return SOURCE_UNKNOWN
    if host in (excluded_hosts or set()) or host in WRAPPER_HOSTS:
        return UNSUPPORTED_NOT_QUALIFYING
    if host in collected_hosts:
        return "COLLECTED"
    if host in known_hosts:
        return SOURCE_KNOWN_NOT_COLLECTED
    return SOURCE_UNKNOWN


def _index(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("id")): row for row in records if row.get("id")}


def classify_result(
    result: dict[str, Any],
    *,
    sources: list[dict[str, Any]],
    published_evidence: list[dict[str, Any]],
    varieties: list[dict[str, Any]],
    candidates: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    qualification = str(result.get("qualification") or "").strip().lower().replace(" ", "_")
    if qualification != "qualifying":
        return {**result, "miss_classification": UNSUPPORTED_NOT_QUALIFYING}

    collected_hosts = collected_publisher_hosts(sources)
    known_hosts = registered_publisher_hosts(sources) | cited_publisher_hosts(published_evidence)
    host = hostname(result.get("domain") or result.get("url"))
    status = collection_status_for_host(
        host, collected_hosts=collected_hosts, known_hosts=known_hosts
    )

    evidence_index = _index(published_evidence)
    variety_index = _index(varieties)
    candidate_index = _index(candidates or [])

    matched_evidence = evidence_index.get(str(result.get("matched_evidence_id") or ""))
    matched_entity = variety_index.get(str(result.get("matched_entity_id") or ""))
    matched_candidate = candidate_index.get(str(result.get("matched_candidate_id") or ""))

    expected_entity = str(result.get("expected_entity_id") or "")
    expected_alias = _normalize_name(result.get("expected_alias"))
    expected_geography = str(result.get("expected_geography_id") or "")
    expected_date = str(result.get("expected_date") or "")

    if expected_alias and matched_entity and expected_alias not in entity_names(matched_entity):
        miss = ENTITY_FOUND_IDENTITY_UNRESOLVED
    elif matched_evidence:
        entity_ids = {str(eid) for eid in (matched_evidence.get("entity_ids") or [])}
        geography_ids = {str(gid) for gid in (matched_evidence.get("geography_ids") or [])}
        entity_geos = {str(gid) for gid in ((matched_entity or {}).get("geography_ids") or [])}
        if expected_entity and expected_entity not in entity_ids and not matched_entity:
            miss = ENTITY_FOUND_IDENTITY_UNRESOLVED if matched_candidate else ITEM_COLLECTED_ENTITY_MISSED
        elif expected_entity and expected_entity not in entity_ids:
            miss = ITEM_COLLECTED_ENTITY_MISSED
        elif expected_geography and expected_geography not in geography_ids and expected_geography not in entity_geos:
            miss = GEOGRAPHY_LINKAGE_FAILURE
        elif expected_date:
            actual = str(matched_evidence.get("published_date") or "")
            miss = DATE_CHRONOLOGY_FAILURE if (not actual or expected_date[:7] not in actual) else FULLY_REPRESENTED
        else:
            miss = FULLY_REPRESENTED
    elif expected_geography and matched_entity:
        entity_geos = {str(gid) for gid in (matched_entity.get("geography_ids") or [])}
        miss = GEOGRAPHY_LINKAGE_FAILURE if expected_geography not in entity_geos else FULLY_REPRESENTED
    elif matched_candidate:
        miss = ENTITY_FOUND_IDENTITY_UNRESOLVED
    elif status == SOURCE_UNKNOWN:
        miss = SOURCE_UNKNOWN
    elif status == SOURCE_KNOWN_NOT_COLLECTED:
        miss = SOURCE_KNOWN_NOT_COLLECTED
    elif status == "COLLECTED":
        miss = SOURCE_COLLECTED_ITEM_MISSED
    else:
        miss = SOURCE_UNKNOWN

    return {
        **{
            key: value
            for key, value in result.items()
            if key not in {
                "reasoning",
                "hidden_reasoning",
                "provider_reasoning",
                "raw_model_output",
                "raw_model_outputs",
                "thinking",
                "chain_of_thought",
            }
        },
        "domain": host,
        "collection_status": status,
        "miss_classification": miss,
        "miss_label": MISS_LABELS[miss],
        "verified_evidence_id": matched_evidence.get("id") if matched_evidence else None,
        "verified_entity_id": matched_entity.get("id") if matched_entity else None,
    }


def score_benchmark(
    benchmark: dict[str, Any],
    *,
    sources: list[dict[str, Any]],
    published_evidence: list[dict[str, Any]],
    varieties: list[dict[str, Any]],
    candidates: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    scored = [
        classify_result(
            row,
            sources=sources,
            published_evidence=published_evidence,
            varieties=varieties,
            candidates=candidates,
        )
        for row in (benchmark.get("results") or [])
        if isinstance(row, dict)
    ]
    qualifying = [row for row in scored if row.get("qualification") == "qualifying"]
    counts = {key: 0 for key in MISS_CLASSES}
    for row in scored:
        miss = row.get("miss_classification")
        if miss in counts:
            counts[miss] += 1
    return {
        "id": benchmark.get("id"),
        "question": benchmark.get("question"),
        "run_date": benchmark.get("run_date"),
        "qualifying_external_results": len(qualifying),
        "counts": counts,
        "results": scored,
        "notes": [
            "This is the result of this specific benchmark, not a coverage percentage.",
            "Benchmark results are not trusted Evidence and do not onboard Sources.",
        ],
    }
