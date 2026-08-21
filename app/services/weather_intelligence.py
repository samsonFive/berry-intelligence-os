"""NASA POWER weather/climate acquisition + berry-relevant derived events.

Weather / Climate Context V1 mission (2026-08-21). NASA POWER's public daily
point API (`power.larc.nasa.gov/api/temporal/daily/point`) is the one
official adapter this mission integrates -- chosen over NOAA Climate Data
Online (real, but requires an email-registered API token this mission could
not self-provision) and ERA5/Copernicus CDS (real, but requires a CDS
account + personal access token, same access-barrier pattern; see
docs/v2/WEATHER-CLIMATE-CONTEXT-V1.md Part 2). Global, keyless, historical
back to 1981, ~0.5-degree (~50km) native grid resolution.

Three responsibilities, kept separate on purpose (mirrors
app/services/trade_intelligence.py exactly):
1. Acquisition (`WeatherIntelligenceService`) -- real HTTP calls, writes only
   untrusted `inbox/evidence/` drafts (`source_type: "weather_climate_record"`),
   never trusted data. One draft per production-region observation window,
   holding a compact daily `series[]` for the comparison window plus a
   compact `baseline_by_month` summary derived from a separate historical
   query -- never one Evidence record per daily reading, and never the raw
   multi-year baseline series itself.
2. Derived events (`frost_event`, `extreme_heat_event`,
   `precipitation_deficit`, `precipitation_excess`, `drought_anomaly`,
   `unusual_temperature_window`) -- pure functions over an already-loaded
   set of weather_observation records. These compute quantitative anomalies
   only; a weather anomaly is a meteorological reading, not proof of crop
   damage or a cause of any trade/market movement (see WEATHER_DOES_NOT_PROVE).
3. Trade-weather corroboration (`weather_context_for_trade_anomaly`) and a
   simple leading-indicator lead-time calculation
   (`leading_indicator_lead_time`) -- both pure, read-only query functions.
   Neither writes an Evidence record, an evidence_link, or a Signal. A human
   reviewer decides whether a returned context bundle is worth a proposed
   `evidence_links` entry, the same discipline already used for the one real
   trade<->regulatory link in Trade Intelligence V1.
"""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

import httpx

POWER_DAILY_POINT_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
POWER_USER_AGENT = "berry-intelligence-os-weather-intelligence/1.0"
POWER_FETCH_TIMEOUT_SECONDS = 30
POWER_COMMUNITY = "AG"
POWER_PARAMETERS = "T2M_MAX,T2M_MIN,PRECTOTCORR"
# NASA POWER's own documented fill value for a date not yet processed/released
# (live-confirmed 2026-08-21: the 3 most recent calendar days of a request
# returned -999.0 while all earlier days in the same request returned real
# readings) -- distinct from a genuine zero reading, never treated as one.
POWER_FILL_VALUE = -999.0

WEATHER_DOES_NOT_PROVE = (
    "that this weather condition caused any observed trade, market, or price movement",
    "crop damage, yield loss, or quality degradation (a weather anomaly is a meteorological reading, not an agronomic damage assessment)",
    "that the single queried point is representative of the entire named production region",
    "a durable climate trend from one anomalous window",
)


class WeatherIntelligenceError(RuntimeError):
    pass


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _yyyymmdd(iso_date: str) -> str:
    return iso_date.replace("-", "")


def _iso_date(yyyymmdd: str) -> str:
    return f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:8]}"


