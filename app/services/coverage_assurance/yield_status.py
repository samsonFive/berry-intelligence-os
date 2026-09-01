"""Technical health vs intelligence yield.

Technical health reuses classify_source_freshness (collector reachable /
last success). Intelligence yield uses observed captured items and explicit
expectations only -- it does not invent a publication frequency.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from app.services.coverage_assurance.statuses import COLLECTED
from app.services.recall_audit.classify import hostname
from app.services.source_freshness import (
    BLOCKED,
    CURRENT,
    DUE,
    FAILING,
    QUIET,
    STALE,
    classify_source_freshness,
)
from app.services.source_lifecycle import is_collection_eligible

TECHNICAL_HEALTHY = "HEALTHY"
TECHNICAL_BROKEN = "BROKEN"
TECHNICAL_STALE = "STALE"
TECHNICAL_MANUAL = "MANUAL"
TECHNICAL_NOT_COLLECTED = "NOT_COLLECTED"

YIELD_ACTIVE = "ACTIVE"
YIELD_DEGRADED = "DEGRADED"
YIELD_UNOBSERVED = "UNOBSERVED"
YIELD_UNKNOWN = "UNKNOWN"
YIELD_NA = "NOT_APPLICABLE"

YIELD_WINDOW_DAYS = 90
YIELD_RECENT_DAYS = 30
HEALTHY_FRESHNESS = frozenset({CURRENT, QUIET, DUE})
BROKEN_FRESHNESS = frozenset({FAILING, BLOCKED})


def _as_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None


def technical_health_of(freshness_state: str | None, *, collected: bool) -> str:
    if not collected:
        return TECHNICAL_NOT_COLLECTED
    if freshness_state in BROKEN_FRESHNESS:
        return TECHNICAL_BROKEN
    if freshness_state in HEALTHY_FRESHNESS:
        return TECHNICAL_HEALTHY
    if freshness_state == STALE:
        return TECHNICAL_STALE
    return TECHNICAL_MANUAL


def _record_host(record: dict[str, Any]) -> str:
    return hostname(record.get("source_url") or record.get("canonical_url") or record.get("url"))


def _in_window(record: dict[str, Any], *, cutoff: date) -> bool:
    for field in ("published_date", "captured_date", "first_seen_at", "discovered_at"):
        when = _as_date(record.get(field))
        if when and when >= cutoff:
            return True
    return False


def yield_for_source(
    source: dict[str, Any],
    *,
    host: str,
    freshness,
    evidence: list[dict[str, Any]],
    publications: list[dict[str, Any]],
    discovered_items: list[dict[str, Any]],
    variety_candidates: list[dict[str, Any]],
    universe_row: dict[str, Any] | None,
    today: date,
    force_collected: bool = False,
) -> dict[str, Any]:
    """`force_collected` is for a host reconciled as COLLECTED via a
    structural pipeline (Coverage Assurance's STRUCTURAL_COLLECTORS,
    e.g. patent_monitor/cpvo_registry) that has no matching Source
    record at all -- without it, `source` is empty and this would
    contradict its own COLLECTED status by reporting NOT_APPLICABLE."""
    collected = force_collected or (is_collection_eligible(source) if source else False)
    freshness_state = getattr(freshness, "state", None) if freshness is not None else None
    technical = technical_health_of(freshness_state, collected=collected)
    source_id = str((source or {}).get("id") or "")

    def belongs(record: dict[str, Any]) -> bool:
        if source_id and str(record.get("source_id") or "") == source_id:
            return True
        return bool(host) and _record_host(record) == host

    cutoff_90 = today - timedelta(days=YIELD_WINDOW_DAYS)
    cutoff_30 = today - timedelta(days=YIELD_RECENT_DAYS)
    evidence_90 = [row for row in evidence if belongs(row) and _in_window(row, cutoff=cutoff_90)]
    evidence_30 = [row for row in evidence if belongs(row) and _in_window(row, cutoff=cutoff_30)]
    pubs_90 = [row for row in publications if belongs(row) and _in_window(row, cutoff=cutoff_90)]
    discovered_90 = [row for row in discovered_items if belongs(row) and _in_window(row, cutoff=cutoff_90)]
    candidates_90 = [row for row in variety_candidates if belongs(row) and _in_window(row, cutoff=cutoff_90)]
    historical = [
        row
        for row in list(evidence) + list(publications) + list(discovered_items)
        if belongs(row)
    ]
    relevant_90 = len(evidence_90) + len(pubs_90) + len(discovered_90)
    latest = None
    for record in historical:
        for field in ("published_date", "captured_date", "first_seen_at"):
            when = str(record.get(field) or "").strip()
            if when and (latest is None or when > latest):
                latest = when

    expectation = None
    if universe_row and universe_row.get("yield_expectation_days"):
        try:
            expectation = int(universe_row["yield_expectation_days"])
        except (TypeError, ValueError):
            expectation = None
    if source and (source.get("yield_expectation_days") or (source.get("discovery") or {}).get("yield_expectation_days")):
        raw = source.get("yield_expectation_days") or (source.get("discovery") or {}).get("yield_expectation_days")
        try:
            expectation = int(raw)
        except (TypeError, ValueError):
            pass

    last_success = getattr(freshness, "last_success_at", None) if freshness is not None else None

    if not collected:
        yield_state = YIELD_NA
        reason = "Source is not actively collected; yield is not applicable."
    elif technical == TECHNICAL_BROKEN:
        yield_state = YIELD_UNKNOWN
        reason = "Collector is broken; intelligence yield cannot be judged from a failed poll."
    elif relevant_90 > 0:
        yield_state = YIELD_ACTIVE
        reason = f"{relevant_90} relevant captured item(s) in the last {YIELD_WINDOW_DAYS} days."
    elif technical == TECHNICAL_HEALTHY and last_success:
        if expectation or historical:
            yield_state = YIELD_DEGRADED
            if historical:
                reason = (
                    f"Collector succeeds, but no relevant items in the last {YIELD_WINDOW_DAYS} days "
                    f"despite earlier observed yield ({len(historical)} historical item(s))."
                )
            else:
                reason = (
                    f"Collector succeeds, but no relevant items in the last {YIELD_WINDOW_DAYS} days "
                    f"against an explicit yield expectation of {expectation} days."
                )
        else:
            yield_state = YIELD_UNOBSERVED
            reason = (
                "Collector succeeds, but this Source has no observed yield history and no explicit "
                "yield expectation, so absence of items is not treated as degradation."
            )
    else:
        yield_state = YIELD_UNKNOWN
        reason = "Not enough successful collection history to judge intelligence yield."

    return {
        "technical_health": technical,
        "freshness_state": freshness_state,
        "yield_state": yield_state,
        "reason": reason,
        "relevant_items_30": len(evidence_30) + sum(1 for row in pubs_90 if _in_window(row, cutoff=cutoff_30)),
        "relevant_items_90": relevant_90,
        "publications_staged_90": len(pubs_90),
        "evidence_generated_90": len(evidence_90),
        "variety_candidates_90": len(candidates_90),
        "newest_item_at": latest,
        "last_success_at": last_success,
        "yield_expectation_days": expectation,
    }


def attach_liveness(
    rows: list[dict[str, Any]],
    *,
    sources: list[dict[str, Any]],
    discovery_states: dict[str, dict[str, Any] | None],
    evidence: list[dict[str, Any]],
    publications: list[dict[str, Any]],
    discovered_items: list[dict[str, Any]],
    variety_candidates: list[dict[str, Any]],
    today: date | None = None,
    latest_dates: dict[str, tuple[str | None, str | None]] | None = None,
) -> list[dict[str, Any]]:
    today = today or datetime.now(UTC).date()
    sources_by_id = {str(row.get("id")): row for row in sources if row.get("id")}
    for row in rows:
        source = sources_by_id.get(str(row.get("known_source_id") or ""))
        source_id = str((source or {}).get("id") or "")
        published_at, captured_at = (None, None)
        if latest_dates and source_id:
            published_at, captured_at = latest_dates.get(source_id, (None, None))
        freshness = None
        if source:
            freshness = classify_source_freshness(
                source,
                discovery_state=discovery_states.get(source_id),
                latest_item_published_at=published_at,
                latest_item_captured_at=captured_at,
                today=today,
            )
        liveness = yield_for_source(
            source or {},
            host=str(row.get("hostname") or ""),
            freshness=freshness,
            evidence=evidence,
            publications=publications,
            discovered_items=discovered_items,
            variety_candidates=variety_candidates,
            universe_row=row,
            today=today,
            force_collected=bool(source is None and row.get("collection_status") == COLLECTED),
        )
        row["technical_health"] = liveness["technical_health"]
        row["yield_state"] = liveness["yield_state"]
        row["liveness"] = liveness
        row["freshness_state"] = liveness.get("freshness_state")
    return rows
