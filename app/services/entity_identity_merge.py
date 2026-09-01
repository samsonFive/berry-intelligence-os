"""Safe canonical entity merge.

Only performs an explicit survivor/retired reconciliation. Does not infer
sameness. Does not rewrite Evidence bodies. Leaves a structured audit row.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date
from typing import Any

from app.services.entity_identity import (
    STATE_CONFIRMED_DUPLICATE,
    canonical_entity_id,
    rewrite_id_list,
    rewrite_record_entity_ids,
)

class EntityMergeError(ValueError):
    pass


def _unique(values: list[Any] | tuple[Any, ...] | None) -> list[Any]:
    out: list[Any] = []
    seen: set[str] = set()
    for raw in values or []:
        key = json_key(raw)
        if key in seen:
            continue
        seen.add(key)
        out.append(raw)
    return out


def json_key(value: Any) -> str:
    return repr(value)


def merge_canonical_entities(
    *,
    surviving_id: str,
    retired_id: str,
    entities: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
    evidence: list[dict[str, Any]] | None = None,
    facts: list[dict[str, Any]] | None = None,
    signals: list[dict[str, Any]] | None = None,
    assessments: list[dict[str, Any]] | None = None,
    decided_on: str | None = None,
    reason: str = "",
) -> dict[str, Any]:
    """In-memory merge. Callers persist the returned records."""
    if surviving_id == retired_id:
        raise EntityMergeError("surviving and retired IDs must differ")
    index = {str(row["id"]): deepcopy(row) for row in entities if row.get("id")}
    survivor = index.get(surviving_id)
    retired = index.get(retired_id)
    if not survivor or not retired:
        raise EntityMergeError("both entities must exist to merge")
    if survivor.get("entity_type") != retired.get("entity_type"):
        raise EntityMergeError("cannot merge entities of different types")

    mapping = {retired_id: surviving_id}
    aliases = _unique(list(survivor.get("aliases") or []) + list(retired.get("aliases") or []))
    retired_name = str(retired.get("name") or "").strip()
    survivor_name = str(survivor.get("name") or "").strip()
    if retired_name and retired_name.casefold() != survivor_name.casefold() and retired_name not in aliases:
        aliases.append(retired_name)

    survivor["aliases"] = aliases
    survivor["evidence_ids"] = rewrite_id_list(
        list(survivor.get("evidence_ids") or []) + list(retired.get("evidence_ids") or []),
        {},
    )
    survivor["fact_ids"] = rewrite_id_list(
        list(survivor.get("fact_ids") or []) + list(retired.get("fact_ids") or []),
        {},
    )
    survivor["berry_ids"] = rewrite_id_list(
        list(survivor.get("berry_ids") or []) + list(retired.get("berry_ids") or []),
        {},
    )
    survivor["roles"] = _unique(list(survivor.get("roles") or []) + list(retired.get("roles") or []))
    survivor_attrs = dict(survivor.get("attributes") or {})
    for key, value in (retired.get("attributes") or {}).items():
        if key == "merged_into":
            continue
        if key not in survivor_attrs or survivor_attrs[key] in (None, "", [], {}):
            survivor_attrs[key] = value
    survivor["attributes"] = survivor_attrs
    survivor["status"] = survivor.get("status") or "active"

    retired_attrs = dict(retired.get("attributes") or {})
    retired_attrs["merged_into"] = surviving_id
    retired["attributes"] = retired_attrs
    retired["status"] = "historical"
    retired["aliases"] = list(retired.get("aliases") or [])

    rewritten_relationships: list[dict[str, Any]] = []
    seen_rel: set[tuple[str, str, str]] = set()
    dropped_relationship_ids: list[str] = []
    for rel in relationships:
        updated = rewrite_record_entity_ids(deepcopy(rel), mapping)
        key = (
            str(updated.get("subject_id") or ""),
            str(updated.get("predicate") or ""),
            str(updated.get("object_id") or ""),
        )
        if key in seen_rel:
            if updated.get("id"):
                dropped_relationship_ids.append(str(updated["id"]))
            continue
        seen_rel.add(key)
        rewritten_relationships.append(updated)

    survivor["relationship_ids"] = [
        str(rel["id"])
        for rel in rewritten_relationships
        if rel.get("id") and (rel.get("subject_id") == surviving_id or rel.get("object_id") == surviving_id)
    ]
    retired["relationship_ids"] = []

    def rewrite_rows(rows: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
        return [rewrite_record_entity_ids(deepcopy(row), mapping) for row in (rows or [])]

    rewritten_entities = list(index.values())
    audit = {
        "record_type": "entity_identity_merge",
        "surviving_id": surviving_id,
        "retired_id": retired_id,
        "state": STATE_CONFIRMED_DUPLICATE,
        "decided_on": decided_on or date.today().isoformat(),
        "reason": reason,
        "aliases_preserved": aliases,
        "relationships_rewritten": len(rewritten_relationships),
        "duplicate_relationships_dropped": dropped_relationship_ids,
        "canonical_retired_resolves_to": canonical_entity_id(
            retired_id, entities=rewritten_entities, redirects=[{
                "retired_id": retired_id,
                "surviving_id": surviving_id,
            }]
        ),
        "bodies_rewritten": False,
    }
    return {
        "entities": rewritten_entities,
        "relationships": rewritten_relationships,
        "evidence": rewrite_rows(evidence),
        "facts": rewrite_rows(facts),
        "signals": rewrite_rows(signals),
        "assessments": rewrite_rows(assessments),
        "audit": audit,
    }
