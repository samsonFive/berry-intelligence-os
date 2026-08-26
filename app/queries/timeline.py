"""TimelineQueryService (V2 Phase 2B.2).

Centralizes which date field represents "when did this happen" per record
type -- Evidence uses published_date (never captured_date, which only
marks when the item entered the system), Facts prefer event_date (the
real-world date, backfilled from evidence text) and fall back to
created_at, Relationships use effective_date. This function does not
silently pick one date field for every record type; it preserves exactly
the distinctions app/main.py's entity_activity() already made.

Pure: takes already-loaded record lists, touches no repository directly.
Moved verbatim from app/main.py (V2 Phase 1.5B) -- app.main.entity_activity
is this module's entity_activity, re-exported under its original name so
every existing caller and test keeps working unchanged.
"""

from __future__ import annotations

from typing import Any


def max_priority_level(record: dict[str, Any]) -> str:
    levels_present = {v.get("level") for v in (record.get("priority") or {}).values()}
    for level in ("high", "medium", "low"):
        if level in levels_present:
            return level
    return "none"


def entity_activity(
    linked_evidence: list[dict[str, Any]],
    entity_facts: list[dict[str, Any]],
    entity_relationships: list[dict[str, Any]],
    entities: dict[str, dict[str, Any]],
    evidence_idx: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """A single chronological feed for one entity, merging evidence, facts,
    and relationships -- the "what's new with company X" view the original
    approved mockup showed (assets/platform-visual-language.png, panel 4)
    but was never actually built.

    Only items with a genuine date make the cut. Roughly half of imported
    evidence (mostly reference material -- company/registry/catalog pages,
    patent records) has no real published_date, only a captured_date marking
    when it was pulled into the system. Falling back to captured_date would
    make evergreen reference pages look like breaking news at the top of the
    feed, defeating the entire point of a "what's new" view. Undated items
    are simply excluded here; they remain visible in the Linked Evidence /
    Facts sections below, just not misrepresented as recent activity.

    Facts use event_date (the real-world date the underlying development
    happened, backfilled from evidence text) when available, falling back to
    created_at (when the fact was authored) since that's still a real date --
    just not necessarily *the* newsworthy one."""
    items: list[dict[str, Any]] = []

    for record in linked_evidence:
        date = record.get("published_date")
        if not date:
            continue
        items.append(
            {
                "date": date,
                "type": "evidence",
                "type_label": record.get("source_type", "evidence").replace("_", " ").title(),
                "title": record.get("title", ""),
                "detail": record.get("summary", ""),
                "url": f"/evidence/{record['id']}",
                "priority": max_priority_level(record),
            }
        )

    for fact in entity_facts:
        evidence_id = (fact.get("evidence_ids") or [None])[0]
        evidence = evidence_idx.get(evidence_id) if evidence_id else None
        fallback_date = evidence.get("published_date") if evidence else None
        date = fact.get("event_date") or fact.get("created_at") or fallback_date
        if not date:
            continue
        detail = f"{fact.get('confidence', '')} confidence"
        if fact.get("status") and fact.get("status") != "active":
            detail += f" · {fact['status']}"
        items.append(
            {
                "date": date,
                "type": "fact",
                "type_label": (fact.get("classification") or "fact").title(),
                "title": fact.get("statement", ""),
                "detail": detail,
                "url": f"/evidence/{evidence_id}" if evidence_id else "",
                "priority": None,
            }
        )

    for rel in entity_relationships:
        evidence_id = (rel.get("evidence_ids") or [None])[0]
        evidence = evidence_idx.get(evidence_id) if evidence_id else None
        fallback_date = evidence.get("published_date") if evidence else None
        date = rel.get("effective_date") or fallback_date
        if not date:
            continue
        subject_name = entities.get(rel.get("subject_id"), {}).get("name", rel.get("subject_id"))
        object_name = entities.get(rel.get("object_id"), {}).get("name", rel.get("object_id"))
        predicate = (rel.get("predicate") or "").replace("_", " ")
        items.append(
            {
                "date": date,
                "type": "relationship",
                "type_label": predicate.title(),
                "title": f"{subject_name} {predicate} {object_name}",
                "detail": rel.get("notes", ""),
                "url": f"/evidence/{evidence_id}" if evidence_id else "",
                "priority": None,
            }
        )

    items.sort(key=lambda item: item["date"], reverse=True)
    return items


KIND_LABELS: dict[str, str] = {
    "evidence": "Evidence",
    "rights": "Rights / IP",
    "commercial": "Commercial observation",
    "fact": "Fact",
    "relationship": "Relationship",
    "signal": "Signal",
    "assessment": "Assessment",
}
KIND_ORDER: dict[str, int] = {
    "evidence": 0,
    "rights": 0,
    "commercial": 0,
    "fact": 1,
    "relationship": 2,
    "signal": 3,
    "assessment": 4,
}
SOURCE_TYPE_LABEL: dict[str, str] = {
    "company_press_release": "Company self-report",
    "trade_press": "Trade press (third-party)",
    "patent_record": "Patent registry",
    "plant_breeders_rights_record": "Plant breeders' rights registry",
    "news_search": "News / press coverage",
    "industry_podcast": "Industry podcast",
    "discovered_media": "Discovered media",
    "private_equity_press_release": "Private equity press release",
    "development_finance_press_release": "Development finance press release",
}


def _humanize_source_type(source_type: str) -> str:
    if not source_type:
        return "Unspecified source"
    return SOURCE_TYPE_LABEL.get(source_type, source_type.replace("_", " ").title())


def _party(entity: dict[str, Any] | None) -> dict[str, str]:
    if not entity or not entity.get("id"):
        return {}
    return {
        "id": str(entity["id"]),
        "name": str(entity.get("name") or entity["id"]),
        "href": (
            f"/geographies/{entity['id']}"
            if entity.get("entity_type") == "geography"
            else f"/entities/{entity.get('entity_type')}/{entity['id']}"
        ),
        "entity_type": str(entity.get("entity_type") or ""),
    }


def _entity_chips(entity_ids: list[Any], entities: dict[str, dict[str, Any]], *, exclude: str | None = None) -> list[dict[str, str]]:
    chips: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw_id in entity_ids or []:
        eid = str(raw_id)
        if eid == exclude or eid in seen:
            continue
        seen.add(eid)
        party = _party(entities.get(eid))
        if party:
            chips.append(party)
    return chips


def _is_rights_record(record: dict[str, Any]) -> bool:
    return record.get("source_type") in {"plant_breeders_rights_record", "patent_record"}


def _rights_kind(record: dict[str, Any]) -> str:
    source_type = str(record.get("source_type") or "")
    blob = " ".join(
        [str(record.get("source_name") or ""), str(record.get("title") or ""), str(record.get("source_id") or "")]
    ).casefold()
    if "cpvo" in blob or "community plant variety" in blob:
        return "CPVO"
    if "uspto" in blob or source_type == "patent_record" or "plant patent" in blob:
        return "USPTO"
    if "cfia" in blob or "pbr" in blob or source_type == "plant_breeders_rights_record":
        return "CFIA PBR"
    return "Other filing"


def _is_commercial_observation(record: dict[str, Any]) -> bool:
    return record.get("intake_type") == "commercial_observation" or bool(record.get("commercial_observation"))


def _evidence_row(record: dict[str, Any], *, entities: dict[str, dict[str, Any]], entity_id: str) -> dict[str, Any]:
    is_rights = _is_rights_record(record)
    is_commercial = _is_commercial_observation(record)
    detail = record.get("commercial_observation") or {}
    date = ""
    date_basis = "published_date"
    if is_commercial:
        # observed_at is the commercial event date; published_date is the
        # source publication date. Never fall back to captured_date -- that
        # is ingestion time and must not look like market chronology
        # (AGENTS.md Entity Intelligence Timeline durable rule).
        date = detail.get("observed_at") or record.get("published_date") or ""
        date_basis = "observed_at" if detail.get("observed_at") else "published_date"
    else:
        date = record.get("published_date") or ""
        date_basis = "published_date"
    kind = "rights" if is_rights else ("commercial" if is_commercial else "evidence")
    geography = _entity_chips(record.get("geography_ids") or [], entities)
    chips = [c for c in _entity_chips(record.get("entity_ids") or [], entities, exclude=entity_id) if c["entity_type"] != "geography"]
    return {
        "id": record.get("id"),
        "kind": kind,
        "kind_label": (_rights_kind(record) if is_rights else KIND_LABELS[kind]),
        "date": date or "",
        "date_basis": date_basis,
        "is_fallback_date": is_commercial and not detail.get("observed_at") and bool(date),
        "headline": record.get("title") or "",
        "excerpt": record.get("summary") or "",
        "trust_label": "Trusted",
        "source_name": record.get("source_name") or "",
        "source_type_label": _humanize_source_type(str(record.get("source_type") or "")),
        "source_authority": record.get("source_authority") or "",
        "verification_state": record.get("verification_state") or "",
        "does_not_prove": list(record.get("does_not_prove") or []),
        "berry_ids": list(record.get("berry_ids") or []),
        "geography": geography,
        "entity_chips": chips,
        "reader_href": f"/intelligence/{record['id']}" if record.get("id") else "",
        "evidence_href": f"/evidence/{record['id']}" if record.get("id") else "",
        "retailer_name": detail.get("retailer_name") or "",
        "lineage": [],
        "derived_items": [],
    }


def _fact_row(fact: dict[str, Any], *, entities: dict[str, dict[str, Any]], evidence_idx: dict[str, dict[str, Any]], entity_id: str) -> dict[str, Any]:
    evidence_ids = [str(e) for e in (fact.get("evidence_ids") or []) if e]
    linked_evidence_records = [evidence_idx[e] for e in evidence_ids if e in evidence_idx]
    fallback_dates = sorted(r.get("published_date") for r in linked_evidence_records if r.get("published_date"))
    event_date = fact.get("event_date")
    created_at = fact.get("created_at")
    date = event_date or created_at or (fallback_dates[0] if fallback_dates else "")
    date_basis = "event_date" if event_date else ("created_at" if created_at else ("evidence_published_date" if fallback_dates else ""))
    chips = _entity_chips(fact.get("entity_ids") or [], entities, exclude=entity_id)
    lineage = [
        {"id": r["id"], "title": r.get("title") or r["id"], "href": f"/evidence/{r['id']}"}
        for r in linked_evidence_records
    ]
    return {
        "id": fact.get("id"),
        "kind": "fact",
        "kind_label": KIND_LABELS["fact"],
        "date": date or "",
        "date_basis": date_basis,
        "is_fallback_date": date_basis in {"created_at", "evidence_published_date"},
        "headline": fact.get("statement") or "",
        "excerpt": "",
        "trust_label": "Fact" if fact.get("classification") == "fact" else "Claim",
        "classification": fact.get("classification") or "",
        "confidence": fact.get("confidence") or "",
        "fact_status": fact.get("status") or "",
        "berry_ids": [],
        "geography": [],
        "entity_chips": chips,
        "reader_href": f"/facts/{fact['id']}" if fact.get("id") else "",
        "lineage": lineage,
        "derived_items": [],
        "_evidence_ids": evidence_ids,
    }


def _relationship_row(
    rel: dict[str, Any], *, entities: dict[str, dict[str, Any]], evidence_idx: dict[str, dict[str, Any]], entity_id: str
) -> dict[str, Any]:
    evidence_ids = [str(e) for e in (rel.get("evidence_ids") or []) if e]
    linked_evidence_records = [evidence_idx[e] for e in evidence_ids if e in evidence_idx]
    fallback_dates = sorted(r.get("published_date") for r in linked_evidence_records if r.get("published_date"))
    effective_date = rel.get("effective_date")
    date = effective_date or (fallback_dates[0] if fallback_dates else "")
    date_basis = "effective_date" if effective_date else ("evidence_published_date" if fallback_dates else "")
    subject = entities.get(str(rel.get("subject_id") or ""))
    obj = entities.get(str(rel.get("object_id") or ""))
    predicate = (rel.get("predicate") or "").replace("_", " ")
    headline = f"{_party(subject).get('name') or rel.get('subject_id')} {predicate} {_party(obj).get('name') or rel.get('object_id')}"
    chips = [c for c in (_party(subject), _party(obj)) if c and c.get("id") != entity_id]
    lineage = [
        {"id": r["id"], "title": r.get("title") or r["id"], "href": f"/evidence/{r['id']}"}
        for r in linked_evidence_records
    ]
    return {
        "id": rel.get("id"),
        "kind": "relationship",
        "kind_label": KIND_LABELS["relationship"],
        "date": date or "",
        "date_basis": date_basis,
        "is_fallback_date": date_basis == "evidence_published_date",
        "headline": headline,
        "excerpt": rel.get("notes") or "",
        "trust_label": "Relationship",
        "predicate": rel.get("predicate") or "",
        "relationship_status": rel.get("status") or "",
        "confidence": rel.get("confidence") or "",
        "berry_ids": [],
        "geography": [],
        "entity_chips": chips,
        "reader_href": "",
        "lineage": lineage,
        "derived_items": [],
        "_evidence_ids": evidence_ids,
    }


def _signal_row(
    signal: dict[str, Any], *, entities: dict[str, dict[str, Any]], evidence_idx: dict[str, dict[str, Any]], entity_id: str
) -> dict[str, Any]:
    evidence_ids = [str(e) for e in (signal.get("evidence_ids") or []) if e]
    linked_evidence_records = [evidence_idx[e] for e in evidence_ids if e in evidence_idx]
    fallback_dates = sorted(r.get("published_date") for r in linked_evidence_records if r.get("published_date"))
    first_seen = signal.get("first_seen")
    last_updated = signal.get("last_updated")
    date = first_seen or last_updated or (fallback_dates[0] if fallback_dates else "")
    date_basis = "first_seen" if first_seen else ("last_updated" if last_updated else ("evidence_published_date" if fallback_dates else ""))
    chips = _entity_chips(signal.get("entity_ids") or [], entities, exclude=entity_id)
    lineage = [
        {"id": r["id"], "title": r.get("title") or r["id"], "href": f"/evidence/{r['id']}"}
        for r in linked_evidence_records
    ]
    return {
        "id": signal.get("id"),
        "kind": "signal",
        "kind_label": KIND_LABELS["signal"],
        "date": date or "",
        "date_basis": date_basis,
        "is_fallback_date": date_basis == "evidence_published_date",
        "headline": signal.get("title") or "",
        "excerpt": "",
        "trust_label": "Signal",
        "strength": signal.get("strength") or "",
        "signal_status": signal.get("status") or "",
        "berry_ids": [],
        "geography": [],
        "entity_chips": chips,
        "reader_href": f"/signals/{signal['id']}" if signal.get("id") else "",
        "lineage": lineage,
        "derived_items": [],
        "_evidence_ids": evidence_ids,
    }


def _assessment_row(
    assessment: dict[str, Any],
    *,
    entities: dict[str, dict[str, Any]],
    evidence_idx: dict[str, dict[str, Any]],
    entity_id: str,
) -> dict[str, Any]:
    date = assessment.get("created_at") or ""
    chips = _entity_chips(assessment.get("entity_ids") or [], entities, exclude=entity_id)
    evidence_ids = [str(e) for e in (assessment.get("evidence_ids") or []) if e]
    linked_evidence_records = [evidence_idx[e] for e in evidence_ids if e in evidence_idx]
    lineage = [
        {"id": r["id"], "title": r.get("title") or r["id"], "href": f"/evidence/{r['id']}"}
        for r in linked_evidence_records
    ]
    # Prefer why_it_matters when present (PR #180 fidelity); else rationale.
    excerpt = (assessment.get("why_it_matters") or assessment.get("rationale") or "").strip()
    return {
        "id": assessment.get("id"),
        "kind": "assessment",
        "kind_label": KIND_LABELS["assessment"],
        "date": date,
        "date_basis": "created_at",
        "is_fallback_date": False,
        "headline": assessment.get("title") or "",
        "excerpt": excerpt,
        "trust_label": "Assessment",
        "confidence": assessment.get("confidence") or "",
        "ai_proposed": bool(assessment.get("ai_proposed")),
        "assessment_status": assessment.get("status") or "",
        "berry_ids": [],
        "geography": [],
        "entity_chips": chips,
        "reader_href": f"/assessments/{assessment['id']}" if assessment.get("id") else "",
        "lineage": lineage,
        "derived_items": [],
    }


def entity_intelligence_timeline(
    *,
    entity_id: str,
    entities: dict[str, dict[str, Any]],
    linked_evidence: list[dict[str, Any]],
    entity_facts: list[dict[str, Any]],
    entity_relationships: list[dict[str, Any]],
    entity_signals: list[dict[str, Any]],
    entity_assessments: list[dict[str, Any]],
    evidence_idx: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """The shared Company/Variety Intelligence Timeline query layer (V1).

    A derived, read-only presentation view over already-trusted objects --
    no new schema, no persisted TimelineEvent. Reuses exactly the
    date-preference philosophy entity_activity() established (Evidence:
    published_date only; Fact: event_date -> created_at; Relationship:
    effective_date) and extends it honestly to Signal (first_seen ->
    last_updated, real data shows both are unpopulated on every live
    Signal today) and Assessment (created_at is the correct semantic date
    for an analyst interpretation, not a fallback). Every row that used
    anything other than its own primary real-world date field carries
    is_fallback_date=True so the template can say so rather than silently
    presenting a record-authored timestamp as history.

    Deterministic grouping: a Fact or Relationship whose evidence_ids
    resolves to an Evidence row already present in this same entity's
    linked_evidence is nested under that Evidence row as a derived_items
    child (one source-event cluster) rather than shown as a third,
    repetitive flat entry. A Fact/Relationship whose evidence points
    elsewhere keeps its own top-level row with a lineage pointer instead --
    honest separation over brittle deduplication, per this mission's own
    instruction.
    """
    evidence_rows = {
        str(r["id"]): _evidence_row(r, entities=entities, entity_id=entity_id)
        for r in linked_evidence
        if r.get("id")
    }
    fact_rows = [_fact_row(f, entities=entities, evidence_idx=evidence_idx, entity_id=entity_id) for f in entity_facts]
    relationship_rows = [
        _relationship_row(r, entities=entities, evidence_idx=evidence_idx, entity_id=entity_id) for r in entity_relationships
    ]
    signal_rows = [_signal_row(s, entities=entities, evidence_idx=evidence_idx, entity_id=entity_id) for s in entity_signals]
    assessment_rows = [
        _assessment_row(a, entities=entities, evidence_idx=evidence_idx, entity_id=entity_id)
        for a in entity_assessments
    ]

    top_level: list[dict[str, Any]] = list(evidence_rows.values())
    for row in fact_rows + relationship_rows:
        parent_id = next((eid for eid in row["_evidence_ids"] if eid in evidence_rows), None)
        row.pop("_evidence_ids", None)
        if parent_id:
            evidence_rows[parent_id]["derived_items"].append(row)
        else:
            top_level.append(row)
    for row in signal_rows:
        row.pop("_evidence_ids", None)
    top_level.extend(signal_rows)
    top_level.extend(assessment_rows)

    for row in evidence_rows.values():
        row["derived_items"].sort(key=lambda r: (r["kind"] != "fact", str(r.get("date") or "")))

    dated = [row for row in top_level if row.get("date")]
    undated = [row for row in top_level if not row.get("date")]
    dated.sort(key=lambda row: (row["date"], KIND_ORDER.get(row["kind"], 9), str(row.get("id") or "")), reverse=True)
    undated.sort(key=lambda row: (KIND_ORDER.get(row["kind"], 9), str(row.get("id") or "")))

    kinds_present = sorted({row["kind"] for row in dated + undated})
    berries_present = sorted({b for row in dated + undated for b in row.get("berry_ids") or []})

    return {
        "dated": dated,
        "undated": undated,
        "has_any": bool(dated or undated),
        "kinds_present": kinds_present,
        "berries_present": berries_present,
        "dated_count": len(dated),
        "undated_count": len(undated),
    }


class TimelineQueryService:
    """Thin composition-registry wrapper around the module-level functions
    above, for callers that reach it via get_query_services() rather than
    importing directly."""

    def __init__(self, repos: Any) -> None:
        self._repos = repos

    def entity_activity(
        self,
        linked_evidence: list[dict[str, Any]],
        entity_facts: list[dict[str, Any]],
        entity_relationships: list[dict[str, Any]],
        entities: dict[str, dict[str, Any]],
        evidence_idx: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        return entity_activity(linked_evidence, entity_facts, entity_relationships, entities, evidence_idx)

    def entity_intelligence_timeline(self, **kwargs: Any) -> dict[str, Any]:
        return entity_intelligence_timeline(**kwargs)
