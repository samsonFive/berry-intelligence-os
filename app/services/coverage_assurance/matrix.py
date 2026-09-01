"""Coverage matrix: raw explainable counts. No percentages. No completeness score."""

from __future__ import annotations

from typing import Any

from app.services.coverage_assurance.classes import MATRIX_CLASS_GROUPS, matrix_group_of
from app.services.coverage_assurance.reconcile import (
    COLLECTED,
    INTENTIONALLY_EXCLUDED,
)
from app.services.coverage_assurance.universe import BERRY_LABELS, BERRY_SCOPE, GEOGRAPHY_BUCKETS
from app.services.coverage_assurance.yield_status import TECHNICAL_HEALTHY, YIELD_DEGRADED


def _empty_counts() -> dict[str, int]:
    return {
        "known_sources": 0,
        "active_sources": 0,
        "healthy": 0,
        "yield_degraded": 0,
        "cited_but_not_collected": 0,
        "independent_benchmark_misses": 0,
    }


def _inc(bucket: dict[str, int], row: dict[str, Any], *, benchmark_misses_by_host: dict[str, int]) -> None:
    if row.get("collection_status") == INTENTIONALLY_EXCLUDED:
        return
    bucket["known_sources"] += 1
    if row.get("collection_status") == COLLECTED:
        bucket["active_sources"] += 1
    if row.get("technical_health") == TECHNICAL_HEALTHY:
        bucket["healthy"] += 1
    if row.get("yield_state") == YIELD_DEGRADED:
        bucket["yield_degraded"] += 1
    if row.get("cited_evidence_ids") and row.get("collection_status") != COLLECTED:
        bucket["cited_but_not_collected"] += 1
    bucket["independent_benchmark_misses"] += int(benchmark_misses_by_host.get(row.get("hostname") or "", 0))


def coverage_matrix(
    rows: list[dict[str, Any]],
    *,
    scored_benchmarks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    benchmark_misses_by_host: dict[str, int] = {}
    for benchmark in scored_benchmarks or []:
        for result in benchmark.get("results") or []:
            if result.get("qualification") != "qualifying":
                continue
            if result.get("miss_classification") in {
                "FULLY_REPRESENTED",
                "UNSUPPORTED_NOT_QUALIFYING",
            }:
                continue
            host = str(result.get("domain") or "")
            if host:
                benchmark_misses_by_host[host] = benchmark_misses_by_host.get(host, 0) + 1

    by_berry = {berry: _empty_counts() for berry in BERRY_SCOPE}
    by_geo = {key: _empty_counts() for key, _label in GEOGRAPHY_BUCKETS}
    by_class = {key: _empty_counts() for key, _label, _members in MATRIX_CLASS_GROUPS}
    totals = _empty_counts()

    for row in rows:
        _inc(totals, row, benchmark_misses_by_host=benchmark_misses_by_host)
        berries = row.get("berry_scope") or []
        if not berries:
            # Untagged known resources still count in totals, not invented into a berry.
            pass
        for berry in berries:
            if berry in by_berry:
                _inc(by_berry[berry], row, benchmark_misses_by_host=benchmark_misses_by_host)
        geos = row.get("geography") or ["other"]
        for geo in geos:
            if geo in by_geo:
                _inc(by_geo[geo], row, benchmark_misses_by_host=benchmark_misses_by_host)
        group = matrix_group_of(str(row.get("source_class") or "trade_press"))
        if group in by_class:
            _inc(by_class[group], row, benchmark_misses_by_host=benchmark_misses_by_host)

    return {
        "totals": totals,
        "by_berry": [
            {"id": berry, "label": BERRY_LABELS.get(berry, berry), **by_berry[berry]}
            for berry in BERRY_SCOPE
        ],
        "by_geography": [
            {"id": key, "label": label, **by_geo[key]} for key, label in GEOGRAPHY_BUCKETS
        ],
        "by_source_class": [
            {"id": key, "label": label, **by_class[key]} for key, label, _members in MATRIX_CLASS_GROUPS
        ],
        "notes": [
            "Counts are raw and explainable, never reduced to a single completeness number.",
            "A cell can be zero. Zero means none recorded, not that the public universe is empty.",
            "Known sources include Source Universe entries plus onboarded publisher hosts.",
            "Cited but not collected is the Italian Berry class of failure.",
        ],
    }
