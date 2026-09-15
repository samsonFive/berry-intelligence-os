"""Company + Genetics Relationships V1 -- competitor registry data contract.

This module is a small, additive data-layer service, not a UI and not a
second discovery/collection engine. It answers exactly one question for the
(separately owned) visual Landscape page: "what is the full, unfiltered
33-entry competitor roster, and what do we honestly know about each entry's
classification and monitoring state right now?"

It intentionally does NOT reuse `app/services/berries/landscape.py`'s own
`actor_rows` filter (companies tagged "competitor" AND showing real
signals/evidence/varieties) -- that filter exists to keep the Landscape
page's "Actors to Watch" section from padding itself with zero-activity
companies, which is the right behavior for that page but the wrong behavior
here: a mandatory 33-entry roster must show every entry, including a
freshly-added company with zero captured activity so far. This module reads
the same underlying entities/relationships/sources every other presentation
service already reads (no repository access of its own beyond one small,
additive `data/imports/*/snapshot.json` loader mirroring
`app.services.coverage_assurance.benchmarks.load_benchmarks`'s own existing
`data/imports/*/benchmark.json` convention) and never mutates anything.

Tier/priority/region classification lives in the frozen snapshot import
(`data/imports/competitor-registry-<date>/snapshot.json`), not duplicated
onto entity records beyond a small back-pointer
(`attributes.competitor_registry_<date>`) -- a later re-import creates a
NEW dated snapshot directory (see `load_latest_snapshot`) rather than
overwriting this one, which is how classification history is preserved.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MONITORING_STATES = (
    "linked_to_runnable_source",
    "source_configured_never_run",
    "source_blocked",
    "discovery_pending",
    "no_supported_source",
    "manual_monitoring_required",
)

_KNOWN_BLOCKED_ENTITIES = {
    # entity_id -> human-readable detail. Small, explicit, honest allowlist --
    # never inferred generically from a Source's own status field, since
    # "reference" (no discovery adapter) alone does not mean "blocked"; it
    # can also mean "manual monitoring required" (no adapter attempted yet)
    # or "discovery pending" (adapter planned). This entity is specifically
    # known-blocked because a *diagnosed* acquisition attempt (a real, cited
    # investigation, not a guess) found it structurally blocked.
    "company-california-giant-berry-farms": (
        "Two Cal Giant Source entries exist as type 'reference' with no discovery adapter; direct "
        "calgiant.com acquisition is TLS/HTTP-client-fingerprint blocked (Cloudflare bot management), "
        "confirmed on fix/astra-news-reader (commit 721a20a). Cited, not re-diagnosed here."
    ),
}


def _entities_by_id(entities: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {e["id"]: e for e in entities if e.get("id")}


def monitoring_state_for_entity(entity_id: str, *, sources: list[dict[str, Any]]) -> dict[str, str]:
    """One current monitoring state for `entity_id`, from real data only --
    never fabricated and never a source count presented as recall (see
    AGENTS.md's Source Health rule, which this function deliberately
    mirrors for a single entity rather than the whole Source inventory).
    """
    if entity_id in _KNOWN_BLOCKED_ENTITIES:
        return {"state": "source_blocked", "detail": _KNOWN_BLOCKED_ENTITIES[entity_id]}

    linked = [
        s for s in sources
        if entity_id in (s.get("linked_competitor_ids") or [])
    ]
    if not linked:
        return {
            "state": "no_supported_source",
            "detail": "No Source record links this entity via linked_competitor_ids, and none was "
            "researched or fabricated for it by this import.",
        }

    runnable = [s for s in linked if (s.get("discovery") or {}).get("adapter") and (
        (s.get("discovery") or {}).get("feed_url") or (s.get("discovery") or {}).get("feed_urls")
    )]
    if not runnable:
        return {
            "state": "manual_monitoring_required",
            "detail": f"{len(linked)} linked Source(s) exist but none carry a discovery adapter/feed "
            "configuration -- manual/analyst-driven monitoring only.",
        }

    never_run = [s for s in runnable if not s.get("last_checked_at")]
    if never_run:
        names = ", ".join(sorted(s["id"] for s in never_run))
        return {
            "state": "source_configured_never_run",
            "detail": f"Discovery-eligible Source(s) {names} exist and have never been run "
            "(last_checked_at is null).",
        }

    return {
        "state": "linked_to_runnable_source",
        "detail": f"{len(runnable)} linked, discovery-configured Source(s) with at least one completed run.",
    }


def load_latest_snapshot(data_dir: Path) -> dict[str, Any] | None:
    """Most recent `data/imports/competitor-registry-*/snapshot.json` by its
    own `snapshot_date` field -- a future re-import creates a new dated
    directory (never overwrites this one), which is how classification
    history survives. Returns None if no snapshot has ever been imported."""
    imports_dir = Path(data_dir) / "imports"
    if not imports_dir.is_dir():
        return None
    candidates: list[dict[str, Any]] = []
    for path in sorted(imports_dir.glob("competitor-registry-*/snapshot.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict) and payload.get("snapshot_date"):
            candidates.append(payload)
    if not candidates:
        return None
    return max(candidates, key=lambda p: p["snapshot_date"])


def load_reconciliation_matrix(data_dir: Path, *, snapshot_date: str | None = None) -> dict[str, Any] | None:
    """Companion reconciliation-matrix.json for the snapshot identified by
    `snapshot_date` (defaults to the latest snapshot's own date)."""
    imports_dir = Path(data_dir) / "imports"
    if snapshot_date is None:
        snapshot = load_latest_snapshot(data_dir)
        if snapshot is None:
            return None
        snapshot_date = snapshot["snapshot_date"]
    path = imports_dir / f"competitor-registry-{snapshot_date}" / "reconciliation-matrix.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def unfiltered_competitor_registry(
    *, data_dir: Path, entities: list[dict[str, Any]], sources: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """The full, unfiltered roster -- every row from the latest reconciliation
    matrix, always returned regardless of blank tier/priority fields, missing
    evidence, or zero captured activity. This is the "product acceptance"
    surface: a mandatory roster is inventory, not a filtered "shown because
    of activity" view like Landscape's Actors to Watch.

    Each row is re-resolved against the CURRENT entity graph and CURRENT
    Source registry at call time (never a frozen copy) -- entity display
    name/status/roles and monitoring state can both change after the
    snapshot was imported; the classification fields (tier/priority/region)
    remain exactly what the dated snapshot says, since those are historical
    record, not live-recomputed.
    """
    matrix = load_reconciliation_matrix(data_dir)
    if matrix is None:
        return []
    by_id = _entities_by_id(entities)
    rows = []
    for row in matrix["rows"]:
        entity = by_id.get(row["canonical_entity_id"])
        monitoring = monitoring_state_for_entity(row["canonical_entity_id"], sources=sources)
        rows.append(
            {
                **row,
                "entity_found": entity is not None,
                "entity_status": entity.get("status") if entity else "missing",
                "entity_name_current": entity.get("name") if entity else row["canonical_display_name"],
                "entity_roles_current": entity.get("roles") if entity else [],
                "monitoring_state": monitoring["state"],
                "monitoring_detail": monitoring["detail"],
            }
        )
    return rows


def genetics_relationships_for_company(
    company_id: str, *, relationships: list[dict[str, Any]], entities: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Company -> genetics providers/programs, both directions of the
    generic Relationship predicates this mission reused (never a new
    parallel schema): returns every relationship where `company_id` is
    either the subject (this company associated with a provider) or the
    object (a provider/company associated with this company), tagged with
    which direction it is. Trust state (`status`) is passed through
    unchanged -- a 'disputed' (pending-review) row is never silently
    presented as confirmed."""
    by_id = _entities_by_id(entities)
    results = []
    for rel in relationships:
        if rel.get("subject_id") == company_id:
            other = rel.get("object_id")
            direction = "outgoing"
        elif rel.get("object_id") == company_id:
            other = rel.get("subject_id")
            direction = "incoming"
        else:
            continue
        other_entity = by_id.get(other)
        results.append(
            {
                "relationship_id": rel["id"],
                "direction": direction,
                "predicate": rel["predicate"],
                "other_entity_id": other,
                "other_entity_name": other_entity.get("name") if other_entity else other,
                "status": rel.get("status"),
                "confidence": rel.get("confidence"),
                "notes": rel.get("notes", ""),
                "evidence_ids": rel.get("evidence_ids") or [],
            }
        )
    return results


def companies_for_genetics_provider(
    provider_id: str, *, relationships: list[dict[str, Any]], entities: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Genetics provider/program -> companies associated with it. Thin
    inverse of `genetics_relationships_for_company` sharing the exact same
    walk, kept as a separate named entry point since "which companies use
    this provider" is a different real question a caller will ask than
    "which providers does this company use", per the mission's bidirectional
    requirement."""
    return [
        row for row in genetics_relationships_for_company(provider_id, relationships=relationships, entities=entities)
        if row["direction"] == "incoming"
    ]
