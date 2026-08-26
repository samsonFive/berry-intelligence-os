"""Claim Testing workspace over tagged published Evidence.

This is not a first-class Claim object store. Items enter because
Evidence.priority.testing.level != none. Analyst Pass / Fail / Defer lives
in inbox/analyst_queue_state.json and never publishes a Fact.

Supporting vs contradicting rows come only from stored evidence_links
predicates. Source independence reuses independence_report — this module
does not invent a second clustering engine.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote_plus

from app.services.analyst_queue import (
    TESTING_ACTIVE,
    TESTING_LABELS,
    load_state,
    present_queue_item,
)
from app.services.source_independence import independence_report

SUPPORT_PREDICATES = {"corroborates"}
CONTRADICT_PREDICATES = {"contradicts"}
LINK_STATUSES = {"proposed", "accepted", "contested"}

ENTITY_HREF = {
    "company": "/entities/company/{id}",
    "variety": "/entities/variety/{id}",
    "geography": "/geographies/{id}",
    "person": "/entities/person/{id}",
    "breeding_program": "/entities/breeding_program/{id}",
}

GROUP_ORDER = ("needs_testing", "defer", "pass", "fail")
GROUP_COPY = {
    "needs_testing": "Needs a human verification decision. Pass/Fail is not a Fact.",
    "defer": "Parked. Still not a Fact and not a Learner Mode topic.",
    "pass": "Analyst recorded a pass on this Evidence. That does not publish a Fact.",
    "fail": "Analyst recorded a fail on this Evidence. That does not publish a Fact.",
}


def related_indexes(
    records: list[dict[str, Any]],
    *,
    get_evidence,
    get_fact,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Load only Evidence/Fact ids cited from the testing set."""

    evidence_by_id = {str(record.get("id")): record for record in records if record.get("id")}
    fact_ids: list[str] = []
    missing: list[str] = []
    for record in records:
        for link in record.get("evidence_links") or []:
            target = str(link.get("target_evidence_id") or "")
            if target and target not in evidence_by_id:
                missing.append(target)
        for fact_id in record.get("fact_ids") or []:
            if fact_id:
                fact_ids.append(str(fact_id))
    for target in dict.fromkeys(missing):
        hit = get_evidence(target)
        if hit:
            evidence_by_id[target] = hit
    facts_by_id: dict[str, dict[str, Any]] = {}
    for fact_id in dict.fromkeys(fact_ids):
        hit = get_fact(fact_id)
        if hit:
            facts_by_id[fact_id] = hit
    return evidence_by_id, facts_by_id


