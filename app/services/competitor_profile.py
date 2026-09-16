"""Competitor Profile Data Service V1 -- refined completeness semantics.

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
     LandscapeFilters/filters_to_query/normalize_tier_status/normalize_priority`
     for the same per-row gap detection, display-label normalization, and
     filtered-landscape-URL construction the `/competitors` page itself
     uses -- a profile's "unresolved data gaps" and "filtered landscape
     URLs" fields must never drift from what that page already shows for
     the same entity.
  - `company_workspace._company_portfolio_roles` for VERIFIED Variety
     relationships (the existing owns/develops/licenses/markets/grows/
     distributes role-bucket walk) -- deliberately never confused with the
     separate, pending, provider-level genetics assertions above.
  - `entity_identity.load_identity_redirects/redirect_map/is_retired_entity/
     merged_into_id/audit_entity_identity` for the same duplicate-resolution
     and identity-integrity mechanism every other identity-aware service in
     this codebase already reads -- a profile never invents its own notion
     of "this canonical id is bad".

Every field this module returns is traceable to one of those pre-existing,
already-tested services. Nothing here performs new web research, writes
canonical data, or activates a Source.

--- Completeness semantics (Refine Profile Completeness Semantics V1) ---

The old model collapsed everything into 10 present/missing/not_applicable
dimensions and one misleading "0/33 complete" framing. That conflated
seven materially different concerns:

  1. Record integrity      -- is the profile itself structurally sound?
  2. Classification coverage -- what do we know about berries/priority/
     regions/competitor type, independently, never inferring one from
     another?
  3. Identity verification  -- how sure are we WHO this entity is?
  4. Relationship knowledge -- do we know this entity's genetics/parent-
     brand/variety relationships, or is that simply not yet known?
  5. Monitoring maturity    -- is discovery SET UP for this entity?
  6. Current intelligence coverage -- do we currently HAVE usable
     acquired content, independent of whether discovery is set up?
  7. Actionable gaps        -- a structured, triaged list of everything
     above that is not fully resolved, each tagged with whether it
     actually blocks stakeholder display.

None of concerns 2-6 can fail concern 1. An Unknown/Unassigned berry slot,
an unassigned strategic priority, a provisional (`unverified`) identity, an
unconfigured source, or zero current coverage are all real, honestly
reported states -- never record defects. Only a genuine structural problem
(a required field literally absent, or a reference that points at nothing/
something retired) marks a profile `missing_required_data` or
`invalid_reference`, and only those two states ever set
`blocks_stakeholder_display=True` on an actionable gap.

Vocabulary is reused wherever the repository already has it (entity
`status` enum for identity settlement; `competitor_landscape`'s own
`TIER_STATUS_VALUES`/`PRIORITY_VALUES` display labels for classification)
and invented only where nothing already represents the concept (record
integrity's own 3-value outcome; the 8-value `FIELD_STATES` generic
coverage vocabulary; the actionable-gap category/severity taxonomy).
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
    normalize_priority,
    normalize_tier_status,
    selected_company_detail,
)
from app.services.competitor_registry import (
    companies_for_genetics_provider,
    genetics_relationships_for_company,
    load_reconciliation_matrix,
    monitoring_maturity_for_entity,
)
from app.services.entity_identity import (
    audit_entity_identity,
    is_retired_entity,
    load_identity_redirects,
    merged_into_id,
    redirect_map,
)

BERRIES = ("strawberry", "blueberry", "raspberry", "blackberry")

# --- Record integrity: is the profile itself structurally sound? ----------
# A small, new 3-value outcome -- nothing in the repository already models
# "is this record's own shape sound", as opposed to the entity `status`
# enum, which governs entity *lifecycle* (active/inactive/historical/
# unverified), not record shape.
INTEGRITY_VALID = "structurally_valid"
INTEGRITY_MISSING_REQUIRED = "missing_required_data"
INTEGRITY_INVALID_REFERENCE = "invalid_reference"
INTEGRITY_STATES = (INTEGRITY_VALID, INTEGRITY_MISSING_REQUIRED, INTEGRITY_INVALID_REFERENCE)

# --- Identity verification: reuses the entity schema's own `status` enum
# wherever it already answers the question; adds only the two concepts that
# enum cannot express -- a still-open duplicate/structural review, and a
# canonical reference that resolves to nothing or to a retired/merged
# record instead of its living survivor.
IDENTITY_VERIFIED = "active_verified"
IDENTITY_PROVISIONAL = "provisional"
IDENTITY_PENDING_REVIEW = "pending_duplicate_review"
IDENTITY_INVALID_REFERENCE = "invalid_canonical_reference"
IDENTITY_VERIFICATION_STATES = (
    IDENTITY_VERIFIED, IDENTITY_PROVISIONAL, IDENTITY_PENDING_REVIEW, IDENTITY_INVALID_REFERENCE,
)

# --- Generic field-coverage vocabulary, reused across classification
# coverage, identity, relationship knowledge, and monitoring so a caller
# never has to learn a different small enum per dimension. Equivalent to
# the mission's own "known/assigned; unknown/unassigned; explicitly not
# applicable; pending verification; unsupported for this entity type;
# absent optional information; missing required data; invalid or
# inconsistent data".
FIELD_ASSIGNED = "assigned"
FIELD_UNKNOWN_UNASSIGNED = "unknown_unassigned"
FIELD_NOT_APPLICABLE = "not_applicable"
FIELD_PENDING_VERIFICATION = "pending_verification"
FIELD_UNSUPPORTED_FOR_ENTITY_TYPE = "unsupported_for_entity_type"
FIELD_ABSENT_OPTIONAL = "absent_optional"
FIELD_MISSING_REQUIRED = "missing_required"
FIELD_INVALID_OR_INCONSISTENT = "invalid_or_inconsistent"
FIELD_STATES = (
    FIELD_ASSIGNED, FIELD_UNKNOWN_UNASSIGNED, FIELD_NOT_APPLICABLE, FIELD_PENDING_VERIFICATION,
    FIELD_UNSUPPORTED_FOR_ENTITY_TYPE, FIELD_ABSENT_OPTIONAL, FIELD_MISSING_REQUIRED,
    FIELD_INVALID_OR_INCONSISTENT,
)

# --- Actionable-gap categories: distinguishes informational uncertainty
# from real analyst/ops/engineering work, per the mission's own list.
GAP_INFORMATIONAL = "informational_uncertainty"
GAP_ANALYST_CLASSIFICATION = "analyst_classification_work"
GAP_IDENTITY_VERIFICATION = "identity_verification"
GAP_SOURCE_CONFIGURATION = "source_configuration"
GAP_ACQUISITION_FAILURE = "acquisition_failure"
GAP_MISSING_REQUIRED_DATA = "missing_required_data"
GAP_INVALID_DATA = "invalid_data"
GAP_CATEGORIES = (
    GAP_INFORMATIONAL, GAP_ANALYST_CLASSIFICATION, GAP_IDENTITY_VERIFICATION, GAP_SOURCE_CONFIGURATION,
    GAP_ACQUISITION_FAILURE, GAP_MISSING_REQUIRED_DATA, GAP_INVALID_DATA,
)

GAP_SEVERITY_BLOCKING = "blocking"
GAP_SEVERITY_ATTENTION = "attention"
GAP_SEVERITY_INFORMATIONAL = "informational"
GAP_SEVERITIES = (GAP_SEVERITY_BLOCKING, GAP_SEVERITY_ATTENTION, GAP_SEVERITY_INFORMATIONAL)


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


def _identity_verification_state(
    entity: dict[str, Any] | None,
    *,
    redirects_map: dict[str, str],
    audit_issues: list[dict[str, Any]],
) -> tuple[str, str]:
    """The identity-verification state machine, kept entirely separate from
    record integrity: a provisional or pending-review identity is a
    verification gap, never automatically a malformed profile. Only an
    entity that fails to resolve at all, or resolves to a retired/merged
    record instead of its living survivor, is `invalid_canonical_reference`
    -- and that state is ALSO what makes `_record_integrity` below mark the
    profile `invalid_reference`, so the two never disagree about the same
    underlying fact."""
    if entity is None:
        return IDENTITY_INVALID_REFERENCE, (
            "canonical_entity_id on this roster row does not resolve to any entity record."
        )
    entity_id = str(entity.get("id") or "")
    if is_retired_entity(entity, redirects=redirects_map):
        survivor = redirects_map.get(entity_id) or merged_into_id(entity)
        return IDENTITY_INVALID_REFERENCE, (
            f"canonical_entity_id resolves to a retired/merged record; the surviving record is "
            f"{survivor!r} (see data/configuration/entity-identity-redirects.json)."
        )
    for issue in audit_issues:
        if entity_id not in (issue.get("entity_ids") or []):
            continue
        if issue.get("reason") == "explicit_redirect":
            continue  # already decided via a recorded redirect -- not an open review
        return IDENTITY_PENDING_REVIEW, (
            f"app.services.entity_identity.audit_entity_identity flagged an unresolved "
            f"'{issue.get('reason')}' ({issue.get('state')}) against this identity."
        )
    if entity.get("status") == "unverified":
        return IDENTITY_PROVISIONAL, (
            "entity status is 'unverified' -- identity not yet independently confirmed. A provisional "
            "identity is a verification gap, not a malformed profile."
        )
    return IDENTITY_VERIFIED, (
        f"entity status is settled ('{entity.get('status')}') with no open duplicate/structural review."
    )


def _identity_block(
    entity: dict[str, Any] | None,
    row: dict[str, Any],
    *,
    redirects_map: dict[str, str],
    audit_issues: list[dict[str, Any]],
) -> dict[str, Any]:
    """Identity status, confidence, and provenance -- kept entirely
    separate from internal classification and from monitoring/coverage.
    Reads `attributes.identity_verification_<date>` when Competitor
    Identity and Genetics Verification V1 recorded one (any dated key --
    a future re-verification adds a new dated block, never overwrites);
    falls back to the reconciliation matrix's own resolution_status for an
    entity that has not yet had a dedicated identity-verification pass.

    `verification_state`/`verification_state_reason` are the refined,
    4-value identity-verification concern (active_verified/provisional/
    pending_duplicate_review/invalid_canonical_reference) -- see
    `_identity_verification_state`."""
    verification_state, verification_reason = _identity_verification_state(
        entity, redirects_map=redirects_map, audit_issues=audit_issues
    )
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
            "verification_state": verification_state,
            "verification_state_reason": verification_reason,
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
            "verification_state": verification_state,
            "verification_state_reason": verification_reason,
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
        "verification_state": verification_state,
        "verification_state_reason": verification_reason,
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


def _dangling_relationship_refs(profile: dict[str, Any], *, entities_by_id: dict[str, dict[str, Any]]) -> list[str]:
    """Reference-integrity check for the relationship edges this profile
    surfaces. `_parent_brand_relationships` and `_verified_variety_relationships`
    already skip an edge whose other side does not resolve (by construction
    of their own lookups), so only the genetics walk -- which passes
    `other_entity_id` through even when the entity is unresolved -- can
    actually produce a dangling reference here."""
    dangling: list[str] = []
    for entry in (*profile["genetics"]["as_company"], *profile["genetics"]["as_provider"]):
        other_id = entry.get("other_entity_id")
        if other_id and str(other_id) not in entities_by_id:
            dangling.append(str(other_id))
    return dangling


def _record_integrity(profile: dict[str, Any], *, entities_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Concern 1: is this profile itself structurally sound? Deliberately
    blind to classification/identity/monitoring content -- a berry slot
    holding Unknown/Unassigned still counts as structurally present, an
    unassigned strategic priority is not a malformed record, a provisional
    identity is not a malformed record, and no current coverage is not a
    malformed record. Only a literally-absent required field or a
    dangling/retired reference fails a check here."""
    identity = profile["identity"]
    berry_tier = profile["classification"]["berry_tier"]
    dangling_refs = _dangling_relationship_refs(profile, entities_by_id=entities_by_id)

    checks = [
        {
            "check": "canonical_entity_id_present",
            "passed": bool(profile["canonical_entity_id"]),
            "category": INTEGRITY_MISSING_REQUIRED,
            "detail": "The roster row must carry a non-empty canonical_entity_id.",
        },
        {
            "check": "display_name_present",
            "passed": bool(profile["display_name"]),
            "category": INTEGRITY_MISSING_REQUIRED,
            "detail": "A profile must have a non-empty display name.",
        },
        {
            "check": "entity_type_present",
            "passed": bool(profile["entity_type"]),
            "category": INTEGRITY_MISSING_REQUIRED,
            "detail": "A profile must declare its entity_type.",
        },
        {
            "check": "roster_resolves_to_entity",
            "passed": bool(identity["entity_found"]),
            "category": INTEGRITY_INVALID_REFERENCE,
            "detail": "canonical_entity_id must resolve to an existing entity record.",
        },
        {
            "check": "canonical_reference_not_retired",
            "passed": (not identity["entity_found"]) or identity["verification_state"] != IDENTITY_INVALID_REFERENCE,
            "category": INTEGRITY_INVALID_REFERENCE,
            "detail": "canonical_entity_id must point at a living record, not a retired/merged duplicate.",
        },
        {
            "check": "all_four_berry_slots_present",
            "passed": all(berry in berry_tier for berry in BERRIES),
            "category": INTEGRITY_MISSING_REQUIRED,
            "detail": (
                "All four berry-position slots (strawberry/blueberry/raspberry/blackberry) must be present "
                "as keys, regardless of value -- Unknown/Unassigned still counts as structurally present."
            ),
        },
        {
            "check": "classification_snapshot_valid",
            "passed": bool(profile["classification"]["snapshot_date"]) and bool(profile["classification"]["provenance"]),
            "category": INTEGRITY_MISSING_REQUIRED,
            "detail": "Classification must trace to a dated, provenanced snapshot.",
        },
        {
            "check": "relationship_references_valid",
            "passed": not dangling_refs,
            "category": INTEGRITY_INVALID_REFERENCE,
            "detail": (
                "Every relationship this profile surfaces must point at an entity id that actually exists."
                + (f" Dangling reference(s): {', '.join(dangling_refs)}." if dangling_refs else "")
            ),
        },
        {
            "check": "profile_route_present",
            "passed": bool(profile["profile_url"]),
            "category": INTEGRITY_MISSING_REQUIRED,
            "detail": "A profile must resolve to a non-empty profile_url.",
        },
        {
            "check": "filtered_landscape_routes_present",
            "passed": all(link.get("href") for link in profile["filtered_landscape_urls"]),
            "category": INTEGRITY_MISSING_REQUIRED,
            "detail": "Every berry's filtered-landscape link must be non-empty.",
        },
    ]

    failed = [c for c in checks if not c["passed"]]
    if any(c["category"] == INTEGRITY_INVALID_REFERENCE for c in failed):
        status = INTEGRITY_INVALID_REFERENCE
    elif any(c["category"] == INTEGRITY_MISSING_REQUIRED for c in failed):
        status = INTEGRITY_MISSING_REQUIRED
    else:
        status = INTEGRITY_VALID
    return {
        "status": status,
        "checks": checks,
        "failed_checks": failed,
        "note": (
            "Structural validity only. An Unknown/Unassigned berry slot, an unassigned strategic priority, "
            "a provisional identity, or a monitoring/coverage gap NEVER fails a check here -- those are "
            "separate concerns reported elsewhere on this profile (classification_coverage, "
            "identity_verification, monitoring_maturity, current_intelligence_coverage)."
        ),
    }


