"""Company + Genetics Relationships V1.

Validates the 33-entry mandatory competitor roster (data/imports/
competitor-registry-2026-09-15/), the resulting entity/relationship
records, and app/services/competitor_registry.py's read-only, unfiltered
presentation of that roster. Deliberately tests against the real committed
data (same convention as tests/test_source_coverage_gap_closure_v1.py),
not synthetic fixtures -- the mission's own acceptance bar is "33/33
represented" against the actual repository, not a toy example.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.competitor_registry import (
    MONITORING_STATES,
    companies_for_genetics_provider,
    genetics_relationships_for_company,
    load_latest_snapshot,
    load_reconciliation_matrix,
    monitoring_state_for_entity,
    unfiltered_competitor_registry,
)

REPO = Path(__file__).resolve().parents[1]
DATA_DIR = REPO / "data"
IMPORT_DIR = DATA_DIR / "imports" / "competitor-registry-2026-09-15"

EXPECTED_ROSTER = [
    "Advanced Berry Breeding", "AgroBerries", "Australasian Plant Genetics", "BerryWorld",
    "Black Venture Farm", "California Giant", "Costa", "Denning Blueberries", "Expoberries",
    "Fall Creek", "Fresh Forward", "Fruitist", "Gem-Pack Berries", "Hortifrut Genetica",
    "IQ Berries", "Marionnet", "Mountain Blue", "Oishii", "Ozblu", "Pairwise", "Perfection Fresh",
    "Planasa", "Plant Sciences", "Royakkers", "Smart Berries", "Splendor Produce", "SunBelle",
    "The Berry Collective", "UC Davis", "University of Arkansas", "University of Florida",
    "Well-Pict", "Wish Farms",
]

BERRIES = ("strawberry", "blueberry", "raspberry", "blackberry")
VALID_TIER_VALUES = {"tier_1", "tier_2", "tier_3", "present", "unassigned", "unknown", "not_applicable"}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_all_entities() -> list[dict]:
    entities = []
    for folder in (DATA_DIR / "entities").iterdir():
        if not folder.is_dir():
            continue
        for path in folder.glob("*.json"):
            entities.append(_load_json(path))
    return entities


def _load_all_relationships() -> list[dict]:
    return [_load_json(p) for p in (DATA_DIR / "relationships").glob("*.json")]


def _load_sources() -> list[dict]:
    return _load_json(DATA_DIR / "configuration" / "sources.json")


@pytest.fixture(scope="module")
def snapshot():
    return _load_json(IMPORT_DIR / "snapshot.json")


@pytest.fixture(scope="module")
def matrix():
    return _load_json(IMPORT_DIR / "reconciliation-matrix.json")


@pytest.fixture(scope="module")
def transcription():
    return _load_json(IMPORT_DIR / "genetics-transcription.json")


@pytest.fixture(scope="module")
def entities():
    return _load_all_entities()


@pytest.fixture(scope="module")
def relationships():
    return _load_all_relationships()


@pytest.fixture(scope="module")
def sources():
    return _load_sources()


# ---------------------------------------------------------------------------
# Snapshot shape
# ---------------------------------------------------------------------------


def test_snapshot_has_exactly_33_rows(snapshot):
    assert snapshot["row_count"] == 33
    assert len(snapshot["rows"]) == 33


def test_snapshot_covers_every_mandatory_roster_label(snapshot):
    labels = {row["spreadsheet_label"] for row in snapshot["rows"]}
    assert labels == set(EXPECTED_ROSTER)
    missing = set(EXPECTED_ROSTER) - labels
    assert missing == set(), f"MISSING ROSTER ROWS: {sorted(missing)}"


def test_snapshot_row_numbers_are_unique(snapshot):
    numbers = [row["row_number"] for row in snapshot["rows"]]
    assert len(numbers) == len(set(numbers))


def test_every_row_has_all_four_berry_tier_slots(snapshot):
    for row in snapshot["rows"]:
        assert set(row["berry_tier"].keys()) == set(BERRIES), row["spreadsheet_label"]
        for berry in BERRIES:
            assert row["berry_tier"][berry] in VALID_TIER_VALUES, (row["spreadsheet_label"], berry)


def test_blank_tier_is_unassigned_not_absent_not_zero(snapshot):
    """A blank spreadsheet cell must round-trip as the explicit string
    'unassigned', never be a missing key, None, empty string, or silently
    coerced to a tier value."""
    for row in snapshot["rows"]:
        for berry, value in row["berry_tier"].items():
            assert value is not None
            assert value != ""
            if value == "unassigned":
                continue
            assert value in VALID_TIER_VALUES


def test_present_is_distinct_from_tier_3(snapshot):
    """'Present' (Denning Blueberries blueberry, Hortifrut Genetica
    strawberry) must never be silently normalized to tier_3 or any other
    tier -- it is its own status."""
    present_rows = [
        (row["spreadsheet_label"], berry)
        for row in snapshot["rows"]
        for berry, value in row["berry_tier"].items()
        if value == "present"
    ]
    assert ("Denning Blueberries", "blueberry") in present_rows
    assert ("Hortifrut Genetica", "strawberry") in present_rows
    # And none of those same cells are also tier_3 -- "present" replaces,
    # never coexists with, a tier value for the same cell.
    denning = next(r for r in snapshot["rows"] if r["spreadsheet_label"] == "Denning Blueberries")
    assert denning["berry_tier"]["blueberry"] == "present"
    assert denning["berry_tier"]["blueberry"] != "tier_3"


def test_priority_is_a_separate_dimension_from_tier(snapshot):
    """A row with no strategic_priority can still carry real berry tiers,
    and vice versa -- the two fields must vary independently, proving
    neither was derived from the other."""
    fall_creek = next(r for r in snapshot["rows"] if r["spreadsheet_label"] == "Fall Creek")
    assert fall_creek["strategic_priority"] is None
    assert fall_creek["berry_tier"]["blueberry"] == "tier_1"  # has a real tier despite no priority

    university_of_arkansas = next(r for r in snapshot["rows"] if r["spreadsheet_label"] == "University of Arkansas")
    assert university_of_arkansas["strategic_priority"] == "Top"
    assert all(v == "unassigned" for v in university_of_arkansas["berry_tier"].values())  # priority despite no tiers


def test_multi_region_values_survive_round_trip_serialization(snapshot, tmp_path):
    """Regions are multi-valued and order/content-preserving through a real
    JSON round trip -- not collapsed to a single string or deduplicated
    unexpectedly."""
    fall_creek = next(r for r in snapshot["rows"] if r["spreadsheet_label"] == "Fall Creek")
    assert fall_creek["regions"] == ["DOTA", "DOA_DANZ", "DEMEA"]
    roundtrip_path = tmp_path / "roundtrip.json"
    roundtrip_path.write_text(json.dumps(snapshot), encoding="utf-8")
    reloaded = json.loads(roundtrip_path.read_text(encoding="utf-8"))
    reloaded_row = next(r for r in reloaded["rows"] if r["spreadsheet_label"] == "Fall Creek")
    assert reloaded_row["regions"] == ["DOTA", "DOA_DANZ", "DEMEA"]


def test_internal_region_codes_preserved_verbatim(snapshot):
    all_codes = {code for row in snapshot["rows"] for code in row["regions"]}
    assert {"DOTA", "DOA_DANZ", "DEMEA"} <= all_codes


# ---------------------------------------------------------------------------
# Reconciliation matrix / entity resolution
# ---------------------------------------------------------------------------


def test_reconciliation_matrix_has_33_rows_one_per_roster_label(matrix):
    assert matrix["row_count"] == 33
    labels = {row["spreadsheet_label"] for row in matrix["rows"]}
    assert labels == set(EXPECTED_ROSTER)


def test_every_roster_row_resolves_to_a_canonical_entity_id(matrix, entities):
    by_id = {e["id"]: e for e in entities}
    unresolved = [row["spreadsheet_label"] for row in matrix["rows"] if row["canonical_entity_id"] not in by_id]
    assert unresolved == [], f"roster rows with no resolvable entity: {unresolved}"


def test_no_accidental_duplicate_canonical_entities_across_roster(matrix):
    """Two different roster labels must never resolve to the same
    canonical_entity_id unless that is an explicit, documented decision
    (there is none in this roster -- every label is a distinct entity)."""
    ids = [row["canonical_entity_id"] for row in matrix["rows"]]
    duplicates = {eid for eid in ids if ids.count(eid) > 1}
    assert duplicates == set(), f"duplicate canonical entity ids across distinct roster rows: {duplicates}"


def test_every_roster_row_has_all_four_berry_tier_fields(matrix):
    for row in matrix["rows"]:
        assert set(row["berry_tier"].keys()) == set(BERRIES)


def test_new_entities_are_marked_unverified_or_actively_verified_never_silently_trusted(matrix, entities):
    """As of this mission's own creation, every newly-created entity started
    'unverified'. Competitor Identity and Genetics Verification V1 (a later
    mission, see data/imports/competitor-identity-genetics-verification-2026-09-15/)
    subsequently promoted 8 of the 17 to 'active' -- but only ever to one of
    these two real, schema-supported statuses, each with a documented reason
    (identity_verification_2026_09_15 in attributes for every one of the 17,
    promoted or not), never silently or to a third, invented status."""
    by_id = {e["id"]: e for e in entities}
    new_rows = [r for r in matrix["rows"] if r["resolution_status"] == "newly_created"]
    assert len(new_rows) == 17
    for row in new_rows:
        entity = by_id[row["canonical_entity_id"]]
        assert entity["status"] in ("unverified", "active"), row["canonical_entity_id"]
        assert "identity_verification_2026_09_15" in (entity.get("attributes") or {}), row["canonical_entity_id"]


def test_aliases_resolve_to_the_canonical_entity(entities):
    """Every spreadsheet-label alias actually added by this mission is
    findable by simple case-sensitive membership on the entity it was
    added to -- proving alias resolution is real, not aspirational."""
    by_id = {e["id"]: e for e in entities}
    checks = [
        ("company-costa-group-holdings", "Costa"),
        ("company-hortifrut", "Hortifrut Genetica"),
        ("brand-ozblu", "Ozblu"),
        ("company-plant-sciences-genetics", "Plant Sciences"),
        ("company-wish-farms", "Wish Farms"),
        ("breeding_program-uc-davis-strawberry", "UC Davis"),
    ]
    for entity_id, alias in checks:
        entity = by_id[entity_id]
        assert alias in (entity.get("aliases") or []) or alias == entity["name"], (entity_id, alias)


def test_ambiguous_costa_resolution_is_documented_not_silent(matrix):
    costa_row = next(r for r in matrix["rows"] if r["spreadsheet_label"] == "Costa")
    assert costa_row["canonical_entity_id"] == "company-costa-group-holdings"
    assert "costa-berry-international" in costa_row["ambiguity_notes"]


def test_fruitist_resolves_to_operating_company_not_a_new_entity(matrix):
    row = next(r for r in matrix["rows"] if r["spreadsheet_label"] == "Fruitist")
    assert row["canonical_entity_id"] == "company-agrovision"
    assert row["resolution_status"] == "existing_alias_match"


# ---------------------------------------------------------------------------
# Monitoring / source coverage
# ---------------------------------------------------------------------------


def test_every_roster_entity_has_a_recognized_monitoring_state(matrix, sources):
    for row in matrix["rows"]:
        result = monitoring_state_for_entity(row["canonical_entity_id"], sources=sources)
        assert result["state"] in MONITORING_STATES, (row["spreadsheet_label"], result)
        assert result["detail"], "monitoring detail must be a real, non-empty explanation"


def test_california_giant_reports_blocked_not_fabricated_active(sources):
    result = monitoring_state_for_entity("company-california-giant-berry-farms", sources=sources)
    assert result["state"] == "source_blocked"


def test_never_run_configured_sources_are_reported_honestly(sources):
    result = monitoring_state_for_entity("company-planasa", sources=sources)
    assert result["state"] == "source_configured_never_run"


def test_brand_new_roster_entity_with_no_source_is_honest_not_active(sources):
    result = monitoring_state_for_entity("company-agroberries", sources=sources)
    assert result["state"] == "no_supported_source"


# ---------------------------------------------------------------------------
# Unfiltered registry service
# ---------------------------------------------------------------------------


def test_unfiltered_registry_returns_all_33_regardless_of_activity(entities, sources):
    rows = unfiltered_competitor_registry(data_dir=DATA_DIR, entities=entities, sources=sources)
    assert len(rows) == 33
    labels = {row["spreadsheet_label"] for row in rows}
    assert labels == set(EXPECTED_ROSTER)


def test_unfiltered_registry_keeps_a_zero_evidence_entity_visible(entities, sources):
    """A brand-new roster entity with zero evidence/signals/varieties --
    exactly what Landscape's own actor_rows filter would exclude -- must
    still appear here."""
    rows = unfiltered_competitor_registry(data_dir=DATA_DIR, entities=entities, sources=sources)
    labels = {row["spreadsheet_label"] for row in rows}
    assert "Marionnet" in labels  # a new, zero-activity entity
    marionnet = next(r for r in rows if r["spreadsheet_label"] == "Marionnet")
    assert marionnet["entity_found"] is True
    assert marionnet["entity_status"] == "unverified"


def test_unfiltered_registry_reports_current_entity_state_live(entities, sources):
    rows = unfiltered_competitor_registry(data_dir=DATA_DIR, entities=entities, sources=sources)
    cal_giant = next(r for r in rows if r["spreadsheet_label"] == "California Giant")
    assert cal_giant["entity_found"] is True
    assert "competitor" in (cal_giant["entity_roles_current"] or [])
    assert cal_giant["monitoring_state"] == "source_blocked"


def test_load_latest_snapshot_finds_the_committed_import(matrix):
    snapshot = load_latest_snapshot(DATA_DIR)
    assert snapshot is not None
    assert snapshot["snapshot_date"] == "2026-09-15"
    reconciliation = load_reconciliation_matrix(DATA_DIR)
    assert reconciliation == matrix


# ---------------------------------------------------------------------------
# Genetics relationships -- bidirectional, no invented varieties
# ---------------------------------------------------------------------------


def test_seeded_genetics_relationships_exist_and_are_pending_review_or_verified(relationships):
    """As seeded by this mission, all 3 were 'disputed' (pending-review).
    Competitor Identity and Genetics Verification V1 (a later mission)
    independently corroborated exactly one (AgroBerries <-> Mountain Blue
    Orchards, via authoritative trade press naming the specific relationship
    type) and upgraded it to 'active' with real added evidence; the other
    two were searched for corroboration, found none, and were deliberately
    left unchanged -- per that mission's own rule that absence of public
    evidence does not disprove a handwritten assertion. See
    data/imports/competitor-identity-genetics-verification-2026-09-15/genetics-relationship-evidence-assessment.json."""
    genetics_rels = {
        r["id"]: r for r in relationships
        if r["id"] in (
            "rel-agroberries-genetics-mountain-blue-orchards",
            "rel-agrovision-genetics-fall-creek-farm-and-nursery",
            "rel-california-giant-berry-farms-genetics-fall-creek-farm-and-nursery",
        )
    }
    assert len(genetics_rels) == 3
    upgraded = genetics_rels["rel-agroberries-genetics-mountain-blue-orchards"]
    assert upgraded["status"] == "active"
    assert upgraded["confidence"] == "high"
    assert set(upgraded["evidence_ids"]) == {
        "ev-competitor-genetics-handwritten-notes-2026-09-15",
        "ev-agroberries-mountain-blue-licensing-freshfruitportal-2026",
    }
    for rel_id in (
        "rel-agrovision-genetics-fall-creek-farm-and-nursery",
        "rel-california-giant-berry-farms-genetics-fall-creek-farm-and-nursery",
    ):
        rel = genetics_rels[rel_id]
        assert rel["status"] == "disputed"  # pending-review, never silently trusted
        assert rel["confidence"] in ("low", "medium", "high")
        assert rel["evidence_ids"] == ["ev-competitor-genetics-handwritten-notes-2026-09-15"]


def test_genetics_relationships_never_point_at_a_variety(relationships, entities):
    """Provider-level notes must not generate invented Variety records --
    every seeded genetics relationship's object must be a company or brand,
    never a variety entity."""
    by_id = {e["id"]: e for e in entities}
    for rel in relationships:
        if rel.get("predicate") != "partners_with":
            continue
        if not rel["id"].startswith("rel-") or "genetics" not in rel["id"]:
            continue
        obj = by_id.get(rel["object_id"])
        if obj:
            assert obj["entity_type"] != "variety", rel["id"]


def test_company_to_genetics_provider_lookup_is_bidirectional(relationships, entities):
    outgoing = genetics_relationships_for_company(
        "company-agroberries", relationships=relationships, entities=entities
    )
    assert any(r["other_entity_id"] == "company-mountain-blue-orchards" and r["direction"] == "outgoing" for r in outgoing)

    incoming = companies_for_genetics_provider(
        "company-mountain-blue-orchards", relationships=relationships, entities=entities
    )
    assert any(r["other_entity_id"] == "company-agroberries" for r in incoming)


def test_no_invented_variety_from_provider_level_mapping(entities):
    """None of the three seeded genetics relationships' subjects/objects
    should have caused a new Variety entity to appear -- this mission
    created zero files under data/entities/varieties/."""
    variety_ids = {e["id"] for e in entities if e.get("entity_type") == "variety"}
    for suspicious in ("variety-mountain-blue-orchards", "variety-fall-creek", "variety-mbo"):
        assert suspicious not in variety_ids


# ---------------------------------------------------------------------------
# Handwritten transcription -- ambiguity handling
# ---------------------------------------------------------------------------


def test_transcription_seeded_and_withheld_counts_are_consistent(transcription):
    seeded = [r for r in transcription["rows"] if r["seeded"]]
    withheld = [r for r in transcription["rows"] if not r["seeded"]]
    assert transcription["seeded_count"] == len(seeded) == 3
    assert transcription["withheld_count"] == len(withheld)
    assert len(seeded) + len(withheld) == transcription["row_count"]


def test_explicit_question_marks_stay_withheld_never_resolved(transcription):
    for row in transcription["rows"]:
        if "??" in row["visible_text"]:
            assert row["seeded"] is False, row["visible_text"]


def test_self_mappings_never_produce_a_relationship(transcription, relationships):
    self_mapping_rows = [r for r in transcription["rows"] if "self-mapping" in r["inferred_relationship"]]
    assert len(self_mapping_rows) >= 5  # Hortifrut, Planasa, Fall Creek, MBO, Plant Sciences, Ozblu
    relationship_ids = {r["id"] for r in relationships}
    for row in self_mapping_rows:
        assert row["seeded"] is False
        implied_id_fragment = (row["company_entity_id"] or "").replace("company-", "").replace("brand-", "")
        assert f"rel-{implied_id_fragment}-genetics-{implied_id_fragment}" not in relationship_ids


def test_out_of_roster_names_are_not_promoted_to_entities(transcription, entities):
    entity_ids = {e["id"] for e in entities}
    out_of_scope_labels = ["Dole", "Inka Berries", "Family Tree", "Fresc Kampo", "Water Fresh Farms", "Good Farms"]
    for label in out_of_scope_labels:
        guessed_id = "company-" + label.lower().replace(" ", "-")
        assert guessed_id not in entity_ids, f"{label} should not have been silently created as {guessed_id}"


def test_unresolved_queue_file_exists_and_matches_withheld_rows(transcription):
    queue = _load_json(IMPORT_DIR / "unresolved-mapping-queue.json")
    withheld = [r for r in transcription["rows"] if not r["seeded"]]
    assert queue["count"] == len(withheld)


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------


def test_provenance_evidence_records_exist_and_are_not_trusted(entities):
    evidence_dir = DATA_DIR / "evidence"
    spreadsheet_evidence = _load_json(evidence_dir / "ev-competitor-registry-2026-09-15-import.json")
    handwritten_evidence = _load_json(evidence_dir / "ev-competitor-genetics-handwritten-notes-2026-09-15.json")
    for evidence in (spreadsheet_evidence, handwritten_evidence):
        assert evidence["status"] == "in_review"  # never "published" -- an internal, unverified import
        assert evidence["submitted_by"] == "operator-import"
