"""Geographic Intelligence Resolution V1 -- canonical geography hierarchy.

Reads ONLY explicit, stored "part_of" Relationship records (authored by
scripts/generate_geography_containment.py from the UN M49 standard as a
one-time bootstrap; never invented or re-derived at runtime) -- never
infers containment from entity names, attributes.region free text, or
ISO codes at query time. That distinguishes this module from
app.services.berries.geography's REGION_LOOKUP/REGIONS, which is a
fixed, incomplete, taxonomy-inconsistent name->label table with no
entity-to-entity relationship at all and is deliberately NOT reused
here as canonical hierarchy.

Descendant/ancestor sets are resolved once per query from the full
relationships list the caller already loaded (the same "no per-record
repository scan" pattern every other query service in this codebase
follows -- see app.queries.scope/entity_intelligence), never re-scanned
per Evidence/Signal/Assessment record. A geography with no part_of
edges (most of the corpus today) simply has an empty descendant set and
behaves exactly as direct-id matching always has -- fully backward
compatible.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

PART_OF = "part_of"


def _children_index(relationships: list[dict[str, Any]]) -> dict[str, set[str]]:
    """object_id (parent) -> {subject_id, ...} (direct children), built
    once from status=active part_of relationships only."""
    children: dict[str, set[str]] = {}
    for rel in relationships:
        if rel.get("predicate") != PART_OF or rel.get("status") != "active":
            continue
        parent = str(rel.get("object_id") or "")
        child = str(rel.get("subject_id") or "")
        if parent and child:
            children.setdefault(parent, set()).add(child)
    return children


def _parent_index(relationships: list[dict[str, Any]]) -> dict[str, str]:
    parents: dict[str, str] = {}
    for rel in relationships:
        if rel.get("predicate") != PART_OF or rel.get("status") != "active":
            continue
        child = str(rel.get("subject_id") or "")
        parent = str(rel.get("object_id") or "")
        if child and parent:
            parents[child] = parent
    return parents


def geography_descendants(geography_id: str, *, relationships: list[dict[str, Any]]) -> set[str]:
    """Every geography explicitly contained within geography_id, at any
    depth, via stored part_of edges only -- a BFS that visits each node
    at most once, so a bad/cyclic edge (never produced by
    generate_geography_containment.py's own validation, but this stays
    safe even against a hand-authored one) can never loop forever."""
    if not geography_id:
        return set()
    children_index = _children_index(relationships)
    result: set[str] = set()
    frontier = [geography_id]
    while frontier:
        current = frontier.pop()
        for child in children_index.get(current, ()):
            if child not in result:
                result.add(child)
                frontier.append(child)
    return result


def geography_ancestors(geography_id: str, *, relationships: list[dict[str, Any]]) -> set[str]:
    """Direct-line ancestors only (this corpus's hierarchy is flat today,
    but the walk is general). Cycle-safe."""
    if not geography_id:
        return set()
    parents_index = _parent_index(relationships)
    result: set[str] = set()
    current = geography_id
    while current in parents_index:
        parent = parents_index[current]
        if parent in result:
            break
        result.add(parent)
        current = parent
    return result


@dataclass(frozen=True)
class GeographyScope:
    selected_id: str
    descendant_ids: frozenset[str]
    ancestor_ids: frozenset[str]

    @property
    def all_ids(self) -> frozenset[str]:
        """What a retrieval filter should intersect against: the selected
        geography plus every canonical descendant. Never includes
        ancestors -- a query scoped to Spain must never pull in
        Europe-only content just because Spain is part of Europe."""
        return frozenset({self.selected_id, *self.descendant_ids})


def resolve_geography_scope(geography_id: str, *, relationships: list[dict[str, Any]]) -> GeographyScope:
    """The single entry point callers should use for geography-scoped
    retrieval. Ancestors are exposed purely for optional display/context
    (e.g. "Spain, part of Europe"), never folded into all_ids."""
    return GeographyScope(
        selected_id=geography_id,
        descendant_ids=frozenset(geography_descendants(geography_id, relationships=relationships)),
        ancestor_ids=frozenset(geography_ancestors(geography_id, relationships=relationships)),
    )


def matched_geography_ids(record: dict[str, Any], scope_geography_ids: frozenset[str] | set[str]) -> tuple[str, ...]:
    """Provenance: which specific geography id(s) on this record actually
    matched a (possibly hierarchy-expanded) scope -- e.g. a Europe query
    matching a Spain-tagged Evidence record returns ("geography-spain",),
    never silently relabeled as Europe. Checks both geography_ids and
    entity_ids (a geography id can legitimately appear in either field
    across this corpus's history -- see app.services.geography_workspace's
    same dual-check)."""
    record_ids = set(record.get("geography_ids") or []) | set(record.get("entity_ids") or [])
    return tuple(sorted(record_ids & set(scope_geography_ids)))