def _classification_coverage(classification: dict[str, Any]) -> dict[str, Any]:
    """Concern 2: berry positions, strategic priority, regions, and
    competitor type reported independently -- never one berry inferred
    from another, and Unknown/Unassigned kept structurally distinct from
    Not Applicable via `competitor_landscape.normalize_tier_status`, the
    same normalizer the `/competitors` page itself uses."""
    berry_tier = classification["berry_tier"] or {}
    berries: dict[str, dict[str, Any]] = {}
    for berry in BERRIES:
        raw = berry_tier.get(berry)
        display = normalize_tier_status(raw)
        if display == "Not Applicable":
            state = FIELD_NOT_APPLICABLE
        elif display == "Unknown/Unassigned":
            state = FIELD_UNKNOWN_UNASSIGNED
        else:
            state = FIELD_ASSIGNED
        berries[berry] = {"raw": raw, "display": display, "state": state}

    priority_raw = classification["strategic_priority"]
    priority_display = normalize_priority(priority_raw)
    priority = {
        "raw": priority_raw,
        "display": priority_display,
        "state": FIELD_UNKNOWN_UNASSIGNED if priority_display == "unassigned" else FIELD_ASSIGNED,
    }

    regions_assigned = list(classification["regions"] or [])
    regions = {
        "assigned": regions_assigned,
        "state": FIELD_ASSIGNED if regions_assigned else FIELD_UNKNOWN_UNASSIGNED,
    }

    types_assigned = [t.strip() for t in (classification["competitor_type"] or "").split(";") if t.strip()]
    competitor_types = {
        "assigned": types_assigned,
        "state": FIELD_ASSIGNED if types_assigned else FIELD_UNKNOWN_UNASSIGNED,
    }

    berry_states = [b["state"] for b in berries.values()]
    has_unassigned = (
        FIELD_UNKNOWN_UNASSIGNED in berry_states
        or priority["state"] == FIELD_UNKNOWN_UNASSIGNED
        or regions["state"] == FIELD_UNKNOWN_UNASSIGNED
        or competitor_types["state"] == FIELD_UNKNOWN_UNASSIGNED
    )
    return {
        "berry_positions": berries,
        "berry_summary": {
            "assigned": berry_states.count(FIELD_ASSIGNED),
            "unknown_unassigned": berry_states.count(FIELD_UNKNOWN_UNASSIGNED),
            "not_applicable": berry_states.count(FIELD_NOT_APPLICABLE),
        },
        "strategic_priority": priority,
        "regions": regions,
        "competitor_types": competitor_types,
        "has_unassigned": has_unassigned,
        "note": (
            "Each berry position, strategic priority, region set, and competitor-type set is reported "
            "independently -- one is never inferred from another. Unknown/Unassigned and Not Applicable "
            "are kept structurally distinct via competitor_landscape.normalize_tier_status."
        ),
    }