def _entity_chip(entity_id: str, entities: dict[str, dict[str, Any]]) -> dict[str, str] | None:
    entity = entities.get(entity_id) or {}
    if not entity:
        return None
    kind = str(entity.get("entity_type") or "")
    name = str(entity.get("name") or entity_id)
    href = ENTITY_HREF.get(kind, "").format(id=entity_id) if kind in ENTITY_HREF else ""
    search_href = f"/search?q={quote_plus(name)}"
    return {
        "id": entity_id,
        "name": name,
        "entity_type": kind,
        "href": href,
        "search_href": search_href,
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


def _link_rows(
    record: dict[str, Any],
    *,
    predicates: set[str],
    evidence_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for link in record.get("evidence_links") or []:
        predicate = str(link.get("predicate") or "")
        status = str(link.get("status") or "")
        target_id = str(link.get("target_evidence_id") or "")
        if predicate not in predicates or status not in LINK_STATUSES or not target_id:
            continue
        target = evidence_by_id.get(target_id) or {}
        rows.append(
            {
                "predicate": predicate,
                "status": status,
                "id": target_id,
                "title": target.get("title") or target_id,
                "source_name": target.get("source_name") or target.get("source_id") or "",
                "href": f"/intelligence/{target_id}",
                "notes": link.get("notes") or "",
            }
        )
    return rows


def _independence_for(record: dict[str, Any], related: list[dict[str, Any]]) -> dict[str, Any]:
    pool = [record] + [row for row in related if row.get("id") and row.get("id") != record.get("id")]
    if len(pool) < 2:
        return {
            "total_evidence_count": 1,
            "independent_source_count": 1,
            "clusters": [],
            "available": False,
            "note": "Not enough linked Evidence to judge independence. One publication is not independent corroboration of itself.",
        }
    report = independence_report(pool)
    report["available"] = True
    if report["independent_source_count"] < report["total_evidence_count"]:
        report["note"] = (
            f"{report['total_evidence_count']} linked records collapse to "
            f"{report['independent_source_count']} independent origin"
            f"{'' if report['independent_source_count'] == 1 else 's'}. Reprints are not extra confirmation."
        )
    else:
        report["note"] = "Linked records currently cluster as distinct origins. That is not the same as proven truth."
    return report


def enrich_testing_item(
    record: dict[str, Any],
    *,
    state: dict[str, dict[str, dict[str, Any]]],
    entities: dict[str, dict[str, Any]],
    berry_labels: dict[str, str],
    evidence_by_id: dict[str, dict[str, Any]] | None = None,
    facts_by_id: dict[str, dict[str, Any]] | None = None,
    static_build: bool = False,
) -> dict[str, Any]:
    evidence_by_id = evidence_by_id or {}
    facts_by_id = facts_by_id or {}
    row = present_queue_item(
        record,
        dimension="testing",
        state=state,
        entities=entities,
        berry_labels=berry_labels,
    )
    chips = _chips_for(record, entities, berry_labels)
    supporting = _link_rows(record, predicates=SUPPORT_PREDICATES, evidence_by_id=evidence_by_id)
    contradicting = _link_rows(record, predicates=CONTRADICT_PREDICATES, evidence_by_id=evidence_by_id)
    related_records = [
        evidence_by_id[item["id"]]
        for item in supporting + contradicting
        if item.get("id") in evidence_by_id
    ]
    listing_claims = list((record.get("commercial_observation") or {}).get("claims") or [])
    citing_facts = []
    for fact_id in record.get("fact_ids") or []:
        fact = facts_by_id.get(str(fact_id))
        if not fact:
            continue
        citing_facts.append(
            {
                "id": fact_id,
                "statement": fact.get("statement") or fact_id,
                "classification": fact.get("classification") or "fact",
                "status": fact.get("status") or "",
            }
        )
    overlay = (state.get("testing") or {}).get(str(record.get("id") or "")) or {}
    scope_parts = [chip["name"] for group in ("berries", "varieties", "geographies") for chip in chips[group]]
    row.update(
        {
            "claim_kind": "source_claim",
            "normalized_claim": record.get("title") or record.get("id"),
            "exact_wording": record.get("summary") or "",
            "claimant": record.get("source_name") or record.get("source_id") or "Unknown source",
            "source_type": record.get("source_type") or "",
            "source_url": record.get("source_url") or "",
            "why_it_matters": record.get("why_it_matters") or "",
            "testing_rationale": ((record.get("priority") or {}).get("testing") or {}).get("rationale") or "",
            "does_not_prove": list(record.get("does_not_prove") or []),
            "listing_claims": listing_claims,
            "companies": chips["companies"],
            "varieties": chips["varieties"],
            "geographies": chips["geographies"],
            "berries": chips["berries"],
            "scope_label": " · ".join(scope_parts) if scope_parts else "Scope not stored on this record",
            "supporting_evidence": supporting,
            "contradicting_evidence": contradicting,
            "supporting_count": len(supporting),
            "contradicting_count": len(contradicting),
            "unresolved": not supporting and not contradicting,
            "independence": _independence_for(record, related_records),
            "citing_facts": citing_facts,
            "detail_href": f"/queues/testing/{record.get('id')}",
            "search_claimant_href": f"/search?q={quote_plus(str(record.get('source_name') or record.get('title') or ''))}",
            "reviewer": "" if static_build else overlay.get("reviewer") or "",
            "updated_at": "" if static_build else overlay.get("updated_at") or "",
        }
    )
    if static_build:
        row["workflow_state"] = "tagged"
        row["workflow_label"] = "Tagged evidence"
        row["is_active"] = True
        row["needs_consume"] = False
    return row


def _filter_options(items: list[dict[str, Any]]) -> dict[str, list[dict[str, str]]]:
    def uniq(kind: str) -> list[dict[str, str]]:
        seen: dict[str, dict[str, str]] = {}
        for item in items:
            for chip in item.get(kind) or []:
                seen[chip["id"]] = {"id": chip["id"], "name": chip["name"]}
        return sorted(seen.values(), key=lambda row: row["name"].casefold())

    berries = uniq("berries")
    companies = uniq("companies")
    varieties = uniq("varieties")
    geographies = uniq("geographies")
    return {
        "berries": berries,
        "companies": companies if len(companies) >= 2 else [],
        "varieties": varieties if len(varieties) >= 2 else [],
        "geographies": geographies if len(geographies) >= 2 else [],
        "states": [{"id": key, "name": TESTING_LABELS[key]} for key in GROUP_ORDER],
    }


def testing_page_model(
    *,
    records: list[dict[str, Any]],
    inbox_dir,
    entities: dict[str, dict[str, Any]],
    berry_labels: dict[str, str],
    evidence_by_id: dict[str, dict[str, Any]] | None = None,
    facts_by_id: dict[str, dict[str, Any]] | None = None,
    show_completed: bool = False,
    static_build: bool = False,
    filters: dict[str, str] | None = None,
) -> dict[str, Any]:
    state = {} if static_build else load_state(inbox_dir)
    presented = [
        enrich_testing_item(
            record,
            state=state,
            entities=entities,
            berry_labels=berry_labels,
            evidence_by_id=evidence_by_id,
            facts_by_id=facts_by_id,
            static_build=static_build,
        )
        for record in records
    ]
    filters = filters or {}
    options = _filter_options(presented)
    berry = filters.get("berry") or ""
    company = filters.get("company") or ""
    variety = filters.get("variety") or ""
    geography = filters.get("geography") or ""
    workflow = filters.get("state") or ""

    def matches(item: dict[str, Any]) -> bool:
        if berry and not any(chip["id"] == berry for chip in item.get("berries") or []):
            return False
        if company and not any(chip["id"] == company for chip in item.get("companies") or []):
            return False
        if variety and not any(chip["id"] == variety for chip in item.get("varieties") or []):
            return False
        if geography and not any(chip["id"] == geography for chip in item.get("geographies") or []):
            return False
        if workflow and item.get("workflow_state") != workflow:
            return False
        return True

    filtered = [item for item in presented if matches(item)]
    counts = {key: 0 for key in GROUP_ORDER}
    for item in presented:
        key = str(item.get("workflow_state") or "")
        if key in GROUP_ORDER:
            counts[key] += 1
    counts["tagged"] = len(presented)
    groups = []
    if static_build:
        groups.append(
            {
                "key": "tagged",
                "label": "Tagged for verification",
                "blurb": (
                    "Public snapshot of published Evidence tagged for verification. "
                    "Analyst Pass/Fail/Defer is private runtime state and is not shown here."
                ),
                "count": len(filtered),
                "entries": filtered,
            }
        )
    else:
        for key in GROUP_ORDER:
            entries = [item for item in filtered if item.get("workflow_state") == key]
            if not show_completed and key not in TESTING_ACTIVE:
                continue
            if not entries:
                continue
            groups.append(
                {
                    "key": key,
                    "label": TESTING_LABELS[key],
                    "blurb": GROUP_COPY[key],
                    "count": len(entries),
                    "entries": entries,
                }
            )
    return {
        "testing_groups": groups,
        "testing_counts": counts,
        "testing_filters": filters,
        "testing_filter_options": options,
        "testing_limitation": (
            "Claim Testing verifies tagged published Evidence. There is no separate Claim record type. "
            "Pass does not create a Fact. This is not Learner Mode."
        ),
        "items": filtered if show_completed or static_build else [i for i in filtered if i.get("is_active")],
        "active_count": sum(1 for item in presented if item.get("workflow_state") in TESTING_ACTIVE),
        "completed_count": sum(1 for item in presented if item.get("workflow_state") not in TESTING_ACTIVE and item.get("workflow_state") != "tagged"),
        "tagged_count": len(presented),
    }