def query_power_range(
    *,
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Real, unauthenticated GET against NASA POWER's public daily point API
    for an arbitrary contiguous date range (unlike UN Comtrade, POWER accepts
    a full multi-year range in one request -- live-verified 2026-08-21: a
    2015-01-01..2024-12-31 request returned in ~1.2s). `start_date`/`end_date`
    are 'YYYY-MM-DD'. Raises WeatherIntelligenceError on transport/HTTP
    failure or an API-reported error. Returns the raw `parameter` dict
    (T2M_MAX/T2M_MIN/PRECTOTCORR keyed by 'YYYYMMDD') plus the response
    header's own `sources` list -- callers normalize from this."""
    params = {
        "parameters": POWER_PARAMETERS,
        "community": POWER_COMMUNITY,
        "longitude": longitude,
        "latitude": latitude,
        "start": _yyyymmdd(start_date),
        "end": _yyyymmdd(end_date),
        "format": "JSON",
    }
    try:
        if client is not None:
            response = client.get(POWER_DAILY_POINT_URL, params=params, timeout=POWER_FETCH_TIMEOUT_SECONDS)
        else:
            response = httpx.get(
                POWER_DAILY_POINT_URL,
                params=params,
                timeout=POWER_FETCH_TIMEOUT_SECONDS,
                headers={"User-Agent": POWER_USER_AGENT},
                follow_redirects=True,
            )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise WeatherIntelligenceError(f"NASA POWER query failed ({latitude},{longitude}, {start_date}..{end_date}): {exc}") from exc
    payload = response.json()
    messages = payload.get("messages") or []
    if messages:
        raise WeatherIntelligenceError(f"NASA POWER API error ({latitude},{longitude}, {start_date}..{end_date}): {messages}")
    parameters = (payload.get("properties") or {}).get("parameter") or {}
    if not parameters:
        raise WeatherIntelligenceError(f"NASA POWER returned no parameter data ({latitude},{longitude}, {start_date}..{end_date})")
    sources = (payload.get("header") or {}).get("sources") or []
    return {"parameters": parameters, "sources": sources}


def normalize_daily_series(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Turns the raw {"T2M_MAX": {"20250101": 30.9, ...}, ...} shape into a
    compact, date-sorted list of {date, t2m_max_c, t2m_min_c,
    precipitation_mm, source_model, is_provisional}. A reading equal to
    POWER_FILL_VALUE means NASA has not yet processed that date -- recorded
    as is_provisional=True with the metric set to None, never as a real
    zero."""
    parameters = raw["parameters"]
    source_model = ", ".join(s for s in raw.get("sources") or [] if s != "POWER") or None
    dates = sorted(set().union(*[set(v.keys()) for v in parameters.values()])) if parameters else []
    series = []
    for day in dates:
        t2m_max = parameters.get("T2M_MAX", {}).get(day)
        t2m_min = parameters.get("T2M_MIN", {}).get(day)
        precip = parameters.get("PRECTOTCORR", {}).get(day)
        provisional = any(v == POWER_FILL_VALUE for v in (t2m_max, t2m_min, precip) if v is not None)
        series.append({
            "date": _iso_date(day),
            "t2m_max_c": None if (t2m_max is None or t2m_max == POWER_FILL_VALUE) else t2m_max,
            "t2m_min_c": None if (t2m_min is None or t2m_min == POWER_FILL_VALUE) else t2m_min,
            "precipitation_mm": None if (precip is None or precip == POWER_FILL_VALUE) else precip,
            "source_model": source_model,
            "is_provisional": provisional,
        })
    return series


def compute_baseline_by_month(raw: dict[str, Any]) -> dict[str, dict[str, float | None]]:
    """Reduces a multi-year raw baseline query to a compact per-calendar-month
    climatological mean -- the baseline's own raw daily readings are
    deliberately never stored on the Evidence draft, only this summary."""
    series = normalize_daily_series(raw)
    by_month: dict[str, dict[str, list[float]]] = {f"{m:02d}": {"t2m_max_c": [], "t2m_min_c": [], "precipitation_mm": []} for m in range(1, 13)}
    for entry in series:
        if entry["is_provisional"]:
            continue
        month = entry["date"][5:7]
        for key in ("t2m_max_c", "t2m_min_c", "precipitation_mm"):
            value = entry[key]
            if value is not None:
                by_month[month][key].append(value)
    result: dict[str, dict[str, float | None]] = {}
    for month, values in by_month.items():
        result[month] = {
            "t2m_max_mean_c": round(sum(values["t2m_max_c"]) / len(values["t2m_max_c"]), 2) if values["t2m_max_c"] else None,
            "t2m_min_mean_c": round(sum(values["t2m_min_c"]) / len(values["t2m_min_c"]), 2) if values["t2m_min_c"] else None,
            "precipitation_mean_mm": round(sum(values["precipitation_mm"]) / len(values["precipitation_mm"]), 3) if values["precipitation_mm"] else None,
        }
    return result


def draft_id_for_region(production_region_id: str) -> str:
    digest = hashlib.sha256(production_region_id.encode("utf-8")).hexdigest()[:16]
    return f"ev-weather-{digest}"


def build_weather_review_draft(
    *,
    production_region_id: str,
    region_entry: dict[str, Any],
    series: list[dict[str, Any]],
    baseline_by_month: dict[str, Any],
    baseline_period: dict[str, str],
    captured_date: str,
) -> dict[str, Any]:
    region_label = region_entry.get("region_name") or production_region_id
    berry_ids = list(region_entry.get("berry_ids") or [])
    dates = sorted({s["date"] for s in series})
    title = f"NASA POWER daily weather -- {region_label} ({production_region_id})"
    summary = (
        f"NASA POWER daily point weather (max/min temperature, precipitation) for {region_label}, "
        f"{len(series)} day(s) ({dates[0] if dates else '?'} to {dates[-1] if dates else '?'}), "
        f"with a {baseline_period.get('start')}..{baseline_period.get('end')} climatological baseline."
    )
    return {
        "id": draft_id_for_region(production_region_id),
        "record_type": "evidence",
        "status": "draft",
        "review_state": "in_review",
        "source_type": "weather_climate_record",
        "intake_type": "weather_observation",
        "title": title,
        "source_name": "NASA POWER (public daily point API)",
        "source_url": POWER_DAILY_POINT_URL,
        "published_date": None,
        "captured_date": captured_date,
        "summary": summary,
        "why_it_matters": (
            "Quantitative production-geography weather context -- a raw meteorological reading against a "
            "climatological baseline, not an interpretation. See does_not_prove."
        ),
        "submitted_by": "weather-intelligence-monitor",
        "berry_ids": berry_ids,
        "geography_ids": [g for g in (region_entry.get("geography_id"),) if g],
        "entity_ids": [g for g in (region_entry.get("geography_id"),) if g],
        "fact_ids": [],
        "relationship_ids": [],
        "strategic_question_ids": [],
        "tags": ["weather", "climate", "quantitative"],
        "auto_captured": False,
        "validated": False,
        "source_authority": "high",
        "source_tier": "tier_1_primary",
        "verification_state": "unverified",
        "does_not_prove": list(WEATHER_DOES_NOT_PROVE),
        "weather_observation": {
            "production_region_id": production_region_id,
            "region_label": region_label,
            "geography_id": region_entry.get("geography_id"),
            "berry_ids": berry_ids,
            "centroid": region_entry.get("centroid"),
            "spatial_resolution_note": (
                f"Single point within {region_label}; NASA POWER's native grid is ~0.5 degrees (~50km). "
                + (region_entry.get("coverage_caveat") or "")
            ).strip(),
            "metrics_tracked": ["t2m_max_c", "t2m_min_c", "precipitation_mm"],
            "baseline_period": baseline_period,
            "baseline_by_month": baseline_by_month,
            "series": series,
            "source_provenance": {
                "api": "NASA POWER daily point API",
                "endpoint": POWER_DAILY_POINT_URL,
                "community": POWER_COMMUNITY,
                "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            },
        },
        "priority": {
            dim: {"level": "none", "rationale": "Untrusted weather-climate draft; not yet human-reviewed."}
            for dim in ("reading", "testing", "commercial_position", "monitoring")
        },
    }


@dataclass
class WeatherRegionRequest:
    production_region_id: str
    baseline_range: tuple[str, str]  # (start, end), 'YYYY-MM-DD'
    comparison_range: tuple[str, str]


@dataclass
class WeatherIntelligenceService:
    inbox_dir: Path
    production_regions: dict[str, dict[str, Any]]
    query: Callable[..., dict[str, Any]] = query_power_range
    failures: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.operations_dir = self.inbox_dir / "operations" / "weather_intelligence"
        self.state_path = self.operations_dir / "state.json"
        self.evidence_dir = self.inbox_dir / "evidence"

    def fetch_region(self, request: WeatherRegionRequest) -> tuple[list[dict[str, Any]], dict[str, Any]] | None:
        region_entry = self.production_regions.get(request.production_region_id)
        if region_entry is None:
            self.failures.append(f"unknown production region {request.production_region_id}")
            return None
        centroid = region_entry.get("centroid") or {}
        latitude, longitude = centroid.get("latitude"), centroid.get("longitude")
        if latitude is None or longitude is None:
            self.failures.append(f"no centroid for production region {request.production_region_id}")
            return None
        try:
            baseline_raw = self.query(
                latitude=latitude, longitude=longitude,
                start_date=request.baseline_range[0], end_date=request.baseline_range[1],
            )
            comparison_raw = self.query(
                latitude=latitude, longitude=longitude,
                start_date=request.comparison_range[0], end_date=request.comparison_range[1],
            )
        except WeatherIntelligenceError as exc:
            self.failures.append(str(exc))
            return None
        baseline_by_month = compute_baseline_by_month(baseline_raw)
        series = normalize_daily_series(comparison_raw)
        return series, baseline_by_month

    def persist_drafts(
        self,
        regions: list[tuple[WeatherRegionRequest, list[dict[str, Any]], dict[str, Any]]],
        *,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        state = load_weather_state(self.state_path)
        seen = set(state.get("seen_region_signatures") or [])
        captured = date.today().isoformat()
        created: list[str] = []
        duplicates: list[str] = []
        review_ready: list[str] = []
        for request, series, baseline_by_month in regions:
            if not series:
                continue
            signature = f"{request.production_region_id}:{request.comparison_range[0]}..{request.comparison_range[1]}"
            draft_id = draft_id_for_region(request.production_region_id)
            draft_path = self.evidence_dir / f"{draft_id}.json"
            if signature in seen or draft_path.is_file():
                duplicates.append(request.production_region_id)
                continue
            region_entry = self.production_regions[request.production_region_id]
            draft = build_weather_review_draft(
                production_region_id=request.production_region_id, region_entry=region_entry,
                series=series, baseline_by_month=baseline_by_month,
                baseline_period={"start": request.baseline_range[0], "end": request.baseline_range[1]},
                captured_date=captured,
            )
            review_ready.append(draft_id)
            if not dry_run:
                _write_json(draft_path, draft)
                seen.add(signature)
                created.append(draft_id)
        if not dry_run:
            state["seen_region_signatures"] = sorted(seen)
            state["last_run_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            state["runs"] = (state.get("runs") or [])[-19:] + [
                {"at": state["last_run_at"], "created": created, "duplicates": duplicates, "failures": self.failures}
            ]
            _write_json(self.state_path, state)
        return {"created": created, "duplicates": duplicates, "review_ready": review_ready, "failures": self.failures}


def load_weather_state(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"seen_region_signatures": [], "runs": []}
    payload = _read_json(path)
    payload.setdefault("seen_region_signatures", [])
    payload.setdefault("runs", [])
    return payload


def run_weather_intelligence_monitor(
    *,
    inbox_dir: Path,
    production_regions: dict[str, dict[str, Any]],
    region_requests: list[WeatherRegionRequest],
    dry_run: bool = False,
    query: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    service = WeatherIntelligenceService(inbox_dir=inbox_dir, production_regions=production_regions, query=query or query_power_range)
    fetched: list[tuple[WeatherRegionRequest, list[dict[str, Any]], dict[str, Any]]] = []
    for request in region_requests:
        result = service.fetch_region(request)
        if result is None:
            continue
        series, baseline_by_month = result
        fetched.append((request, series, baseline_by_month))
    persisted = service.persist_drafts(fetched, dry_run=dry_run)
    return {
        "regions_requested": len(region_requests),
        "regions_with_data": len([f for f in fetched if f[1]]),
        "duplicates": len(persisted["duplicates"]),
        "review_ready": len(persisted["review_ready"]),
        "created": persisted["created"],
        "failed": persisted["failures"],
        "dry_run": dry_run,
    }


# ---------------------------------------------------------------------------
# Derived events -- pure functions, nothing persisted, nothing auto-trusted.
# Operate on a list of already-loaded weather_observation-shaped records
# (published Evidence, inbox drafts, or a mix). Every result carries
# WEATHER_DOES_NOT_PROVE; none of these creates a Signal, a trusted claim,
# or a causal statement.
# ---------------------------------------------------------------------------


def _region_series(records: list[dict[str, Any]], *, production_region_id: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    for record in records:
        detail = record.get("weather_observation") or {}
        if detail.get("production_region_id") == production_region_id:
            return detail.get("series") or [], detail.get("baseline_by_month") or {}
    return [], {}


def _window(series: list[dict[str, Any]], *, start: str, end: str) -> list[dict[str, Any]]:
    return [s for s in series if start <= s["date"] <= end and not s.get("is_provisional")]


def frost_event(
    records: list[dict[str, Any]], *, production_region_id: str, start: str, end: str, threshold_c: float = 0.0
) -> dict[str, Any]:
    """Days in [start, end] whose minimum temperature fell at or below
    threshold_c (default 0C) -- a real, meteorologically-observed frost
    condition, not a claim of frost damage to any crop."""
    series, _ = _region_series(records, production_region_id=production_region_id)
    days = [s for s in _window(series, start=start, end=end) if s.get("t2m_min_c") is not None and s["t2m_min_c"] <= threshold_c]
    return {
        "production_region_id": production_region_id, "window": {"start": start, "end": end},
        "threshold_c": threshold_c, "frost_dates": [d["date"] for d in days],
        "count": len(days), "flagged": len(days) > 0, "does_not_prove": list(WEATHER_DOES_NOT_PROVE),
    }


def extreme_heat_event(
    records: list[dict[str, Any]], *, production_region_id: str, start: str, end: str,
    anomaly_threshold_c: float = 5.0, min_consecutive_days: int = 3,
) -> dict[str, Any]:
    """Runs of >= min_consecutive_days where max temperature exceeded that
    calendar month's baseline mean by >= anomaly_threshold_c -- a positive
    temperature anomaly, not a heat-damage claim."""
    series, baseline = _region_series(records, production_region_id=production_region_id)
    days = _window(series, start=start, end=end)
    deviations = []
    for entry in days:
        month = entry["date"][5:7]
        baseline_mean = (baseline.get(month) or {}).get("t2m_max_mean_c")
        if entry.get("t2m_max_c") is not None and baseline_mean is not None:
            deviations.append((entry["date"], entry["t2m_max_c"] - baseline_mean))
    runs = _consecutive_runs_above(deviations, anomaly_threshold_c, min_consecutive_days)
    return {
        "production_region_id": production_region_id, "window": {"start": start, "end": end},
        "anomaly_threshold_c": anomaly_threshold_c, "min_consecutive_days": min_consecutive_days,
        "runs": runs, "flagged": len(runs) > 0, "does_not_prove": list(WEATHER_DOES_NOT_PROVE),
    }


def unusual_temperature_window(
    records: list[dict[str, Any]], *, production_region_id: str, start: str, end: str,
    anomaly_threshold_c: float = 3.0, min_consecutive_days: int = 3,
) -> dict[str, Any]:
    """Like extreme_heat_event but bidirectional (either max or min
    temperature deviating from baseline by >= anomaly_threshold_c in either
    direction) -- the generic 'unusual temperature window' condition, e.g.
    covers an unusually cold (but not frost-threshold) run as well as heat."""
    series, baseline = _region_series(records, production_region_id=production_region_id)
    days = _window(series, start=start, end=end)
    deviations = []
    for entry in days:
        month = entry["date"][5:7]
        base = baseline.get(month) or {}
        max_dev = (entry["t2m_max_c"] - base["t2m_max_mean_c"]) if entry.get("t2m_max_c") is not None and base.get("t2m_max_mean_c") is not None else None
        min_dev = (entry["t2m_min_c"] - base["t2m_min_mean_c"]) if entry.get("t2m_min_c") is not None and base.get("t2m_min_mean_c") is not None else None
        candidates = [d for d in (max_dev, min_dev) if d is not None]
        deviations.append((entry["date"], max(candidates, key=abs) if candidates else None))
    deviations = [(d, v) for d, v in deviations if v is not None]
    runs = _consecutive_runs_above(deviations, anomaly_threshold_c, min_consecutive_days, absolute=True)
    return {
        "production_region_id": production_region_id, "window": {"start": start, "end": end},
        "anomaly_threshold_c": anomaly_threshold_c, "min_consecutive_days": min_consecutive_days,
        "runs": runs, "flagged": len(runs) > 0, "does_not_prove": list(WEATHER_DOES_NOT_PROVE),
    }


def _consecutive_runs_above(
    deviations: list[tuple[str, float]], threshold: float, min_days: int, *, absolute: bool = False
) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    current: list[tuple[str, float]] = []
    for day, value in deviations:
        meets = (abs(value) >= threshold) if absolute else (value >= threshold)
        if meets:
            current.append((day, value))
        else:
            if len(current) >= min_days:
                runs.append(_summarize_run(current))
            current = []
    if len(current) >= min_days:
        runs.append(_summarize_run(current))
    return runs


def _summarize_run(run: list[tuple[str, float]]) -> dict[str, Any]:
    return {
        "start_date": run[0][0], "end_date": run[-1][0], "days": len(run),
        "mean_deviation_c": round(sum(v for _, v in run) / len(run), 2),
    }


def _expected_precipitation(baseline: dict[str, Any], *, start: str, end: str) -> float | None:
    start_d, end_d = date.fromisoformat(start), date.fromisoformat(end)
    total = 0.0
    day = start_d
    missing = False
    while day <= end_d:
        month = f"{day.month:02d}"
        mean = (baseline.get(month) or {}).get("precipitation_mean_mm")
        if mean is None:
            missing = True
        else:
            total += mean
        day += timedelta(days=1)
    return None if missing else round(total, 2)


def _actual_precipitation(series: list[dict[str, Any]], *, start: str, end: str) -> float | None:
    days = _window(series, start=start, end=end)
    values = [d["precipitation_mm"] for d in days if d.get("precipitation_mm") is not None]
    if not values or len(values) < len(days):
        return None
    return round(sum(values), 2)


def precipitation_deficit(
    records: list[dict[str, Any]], *, production_region_id: str, start: str, end: str, deficit_pct: float = 0.4
) -> dict[str, Any]:
    """Total precipitation over [start, end] vs. the baseline's expected
    total for the same calendar days -- flagged when actual is at or below
    (1 - deficit_pct) of expected. A rainfall shortfall reading, not a
    drought or crop-stress claim by itself."""
    series, baseline = _region_series(records, production_region_id=production_region_id)
    expected = _expected_precipitation(baseline, start=start, end=end)
    actual = _actual_precipitation(series, start=start, end=end)
    pct_of_normal = (actual / expected) if (expected and actual is not None and expected > 0) else None
    flagged = pct_of_normal is not None and pct_of_normal <= (1 - deficit_pct)
    return {
        "production_region_id": production_region_id, "window": {"start": start, "end": end},
        "expected_mm": expected, "actual_mm": actual, "pct_of_normal": round(pct_of_normal, 3) if pct_of_normal is not None else None,
        "deficit_pct_threshold": deficit_pct, "flagged": flagged, "does_not_prove": list(WEATHER_DOES_NOT_PROVE),
    }


def precipitation_excess(
    records: list[dict[str, Any]], *, production_region_id: str, start: str, end: str, excess_pct: float = 0.5
) -> dict[str, Any]:
    """Same comparison as precipitation_deficit, flagged when actual is at
    or above (1 + excess_pct) of expected -- excess rainfall, not a flood or
    disease-pressure claim by itself."""
    series, baseline = _region_series(records, production_region_id=production_region_id)
    expected = _expected_precipitation(baseline, start=start, end=end)
    actual = _actual_precipitation(series, start=start, end=end)
    pct_of_normal = (actual / expected) if (expected and actual is not None and expected > 0) else None
    flagged = pct_of_normal is not None and pct_of_normal >= (1 + excess_pct)
    return {
        "production_region_id": production_region_id, "window": {"start": start, "end": end},
        "expected_mm": expected, "actual_mm": actual, "pct_of_normal": round(pct_of_normal, 3) if pct_of_normal is not None else None,
        "excess_pct_threshold": excess_pct, "flagged": flagged, "does_not_prove": list(WEATHER_DOES_NOT_PROVE),
    }


def drought_anomaly(
    records: list[dict[str, Any]], *, production_region_id: str, start: str, end: str,
    deficit_pct: float = 0.4, min_window_days: int = 30,
) -> dict[str, Any]:
    """A sustained precipitation_deficit -- same computation, but only
    meaningful (and only flagged) over a window of at least min_window_days,
    distinguishing a genuine dry spell from one dry week. Still a rainfall
    reading, not a drought-index product and not a crop-loss claim."""
    window_days = (date.fromisoformat(end) - date.fromisoformat(start)).days + 1
    result = precipitation_deficit(records, production_region_id=production_region_id, start=start, end=end, deficit_pct=deficit_pct)
    result["min_window_days"] = min_window_days
    result["window_days"] = window_days
    if window_days < min_window_days:
        result["flagged"] = False
        result["note"] = f"window is {window_days} day(s), below the {min_window_days}-day minimum for a drought-anomaly read"
    return result


# ---------------------------------------------------------------------------
# Trade-weather corroboration + leading-indicator lead time.
# ---------------------------------------------------------------------------


def _month_bounds(period: str) -> tuple[str, str]:
    year, month = (int(p) for p in period.split("-"))
    last_day = monthrange(year, month)[1]
    return f"{year:04d}-{month:02d}-01", f"{year:04d}-{month:02d}-{last_day:02d}"


def weather_context_for_trade_anomaly(
    *,
    weather_records: list[dict[str, Any]],
    production_region_id: str,
    trade_period: str,
    lookback_days: int = 60,
) -> dict[str, Any]:
    """For a real trade-anomaly period ('YYYY-MM', e.g. from
    trade_intelligence.year_over_year_change()), runs every derived-event
    check over the trade period's own month plus a lookback window before
    it, for the given production region. Returns a structured context
    bundle -- frost/heat/unusual-temperature/precip-deficit/precip-excess
    results plus whether any of them flagged -- never a trusted link and
    never a causal claim. A human reviewer decides whether this is worth a
    proposed evidence_links entry."""
    month_start, month_end = _month_bounds(trade_period)
    window_start = (date.fromisoformat(month_start) - timedelta(days=lookback_days)).isoformat()
    events = {
        "frost": frost_event(weather_records, production_region_id=production_region_id, start=window_start, end=month_end),
        "extreme_heat": extreme_heat_event(weather_records, production_region_id=production_region_id, start=window_start, end=month_end),
        "unusual_temperature": unusual_temperature_window(weather_records, production_region_id=production_region_id, start=window_start, end=month_end),
        "precipitation_deficit": precipitation_deficit(weather_records, production_region_id=production_region_id, start=window_start, end=month_end),
        "precipitation_excess": precipitation_excess(weather_records, production_region_id=production_region_id, start=window_start, end=month_end),
        "drought": drought_anomaly(weather_records, production_region_id=production_region_id, start=window_start, end=month_end),
    }
    any_flagged = any(e.get("flagged") for e in events.values())
    return {
        "production_region_id": production_region_id, "trade_period": trade_period,
        "window": {"start": window_start, "end": month_end}, "lookback_days": lookback_days,
        "weather_events": events, "any_material_anomaly_found": any_flagged,
        "does_not_prove": list(WEATHER_DOES_NOT_PROVE) + [
            "that this window's absence of a flagged anomaly means weather was irrelevant -- only that this pilot's specific checks, thresholds, and single-point region found none"
        ],
    }


def leading_indicator_lead_time(*, weather_anomaly_end_date: str, trade_period: str) -> dict[str, Any]:
    """How many real days elapsed between a weather anomaly's own end date
    and the end of the trade-reporting month it might have anticipated --
    a simple, honest calendar calculation, not a forecast model. Treats a
    trade period as 'observable' at that month's end (a conservative
    assumption; Trade Intelligence V1's own findings show the real
    publication lag is longer than that)."""
    _, period_end = _month_bounds(trade_period)
    lead_days = (date.fromisoformat(period_end) - date.fromisoformat(weather_anomaly_end_date)).days
    return {
        "weather_anomaly_end_date": weather_anomaly_end_date, "trade_period": trade_period,
        "trade_period_end_date": period_end, "lead_time_days": lead_days,
        "note": "Trade period treated as observable at month-end; real Comtrade publication lag is longer (see Trade Intelligence V1), so this is a conservative, not optimistic, lead-time estimate.",
    }
