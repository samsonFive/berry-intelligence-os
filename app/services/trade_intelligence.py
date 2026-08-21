"""UN Comtrade trade-flow acquisition + derived quantitative metrics.

Global Trade / Customs Intelligence V1 mission (2026-08-21). UN Comtrade's
public preview API (`comtradeapi.un.org/public/v1/preview/...`) is the one
official adapter this mission integrates -- chosen over the US Census
International Trade API (real, but requires a registered API key this
mission could not self-provision; see docs/v2/TRADE-INTELLIGENCE-V1.md Part
1), Eurostat/UK HMRC (audited, not implemented this mission), and
Agronometrics (explicitly a secondary/commercial analytic source per the
mission brief, never a replacement for official data -- not queried for
raw figures at all).

Two responsibilities, kept separate on purpose:
1. Acquisition (`TradeIntelligenceService`) -- real HTTP calls, writes only
   untrusted `inbox/evidence/` drafts (`source_type: "trade_statistics_record"`),
   never trusted data. One draft per (reporter, partner, flow, HS code)
   lane, holding a `series[]` of periods -- not one draft per monthly data
   point, per the mission's own instruction.
2. Derived metrics (`year_over_year_change`, `rolling_seasonal_comparison`,
   `unusual_movement`, `partner_flow_changes`) -- pure functions over an
   already-loaded set of trade_observation records (published or draft,
   always labeled). These compute quantitative observations only; nothing
   here creates a trusted Signal or Assessment. A human forms a Signal from
   a derived metric exactly the same way they would from any other
   evidence-backed pattern.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from typing import Any, Callable

import httpx

# Live-observed 2026-08-21: rapid sequential preview requests (the API
# allows only one period per request, so a multi-period lane means many
# requests) can draw a real HTTP 429 from the unauthenticated preview
# endpoint. A short delay between period requests is cheap insurance, not
# a documented rate limit -- the exact limit was not published anywhere
# this mission found.
COMTRADE_REQUEST_DELAY_SECONDS = 1.0

COMTRADE_PREVIEW_URL = "https://comtradeapi.un.org/public/v1/preview/C/M/HS"
COMTRADE_USER_AGENT = "berry-intelligence-os-trade-intelligence/1.0"
COMTRADE_FETCH_TIMEOUT_SECONDS = 20

# UN M49 / Comtrade reporter-partner numeric codes for the geographies this
# mission's pilot actually queried -- live-verified 2026-08-21 (each code
# was confirmed to return real, non-empty data for at least one real query
# during this mission's research). Not a complete world list.
COMTRADE_COUNTRY_CODES: dict[str, str] = {
    "geography-united-states": "842",
    "geography-mexico": "484",
    "geography-peru": "604",
    "geography-chile": "152",
    "geography-united-kingdom": "826",
    "geography-morocco": "504",
    "geography-south-africa": "710",
}
COMTRADE_CODE_TO_GEOGRAPHY: dict[str, str] = {v: k for k, v in COMTRADE_COUNTRY_CODES.items()}

# qtyUnitCode 8 = "Weight in kilograms" per UN Comtrade's own quantity-unit
# reference table (live-confirmed against real query results this mission,
# not assumed) -- the only unit code this mission's real queries returned.
COMTRADE_QTY_UNIT_LABELS: dict[int, str] = {8: "kg"}

TRADE_DOES_NOT_PROVE = (
    "the cause of any observed change (a volume shift correlating with a news event is not proof that event caused it)",
    "retail price or consumer availability",
    "company-level market share (trade statistics are country-level, not company-level)",
    "that a single month's figure represents a durable trend",
    "commercial success or product quality",
)


class TradeIntelligenceError(RuntimeError):
    pass


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def query_comtrade_period(
    *,
    reporter_code: str,
    partner_code: str,
    period: str,
    flow_code: str,
    hs_code: str,
    client: httpx.Client | None = None,
) -> list[dict[str, Any]]:
    """Real, unauthenticated GET against UN Comtrade's public preview API
    for exactly one reporting period (the API itself rejects more than one
    period per preview request -- live-verified 2026-08-21, not assumed).
    `period` is 'YYYYMM'. Raises TradeIntelligenceError on transport/HTTP
    failure or an API-reported error; returns an empty list for a
    legitimate zero-trade or not-yet-reported result (never raises for
    that -- it is a common, real answer, not a failure)."""
    params = {
        "reporterCode": reporter_code,
        "partnerCode": partner_code,
        "period": period,
        "flowCode": flow_code,
        "cmdCode": hs_code,
    }
    try:
        if client is not None:
            response = client.get(COMTRADE_PREVIEW_URL, params=params, timeout=COMTRADE_FETCH_TIMEOUT_SECONDS)
        else:
            response = httpx.get(
                COMTRADE_PREVIEW_URL,
                params=params,
                timeout=COMTRADE_FETCH_TIMEOUT_SECONDS,
                headers={"User-Agent": COMTRADE_USER_AGENT},
                follow_redirects=True,
            )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise TradeIntelligenceError(f"Comtrade query failed ({reporter_code}<-{partner_code}, {period}, {hs_code}): {exc}") from exc
    payload = response.json()
    if payload.get("error"):
        raise TradeIntelligenceError(f"Comtrade API error ({reporter_code}<-{partner_code}, {period}, {hs_code}): {payload['error']}")
    return [row for row in (payload.get("data") or []) if isinstance(row, dict)]


def _period_to_iso(period: str) -> str:
    # '202505' -> '2025-05'
    return f"{period[:4]}-{period[4:6]}"


def normalize_series_row(row: dict[str, Any]) -> dict[str, Any]:
    unit_code = row.get("qtyUnitCode")
    value_basis = "CIF" if row.get("flowCode") == "M" else ("FOB" if row.get("flowCode") == "X" else "unspecified")
    return {
        "period": _period_to_iso(str(row.get("period") or "")),
        "quantity": row.get("qty"),
        "quantity_unit": COMTRADE_QTY_UNIT_LABELS.get(unit_code) if isinstance(unit_code, int) else None,
        "trade_value": row.get("primaryValue"),
        "currency": "USD",  # Comtrade reports all values in USD regardless of reporter -- documented convention, not assumed.
        "value_basis": value_basis,
        "is_estimated": row.get("isQtyEstimated"),
        "is_reported": row.get("isReported"),
        "release_status": "final" if row.get("isReported") else "provisional",
    }


def canonical_lane_id(reporter_code: str, partner_code: str, flow_code: str, hs_code: str) -> str:
    raw = f"{reporter_code}-{partner_code}-{flow_code}-{hs_code}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"trade-{digest}"


def draft_id_for_lane(lane_id: str) -> str:
    return f"ev-trade-{lane_id}"


def build_trade_review_draft(
    *,
    lane_id: str,
    reporter_code: str,
    partner_code: str,
    flow_code: str,
    hs_code: str,
    hs_entry: dict[str, Any],
    series: list[dict[str, Any]],
    captured_date: str,
) -> dict[str, Any]:
    reporter_geo = COMTRADE_CODE_TO_GEOGRAPHY.get(reporter_code)
    partner_geo = COMTRADE_CODE_TO_GEOGRAPHY.get(partner_code)
    flow_label = "imports" if flow_code == "M" else "exports"
    berry_label = " / ".join(hs_entry.get("berry_ids") or []) or "unmapped"
    reporter_label = reporter_geo.replace("geography-", "").replace("-", " ").title() if reporter_geo else reporter_code
    partner_label = (partner_geo.replace("geography-", "").replace("-", " ").title() if partner_geo else "World") if partner_code != "0" else "World"
    title = f"{reporter_label} {flow_label} from {partner_label} -- HS {hs_code} ({hs_entry.get('fresh_or_frozen')}, {berry_label})"
    periods = sorted({s["period"] for s in series})
    summary = (
        f"UN Comtrade monthly trade statistics: {reporter_label} {flow_label} of HS {hs_code} "
        f"({hs_entry.get('description')}) from/to {partner_label}, {len(series)} period(s) "
        f"({periods[0] if periods else '?'} to {periods[-1] if periods else '?'})."
    )
    if hs_entry.get("berry_code_purity") == "multi_berry_combined":
        summary += f" HS code is NOT berry-exclusive -- {hs_entry.get('limitations')}"
    return {
        "id": draft_id_for_lane(lane_id),
        "record_type": "evidence",
        "status": "draft",
        "review_state": "in_review",
        "source_type": "trade_statistics_record",
        "intake_type": "trade_observation",
        "title": title,
        "source_name": "UN Comtrade (public preview API)",
        "source_url": "https://comtradeapi.un.org/public/v1/preview/C/M/HS",
        "published_date": None,
        "captured_date": captured_date,
        "summary": summary,
        "why_it_matters": (
            "Quantitative trade-flow context for this berry/country pair -- an official government-reported "
            "statistic, not an interpretation. See does_not_prove."
        ),
        "submitted_by": "trade-intelligence-monitor",
        "berry_ids": list(hs_entry.get("berry_ids") or []),
        "geography_ids": [g for g in (reporter_geo, partner_geo) if g],
        "entity_ids": [g for g in (reporter_geo, partner_geo) if g],
        "fact_ids": [],
        "relationship_ids": [],
        "strategic_question_ids": [],
        "tags": ["trade", "customs", "quantitative", hs_entry.get("fresh_or_frozen") or ""],
        "auto_captured": False,
        "validated": False,
        "source_authority": "high",
        "source_tier": "tier_1_primary",
        "verification_state": "unverified",
        "does_not_prove": list(TRADE_DOES_NOT_PROVE) + (
            [hs_entry["limitations"]] if hs_entry.get("berry_code_purity") == "multi_berry_combined" else []
        ),
        "trade_observation": {
            "reporter_geography_id": reporter_geo,
            "reporter_name": reporter_label,
            "partner_geography_id": partner_geo,
            "partner_name": partner_label,
            "flow": "import" if flow_code == "M" else "export",
            "hs_code": hs_code,
            "hs_revision": "HS 2022 (H6)",
            "berry_code_purity": hs_entry.get("berry_code_purity"),
            "fresh_or_frozen": hs_entry.get("fresh_or_frozen"),
            "series": series,
            "source_provenance": {
                "api": "UN Comtrade public preview",
                "endpoint": COMTRADE_PREVIEW_URL,
                "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "classification_code": "H6",
            },
        },
        "priority": {
            dim: {"level": "none", "rationale": "Untrusted trade-statistics draft; not yet human-reviewed."}
            for dim in ("reading", "testing", "commercial_position", "monitoring")
        },
    }


@dataclass
class TradeLaneRequest:
    reporter_geo: str
    partner_geo: str
    flow_code: str  # "M" or "X"
    hs_code: str
    periods: list[str]  # ['202501', '202502', ...]


@dataclass
class TradeIntelligenceService:
    inbox_dir: Path
    hs_taxonomy: dict[str, dict[str, Any]]
    query: Callable[..., list[dict[str, Any]]] = query_comtrade_period
    failures: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.operations_dir = self.inbox_dir / "operations" / "trade_intelligence"
        self.state_path = self.operations_dir / "state.json"
        self.evidence_dir = self.inbox_dir / "evidence"

    def fetch_lane(self, request: TradeLaneRequest) -> tuple[str, list[dict[str, Any]]] | None:
        reporter_code = COMTRADE_COUNTRY_CODES.get(request.reporter_geo)
        partner_code = COMTRADE_COUNTRY_CODES.get(request.partner_geo)
        if reporter_code is None or partner_code is None:
            self.failures.append(f"unknown geography for lane {request.reporter_geo}<-{request.partner_geo}")
            return None
        hs_entry = self.hs_taxonomy.get(request.hs_code)
        if hs_entry is None:
            self.failures.append(f"unmapped HS code {request.hs_code}")
            return None
        series: list[dict[str, Any]] = []
        for index, period in enumerate(request.periods):
            if index > 0:
                time.sleep(COMTRADE_REQUEST_DELAY_SECONDS)
            try:
                rows = self.query(
                    reporter_code=reporter_code, partner_code=partner_code, period=period,
                    flow_code=request.flow_code, hs_code=request.hs_code,
                )
            except TradeIntelligenceError as exc:
                self.failures.append(str(exc))
                continue
            # Prefer the single "isReported: true, isAggregate: false" row
            # when present (the real, disaggregated figure); otherwise the
            # best available aggregate row -- never silently sum multiple
            # rows together, which would double-count.
            reported = [r for r in rows if r.get("isReported") and not r.get("isAggregate")]
            chosen = reported[0] if reported else (rows[0] if rows else None)
            if chosen is not None:
                series.append(normalize_series_row(chosen))
        lane_id = canonical_lane_id(reporter_code, partner_code, request.flow_code, request.hs_code)
        return lane_id, series

    def persist_drafts(
        self, lanes: list[tuple[TradeLaneRequest, str, list[dict[str, Any]]]], *, dry_run: bool = False
    ) -> dict[str, Any]:
        state = load_trade_state(self.state_path)
        seen = set(state.get("seen_lane_signatures") or [])
        captured = date.today().isoformat()
        created: list[str] = []
        duplicates: list[str] = []
        review_ready: list[str] = []
        for request, lane_id, series in lanes:
            if not series:
                continue
            signature = f"{lane_id}:{sorted(s['period'] for s in series)}"
            draft_id = draft_id_for_lane(lane_id)
            draft_path = self.evidence_dir / f"{draft_id}.json"
            if signature in seen or draft_path.is_file():
                duplicates.append(lane_id)
                continue
            hs_entry = self.hs_taxonomy[request.hs_code]
            reporter_code = COMTRADE_COUNTRY_CODES[request.reporter_geo]
            partner_code = COMTRADE_COUNTRY_CODES[request.partner_geo]
            draft = build_trade_review_draft(
                lane_id=lane_id, reporter_code=reporter_code, partner_code=partner_code,
                flow_code=request.flow_code, hs_code=request.hs_code, hs_entry=hs_entry,
                series=series, captured_date=captured,
            )
            review_ready.append(draft_id)
            if not dry_run:
                _write_json(draft_path, draft)
                seen.add(signature)
                created.append(draft_id)
        if not dry_run:
            state["seen_lane_signatures"] = sorted(seen)
            state["last_run_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            state["runs"] = (state.get("runs") or [])[-19:] + [
                {"at": state["last_run_at"], "created": created, "duplicates": duplicates, "failures": self.failures}
            ]
            _write_json(self.state_path, state)
        return {"created": created, "duplicates": duplicates, "review_ready": review_ready, "failures": self.failures}


def load_trade_state(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"seen_lane_signatures": [], "runs": []}
    payload = _read_json(path)
    payload.setdefault("seen_lane_signatures", [])
    payload.setdefault("runs", [])
    return payload


def run_trade_intelligence_monitor(
    *,
    inbox_dir: Path,
    hs_taxonomy: dict[str, dict[str, Any]],
    lane_requests: list[TradeLaneRequest],
    dry_run: bool = False,
    query: Callable[..., list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    service = TradeIntelligenceService(inbox_dir=inbox_dir, hs_taxonomy=hs_taxonomy, query=query or query_comtrade_period)
    fetched: list[tuple[TradeLaneRequest, str, list[dict[str, Any]]]] = []
    for request in lane_requests:
        result = service.fetch_lane(request)
        if result is None:
            continue
        lane_id, series = result
        fetched.append((request, lane_id, series))
    persisted = service.persist_drafts(fetched, dry_run=dry_run)
    return {
        "lanes_requested": len(lane_requests),
        "lanes_with_data": len([f for f in fetched if f[2]]),
        "duplicates": len(persisted["duplicates"]),
        "review_ready": len(persisted["review_ready"]),
        "created": persisted["created"],
        "failed": persisted["failures"],
        "dry_run": dry_run,
    }


# ---------------------------------------------------------------------------
# Derived metrics -- pure functions, nothing persisted, nothing auto-trusted.
# Operate on a list of already-loaded trade_observation-shaped records
# (published Evidence, inbox drafts, or a mix -- caller's choice, always
# labeled by the caller if trust distinction matters downstream).
# ---------------------------------------------------------------------------


def _lane_series(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten every record's series into (record, period_entry) rows,
    carrying the record's own lane identity onto each row."""
    rows = []
    for record in records:
        detail = record.get("trade_observation") or {}
        for entry in detail.get("series") or []:
            rows.append({**entry, "_record_id": record.get("id"), "_detail": detail})
    return rows


