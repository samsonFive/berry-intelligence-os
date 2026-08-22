"""NASA POWER weather-context acquisition + derived events.

No live network in pytest: `query` is always a fake/injected callable here,
matching this project's existing patent-monitor/trade-intelligence test
convention. The real endpoint
(https://power.larc.nasa.gov/api/temporal/daily/point) was proven live, by
hand, during the mission -- see docs/v2/WEATHER-CLIMATE-CONTEXT-V1.md.
"""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from app.services.weather_intelligence import (
    POWER_FILL_VALUE,
    WeatherRegionRequest,
    build_weather_review_draft,
    compute_baseline_by_month,
    drought_anomaly,
    extreme_heat_event,
    frost_event,
    leading_indicator_lead_time,
    normalize_daily_series,
    precipitation_deficit,
    precipitation_excess,
    run_weather_intelligence_monitor,
    unusual_temperature_window,
    weather_context_for_trade_anomaly,
)

ROOT = Path(__file__).resolve().parents[1]

PRODUCTION_REGIONS = {
    "test-region-blueberry": {
        "id": "test-region-blueberry", "geography_id": "geography-chile", "region_name": "Test Region",
        "berry_ids": ["berry-blueberry"], "centroid": {"latitude": -35.4, "longitude": -71.6},
        "coverage_caveat": "test caveat",
    },
}


def _raw(days: dict[str, float], sources=("MERRA2", "POWER")) -> dict:
    return {
        "parameters": {
            "T2M_MAX": {d: v + 20 for d, v in days.items()},
            "T2M_MIN": {d: v for d, v in days.items()},
            "PRECTOTCORR": {d: 0.5 for d in days},
        },
        "sources": list(sources),
    }


def test_normalize_daily_series_treats_fill_value_as_provisional_not_failure() -> None:
    raw = _raw({"20260101": 10.0, "20260102": 10.0})
    raw["parameters"]["T2M_MAX"]["20260103"] = POWER_FILL_VALUE
    raw["parameters"]["T2M_MIN"]["20260103"] = POWER_FILL_VALUE
    raw["parameters"]["PRECTOTCORR"]["20260103"] = POWER_FILL_VALUE
    series = normalize_daily_series(raw)
    by_date = {s["date"]: s for s in series}
    assert by_date["2026-01-03"]["is_provisional"] is True
    assert by_date["2026-01-03"]["t2m_max_c"] is None
    assert by_date["2026-01-01"]["is_provisional"] is False
    assert by_date["2026-01-01"]["t2m_max_c"] == 30.0
    assert by_date["2026-01-01"]["source_model"] == "MERRA2"


def test_compute_baseline_by_month_excludes_provisional_days() -> None:
    raw = _raw({"20200115": 10.0, "20200116": 12.0})
    raw["parameters"]["T2M_MAX"]["20200117"] = POWER_FILL_VALUE
    raw["parameters"]["T2M_MIN"]["20200117"] = POWER_FILL_VALUE
    raw["parameters"]["PRECTOTCORR"]["20200117"] = POWER_FILL_VALUE
    baseline = compute_baseline_by_month(raw)
    assert baseline["01"]["t2m_min_mean_c"] == 11.0  # (10+12)/2, provisional day excluded
    assert baseline["02"]["t2m_min_mean_c"] is None  # no data at all for February


