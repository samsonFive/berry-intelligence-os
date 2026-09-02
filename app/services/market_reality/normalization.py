"""Closed-vocabulary commodity/geography normalization for Market Reality V1.

Deliberately explicit and small: a source code maps to a normalized entity
id only when the mapping is unambiguous. A mixed/aggregate category (e.g.
Eurostat's "Berries (excluding strawberries)", which spans raspberry,
blackberry, currants and more) or a geography with no existing entity
(e.g. a supranational aggregate) stays unmapped -- never guessed."""

from __future__ import annotations

# Eurostat apro_cpsh1 crop code -> (berry_id or None, source label, form).
# F3000 stays unmapped on purpose: it is a mixed "other berries" category,
# not a single berry, per E) Commodity Normalization's explicit instruction
# not to pretend incomparable measures are interchangeable.
EUROSTAT_CROP_TO_BERRY: dict[str, tuple[str | None, str, str]] = {
    "S0000": ("berry-strawberry", "Strawberries", "fresh"),
    "F3000": (None, "Berries (excluding strawberries)", "fresh"),
}

# Eurostat apro_cpsh1 structure-of-production indicator -> (metric, unit).
EUROSTAT_INDICATOR_TO_METRIC: dict[str, tuple[str, str]] = {
    "AR_THS_HA": ("ACREAGE", "1000 ha"),
    "HPRD_HUMD_EU_THS_T": ("PRODUCTION", "1000 t"),
    "YLD_HUMD_EU_T_HA": ("YIELD", "t/ha"),
}

# Eurostat geo code -> geography_id, only where a real entity already
# exists in data/entities/geographies/. EU27_2020 (the EU aggregate) is
# intentionally absent: it is not a country and must not be mapped to one.
EUROSTAT_GEO_TO_ENTITY: dict[str, str] = {
    "ES": "geography-spain",
    "DE": "geography-germany",
    "NL": "geography-netherlands",
    "PT": "geography-portugal",
}


def normalize_berry(crop_code: str) -> tuple[str | None, str, str]:
    return EUROSTAT_CROP_TO_BERRY.get(crop_code, (None, crop_code, "unspecified"))


def normalize_geography(geo_code: str) -> str | None:
    return EUROSTAT_GEO_TO_ENTITY.get(geo_code)
