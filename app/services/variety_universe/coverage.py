"""Explainable Variety coverage counts. No completeness score."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.services.variety_universe.identity import STATE_POSSIBLE_ALIAS, STATE_UNKNOWN


def universe_headcounts(
    *,
    varieties: list[dict[str, Any]],
    candidates: list[dict[str, Any]] | None = None,
) -> dict[str, int]:
    """Trusted vs discovered vs unresolved. Raw counts, no completeness score."""
    active = [row for row in (candidates or []) if row.get("status") != "rejected"]
    return {
        "trusted_varieties": len(varieties),
        "discovered_candidates": len(active),
        "unresolved_identities": sum(
            1 for row in active if row.get("identity_state") in {STATE_POSSIBLE_ALIAS, STATE_UNKNOWN}
        ),
    }


BERRY_ORDER = (
    "berry-blueberry",
    "berry-strawberry",
    "berry-raspberry",
    "berry-blackberry",
)
BERRY_LABELS = {
    "berry-blueberry": "Blueberry",
    "berry-strawberry": "Strawberry",
    "berry-raspberry": "Raspberry",
    "berry-blackberry": "Blackberry",
}
GEO_FOCUS = (
    ("eu", "EU", {"geography-europe", "EU", "eu", "CPVO", "EU (CPVO)"}),
    ("uk", "United Kingdom", {"geography-united-kingdom", "UK", "United Kingdom", "GB"}),
    ("za", "South Africa", {"geography-south-africa", "ZA", "South Africa"}),
    ("other", "Other existing regions", set()),
)
_GEO_ALIASES = {key: {alias.casefold() for alias in aliases} for key, _label, aliases in GEO_FOCUS if aliases}

ROLE_OWNERSHIP_PREDICATES = {"develops", "owns"}
ROLE_DEPLOYMENT_PREDICATES = {"grows", "markets", "sells", "trials", "licenses"}
RIGHTS_SOURCE_TYPES = {"plant_breeders_rights_record", "patent_record", "patent", "patent_aggregator"}


def _berries(record: dict[str, Any]) -> set[str]:
    berries = {str(item) for item in (record.get("berry_ids") or []) if item}
    berry = str(record.get("berry_id") or "").strip()
    if berry:
        berries.add(berry)
    return berries


def _geo_buckets(tokens: Iterable[str]) -> set[str]:
    keys = {token.casefold() for token in tokens if token}
    return {key for key, aliases in _GEO_ALIASES.items() if keys & aliases} or {"other"}


def coverage_matrix(
    *,
    varieties: list[dict[str, Any]],
    entities: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
    published_evidence: list[dict[str, Any]],
    facts: list[dict[str, Any]],
    candidates: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    candidates = [row for row in (candidates or []) if row.get("status") != "rejected"]
    entity_index = {str(e["id"]): e for e in entities if e.get("id")}
    variety_ids = {str(v["id"]) for v in varieties if v.get("id")}

    ownership_ids: set[str] = set()
    deployment_ids: set[str] = set()
    related_geos: dict[str, set[str]] = {}
    first_breeder: dict[str, str] = {}
    for rel in relationships:
        predicate = rel.get("predicate")
        subject, target = rel.get("subject_id"), rel.get("object_id")
        if target in variety_ids:
            if predicate in ROLE_OWNERSHIP_PREDICATES:
                ownership_ids.add(target)
            if predicate in ROLE_DEPLOYMENT_PREDICATES:
                deployment_ids.add(target)
            if predicate == "develops" and target not in first_breeder:
                company = entity_index.get(str(subject or ""))
                if company and company.get("entity_type") == "company":
                    first_breeder[target] = str(company.get("name") or company["id"])
            if predicate == "operates_in":
                related_geos.setdefault(target, set()).add(str(subject or ""))
        if predicate == "operates_in" and subject in variety_ids:
            related_geos.setdefault(subject, set()).add(str(target or ""))

    registration_ids: set[str] = set()
    for row in published_evidence:
        geos = {str(geo) for geo in (row.get("geography_ids") or []) if geo}
        rights_source = row.get("source_type") in RIGHTS_SOURCE_TYPES
        if not geos and not rights_source:
            continue
        linked = variety_ids.intersection(row.get("entity_ids") or [])
        if rights_source:
            registration_ids.update(linked)
        if geos:
            for variety_id in linked:
                related_geos.setdefault(variety_id, set()).update(geos)
    agronomic_ids: set[str] = set()
    for variety in varieties:
        vid = str(variety.get("id") or "")
        attrs = variety.get("attributes") or {}
        if vid and (attrs.get("traits") or []):
            agronomic_ids.add(vid)
    for fact in facts:
        if not any(str(eid).startswith("trait-") for eid in (fact.get("entity_ids") or [])):
            continue
        agronomic_ids.update(eid for eid in (fact.get("entity_ids") or []) if eid in variety_ids)

    def empty_counts() -> dict[str, int]:
        return {
            "canonical_varieties": 0,
            "candidates": 0,
            "confirmed_breeder_owner": 0,
            "registration_evidence": 0,
            "commercial_deployment_evidence": 0,
            "agronomic_product_knowledge": 0,
            "unresolved_aliases": 0,
        }

    by_berry = {berry_id: empty_counts() for berry_id in BERRY_ORDER}
    by_geo = {key: empty_counts() for key, _label, _aliases in GEO_FOCUS}
    breeders: dict[str, dict[str, int]] = {}

    for variety in varieties:
        vid = str(variety.get("id") or "")
        if not vid:
            continue
        berries = _berries(variety) or {"(untagged)"}
        geos = _geo_buckets((
            str(variety.get("jurisdiction") or variety.get("geography") or "").strip(),
            str(variety.get("geography_id") or "").strip(),
            *(str(geo) for geo in (variety.get("geography_ids") or []) if geo),
            *related_geos.get(vid, ()),
        ))
        for berry_id in berries:
            if berry_id not in by_berry:
                by_berry[berry_id] = empty_counts()
            by_berry[berry_id]["canonical_varieties"] += 1
            if vid in ownership_ids or str((variety.get("attributes") or {}).get("breeder") or "").strip():
                by_berry[berry_id]["confirmed_breeder_owner"] += 1
            if vid in registration_ids:
                by_berry[berry_id]["registration_evidence"] += 1
            if vid in deployment_ids:
                by_berry[berry_id]["commercial_deployment_evidence"] += 1
            if vid in agronomic_ids:
                by_berry[berry_id]["agronomic_product_knowledge"] += 1
        for geo in geos:
            by_geo[geo]["canonical_varieties"] += 1
            if vid in ownership_ids:
                by_geo[geo]["confirmed_breeder_owner"] += 1
            if vid in registration_ids:
                by_geo[geo]["registration_evidence"] += 1
            if vid in deployment_ids:
                by_geo[geo]["commercial_deployment_evidence"] += 1
            if vid in agronomic_ids:
                by_geo[geo]["agronomic_product_knowledge"] += 1
        saved_breeder = ((entity_index.get(vid) or {}).get("attributes") or {}).get("breeder")
        breeder = first_breeder.get(vid) or str(saved_breeder or "").strip() or "(no breeder/owner recorded)"
        bucket = breeders.setdefault(
            breeder,
            {"known_canonical_varieties": 0, "candidate_varieties": 0, "unresolved_aliases": 0},
        )
        bucket["known_canonical_varieties"] += 1

    for candidate in candidates:
        berries = _berries(candidate) or {"(untagged)"}
        jurisdiction = str(candidate.get("jurisdiction") or "")
        geos = _geo_buckets((jurisdiction,))
        unresolved = candidate.get("identity_state") in {STATE_POSSIBLE_ALIAS, STATE_UNKNOWN}
        owner = str(candidate.get("breeder_owner") or candidate.get("applicant") or "").strip() or "(no breeder/owner recorded)"
        breeders.setdefault(
            owner,
            {"known_canonical_varieties": 0, "candidate_varieties": 0, "unresolved_aliases": 0},
        )
        breeders[owner]["candidate_varieties"] += 1
        if unresolved:
            breeders[owner]["unresolved_aliases"] += 1
        for berry_id in berries:
            if berry_id not in by_berry:
                by_berry[berry_id] = empty_counts()
            by_berry[berry_id]["candidates"] += 1
            if unresolved:
                by_berry[berry_id]["unresolved_aliases"] += 1
            if candidate.get("registration") or candidate.get("application_number") or candidate.get("grant_number"):
                by_berry[berry_id]["registration_evidence"] += 0  # candidate registration is not trusted evidence
        for geo in geos:
            by_geo[geo]["candidates"] += 1
            if unresolved:
                by_geo[geo]["unresolved_aliases"] += 1

    def present_berry(berry_id: str, counts: dict[str, int]) -> dict[str, Any]:
        return {"id": berry_id, "label": BERRY_LABELS.get(berry_id, berry_id), **counts}

    return {
        "totals": {
            "canonical_varieties": len(varieties),
            "candidates": len(candidates),
            "confirmed_breeder_owner": len(ownership_ids),
            "registration_evidence": len(registration_ids),
            "commercial_deployment_evidence": len(deployment_ids),
            "agronomic_product_knowledge": len(agronomic_ids),
            "unresolved_aliases": sum(
                1
                for row in candidates
                if row.get("identity_state") in {STATE_POSSIBLE_ALIAS, STATE_UNKNOWN}
            ),
        },
        "by_berry": [present_berry(berry_id, by_berry[berry_id]) for berry_id in BERRY_ORDER if berry_id in by_berry]
        + [present_berry(berry_id, counts) for berry_id, counts in by_berry.items() if berry_id not in BERRY_ORDER],
        "by_geography": [
            {"id": key, "label": label, **by_geo[key]}
            for key, label, _aliases in GEO_FOCUS
        ],
        "by_breeder": [
            {"name": name, **counts}
            for name, counts in sorted(breeders.items(), key=lambda item: (-item[1]["known_canonical_varieties"], item[0].casefold()))
        ],
        "notes": [
            "Counts are raw and explainable. There is no completeness score.",
            "Candidate registration identifiers are provenance on an untrusted candidate, not trusted Evidence.",
            "GET/render of this matrix does not approve, publish, or merge varieties.",
            "Catalog entries may be active, unverified or historical. Discovered names still need human identity and source review.",
        ],
        "universe": universe_headcounts(varieties=varieties, candidates=candidates),
    }
