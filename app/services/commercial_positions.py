"""Commercial Positions V2: tagged published Evidence, not Position objects.

Items enter because Evidence.priority.commercial_position.level != none.
Grouping by company is a view. It does not create a Position schema or a
competitive score. Facts, Signals, and Assessments stay labeled as themselves.
Trade and commercial observations stay context, not conclusions.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any
from urllib.parse import quote_plus

from app.services.analyst_queue import present_queue_item
from app.services.testing_workspace import ENTITY_HREF

STATIC_SIGNAL_SKIP = {
    "proposed",
    "deferred",
    "dismissed",
    "disputed",
}
PUBLIC_ASSESSMENT = {"active"}
PUBLIC_FACT = {"active", "disputed", "superseded"}


def _entity_chip(entity_id: str, entities: dict[str, dict[str, Any]]) -> dict[str, str] | None:
    entity = entities.get(entity_id) or {}
    if not entity:
        return None
    kind = str(entity.get("entity_type") or "")
    name = str(entity.get("name") or entity_id)
    href = ENTITY_HREF.get(kind, "").format(id=entity_id) if kind in ENTITY_HREF else ""
    return {
        "id": entity_id,
        "name": name,
        "entity_type": kind,
        "href": href,
        "search_href": f"/search?q={quote_plus(name)}",
    }


def _chips_for(record: dict[str, Any], entities: dict[str, dict[str, Any]], berry_labels: dict[str, str]) -> dict[str, list[dict[str, str]]]:
    companies: list[dict[str, str]] = []
    varieties: list[dict[str, str]] = []
    geographies: list[dict[str, str]] = []
    berries: list[dict[str, str]] = []
    seen: set[str] = set()
    for entity_id in list(record.get("entity_ids") or []) + list(record.get("geography_ids") or []):
        if not entity_id or entity_id in seen:
            continue
        chip = _entity_chip(str(entity_id), entities)
        if not chip:
            continue
        seen.add(str(entity_id))
        kind = chip["entity_type"]
        if kind == "company":
            companies.append(chip)
        elif kind == "variety":
            varieties.append(chip)
        elif kind == "geography":
            geographies.append(chip)
        elif kind == "berry":
            berries.append(chip)
    for berry_id in record.get("berry_ids") or []:
        if berry_id in seen:
            continue
        seen.add(str(berry_id))
        berries.append(
            {
                "id": str(berry_id),
                "name": berry_labels.get(berry_id) or str(berry_id),
                "entity_type": "berry",
                "href": "",
                "search_href": f"/search?q={quote_plus(berry_labels.get(berry_id) or str(berry_id))}",
            }
        )
    return {
        "companies": companies,
        "varieties": varieties,
        "geographies": geographies,
        "berries": berries,
    }


def related_position_indexes(
    records: list[dict[str, Any]],
    *,
    facts: list[dict[str, Any]],
    signals: list[dict[str, Any]],
    assessments: list[dict[str, Any]],
    static_build: bool,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    """Index Facts/Signals/Assessments once for the tagged Evidence set."""

    tagged_ids = {str(record.get("id")) for record in records if record.get("id")}
    records_by_id = {str(record.get("id")): record for record in records if record.get("id")}
    facts_by_evidence: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen_fact: dict[str, set[str]] = defaultdict(set)
    for fact in facts:
        if str(fact.get("status") or "") not in PUBLIC_FACT:
            continue
        fact_id = str(fact.get("id") or "")
        if not fact_id:
            continue
        row = {
            "id": fact_id,
            "statement": fact.get("statement") or fact_id,
            "classification": fact.get("classification") or "fact",
            "status": fact.get("status") or "",
            "href": f"/facts/{fact_id}",
        }
        targets = {str(eid) for eid in (fact.get("evidence_ids") or []) if str(eid) in tagged_ids}
        for evidence_id, record in records_by_id.items():
            if fact_id in (record.get("fact_ids") or []):
                targets.add(evidence_id)
        for evidence_id in targets:
            if fact_id in seen_fact[evidence_id]:
                continue
            seen_fact[evidence_id].add(fact_id)
            facts_by_evidence[evidence_id].append(row)

    signals_by_evidence: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for signal in signals:
        status = str(signal.get("status") or "")
        if static_build and status in STATIC_SIGNAL_SKIP:
            continue
        row = {
            "id": signal.get("id"),
            "title": signal.get("title") or signal.get("id"),
            "status": status,
            "kind_label": "Signal",
            "href": f"/signals/{signal.get('id')}",
        }
        for evidence_id in signal.get("evidence_ids") or []:
            if str(evidence_id) in tagged_ids:
                signals_by_evidence[str(evidence_id)].append(row)

    fact_ids_by_evidence = {
        evidence_id: {str(item.get("id")) for item in rows if item.get("id")}
        for evidence_id, rows in facts_by_evidence.items()
    }
    assessments_by_evidence: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for assessment in assessments:
        if str(assessment.get("status") or "") not in PUBLIC_ASSESSMENT:
            continue
        if static_build and assessment.get("ai_proposed"):
            continue
        row = {
            "id": assessment.get("id"),
            "title": assessment.get("title") or assessment.get("id"),
            "status": assessment.get("status") or "",
            "confidence": assessment.get("confidence") or "",
            "would_change_our_view": assessment.get("would_change_our_view") or "",
            "kind_label": "Assessment",
            "href": f"/assessments/{assessment.get('id')}",
        }
        cited_evidence = {str(eid) for eid in (assessment.get("evidence_ids") or []) if eid}
        cited_facts = {str(fid) for fid in (assessment.get("fact_ids") or []) if fid}
        for evidence_id in tagged_ids:
            if evidence_id in cited_evidence or (cited_facts & fact_ids_by_evidence.get(evidence_id, set())):
                assessments_by_evidence[evidence_id].append(row)
    return facts_by_evidence, signals_by_evidence, assessments_by_evidence


def _testing_level(record: dict[str, Any]) -> str:
    return str(((record.get("priority") or {}).get("testing") or {}).get("level") or "none")


def enrich_position_item(
    record: dict[str, Any],
    *,
    state: dict[str, dict[str, dict[str, Any]]],
    entities: dict[str, dict[str, Any]],
    berry_labels: dict[str, str],
    facts_by_evidence: dict[str, list[dict[str, Any]]],
    signals_by_evidence: dict[str, list[dict[str, Any]]],
    assessments_by_evidence: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    row = present_queue_item(
        record,
        dimension="commercial_position",
        state=state,
        entities=entities,
        berry_labels=berry_labels,
    )
    chips = _chips_for(record, entities, berry_labels)
    item_id = str(record.get("id") or "")
    commercial = record.get("commercial_observation") if isinstance(record.get("commercial_observation"), dict) else {}
    trade = record.get("trade_observation") if isinstance(record.get("trade_observation"), dict) else {}
    berry_code_purity = str(trade.get("berry_code_purity") or "")
    testing_level = _testing_level(record)
    row.update(
        {
            "companies": chips["companies"],
            "varieties": chips["varieties"],
            "geographies": chips["geographies"],
            "berries": chips["berries"],
            "tag_priority": row.get("priority_level") or "none",
            "position_rationale": row.get("why") or "",
            "facts": facts_by_evidence.get(item_id) or [],
            "signals": signals_by_evidence.get(item_id) or [],
            "assessments": assessments_by_evidence.get(item_id) or [],
            "does_not_prove": list(record.get("does_not_prove") or []),
            "commercial_observation": commercial or None,
            "trade_observation": trade or None,
            "berry_code_purity": berry_code_purity,
            "has_testing_tag": testing_level not in {"", "none"},
            "testing_href": f"/queues/testing/{item_id}" if testing_level not in {"", "none"} else "",
            "reader_href": f"/intelligence/{item_id}",
        }
    )
    return row


def _option_rows(items: list[dict[str, Any]], key: str) -> list[dict[str, str]]:
    seen: dict[str, str] = {}
    for item in items:
        for chip in item.get(key) or []:
            chip_id = str(chip.get("id") or "")
            if chip_id and chip_id not in seen:
                seen[chip_id] = str(chip.get("name") or chip_id)
    return [{"id": option_id, "name": name} for option_id, name in sorted(seen.items(), key=lambda pair: pair[1].lower())]


def _matches_filters(item: dict[str, Any], filters: dict[str, str]) -> bool:
    checks = (
        ("berry", "berries"),
        ("company", "companies"),
        ("variety", "varieties"),
        ("geography", "geographies"),
    )
    for filter_key, chip_key in checks:
        wanted = (filters.get(filter_key) or "").strip()
        if not wanted:
            continue
        ids = {str(chip.get("id") or "") for chip in item.get(chip_key) or []}
        if wanted not in ids:
            return False
    return True


def _group_key(item: dict[str, Any]) -> tuple[str, str, str]:
    companies = item.get("companies") or []
    if not companies:
        return ("unattributed", "No company on record", "")
    first = companies[0]
    return (str(first.get("id") or "unattributed"), str(first.get("name") or "Company"), str(first.get("href") or ""))


def commercial_page_model(
    records: list[dict[str, Any]],
    *,
    inbox_dir,
    entities: dict[str, dict[str, Any]],
    berry_labels: dict[str, str],
    facts: list[dict[str, Any]] | None = None,
    signals: list[dict[str, Any]] | None = None,
    assessments: list[dict[str, Any]] | None = None,
    static_build: bool = False,
    filters: dict[str, str] | None = None,
) -> dict[str, Any]:
    from app.services.analyst_queue import load_state

    state = load_state(inbox_dir) if inbox_dir else {}
    facts_by_evidence, signals_by_evidence, assessments_by_evidence = related_position_indexes(
        records,
        facts=facts or [],
        signals=signals or [],
        assessments=assessments or [],
        static_build=static_build,
    )
    items = [
        enrich_position_item(
            record,
            state=state,
            entities=entities,
            berry_labels=berry_labels,
            facts_by_evidence=facts_by_evidence,
            signals_by_evidence=signals_by_evidence,
            assessments_by_evidence=assessments_by_evidence,
        )
        for record in records
    ]
    items.sort(key=lambda row: (str(row.get("date") or ""), str(row.get("title") or "")), reverse=True)
    applied = filters or {"berry": "", "company": "", "variety": "", "geography": ""}
    filter_options = {
        "berries": _option_rows(items, "berries"),
        "companies": _option_rows(items, "companies"),
        "varieties": _option_rows(items, "varieties"),
        "geographies": _option_rows(items, "geographies"),
    }
    visible = [item for item in items if _matches_filters(item, applied)]
    groups_map: dict[str, dict[str, Any]] = {}
    for item in visible:
        group_id, name, href = _group_key(item)
        group = groups_map.setdefault(
            group_id,
            {
                "id": group_id,
                "name": name,
                "href": href,
                "entries": [],
                "berries": [],
                "geographies": [],
                "blackberry_present": False,
            },
        )
        group["entries"].append(item)
        for chip in item.get("berries") or []:
            if chip not in group["berries"]:
                group["berries"].append(chip)
            if chip.get("id") == "berry-blackberry":
                group["blackberry_present"] = True
        for chip in item.get("geographies") or []:
            if chip not in group["geographies"]:
                group["geographies"].append(chip)
    groups = sorted(groups_map.values(), key=lambda group: (group["id"] == "unattributed", group["name"].lower()))
    berry_counts = []
    for option in filter_options["berries"]:
        count = sum(1 for item in items if any(chip.get("id") == option["id"] for chip in item.get("berries") or []))
        berry_counts.append({**option, "count": count})
    blackberry_count = next((row["count"] for row in berry_counts if row["id"] == "berry-blackberry"), 0)
    return {
        "position_items": visible,
        "position_groups": groups,
        "position_filters": applied,
        "position_filter_options": {
            key: rows for key, rows in filter_options.items() if len(rows) > 1
        },
        "position_counts": {
            "tagged": len(items),
            "visible": len(visible),
            "companies": len(groups_map) - (1 if "unattributed" in groups_map else 0),
            "blackberry": blackberry_count,
        },
        "position_berry_counts": berry_counts,
        "position_limitation": (
            "This is tagged published Evidence for commercial-position thinking, not a Position object "
            "and not a competitive score. Tag priority is not truth confidence. "
            "Facts, Signals, and Assessments stay distinct. Trade and commercial observations are context."
        ),
    }
