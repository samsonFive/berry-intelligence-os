"""Research Desk read interface for Market Reality Data Layer V1.

A clean, dependency-free query seam: given a berry/geography/metric, get
back normalized observations plus a deterministic change summary. Built
for the concurrent Strategy Research Desk / Ask Berry OS work to consume
-- this module has no knowledge of that consumer's UI or code, and it
mutates nothing (read-only over MarketObservationRepository).

    from app.services.market_reality.research_desk import market_reality_for
    result = market_reality_for(
        repo,
        berry_id="berry-blueberry",
        source_commodity_code="BLUEBERRY",
        geography="US",
    )
    result["observations"]  # normalized, one row per (metric, form, period)
    result["change"]        # {metric_key: latest_vs_previous() dict or None}
"""

from __future__ import annotations

from typing import Any

from app.services.market_reality.change_detection import latest_vs_previous, year_over_year


def market_reality_for(
    repo: Any,
    *,
    berry_id: str | None = None,
    source_commodity_code: str | None = None,
    geography: str | None = None,
    geography_id: str | None = None,
    metric: str | None = None,
) -> dict[str, Any]:
    """One call, any subset of filters. Returns:
    {
        "filters": {...as passed...},
        "observations": [market_observation dict, ...],  # latest capture per series, period ascending
        "change_by_series": {
            "<metric>|<source_commodity_code>|<form>|<geography>": {
                "latest_vs_previous": {...} | None,
                "year_over_year": {...} | None,
            },
            ...
        },
    }
    Never infers a conclusion beyond the numbers -- callers decide what to
    do with the change dicts; this function only computes them."""
    filters: dict[str, Any] = {}
    if berry_id is not None:
        filters["berry_id"] = berry_id
    if source_commodity_code is not None:
        filters["source_commodity_code"] = source_commodity_code
    if geography is not None:
        filters["geography"] = geography
    if geography_id is not None:
        filters["geography_id"] = geography_id
    if metric is not None:
        filters["metric"] = metric

    observations = repo.latest_by_key(**filters)

    series: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for obs in observations:
        key = (obs.get("metric"), obs.get("source_commodity_code"), obs.get("form"), obs.get("geography"))
        series.setdefault(key, []).append(obs)

    change_by_series: dict[str, dict[str, Any]] = {}
    for key, rows in series.items():
        rows_sorted = sorted(rows, key=lambda r: r.get("period", ""))
        label = "|".join(str(part) for part in key)
        change_by_series[label] = {
            "latest_vs_previous": latest_vs_previous(rows_sorted),
            "year_over_year": year_over_year(rows_sorted),
        }

    return {
        "filters": filters,
        "observations": observations,
        "change_by_series": change_by_series,
    }
