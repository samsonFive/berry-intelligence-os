"""Strategic Whitespace Radar — observed concentration vs coverage, not opportunity.

Derived read model over Competitive Moves, trusted Evidence, rights/IP,
and Market Reality. Creates no store and no activity/strength score.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Mapping
from urllib.parse import urlencode

from app.services.geography_hierarchy import resolve_geography_scope
from app.services.market_reality.research_desk import market_context_for_research_scope

STATE_ACTIVE = "ACTIVE / CONCENTRATED"
STATE_LOW_ACTIVITY = "LOW OBSERVED ACTIVITY"
STATE_LOW_COVERAGE = "LOW COVERAGE / UNKNOWN"

ACTIVITY_LANES: tuple[tuple[str, str, frozenset[str]], ...] = (
    ("genetics", "GENETICS / VARIETIES", frozenset({
        "GENETICS_LAUNCH", "VARIETY_LAUNCH", "GENETICS_INNOVATION",
        "VARIETY_COMMERCIALIZATION", "R&D / TECHNOLOGY",
    })),
    ("commercialization", "COMMERCIALIZATION", frozenset({
        "VARIETY_COMMERCIALIZATION",
    })),
    ("expansion", "PRODUCTION EXPANSION", frozenset({
        "EXPANSION", "PRODUCTION_EXPANSION", "SUPPLY / PRODUCTION_SHIFT",
    })),
    ("market_entry", "MARKET ENTRY", frozenset({"MARKET_ENTRY", "MARKET_ACCESS"})),
    ("partnership", "PARTNERSHIP / LICENSING", frozenset({
        "PARTNERSHIP", "LICENSING", "ACQUISITION / INVESTMENT",
    })),
    ("pbr", "PBR / RIGHTS", frozenset({"PBR / IP"})),
    ("patents", "PATENTS / IP", frozenset()),
    ("retail", "RETAIL / PROGRAM", frozenset({"RETAIL_PROGRAM"})),
    ("legal", "LEGAL / CONSTRAINT", frozenset({"LEGAL / COMPETITIVE_CONSTRAINT"})),
)

DEMO_COMPANIES = (
    "company-planasa",
    "company-fall-creek-farm-and-nursery",
    "company-hortifrut",
)
DEMO_GEOGRAPHIES = ("geography-peru", "geography-europe")

# Company×geography cells where public activity is obvious and Berry OS
# currently lacks the sources/moves to describe it. Never treat these as
# low observed activity.
MANUAL_COVERAGE_FAILURES: dict[tuple[str, str, str], str] = {
    ("company-planasa", "geography-peru", "berry-blueberry"): (
        "Manual challenge 2026-09-03: Planasa's Peru blueberry program is publicly obvious "
        "(Blue Manila campaign, commercial-manager appointment, nursery/variety support in Piura–Ica) "
        "and is missing from this packet. This cell is a coverage failure, not low activity."
    ),
    ("company-planasa", "geography-europe", "berry-blueberry"): (
        "Manual challenge 2026-09-03: Planasa's March 2026 Cartaya Meet & Greet presented its "
        "blueberry portfolio (Blue Madeira, Blue Maldiva, Blue Manila) to European buyers. "
        "That visible Europe genetics activity is not represented as a Competitive Move here."
    ),
}

FORBIDDEN_CLAIMS = (
    "whitespace = opportunity",
    "whitespace is opportunity",
    "low coverage is opportunity",
    "strength score",
)


def classify_cell(*, move_count: int, actor_count: int, coverage_adequate: bool) -> str:
    """Transparent three-state rule. Coverage is judged first."""
    if not coverage_adequate:
        return STATE_LOW_COVERAGE
    if move_count >= 2 or actor_count >= 2:
        return STATE_ACTIVE
    return STATE_LOW_ACTIVITY


def _ask_href(question: str) -> str:
    return "/research?" + urlencode({"q": question})


def _geo_scope_ids(geography_id: str, relationships: list[dict[str, Any]]) -> set[str]:
    return set(resolve_geography_scope(geography_id, relationships=relationships).all_ids)


def _move_in_geo(row: Mapping[str, Any], allowed: set[str]) -> bool:
    return bool(allowed.intersection(row.get("geography_ids") or []))


def _linked_ids(record: Mapping[str, Any]) -> set[str]:
    return set(record.get("entity_ids") or []) | set(record.get("geography_ids") or [])


def _evidence_in_scope(
    record: Mapping[str, Any],
    *,
    berry_id: str | None,
    allowed_geos: set[str],
) -> bool:
    if allowed_geos and not _linked_ids(record).intersection(allowed_geos):
        return False
    if berry_id and berry_id not in set(record.get("berry_ids") or record.get("market_ids") or []):
        return False
    return True


def _is_patent(record: Mapping[str, Any]) -> bool:
    intake = str(record.get("intake_type") or "")
    source_type = str(record.get("source_type") or "")
    return bool(record.get("patent_filing") or intake == "patent_filing" or source_type == "patent_record")


def _is_pbr(record: Mapping[str, Any]) -> bool:
    intake = str(record.get("intake_type") or "")
    source_type = str(record.get("source_type") or "")
    return bool(
        record.get("cpvo_filing")
        or intake in {"pvr_filing", "pvp_filing"}
        or source_type == "plant_breeders_rights_record"
    )


def _is_rights(record: Mapping[str, Any]) -> bool:
    return _is_patent(record) or _is_pbr(record)


def _unique(values: list[str]) -> list[str]:
    out: list[str] = []
    for value in values:
        if value and value not in out:
            out.append(value)
    return out


def _market_rows(repo: Any | None, berry_id: str | None, allowed_ids: set[str]) -> list[dict[str, Any]]:
    if repo is None:
        return []
    return market_context_for_research_scope(
        repo,
        SimpleNamespace(berry_id=berry_id, geography_ids=list(allowed_ids)),
        limit=6,
    )


def compose_whitespace_landscape(
    *,
    berry_id: str | None,
    company_ids: list[str],
    geography_ids: list[str],
    window_days: int,
    entities: Mapping[str, dict[str, Any]],
    relationships: list[dict[str, Any]],
    published_evidence: list[dict[str, Any]],
    moves: list[Mapping[str, Any]],
    market_repo: Any | None = None,
) -> dict[str, Any]:
    """Build the war-room model. Callers pass already-loaded stores."""
    selected = set(company_ids)
    companies = []
    for company_id in company_ids:
        entity = entities.get(company_id) or {}
        if entity.get("entity_type") != "company":
            continue
        companies.append({
            "id": company_id,
            "name": entity.get("name") or company_id,
            "href": f"/entities/company/{company_id}",
        })
    geos = []
    scopes: dict[str, set[str]] = {}
    for geography_id in geography_ids:
        entity = entities.get(geography_id) or {}
        if entity.get("entity_type") != "geography":
            continue
        scopes[geography_id] = _geo_scope_ids(geography_id, relationships)
        geos.append({
            "id": geography_id,
            "name": entity.get("name") or geography_id,
            "href": f"/geographies/{geography_id}",
        })

    berry_label = (entities.get(berry_id) or {}).get("name") if berry_id else None
    berry_label = berry_label or (berry_id or "berries").removeprefix("berry-").title()

    scoped_moves = [
        row for row in moves
        if not berry_id or berry_id in set(row.get("berry_ids") or [])
    ]

    geo_coverage: dict[str, dict[str, Any]] = {}
    for geo in geos:
        allowed = scopes[geo["id"]]
        geo_moves = [row for row in scoped_moves if _move_in_geo(row, allowed)]
        trusted = [
            row for row in published_evidence
            if _evidence_in_scope(row, berry_id=berry_id, allowed_geos=allowed)
        ]
        source_ids = {
            str(src.get("url") or src.get("publisher") or "")
            for row in geo_moves
            for src in (row.get("supporting_sources") or [])
            if src
        }
        market_cards = _market_rows(market_repo, berry_id, allowed)
        adequate = bool(trusted or len(source_ids) >= 2 or market_cards or len(geo_moves) >= 2)
        actors = _unique([
            str((entities.get(row.get("company_id")) or {}).get("name") or row.get("company_name") or row.get("company_id"))
            for row in geo_moves
            if row.get("company_id")
        ])
        geo_coverage[geo["id"]] = {
            "trusted_count": len(trusted),
            "source_count": len({item for item in source_ids if item}),
            "move_count": len(geo_moves),
            "market": market_cards[:4],
            "adequate": adequate,
            "observed_actors": actors[:8],
        }

    company_geo: list[dict[str, Any]] = []
    for company in companies:
        for geo in geos:
            allowed = scopes[geo["id"]]
            cell_moves = [
                row for row in scoped_moves
                if row.get("company_id") == company["id"] and _move_in_geo(row, allowed)
            ]
            cell_rights = [
                row for row in published_evidence
                if company["id"] in set(row.get("entity_ids") or [])
                and _is_rights(row)
                and _evidence_in_scope(row, berry_id=berry_id, allowed_geos=allowed)
            ]
            lanes = []
            for key, label, types in ACTIVITY_LANES:
                hits = [row for row in cell_moves if str(row.get("move_type") or "") in types]
                if key == "pbr":
                    hits = hits + [row for row in cell_rights if _is_pbr(row)]
                if key == "patents":
                    hits = [row for row in cell_rights if _is_patent(row)]
                if hits:
                    lanes.append({"key": key, "label": label, "count": len(hits)})
            activity_count = len(cell_moves) + len(cell_rights)
            state = classify_cell(
                move_count=activity_count,
                actor_count=1 if activity_count else 0,
                coverage_adequate=geo_coverage[geo["id"]]["adequate"],
            )
            failure = MANUAL_COVERAGE_FAILURES.get((company["id"], geo["id"], berry_id or ""))
            if failure:
                state = STATE_LOW_COVERAGE
            question = (
                f"Why does Berry OS show {state.casefold()} for {company['name']} "
                f"in {geo['name']} {berry_label}?"
            )
            company_geo.append({
                "company_id": company["id"],
                "company_name": company["name"],
                "geography_id": geo["id"],
                "geography_name": geo["name"],
                "state": state,
                "state_key": (
                    "active" if state == STATE_ACTIVE
                    else ("low-coverage" if state == STATE_LOW_COVERAGE else "low-activity")
                ),
                "move_count": len(cell_moves),
                "rights_count": len(cell_rights),
                "activity_count": activity_count,
                "lanes": lanes,
                "titles": [row.get("title") or row.get("what_happened") for row in cell_moves[:3]],
                "ask_href": _ask_href(question),
                "coverage_failure": failure,
            })

    geo_activity: list[dict[str, Any]] = []
    for geo in geos:
        allowed = scopes[geo["id"]]
        geo_rights = [
            row for row in published_evidence
            if _is_rights(row) and _evidence_in_scope(row, berry_id=berry_id, allowed_geos=allowed)
        ]
        for key, label, types in ACTIVITY_LANES:
            hits = [
                row for row in scoped_moves
                if _move_in_geo(row, allowed) and str(row.get("move_type") or "") in types
            ]
            extra = []
            if key == "pbr":
                extra = [row for row in geo_rights if _is_pbr(row)]
            if key == "patents":
                extra = [row for row in geo_rights if _is_patent(row)]
            actors = _unique([
                str(row.get("company_id"))
                for row in hits
                if row.get("company_id") and (entities.get(row.get("company_id")) or {}).get("entity_type") == "company"
            ] + [
                company_id
                for row in extra
                for company_id in row.get("entity_ids") or []
                if (entities.get(company_id) or {}).get("entity_type") == "company"
            ])
            actor_names = [
                (entities.get(cid) or {}).get("name") or cid for cid in actors
            ]
            state = classify_cell(
                move_count=len(hits) + len(extra),
                actor_count=len(actors),
                coverage_adequate=geo_coverage[geo["id"]]["adequate"],
            )
            question = (
                f"Where is {berry_label.casefold()} {label.casefold()} activity "
                f"concentrated around {geo['name']}?"
            )
            geo_activity.append({
                "geography_id": geo["id"],
                "geography_name": geo["name"],
                "lane_key": key,
                "lane_label": label,
                "state": state,
                "state_key": (
                    "active" if state == STATE_ACTIVE
                    else ("low-coverage" if state == STATE_LOW_COVERAGE else "low-activity")
                ),
                "move_count": len(hits) + len(extra),
                "actor_count": len(actors),
                "actor_names": actor_names,
                "ask_href": _ask_href(question),
            })

    footprints = []
    for company in companies:
        company_moves = [row for row in scoped_moves if row.get("company_id") == company["id"]]
        types = _unique([str(row.get("move_type") or "") for row in company_moves])
        varieties = _unique([
            name for row in company_moves for name in (row.get("variety_names") or [])
        ])
        geos_seen = _unique([
            label for row in company_moves for label in (row.get("geography_labels") or [])
        ])
        berries = _unique([
            label for row in company_moves for label in (row.get("berry_labels") or [])
        ])
        rights = [
            row for row in published_evidence
            if company["id"] in set(row.get("entity_ids") or []) and _is_rights(row)
        ]
        trusted = [
            row for row in published_evidence
            if company["id"] in set(row.get("entity_ids") or [])
            and (not berry_id or berry_id in set(row.get("berry_ids") or row.get("market_ids") or []))
        ]
        live_sources = {
            str(src.get("url") or src.get("publisher") or "")
            for row in company_moves
            for src in (row.get("supporting_sources") or [])
            if src
        }
        footprints.append({
            "id": company["id"],
            "name": company["name"],
            "href": company["href"],
            "observed_geographies": geos_seen[:6],
            "move_types": types,
            "berries": berries[:4] or ([berry_label] if berry_id else []),
            "varieties": varieties[:6],
            "rights_count": len(rights),
            "recent_move_count": len(company_moves),
            "trusted_count": len(trusted),
            "live_source_count": len({item for item in live_sources if item}),
        })

    overlap = []
    for geo in geos:
        cells = [cell for cell in company_geo if cell["geography_id"] == geo["id"] and cell["activity_count"]]
        if len(cells) >= 2:
            overlap.append({
                "geography_id": geo["id"],
                "geography_name": geo["name"],
                "companies": [cell["company_name"] for cell in cells],
                "text": (
                    f"Berry OS currently observes overlapping visible activity in {geo['name']} "
                    f"for {', '.join(cell['company_name'] for cell in cells)}."
                ),
            })

    concentration = [cell for cell in geo_activity if cell["state"] == STATE_ACTIVE]
    investigate = []
    for geo in geos:
        coverage = geo_coverage[geo["id"]]
        if coverage["adequate"] and coverage["move_count"] <= 1:
            investigate.append({
                "kind": "hypothesis",
                "text": (
                    f"Hypothesis — not a recommendation: {geo['name']} {berry_label} currently shows "
                    f"adequate source coverage ({coverage['trusted_count']} trusted records, "
                    f"{coverage['source_count']} live sources) and little observed competitor-move volume. "
                    "This is low observed activity, not a finding that the market is empty."
                ),
                "ask_href": _ask_href(
                    f"Where do we see relatively little observed competitive activity in {geo['name']} {berry_label}?"
                ),
            })
        if coverage["market"] and coverage["move_count"] < 2:
            investigate.append({
                "kind": "hypothesis",
                "text": (
                    f"Hypothesis — not a recommendation: Market Reality is moving in {geo['name']} {berry_label} "
                    "while observed competitor-move volume in this packet is limited. "
                    "Do not treat the market series as caused by, or allocated to, any company."
                ),
                "ask_href": _ask_href(
                    f"Where do we see market growth but relatively little observed competitive activity in {geo['name']} {berry_label}?"
                ),
            })
    coverage_gaps = [
        {
            "geography_id": geo["id"],
            "geography_name": geo["name"],
            "text": (
                f"{geo['name']} {berry_label} is LOW COVERAGE / UNKNOWN: Berry OS does not currently "
                "have enough trusted Evidence, live sources, or Market Reality series to describe "
                "competitor activity here. This is not whitespace and not opportunity."
            ),
            "ask_href": _ask_href(
                f"Which berry/geography combinations have weak coverage around {geo['name']} {berry_label}?"
            ),
        }
        for geo in geos
        if not geo_coverage[geo["id"]]["adequate"]
    ]
    for cell in company_geo:
        if cell.get("coverage_failure"):
            coverage_gaps.append({
                "geography_id": cell["geography_id"],
                "geography_name": cell["geography_name"],
                "text": cell["coverage_failure"],
                "ask_href": cell["ask_href"],
            })

    watch_next = []
    for company in companies:
        company_moves = [row for row in scoped_moves if row.get("company_id") == company["id"]]
        if not company_moves:
            continue
        lead = company_moves[0]
        scoped_place = next(
            (
                geo["name"]
                for geo in geos
                if any(
                    cell["company_id"] == company["id"]
                    and cell["geography_id"] == geo["id"]
                    and cell["activity_count"]
                    for cell in company_geo
                )
            ),
            None,
        )
        place = scoped_place or (list(lead.get("geography_labels") or []) or [None])[0]
        cultivar = (list(lead.get("variety_names") or []) or [None])[0]
        noun = str(lead.get("move_type") or "competitive move").replace("_", " ").casefold()
        parts = [f"Watch {company['name']}'s next {noun}"]
        if place:
            parts.append(f"in {place}")
        elif berry_label:
            parts.append(f"in {berry_label}")
        if cultivar:
            parts.append(f"around {cultivar}")
        watch_next.append(" ".join(parts) + ".")

    genetics_active = [
        cell for cell in geo_activity
        if cell["lane_key"] == "genetics" and cell["state"] == STATE_ACTIVE
    ]
    peru = next((geo for geo in geos if geo["id"] == "geography-peru"), None)
    peru_actors = []
    if peru:
        peru_actors = [
            cell["company_name"]
            for cell in company_geo
            if cell["geography_id"] == "geography-peru" and cell["activity_count"]
        ]
        extra = [
            name for name in geo_coverage.get("geography-peru", {}).get("observed_actors") or []
            if name not in peru_actors
        ]
        peru_actors = peru_actors + extra
    questions = [
        {
            "id": "genetics-concentration",
            "prompt": f"Where is {berry_label.casefold()} genetics activity concentrated?",
            "answer": (
                "; ".join(
                    f"{cell['geography_name']} — {cell['actor_count']} companies, "
                    f"{cell['move_count']} visible genetics/variety moves "
                    f"({', '.join(cell['actor_names']) or 'unnamed'})"
                    for cell in genetics_active
                )
                or "No geography in this scope currently meets ACTIVE / CONCENTRATED for genetics."
            ),
        },
        {
            "id": "peru-actors",
            "prompt": f"Which competitors are visibly active in Peru {berry_label.casefold()}?",
            "answer": (
                ", ".join(peru_actors)
                if peru_actors
                else (
                    "No selected or other observed competitor-move activity in Peru in this window."
                    if peru else "Peru is not in the current geography scope."
                )
            ),
        },
        {
            "id": "market-low-activity",
            "prompt": "Where do we see market movement but relatively little observed competitive activity?",
            "answer": (
                " ".join(item["text"] for item in investigate if "Market Reality" in item["text"])
                or "No geography in this scope currently pairs a Market Reality series with low move volume."
            ),
        },
        {
            "id": "weak-coverage",
            "prompt": "Which berry/geography combinations have weak coverage?",
            "answer": (
                " ".join(item["text"] for item in coverage_gaps)
                or f"Every selected geography currently has enough trusted Evidence, live sources, or Market Reality to describe {berry_label.casefold()} activity — that is not a completeness claim."
            ),
        },
        {
            "id": "overlap",
            "prompt": "Where are the selected competitors overlapping?",
            "answer": (
                " ".join(item["text"] for item in overlap)
                or "No selected-company overlap is currently visible in the chosen geographies."
            ),
        },
    ]

    brief_notes = [
        f"Strategic whitespace landscape for {berry_label}.",
        "Observed concentration, low observed activity, and low coverage are distinct.",
    ]
    if overlap:
        brief_notes.append("Overlap: " + "; ".join(row["text"] for row in overlap[:3]))
    if coverage_gaps:
        brief_notes.append("Coverage gaps: " + "; ".join(row["text"] for row in coverage_gaps[:2]))

    return {
        "berry_id": berry_id,
        "berry_label": berry_label,
        "window_days": window_days,
        "companies": companies,
        "geographies": geos,
        "lanes": [{"key": key, "label": label} for key, label, _types in ACTIVITY_LANES],
        "company_geo": company_geo,
        "company_geo_lookup": {
            f"{cell['company_id']}|{cell['geography_id']}": cell for cell in company_geo
        },
        "geo_activity": geo_activity,
        "geo_activity_lookup": {
            f"{cell['geography_id']}|{cell['lane_key']}": cell for cell in geo_activity
        },
        "geo_coverage": {
            geo["id"]: {
                **geo_coverage[geo["id"]],
                "name": geo["name"],
                "href": geo["href"],
            }
            for geo in geos
        },
        "footprints": footprints,
        "overlap": overlap,
        "questions": questions,
        "concentration": [
            {
                "text": (
                    f"{row['geography_name']}: {row['lane_label']} currently shows "
                    f"{row['actor_count']} companies and {row['move_count']} visible moves "
                    f"({', '.join(row['actor_names']) or 'unnamed'})."
                ),
                "ask_href": row["ask_href"],
            }
            for row in concentration[:8]
        ],
        "investigate": investigate[:6],
        "coverage_gaps": coverage_gaps,
        "watch_next": watch_next[:5],
        "brief_focus_notes": "\n".join(brief_notes),
        "states": [STATE_ACTIVE, STATE_LOW_ACTIVITY, STATE_LOW_COVERAGE],
        "method_note": (
            "Cells are categorical. ACTIVE / CONCENTRATED means two or more visible moves, "
            "rights filings, or actors in a geography that already has adequate coverage. "
            "LOW OBSERVED ACTIVITY means coverage is adequate and few moves are visible. "
            "LOW COVERAGE / UNKNOWN means Berry OS cannot say. "
            "None of these is opportunity, market share, or a competitive score."
        ),
        "selected_company_ids": list(selected),
    }


def default_demo_scope() -> dict[str, Any]:
    return {
        "berry_id": "berry-blueberry",
        "company_ids": list(DEMO_COMPANIES),
        "geography_ids": list(DEMO_GEOGRAPHIES),
        "window_days": 30,
    }


def parse_id_list(raw: str | None, fallback: tuple[str, ...] | list[str]) -> list[str]:
    values = [item.strip() for item in str(raw or "").split(",") if item.strip()]
    return values or list(fallback)
