"""Competitor Profile Data Service V1.

One reusable profile view model for a single roster entity, composed
entirely from already-existing, already-verified services -- this module
adds no new discovery, no new research, no new canonical facts, and no UI.
It answers "what do we honestly know about this one competitor" the way
`app/services/competitor_registry.py` answers "what is the full roster"
and `app/services/competitor_landscape.py` answers "what does the filtered
grid look like" -- a third, complementary read path over the same data,
not a fourth company database.

Reused verbatim rather than re-derived:
  - `competitor_registry.load_reconciliation_matrix/monitoring_maturity_for_entity/
     genetics_relationships_for_company/companies_for_genetics_provider`
     for classification, monitoring, and genetics-provider facts.
  - `competitor_landscape.CompetitorLandscapeAdapter/selected_company_detail/
     LandscapeFilters/filters_to_query` for the same per-row gap detection
     and filtered-landscape-URL construction the `/competitors` page itself
     uses -- a profile's "unresolved data gaps" and "filtered landscape
     URLs" fields must never drift from what that page already shows for
     the same entity.
  - `company_workspace._company_portfolio_roles` for VERIFIED Variety
     relationships (the existing owns/develops/licenses/markets/grows/
     distributes role-bucket walk) -- deliberately never confused with the
     separate, pending, provider-level genetics assertions above.

Every field this module returns is traceable to one of those pre-existing,
already-tested services. Nothing here performs new web research, writes
canonical data, or activates a Source.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from app.services.company_workspace import _company_portfolio_roles
from app.services.competitor_landscape import (
    CompetitorLandscapeAdapter,
    LandscapeFilters,
    _data_gaps,
    filters_to_query,
    selected_company_detail,
)
from app.services.competitor_registry import (
    companies_for_genetics_provider,
    genetics_relationships_for_company,
    load_reconciliation_matrix,
    monitoring_maturity_for_entity,
)

BERRIES = ("strawberry", "blueberry", "raspberry", "blackberry")

# The completeness dimensions this service audits, in a fixed order so a
# caller can render them consistently. Each dimension is scored
# independently -- see `profile_completeness()` -- and a dimension that is
# legitimately not applicable (e.g. "genetics" for an entity with no
# handwritten-note evidence either way) is reported as such, never folded
# into a missing/incomplete count it does not belong in.
COMPLETENESS_DIMENSIONS = (
    "identity",
    "aliases",
    "classifications",
    "berry_positions",
    "regions",
    "genetics",
    "source_configuration",
    "operational_discovery",
    "readable_content",
    "current_coverage",
)


def _entities_by_id(entities: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {e["id"]: e for e in entities if e.get("id")}


def _profile_url_for(entity: dict[str, Any] | None, *, fallback_id: str, entry_route: str | None) -> str:
    """Mirrors `CompetitorLandscapeAdapter._row_from_entry`'s own profile_url
    derivation exactly, so a profile and a landscape row never disagree
    about where "View profile" should go."""
    if entry_route:
        return str(entry_route)
    if entity is None:
        return ""
    entity_type = str(entity.get("entity_type") or "company")
    return f"/entities/{entity_type}/{entity.get('id')}"


def _identity_block(entity: dict[str, Any] | None, row: dict[str, Any]) -> dict[str, Any]:
    """Identity status, confidence, and provenance -- kept entirely
    separate from internal classification and from monitoring/coverage.
    Reads `attributes.identity_verification_<date>` when Competitor
    Identity and Genetics Verification V1 recorded one (any dated key --
    a future re-verification adds a new dated block, never overwrites);
    falls back to the reconciliation matrix's own resolution_status for an
    entity that has not yet had a dedicated identity-verification pass."""
    if entity is None:
        return {
            "entity_found": False,
            "status": "missing",
            "resolution_status": row.get("resolution_status"),
            "confidence": None,
            "verdict": None,
            "reason": "No canonical entity record resolves this roster row's canonical_entity_id.",
            "evidence_urls": [],
            "verification_date": None,
        }
    attributes = entity.get("attributes") or {}
    verification_keys = sorted(
        (key for key in attributes if key.startswith("identity_verification_")), reverse=True
    )
    if verification_keys:
        block = attributes[verification_keys[0]]
        return {
            "entity_found": True,
            "status": entity.get("status"),
            "resolution_status": row.get("resolution_status"),
            "confidence": block.get("confidence"),
            "verdict": block.get("verdict"),
            "reason": block.get("reason"),
            "evidence_urls": block.get("evidence_urls") or [],
            "verification_date": block.get("verification_date"),
        }
    return {
        "entity_found": True,
        "status": entity.get("status"),
        "resolution_status": row.get("resolution_status"),
        "confidence": None,
        "verdict": None,
        "reason": (
            "Existing exact/alias match from the original competitor-registry reconciliation; "
            "no dedicated identity-verification pass has been recorded for this entity."
            if row.get("resolution_status") != "newly_created"
            else "Newly represented entity; no dedicated identity-verification pass has been recorded yet."
        ),
        "evidence_urls": [],
        "verification_date": None,
    }


def _parent_brand_relationships(
    entity: dict[str, Any] | None, *, relationships: list[dict[str, Any]], entities_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Parent/subsidiary/brand/division/program relationships already
    modeled as real Relationship records (owns/part_of/etc.) touching this
    entity -- read-only, never inferred beyond what a stored relationship
    already asserts."""
    if entity is None:
        return []
    entity_id = entity["id"]
    rows: list[dict[str, Any]] = []
    for rel in relationships:
        subject_is_self = rel.get("subject_id") == entity_id
        object_is_self = rel.get("object_id") == entity_id
        if not (subject_is_self or object_is_self):
            continue
        other_id = rel.get("object_id") if subject_is_self else rel.get("subject_id")
        other = entities_by_id.get(other_id)
        if not other or other.get("entity_type") not in {"company", "brand", "breeding_program"}:
            continue
        if rel.get("predicate") not in {"owns", "part_of", "partners_with"}:
            continue
        rows.append(
            {
                "relationship_id": rel["id"],
                "direction": "outgoing" if subject_is_self else "incoming",
                "predicate": rel["predicate"],
                "other_entity_id": other_id,
                "other_entity_name": other.get("name"),
                "other_entity_type": other.get("entity_type"),
                "status": rel.get("status"),
            }
        )
    return rows


