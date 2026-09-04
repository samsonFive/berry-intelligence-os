"""Evidence-grounded change observations and scenarios — not forecasts.

Derived from an already-assembled ResearchPacket. Creates no store,
assigns no probabilities, and never mutates the packet.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Iterable, Mapping

CHANGE_TYPES = (
    "COMPETITOR_ACTIVITY_CHANGE",
    "GEOGRAPHIC_EXPANSION",
    "GENETICS_ACTIVITY_CHANGE",
    "COMMERCIALIZATION_CHANGE",
    "PARTNERSHIP_CHANGE",
    "PBR_IP_CHANGE",
    "MARKET_CONDITION_CHANGE",
    "SUPPLY_CHANGE",
    "LEADERSHIP_CHANGE",
    "LEGAL_CONSTRAINT_CHANGE",
    "COVERAGE_CHANGE",
    "GENETICS_GEOGRAPHIC_EXPANSION",
    "GEOGRAPHIC_PROPAGATION",
    "OTHER",
)

MOVE_TO_CHANGE = {
    "EXPANSION": "GEOGRAPHIC_EXPANSION",
    "PRODUCTION_EXPANSION": "GEOGRAPHIC_EXPANSION",
    "MARKET_ENTRY": "GEOGRAPHIC_EXPANSION",
    "MARKET_ACCESS": "GEOGRAPHIC_EXPANSION",
    "SUPPLY / PRODUCTION_SHIFT": "SUPPLY_CHANGE",
    "GENETICS_LAUNCH": "GENETICS_ACTIVITY_CHANGE",
    "VARIETY_LAUNCH": "GENETICS_ACTIVITY_CHANGE",
    "GENETICS_INNOVATION": "GENETICS_ACTIVITY_CHANGE",
    "R&D / TECHNOLOGY": "GENETICS_ACTIVITY_CHANGE",
    "VARIETY_COMMERCIALIZATION": "COMMERCIALIZATION_CHANGE",
    "RETAIL_PROGRAM": "COMMERCIALIZATION_CHANGE",
    "LICENSING": "PARTNERSHIP_CHANGE",
    "PARTNERSHIP": "PARTNERSHIP_CHANGE",
    "ACQUISITION / INVESTMENT": "PARTNERSHIP_CHANGE",
    "PBR / IP": "PBR_IP_CHANGE",
    "LEADERSHIP": "LEADERSHIP_CHANGE",
    "LEGAL / COMPETITIVE_CONSTRAINT": "LEGAL_CONSTRAINT_CHANGE",
}

EVENT_TO_CHANGE = {
    "PRODUCTION_EXPANSION": "GEOGRAPHIC_EXPANSION",
    "MARKET_ACCESS": "GEOGRAPHIC_EXPANSION",
    "VARIETY_LAUNCH": "GENETICS_ACTIVITY_CHANGE",
    "GENETICS_INNOVATION": "GENETICS_ACTIVITY_CHANGE",
    "LICENSING": "PARTNERSHIP_CHANGE",
    "PARTNERSHIP": "PARTNERSHIP_CHANGE",
    "LEADERSHIP": "LEADERSHIP_CHANGE",
    "PBR": "PBR_IP_CHANGE",
    "PATENT": "PBR_IP_CHANGE",
    "PBR / PVP": "PBR_IP_CHANGE",
    "RETAIL_PROGRAM": "COMMERCIALIZATION_CHANGE",
    "SUPPLY_CHANGE": "SUPPLY_CHANGE",
    "LEGAL": "LEGAL_CONSTRAINT_CHANGE",
}

FORBIDDEN_CLAIMS = (
    "will definitely",
    "forecast",
    "probability",
    "% likely",
    "hortifrut will",
    "planasa will",
    "fall creek will",
)

_SUPPLY_HINTS = ("export", "volume", "production", "supply", "shipment", "tonnage")
_PRICE_HINTS = ("price", "value", "unit value", "fob")


def _parse_day(value: Any) -> date | None:
    text = str(value or "")[:10]
    if len(text) < 10:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _source_published(row: Mapping[str, Any]) -> date | None:
    stamps: list[date] = []
    for key in ("supporting_sources", "sources"):
        for source in row.get(key) or []:
            stamp = _parse_day(source.get("published_date") or source.get("date") or source.get("event_date"))
            if stamp:
                stamps.append(stamp)
    return min(stamps) if stamps else None


def _event_date(row: Mapping[str, Any]) -> date | None:
    if _is_market_row(row):
        return None
    for key in ("published_date", "event_date", "effective_date"):
        stamp = _parse_day(row.get(key))
        if stamp:
            return stamp
    published = _source_published(row)
    if published:
        return published
    for key in ("date", "latest_update"):
        stamp = _parse_day(row.get(key))
        if stamp:
            return stamp
    return None


def _seen_date(row: Mapping[str, Any]) -> date | None:
    stamps: list[date] = []
    for key in ("captured_date", "first_seen", "captured_at", "latest_update"):
        stamp = _parse_day(row.get(key))
        if stamp:
            stamps.append(stamp)
    presented = _parse_day(row.get("date"))
    event = _source_published(row) or _parse_day(row.get("event_date") or row.get("published_date"))
    if presented and event and presented > event:
        stamps.append(presented)
    return max(stamps) if stamps else None


def _row_id(row: Mapping[str, Any]) -> str:
    return str(row.get("id") or "")


def _title(row: Mapping[str, Any]) -> str:
    return str(row.get("title") or row.get("what_happened") or row.get("statement") or _row_id(row))


def _kind(row: Mapping[str, Any]) -> str:
    return str(
        row.get("move_type")
        or row.get("event_type")
        or row.get("structured_kind")
        or row.get("trust_class")
        or "OTHER"
    )


def _looks_like_market_text(row: Mapping[str, Any]) -> bool:
    hay = " ".join(str(row.get(key) or "") for key in ("title", "what_happened", "metric")).casefold()
    return any(hint in hay for hint in (*_SUPPLY_HINTS, *_PRICE_HINTS, "tonnes", "tons of"))


def _change_type_for(row: Mapping[str, Any]) -> str:
    kind = _kind(row)
    mapped = MOVE_TO_CHANGE.get(kind) or EVENT_TO_CHANGE.get(kind)
    if mapped:
        return mapped
    if _is_market_row(row) or _looks_like_market_text(row):
        return _market_change_type(row)
    if kind in {"PATENT", "PBR / PVP"}:
        return "PBR_IP_CHANGE"
    return "COMPETITOR_ACTIVITY_CHANGE"


def _company_ids(row: Mapping[str, Any]) -> list[str]:
    if row.get("company_id"):
        return [str(row["company_id"])]
    return [
        str(value)
        for value in (row.get("company_ids") or row.get("entity_ids") or [])
        if str(value).startswith("company-")
    ]


def _trust_state(row: Mapping[str, Any]) -> str:
    return str(row.get("trust_state") or row.get("trust_class") or row.get("layer") or "LIVE / UNREVIEWED")


def _is_market_row(row: Mapping[str, Any]) -> bool:
    kind = str(row.get("structured_kind") or row.get("trust_class") or "").upper()
    return "MARKET" in kind or row.get("pct_change") is not None or row.get("latest_vs_previous")


def split_windows(window_days: int, *, today: date) -> tuple[date, date, date]:
    """BEFORE starts at today-window; NOW starts at the midpoint."""
    days = max(int(window_days or 30), 2)
    start = today - timedelta(days=days)
    mid = today - timedelta(days=days // 2)
    return start, mid, today


def classify_coverage_artifact(row: Mapping[str, Any], *, mid: date, today: date) -> bool:
    """True when Berry OS newly saw an older event — not a recent competitive change."""
    event = _event_date(row)
    seen = _seen_date(row)
    if seen is None or event is None:
        return False
    return seen >= mid and seen <= today and event < mid


def change_question(text: str) -> bool:
    folded = str(text or "").casefold()
    return any(term in folded for term in (
        "what changed",
        "what has shifted",
        "what has changed",
        "what might",
        "what could",
        "scenarios",
        "this season",
        "competitive position",
    ))


def _period_label(start: date, end: date) -> str:
    return f"{start.isoformat()} to {end.isoformat()}"


def _summarize(rows: list[Mapping[str, Any]], empty: str) -> str:
    if not rows:
        return empty
    kinds: list[str] = []
    for row in rows:
        label = _kind(row).replace("_", " ").casefold()
        if label not in kinds:
            kinds.append(label)
    lead = _title(rows[0])
    if len(rows) == 1:
        return lead
    return f"{lead} plus {len(rows) - 1} other dated item{'s' if len(rows) != 2 else ''} ({', '.join(kinds[:4])})."


def _copy_rows(packet: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, fallback_kind in (
        ("competitive_moves", "COMPETITIVE MOVE"),
        ("radar_developments", "RADAR DEVELOPMENT"),
        ("evidence", "EVIDENCE"),
        ("signals", "SIGNAL"),
        ("assessments", "ASSESSMENT"),
        ("rights_ip", "RIGHTS / IP"),
        ("related_genetics", "RELATED GENETICS"),
    ):
        for row in packet.get(key) or []:
            payload = dict(row)
            payload["_origin"] = key
            payload["_fallback_kind"] = fallback_kind
            rows.append(payload)
    return rows


def _market_change_type(row: Mapping[str, Any]) -> str:
    hay = " ".join(
        str(row.get(key) or "")
        for key in ("metric", "title", "structured_kind")
    ).casefold()
    if any(hint in hay for hint in _PRICE_HINTS):
        return "MARKET_CONDITION_CHANGE"
    if any(hint in hay for hint in _SUPPLY_HINTS):
        return "SUPPLY_CHANGE"
    return "MARKET_CONDITION_CHANGE"


def _market_changes(packet: Mapping[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in packet.get("market_context") or []:
        if not _is_market_row(row) and not row.get("title"):
            continue
        change = dict(row.get("latest_vs_previous") or {})
        pct = change.get("pct_change", row.get("pct_change"))
        previous_period = change.get("previous_period") or row.get("previous_period")
        latest_period = change.get("latest_period") or row.get("latest_period")
        previous_value = change.get("previous_value", row.get("previous_value"))
        latest_value = change.get("latest_value", row.get("latest_value"))
        unit = change.get("unit") or row.get("unit") or ""
        title = _title(row)
        if pct is None and not title:
            continue
        before = (
            f"{previous_period}: {previous_value} {unit}".strip()
            if previous_period is not None and previous_value is not None
            else "Earlier Market Reality period recorded in the series title."
        )
        now = (
            f"{latest_period}: {latest_value} {unit}".strip()
            if latest_period is not None and latest_value is not None
            else title
        )
        out.append({
            "change_type": _market_change_type(row),
            "what_changed": title or "Market Reality recorded a period-to-period change.",
            "before": before,
            "now": now,
            "evidence_basis": (
                "Deterministic latest-versus-previous Market Reality arithmetic. "
                "Not a confidence percentage and not a forecast."
            ),
            "coverage_notes": (
                "This is an observed series delta. Absence of a matching company move "
                "does not explain why the series moved."
            ),
            "supporting_ids": [_row_id(row)] if _row_id(row) else [],
            "first_observed": str(previous_period or row.get("date") or ""),
            "last_updated": str(latest_period or row.get("date") or ""),
        })
    return out


def build_change_scenario(
    scope: Any,
    packet: Mapping[str, Any],
    *,
    today: date | None = None,
) -> dict[str, Any]:
    """Derived before/now/change/scenario model over an assembled packet."""
    today = today or date.today()
    window_days = int(getattr(scope, "window_days", None) or (packet.get("scope") or {}).get("window_days") or 30)
    start, mid, end = split_windows(window_days, today=today)
    from app.services.genetics_geography import (
        IN_SCOPE,
        build_genetics_geography,
        wants_genetics_geography,
    )

    copied = _copy_rows(packet)
    genetics_geo = None
    if wants_genetics_geography(scope) or packet.get("related_genetics"):
        genetics_geo = build_genetics_geography(scope, packet, copied)
        rows = [
            row for row in genetics_geo["classified_rows"]
            if row.get("_geo_class") == IN_SCOPE
        ]
    else:
        rows = [row for row in copied if _row_fits_scope(scope, packet, row)]

    coverage_ids = {
        _row_id(row) or str(index)
        for index, row in enumerate(rows)
        if classify_coverage_artifact(row, mid=mid, today=today)
    }
    coverage_rows = [
        row for index, row in enumerate(rows)
        if (_row_id(row) or str(index)) in coverage_ids
    ]
    dated = [row for row in rows if _event_date(row)]
    before_rows = [
        row for row in dated
        if start <= (_event_date(row) or start) < mid and (_row_id(row) not in coverage_ids)
    ]
    now_rows = [
        row for row in dated
        if mid <= (_event_date(row) or end) <= end and (_row_id(row) not in coverage_ids)
    ]

    changes: list[dict[str, Any]] = []
    if coverage_rows:
        changes.append({
            "change_type": "COVERAGE_CHANGE",
            "what_changed": (
                f"Berry OS newly indexed {len(coverage_rows)} older item"
                f"{'s' if len(coverage_rows) != 1 else ''} in the later window. "
                "That is a coverage change, not a recent competitive development."
            ),
            "before": "Those events already had earlier event/published dates.",
            "now": _summarize(coverage_rows, "No newly indexed older items."),
            "evidence_basis": (
                f"{len(coverage_rows)} items with captured/first-seen in the later window "
                "and an earlier event date."
            ),
            "coverage_notes": "Do not treat source onboarding or delayed indexing as competitor activity.",
            "supporting_ids": [_row_id(row) for row in coverage_rows if _row_id(row)][:8],
            "first_observed": min((_seen_date(row) or mid).isoformat() for row in coverage_rows),
            "last_updated": max((_seen_date(row) or end).isoformat() for row in coverage_rows),
        })

    structured_market = _market_changes(packet)
    changes.extend(structured_market)
    if structured_market:
        before_rows = [row for row in before_rows if not _is_weaker_market_article(row)]
        now_rows = [row for row in now_rows if not _is_weaker_market_article(row)]

    by_type: dict[str, list[dict[str, Any]]] = {}
    for row in now_rows:
        by_type.setdefault(_change_type_for(row), []).append(row)
    names = {row.get("id"): row.get("name") for row in packet.get("companies") or []}
    for change_type, current in by_type.items():
        earlier = [row for row in before_rows if _change_type_for(row) == change_type]
        companies: list[str] = []
        for row in current:
            for company_id in _company_ids(row):
                name = names.get(company_id) or company_id
                if name not in companies:
                    companies.append(str(name))
        actor = ", ".join(companies[:3]) or "Observed activity"
        isolated = len(current) == 1 and not earlier
        if isolated:
            what = (
                f"{actor}: later window shows an isolated {_kind(current[0]).replace('_', ' ').casefold()} "
                f"item — {_title(current[0])}. That is not yet a sustained pattern."
            )
        elif earlier:
            what = (
                f"{actor}: {change_type.replace('_', ' ').title()} moved from "
                f"{_summarize(earlier, 'no earlier dated items')} "
                f"to {_summarize(current, 'no later dated items')}."
            )
        else:
            what = (
                f"{actor}: {change_type.replace('_', ' ').title()} is newly visible in the later window "
                f"({len(current)} dated item{'s' if len(current) != 1 else ''}) with no matching earlier-window items."
            )
        changes.append({
            "change_type": change_type,
            "what_changed": what,
            "before": _summarize(earlier, "No dated items of this type in the earlier window."),
            "now": _summarize(current, "No dated items of this type in the later window."),
            "evidence_basis": (
                f"{len(current)} later-window items and {len(earlier)} earlier-window items. "
                "This is a count of dated records, not a confidence percentage."
            ),
            "coverage_notes": (
                "Weak evidence — a single later-window item is not a sustained pattern."
                if isolated else
                "Evidence is the dated records listed; absence of a type is not proof it stopped."
            ),
            "supporting_ids": [_row_id(row) for row in [*current, *earlier] if _row_id(row)][:8],
            "first_observed": min(_event_date(row).isoformat() for row in current),  # type: ignore[union-attr]
            "last_updated": max(_event_date(row).isoformat() for row in current),  # type: ignore[union-attr]
        })

    if not changes and (now_rows or before_rows):
        changes.append({
            "change_type": "OTHER",
            "what_changed": "Dated items exist in this window, but they do not form a typed pattern beyond isolated events.",
            "before": _summarize(before_rows, "No earlier-window dated items."),
            "now": _summarize(now_rows, "No later-window dated items."),
            "evidence_basis": f"{len(now_rows)} later-window and {len(before_rows)} earlier-window dated records.",
            "coverage_notes": "Do not manufacture a narrative from isolated events.",
            "supporting_ids": [_row_id(row) for row in [*now_rows, *before_rows] if _row_id(row)][:8],
            "first_observed": (min(_event_date(row) for row in dated).isoformat() if dated else start.isoformat()),
            "last_updated": (max(_event_date(row) for row in dated).isoformat() if dated else end.isoformat()),
        })

    if genetics_geo:
        changes.extend(genetics_geo.get("program_expansions") or [])
        for row in genetics_geo.get("propagation") or []:
            changes.append({
                "change_type": "GEOGRAPHIC_PROPAGATION",
                "what_changed": row["text"],
                "before": "The same genetics object had not yet been assembled across these geographies in this packet.",
                "now": row["text"],
                "evidence_basis": "Shared Variety, breeding program, IP family, or multi-company platform across geographies.",
                "coverage_notes": "This is an observed footprint, not a claim of global strategy.",
                "supporting_ids": list(row.get("source_ids") or [])[:8],
                "first_observed": "",
                "last_updated": "",
            })

    scenarios = _scenarios(changes, now_rows, packet, genetics_geo=genetics_geo)
    competitor_next = _competitor_next(now_rows, packet)
    questions = _generated_questions(changes, scope)
    timeline = _timeline([*now_rows, *before_rows, *coverage_rows])
    if genetics_geo and genetics_geo.get("timeline"):
        timeline = [
            {
                "date": row["date"],
                "title": row["genetics_development"],
                "kind": row.get("kind") or "GENETICS",
                "source": row.get("geography") or "",
                "trust_state": row.get("geo_class") or "",
                "id": row.get("id") or "",
                "href": "",
                "coverage_artifact": False,
                "geography": row.get("geography") or "",
                "relationship": row.get("relationship") or "",
            }
            for row in genetics_geo["timeline"]
        ]
    temporal = _temporal_differences(scope, packet, before_rows, now_rows)

    blob = " ".join(
        str(item.get("what_changed") or item.get("text") or "")
        for item in [*changes, *scenarios, *competitor_next]
    ).casefold()
    for phrase in FORBIDDEN_CLAIMS:
        if phrase in blob:
            scenarios = [row for row in scenarios if phrase not in str(row).casefold()]
            competitor_next = [row for row in competitor_next if phrase not in str(row).casefold()]

    return {
        "before_period": _period_label(start, mid - timedelta(days=1)),
        "after_period": _period_label(mid, end),
        "window_days": window_days,
        "changes": changes[:8],
        "scenarios": scenarios[:6],
        "competitor_next": competitor_next[:6],
        "questions": questions[:6],
        "timeline": timeline[:12],
        "temporal_differences": temporal[:6],
        "coverage_notes": [
            row["what_changed"] for row in changes if row["change_type"] == "COVERAGE_CHANGE"
        ],
        "genetics_geography": (
            {
                "in_scope": genetics_geo["in_scope"],
                "cross_geography_related": genetics_geo["cross_geography_related"],
                "global_platform_context": genetics_geo["global_platform_context"],
                "excluded": genetics_geo["excluded"],
                "footprints": genetics_geo["footprints"],
                "propagation": genetics_geo["propagation"],
                "timeline": genetics_geo["timeline"],
                "what_this_may_mean": _genetics_meaning(genetics_geo),
                "watch_next": _genetics_watch(genetics_geo),
            }
            if genetics_geo
            else None
        ),
        "method_note": (
            "BEFORE is the earlier half of the selected window; NOW is the later half. "
            "Dates use published/event dates, not captured_date. "
            "Cross-geography genetics stay in a separate section and only when an explicit "
            "Variety, platform, IP family, or multi-company program is shared. "
            "Scenarios are hypotheses to watch, not forecasts, and have no probabilities."
        ),
    }


def _genetics_meaning(model: Mapping[str, Any]) -> list[dict[str, Any]]:
    from app.services.genetics_geography import _what_this_may_mean

    return _what_this_may_mean(model)


def _genetics_watch(model: Mapping[str, Any]) -> list[dict[str, Any]]:
    from app.services.genetics_geography import _watch_next

    return _watch_next(model)


def _scenarios(
    changes: list[dict[str, Any]],
    now_rows: list[Mapping[str, Any]],
    packet: Mapping[str, Any],
    *,
    genetics_geo: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    ids = [sid for change in changes for sid in change.get("supporting_ids") or []]
    types = {change["change_type"] for change in changes}
    supply = [change for change in changes if change["change_type"] == "SUPPLY_CHANGE"]
    market = [change for change in changes if change["change_type"] == "MARKET_CONDITION_CHANGE"]
    structured_ids = [
        sid
        for row in packet.get("market_context") or []
        if row.get("latest_vs_previous") or str(row.get("trust_class") or "") == "MARKET REALITY"
        for sid in ([_row_id(row)] if _row_id(row) else [])
    ]
    market_ids = structured_ids or [sid for change in [*supply, *market] for sid in change.get("supporting_ids") or []]
    hay = " ".join(change.get("what_changed") or "" for change in [*supply, *market]).casefold()
    opposing = (
        any(hint in hay for hint in _SUPPLY_HINTS)
        and any(hint in hay for hint in _PRICE_HINTS)
        and ("+" in hay or "up" in hay)
        and ("-" in hay or "down" in hay)
    )
    if "MARKET_CONDITION_CHANGE" in types or "SUPPLY_CHANGE" in types:
        if opposing or supply or market:
            out.extend([
                _scenario(
                    "Continued supply expansion could keep pressuring price.",
                    "A volume/export series moved while a price series moved the other way, or volume rose without a matching price recovery.",
                    "A later Market Reality period shows volume still up and price still down.",
                    "Volume stalls or price recovers in the next Market Reality period.",
                    "Next Market Reality capture for this geography/berry.",
                    market_ids or ids,
                ),
                _scenario(
                    "Demand growth could absorb additional volume.",
                    "Volume can rise without implying unsold fruit if destination demand also moved.",
                    "A later period shows volume up with a stable or recovering price.",
                    "Price keeps falling while inventories or quality complaints appear in dated sources.",
                    "Price series plus any destination-market notes already in this packet.",
                    market_ids or ids,
                ),
                _scenario(
                    "Weather, quality, or market-access constraints could interrupt expansion.",
                    "Supply expansions in berries are routinely interrupted by weather and access — only watch this if dated items exist.",
                    "A later dated item reports weather, quality, or access interruption in the same geography.",
                    "Volume and quality both continue without interruption in later dated items.",
                    "Radar Developments and trusted Evidence in this geography.",
                    market_ids or ids,
                ),
            ])
    if "GENETICS_ACTIVITY_CHANGE" in types or "COMMERCIALIZATION_CHANGE" in types:
        out.append(_scenario(
            "Based on current observed activity, one plausible next development is further commercialization of named cultivars.",
            "Later-window genetics or commercialization records already exist.",
            "A later Competitive Move of type VARIETY_COMMERCIALIZATION or RETAIL_PROGRAM cites the same companies or varieties.",
            "Later items stay at trial/launch language with no commercialization record.",
            "Competitive Moves classified as commercialization or retail program.",
            ids,
        ))
    if "PARTNERSHIP_CHANGE" in types or "GEOGRAPHIC_EXPANSION" in types:
        out.append(_scenario(
            "Based on current observed activity, one plausible next development is another partnership or geography extension in the same pattern.",
            "Later-window partnership or expansion records already exist.",
            "A later move of the same type appears for the same company.",
            "No further partnership or expansion records appear while other move types dominate.",
            "Competitive Moves of type PARTNERSHIP, LICENSING, EXPANSION, or MARKET_ENTRY.",
            ids,
        ))
    if genetics_geo and (genetics_geo.get("cross_geography_related") or genetics_geo.get("propagation")):
        watch_ids = [
            sid
            for row in [
                *(genetics_geo.get("cross_geography_related") or []),
                *(genetics_geo.get("propagation") or []),
            ]
            for sid in (row.get("source_ids") or ([row.get("id")] if row.get("id") else []))
            if sid
        ]
        out.append(_scenario(
            "Additional geographic commercialization is a development to watch.",
            "The same Variety, breeding platform, or multi-company program already appears in more than one geography.",
            "A later dated commercialization or licensing record appears in another geography for the same genetics object.",
            "Later items stay in the original geography with no further licensing or commercialization record.",
            "Licensing, commercialization, and variety-launch records for the same genetics object.",
            watch_ids or ids,
        ))
    return [row for row in out if row.get("source_ids")]


def _scenario(text: str, why: str, confirm: str, refute: str, watch: str, source_ids: Iterable[str]) -> dict[str, Any]:
    ids = [str(value) for value in source_ids if value]
    return {
        "text": text,
        "why_plausible": why,
        "supporting_evidence": ", ".join(ids[:8]),
        "would_confirm": confirm,
        "would_refute": refute,
        "watch": watch,
        "source_ids": ids[:8],
        "kind": "SCENARIO TO WATCH",
    }


def _competitor_next(now_rows: list[Mapping[str, Any]], packet: Mapping[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    by_company: dict[str, list[Mapping[str, Any]]] = {}
    for row in now_rows:
        for company_id in _company_ids(row):
            by_company.setdefault(company_id, []).append(row)
    names = {row.get("id"): row.get("name") for row in packet.get("companies") or []}
    for company_id, rows in by_company.items():
        kinds = [_kind(row) for row in rows]
        name = names.get(company_id) or company_id
        ids = [_row_id(row) for row in rows if _row_id(row)]
        if any(
            (kind in MOVE_TO_CHANGE and MOVE_TO_CHANGE[kind] == "GENETICS_ACTIVITY_CHANGE")
            or kind in {"GENETICS_LAUNCH", "VARIETY_LAUNCH", "GENETICS_INNOVATION"}
            for kind in kinds
        ):
            out.append({
                "text": (
                    f"Based on current observed activity, one plausible next development is {name} "
                    "extending genetics activity into commercialization or licensing — not a prediction that they will."
                ),
                "source_ids": ids[:6],
                "kind": "PLAUSIBLE NEXT MOVE",
            })
        if any(MOVE_TO_CHANGE.get(kind) == "GEOGRAPHIC_EXPANSION" or kind in {"EXPANSION", "MARKET_ENTRY"} for kind in kinds):
            out.append({
                "text": (
                    f"Based on current observed activity, one plausible next development is {name} "
                    "adding another geography or production footprint in the same pattern."
                ),
                "source_ids": ids[:6],
                "kind": "PLAUSIBLE NEXT MOVE",
            })
        if any(MOVE_TO_CHANGE.get(kind) == "PARTNERSHIP_CHANGE" or kind in {"PARTNERSHIP", "LICENSING"} for kind in kinds):
            out.append({
                "text": (
                    f"Based on current observed activity, one plausible next development is {name} "
                    "adding another partnership or licensing counterpart."
                ),
                "source_ids": ids[:6],
                "kind": "PLAUSIBLE NEXT MOVE",
            })
    return [row for row in out if row.get("source_ids")]


def _generated_questions(changes: list[dict[str, Any]], scope: Any) -> list[dict[str, Any]]:
    berry = getattr(scope, "berry_id", None) or (getattr(scope, "as_dict", lambda: {})() or {}).get("berry_id") or "this berry"
    berry_label = str(berry).removeprefix("berry-").replace("-", " ")
    out: list[str] = []
    types = {change["change_type"] for change in changes}
    if "GENETICS_ACTIVITY_CHANGE" in types or "COMMERCIALIZATION_CHANGE" in types:
        out.append("Is this an isolated launch or a sustained commercialization pattern?")
        out.append("Is genetics activity translating into production scale?")
    if "MARKET_CONDITION_CHANGE" in types or "SUPPLY_CHANGE" in types:
        out.append(f"Is {berry_label} export/price movement structural or a single-period swing?")
    if "GEOGRAPHIC_EXPANSION" in types:
        out.append("Is a new geography becoming strategically important, or a one-off mention?")
    if "COVERAGE_CHANGE" in types:
        out.append("Which of these later-window items are newly collected older events rather than new activity?")
    if "LEADERSHIP_CHANGE" in types:
        out.append("Does the leadership change coincide with a visible strategy shift, or only a title change?")
    if "PARTNERSHIP_CHANGE" in types:
        out.append("Is the partnership a one-off announcement or the start of a platform pattern?")
    if not out and changes:
        out.append("Do later-window items form a pattern, or remain isolated events?")
    return [{"text": text, "kind": "AI-GENERATED STRATEGIC QUESTION"} for text in out]


def _timeline(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    dated = []
    for row in rows:
        stamp = _event_date(row) or _seen_date(row)
        if not stamp:
            continue
        sources = row.get("supporting_sources") or []
        source_name = (
            row.get("source_name")
            or (sources[0].get("publisher") if sources else "")
            or row.get("id")
            or ""
        )
        dated.append({
            "date": stamp.isoformat(),
            "title": _title(row),
            "kind": _kind(row),
            "source": source_name,
            "trust_state": _trust_state(row),
            "id": _row_id(row),
            "href": row.get("href") or row.get("url") or "",
            "coverage_artifact": bool(
                _seen_date(row)
                and _event_date(row)
                and _seen_date(row) != _event_date(row)
                and _seen_date(row) > _event_date(row)
            ),
        })
    dated.sort(key=lambda row: row["date"], reverse=True)
    return dated


def _temporal_differences(
    scope: Any,
    packet: Mapping[str, Any],
    before_rows: list[Mapping[str, Any]],
    now_rows: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    selected = tuple(getattr(scope, "company_ids", None) or (packet.get("scope") or {}).get("company_ids") or ())
    comparison = bool(getattr(scope, "comparison", False) or (packet.get("scope") or {}).get("comparison"))
    if not comparison and len(selected) < 2:
        return []
    companies = list(packet.get("companies") or [])
    if selected:
        companies = [row for row in companies if row.get("id") in set(selected)] or companies
    if len(companies) < 2:
        return []
    out = []
    for company in companies[:5]:
        cid = company.get("id")
        before = [row for row in before_rows if cid in _company_ids(row)]
        now = [row for row in now_rows if cid in _company_ids(row)]
        before_kinds = sorted({_kind(row) for row in before})
        now_kinds = sorted({_kind(row) for row in now})
        if not now and not before:
            continue
        ids = [_row_id(row) for row in [*now, *before] if _row_id(row)]
        if not ids:
            continue
        out.append({
            "text": (
                f"{company.get('name')}: later window shows {', '.join(now_kinds) or 'no dated moves'} "
                f"versus earlier window {', '.join(before_kinds) or 'no dated moves'}."
            ),
            "source_ids": ids[:8],
            "kind": "TEMPORAL DIFFERENCE",
        })
    return out


def _row_fits_scope(scope: Any, packet: Mapping[str, Any], row: Mapping[str, Any]) -> bool:
    from app.services.geography_hierarchy import geography_scope_match, record_geography_ids

    geos = tuple(getattr(scope, "geography_ids", None) or (packet.get("scope") or {}).get("geography_ids") or ())
    berry_id = getattr(scope, "berry_id", None) or (packet.get("scope") or {}).get("berry_id")
    if geos and not geography_scope_match(record_geography_ids(row), geos):
        return False
    if berry_id:
        berries = {str(value) for value in (row.get("berry_ids") or row.get("market_ids") or []) if value}
        if berries and berry_id not in berries:
            return False
    return True


def _is_weaker_market_article(row: Mapping[str, Any]) -> bool:
    return row.get("_origin") == "evidence" and _looks_like_market_text(row) and not row.get("latest_vs_previous")


def change_scenario_for(scope: Any, packet: Mapping[str, Any], *, today: date | None = None) -> dict[str, Any]:
    """Official read seam for Ask Berry OS and War Room. Creates no store and no UI."""
    model = build_change_scenario(scope, packet, today=today)
    return {
        "what_changed": model["changes"],
        "scenarios": [
            {
                "text": row["text"],
                "why_plausible": row["why_plausible"],
                "supporting_evidence": row.get("supporting_evidence") or ", ".join(row.get("source_ids") or []),
                "would_confirm": row["would_confirm"],
                "would_refute": row["would_refute"],
                "watch": row["watch"],
                "source_ids": row["source_ids"],
                "kind": row["kind"],
            }
            for row in model["scenarios"]
        ],
        "before_period": model["before_period"],
        "after_period": model["after_period"],
        "coverage_notes": model["coverage_notes"],
        "method_note": model["method_note"],
        "genetics_geography": model.get("genetics_geography"),
        "geographic_propagation": list((model.get("genetics_geography") or {}).get("propagation") or []),
        "genetics_footprints": list((model.get("genetics_geography") or {}).get("footprints") or []),
    }