def year_over_year_change(records: list[dict[str, Any]], *, period: str) -> dict[str, Any] | None:
    """`period` is 'YYYY-MM'. Compares that period's quantity/value against
    the same month one year earlier, across the SAME lane (reporter,
    partner, flow, hs_code) -- never across different lanes. Returns None
    if either period is missing (a real, common, honestly-reported case --
    not an error)."""
    year, month = period.split("-")
    prior_period = f"{int(year) - 1}-{month}"
    rows = _lane_series(records)
    current = next((r for r in rows if r["period"] == period), None)
    prior = next((r for r in rows if r["period"] == prior_period), None)
    if current is None or prior is None:
        return None
    qty_change = None
    if current.get("quantity") is not None and prior.get("quantity"):
        qty_change = (current["quantity"] - prior["quantity"]) / prior["quantity"]
    value_change = None
    if current.get("trade_value") is not None and prior.get("trade_value"):
        value_change = (current["trade_value"] - prior["trade_value"]) / prior["trade_value"]
    return {
        "period": period,
        "prior_period": prior_period,
        "quantity_change_pct": qty_change,
        "value_change_pct": value_change,
        "current_quantity": current.get("quantity"),
        "prior_quantity": prior.get("quantity"),
        "current_value": current.get("trade_value"),
        "prior_value": prior.get("trade_value"),
    }


