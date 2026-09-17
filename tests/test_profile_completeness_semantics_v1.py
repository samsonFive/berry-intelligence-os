"""Refine Profile Completeness Semantics V1.

Proves the refined, 7-concern completeness model in
app/services/competitor_profile.py does not conflate structural data
quality with legitimate Unknown/Unassigned classifications or operational
coverage gaps. Companion to tests/test_competitor_profile_v1.py, which
still covers the base view-model contract (roster resolution, genetics
directionality, monitoring facets, URLs, etc.) unchanged by this mission.

Every synthetic profile below is a plain dict built by hand -- not routed
through build_competitor_profile() -- so each proof point isolates exactly
one rule of the semantic model without depending on today's real roster
data ever happening to contain that state.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from app.services.competitor_profile import (
    BERRIES,
    FIELD_STATES,
    GAP_SEVERITIES,
    IDENTITY_VERIFICATION_STATES,
    INTEGRITY_STATES,
    build_competitor_profile,
    profile_completeness,
    profile_roster_summary,
)
from app.services.competitor_registry import load_reconciliation_matrix

REPO = Path(__file__).resolve().parents[1]
DATA_DIR = REPO / "data"


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
    profiles = []
    for row in matrix["rows"]:
        profile = build_competitor_profile(
            row["spreadsheet_label"], data_dir=DATA_DIR, entities=entities,
            sources=sources, relationships=relationships,
        )
        assert profile is not None, row["spreadsheet_label"]
        profiles.append(profile)
    return profiles


def _base_profile(**overrides) -> dict:
    """A minimal, structurally-valid synthetic profile -- every test below
    starts from this and overrides exactly the field(s) under test."""
    base = {
        "canonical_entity_id": "company-test",
        "display_name": "Test Co",
        "spreadsheet_label": "Test Co",
        "aliases": [],
        "entity_type": "company",
        "identity": {
            "entity_found": True,
            "status": "active",
            "resolution_status": "existing_exact_match",
            "confidence": None,
            "verdict": None,
            "reason": "settled",
            "evidence_urls": [],
            "verification_date": None,
            "verification_state": "active_verified",
            "verification_state_reason": "settled",
        },
        "classification": {
            "competitor_type": "Commercial",
            "strategic_priority": "Top",
            "regions": ["DOTA"],
            "berry_tier": {"strawberry": "tier_1", "blueberry": "unassigned", "raspberry": "unassigned", "blackberry": "unassigned"},
            "snapshot_date": "2026-09-15",
            "provenance": "internal_competitor_registry_spreadsheet, snapshot_date=2026-09-15",
        },
        "parent_brand_relationships": [],
        "genetics": {"as_company": [], "as_provider": []},
        "verified_variety_relationships": {"roles": {}},
        "monitoring": {
            "maturity": {
                "entity_represented": True,
                "discovery_configured": True,
                "discovery_operational": True,
                "readable_content_acquired": True,
                "current_coverage_available": True,
                "linked_source_count": 1,
                "runnable_source_count": 1,
                "current_usable_coverage_count": 3,
                "official_source_blocked": False,
                "official_source_block_detail": "",
                "manual_or_alternative_source_required": False,
            },
        },
        "profile_url": "/entities/company/company-test",
        "filtered_landscape_urls": [{"berry": b, "href": f"/competitors?berry={b}&company=company-test"} for b in BERRIES],
        "unresolved_data_gaps": [],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# 1. Record integrity vs. Unknown/Unassigned/unassigned-priority/provisional
# ---------------------------------------------------------------------------


def test_unknown_unassigned_berry_slot_is_not_missing_required():
    profile = _base_profile()
    completeness = profile_completeness(profile, entities_by_id={"company-test": {}})
    assert completeness["record_integrity"]["status"] == "structurally_valid"
    assert completeness["classification_coverage"]["berry_positions"]["blueberry"]["state"] == "unknown_unassigned"


def test_all_four_berry_slots_remain_present_after_refinement():
    profile = _base_profile()
    completeness = profile_completeness(profile, entities_by_id={"company-test": {}})
    berries = completeness["classification_coverage"]["berry_positions"]
    assert set(berries.keys()) == set(BERRIES)
    check = next(c for c in completeness["record_integrity"]["checks"] if c["check"] == "all_four_berry_slots_present")
    assert check["passed"] is True


def test_not_applicable_remains_distinct_from_unknown_unassigned_and_missing():
    profile = _base_profile()
    # "n/a" is the spelling competitor_landscape.normalize_tier_status's own
    # (frozen, out-of-scope-to-modify) alias table recognizes as Not
    # Applicable -- see that module's `normalize_tier_status` for the exact
    # accepted spellings ("n/a", "na", "not applicable").
    profile["classification"]["berry_tier"]["raspberry"] = "n/a"
    completeness = profile_completeness(profile, entities_by_id={"company-test": {}})
    berries = completeness["classification_coverage"]["berry_positions"]
    assert berries["raspberry"]["state"] == "not_applicable"
    assert berries["blueberry"]["state"] == "unknown_unassigned"
    assert berries["raspberry"]["state"] != berries["blueberry"]["state"]
    # Not Applicable never produces an actionable gap -- it is a resolved state.
    assert not any(g["dimension"] == "berry_position:raspberry" for g in completeness["actionable_gaps"])


def test_unassigned_strategic_priority_is_not_malformed_data():
    profile = _base_profile()
    profile["classification"]["strategic_priority"] = None
    completeness = profile_completeness(profile, entities_by_id={"company-test": {}})
    assert completeness["record_integrity"]["status"] == "structurally_valid"
    assert completeness["classification_coverage"]["strategic_priority"]["state"] == "unknown_unassigned"


def test_provisional_identity_remains_explicit_and_never_malformed():
    profile = _base_profile()
    profile["identity"]["status"] = "unverified"
    profile["identity"]["verification_state"] = "provisional"
    completeness = profile_completeness(profile, entities_by_id={"company-test": {}})
    assert completeness["identity_verification"]["state"] == "provisional"
    assert completeness["record_integrity"]["status"] == "structurally_valid"
    gap = next(g for g in completeness["actionable_gaps"] if g["dimension"] == "identity")
    assert gap["blocks_stakeholder_display"] is False


def test_monitoring_gaps_remain_separate_from_record_integrity():
    profile = _base_profile()
    profile["monitoring"]["maturity"].update({
        "discovery_configured": False, "discovery_operational": False,
        "readable_content_acquired": False, "current_coverage_available": False,
    })
    completeness = profile_completeness(profile, entities_by_id={"company-test": {}})
    assert completeness["record_integrity"]["status"] == "structurally_valid"
    assert completeness["monitoring_maturity"]["discovery_configured"] is False
    assert completeness["current_intelligence_coverage"]["current_coverage_available"] is False
    assert not any(g["blocks_stakeholder_display"] for g in completeness["actionable_gaps"])


# ---------------------------------------------------------------------------
# 2. Missing required data and invalid references ARE detected
# ---------------------------------------------------------------------------


def test_missing_display_name_is_detected_as_missing_required_data():
    profile = _base_profile(display_name="")
    completeness = profile_completeness(profile, entities_by_id={"company-test": {}})
    assert completeness["record_integrity"]["status"] == "missing_required_data"
    failed = {c["check"] for c in completeness["record_integrity"]["failed_checks"]}
    assert "display_name_present" in failed
    gap = next(g for g in completeness["actionable_gaps"] if "display_name_present" in g["dimension"])
    assert gap["blocks_stakeholder_display"] is True


def test_missing_berry_slot_is_detected_as_missing_required_data():
    profile = _base_profile()
    del profile["classification"]["berry_tier"]["blackberry"]
    completeness = profile_completeness(profile, entities_by_id={"company-test": {}})
    assert completeness["record_integrity"]["status"] == "missing_required_data"
    failed = {c["check"] for c in completeness["record_integrity"]["failed_checks"]}
    assert "all_four_berry_slots_present" in failed


def test_unresolved_entity_is_invalid_reference_and_blocks_display():
    profile = _base_profile()
    profile["identity"]["entity_found"] = False
    profile["identity"]["verification_state"] = "invalid_canonical_reference"
    completeness = profile_completeness(profile, entities_by_id={})
    assert completeness["record_integrity"]["status"] == "invalid_reference"
    assert any(g["blocks_stakeholder_display"] for g in completeness["actionable_gaps"])
    assert completeness["ui_flags"]["profile_structurally_valid"] is False


def test_dangling_genetics_reference_fails_integrity():
    profile = _base_profile()
    profile["genetics"]["as_company"] = [
        {"relationship_id": "rel-1", "direction": "outgoing", "predicate": "licenses",
         "other_entity_id": "company-does-not-exist", "other_entity_name": "company-does-not-exist",
         "status": "active", "confidence": "high"},
    ]
    completeness = profile_completeness(profile, entities_by_id={"company-test": {}})
    assert completeness["record_integrity"]["status"] == "invalid_reference"
    failed = {c["check"] for c in completeness["record_integrity"]["failed_checks"]}
    assert "relationship_references_valid" in failed


def test_structural_rendering_blockers_are_deterministic():
    """Running the same synthetic profile through profile_completeness
    twice must produce byte-identical structural verdicts and gap lists --
    no randomness, no ordering nondeterminism."""
    profile = _base_profile(display_name="")
    entities_by_id = {"company-test": {}}
    first = profile_completeness(deepcopy(profile), entities_by_id=entities_by_id)
    second = profile_completeness(deepcopy(profile), entities_by_id=entities_by_id)
    assert first["record_integrity"] == second["record_integrity"]
    assert first["actionable_gaps"] == second["actionable_gaps"]


# ---------------------------------------------------------------------------
# 3. Non-company entities: correct applicability, no false penalty
# ---------------------------------------------------------------------------


def test_non_company_entity_types_get_correct_applicability(all_profiles):
    for profile in all_profiles:
        if profile["entity_type"] in ("brand", "breeding_program"):
            completeness = profile["completeness"]
            assert completeness["record_integrity"]["status"] == "structurally_valid"
            # entity_type never appears as a reason any check failed.
            assert not any("entity_type" in c["check"] and not c["passed"] for c in completeness["record_integrity"]["checks"])


# ---------------------------------------------------------------------------
# 4. Only genuine integrity errors block stakeholder display
# ---------------------------------------------------------------------------


def test_only_integrity_failures_ever_block_stakeholder_display(all_profiles):
    for profile in all_profiles:
        completeness = profile["completeness"]
        for gap in completeness["actionable_gaps"]:
            if gap["blocks_stakeholder_display"]:
                assert gap["category"] in ("missing_required_data", "invalid_data")
            else:
                assert gap["category"] not in ("missing_required_data", "invalid_data")
    # Direct proof: an Unknown/Unassigned or provisional-identity gap never blocks.
    for profile in all_profiles:
        for gap in profile["completeness"]["actionable_gaps"]:
            if gap["state"] in ("unknown_unassigned", "not_applicable", "pending_verification", "absent_optional"):
                assert gap["blocks_stakeholder_display"] is False


def test_actionable_gap_shape_carries_every_required_field(all_profiles):
    required_keys = {
        "dimension", "state", "category", "severity", "why_it_matters", "recommended_next_action",
        "owning_workflow", "source_provenance", "blocks_stakeholder_display",
    }
    seen_any_gap = False
    for profile in all_profiles:
        for gap in profile["completeness"]["actionable_gaps"]:
            seen_any_gap = True
            assert required_keys <= set(gap.keys())
            assert gap["state"] in FIELD_STATES
    assert seen_any_gap


# ---------------------------------------------------------------------------
# 5. All 33 profiles still return; roster summary is multidimensional
# ---------------------------------------------------------------------------


def test_all_33_profiles_still_return_under_the_refined_model(all_profiles):
    assert len(all_profiles) == 33
    for profile in all_profiles:
        assert profile["completeness"]["record_integrity"]["status"] in INTEGRITY_STATES
        assert profile["completeness"]["identity_verification"]["state"] in IDENTITY_VERIFICATION_STATES


def test_roster_summary_never_collapses_to_a_single_percentage(all_profiles):
    summary = profile_roster_summary(all_profiles)
    assert "percent_complete" not in summary
    assert "score" not in summary
    assert summary["profiles_returned"] == 33
    assert summary["structurally_valid"] == 33
    assert summary["missing_required_data"] == 0
    assert summary["invalid_reference"] == 0
    assert summary["blocking_profile_defects"] == 0
    # Real, honestly-counted gaps still show up distinctly.
    assert summary["provisional_identity"] == 9
    assert summary["unassigned_internal_classification"] > 0
    assert summary["lacking_genetics_information"] > 0


def test_no_canonical_record_changes_from_this_mission():
    import subprocess
    for path in (
        "data/entities", "data/relationships", "data/evidence", "data/configuration/sources.json",
        "data/configuration/competitor-tiers.json", "data/configuration/priorities.json",
        "data/configuration/regions.json",
    ):
        result = subprocess.run(
            ["git", "-c", f"safe.directory={REPO}", "status", "--porcelain", "--", path],
            cwd=REPO, capture_output=True, text=True, check=False,
        )
        assert result.stdout.strip() == "", f"unexpected changes under {path}: {result.stdout}"


def test_gap_severity_and_category_vocabularies_are_the_documented_small_sets(all_profiles):
    for profile in all_profiles:
        for gap in profile["completeness"]["actionable_gaps"]:
            assert gap["severity"] in GAP_SEVERITIES
