"""Claim Testing / Testing Queue presentation.

A Testing Queue item is published Evidence with ``priority.testing.level``
other than ``none``. Analyst disposition lives in
``inbox/analyst_queue_state.json`` and never mutates trusted Evidence or
publishes a Fact.

Real overlay states: ``needs_testing``, ``pass``, ``fail``, ``defer``.
Do not map Pass to Fact or Fail to contradicted Evidence.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote_plus

from app.services.analyst_queue import (
    TESTING_ACTIVE,
    TESTING_LABELS,
    present_queue_item,
)

TESTING_BUCKETS = (
    ("needs_testing", "Needs testing", "Tagged evidence still awaiting Pass, Fail, or Defer."),
    ("pass", "Pass", "Analyst recorded a pass. This is a disposition, not a Fact."),
    ("fail", "Fail", "Analyst recorded a fail. This is a disposition, not contradicted Evidence."),
    ("defer", "Deferred", "Parked without a pass or fail. The source claim stays visible."),
)
SUPPORTING_PREDICATES = {"corroborates"}
CONTRADICTING_PREDICATES = {"contradicts"}
RELATED_PREDICATES = {"follows_up", "same_signal"}
DUPLICATE_PREDICATES = {"duplicates"}
VISIBLE_LINK_STATUSES = {"proposed", "accepted", "contested"}
ENTITY_ROUTE_TYPES = {
    "company": "company",
    "variety": "variety",
    "geography": "geography",
    "berry": "berry",
    "person": "person",
    "brand": "brand",
    "trait": "trait",
    "breeding_program": "breeding_program",
    "retailer": "retailer",
}


def entity_href(entity: dict[str, Any] | None, entity_id: str = "") -> str:
    record = entity or {}
    ident = str(record.get("id") or entity_id or "")
    kind = str(record.get("entity_type") or "")
    folder = ENTITY_ROUTE_TYPES.get(kind, kind or "entity")
    if not ident:
        return "/entities"
    return f"/entities/{folder}/{ident}"


def search_href(*terms: str) -> str:
    query = " ".join(str(term).strip() for term in terms if str(term).strip())
    if not query:
        return "/search"
    return f"/search?q={quote_plus(query)}"


def _entity_ids(record: dict[str, Any]) -> list[str]:
    seen: list[str] = []
    for value in list(record.get("entity_ids") or []) + list(record.get("geography_ids") or []):
        ident = str(value or "")
        if ident and ident not in seen:
            seen.append(ident)
    return seen


def linked_entities(
    record: dict[str, Any],
    entities: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entity_id in _entity_ids(record):
        entity = entities.get(entity_id) or {}
        kind = str(entity.get("entity_type") or "")
        rows.append(
            {
                "id": entity_id,
                "name": str(entity.get("name") or entity_id),
                "entity_type": kind,
                "href": entity_href(entity, entity_id),
                "is_variety": kind == "variety",
                "is_company": kind == "company",
                "is_geography": kind == "geography",
                "is_berry": kind == "berry" or entity_id.startswith("berry-"),
            }
        )
    return rows


def _source_key(record: dict[str, Any]) -> str:
    return str(record.get("source_id") or record.get("source_name") or "").strip().casefold()


def independence_note(source: dict[str, Any], other: dict[str, Any]) -> str:
    source_id = str(source.get("source_id") or "").strip()
    other_id = str(other.get("source_id") or "").strip()
    if source_id and other_id and source_id == other_id:
        return "Same Source — not independent corroboration"
    source_name = str(source.get("source_name") or "").strip().casefold()
    other_name = str(other.get("source_name") or "").strip().casefold()
    if source_name and other_name and source_name == other_name:
        return "Same named source — not independent corroboration"
    return ""


def _present_link(
    link: dict[str, Any],
    *,
    counterpart: dict[str, Any] | None,
    source: dict[str, Any],
    inbound: bool,
) -> dict[str, Any]:
    target_id = str(link.get("target_evidence_id") or (counterpart or {}).get("id") or "")
    record = counterpart or {}
    return {
        "predicate": str(link.get("predicate") or ""),
        "status": str(link.get("status") or ""),
        "notes": str(link.get("notes") or ""),
        "inbound": inbound,
        "id": str(record.get("id") or target_id),
        "title": str(record.get("title") or target_id or "Linked evidence"),
        "source_name": str(record.get("source_name") or record.get("source_type") or ""),
        "summary": str(record.get("summary") or ""),
        "href": f"/intelligence/{record['id']}" if record.get("id") else "",
        "static_href": f"/evidence/{record['id']}" if record.get("id") else "",
        "independence_note": independence_note(source, record) if record else "",
        "missing": counterpart is None,
    }


def evidence_chain(
    record: dict[str, Any],
    published_by_id: dict[str, dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Split existing Evidence links. Does not infer support from repetition."""

    source_id = str(record.get("id") or "")
    supporting: list[dict[str, Any]] = []
    contradicting: list[dict[str, Any]] = []
    related: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []

    def place(row: dict[str, Any]) -> None:
        predicate = row["predicate"]
        if predicate in SUPPORTING_PREDICATES:
            supporting.append(row)
        elif predicate in CONTRADICTING_PREDICATES:
            contradicting.append(row)
        elif predicate in DUPLICATE_PREDICATES:
            duplicates.append(row)
        elif predicate in RELATED_PREDICATES:
            related.append(row)

    for link in record.get("evidence_links") or []:
        if not isinstance(link, dict):
            continue
        if str(link.get("status") or "") not in VISIBLE_LINK_STATUSES:
            continue
        target_id = str(link.get("target_evidence_id") or "")
        place(_present_link(link, counterpart=published_by_id.get(target_id), source=record, inbound=False))

    if source_id:
        for other in published_by_id.values():
            if str(other.get("id") or "") == source_id:
                continue
            for link in other.get("evidence_links") or []:
                if not isinstance(link, dict):
                    continue
                if str(link.get("target_evidence_id") or "") != source_id:
                    continue
                if str(link.get("status") or "") not in VISIBLE_LINK_STATUSES:
                    continue
                place(_present_link(link, counterpart=other, source=record, inbound=True))

    return {
        "supporting": supporting,
        "contradicting": contradicting,
        "related": related,
        "duplicates": duplicates,
    }


