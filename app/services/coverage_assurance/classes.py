"""Source classes for Coverage Assurance.

These are labels, not importance scores. Mapping from registered Source
entity_types is best-effort overlay; a universe row may override.
"""

from __future__ import annotations

from typing import Any

BREEDER_GENETICS_OWNER = "breeder_genetics_owner"
PBR_PVP_REGISTRY = "pbr_pvp_registry"
GOVERNMENT_STATISTICAL = "government_statistical"
UNIVERSITY_EXTENSION = "university_extension"
PEER_REVIEWED_ACADEMIC = "peer_reviewed_academic"
TRADE_PRESS = "trade_press"
GROWER_MARKETER_ORGANIZATION = "grower_marketer_organization"
NURSERY_PROPAGATION_CATALOGUE = "nursery_propagation_catalogue"
RETAILER_BRAND_DISCLOSURE = "retailer_brand_disclosure"
CONFERENCE_TRIAL_MATERIAL = "conference_trial_material"
INDUSTRY_ASSOCIATION = "industry_association"

SOURCE_CLASSES = (
    BREEDER_GENETICS_OWNER,
    PBR_PVP_REGISTRY,
    GOVERNMENT_STATISTICAL,
    UNIVERSITY_EXTENSION,
    PEER_REVIEWED_ACADEMIC,
    TRADE_PRESS,
    GROWER_MARKETER_ORGANIZATION,
    NURSERY_PROPAGATION_CATALOGUE,
    RETAILER_BRAND_DISCLOSURE,
    CONFERENCE_TRIAL_MATERIAL,
    INDUSTRY_ASSOCIATION,
)

SOURCE_CLASS_LABELS = {
    BREEDER_GENETICS_OWNER: "Breeder / genetics owner",
    PBR_PVP_REGISTRY: "PBR / PVP registry",
    GOVERNMENT_STATISTICAL: "Government / statistical",
    UNIVERSITY_EXTENSION: "University / extension",
    PEER_REVIEWED_ACADEMIC: "Peer-reviewed / academic",
    TRADE_PRESS: "Trade press",
    GROWER_MARKETER_ORGANIZATION: "Grower / marketer organization",
    NURSERY_PROPAGATION_CATALOGUE: "Nursery / propagation catalogue",
    RETAILER_BRAND_DISCLOSURE: "Retailer / brand disclosure",
    CONFERENCE_TRIAL_MATERIAL: "Conference / trial material",
    INDUSTRY_ASSOCIATION: "Industry association",
}

ENTITY_TYPE_TO_CLASS = {
    "breeding_program": BREEDER_GENETICS_OWNER,
    "genetics_company": BREEDER_GENETICS_OWNER,
    "government_regulatory": GOVERNMENT_STATISTICAL,
    "academic_journal": PEER_REVIEWED_ACADEMIC,
    "trade_press": TRADE_PRESS,
    "grower_marketer": GROWER_MARKETER_ORGANIZATION,
    "nursery_propagator": NURSERY_PROPAGATION_CATALOGUE,
    "retailer_foodservice": RETAILER_BRAND_DISCLOSURE,
    "trade_association": INDUSTRY_ASSOCIATION,
    "market_research": TRADE_PRESS,
}

# Collapsed matrix columns from the mission (raw counts, not scores).
MATRIX_CLASS_GROUPS = (
    ("registry", "Registry", frozenset({PBR_PVP_REGISTRY})),
    ("breeder", "Breeder", frozenset({BREEDER_GENETICS_OWNER})),
    ("trade_press", "Trade press", frozenset({TRADE_PRESS})),
    (
        "academic_trials",
        "Academic / trials",
        frozenset({PEER_REVIEWED_ACADEMIC, UNIVERSITY_EXTENSION, CONFERENCE_TRIAL_MATERIAL}),
    ),
    ("government_statistics", "Government / statistics", frozenset({GOVERNMENT_STATISTICAL})),
    (
        "grower_marketer",
        "Grower / marketer",
        frozenset(
            {
                GROWER_MARKETER_ORGANIZATION,
                NURSERY_PROPAGATION_CATALOGUE,
                RETAILER_BRAND_DISCLOSURE,
                INDUSTRY_ASSOCIATION,
            }
        ),
    ),
)


def source_class_of(source: dict[str, Any], *, override: str | None = None) -> str:
    if override and override in SOURCE_CLASS_LABELS:
        return override
    for entity_type in source.get("entity_types") or []:
        mapped = ENTITY_TYPE_TO_CLASS.get(str(entity_type))
        if mapped:
            return mapped
    return TRADE_PRESS


def matrix_group_of(source_class: str) -> str:
    for key, _label, members in MATRIX_CLASS_GROUPS:
        if source_class in members:
            return key
    return "grower_marketer"
