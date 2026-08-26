"""Explainable Variety coverage counts. No completeness score."""

from __future__ import annotations

from typing import Any

from app.services.variety_universe.identity import STATE_POSSIBLE_ALIAS, STATE_UNKNOWN

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

ROLE_OWNERSHIP_PREDICATES = {"develops", "owns"}
ROLE_DEPLOYMENT_PREDICATES = {"grows", "markets", "sells", "trials", "licenses"}
RIGHTS_SOURCE_TYPES = {"plant_breeders_rights_record", "patent_record", "patent", "patent_aggregator"}


def _berries(record: dict[str, Any]) -> set[str]:
    berries = {str(item) for item in (record.get("berry_ids") or []) if item}
    berry = str(record.get("berry_id") or "").strip()
    if berry:
        berries.add(berry)
    return berries


def _geo_bucket(record: dict[str, Any], evidence: list[dict[str, Any]], relationships: list[dict[str, Any]]) -> set[str]:
    buckets: set[str] = set()
    jurisdiction = str(record.get("jurisdiction") or record.get("geography") or "").strip()
    geo_id = str(record.get("geography_id") or "").strip()
    tokens = {jurisdiction, geo_id, *(str(g) for g in (record.get("geography_ids") or []) if g)}
    record_id = str(record.get("id") or "")
    for row in evidence:
        if record_id and record_id in (row.get("entity_ids") or []):
            tokens.update(str(g) for g in (row.get("geography_ids") or []) if g)
    for rel in relationships:
        if rel.get("object_id") == record_id and rel.get("predicate") == "operates_in":
            tokens.add(str(rel.get("subject_id") or ""))
        if rel.get("subject_id") == record_id and rel.get("predicate") == "operates_in":
            tokens.add(str(rel.get("object_id") or ""))
    for key, _label, aliases in GEO_FOCUS:
        if key == "other":
            continue
        if any(token in aliases or token.casefold() in {a.casefold() for a in aliases} for token in tokens if token):
            buckets.add(key)
    if not buckets:
        buckets.add("other")
    return buckets


def _breeder_name(variety_id: str, entities: dict[str, dict[str, Any]], relationships: list[dict[str, Any]]) -> str:
    names: list[str] = []
    for rel in relationships:
        if rel.get("object_id") != variety_id or rel.get("predicate") != "develops":
            continue
        subject = entities.get(str(rel.get("subject_id") or ""))
        if subject and subject.get("entity_type") == "company":
            name = str(subject.get("name") or subject["id"])
            if name not in names:
                names.append(name)
    attrs_breeder = str((entities.get(variety_id) or {}).get("attributes", {}).get("breeder") or "").strip()
    if attrs_breeder and attrs_breeder not in names:
        names.append(attrs_breeder)
    return names[0] if names else "(no breeder/owner recorded)"


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

    ownership_ids = {
        str(rel.get("object_id"))
        for rel in relationships
        if rel.get("predicate") in ROLE_OWNERSHIP_PREDICATES and rel.get("object_id") in variety_ids
    }
    deployment_ids = {
        str(rel.get("object_id"))
        for rel in relationships
        if rel.get("predicate") in ROLE_DEPLOYMENT_PREDICATES and rel.get("object_id") in variety_ids
    }
    registration_ids: set[str] = set()
    for row in published_evidence:
        if row.get("source_type") not in RIGHTS_SOURCE_TYPES:
            continue
        registration_ids.update(eid for eid in (row.get("entity_ids") or []) if eid in variety_ids)
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
        geos = _geo_bucket(variety, published_evidence, relationships)
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
        breeder = _breeder_name(vid, entity_index, relationships)
        bucket = breeders.setdefault(
            breeder,
            {"known_canonical_varieties": 0, "candidate_varieties": 0, "unresolved_aliases": 0},
        )
        bucket["known_canonical_varieties"] += 1

    for candidate in candidates:
        berries = _berries(candidate) or {"(untagged)"}
        geos = set()
        jurisdiction = str(candidate.get("jurisdiction") or "")
        for key, _label, aliases in GEO_FOCUS:
            if key == "other":
                continue
            if jurisdiction in aliases or jurisdiction.casefold() in {a.casefold() for a in aliases}:
                geos.add(key)
        if not geos:
            geos.add("other")
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
        ],
    }
