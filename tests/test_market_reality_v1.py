"""Market Reality Data Layer V1.

Covers: JSON-stat decoding, commodity/geography normalization, observation
building, immutable-by-construction persistence (a re-fetch never
overwrites a prior capture), and deterministic change detection.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.repositories.base import DuplicateRecord
from app.repositories.json.market_observations import MarketObservationRepository
from app.services.market_reality.change_detection import latest_vs_previous, year_over_year
from app.services.market_reality.eurostat_apro import build_observations, decode_jsonstat
from app.services.market_reality.normalization import normalize_berry, normalize_geography


# --- normalization -----------------------------------------------------


def test_normalize_berry_strawberry_maps_cleanly():
    berry_id, label, form = normalize_berry("S0000")
    assert berry_id == "berry-strawberry"
    assert label == "Strawberries"
    assert form == "fresh"


def test_normalize_berry_mixed_category_stays_unmapped():
    berry_id, label, form = normalize_berry("F3000")
    assert berry_id is None  # never guess a single berry for a mixed category
    assert label == "Berries (excluding strawberries)"


def test_normalize_berry_unknown_code_stays_unmapped():
    berry_id, label, form = normalize_berry("Z9999")
    assert berry_id is None
    assert label == "Z9999"


def test_normalize_geography_known_country():
    assert normalize_geography("ES") == "geography-spain"


def test_normalize_geography_aggregate_stays_unmapped():
    assert normalize_geography("EU27_2020") is None  # not a country


# --- JSON-stat decoding --------------------------------------------------


def _tiny_jsonstat_payload() -> dict:
    # 2 crops x 1 indicator x 2 geos x 2 times = 8 cells, 3 populated.
    return {
        "id": ["crops", "strucpro", "geo", "time"],
        "size": [2, 1, 2, 2],
        "dimension": {
            "crops": {"category": {"index": {"S0000": 0, "F3000": 1}}},
            "strucpro": {"category": {"index": {"HPRD_HUMD_EU_THS_T": 0}}},
            "geo": {"category": {"index": {"ES": 0, "DE": 1}}},
            "time": {"category": {"index": {"2024": 0, "2025": 1}}},
        },
        # flat index = ((crop*1 + strucpro)*2 + geo)*2 + time
        "value": {
            "1": 300.5,  # crop=S0000(0), geo=ES(0), time=2025(1) -> 0*2*2 + 0*2 + 1 = 1
            "3": 280.0,  # crop=S0000(0), geo=DE(1), time=2025(1) -> 0*2*2 + 1*2 + 1 = 3
            "5": 90.25,  # crop=F3000(1), geo=ES(0), time=2025(1) -> 1*2*2 + 0*2 + 1 = 5
        },
    }


def test_decode_jsonstat_recovers_every_populated_cell():
    rows = decode_jsonstat(_tiny_jsonstat_payload())
    assert len(rows) == 3
    by_geo_crop = {(r["geo"], r["crops"]): r["value"] for r in rows}
    assert by_geo_crop[("ES", "S0000")] == 300.5
    assert by_geo_crop[("DE", "S0000")] == 280.0
    assert by_geo_crop[("ES", "F3000")] == 90.25
    assert all(r["time"] == "2025" for r in rows)  # only the populated (real) cells decoded


def test_decode_jsonstat_empty_value_returns_no_rows():
    payload = _tiny_jsonstat_payload()
    payload["value"] = {}
    assert decode_jsonstat(payload) == []


# --- observation building -------------------------------------------------


def test_build_observations_normalizes_and_preserves_source_fields():
    rows = decode_jsonstat(_tiny_jsonstat_payload())
    observations = build_observations(rows, captured_at="2026-09-02T00:00:00+00:00")
    assert len(observations) == 3
    strawberry_es = next(o for o in observations if o["source_commodity_code"] == "S0000" and o["geography"] == "ES")
    assert strawberry_es["metric"] == "PRODUCTION"
    assert strawberry_es["berry_id"] == "berry-strawberry"
    assert strawberry_es["geography_id"] == "geography-spain"
    assert strawberry_es["unit"] == "1000 t"
    assert strawberry_es["source_commodity_label"] == "Strawberries"
    assert strawberry_es["period"] == "2025"
    assert strawberry_es["captured_at"] == "2026-09-02T00:00:00+00:00"
    assert strawberry_es["source"] == "eurostat"
    assert strawberry_es["source_dataset"] == "apro_cpsh1"

    other_berries = next(o for o in observations if o["source_commodity_code"] == "F3000")
    assert other_berries["berry_id"] is None  # mixed category, never guessed
    assert other_berries["berry_ids"] == []
    assert other_berries["source_commodity_label"] == "Berries (excluding strawberries)"


def test_build_observations_skips_unrecognized_indicator():
    payload = _tiny_jsonstat_payload()
    payload["dimension"]["strucpro"]["category"]["index"] = {"HUMD_EU_PC": 0}
    rows = decode_jsonstat(payload)
    observations = build_observations(rows, captured_at="2026-09-02T00:00:00+00:00")
    assert observations == []  # humidity-percent is not PRICE/PRODUCTION/etc, must not be guessed into one


def test_build_observations_ids_are_unique_and_deterministic():
    rows = decode_jsonstat(_tiny_jsonstat_payload())
    obs_a = build_observations(rows, captured_at="2026-09-02T00:00:00+00:00")
    obs_b = build_observations(rows, captured_at="2026-09-02T00:00:00+00:00")
    assert [o["id"] for o in obs_a] == [o["id"] for o in obs_b]  # same inputs -> same ids
    obs_c = build_observations(rows, captured_at="2026-09-03T00:00:00+00:00")
    assert {o["id"] for o in obs_a}.isdisjoint({o["id"] for o in obs_c})  # different capture -> different ids


# --- repository: immutability / revision behavior --------------------------


@pytest.fixture
def repo(tmp_path: Path) -> MarketObservationRepository:
    schemas_dir = Path(__file__).resolve().parents[1] / "schemas"
    return MarketObservationRepository(data_dir=tmp_path, schemas_dir=schemas_dir)


def test_market_observation_schema_validates_a_real_record(repo):
    rows = decode_jsonstat(_tiny_jsonstat_payload())
    obs = build_observations(rows, captured_at="2026-09-02T00:00:00+00:00")[0]
    created = repo.create(obs)
    assert created["id"] == obs["id"]
    assert repo.get(obs["id"]) == obs


def test_market_observation_recapture_does_not_overwrite_prior_value(repo):
    rows = decode_jsonstat(_tiny_jsonstat_payload())
    first = build_observations(rows, captured_at="2026-09-01T00:00:00+00:00")[0]
    repo.create(first)

    # A later capture of the exact same logical series with a *different*
    # value (a real revision) must not silently replace the first record.
    revised_rows = [{**rows[0], "value": rows[0]["value"] + 5.0}]
    second = build_observations(revised_rows, captured_at="2026-09-08T00:00:00+00:00")[0]
    repo.create(second)

    all_captures = repo.list(source_commodity_code=first["source_commodity_code"], geography=first["geography"])
    assert len(all_captures) == 2
    values = {c["captured_at"]: c["value"] for c in all_captures}
    assert values["2026-09-01T00:00:00+00:00"] == first["value"]  # original untouched
    assert values["2026-09-08T00:00:00+00:00"] == first["value"] + 5.0


def test_market_observation_exact_recapture_raises_duplicate_not_silent_overwrite(repo):
    rows = decode_jsonstat(_tiny_jsonstat_payload())
    obs = build_observations(rows, captured_at="2026-09-02T00:00:00+00:00")[0]
    repo.create(obs)
    with pytest.raises(DuplicateRecord):
        repo.create(obs)  # identical id (same everything, including captured_at) -- must reject, not overwrite


def test_latest_by_key_does_not_collide_across_different_forms(repo):
    """Regression test for a real bug found during this mission's own
    data-quality pass: US blueberry price for the same year is a
    genuinely different number fresh vs. processed vs. unspecified, and
    latest_by_key() must return all three, not silently collapse them to
    whichever happened to be created last."""
    base = {
        "record_type": "market_observation",
        "metric": "PRICE",
        "berry_id": "berry-blueberry",
        "source_commodity_label": "Blueberry, Cultivated",
        "source_commodity_code": "BLUEBERRY",
        "geography": "US",
        "geography_id": "geography-united-states",
        "period": "2024",
        "period_type": "year",
        "unit": "USD/lb",
        "source": "usda_nass",
        "source_dataset": "ncit0525",
        "captured_at": "2026-09-02T00:00:00+00:00",
        "berry_ids": ["berry-blueberry"],
        "geography_ids": ["geography-united-states"],
    }
    repo.create({**base, "id": "mkt-price-2024-unspecified", "form": "unspecified", "value": 1.450})
    repo.create({**base, "id": "mkt-price-2024-fresh", "form": "fresh", "value": 2.220})
    repo.create({**base, "id": "mkt-price-2024-processed", "form": "processed", "value": 0.526})

    latest = repo.latest_by_key(metric="PRICE", source_commodity_code="BLUEBERRY", geography="US")
    assert len(latest) == 3  # all three forms survive, none silently dropped
    by_form = {r["form"]: r["value"] for r in latest}
    assert by_form == {"unspecified": 1.450, "fresh": 2.220, "processed": 0.526}


def test_latest_by_key_returns_most_recently_captured_value(repo):
    rows = decode_jsonstat(_tiny_jsonstat_payload())
    first = build_observations(rows, captured_at="2026-09-01T00:00:00+00:00")[0]
    repo.create(first)
    revised_rows = [{**rows[0], "value": rows[0]["value"] + 5.0}]
    second = build_observations(revised_rows, captured_at="2026-09-08T00:00:00+00:00")[0]
    repo.create(second)

    latest = repo.latest_by_key(source_commodity_code=first["source_commodity_code"], geography=first["geography"])
    assert len(latest) == 1
    assert latest[0]["value"] == first["value"] + 5.0
    assert latest[0]["captured_at"] == "2026-09-08T00:00:00+00:00"


# --- change detection -------------------------------------------------


def _series(values: dict[str, float], *, metric: str = "PRODUCTION", unit: str = "1000 t") -> list[dict]:
    return [
        {"metric": metric, "unit": unit, "period": period, "period_type": "year", "value": value}
        for period, value in sorted(values.items())
    ]


def test_latest_vs_previous_computes_real_delta():
    series = _series({"2023": 100.0, "2024": 90.0, "2025": 120.0})
    result = latest_vs_previous(series)
    assert result["previous_period"] == "2024"
    assert result["latest_period"] == "2025"
    assert result["delta"] == pytest.approx(30.0)
    assert result["pct_change"] == pytest.approx(33.333, rel=1e-3)
    assert result["direction"] == "up"


def test_latest_vs_previous_needs_at_least_two_points():
    assert latest_vs_previous(_series({"2025": 100.0})) is None
    assert latest_vs_previous([]) is None


def test_year_over_year_matches_exact_year_gap():
    series = _series({"2022": 80.0, "2024": 100.0, "2025": 110.0})
    result = year_over_year(series, years_back=1)
    assert result["base_period"] == "2024"
    assert result["latest_period"] == "2025"
    assert result["delta"] == pytest.approx(10.0)
    assert result["direction"] == "up"


def test_year_over_year_returns_none_when_no_matching_prior_year():
    series = _series({"2020": 80.0, "2025": 110.0})
    assert year_over_year(series, years_back=1) is None  # no 2024 point -- must not fabricate one