def _verified_variety_relationships(
    entity: dict[str, Any] | None, *, relationships: list[dict[str, Any]], entities: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Real, already-trusted Company/Brand/Program -> Variety relationships
    (owns/develops/licenses/markets/grows/distributes), reusing the exact
    role-bucket walk `_company_portfolio_roles` already proved for Company
    Compare/Portfolio -- works for any subject entity id regardless of
    entity_type, since the function itself only requires the *object* to
    be a Variety. Deliberately never confused with `genetics_providers`
    below, which are pending, provider-level, non-Variety assertions."""
    if entity is None:
        return {}
    return _company_portfolio_roles(entity["id"], relationships=relationships, entities=_entities_by_id(entities))


def _genetics_block(
    entity: dict[str, Any] | None, *, relationships: list[dict[str, Any]], entities: list[dict[str, Any]],
) -> dict[str, Any]:
    """Provider-level genetics associations (this entity <-> another
    company/program), bidirectional, with review state and confidence
    passed through unchanged -- never presented as more certain than the
    stored relationship's own `status`/`confidence` say."""
    if entity is None:
        return {"as_company": [], "as_provider": []}
    entity_id = entity["id"]
    as_company = genetics_relationships_for_company(entity_id, relationships=relationships, entities=entities)
    as_provider = companies_for_genetics_provider(entity_id, relationships=relationships, entities=entities)
    return {"as_company": as_company, "as_provider": as_provider}


def _completeness_status(present: bool | None, *, not_applicable: bool = False) -> str:
    if not_applicable:
        return "not_applicable"
    return "present" if present else "missing"


def profile_completeness(profile: dict[str, Any]) -> dict[str, Any]:
    """Deterministic, per-dimension completeness -- never a single blended
    score, per this mission's own rule. A dimension legitimately absent
    (e.g. no genetics assertion exists either way for this company) is
    `not_applicable`, not `missing` -- the two must never be conflated,
    since `missing` implies a real gap and `not_applicable` does not."""
    identity = profile["identity"]
    classification = profile["classification"]
    genetics = profile["genetics"]
    maturity = profile["monitoring"]["maturity"]

    has_genetics_evidence = bool(genetics["as_company"] or genetics["as_provider"])
    dims = {
        "identity": _completeness_status(identity["entity_found"] and identity["status"] == "active"),
        "aliases": _completeness_status(bool(profile["aliases"])),
        "classifications": _completeness_status(bool(classification["competitor_type"])),
        "berry_positions": _completeness_status(
            any(v not in ("unassigned",) for v in classification["berry_tier"].values())
        ),
        "regions": _completeness_status(bool(classification["regions"])),
        "genetics": _completeness_status(has_genetics_evidence, not_applicable=not has_genetics_evidence and not profile["unresolved_data_gaps"]),
        "source_configuration": _completeness_status(bool(maturity.get("discovery_configured"))),
        "operational_discovery": _completeness_status(bool(maturity.get("discovery_operational"))),
        "readable_content": _completeness_status(bool(maturity.get("readable_content_acquired"))),
        "current_coverage": _completeness_status(bool(maturity.get("current_coverage_available"))),
    }
    present_count = sum(1 for v in dims.values() if v == "present")
    applicable_count = sum(1 for v in dims.values() if v != "not_applicable")
    return {
        "dimensions": dims,
        "present_count": present_count,
        "applicable_count": applicable_count,
        "missing_count": sum(1 for v in dims.values() if v == "missing"),
        "not_applicable_count": sum(1 for v in dims.values() if v == "not_applicable"),
        "note": (
            "A per-dimension completeness map, never a single invented strategic score. "
            "`not_applicable` means the dimension legitimately does not apply yet (e.g. no genetics "
            "assertion exists either way); `missing` means a real, addressable gap."
        ),
    }


def _filtered_landscape_urls(row: dict[str, Any], *, entity_id: str) -> list[dict[str, str]]:
    """One `/competitors?...` deep link per berry this entity has ANY
    recorded position for (including 'unassigned', so a caller can still
    jump to that berry's filtered view), reusing the landscape page's own
    `LandscapeFilters`/`filters_to_query` builders verbatim -- a profile
    link must never diverge from what typing the same filters into
    `/competitors` itself would produce."""
    links = []
    for berry in BERRIES:
        filters = LandscapeFilters(berry=berry, company=entity_id)
        links.append(
            {
                "berry": berry,
                "href": f"/competitors?{filters_to_query(filters, include_company=True)}",
            }
        )
    return links


def build_competitor_profile(
    identifier: str,
    *,
    data_dir: Path,
    entities: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
    published: list[dict[str, Any]] | None = None,
    inbox_dir: Path | None = None,
    days: int = 90,
    today: date | None = None,
) -> dict[str, Any] | None:
    """The one reusable profile view model. `identifier` may be a
    canonical_entity_id or the original spreadsheet_label -- both resolve
    to the same row. Returns None only if `identifier` matches no roster
    row at all (never for a roster row whose entity happens to be
    unresolved -- that is itself represented honestly in the identity
    block, per this mission's non-company-support requirement)."""
    matrix = load_reconciliation_matrix(data_dir)
    if matrix is None:
        return None
    row = next(
        (
            r for r in matrix["rows"]
            if r["canonical_entity_id"] == identifier or r["spreadsheet_label"] == identifier
        ),
        None,
    )
    if row is None:
        return None

    entities_by_id = _entities_by_id(entities)
    entity = entities_by_id.get(row["canonical_entity_id"])
    published = published or []
    inbox_dir = inbox_dir or (Path(data_dir).parent / "inbox")

    maturity = monitoring_maturity_for_entity(
        entity, sources=sources, published=published, inbox_dir=inbox_dir, days=days, today=today,
    )
    genetics = _genetics_block(entity, relationships=relationships, entities=entities)
    variety_roles = _verified_variety_relationships(entity, relationships=relationships, entities=entities)
    parent_brand = _parent_brand_relationships(entity, relationships=relationships, entities_by_id=entities_by_id)

    monitoring_state = {
        "linked_to_runnable_source": maturity["discovery_operational"],
        "source_configured_never_run": maturity["discovery_configured"] and not maturity["discovery_operational"],
    }
    resolved_monitoring_state = row.get("monitoring_state") or row.get("source_execution_state") or "no_supported_source"

    aliases = list(dict.fromkeys((entity.get("aliases") or []) if entity else []))

    profile: dict[str, Any] = {
        "canonical_entity_id": row["canonical_entity_id"],
        "display_name": (entity.get("name") if entity else None) or row["canonical_display_name"],
        "spreadsheet_label": row["spreadsheet_label"],
        "aliases": aliases,
        "entity_type": (entity.get("entity_type") if entity else row.get("entity_type")) or "company",
        "identity": _identity_block(entity, row),
        "classification": {
            "competitor_type": row.get("competitor_type"),
            "strategic_priority": row.get("strategic_priority"),
            "regions": row.get("regions") or [],
            "berry_tier": row.get("berry_tier") or {},
            "snapshot_date": row.get("snapshot_date") or matrix.get("snapshot_date"),
            "provenance": row.get("provenance"),
            "note": "Internal, user-curated classification from the competitor-registry spreadsheet snapshot -- "
                    "never independently verified market research, and never modified by this service.",
        },
        "parent_brand_relationships": parent_brand,
        "genetics": {
            **genetics,
            "note": "Provider-level, company<->company/program associations only -- distinct from verified "
                    "Variety relationships below. status='disputed' means pending human review, not that the "
                    "parties disagree; status='active' means externally corroborated.",
        },
        "verified_variety_relationships": {
            "roles": variety_roles,
            "note": "Real, already-trusted Company/Brand/Program-to-Variety relationships (owns/develops/"
                    "licenses/markets/grows/distributes) -- distinct from the pending genetics-provider "
                    "assertions above. Empty for most of this roster; this service creates none.",
        },
        "monitoring": {
            "maturity": maturity,
            "resolved_state": resolved_monitoring_state,
            "detail": row.get("monitoring_detail") or row.get("source_execution_detail") or "",
        },
        "profile_url": _profile_url_for(entity, fallback_id=row["canonical_entity_id"], entry_route=row.get("entity_route")),
        "filtered_landscape_urls": _filtered_landscape_urls(row, entity_id=row["canonical_entity_id"]),
    }

    landscape_adapter_row = selected_company_detail(
        [
            {
                **row,
                "entity_id": row["canonical_entity_id"],
                "registry_label": row["spreadsheet_label"],
                "canonical_or_pending_state": "pending" if entity is None else "canonical",
                "competitor_types": [t.strip() for t in (row.get("competitor_type") or "").split(";") if t.strip()],
                "berry_positions": row.get("berry_tier") or {},
                "monitoring_maturity": maturity,
                "recent_usable_coverage_count": maturity.get("current_usable_coverage_count", 0),
            }
        ],
        row["canonical_entity_id"],
        berry="blueberry",
    )
    profile["unresolved_data_gaps"] = (landscape_adapter_row or {}).get("data_gaps") or []
    profile["completeness"] = profile_completeness(profile)
    return profile