def _facts_for_record(
    record: dict[str, Any],
    facts_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for fact_id in record.get("fact_ids") or []:
        fact = facts_by_id.get(str(fact_id)) or {}
        if not fact:
            rows.append(
                {
                    "id": fact_id,
                    "statement": fact_id,
                    "classification": "unknown",
                    "confidence": "",
                    "status": "",
                    "missing": True,
                    "is_claim": False,
                    "is_fact": False,
                    "is_disputed": False,
                }
            )
            continue
        classification = str(fact.get("classification") or "")
        status = str(fact.get("status") or "")
        rows.append(
            {
                **fact,
                "missing": False,
                "is_claim": classification == "claim",
                "is_fact": classification == "fact",
                "is_disputed": status == "disputed",
            }
        )
    return rows


def present_testing_item(
    record: dict[str, Any],
    *,
    state: dict[str, dict[str, dict[str, Any]]],
    entities: dict[str, dict[str, Any]],
    berry_labels: dict[str, str],
    facts_by_id: dict[str, dict[str, Any]] | None = None,
    published_by_id: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    row = present_queue_item(
        record,
        dimension="testing",
        state=state,
        entities=entities,
        berry_labels=berry_labels,
    )
    entities_linked = linked_entities(record, entities)
    facts = _facts_for_record(record, facts_by_id or {})
    chain = evidence_chain(record, published_by_id or {})
    companies = [item for item in entities_linked if item["is_company"]]
    varieties = [item for item in entities_linked if item["is_variety"]]
    geographies = [item for item in entities_linked if item["is_geography"]]
    berries = [
        {
            "id": berry_id,
            "name": berry_labels.get(berry_id) or berry_id,
            "href": f"/entities/berry/{berry_id}",
        }
        for berry_id in (record.get("berry_ids") or [])
        if berry_id
    ]
    claim_facts = [fact for fact in facts if fact.get("is_claim")]
    trusted_facts = [fact for fact in facts if fact.get("is_fact")]
    overlay = ((state.get("testing") or {}).get(str(record.get("id") or "")) or {})
    search_term = (
        (companies[0]["name"] if companies else "")
        or (varieties[0]["name"] if varieties else "")
        or str(record.get("title") or "")
    )
    row.update(
        {
            "detail_href": f"/queues/testing/{record.get('id')}",
            "reader_href": f"/intelligence/{record.get('id')}",
            "trusted_href": f"/evidence/{record.get('id')}",
            "linked_entities": entities_linked,
            "company_links": companies,
            "variety_links": varieties,
            "geography_links": geographies,
            "berry_links": berries,
            "source_name": str(record.get("source_name") or record.get("source_type") or ""),
            "source_id": str(record.get("source_id") or ""),
            "source_url": str(record.get("source_url") or ""),
            "summary": str(record.get("summary") or ""),
            "why_it_matters": str(record.get("why_it_matters") or ""),
            "does_not_prove": [str(item) for item in (record.get("does_not_prove") or []) if item],
            "verification_state": str(record.get("verification_state") or ""),
            "information_confidence": str(record.get("information_confidence") or ""),
            "linked_facts": facts,
            "claim_facts": claim_facts,
            "trusted_facts": trusted_facts,
            "claim_count": len(claim_facts),
            "fact_count": len(trusted_facts),
            "supporting": chain["supporting"],
            "contradicting": chain["contradicting"],
            "related_evidence": chain["related"],
            "duplicate_evidence": chain["duplicates"],
            "support_count": len(chain["supporting"]),
            "contradict_count": len(chain["contradicting"]),
            "last_reviewer": str(overlay.get("reviewer") or ""),
            "last_updated_at": str(overlay.get("updated_at") or ""),
            "last_action": str(overlay.get("action") or ""),
            "search_href": search_href(search_term),
            "search_term": search_term,
        }
    )
    return row


def _option(value: str, label: str | None = None) -> dict[str, str]:
    return {"id": value, "label": label or value}


def filter_options(items: list[dict[str, Any]]) -> dict[str, list[dict[str, str]]]:
    berries: dict[str, str] = {}
    companies: dict[str, str] = {}
    varieties: dict[str, str] = {}
    geographies: dict[str, str] = {}
    sources: dict[str, str] = {}
    levels: dict[str, str] = {}
    for item in items:
        for berry in item.get("berry_links") or []:
            berries[str(berry["id"])] = str(berry["name"])
        for company in item.get("company_links") or []:
            companies[str(company["id"])] = str(company["name"])
        for variety in item.get("variety_links") or []:
            varieties[str(variety["id"])] = str(variety["name"])
        for geography in item.get("geography_links") or []:
            geographies[str(geography["id"])] = str(geography["name"])
        source_name = str(item.get("source_name") or "")
        if source_name:
            sources[source_name] = source_name
        level = str(item.get("priority_level") or "")
        if level and level != "none":
            levels[level] = level
    return {
        "states": [_option(key, label) for key, label, _hint in TESTING_BUCKETS],
        "berries": [_option(key, label) for key, label in sorted(berries.items(), key=lambda row: row[1])],
        "companies": [_option(key, label) for key, label in sorted(companies.items(), key=lambda row: row[1])],
        "varieties": [_option(key, label) for key, label in sorted(varieties.items(), key=lambda row: row[1])],
        "geographies": [_option(key, label) for key, label in sorted(geographies.items(), key=lambda row: row[1])],
        "sources": [_option(key, label) for key, label in sorted(sources.items(), key=lambda row: row[1])],
        "levels": [_option(key, key) for key in ("high", "medium", "low") if key in levels],
    }


def matches_filters(item: dict[str, Any], filters: dict[str, str]) -> bool:
    state = str(filters.get("state") or "")
    if state and str(item.get("workflow_state") or "") != state:
        return False
    berry = str(filters.get("berry") or "")
    if berry and berry not in {row["id"] for row in item.get("berry_links") or []}:
        return False
    company = str(filters.get("company") or "")
    if company and company not in {row["id"] for row in item.get("company_links") or []}:
        return False
    variety = str(filters.get("variety") or "")
    if variety and variety not in {row["id"] for row in item.get("variety_links") or []}:
        return False
    geography = str(filters.get("geography") or "")
    if geography and geography not in {row["id"] for row in item.get("geography_links") or []}:
        return False
    source = str(filters.get("source") or "")
    if source and str(item.get("source_name") or "") != source:
        return False
    level = str(filters.get("level") or "")
    if level and str(item.get("priority_level") or "") != level:
        return False
    return True


def build_testing_workspace(
    *,
    records: list[dict[str, Any]],
    state: dict[str, dict[str, dict[str, Any]]],
    entities: dict[str, dict[str, Any]],
    berry_labels: dict[str, str],
    facts: list[dict[str, Any]] | None = None,
    published: list[dict[str, Any]] | None = None,
    filters: dict[str, str] | None = None,
    berry_context: str = "global",
    show_completed: bool = False,
) -> dict[str, Any]:
    facts_by_id = {str(fact.get("id")): fact for fact in (facts or []) if fact.get("id")}
    published_by_id = {str(item.get("id")): item for item in (published or records) if item.get("id")}
    presented = [
        present_testing_item(
            record,
            state=state,
            entities=entities,
            berry_labels=berry_labels,
            facts_by_id=facts_by_id,
            published_by_id=published_by_id,
        )
        for record in records
    ]
    if berry_context and berry_context != "global":
        presented = [
            item
            for item in presented
            if berry_context in {row["id"] for row in item.get("berry_links") or []}
        ]
    options = filter_options(presented)
    selected = filters or {}
    filtered = [item for item in presented if matches_filters(item, selected)]
    if not show_completed and not selected.get("state"):
        filtered = [item for item in filtered if item.get("workflow_state") in TESTING_ACTIVE]
    buckets = []
    for key, label, hint in TESTING_BUCKETS:
        entries = [item for item in filtered if item.get("workflow_state") == key]
        buckets.append({"key": key, "label": label, "hint": hint, "entries": entries, "count": len(entries)})
    active_count = sum(1 for item in presented if item.get("workflow_state") in TESTING_ACTIVE)
    return {
        "dimension": "testing",
        "label": "Claim testing",
        "eyebrow": "DECIDE — VERIFY THE CLAIM",
        "purpose": (
            "Which concrete claims need verification, what evidence supports or contradicts them, "
            "and what is the analyst's disposition? Pass, Fail, and Defer record disposition only. "
            "They do not publish a Fact. This is not Learner Mode and not model-qualification "
            "or extraction testing."
        ),
        "items": filtered,
        "buckets": buckets,
        "active_count": active_count,
        "tagged_count": len(presented),
        "visible_count": len(filtered),
        "completed_count": len(presented) - active_count,
        "show_completed": show_completed,
        "filter_options": options,
        "filters": {
            "state": selected.get("state") or "",
            "berry": selected.get("berry") or "",
            "company": selected.get("company") or "",
            "variety": selected.get("variety") or "",
            "geography": selected.get("geography") or "",
            "source": selected.get("source") or "",
            "level": selected.get("level") or "",
            "region": selected.get("region") or "",
        },
        "search_href": "/search",
        "workflow_labels": TESTING_LABELS,
    }


def build_testing_detail(
    record: dict[str, Any],
    *,
    state: dict[str, dict[str, dict[str, Any]]],
    entities: dict[str, dict[str, Any]],
    berry_labels: dict[str, str],
    facts: list[dict[str, Any]] | None = None,
    published: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    facts_by_id = {str(fact.get("id")): fact for fact in (facts or []) if fact.get("id")}
    published_by_id = {str(item.get("id")): item for item in (published or [record]) if item.get("id")}
    item = present_testing_item(
        record,
        state=state,
        entities=entities,
        berry_labels=berry_labels,
        facts_by_id=facts_by_id,
        published_by_id=published_by_id,
    )
    unknown: list[str] = []
    if item.get("does_not_prove"):
        unknown.extend(item["does_not_prove"])
    if not item["supporting"] and not item["contradicting"]:
        unknown.append("No supporting or contradicting Evidence links are recorded yet.")
    if any(fact.get("is_disputed") for fact in item["linked_facts"]):
        unknown.append("At least one linked Fact is disputed. That is not a Testing Pass or Fail.")
    if item.get("verification_state") in {"unverified", "single_source", ""}:
        unknown.append("Verification state is not independently corroborated on this Evidence record.")
    item["still_unknown"] = unknown
    item["analyst_conclusion"] = {
        "state": item.get("workflow_state"),
        "label": item.get("workflow_label"),
        "reviewer": item.get("last_reviewer") or "",
        "updated_at": item.get("last_updated_at") or "",
        "action": item.get("last_action") or "",
        "creates_fact": False,
        "note": (
            "Pass, Fail, and Defer are analyst dispositions on tagged Evidence. "
            "They do not convert this claim into a Fact."
        ),
    }
    return item
