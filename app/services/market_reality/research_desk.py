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


_FORECAST_SUFFIX = "f"
_GEOGRAPHY_LABELS: dict[str, str] = {
    "US": "United States",
    "PE": "Peru",
    "PE-to-US": "Peru → United States",
    "ES": "Spain",
    "DE": "Germany",
    "NL": "Netherlands",
    "PT": "Portugal",
    "EU27_2020": "EU-27",
}


def market_reality_highlights(
    repo: Any,
    *,
    berry_id: str | None = None,
    limit: int = 4,
) -> list[dict[str, Any]]:
    """Morning Edition card feed: the most notable real, deterministic
    changes for a berry (or, if berry_id is None, across everything the
    store has), ranked by |pct_change|. Never includes a forecast-vs-
    forecast comparison as a headline "change" -- a report's own forward
    estimate isn't something that "changed," so any series whose latest
    two periods are both forecast-suffixed is skipped rather than shown
    as if it were a measured move. Returns [] (not padding) when nothing
    qualifies -- the caller must omit the section, not fake content."""
    result = market_reality_for(repo, berry_id=berry_id)
    cards: list[dict[str, Any]] = []
    for label, changes in result["change_by_series"].items():
        change = changes.get("latest_vs_previous")
        if not change or change.get("pct_change") is None:
            continue
        if str(change["latest_period"]).endswith(_FORECAST_SUFFIX) and str(change["previous_period"]).endswith(_FORECAST_SUFFIX):
            continue
        metric, commodity_code, _form, geography = label.split("|", 3)
        series_rows = [o for o in result["observations"] if o.get("metric") == metric and o.get("source_commodity_code") == commodity_code and o.get("geography") == geography]
        source_row = series_rows[-1] if series_rows else {}
        cards.append(
            {
                "metric": metric,
                "commodity_label": source_row.get("source_commodity_label") or commodity_code,
                "geography_label": _GEOGRAPHY_LABELS.get(geography, geography),
                "unit": change["unit"],
                "previous_period": change["previous_period"],
                "previous_value": change["previous_value"],
                "latest_period": change["latest_period"],
                "latest_value": change["latest_value"],
                "direction": change["direction"],
                "pct_change": change["pct_change"],
                "source": source_row.get("source"),
                "source_dataset": source_row.get("source_dataset"),
                "source_url": source_row.get("source_url"),
                "captured_at": source_row.get("captured_at"),
            }
        )
    cards.sort(key=lambda c: abs(c["pct_change"]), reverse=True)
    return cards[:limit]