def _relationship_knowledge(profile: dict[str, Any]) -> dict[str, Any]:
    """Concern 4: do we know this entity's genetics/parent-brand/variety
    relationships, or is that simply not yet known? Absence here is
    `absent_optional` -- optional information not yet recorded -- never a
    record defect, since none of these relationships is required for a
    profile to be structurally valid."""
    genetics = profile["genetics"]
    genetics_known = bool(genetics["as_company"] or genetics["as_provider"])
    variety_roles = profile["verified_variety_relationships"]["roles"]
    variety_relationships_known = any(bool(parties) for parties in variety_roles.values())
    parent_brand_known = bool(profile["parent_brand_relationships"])
    return {
        "genetics_known": genetics_known,
        "genetics_state": FIELD_ASSIGNED if genetics_known else FIELD_ABSENT_OPTIONAL,
        "verified_variety_relationships_known": variety_relationships_known,
        "verified_variety_relationships_state": (
            FIELD_ASSIGNED if variety_relationships_known else FIELD_ABSENT_OPTIONAL
        ),
        "parent_brand_relationships_known": parent_brand_known,
        "parent_brand_relationships_state": FIELD_ASSIGNED if parent_brand_known else FIELD_ABSENT_OPTIONAL,
        "note": (
            "Genetics, verified-variety, and parent/brand relationships are recorded only when a real "
            "Relationship already exists in the graph. Absence here means not yet known -- an optional, "
            "informational gap, never a structural defect."
        ),
    }


