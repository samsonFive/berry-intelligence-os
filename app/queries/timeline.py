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
