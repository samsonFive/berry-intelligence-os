"""UN Comtrade trade-intelligence acquisition + derived metrics.

No live network in pytest: `query` is always a fake/injected callable here,
matching this project's existing patent-monitor/CPVO-registry test
convention. The real endpoint
(https://comtradeapi.un.org/public/v1/preview/C/M/HS) was proven live, by
hand, during the mission -- see docs/v2/TRADE-INTELLIGENCE-V1.md.
"""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from app.services.trade_intelligence import (
    TradeLaneRequest,
    build_trade_review_draft,
    canonical_lane_id,
    normalize_series_row,
    rolling_seasonal_comparison,
    run_trade_intelligence_monitor,
    unusual_movement,
    year_over_year_change,
)

ROOT = Path(__file__).resolve().parents[1]

HS_TAXONOMY = {
    "081010": {
        "hs_code": "081010", "description": "Strawberries, fresh", "berry_ids": ["berry-strawberry"],
        "fresh_or_frozen": "fresh", "berry_code_purity": "single_berry", "limitations": "None found.",
    },
    "081020": {
        "hs_code": "081020", "description": "Raspberries, blackberries, mulberries and loganberries, fresh",
        "berry_ids": ["berry-raspberry", "berry-blackberry"], "fresh_or_frozen": "fresh",
        "berry_code_purity": "multi_berry_combined", "limitations": "Not separable into raspberry vs blackberry.",
    },
}


def _row(period="202505", qty=117636.0, value=1325969.0, reported=True, aggregate=False, flow="M"):
    return {
        "period": period, "qty": qty, "qtyUnitCode": 8, "primaryValue": value,
        "isQtyEstimated": False, "isReported": reported, "isAggregate": aggregate, "flowCode": flow,
    }


def test_normalize_series_row_keeps_cif_fob_distinct() -> None:
    imp = normalize_series_row(_row(flow="M"))
    exp = normalize_series_row(_row(flow="X"))
    assert imp["value_basis"] == "CIF"
    assert exp["value_basis"] == "FOB"
    assert imp["period"] == "2025-05"
    assert imp["quantity_unit"] == "kg"
    assert imp["currency"] == "USD"


def test_canonical_lane_id_is_deterministic() -> None:
    a = canonical_lane_id("842", "484", "M", "081010")
    b = canonical_lane_id("842", "484", "M", "081010")
    c = canonical_lane_id("842", "484", "M", "081020")
    assert a == b
    assert a != c