def _monitoring_maturity_concern(maturity: dict[str, Any]) -> dict[str, Any]:
    """Concern 5: is discovery SET UP for this entity? Deliberately blind
    to whether current news actually exists -- see
    `_current_intelligence_coverage_concern` for that separate question."""
    configured = bool(maturity.get("discovery_configured"))
    operational = bool(maturity.get("discovery_operational"))
    return {
        "entity_represented": bool(maturity.get("entity_represented")),
        "discovery_configured": configured,
        "discovery_operational": operational,
        "linked_source_count": maturity.get("linked_source_count", 0),
        "runnable_source_count": maturity.get("runnable_source_count", 0),
        "state": (
            "configured_and_operational" if operational
            else "configured_not_operational" if configured
            else FIELD_ABSENT_OPTIONAL
        ),
        "note": (
            "Whether monitoring is SET UP for this entity -- never whether current news exists right now. "
            "No configured source is an operational gap, never a profile-schema failure."
        ),
    }


def _current_intelligence_coverage_concern(maturity: dict[str, Any]) -> dict[str, Any]:
    """Concern 6: do we currently HAVE usable acquired content, independent
    of whether discovery is set up? A blocked official source or zero
    current coverage is an operational intelligence gap, never a
    profile-schema failure."""
    readable = bool(maturity.get("readable_content_acquired"))
    current = bool(maturity.get("current_coverage_available"))
    return {
        "readable_content_acquired": readable,
        "current_coverage_available": current,
        "current_usable_coverage_count": maturity.get("current_usable_coverage_count", 0),
        "official_source_blocked": bool(maturity.get("official_source_blocked")),
        "official_source_block_detail": maturity.get("official_source_block_detail") or "",
        "manual_or_alternative_source_required": bool(maturity.get("manual_or_alternative_source_required")),
        "state": (
            "current" if current
            else "readable_but_not_current" if readable
            else FIELD_ABSENT_OPTIONAL
        ),
        "note": (
            "Whether we currently HAVE usable intelligence for this entity -- an operational acquisition/"
            "coverage gap when absent, never a profile-schema failure."
        ),
    }


