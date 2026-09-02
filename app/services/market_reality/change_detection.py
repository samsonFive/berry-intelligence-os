"""Deterministic market-change observations (Market Reality Data Layer V1).

Plain arithmetic over an ordered time series -- latest vs. previous period,
and year-over-year where two same-period-type points exist a year apart.
No opaque scoring, no automatic Signal/Assessment creation: this module
returns structured facts about the numbers themselves, nothing more."""

from __future__ import annotations

from typing import Any


def latest_vs_previous(observations: list[dict[str, Any]]) -> dict[str, Any] | None:
    """observations must already be one series (same metric/commodity/
    geography), sorted by period ascending -- e.g. from
    MarketObservationRepository.latest_by_key() filtered to one key."""
    if len(observations) < 2:
        return None
    previous, latest = observations[-2], observations[-1]
    prev_value, latest_value = previous["value"], latest["value"]
    delta = latest_value - prev_value
    pct_change = (delta / prev_value * 100) if prev_value else None
    return {
        "metric": latest["metric"],
        "unit": latest["unit"],
        "previous_period": previous["period"],
        "previous_value": prev_value,
        "latest_period": latest["period"],
        "latest_value": latest_value,
        "delta": delta,
        "pct_change": pct_change,
        "direction": "up" if delta > 0 else ("down" if delta < 0 else "flat"),
    }


def year_over_year(observations: list[dict[str, Any]], *, years_back: int = 1) -> dict[str, Any] | None:
    """Only compares two points whose period_type is 'year' and whose
    numeric periods differ by exactly years_back -- never a same-period
    comparison mislabeled as YoY."""
    yearly = [o for o in observations if o.get("period_type") == "year" and str(o.get("period", "")).isdigit()]
    if len(yearly) < 2:
        return None
    yearly = sorted(yearly, key=lambda o: int(o["period"]))
    latest = yearly[-1]
    target_year = int(latest["period"]) - years_back
    match = next((o for o in yearly if int(o["period"]) == target_year), None)
    if match is None:
        return None
    delta = latest["value"] - match["value"]
    pct_change = (delta / match["value"] * 100) if match["value"] else None
    return {
        "metric": latest["metric"],
        "unit": latest["unit"],
        "base_period": match["period"],
        "base_value": match["value"],
        "latest_period": latest["period"],
        "latest_value": latest["value"],
        "delta": delta,
        "pct_change": pct_change,
        "direction": "up" if delta > 0 else ("down" if delta < 0 else "flat"),
        "years_back": years_back,
    }
