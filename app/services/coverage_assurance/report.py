"""Coverage Assurance page model. GET-safe: never writes Sources, Evidence, or universe."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from app.services.coverage_assurance.benchmarks import (
    load_benchmarks,
    miss_totals,
    score_all_benchmarks,
)
from app.services.coverage_assurance.matrix import coverage_matrix
from app.services.coverage_assurance.reconcile import (
    COLLECTED,
    INTENTIONALLY_EXCLUDED,
    KNOWN_NOT_COLLECTED,
    UNKNOWN_SOURCE_IDENTITY,
    reconcile,
)
from app.services.coverage_assurance.universe import load_universe
from app.services.coverage_assurance.yield_status import (
    TECHNICAL_BROKEN,
    TECHNICAL_HEALTHY,
    YIELD_DEGRADED,
    attach_liveness,
)
from app.services.media_discovery import read_source_discovery_state
from app.services.recall_audit.classify import MISS_LABELS, hostname
from app.services.source_freshness import index_latest_item_dates
from app.services.source_lifecycle import is_collection_eligible
from app.services.variety_universe.identity import STATE_POSSIBLE_ALIAS, STATE_UNKNOWN

FORBIDDEN_COMPLETENESS_CLAIMS = (
    "coverage score",
    "completeness score",
    "percent coverage",
    "% coverage",
    "fully covered",
    "universe is complete",
)


def _discovery_states(inbox_dir: Path | None, sources: list[dict[str, Any]]) -> dict[str, dict[str, Any] | None]:
    if inbox_dir is None:
        return {}
    states: dict[str, dict[str, Any] | None] = {}
    for source in sources:
        source_id = str(source.get("id") or "")
        if source_id:
            states[source_id] = read_source_discovery_state(inbox_dir, source_id)
    return states


def _variety_related(record: dict[str, Any]) -> bool:
    if any(str(eid).startswith("variety-") for eid in (record.get("entity_ids") or [])):
        return True
    if record.get("source_type") in {"plant_breeders_rights_record", "patent_record", "patent"}:
        return True
    return False


def variety_coverage_slice(
    rows: list[dict[str, Any]],
    *,
    published_evidence: list[dict[str, Any]],
    variety_candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    variety_hosts = {
        hostname(row.get("source_url") or row.get("canonical_url"))
        for row in published_evidence
        if _variety_related(row)
    }
    variety_hosts -= {""}
    dense_known = [row for row in rows if row.get("variety_dense") or row["hostname"] in variety_hosts]
    dense_collected = [row for row in dense_known if row.get("collection_status") == COLLECTED]
    cited_not_collected = [
        row
        for row in rows
        if row["hostname"] in variety_hosts
        and row.get("collection_status") not in {COLLECTED, INTENTIONALLY_EXCLUDED}
    ]
    unresolved = [
        row
        for row in variety_candidates
        if row.get("status") != "rejected"
        and row.get("identity_state") in {STATE_POSSIBLE_ALIAS, STATE_UNKNOWN}
    ]
    return {
        "variety_dense_known": len(dense_known),
        "variety_dense_collected": len(dense_collected),
        "cited_variety_hosts_not_collected": cited_not_collected,
        "recent_cultivar_candidates": len(
            [row for row in variety_candidates if row.get("status") != "rejected"]
        ),
        "candidate_generation_yield": len(
            [row for row in variety_candidates if row.get("status") != "rejected"]
        ),
        "unresolved_candidates": len(unresolved),
        "notes": [
            "Variety Coverage reuses Coverage Assurance. This is not a Variety-only system.",
            "Cited variety hosts that are not collected is the Italian Berry class of failure.",
        ],
    }


def build_coverage_report(
    *,
    data_dir: Path,
    sources: list[dict[str, Any]],
    published_evidence: list[dict[str, Any]],
    publications: list[dict[str, Any]] | None = None,
    variety_candidates: list[dict[str, Any]] | None = None,
    varieties: list[dict[str, Any]] | None = None,
    discovered_items: list[dict[str, Any]] | None = None,
    blocked_domains: list[str] | None = None,
    inbox_dir: Path | None = None,
    benchmarks: list[dict[str, Any]] | None = None,
    discovery_states: dict[str, dict[str, Any] | None] | None = None,
    now: datetime | date | None = None,
) -> dict[str, Any]:
    publications = publications or []
    variety_candidates = variety_candidates or []
    varieties = varieties or []
    discovered_items = discovered_items or []
    if isinstance(now, datetime):
        today = now.date()
    else:
        today = now or datetime.now(UTC).date()

    universe = load_universe(data_dir)
    reconciliation = reconcile(
        universe_entries=universe.get("entries") or [],
        sources=sources,
        published_evidence=published_evidence,
        publications=publications,
        blocked_domains=blocked_domains,
    )
    states = discovery_states if discovery_states is not None else _discovery_states(inbox_dir, sources)
    latest_dates = index_latest_item_dates(
        discovered_items=discovered_items,
        published_evidence=published_evidence,
    )
    rows = attach_liveness(
        reconciliation["rows"],
        sources=sources,
        discovery_states=states,
        evidence=published_evidence,
        publications=publications,
        discovered_items=discovered_items,
        variety_candidates=variety_candidates,
        today=today,
        latest_dates=latest_dates,
    )
    # Re-bind list aliases after liveness mutation (rows are the same dicts).
    reconciliation["rows"] = rows
    loaded_benchmarks = benchmarks if benchmarks is not None else load_benchmarks(inbox_dir, data_dir=data_dir)
    scored = score_all_benchmarks(
        loaded_benchmarks,
        sources=sources,
        published_evidence=published_evidence,
        varieties=varieties,
        candidates=variety_candidates,
    )
    matrix = coverage_matrix(rows, scored_benchmarks=scored)
    yield_degraded = [row for row in rows if row.get("yield_state") == YIELD_DEGRADED]
    broken = [row for row in rows if row.get("technical_health") == TECHNICAL_BROKEN]
    attention = list(reconciliation["cited_not_collected"]) + [
        row for row in yield_degraded if row not in reconciliation["cited_not_collected"]
    ]
    variety = variety_coverage_slice(
        rows,
        published_evidence=published_evidence,
        variety_candidates=variety_candidates,
    )
    active_sources = [source for source in sources if is_collection_eligible(source)]
    return {
        "universe_entry_count": len(universe.get("entries") or []),
        "known_resources": len(
            [
                row
                for row in rows
                if row.get("collection_status") != INTENTIONALLY_EXCLUDED
            ]
        ),
        "actively_collected": len(active_sources),
        "collected_publisher_hosts": len(
            [row for row in rows if row.get("collection_status") == COLLECTED]
        ),
        "known_not_collected": len(reconciliation["known_not_collected"]),
        "cited_not_collected": reconciliation["cited_not_collected"],
        "cited_not_collected_count": len(reconciliation["cited_not_collected"]),
        "unknown_identity": reconciliation["unknown_identity"],
        "intentionally_excluded": reconciliation["intentionally_excluded"],
        "yield_degraded": yield_degraded,
        "yield_degraded_count": len(yield_degraded),
        "technically_healthy": [
            row for row in rows if row.get("technical_health") == TECHNICAL_HEALTHY
        ],
        "broken_collectors": broken,
        "rows": rows,
        "matrix": matrix,
        "benchmarks": scored,
        "benchmark_miss_totals": miss_totals(scored),
        "miss_labels": MISS_LABELS,
        "variety": variety,
        "attention_count": len(attention),
        "onboard_href": "/sources",
        "notes": [
            "This page makes no claim that the public universe of relevant publishers is fully enumerated.",
            "Counts are raw and explainable, never reduced to a single completeness number.",
            "Gaps do not auto-onboard Sources. Use Source Health to add a collector.",
            "Benchmarks do not become trusted Evidence.",
            "GET is read-only.",
        ],
        "status_labels": {
            COLLECTED: "COLLECTED",
            KNOWN_NOT_COLLECTED: "KNOWN / NOT COLLECTED",
            UNKNOWN_SOURCE_IDENTITY: "UNKNOWN SOURCE IDENTITY",
            INTENTIONALLY_EXCLUDED: "INTENTIONALLY EXCLUDED",
        },
    }


def coverage_attention_count(report: dict[str, Any]) -> int:
    return int(report.get("attention_count") or 0)