def _gap(
    *, dimension: str, state: str, category: str, severity: str, why_it_matters: str,
    recommended_next_action: str, owning_workflow: str, source_provenance: str,
) -> dict[str, Any]:
    return {
        "dimension": dimension,
        "state": state,
        "category": category,
        "severity": severity,
        "why_it_matters": why_it_matters,
        "recommended_next_action": recommended_next_action,
        "owning_workflow": owning_workflow,
        "source_provenance": source_provenance,
        "blocks_stakeholder_display": severity == GAP_SEVERITY_BLOCKING,
    }


def _actionable_gaps(
    *,
    integrity: dict[str, Any],
    identity: dict[str, Any],
    classification_coverage: dict[str, Any],
    relationship_knowledge: dict[str, Any],
    monitoring_concern: dict[str, Any],
    coverage_concern: dict[str, Any],
    provenance: str,
) -> list[dict[str, Any]]:
    """Concern 7: a structured, triaged gap list. Only genuine record-
    integrity failures ever set `blocks_stakeholder_display=True` -- every
    other gap (Unknown/Unassigned classification, provisional identity,
    unconfigured monitoring, no current coverage) is real and reported, but
    never blocks rendering."""
    gaps: list[dict[str, Any]] = []

    for check in integrity["failed_checks"]:
        blocking_category = GAP_INVALID_DATA if check["category"] == INTEGRITY_INVALID_REFERENCE else GAP_MISSING_REQUIRED_DATA
        state = FIELD_INVALID_OR_INCONSISTENT if check["category"] == INTEGRITY_INVALID_REFERENCE else FIELD_MISSING_REQUIRED
        gaps.append(_gap(
            dimension=f"record_integrity:{check['check']}",
            state=state,
            category=blocking_category,
            severity=GAP_SEVERITY_BLOCKING,
            why_it_matters="A structurally unsound profile cannot be trusted for stakeholder display.",
            recommended_next_action=check["detail"],
            owning_workflow="Record data-quality fix",
            source_provenance="app.services.competitor_profile._record_integrity",
        ))

    if identity["verification_state"] == IDENTITY_PROVISIONAL:
        gaps.append(_gap(
            dimension="identity",
            state=FIELD_PENDING_VERIFICATION,
            category=GAP_IDENTITY_VERIFICATION,
            severity=GAP_SEVERITY_ATTENTION,
            why_it_matters="Stakeholders should know this identity has not been independently confirmed yet.",
            recommended_next_action="Run a dedicated identity-verification pass and record evidence_urls/confidence.",
            owning_workflow="Identity verification pass",
            source_provenance="entity.status == 'unverified'",
        ))
    elif identity["verification_state"] == IDENTITY_PENDING_REVIEW:
        gaps.append(_gap(
            dimension="identity",
            state=FIELD_PENDING_VERIFICATION,
            category=GAP_IDENTITY_VERIFICATION,
            severity=GAP_SEVERITY_ATTENTION,
            why_it_matters="An open duplicate/structural-review finding means this identity may need to merge or split.",
            recommended_next_action="Resolve the flagged entity_identity audit finding (merge, redirect, or dismiss).",
            owning_workflow="Identity verification pass",
            source_provenance="app.services.entity_identity.audit_entity_identity",
        ))

    for berry, block in classification_coverage["berry_positions"].items():
        if block["state"] == FIELD_UNKNOWN_UNASSIGNED:
            gaps.append(_gap(
                dimension=f"berry_position:{berry}",
                state=FIELD_UNKNOWN_UNASSIGNED,
                category=GAP_INFORMATIONAL,
                severity=GAP_SEVERITY_INFORMATIONAL,
                why_it_matters=f"{berry.title()} tier is legitimately unclassified -- visible uncertainty, not a defect.",
                recommended_next_action=f"An analyst may classify {berry} tier from the source spreadsheet when known.",
                owning_workflow="Analyst classification pass",
                source_provenance=provenance,
            ))
    if classification_coverage["strategic_priority"]["state"] == FIELD_UNKNOWN_UNASSIGNED:
        gaps.append(_gap(
            dimension="strategic_priority",
            state=FIELD_UNKNOWN_UNASSIGNED,
            category=GAP_ANALYST_CLASSIFICATION,
            severity=GAP_SEVERITY_ATTENTION,
            why_it_matters="An unassigned strategic priority limits stakeholder prioritization views.",
            recommended_next_action="An analyst may assign Top/Watch priority from internal strategy review.",
            owning_workflow="Analyst classification pass",
            source_provenance=provenance,
        ))
    if classification_coverage["regions"]["state"] == FIELD_UNKNOWN_UNASSIGNED:
        gaps.append(_gap(
            dimension="regions",
            state=FIELD_UNKNOWN_UNASSIGNED,
            category=GAP_ANALYST_CLASSIFICATION,
            severity=GAP_SEVERITY_ATTENTION,
            why_it_matters="No region assignment limits regional filtering/reporting for this competitor.",
            recommended_next_action="An analyst may assign region code(s) from internal classification.",
            owning_workflow="Analyst classification pass",
            source_provenance=provenance,
        ))
    if classification_coverage["competitor_types"]["state"] == FIELD_UNKNOWN_UNASSIGNED:
        gaps.append(_gap(
            dimension="competitor_types",
            state=FIELD_UNKNOWN_UNASSIGNED,
            category=GAP_ANALYST_CLASSIFICATION,
            severity=GAP_SEVERITY_ATTENTION,
            why_it_matters="No competitor-type assignment limits type-based filtering/reporting for this competitor.",
            recommended_next_action="An analyst may assign competitor type(s) from internal classification.",
            owning_workflow="Analyst classification pass",
            source_provenance=provenance,
        ))

    if not relationship_knowledge["genetics_known"]:
        gaps.append(_gap(
            dimension="genetics",
            state=FIELD_ABSENT_OPTIONAL,
            category=GAP_INFORMATIONAL,
            severity=GAP_SEVERITY_INFORMATIONAL,
            why_it_matters="No genetics-provider relationship is recorded for this entity yet.",
            recommended_next_action="Record a genetics Relationship if/when supporting evidence is found.",
            owning_workflow="Analyst classification pass",
            source_provenance="app.services.competitor_registry.genetics_relationships_for_company",
        ))

    if not monitoring_concern["discovery_configured"]:
        gaps.append(_gap(
            dimension="source_configuration",
            state=FIELD_ABSENT_OPTIONAL,
            category=GAP_SOURCE_CONFIGURATION,
            severity=GAP_SEVERITY_ATTENTION,
            why_it_matters="No runnable Source is linked, so this entity is not being monitored at all.",
            recommended_next_action="Link and configure a discovery-eligible Source for this entity.",
            owning_workflow="Source configuration",
            source_provenance="app.services.competitor_registry.monitoring_maturity_for_entity",
        ))
    elif not monitoring_concern["discovery_operational"]:
        gaps.append(_gap(
            dimension="operational_discovery",
            state=FIELD_ABSENT_OPTIONAL,
            category=GAP_SOURCE_CONFIGURATION,
            severity=GAP_SEVERITY_ATTENTION,
            why_it_matters="A Source is linked but has never completed a successful discovery run.",
            recommended_next_action="Run or debug the linked Source's discovery adapter.",
            owning_workflow="Source configuration",
            source_provenance="app.services.competitor_registry.monitoring_maturity_for_entity",
        ))

    if coverage_concern["official_source_blocked"]:
        gaps.append(_gap(
            dimension="current_intelligence_coverage",
            state=FIELD_ABSENT_OPTIONAL,
            category=GAP_ACQUISITION_FAILURE,
            severity=GAP_SEVERITY_ATTENTION,
            why_it_matters=coverage_concern["official_source_block_detail"] or "Official source acquisition is blocked.",
            recommended_next_action="Pursue a compliant alternative/manual acquisition path.",
            owning_workflow="Acquisition / collection pipeline",
            source_provenance="app.services.competitor_registry._KNOWN_BLOCKED_ENTITIES",
        ))
    elif not coverage_concern["readable_content_acquired"] and monitoring_concern["discovery_operational"]:
        gaps.append(_gap(
            dimension="current_intelligence_coverage",
            state=FIELD_ABSENT_OPTIONAL,
            category=GAP_ACQUISITION_FAILURE,
            severity=GAP_SEVERITY_ATTENTION,
            why_it_matters="Discovery has run but no readable article body has been acquired yet.",
            recommended_next_action="Investigate article-body acquisition for this entity's linked source(s).",
            owning_workflow="Acquisition / collection pipeline",
            source_provenance="app.services.competitor_registry.monitoring_maturity_for_entity",
        ))
    if not coverage_concern["current_coverage_available"]:
        gaps.append(_gap(
            dimension="current_intelligence_coverage",
            state=FIELD_ABSENT_OPTIONAL,
            category=GAP_ACQUISITION_FAILURE,
            severity=GAP_SEVERITY_INFORMATIONAL,
            why_it_matters="No current usable coverage window is available for this entity right now.",
            recommended_next_action="No action required unless monitoring is also unconfigured -- see that gap.",
            owning_workflow="Acquisition / collection pipeline",
            source_provenance="app.services.competitor_registry.monitoring_maturity_for_entity",
        ))

    return gaps


