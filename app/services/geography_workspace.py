"""Geography / Market Intelligence V1 -- the Geography analogue of
Company/Variety Intelligence: "what do we currently know about this
market/geography," never a claim about total real-world market activity.
Presentation only, derived from existing trusted objects; reuses the same
role/rights/observation helpers Company Compare and Company Portfolio
already proved (variety_workspace._is_rights_record/_is_observation/
_rights_kind/_party, company_workspace._humanize_source_type,
berries.geography.geography_region) rather than re-deriving any of that
logic or inventing a competing Market schema."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.services.berries.geography import geography_region
from app.services.chronology import meaningful_date_text
from app.services.company_workspace import _humanize_source_type
from app.services.variety_workspace import (
    _is_observation,
    _is_rights_record,
    _party,
    _rights_kind,
)

GEOGRAPHY_RECENT_MOVES_LIMIT = 10
GEOGRAPHY_ACTOR_LIMIT = 12
GEOGRAPHY_VARIETY_LIMIT = 12
COVERAGE_CAVEAT = "Captured intelligence coverage is not a measure of total market activity."


def _geography_linked_evidence(
    geography_id: str, published_evidence: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """A geography can be linked to evidence two ways, same dual-check as
    berries.geography.evidence_regions(): the dedicated geography_ids array,
    or as a plain entity_ids member."""
    return [
        r
        for r in published_evidence
        if geography_id in (r.get("geography_ids") or []) or geography_id in (r.get("entity_ids") or [])
    ]


def _evidence_by_geography(published_evidence: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """One-pass index: geography_ids + entity_ids → evidence rows."""
    index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in published_evidence:
        seen: set[str] = set()
        for field_name in ("geography_ids", "entity_ids"):
            for geo_id in record.get(field_name) or []:
                text = str(geo_id or "")
                if not text or text in seen:
                    continue
                seen.add(text)
                index[text].append(record)
    return index


def _evidence_reason(record: dict[str, Any]) -> str:
    """Why a Variety or Company appears in this Geography's captured
    intelligence -- honest, source-grounded, never inferring commercial
    presence from a bare mention."""
    if _is_rights_record(record):
        return "Rights / IP"
    if _is_observation(record):
        return "Commercial observation"
    return _humanize_source_type(str(record.get("source_type") or ""))


def geography_index(
    *,
    entities: dict[str, dict[str, Any]],
    published_evidence: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
    signals: list[dict[str, Any]],
    berry_labels: dict[str, str],
) -> list[dict[str, Any]]:
    """Browse/search surface for every Geography entity -- captured
    intelligence counts only, sorted alphabetically (not by "importance",
    which would imply a ranking that does not exist)."""
    evidence_index = _evidence_by_geography(published_evidence)
    signals_by_entity: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for signal in signals:
        for entity_id in signal.get("entity_ids") or []:
            signals_by_entity[str(entity_id)].append(signal)
    operates_in_by_geo: dict[str, set[str]] = defaultdict(set)
    for rel in relationships:
        if rel.get("predicate") == "operates_in" and rel.get("object_id"):
            operates_in_by_geo[str(rel["object_id"])].add(str(rel.get("subject_id") or ""))

    rows: list[dict[str, Any]] = []
    for geo in entities.values():
        if geo.get("entity_type") != "geography":
            continue
        gid = geo["id"]
        linked = evidence_index.get(gid, [])
        company_ids = set(operates_in_by_geo.get(gid, ()))
        variety_ids: set[str] = set()
        for record in linked:
            for eid in record.get("entity_ids") or []:
                other = entities.get(eid)
                if not other:
                    continue
                if other.get("entity_type") == "company":
                    company_ids.add(eid)
                elif other.get("entity_type") == "variety":
                    variety_ids.add(eid)
        geo_signals = signals_by_entity.get(gid, [])
        berry_ids = [str(b) for b in (geo.get("berry_ids") or []) if b]
        dates = [meaningful_date_text(r) for r in linked]
        dates = [d for d in dates if d]
        rows.append(
            {
                "id": gid,
                "name": geo.get("name") or gid,
                "href": f"/geographies/{gid}",
                "type": "Country" if (geo.get("attributes") or {}).get("iso_3166_1_alpha_2") else "Region / other",
                "region": geography_region(geo) or "",
                "berry_ids": berry_ids,
                "berries": [berry_labels.get(b, b) for b in berry_ids],
                "company_count": len(company_ids),
                "variety_count": len(variety_ids),
                "evidence_count": len(linked),
                "signal_count": len(geo_signals),
                "latest_activity": max(dates) if dates else "",
            }
        )
    rows.sort(key=lambda r: r["name"])
    return rows


def geography_detail(
    geography_id: str,
    *,
    entities: dict[str, dict[str, Any]],
    relationships: list[dict[str, Any]],
    published_evidence: list[dict[str, Any]],
    signals: list[dict[str, Any]],
    assessments: list[dict[str, Any]],
    berry_labels: dict[str, str],
    strategic_questions: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Geography Intelligence V1's detail view -- what does our captured
    intelligence show about this place. Returns None for an unknown or
    non-geography id (the route turns that into a 404).

    `strategic_questions` is optional (Strategic Question + Decision
    Workspace V1) -- when supplied, surfaces which Strategic Questions this
    Geography's own linked Evidence/Signals/Assessments actually bear on,
    reusing the real strategic_question_ids field already authored on
    those records rather than a new linkage mechanism."""
    geo = entities.get(geography_id)
    if not geo or geo.get("entity_type") != "geography":
        return None

    linked = _geography_linked_evidence(geography_id, published_evidence)

    company_ids_via_relationship = {
        r["subject_id"]
        for r in relationships
        if r.get("predicate") == "operates_in" and r.get("object_id") == geography_id
    }
    company_ids = set(company_ids_via_relationship)
    variety_ids: set[str] = set()
    for record in linked:
        for eid in record.get("entity_ids") or []:
            other = entities.get(eid)
            if not other:
                continue
            if other.get("entity_type") == "company":
                company_ids.add(eid)
            elif other.get("entity_type") == "variety":
                variety_ids.add(eid)

    actor_rows: list[dict[str, Any]] = []
    for cid in company_ids:
        company = entities.get(cid)
        if not company:
            continue
        company_linked = [r for r in linked if cid in (r.get("entity_ids") or [])]
        berry_ids = [str(b) for b in (company.get("berry_ids") or []) if b]
        actor_rows.append(
            {
                "id": cid,
                "name": company.get("name") or cid,
                "href": f"/entities/company/{cid}",
                "portfolio_href": f"/entities/company/{cid}/portfolio",
                "berries": [berry_labels.get(b, b) for b in berry_ids],
                "evidence_count": len(company_linked),
                "has_operates_in_relationship": cid in company_ids_via_relationship,
            }
        )
    actor_rows.sort(key=lambda r: (-r["evidence_count"], r["name"]))
    actor_overflow = max(0, len(actor_rows) - GEOGRAPHY_ACTOR_LIMIT)
    actor_rows = actor_rows[:GEOGRAPHY_ACTOR_LIMIT]

    variety_rows: list[dict[str, Any]] = []
    for vid in variety_ids:
        variety = entities.get(vid)
        if not variety:
            continue
        variety_linked = [r for r in linked if vid in (r.get("entity_ids") or [])]
        reasons = sorted({_evidence_reason(r) for r in variety_linked})
        berry_ids = [str(b) for b in (variety.get("berry_ids") or []) if b]
        variety_rows.append(
            {
                "id": vid,
                "name": variety.get("name") or vid,
                "href": f"/entities/variety/{vid}",
                "berries": [berry_labels.get(b, b) for b in berry_ids],
                "why_shown": ", ".join(reasons) if reasons else "Named in captured intelligence",
                "evidence_count": len(variety_linked),
            }
        )
    variety_rows.sort(key=lambda r: (-r["evidence_count"], r["name"]))
    variety_overflow = max(0, len(variety_rows) - GEOGRAPHY_VARIETY_LIMIT)
    variety_rows = variety_rows[:GEOGRAPHY_VARIETY_LIMIT]

    rights_records = [
        {
            "id": r["id"],
            "title": r.get("title"),
            "kind": _rights_kind(r),
            "published_date": r.get("published_date"),
            "href": f"/evidence/{r['id']}",
        }
        for r in linked
        if _is_rights_record(r) and r.get("id")
    ]
    rights_records.sort(key=lambda r: str(r.get("published_date") or ""), reverse=True)

    commercial_records = [
        {
            "id": r["id"],
            "title": r.get("title"),
            "observed_at": (r.get("commercial_observation") or {}).get("observed_at") or r.get("published_date"),
            "retailer": _party(entities.get((r.get("commercial_observation") or {}).get("retailer_entity_id"))),
            "href": f"/evidence/{r['id']}",
        }
        for r in linked
        if _is_observation(r) and r.get("id")
    ]
    commercial_records.sort(key=lambda r: str(r.get("observed_at") or ""), reverse=True)

    recent_sorted = sorted(
        linked,
        key=lambda r: str(r.get("published_date") or r.get("captured_date") or ""),
        reverse=True,
    )
    recent_moves = [
        {
            "id": r["id"],
            "title": r.get("title"),
            "date": r.get("published_date") or r.get("captured_date"),
            "kind": _evidence_reason(r),
            "href": f"/evidence/{r['id']}",
        }
        for r in recent_sorted
        if r.get("id") and (r.get("published_date") or r.get("captured_date"))
    ][:GEOGRAPHY_RECENT_MOVES_LIMIT]

    geo_signals = [s for s in signals if geography_id in (s.get("entity_ids") or [])]
    geo_assessments = [a for a in assessments if geography_id in (a.get("entity_ids") or [])]

    linked_strategic_question_ids: set[str] = set()
    for record in linked + geo_signals + geo_assessments:
        linked_strategic_question_ids.update(record.get("strategic_question_ids") or [])
    linked_strategic_questions = [
        {"id": sq["id"], "title": sq.get("title") or sq["id"], "href": f"/strategic-questions/{sq['id']}"}
        for sq in (strategic_questions or [])
        if sq.get("id") in linked_strategic_question_ids
    ]

    source_type_counts: dict[str, int] = {}
    source_names: set[str] = set()
    for record in linked:
        label = _humanize_source_type(str(record.get("source_type") or ""))
        source_type_counts[label] = source_type_counts.get(label, 0) + 1
        if record.get("source_name"):
            source_names.add(str(record["source_name"]))

    dates = [str(r.get("published_date") or r.get("captured_date") or "") for r in linked]
    dates = [d for d in dates if d]

    coverage = {
        "evidence_count": len(linked),
        "company_count": len(company_ids),
        "variety_count": len(variety_ids),
        "source_count": len(source_names),
        "signal_count": len(geo_signals),
        "assessment_count": len(geo_assessments),
        "latest_date": max(dates) if dates else "",
    }

    region_label = geography_region(geo) or ""
    region_entity = next(
        (
            other
            for other in entities.values()
            if other.get("entity_type") == "geography"
            and other.get("id") != geography_id
            and (other.get("name") or "").strip().casefold() == region_label.strip().casefold()
        ),
        None,
    )

    berry_ids = [str(b) for b in (geo.get("berry_ids") or []) if b]

    return {
        "id": geography_id,
        "name": geo.get("name") or geography_id,
        "href": f"/geographies/{geography_id}",
        "type": "Country" if (geo.get("attributes") or {}).get("iso_3166_1_alpha_2") else "Region / other",
        "description": geo.get("description") or "",
        "region_label": region_label,
        "region_href": f"/geographies/{region_entity['id']}" if region_entity else "",
        "region_name": region_entity.get("name") if region_entity else "",
        "berry_ids": berry_ids,
        "berries": [berry_labels.get(b, b) for b in berry_ids],
        "actors": actor_rows,
        "actor_overflow": actor_overflow,
        "varieties": variety_rows,
        "variety_overflow": variety_overflow,
        "rights_records": rights_records,
        "commercial_records": commercial_records,
        "recent_moves": recent_moves,
        "signals": [
            {"id": s.get("id"), "title": s.get("title"), "status": s.get("status"), "href": f"/signals/{s['id']}"}
            for s in geo_signals
        ],
        "assessments": [
            {
                "id": a.get("id"),
                "title": a.get("title"),
                "confidence": a.get("confidence"),
                "ai_proposed": bool(a.get("ai_proposed")),
                "href": f"/assessments/{a['id']}",
            }
            for a in geo_assessments
        ],
        "source_type_counts": sorted(source_type_counts.items(), key=lambda kv: -kv[1]),
        "coverage": coverage,
        "coverage_caveat": COVERAGE_CAVEAT,
        "linked_strategic_questions": linked_strategic_questions,
    }
