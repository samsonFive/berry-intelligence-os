"""Grounded strategy comparison over an Ask Berry OS ResearchPacket.

This is a presentation/read model, not an intelligence store or a competitive
score.  It consumes already-resolved Company cards plus packet/live rows and
emits only dimensions that contain real data.  Every generated difference or
monitoring priority carries source IDs from the packet.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from app.services.research_desk import ResearchScope

# Radar event types plus official Competitive Move Detector types.
MOVE_TYPES = {
    "LEADERSHIP",
    "PARTNERSHIP",
    "LICENSING",
    "VARIETY_LAUNCH",
    "GENETICS_INNOVATION",
    "PRODUCTION_EXPANSION",
    "MARKET_ACCESS",
    "RETAIL_PROGRAM",
    "EXPANSION",
    "MARKET_ENTRY",
    "GENETICS_LAUNCH",
    "VARIETY_COMMERCIALIZATION",
    "ACQUISITION / INVESTMENT",
    "R&D / TECHNOLOGY",
    "PBR / IP",
    "SUPPLY / PRODUCTION_SHIFT",
    "LEGAL / COMPETITIVE_CONSTRAINT",
}

EXPANSION_TYPES = {
    "EXPANSION",
    "PRODUCTION_EXPANSION",
    "MARKET_ENTRY",
    "MARKET_ACCESS",
    "SUPPLY / PRODUCTION_SHIFT",
}
GENETICS_TYPES = {
    "GENETICS_LAUNCH",
    "VARIETY_LAUNCH",
    "GENETICS_INNOVATION",
    "VARIETY_COMMERCIALIZATION",
    "R&D / TECHNOLOGY",
}
COMMERCIAL_TYPES = {
    "VARIETY_COMMERCIALIZATION",
    "LICENSING",
    "PARTNERSHIP",
    "RETAIL_PROGRAM",
    "ACQUISITION / INVESTMENT",
}

MOVE_WATCH_NOUN = {
    "EXPANSION": "production expansion",
    "PRODUCTION_EXPANSION": "production expansion",
    "SUPPLY / PRODUCTION_SHIFT": "production / supply shift",
    "MARKET_ENTRY": "market entry",
    "MARKET_ACCESS": "market-access move",
    "GENETICS_LAUNCH": "genetics launch",
    "VARIETY_LAUNCH": "variety launch",
    "GENETICS_INNOVATION": "genetics platform move",
    "VARIETY_COMMERCIALIZATION": "commercialization move",
    "LICENSING": "licensing relationship",
    "PARTNERSHIP": "partnership",
    "ACQUISITION / INVESTMENT": "acquisition / investment",
    "LEADERSHIP": "leadership appointment",
    "PBR / IP": "IP / PBR event",
    "PATENT": "IP / PBR event",
    "R&D / TECHNOLOGY": "R&D move",
    "RETAIL_PROGRAM": "retail program",
    "LEGAL / COMPETITIVE_CONSTRAINT": "legal / competitive constraint",
}


def _unique_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for raw in rows:
        row = dict(raw)
        identity = str(row.get("id") or row.get("url") or row.get("title") or "")
        if not identity or identity in seen:
            continue
        seen.add(identity)
        out.append(row)
    return out


def _company_ids_on(row: Mapping[str, Any]) -> set[str]:
    ids = set(str(value) for value in (row.get("company_ids") or row.get("entity_ids") or []) if value)
    if row.get("company_id"):
        ids.add(str(row["company_id"]))
    return ids


def _for_company(rows: Iterable[Mapping[str, Any]], company_id: str) -> list[dict[str, Any]]:
    return _unique_rows(row for row in rows if company_id in _company_ids_on(row))


def _source_ids(rows: Iterable[Mapping[str, Any]], known_ids: set[str]) -> list[str]:
    out: list[str] = []
    for row in rows:
        candidate_ids = [row.get("id"), *(row.get("source_ids") or []), *(row.get("evidence_ids") or [])]
        for value in candidate_ids:
            source_id = str(value or "")
            if source_id in known_ids and source_id not in out:
                out.append(source_id)
    return out


def _item(row: Mapping[str, Any], *, fallback_kind: str = "STRUCTURED") -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "title": row.get("title") or row.get("name") or row.get("statement") or row.get("id"),
        "href": row.get("href") or row.get("url") or "",
        "kind": row.get("move_type") or row.get("event_type") or row.get("structured_kind") or row.get("trust_class") or fallback_kind,
        "date": row.get("date") or row.get("published_date") or row.get("latest_update") or "",
    }


def _place_clause(geography_label: str, berry_label: str) -> str:
    if geography_label and berry_label:
        return f" in {geography_label} {berry_label}"
    if geography_label:
        return f" in {geography_label}"
    if berry_label:
        return f" in {berry_label}"
    return ""


def _count_difference(
    company_rows: list[dict[str, Any]],
    *,
    count_key: str,
    rows_key: str,
    description: str,
    known_ids: set[str],
    place: str = "",
) -> dict[str, Any] | None:
    values = [(row, int(row.get(count_key) or 0)) for row in company_rows]
    if not values:
        return None
    highest = max(value for _row, value in values)
    lowest = min(value for _row, value in values)
    leaders = [row for row, value in values if value == highest]
    if highest <= 0 or highest == lowest or len(leaders) != 1:
        return None
    leader = leaders[0]
    ids = _source_ids(leader.get(rows_key) or [], known_ids)
    if not ids:
        return None
    return {
        "text": (
            f"Berry OS currently observes more recent visible {description} for {leader['name']}"
            f"{place} ({highest}) than for at least one compared company ({lowest}). "
            "This describes captured coverage, not underlying company performance."
        ),
        "source_ids": ids[:6],
        "kind": "VISIBLE EVIDENCE DIFFERENCE",
    }


def _lead_title(rows: Iterable[Mapping[str, Any]]) -> str:
    for row in rows:
        title = row.get("title") or row.get("theme") or row.get("label") or row.get("name") or row.get("what_happened")
        if title:
            return str(title)
    return ""


def _lane(rows: list[Mapping[str, Any]], label: str) -> dict[str, Any] | None:
    if not rows:
        return None
    return {"count": len(rows), "lead": _lead_title(rows), "label": label}


def _is_pbr(row: Mapping[str, Any]) -> bool:
    kind = str(row.get("structured_kind") or row.get("move_type") or row.get("event_type") or "")
    return kind in {"PBR / PVP", "PBR / IP"} or "pbr" in kind.casefold() or "pvp" in kind.casefold()


def _is_patent(row: Mapping[str, Any]) -> bool:
    kind = str(row.get("structured_kind") or row.get("move_type") or row.get("event_type") or "")
    return kind == "PATENT" or "patent" in kind.casefold()


def _watch_text(company: Mapping[str, Any], geography_label: str, berry_label: str) -> str | None:
    patterns = list(company.get("patterns") or [])
    candidates = list(company.get("moves") or []) or list(company.get("current") or [])
    if not candidates and not patterns:
        return None
    lead = candidates[0] if candidates else patterns[0]
    event = str(lead.get("move_type") or lead.get("event_type") or "")
    noun = MOVE_WATCH_NOUN.get(event, event.replace("_", " ").casefold() or "competitive move")
    if patterns:
        theme = str(patterns[0].get("theme") or "").replace("_", " ").casefold()
        if theme:
            noun = f"{theme} pattern"
    geos = list(lead.get("geography_labels") or [])
    place = geography_label or (geos[0] if geos else "")
    varieties = [str(name) for name in (lead.get("variety_names") or []) if name]
    cultivar = varieties[0] if varieties else ""
    partners = []
    for row in company.get("partnerships") or []:
        other = row.get("object_name") if str(row.get("subject_id")) == company["id"] else row.get("subject_name")
        if other and other != company["name"]:
            partners.append(str(other))
    parts = [f"Watch {company['name']}'s next {noun}"]
    if place:
        parts.append(f"in {place}")
    elif berry_label:
        parts.append(f"in {berry_label}")
    if cultivar:
        parts.append(f"around {cultivar}")
    elif partners:
        parts.append(f"with {partners[0]}")
    return " ".join(parts) + "; the packet contains a visible sourced move in that lane."


def build_research_decision_support(
    scope: ResearchScope,
    *,
    packet: Mapping[str, Any],
    company_compare: Mapping[str, Any] | None,
    live: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Build a comparison/deep-dive model with no inferred winner."""
    cards = list((company_compare or {}).get("companies") or [])
    if not cards:
        return None
    live = live or {}
    known_ids = set((packet.get("source_index") or {}).keys()) | {
        str(row.get("id")) for row in live.get("items") or [] if row.get("id")
    }
    developments = _unique_rows([
        *(packet.get("competitive_moves") or []),
        *(packet.get("radar_developments") or []),
        *(live.get("items") or []),
    ])
    market_rows = list(packet.get("market_context") or [])
    relationships = list(packet.get("relationships") or [])
    evidence = list(packet.get("evidence") or [])
    rights = list(packet.get("rights_ip") or [])
    signals = list(packet.get("signals") or [])
    patterns = list(packet.get("move_patterns") or [])

    companies: list[dict[str, Any]] = []
    for card in cards:
        company_id = str(card.get("id") or "")
        current = _for_company(developments, company_id)
        moves = [
            row for row in current
            if str(row.get("move_type") or row.get("event_type") or "") in MOVE_TYPES
            or row.get("layer") == "COMPETITIVE MOVE"
        ]
        trusted = _for_company(evidence, company_id)
        company_rights = _for_company(rights, company_id)
        rights_by_id = {str(row.get("id")): dict(row) for row in company_rights if row.get("id")}
        for row in card.get("rights_published") or []:
            if row.get("id"):
                rights_by_id.setdefault(str(row["id"]), dict(row))
        company_rights = list(rights_by_id.values())
        company_relationships = [
            dict(row) for row in relationships
            if company_id in {str(row.get("subject_id") or ""), str(row.get("object_id") or "")}
        ]
        partnerships = [
            row for row in company_relationships
            if str(row.get("predicate") or "") in {"partners_with", "licenses", "licensed_by", "markets", "owns"}
        ]
        company_signals = _for_company(signals, company_id)
        varieties = _unique_rows(
            party
            for parties in (card.get("roles") or {}).values()
            for party in parties
        )
        if scope.berry_id:
            varieties = [
                row for row in varieties
                if not row.get("berry_ids") or scope.berry_id in set(row.get("berry_ids") or [])
            ]
        company_patterns = [row for row in patterns if str(row.get("company_id") or "") == company_id]
        expansion = [
            row for row in moves
            if str(row.get("move_type") or row.get("event_type") or "") in EXPANSION_TYPES
        ]
        genetics_moves = [
            row for row in moves
            if str(row.get("move_type") or row.get("event_type") or "") in GENETICS_TYPES
        ]
        commercial_moves = [
            row for row in moves
            if str(row.get("move_type") or row.get("event_type") or "") in COMMERCIAL_TYPES
        ]
        pbr = [row for row in company_rights if _is_pbr(row)]
        patents = [row for row in company_rights if _is_patent(row)]
        current_source_count = sum(max(1, int(row.get("source_count") or 1)) for row in current)
        coverage_source_ids = _source_ids([*trusted, *current, *company_rights, *partnerships], known_ids)
        move_kinds = []
        for row in moves:
            kind = str(row.get("move_type") or row.get("event_type") or "")
            if kind and kind not in move_kinds:
                move_kinds.append(kind)
        companies.append({
            "id": company_id,
            "name": card.get("name") or company_id,
            "href": card.get("href") or f"/entities/company/{company_id}",
            "current": current,
            "moves": moves,
            "expansion": expansion,
            "pbr": pbr,
            "patents": patents,
            "trusted": trusted,
            "rights": company_rights,
            "relationships": company_relationships,
            "partnerships": partnerships,
            "signals": company_signals,
            "varieties": varieties,
            "geographies": list(card.get("geographies") or []),
            "patterns": company_patterns,
            "genetics_moves": genetics_moves,
            "commercial_moves": commercial_moves,
            "move_kinds": move_kinds,
            "current_source_count": current_source_count,
            "trusted_source_count": len(trusted),
            "observed_move_count": len(moves),
            "coverage_source_ids": coverage_source_ids,
            "profile": card,
        })

    dimension_specs = (
        ("current", "Current developments", "current", "Current sourced developments"),
        ("moves", "Current moves", "moves", "Visible moves"),
        ("expansion", "Expansion", "expansion", "Expansion / footprint moves"),
        ("patterns", "Repeated move patterns", "patterns", "Repeated move patterns"),
        ("geographies", "Geographic activity", "geographies", "Captured geographies"),
        ("varieties", "Genetics / varieties", "varieties", "Linked varieties"),
        ("partnerships", "Licensing / partnerships", "partnerships", "Captured relationships"),
        ("pbr", "PBR / rights", "pbr", "Captured PBR / PVP records"),
        ("patents", "Patents / IP", "patents", "Captured patent records"),
        ("trusted", "Trusted evidence", "trusted", "Scoped trusted records"),
        ("signals", "Weak signals", "signals", "Linked signals"),
    )
    dimensions: list[dict[str, Any]] = []
    for key, label, rows_key, summary_label in dimension_specs:
        cells = []
        for company in companies:
            rows = company[rows_key]
            cells.append({
                "company_id": company["id"],
                "count": len(rows),
                "summary": f"{len(rows)} {summary_label.casefold()}",
                "items": [
                    (
                        {"id": row.get("id"), "title": row.get("theme") or row.get("label") or row.get("why"), "href": "", "kind": "REPEATED MOVE PATTERN", "date": row.get("latest_update") or ""}
                        if rows_key == "patterns"
                        else _item(row)
                    )
                    for row in rows[:5]
                ],
            })
        if any(cell["count"] for cell in cells):
            dimensions.append({"key": key, "label": label, "cells": cells})

    geo_names = [str(row.get("name")) for row in packet.get("geographies") or [] if row.get("name")]
    geography_label = "Europe" if "Europe" in geo_names else (geo_names[0] if geo_names else "")
    berry_label = str(scope.berry_id or "").removeprefix("berry-").title()
    place = _place_clause(geography_label, berry_label)
    key_differences = [
        row for row in (
            _count_difference(companies, count_key="current_source_count", rows_key="current", description="current-source coverage", known_ids=known_ids, place=place),
            _count_difference(companies, count_key="trusted_source_count", rows_key="trusted", description="trusted scoped Evidence", known_ids=known_ids, place=place),
        ) if row
    ]
    rights_difference = _count_difference(
        [{**row, "rights_count": len(row["rights"])} for row in companies],
        count_key="rights_count", rows_key="rights", description="rights/IP records", known_ids=known_ids, place=place,
    )
    if rights_difference:
        key_differences.append(rights_difference)
    move_difference = _count_difference(
        [{**row, "moves_count": len(row["moves"])} for row in companies],
        count_key="moves_count", rows_key="moves", description="recent competitive moves", known_ids=known_ids, place=place,
    )
    if move_difference:
        key_differences.append(move_difference)
    genetics_difference = _count_difference(
        [{**row, "genetics_count": len(row["genetics_moves"]) + len(row["varieties"])} for row in companies],
        count_key="genetics_count", rows_key="varieties", description="genetics/commercialization activity", known_ids=known_ids, place=place,
    )
    if genetics_difference:
        key_differences.append(genetics_difference)

    current_counts = {row["name"]: row["current_source_count"] for row in companies}
    trusted_counts = {row["name"]: row["trusted_source_count"] for row in companies}
    observed_activity = {row["name"]: row["observed_move_count"] for row in companies}
    coverage_depth = {row["name"]: row["trusted_source_count"] for row in companies}
    coverage_difference = {
        "current_counts": current_counts,
        "trusted_counts": trusted_counts,
        "observed_activity": observed_activity,
        "coverage_depth": coverage_depth,
        "different": len(set(current_counts.values())) > 1 or len(set(trusted_counts.values())) > 1 or len(set(observed_activity.values())) > 1,
        "note": (
            "Observed activity and coverage depth are different things. Higher visible coverage can reflect "
            "collection and publisher attention; it must not be interpreted automatically as higher competitive activity."
        ),
        "observed_note": "Observed activity counts visible competitive moves attributed to the company in this packet.",
        "coverage_note": "Coverage depth counts trusted scoped Evidence. More sources is not more activity.",
    }

    interpretation: list[dict[str, Any]] = []
    for row in key_differences[:3]:
        interpretation.append({
            "text": row["text"].split(" This describes", 1)[0] + " This may justify closer monitoring, not a winner conclusion.",
            "source_ids": row["source_ids"],
            "kind": "POSSIBLE IMPLICATION — NOT YET REVIEWED",
        })
    if market_rows:
        market_ids = _source_ids(market_rows, known_ids)
        if market_ids:
            interpretation.append({
                "text": "The scoped market movement may affect the competitive setting shared by these companies; it does not allocate market share or performance to any company.",
                "source_ids": market_ids[:4],
                "kind": "POSSIBLE IMPLICATION — NOT YET REVIEWED",
            })

    watch_next: list[dict[str, Any]] = []
    watch_berry = berry_label or "berries"
    for company in companies:
        candidates = company["moves"] or company["current"]
        ids = _source_ids(candidates[:1], known_ids)
        text = _watch_text(company, geography_label, watch_berry)
        if not candidates or not ids or not text:
            continue
        watch_next.append({
            "text": text,
            "source_ids": ids,
            "company_id": company["id"],
        })
    if market_rows:
        ids = _source_ids(market_rows[:2], known_ids)
        if ids:
            watch_next.append({
                "text": (
                    f"Track the next production, shipment, or price release for {watch_berry}"
                    f"{' in ' + geography_label if geography_label else ''}; "
                    "compare the direction with the current structured series before attributing impact to a company."
                ),
                "source_ids": ids,
                "company_id": "",
            })

    selected_source_ids: list[str] = []
    for row in [*key_differences, *watch_next]:
        for source_id in row.get("source_ids") or []:
            if source_id not in selected_source_ids:
                selected_source_ids.append(source_id)
    if not selected_source_ids:
        for company in companies:
            for source_id in company["coverage_source_ids"]:
                if source_id not in selected_source_ids:
                    selected_source_ids.append(source_id)

    positioning: list[dict[str, Any]] = []
    for company in companies:
        lanes = {
            "visible_current_moves": _lane(company["moves"] or company["current"], "Visible current moves"),
            "primary_geographies": _lane(company["geographies"], "Primary geographies"),
            "genetics_activity": _lane(company["genetics_moves"] or company["varieties"], "Genetics activity"),
            "commercialization_activity": _lane(company["commercial_moves"] or company["partnerships"], "Commercialization activity"),
            "ip_rights_activity": _lane(company["rights"], "IP / rights activity"),
            "emerging_issues": _lane(company["signals"], "Emerging issues"),
        }
        snapshot = {
            "id": company["id"],
            "name": company["name"],
            "href": company["href"],
            "move_kinds": company["move_kinds"],
            "observed_move_count": company["observed_move_count"],
            "coverage_depth": company["trusted_source_count"],
        }
        snapshot.update({key: value for key, value in lanes.items() if value})
        positioning.append(snapshot)

    return {
        "mode": "comparison" if len(companies) >= 2 else "company_deep_dive",
        "companies": companies,
        "positioning": positioning,
        "dimensions": dimensions,
        "key_differences": key_differences,
        "coverage_difference": coverage_difference,
        "interpretation": interpretation,
        "watch_next": watch_next[:5],
        "market_context": market_rows,
        "selected_source_ids": selected_source_ids[:12],
        "brief_key_differences": [row["text"] for row in key_differences[:5]],
        "brief_watch_next": [row["text"] for row in watch_next[:5]],
        "executive_takeaway": (
            key_differences[0]["text"] if key_differences
            else "The packet supports a structured comparison, but not a source-grounded claim that one company is ahead."
        ),
    }
