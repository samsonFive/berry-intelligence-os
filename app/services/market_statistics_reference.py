"""Bounded official reference captures, separate from reviewed intelligence.

No writes, provider calls, inferred yields, unit conversions or trust decisions.
The existing Eurostat collector supplies the original JSON-stat response.
"""
import hashlib
import math
from datetime import datetime
from urllib.parse import urlencode

from app.services.market_reality.eurostat_apro import EUROSTAT_APRO_URL, decode_jsonstat
from app.services.market_reality.normalization import EUROSTAT_GEO_TO_ENTITY

GEOS = ("DE", "ES", "NL", "PT")
INDICATORS = {
    "AR_THS_HA": ("Area", "1000 ha"),
    "HPRD_HUMD_EU_THS_T": ("Harvested production", "1000 t"),
    "YLD_HUMD_EU_T_HA": ("Yield", "t/ha"),
}
METHODOLOGY = "https://ec.europa.eu/eurostat/cache/metadata/en/apro_cp_esms.htm"


def group_id(group):
    key = "|".join(str(group.get(k) or "") for k in ("source", "country_id", "berry_id", "commodity", "period", "source_url"))
    return "market-ref-" + hashlib.sha256(key.encode()).hexdigest()[:16]


def identified_groups(groups):
    """Stable selections use source/category/period, never a position or value."""
    result = []
    for group in groups:
        gid = group_id(group)
        metrics = []
        for metric in group["metrics"]:
            key = metric.get("source_code") or metric["label"]
            mid = gid + "-" + hashlib.sha256(key.encode()).hexdigest()[:8]
            metrics.append({**metric, "id": mid})
        result.append({**group, "id": gid, "metrics": metrics})
    return result


def eurostat_groups(payload, *, captured_at):
    """Latest populated annual period per country; retain original flags/labels.

    An empty future period cannot erase last year's figures. Missing cells are
    absent, not zero. A missing yield is never calculated from area/production.
    Reject out-of-scope or ambiguous dimensions instead of broadening capture.
    """
    stamp = datetime.fromisoformat(captured_at)
    if stamp.utcoffset() is None:
        raise ValueError("Capture time must include its UTC offset")
    dims = payload.get("id") or []
    sizes = payload.get("size") or []
    expected = {"freq", "crops", "strucpro", "geo", "time"}
    if set(dims) != expected or len(dims) != 5 or len(sizes) != 5:
        raise ValueError("Unexpected Eurostat dimensions")
    indexes, labels = {}, {}
    for dim, size in zip(dims, sizes):
        category = payload["dimension"][dim]["category"]
        index = category["index"]
        if not isinstance(index, dict) or set(index.values()) != set(range(size)):
            raise ValueError("Invalid Eurostat dimension index")
        indexes[dim], labels[dim] = index, category.get("label") or {}
    if set(indexes["freq"]) != {"A"} or set(indexes["crops"]) != {"S0000"}:
        raise ValueError("Capture only annual strawberries; mixed berries stay separate")
    if not set(indexes["geo"]).issubset(GEOS) or not set(indexes["strucpro"]).issubset(INDICATORS):
        raise ValueError("Capture exceeds the bounded country/indicator scope")
    years = indexes["time"]
    if not years or len(years) > 5 or any(not y.isdigit() or len(y) != 4 or not stamp.year - 4 <= int(y) <= stamp.year for y in years):
        raise ValueError("Capture only the recent five-year annual window")
    cell_count = math.prod(sizes)
    for key, value in (payload.get("value") or {}).items():
        if not str(key).isdigit() or not 0 <= int(key) < cell_count or isinstance(value, bool):
            raise ValueError("Invalid Eurostat cell position or value")
    rows = decode_jsonstat(payload)
    flags = payload.get("status") or {}
    by_geo = {}
    for row in rows:
        if not math.isfinite(row["value"]) or row["value"] < 0:
            raise ValueError("Invalid Eurostat numeric value")
        flat = 0
        for dim, size in zip(dims, sizes):
            flat = flat * size + indexes[dim][row[dim]]
        row["source_flag"] = flags.get(str(flat), "")
        if "c" in row["source_flag"]:
            continue  # Confidential cells are never public reference figures.
        by_geo.setdefault(row["geo"], []).append(row)
    if not by_geo:
        raise ValueError("No populated Eurostat cells; keep the previous reference")
    groups = []
    for geo, rows in sorted(by_geo.items()):
        year = max(r["time"] for r in rows)
        selected = {r["strucpro"]: r for r in rows if r["time"] == year}
        url = EUROSTAT_APRO_URL + "?" + urlencode({"format": "JSON", "lang": "en", "crops": "S0000", "geo": geo, "time": year})
        metrics = []
        for code, (label, unit) in INDICATORS.items():
            if code not in selected:
                continue
            row = selected[code]
            metrics.append({"label": label, "value": row["value"], "unit": unit,
                            "source_code": code, "source_label": labels["strucpro"].get(code, code), "source_flag": row["source_flag"]})
        groups.append({"country_id": EUROSTAT_GEO_TO_ENTITY[geo], "country": labels["geo"].get(geo, geo),
                       "berry_id": "berry-strawberry", "commodity": "Strawberries", "period": year + " calendar year",
                       "source": "Eurostat", "source_url": url, "locator": "apro_cpsh1 · S0000 · " + geo + " · " + year,
                       "published_date": "Not supplied", "source_updated_at": payload.get("updated") or "Not supplied",
                       "accessed_date": stamp.date().isoformat(), "methodology_url": METHODOLOGY,
                       "status": "Official statistics · original cell flags retained",
                       "basis": "Production counts harvested fruit; USDA utilization figures count fruit used or sold. Figures keep the source units and are not combined. Eurostat changed its reporting framework in 2025, so earlier years may differ in coverage. Missing yield and other cells remain unknown.",
                       "metrics": metrics})
    return groups


def flag_label(flag):
    if not flag:
        return "No status flag supplied"
    return {"p": "Provisional", "e": "Estimated", "b": "Break in series", "d": "Definition differs"}.get(flag, "Source flag: " + flag)