def rolling_seasonal_comparison(records: list[dict[str, Any]], *, months: int = 3) -> list[dict[str, Any]]:
    """Latest N months' quantity/value, sorted chronologically -- a
    trend-context view, not a scored judgment. Caller decides what (if
    anything) is 'unusual'."""
    rows = sorted(_lane_series(records), key=lambda r: r["period"])
    return rows[-months:]


def unusual_movement(records: list[dict[str, Any]], *, period: str, threshold_pct: float = 0.25) -> dict[str, Any] | None:
    """Flags a period whose quantity moved more than `threshold_pct` from
    the same period a year earlier -- a quantitative flag only, explicitly
    NOT a Signal and NOT auto-trusted. Returns None if YoY cannot be
    computed (see year_over_year_change)."""
    yoy = year_over_year_change(records, period=period)
    if yoy is None or yoy["quantity_change_pct"] is None:
        return None
    flagged = abs(yoy["quantity_change_pct"]) >= threshold_pct
    return {**yoy, "flagged_unusual": flagged, "threshold_pct": threshold_pct}


def partner_flow_changes(
    records_by_partner: dict[str, list[dict[str, Any]]], *, period: str
) -> list[dict[str, Any]]:
    """'Which partner flows expanded/contracted YoY for this period?' --
    across several partner-specific record sets for the same reporter/HS
    lane. Returns only partners where YoY was actually computable; a
    missing partner is reported as absent, not assumed zero."""
    results = []
    for partner_geo, records in records_by_partner.items():
        yoy = year_over_year_change(records, period=period)
        if yoy is not None:
            results.append({"partner_geography_id": partner_geo, **yoy})
    return sorted(results, key=lambda r: (r["quantity_change_pct"] is None, -(r["quantity_change_pct"] or 0)))
