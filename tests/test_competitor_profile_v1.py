"""Competitor Profile Data Service V1.

Validates app/services/competitor_profile.py -- a composition-only service
that returns a reusable profile view model for any of the 33 roster
entities regardless of entity_type. No new canonical facts, no new
relationships, no new varieties: everything here reads real, already-
committed data (the same data Company + Genetics Relationships V1 and
Competitor Identity and Genetics Verification V1 already produced).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.competitor_profile import (
    COMPLETENESS_DIMENSIONS,
    build_competitor_profile,
    profile_completeness,
)
from app.services.competitor_registry import load_reconciliation_matrix

REPO = Path(__file__).resolve().parents[1]
DATA_DIR = REPO / "data"

EXPECTED_ROSTER = [
    "Advanced Berry Breeding", "AgroBerries", "Australasian Plant Genetics", "BerryWorld",
    "Black Venture Farm", "California Giant", "Costa", "Denning Blueberries", "Expoberries",
    "Fall Creek", "Fresh Forward", "Fruitist", "Gem-Pack Berries", "Hortifrut Genetica",
    "IQ Berries", "Marionnet", "Mountain Blue", "Oishii", "Ozblu", "Pairwise", "Perfection Fresh",
    "Planasa", "Plant Sciences", "Royakkers", "Smart Berries", "Splendor Produce", "SunBelle",
    "The Berry Collective", "UC Davis", "University of Arkansas", "University of Florida",
    "Well-Pict", "Wish Farms",
]


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_all_entities() -> list[dict]:
    return [
        _load(p)
        for folder in (DATA_DIR / "entities").iterdir() if folder.is_dir()
        for p in folder.glob("*.json")
    ]


def _load_all_relationships() -> list[dict]:
    return [_load(p) for p in (DATA_DIR / "relationships").glob("*.json")]


def _load_sources() -> list[dict]:
    return _load(DATA_DIR / "configuration" / "sources.json")


@pytest.fixture(scope="module")
def entities():
    return _load_all_entities()


@pytest.fixture(scope="module")
def relationships():
    return _load_all_relationships()


@pytest.fixture(scope="module")
def sources():
    return _load_sources()


@pytest.fixture(scope="module")
def matrix():
    return load_reconciliation_matrix(DATA_DIR)


@pytest.fixture(scope="module")
def all_profiles(entities, relationships, sources, matrix):
    profiles = {}
    for row in matrix["rows"]:
        profile = build_competitor_profile(
            row["spreadsheet_label"], data_dir=DATA_DIR, entities=entities,
            sources=sources, relationships=relationships,
        )
        profiles[row["spreadsheet_label"]] = profile
    return profiles


# ---------------------------------------------------------------------------
# 33/33 roster returns profiles
# ---------------------------------------------------------------------------


def test_all_33_roster_entries_return_a_profile(all_profiles):
    assert len(all_profiles) == 33
    for label, profile in all_profiles.items():
        assert profile is not None, label


def test_unknown_identifier_returns_none(entities, relationships, sources):
    result = build_competitor_profile(
        "not-a-real-roster-entry", data_dir=DATA_DIR, entities=entities,
        sources=sources, relationships=relationships,
    )
    assert result is None


def test_profile_resolves_by_canonical_id_or_spreadsheet_label_identically(entities, relationships, sources, matrix):
    row = next(r for r in matrix["rows"] if r["spreadsheet_label"] == "California Giant")
    by_label = build_competitor_profile(
        "California Giant", data_dir=DATA_DIR, entities=entities, sources=sources, relationships=relationships,
    )
    by_id = build_competitor_profile(
        row["canonical_entity_id"], data_dir=DATA_DIR, entities=entities, sources=sources, relationships=relationships,
    )
    assert by_label == by_id


# ---------------------------------------------------------------------------
# All canonical entity types work
# ---------------------------------------------------------------------------


def test_all_three_canonical_entity_types_are_represented(all_profiles):
    types = {p["entity_type"] for p in all_profiles.values()}
    assert types == {"company", "brand", "breeding_program"}


def test_ozblu_is_a_brand_profile_with_a_valid_route(all_profiles):
    profile = all_profiles["Ozblu"]
    assert profile["entity_type"] == "brand"
    assert profile["profile_url"] == "/entities/brand/brand-ozblu"


def test_uc_davis_is_a_breeding_program_profile_with_a_valid_route(all_profiles):
    profile = all_profiles["UC Davis"]
    assert profile["entity_type"] == "breeding_program"
    assert profile["profile_url"] == "/entities/breeding_program/breeding_program-uc-davis-strawberry"


def test_universities_are_company_type_profiles_per_existing_convention(all_profiles):
    for label in ("University of Arkansas", "University of Florida"):
        assert all_profiles[label]["entity_type"] == "company"


def test_non_company_entities_do_not_depend_on_company_only_queries(all_profiles):
    """A brand/breeding_program profile must not crash or silently empty out
    genetics/monitoring/completeness just because it isn't entity_type
    'company'."""
    for label in ("Ozblu", "UC Davis"):
        profile = all_profiles[label]
        assert isinstance(profile["genetics"]["as_company"], list)
        assert isinstance(profile["genetics"]["as_provider"], list)
        assert profile["monitoring"]["maturity"] is not None
        assert profile["completeness"]["applicable_count"] > 0


# ---------------------------------------------------------------------------
# Aliases and spreadsheet labels resolve
# ---------------------------------------------------------------------------


def test_aliases_present_on_profile_for_a_well_aliased_entity(all_profiles):
    profile = all_profiles["California Giant"]
    assert "California Giant" in profile["aliases"] or profile["spreadsheet_label"] == "California Giant"
    assert "Cal Giant" in profile["aliases"]


def test_every_profile_carries_its_own_spreadsheet_label(all_profiles):
    for label, profile in all_profiles.items():
        assert profile["spreadsheet_label"] == label


# ---------------------------------------------------------------------------
# Berry tiers remain berry-specific; priority separate from tier
# ---------------------------------------------------------------------------


def test_berry_tiers_are_berry_specific_not_shared(all_profiles):
    profile = all_profiles["Fall Creek"]
    tiers = profile["classification"]["berry_tier"]
    assert tiers["blueberry"] == "tier_1"
    assert tiers["strawberry"] == "unassigned"
    assert tiers["raspberry"] == "unassigned"
    assert tiers["blackberry"] == "unassigned"


def test_priority_is_independent_of_tier(all_profiles):
    fall_creek = all_profiles["Fall Creek"]
    assert fall_creek["classification"]["strategic_priority"] is None
    assert fall_creek["classification"]["berry_tier"]["blueberry"] == "tier_1"

    university = all_profiles["University of Arkansas"]
    assert university["classification"]["strategic_priority"] == "Top"
    assert all(v == "unassigned" for v in university["classification"]["berry_tier"].values())


# ---------------------------------------------------------------------------
# Incomplete fields remain explicit -- never silently blank
# ---------------------------------------------------------------------------


def test_incomplete_dimensions_are_explicit_not_silently_blank(all_profiles):
    profile = all_profiles["Denning Blueberries"]
    dims = profile["completeness"]["dimensions"]
    assert dims["identity"] == "missing"  # still 'unverified', not promoted
    assert set(dims.values()) <= {"present", "missing", "not_applicable"}
    assert len(profile["unresolved_data_gaps"]) > 0


def test_completeness_dimensions_are_the_fixed_documented_set(all_profiles):
    for profile in all_profiles.values():
        assert set(profile["completeness"]["dimensions"].keys()) == set(COMPLETENESS_DIMENSIONS)


def test_completeness_is_never_a_single_invented_score(all_profiles):
    for profile in all_profiles.values():
        completeness = profile["completeness"]
        assert "score" not in completeness
        assert "strategic_score" not in completeness
        assert isinstance(completeness["dimensions"], dict)


def test_not_applicable_never_conflated_with_missing():
    """A synthetic profile-completeness call proves not_applicable and
    missing are structurally distinct outcomes, not just differently-named
    versions of the same thing."""
    profile_no_genetics_no_gaps = {
        "identity": {"entity_found": True, "status": "active"},
        "classification": {"competitor_type": "Commercial", "berry_tier": {"blueberry": "tier_1", "strawberry": "unassigned", "raspberry": "unassigned", "blackberry": "unassigned"}, "regions": ["DOTA"]},
        "genetics": {"as_company": [], "as_provider": []},
        "monitoring": {"maturity": {"discovery_configured": True, "discovery_operational": True, "readable_content_acquired": True, "current_coverage_available": True}},
        "aliases": ["Alias"],
        "unresolved_data_gaps": [],
    }
    result = profile_completeness(profile_no_genetics_no_gaps)
    assert result["dimensions"]["genetics"] == "not_applicable"
    assert result["dimensions"]["identity"] == "present"


# ---------------------------------------------------------------------------
# Genetics directionality and review state survive
# ---------------------------------------------------------------------------


def test_genetics_directionality_is_correct_both_sides(all_profiles):
    agroberries = all_profiles["AgroBerries"]
    outgoing = [r for r in agroberries["genetics"]["as_company"] if r["direction"] == "outgoing"]
    assert any(r["other_entity_id"] == "company-mountain-blue-orchards" for r in outgoing)

    mountain_blue = all_profiles["Mountain Blue"]
    incoming = [r for r in mountain_blue["genetics"]["as_provider"]]
    assert any(r["other_entity_id"] == "company-agroberries" for r in incoming)


def test_genetics_review_state_and_confidence_survive_unflattened(all_profiles):
    agroberries = all_profiles["AgroBerries"]
    rel = next(r for r in agroberries["genetics"]["as_company"] if r["other_entity_id"] == "company-mountain-blue-orchards")
    assert rel["status"] == "active"
    assert rel["confidence"] == "high"
    assert rel["predicate"] == "licenses"

    fall_creek_side = all_profiles["Fall Creek"]
    pending = [r for r in fall_creek_side["genetics"]["as_provider"] if r["status"] == "disputed"]
    assert len(pending) >= 2  # Agrovision and California Giant, both still pending


# ---------------------------------------------------------------------------
# Provider mappings do not create varieties
# ---------------------------------------------------------------------------


def test_provider_genetics_never_populates_verified_variety_relationships(all_profiles):
    agroberries = all_profiles["AgroBerries"]
    # The AgroBerries<->MBO relationship is a provider-level 'licenses' edge
    # between two companies, not a company-to-Variety edge -- it must never
    # appear in verified_variety_relationships.
    for role_list in agroberries["verified_variety_relationships"]["roles"].values():
        for party in role_list:
            assert party.get("id") != "company-mountain-blue-orchards"


def test_no_variety_entities_exist_from_this_service(entities):
    """This service is read-only; confirm it created no Variety entity."""
    variety_ids = {e["id"] for e in entities if e.get("entity_type") == "variety"}
    for suspicious in ("variety-agroberries", "variety-mountain-blue-orchards"):
        assert suspicious not in variety_ids


# ---------------------------------------------------------------------------
# Monitoring facets remain separate
# ---------------------------------------------------------------------------


def test_monitoring_facets_are_five_independent_facts(all_profiles):
    for profile in all_profiles.values():
        maturity = profile["monitoring"]["maturity"]
        for key in (
            "entity_represented", "discovery_configured", "discovery_operational",
            "readable_content_acquired", "current_coverage_available",
        ):
            assert key in maturity
            assert isinstance(maturity[key], bool)


def test_california_giant_monitoring_is_honestly_blocked_not_fabricated(all_profiles):
    profile = all_profiles["California Giant"]
    assert profile["monitoring"]["resolved_state"] == "source_blocked"


# ---------------------------------------------------------------------------
# Provisional identities remain honest
# ---------------------------------------------------------------------------


def test_provisional_identities_stay_unverified_in_the_profile(all_profiles):
    for label in ("Denning Blueberries", "Marionnet", "The Berry Collective"):
        profile = all_profiles[label]
        assert profile["identity"]["status"] == "unverified"
        assert profile["identity"]["reason"]  # never blank


def test_verified_identities_carry_evidence_in_the_profile(all_profiles):
    profile = all_profiles["Oishii"]
    assert profile["identity"]["status"] == "active"
    assert profile["identity"]["evidence_urls"]
    assert profile["identity"]["confidence"] == "high"


# ---------------------------------------------------------------------------
# No duplicate canonical entity introduced
# ---------------------------------------------------------------------------


def test_no_duplicate_canonical_entity_across_all_profiles(all_profiles):
    ids = [p["canonical_entity_id"] for p in all_profiles.values()]
    assert len(ids) == len(set(ids)) == 33


# ---------------------------------------------------------------------------
# Profile URLs and landscape handoffs are valid
# ---------------------------------------------------------------------------


def test_every_profile_url_is_a_well_formed_entity_route(all_profiles):
    for label, profile in all_profiles.items():
        url = profile["profile_url"]
        assert url.startswith(f"/entities/{profile['entity_type']}/"), label


def test_filtered_landscape_urls_cover_all_four_berries(all_profiles):
    for profile in all_profiles.values():
        berries_linked = {link["berry"] for link in profile["filtered_landscape_urls"]}
        assert berries_linked == {"strawberry", "blueberry", "raspberry", "blackberry"}
        for link in profile["filtered_landscape_urls"]:
            assert link["href"].startswith("/competitors?")
            assert f"company={profile['canonical_entity_id']}" in link["href"]


def test_landscape_urls_use_the_same_filter_builder_as_the_landscape_page(all_profiles):
    """Cross-check against competitor_landscape's own filters_to_query, so
    a profile link can never silently diverge from what /competitors
    itself would produce for the same filters."""
    from app.services.competitor_landscape import LandscapeFilters, filters_to_query

    profile = all_profiles["California Giant"]
    blueberry_link = next(link for link in profile["filtered_landscape_urls"] if link["berry"] == "blueberry")
    expected = filters_to_query(
        LandscapeFilters(berry="blueberry", company=profile["canonical_entity_id"]), include_company=True
    )
    assert blueberry_link["href"] == f"/competitors?{expected}"


# ---------------------------------------------------------------------------
# Internal classifications untouched by this service
# ---------------------------------------------------------------------------


def test_service_never_mutates_canonical_data():
    import subprocess
    for path in ("data/entities", "data/relationships", "data/evidence", "data/configuration/sources.json"):
        result = subprocess.run(
            ["git", "-c", f"safe.directory={REPO}", "status", "--porcelain", "--", path],
            cwd=REPO, capture_output=True, text=True, check=False,
        )
        assert result.stdout.strip() == "", f"unexpected changes under {path}: {result.stdout}"