def test_build_review_draft_never_auto_trusts_and_flags_combined_hs_code() -> None:
    series = [normalize_series_row(_row(period="202505")), normalize_series_row(_row(period="202605", qty=200000))]
    draft = build_trade_review_draft(
        lane_id="trade-test", reporter_code="842", partner_code="484", flow_code="M",
        hs_code="081020", hs_entry=HS_TAXONOMY["081020"], series=series, captured_date="2026-08-21",
    )
    assert draft["status"] == "draft"
    assert draft["review_state"] == "in_review"
    assert draft["verification_state"] == "unverified"
    assert draft["validated"] is False
    assert draft["source_type"] == "trade_statistics_record"
    assert draft["trade_observation"]["berry_code_purity"] == "multi_berry_combined"
    assert "not separable" in draft["does_not_prove"][-1].lower()
    assert draft["berry_ids"] == ["berry-raspberry", "berry-blackberry"]

    schema = json.loads((ROOT / "schemas" / "evidence.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = list(validator.iter_errors(draft))
    assert not errors, [e.message for e in errors]


def test_single_berry_hs_code_has_no_purity_caveat() -> None:
    series = [normalize_series_row(_row())]
    draft = build_trade_review_draft(
        lane_id="trade-test2", reporter_code="842", partner_code="484", flow_code="M",
        hs_code="081010", hs_entry=HS_TAXONOMY["081010"], series=series, captured_date="2026-08-21",
    )
    assert draft["trade_observation"]["berry_code_purity"] == "single_berry"
    # The generic does_not_prove list only, no HS-purity caveat appended.
    from app.services.trade_intelligence import TRADE_DOES_NOT_PROVE

    assert draft["does_not_prove"] == list(TRADE_DOES_NOT_PROVE)


def test_run_monitor_is_idempotent_and_never_sums_aggregate_rows(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    calls: list[str] = []

    def fake_query(*, reporter_code, partner_code, period, flow_code, hs_code):
        calls.append(period)
        # Real-shaped response: one true disaggregated row plus a
        # world-aggregate row -- the service must prefer the disaggregated
        # one and never sum them.
        return [
            _row(period=period, qty=100.0, value=1000.0, reported=False, aggregate=True),
            _row(period=period, qty=50.0, value=500.0, reported=True, aggregate=False),
        ]

    lanes = [TradeLaneRequest(reporter_geo="geography-united-states", partner_geo="geography-mexico", flow_code="M", hs_code="081010", periods=["202501", "202502"])]
    first = run_trade_intelligence_monitor(inbox_dir=inbox, hs_taxonomy=HS_TAXONOMY, lane_requests=lanes, query=fake_query)
    assert first["lanes_with_data"] == 1
    assert first["review_ready"] == 1
    assert len(first["created"]) == 1
    written = list((inbox / "evidence").glob("ev-trade-*.json"))
    assert len(written) == 1
    draft = json.loads(written[0].read_text(encoding="utf-8"))
    series = draft["trade_observation"]["series"]
    assert len(series) == 2
    assert all(s["quantity"] == 50.0 for s in series)  # the disaggregated row, not the aggregate/summed one

    second = run_trade_intelligence_monitor(inbox_dir=inbox, hs_taxonomy=HS_TAXONOMY, lane_requests=lanes, query=fake_query)
    assert second["duplicates"] == 1
    assert second["created"] == []
    assert len(list((inbox / "evidence").glob("ev-trade-*.json"))) == 1


def test_data_not_yet_released_is_not_treated_as_a_failure(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"

    def fake_query(*, reporter_code, partner_code, period, flow_code, hs_code):
        return [] if period == "202607" else [_row(period=period)]

    lanes = [TradeLaneRequest(reporter_geo="geography-united-states", partner_geo="geography-mexico", flow_code="M", hs_code="081010", periods=["202506", "202607"])]
    result = run_trade_intelligence_monitor(inbox_dir=inbox, hs_taxonomy=HS_TAXONOMY, lane_requests=lanes, query=fake_query)
    assert result["failed"] == []  # a genuinely empty period is not a failure
    written = list((inbox / "evidence").glob("ev-trade-*.json"))
    draft = json.loads(written[0].read_text(encoding="utf-8"))
    assert len(draft["trade_observation"]["series"]) == 1  # only the real period, the empty one silently excluded


def test_unexpected_adapter_failure_isolated_to_one_period(tmp_path: Path) -> None:
    def fake_query(*, period, **kwargs):
        if period == "202501":
            raise ValueError("unexpected adapter failure")
        return [_row(period=period)]

    lanes = [TradeLaneRequest(reporter_geo="geography-united-states", partner_geo="geography-mexico", flow_code="M", hs_code="081010", periods=["202501", "202502"])]
    result = run_trade_intelligence_monitor(inbox_dir=tmp_path / "inbox", hs_taxonomy=HS_TAXONOMY, lane_requests=lanes, query=fake_query)
    assert len(result["failed"]) == 1
    assert result["lanes_with_data"] == 1 and result["review_ready"] == 1


def test_year_over_year_change_requires_same_lane_and_both_periods() -> None:
    record = {
        "id": "ev-trade-x",
        "trade_observation": {
            "series": [
                {"period": "2025-05", "quantity": 100.0, "trade_value": 1000.0},
                {"period": "2026-05", "quantity": 150.0, "trade_value": 1200.0},
            ]
        },
    }
    yoy = year_over_year_change([record], period="2026-05")
    assert yoy is not None
    assert round(yoy["quantity_change_pct"], 4) == 0.5
    assert round(yoy["value_change_pct"], 4) == 0.2

    missing = year_over_year_change([record], period="2026-06")
    assert missing is None  # honest None, not a fabricated 0% change


def test_unusual_movement_flags_only_above_threshold() -> None:
    record = {
        "id": "ev-trade-y",
        "trade_observation": {
            "series": [
                {"period": "2025-05", "quantity": 100.0, "trade_value": 1000.0},
                {"period": "2026-05", "quantity": 110.0, "trade_value": 1100.0},
            ]
        },
    }
    result = unusual_movement([record], period="2026-05", threshold_pct=0.25)
    assert result["flagged_unusual"] is False  # 10% change, below the 25% threshold

    record["trade_observation"]["series"][1]["quantity"] = 200.0
    result2 = unusual_movement([record], period="2026-05", threshold_pct=0.25)
    assert result2["flagged_unusual"] is True  # 100% change, above threshold


def test_rolling_seasonal_comparison_returns_latest_n_in_chronological_order() -> None:
    record = {
        "id": "ev-trade-z",
        "trade_observation": {
            "series": [
                {"period": "2026-01", "quantity": 10.0},
                {"period": "2026-03", "quantity": 30.0},
                {"period": "2026-02", "quantity": 20.0},
            ]
        },
    }
    rows = rolling_seasonal_comparison([record], months=2)
    assert [r["period"] for r in rows] == ["2026-02", "2026-03"]
