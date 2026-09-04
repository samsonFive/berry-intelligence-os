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


def market_context_for_research_scope(repo: Any, scope: Any, *, limit: int = 6) -> list[dict[str, Any]]:
    """Adapter for Ask Berry OS's `market_context_provider` seam
    (`app/services/research_desk.py::assemble_research_packet`). Takes any
    object with `.berry_id` (str | None) and `.geography_ids` (list[str])
    attributes -- duck-typed, not a hard import of ResearchScope, so this
    module keeps its "no knowledge of the consumer" property. Returns rows
    shaped like the packet's own evidence_rows (id/title/source_name/date/
    href/structured_kind) so the existing "Market context" section in
    _research_result.html renders them with zero template changes.

    Flagship acceptance case (Overnight Flagship Integration V1, section
    6): this is the only place Market Reality data enters an Ask Berry OS
    answer -- read-only, never inferring causality, always carrying the
    real source/date/unit in the title string itself."""
    berry_id = getattr(scope, "berry_id", None) or None
    geography_ids = list(getattr(scope, "geography_ids", None) or [])
    if geography_ids:
        # A real bug found during this mission's own demo-question testing:
        # a Europe-scoped question was returning unfiltered Peru/US cards
        # because the old code fell back to the unfiltered list whenever no
        # geography matched, instead of returning nothing. No matching
        # geography now means an honest empty list -- never someone else's
        # region silently relabeled as if it answered the question asked.
        result = market_reality_for(repo, berry_id=berry_id)
        allowed_geographies = {
            obs["geography"] for obs in result["observations"] if obs.get("geography_id") in geography_ids
        }
        if not allowed_geographies:
            return []
        cards = [
            c for c in market_reality_highlights(repo, berry_id=berry_id, limit=limit * 4)
            if c["geography_label"] in {_GEOGRAPHY_LABELS.get(g, g) for g in allowed_geographies}
        ]
    else:
        cards = market_reality_highlights(repo, berry_id=berry_id, limit=limit * 2)
    rows: list[dict[str, Any]] = []
    for card in cards[:limit]:
        arrow = "up" if card["direction"] == "up" else ("down" if card["direction"] == "down" else "flat")
        title = (
            f"{card['geography_label']} {card['commodity_label']} -- {card['metric'].replace('_', ' ').title()} "
            f"{'+' if arrow == 'up' else ('-' if arrow == 'down' else '')}{abs(card['pct_change']):.1f}% "
            f"({card['previous_period']} -> {card['latest_period']}, {card['previous_value']:,.0f} -> {card['latest_value']:,.0f} {card['unit']})"
        )
        rows.append(
            {
                "id": f"mkt-{card['source_dataset']}-{card['metric']}-{card['geography_label']}",
                "title": title,
                "source_name": card.get("source") or "",
                "date": (card.get("captured_at") or "")[:10],
                "href": card.get("source_url") or "#",
                "reader_href": card.get("source_url") or "#",
                "trust_class": "MARKET REALITY",
                "structured_kind": "MARKET OBSERVATION",
                "entity_ids": [],
                "geography_ids": [],
                "metric": card["metric"],
                "unit": card["unit"],
                "pct_change": card["pct_change"],
                "direction": card["direction"],
                "previous_period": card["previous_period"],
                "previous_value": card["previous_value"],
                "latest_period": card["latest_period"],
                "latest_value": card["latest_value"],
                "latest_vs_previous": {
                    "metric": card["metric"],
                    "unit": card["unit"],
                    "pct_change": card["pct_change"],
                    "direction": card["direction"],
                    "previous_period": card["previous_period"],
                    "previous_value": card["previous_value"],
                    "latest_period": card["latest_period"],
                    "latest_value": card["latest_value"],
                },
            }
        )
    return rows