def _ui_flags(
    *, integrity: dict[str, Any], identity: dict[str, Any], classification_coverage: dict[str, Any],
    monitoring_concern: dict[str, Any], coverage_concern: dict[str, Any], gaps: list[dict[str, Any]],
) -> dict[str, Any]:
    """Concise, UI-ready booleans for a future drill-down surface. Data
    only -- no UI/route/template is built or modified by this mission."""
    return {
        "profile_structurally_valid": integrity["status"] == INTEGRITY_VALID,
        "classification_incomplete_or_unassigned": classification_coverage["has_unassigned"],
        "identity_provisional": identity["verification_state"] in (IDENTITY_PROVISIONAL, IDENTITY_PENDING_REVIEW),
        "monitoring_not_configured": not monitoring_concern["discovery_configured"],
        "coverage_unavailable": not coverage_concern["current_coverage_available"],
        "action_required": any(g["severity"] in (GAP_SEVERITY_BLOCKING, GAP_SEVERITY_ATTENTION) for g in gaps),
    }


def profile_completeness(
    profile: dict[str, Any], *, entities_by_id: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """The refined, 7-concern completeness report -- never a single
    blended score. `entities_by_id` is required to check reference
    integrity for relationships this profile surfaces; callers that only
    need the older shape for a synthetic/partial profile may omit it (an
    empty map is used, which only affects the `relationship_references_valid`
    check)."""
    entities_by_id = entities_by_id or {}
    identity = profile["identity"]
    classification_coverage = _classification_coverage(profile["classification"])
    relationship_knowledge = _relationship_knowledge(profile)
    maturity = profile["monitoring"]["maturity"]
    monitoring_concern = _monitoring_maturity_concern(maturity)
    coverage_concern = _current_intelligence_coverage_concern(maturity)
    integrity = _record_integrity(profile, entities_by_id=entities_by_id)
    provenance = profile["classification"].get("provenance") or "internal_competitor_registry_spreadsheet"
    gaps = _actionable_gaps(
        integrity=integrity,
        identity=identity,
        classification_coverage=classification_coverage,
        relationship_knowledge=relationship_knowledge,
        monitoring_concern=monitoring_concern,
        coverage_concern=coverage_concern,
        provenance=provenance,
    )
    ui_flags = _ui_flags(
        integrity=integrity, identity=identity, classification_coverage=classification_coverage,
        monitoring_concern=monitoring_concern, coverage_concern=coverage_concern, gaps=gaps,
    )
    identity_verification = {
        "state": identity["verification_state"],
        "reason": identity["verification_state_reason"],
    }
    return {
        "record_integrity": integrity,
        "classification_coverage": classification_coverage,
        "identity_verification": identity_verification,
        "relationship_knowledge": relationship_knowledge,
        "monitoring_maturity": monitoring_concern,
        "current_intelligence_coverage": coverage_concern,
        "actionable_gaps": gaps,
        "ui_flags": ui_flags,
        "note": (
            "Seven separated concerns -- record integrity, classification coverage, identity verification, "
            "relationship knowledge, monitoring maturity, current intelligence coverage, and actionable "
            "gaps -- never collapsed into one invented completeness score. Unknown/Unassigned "
            "classifications, provisional identities, and monitoring/coverage gaps are counted honestly "
            "but never treated as record defects; only record_integrity.status != 'structurally_valid' "
            "represents a genuine, blocking structural problem."
        ),
    }


def profile_roster_summary(profiles: list[dict[str, Any]]) -> dict[str, Any]:
    """A multidimensional summary across the full roster, replacing the old
    single, misleading "Complete profiles: N/33" metric. Deliberately never
    collapsed into one opaque percentage."""
    def count(predicate) -> int:
        return sum(1 for profile in profiles if predicate(profile))

    return {
        "profiles_returned": len(profiles),
        "structurally_valid": count(lambda p: p["completeness"]["record_integrity"]["status"] == INTEGRITY_VALID),
        "missing_required_data": count(
            lambda p: p["completeness"]["record_integrity"]["status"] == INTEGRITY_MISSING_REQUIRED
        ),
        "invalid_reference": count(
            lambda p: p["completeness"]["record_integrity"]["status"] == INTEGRITY_INVALID_REFERENCE
        ),
        "unassigned_internal_classification": count(
            lambda p: p["completeness"]["classification_coverage"]["has_unassigned"]
        ),
        "provisional_identity": count(
            lambda p: p["completeness"]["identity_verification"]["state"]
            in (IDENTITY_PROVISIONAL, IDENTITY_PENDING_REVIEW)
        ),
        "lacking_genetics_information": count(
            lambda p: not p["completeness"]["relationship_knowledge"]["genetics_known"]
        ),
        "no_configured_sources": count(
            lambda p: not p["completeness"]["monitoring_maturity"]["discovery_configured"]
        ),
        "no_operational_discovery": count(
            lambda p: not p["completeness"]["monitoring_maturity"]["discovery_operational"]
        ),
        "no_readable_coverage": count(
            lambda p: not p["completeness"]["current_intelligence_coverage"]["readable_content_acquired"]
        ),
        "no_current_usable_coverage": count(
            lambda p: not p["completeness"]["current_intelligence_coverage"]["current_coverage_available"]
        ),
        "blocking_profile_defects": count(
            lambda p: any(g["blocks_stakeholder_display"] for g in p["completeness"]["actionable_gaps"])
        ),
        "note": (
            "A multidimensional summary, deliberately never collapsed into one 'X/33 complete' percentage. "
            "Unknown/Unassigned classifications, provisional identities, and monitoring/coverage gaps are "
            "counted honestly here but never treated as record defects -- only missing_required_data, "
            "invalid_reference, and blocking_profile_defects represent genuine structural problems."
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

    identity_redirects = load_identity_redirects(data_dir)
    redirects_map = redirect_map(identity_redirects)
    audit_issues = audit_entity_identity(
        entities, relationships=relationships, redirects=identity_redirects
    )["companies"]["issues"]

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
        "identity": _identity_block(entity, row, redirects_map=redirects_map, audit_issues=audit_issues),
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
    profile["completeness"] = profile_completeness(profile, entities_by_id=entities_by_id)
    return profile