def test_build_review_draft_never_auto_trusts_and_validates_against_schema() -> None:
    series = normalize_daily_series(_raw({"20260101": 5.0, "20260102": -1.0}))
    baseline = compute_baseline_by_month(_raw({"20200101": 8.0}))
    draft = build_weather_review_draft(
        production_region_id="test-region-blueberry", region_entry=PRODUCTION_REGIONS["test-region-blueberry"],
        series=series, baseline_by_month=baseline, baseline_period={"start": "2020-01-01", "end": "2020-01-01"},
        captured_date="2026-08-21",
    )
    assert draft["status"] == "draft"
    assert draft["review_state"] == "in_review"
    assert draft["verification_state"] == "unverified"
    assert draft["validated"] is False
    assert draft["source_type"] == "weather_climate_record"
    assert draft["weather_observation"]["production_region_id"] == "test-region-blueberry"
    assert "crop damage" in " ".join(draft["does_not_prove"])

    schema = json.loads((ROOT / "schemas" / "evidence.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = list(validator.iter_errors(draft))
    assert not errors, [e.message for e in errors]


def test_run_monitor_is_idempotent(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"

    def fake_query(*, latitude, longitude, start_date, end_date):
        if start_date.startswith("2015") or start_date.startswith("2020"):
            return _raw({"20200101": 10.0, "20200201": 12.0})
        return _raw({"20260101": 5.0, "20260102": 6.0})

    regions = [WeatherRegionRequest(
        production_region_id="test-region-blueberry",
        baseline_range=("2020-01-01", "2020-02-28"), comparison_range=("2026-01-01", "2026-01-02"),
    )]
    first = run_weather_intelligence_monitor(inbox_dir=inbox, production_regions=PRODUCTION_REGIONS, region_requests=regions, query=fake_query)
    assert first["regions_with_data"] == 1
    assert first["review_ready"] == 1
    assert len(first["created"]) == 1
    written = list((inbox / "evidence").glob("ev-weather-*.json"))
    assert len(written) == 1

    second = run_weather_intelligence_monitor(inbox_dir=inbox, production_regions=PRODUCTION_REGIONS, region_requests=regions, query=fake_query)
    assert second["duplicates"] == 1
    assert second["created"] == []
    assert len(list((inbox / "evidence").glob("ev-weather-*.json"))) == 1


def test_data_not_yet_released_is_not_treated_as_a_failure(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"

    def fake_query(*, latitude, longitude, start_date, end_date):
        if start_date.startswith("2020"):
            return _raw({"20200101": 10.0})
        raw = _raw({"20260101": 5.0})
        raw["parameters"]["T2M_MAX"]["20260102"] = POWER_FILL_VALUE
        raw["parameters"]["T2M_MIN"]["20260102"] = POWER_FILL_VALUE
        raw["parameters"]["PRECTOTCORR"]["20260102"] = POWER_FILL_VALUE
        return raw

    regions = [WeatherRegionRequest(
        production_region_id="test-region-blueberry",
        baseline_range=("2020-01-01", "2020-01-01"), comparison_range=("2026-01-01", "2026-01-02"),
    )]
    result = run_weather_intelligence_monitor(inbox_dir=inbox, production_regions=PRODUCTION_REGIONS, region_requests=regions, query=fake_query)
    assert result["failed"] == []
    draft = json.loads(next((inbox / "evidence").glob("ev-weather-*.json")).read_text(encoding="utf-8"))
    provisional = [s for s in draft["weather_observation"]["series"] if s["is_provisional"]]
    assert len(provisional) == 1
    assert provisional[0]["date"] == "2026-01-02"


def test_unexpected_adapter_failure_becomes_structured_region_failure(tmp_path: Path) -> None:
    def broken_query(**kwargs):
        raise ValueError("unexpected malformed response")

    regions = [WeatherRegionRequest(
        production_region_id="test-region-blueberry",
        baseline_range=("2020-01-01", "2020-01-01"), comparison_range=("2026-01-01", "2026-01-02"),
    )]
    result = run_weather_intelligence_monitor(inbox_dir=tmp_path / "inbox", production_regions=PRODUCTION_REGIONS, region_requests=regions, query=broken_query)
    assert result["regions_with_data"] == 0
    assert result["failed"] == ["unexpected malformed response"]


def _fixture_records() -> list[dict]:
    baseline = {m: {"t2m_max_mean_c": 30.0, "t2m_min_mean_c": 15.0, "precipitation_mean_mm": 1.0} for m in
                [f"{i:02d}" for i in range(1, 13)]}
    series = []
    for day in range(1, 6):
        series.append({"date": f"2026-01-0{day}", "t2m_max_c": 30.0, "t2m_min_c": 15.0, "precipitation_mm": 1.0, "is_provisional": False})
    # a real 3-day frost run
    for day, val in zip([6, 7, 8], [-1.0, -0.5, -2.0]):
        series.append({"date": f"2026-01-0{day}", "t2m_max_c": 12.0, "t2m_min_c": val, "precipitation_mm": 1.0, "is_provisional": False})
    # a real 3-day extreme-heat run
    for day, val in zip([9], [40.0]):
        pass
    for i, day in enumerate(["09", "10", "11"]):
        series.append({"date": f"2026-01-{day}", "t2m_max_c": 40.0, "t2m_min_c": 20.0, "precipitation_mm": 0.0, "is_provisional": False})
    return [{"weather_observation": {"production_region_id": "test-region-blueberry", "series": series, "baseline_by_month": baseline}}]


def test_frost_event_flags_real_sub_zero_days() -> None:
    result = frost_event(_fixture_records(), production_region_id="test-region-blueberry", start="2026-01-01", end="2026-01-11", threshold_c=0.0)
    assert result["count"] == 3  # -1.0, -0.5, and -2.0 are all <= the 0.0C threshold
    assert result["flagged"] is True
    assert "2026-01-06" in result["frost_dates"]
    assert "2026-01-05" not in result["frost_dates"]  # the pre-frost-run day (t2m_min 15.0) stays excluded


def test_extreme_heat_event_requires_consecutive_days_above_baseline() -> None:
    result = extreme_heat_event(_fixture_records(), production_region_id="test-region-blueberry", start="2026-01-01", end="2026-01-11", anomaly_threshold_c=5.0, min_consecutive_days=3)
    assert result["flagged"] is True
    assert result["runs"][0]["days"] == 3
    assert result["runs"][0]["start_date"] == "2026-01-09"


def test_extreme_heat_event_not_flagged_when_run_too_short() -> None:
    result = extreme_heat_event(_fixture_records(), production_region_id="test-region-blueberry", start="2026-01-01", end="2026-01-11", anomaly_threshold_c=5.0, min_consecutive_days=10)
    assert result["flagged"] is False


def test_precipitation_deficit_and_excess_are_symmetric_and_mutually_exclusive() -> None:
    records = _fixture_records()
    deficit = precipitation_deficit(records, production_region_id="test-region-blueberry", start="2026-01-09", end="2026-01-11", deficit_pct=0.4)
    excess = precipitation_excess(records, production_region_id="test-region-blueberry", start="2026-01-09", end="2026-01-11", excess_pct=0.5)
    assert deficit["actual_mm"] == 0.0  # the 3 heat days have zero rain in the fixture
    assert deficit["flagged"] is True
    assert excess["flagged"] is False


def test_drought_anomaly_requires_minimum_window_length() -> None:
    records = _fixture_records()
    short = drought_anomaly(records, production_region_id="test-region-blueberry", start="2026-01-09", end="2026-01-11", deficit_pct=0.4, min_window_days=30)
    assert short["flagged"] is False
    assert "below the 30-day minimum" in short["note"]


def test_unusual_temperature_window_is_bidirectional() -> None:
    result = unusual_temperature_window(_fixture_records(), production_region_id="test-region-blueberry", start="2026-01-06", end="2026-01-08", anomaly_threshold_c=3.0, min_consecutive_days=3)
    assert result["flagged"] is True  # the frost run also deviates from the 15.0 baseline min by >= 3C


def test_weather_context_for_trade_anomaly_returns_structured_bundle_never_auto_trusted() -> None:
    ctx = weather_context_for_trade_anomaly(
        weather_records=_fixture_records(), production_region_id="test-region-blueberry", trade_period="2026-01", lookback_days=15,
    )
    assert ctx["any_material_anomaly_found"] is True
    assert ctx["weather_events"]["extreme_heat"]["flagged"] is True
    assert "does_not_prove" in ctx
    assert ctx["window"]["end"] == "2026-01-31"


def test_weather_context_reports_honest_none_when_region_missing() -> None:
    ctx = weather_context_for_trade_anomaly(
        weather_records=_fixture_records(), production_region_id="nonexistent-region", trade_period="2026-01", lookback_days=15,
    )
    assert ctx["any_material_anomaly_found"] is False


def test_leading_indicator_lead_time_is_a_simple_honest_calendar_calculation() -> None:
    result = leading_indicator_lead_time(weather_anomaly_end_date="2025-12-31", trade_period="2026-02")
    assert result["lead_time_days"] == 59
    assert result["trade_period_end_date"] == "2026-02-28"
