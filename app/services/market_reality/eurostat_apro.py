"""Eurostat annual crop production (apro_cpsh1) collector.

Real, keyless, publicly documented REST API -- no registration, no
credential of any kind. Bounded by construction: the caller supplies the
exact crops/geos to fetch (never "all crops, all countries, all years").
Decodes the standard JSON-stat 2.0 sparse-array response Eurostat's
dissemination API returns; this decoder is generic to JSON-stat, not
apro_cpsh1-specific.

Does not write anywhere. build_observations() returns plain dicts;
persistence is the caller's responsibility (see
scripts/ingest_market_reality_eurostat.py)."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Callable

import httpx

from app.services.market_reality.normalization import (
    EUROSTAT_INDICATOR_TO_METRIC,
    normalize_berry,
    normalize_geography,
)

EUROSTAT_APRO_URL = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/apro_cpsh1"
EUROSTAT_DATASET = "apro_cpsh1"
EUROSTAT_SOURCE = "eurostat"


def fetch_apro_cpsh1(
    *,
    crops: list[str],
    geos: list[str],
    since_year: int,
    strucpro: list[str] | None = None,
    get: Callable[..., Any] = httpx.get,
    timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    """One bounded GET. Never call with unbounded crops/geos ("all crops")
    or unbounded time -- apro_cpsh1's full history runs back decades;
    since_year keeps this a recent-trend query, not a giant historical
    import (Market Reality Data Layer V1, section F)."""
    params: list[tuple[str, str]] = [("format", "JSON"), ("lang", "en"), ("sinceTimePeriod", str(since_year))]
    for crop in crops:
        params.append(("crops", crop))
    for geo in geos:
        params.append(("geo", geo))
    for indicator in strucpro or list(EUROSTAT_INDICATOR_TO_METRIC):
        params.append(("strucpro", indicator))
    response = get(EUROSTAT_APRO_URL, params=params, timeout=timeout_seconds)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("Eurostat apro_cpsh1 returned a non-object payload")
    return payload


def _invert_index(category_index: dict[str, int]) -> dict[int, str]:
    return {position: code for code, position in category_index.items()}


def decode_jsonstat(payload: dict[str, Any]) -> list[dict[str, str | float]]:
    """Generic JSON-stat 2.0 sparse-value decoder. Returns one row per
    populated cell: {dim_name: code, ..., "value": float}."""
    dims: list[str] = payload.get("id") or []
    sizes: list[int] = payload.get("size") or []
    dimension = payload.get("dimension") or {}
    values: dict[str, float] = payload.get("value") or {}
    if not dims or not sizes or len(dims) != len(sizes):
        return []

    position_to_code: list[dict[int, str]] = []
    for dim_name in dims:
        category_index = ((dimension.get(dim_name) or {}).get("category") or {}).get("index") or {}
        position_to_code.append(_invert_index(category_index))

    rows: list[dict[str, str | float]] = []
    for flat_key, value in values.items():
        if value is None:
            continue
        remaining = int(flat_key)
        positions: list[int] = []
        for size in reversed(sizes):
            positions.append(remaining % size)
            remaining //= size
        positions.reverse()
        row: dict[str, str | float] = {}
        for dim_name, position, lookup in zip(dims, positions, position_to_code):
            row[dim_name] = lookup.get(position, str(position))
        row["value"] = float(value)
        rows.append(row)
    return rows


def _observation_id(*, dataset: str, metric: str, crop_code: str, geo: str, period: str, captured_at: str) -> str:
    key = f"{dataset}|{metric}|{crop_code}|{geo}|{period}|{captured_at}"
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]
    return f"mkt-{digest}"


def build_observations(
    rows: list[dict[str, str | float]],
    *,
    captured_at: str | None = None,
    source_url: str = EUROSTAT_APRO_URL,
) -> list[dict[str, Any]]:
    """Normalize decoded JSON-stat rows into market_observation records.
    Rows whose indicator isn't one of the recognized production/acreage/
    yield codes are skipped (humidity-percent rows, e.g.) rather than
    guessed into a metric."""
    stamp = captured_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    observations: list[dict[str, Any]] = []
    for row in rows:
        indicator = str(row.get("strucpro", ""))
        metric_unit = EUROSTAT_INDICATOR_TO_METRIC.get(indicator)
        if metric_unit is None:
            continue
        metric, unit = metric_unit
        crop_code = str(row.get("crops", ""))
        berry_id, commodity_label, form = normalize_berry(crop_code)
        geo = str(row.get("geo", ""))
        geography_id = normalize_geography(geo)
        period = str(row.get("time", ""))
        obs_id = _observation_id(
            dataset=EUROSTAT_DATASET, metric=metric, crop_code=crop_code, geo=geo, period=period, captured_at=stamp
        )
        observations.append(
            {
                "id": obs_id,
                "record_type": "market_observation",
                "metric": metric,
                "berry_id": berry_id,
                "source_commodity_label": commodity_label,
                "source_commodity_code": crop_code,
                "form": form,
                "geography": geo,
                "geography_id": geography_id,
                "period": period,
                "period_type": "year",
                "unit": unit,
                "value": float(row.get("value", 0.0)),
                "source": EUROSTAT_SOURCE,
                "source_dataset": EUROSTAT_DATASET,
                "source_url": source_url,
                "methodology_reference": "https://ec.europa.eu/eurostat/cache/metadata/en/apro_cp_esms.htm",
                "captured_at": stamp,
                "berry_ids": [berry_id] if berry_id else [],
                "geography_ids": [geography_id] if geography_id else [],
            }
        )
    return observations
