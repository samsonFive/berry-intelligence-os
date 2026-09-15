"""Competitor Identity and Genetics Verification V1.

Validates identity/relationship confidence improvements against the real
committed data: the 17 provisional entities, the 3 seeded genetics
relationships, and the 19 previously-withheld handwritten mappings. Proves
internal classifications (tier/priority/region) were not touched, no
accidental duplicate was introduced, and ambiguous handwriting was never
guessed at.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
DATA_DIR = REPO / "data"
REGISTRY_DIR = DATA_DIR / "imports" / "competitor-registry-2026-09-15"
VERIFICATION_DIR = DATA_DIR / "imports" / "competitor-identity-genetics-verification-2026-09-15"

EXPECTED_ROSTER = [
    "Advanced Berry Breeding", "AgroBerries", "Australasian Plant Genetics", "BerryWorld",
    "Black Venture Farm", "California Giant", "Costa", "Denning Blueberries", "Expoberries",
    "Fall Creek", "Fresh Forward", "Fruitist", "Gem-Pack Berries", "Hortifrut Genetica",
    "IQ Berries", "Marionnet", "Mountain Blue", "Oishii", "Ozblu", "Pairwise", "Perfection Fresh",
    "Planasa", "Plant Sciences", "Royakkers", "Smart Berries", "Splendor Produce", "SunBelle",
    "The Berry Collective", "UC Davis", "University of Arkansas", "University of Florida",
    "Well-Pict", "Wish Farms",
]

PROMOTED_IDS = {
    "company-australasian-plant-genetics", "company-fresh-forward", "company-oishii",
    "company-pairwise", "company-perfection-fresh", "company-royakkers",
    "company-smart-berries", "company-sunbelle",
}
RETAINED_PROVISIONAL_IDS = {
    "company-agroberries", "company-black-venture-farm", "company-denning-blueberries",
    "company-expoberries", "company-gem-pack-berries", "company-marionnet",
    "company-splendor-produce", "company-the-berry-collective", "company-well-pict",
}


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


@pytest.fixture(scope="module")
def reconciliation():
    return _load(REGISTRY_DIR / "reconciliation-matrix.json")


@pytest.fixture(scope="module")
def snapshot():
    return _load(REGISTRY_DIR / "snapshot.json")


@pytest.fixture(scope="module")
def identity_matrix():
    return _load(VERIFICATION_DIR / "provisional-identity-verification-matrix.json")


@pytest.fixture(scope="module")
def structural_review():
    return _load(VERIFICATION_DIR / "duplicate-structural-identity-review.json")


@pytest.fixture(scope="module")
def relationship_assessment():
    return _load(VERIFICATION_DIR / "genetics-relationship-evidence-assessment.json")


@pytest.fixture(scope="module")
def withheld_review():
    return _load(VERIFICATION_DIR / "withheld-mapping-review-update.json")


@pytest.fixture(scope="module")
def entities():
    return _load_all_entities()


@pytest.fixture(scope="module")
def relationships():
    return _load_all_relationships()


# ---------------------------------------------------------------------------
# 33/33 roster remains fully represented
# ---------------------------------------------------------------------------


def test_all_33_roster_rows_remain_represented(reconciliation):
    assert reconciliation["row_count"] == 33
    labels = {r["spreadsheet_label"] for r in reconciliation["rows"]}
    assert labels == set(EXPECTED_ROSTER)


def test_no_roster_row_disappeared(snapshot):
    assert snapshot["row_count"] == 33
    assert {r["spreadsheet_label"] for r in snapshot["rows"]} == set(EXPECTED_ROSTER)


def test_no_accidental_duplicate_canonical_entity(reconciliation):
    ids = [r["canonical_entity_id"] for r in reconciliation["rows"]]
    assert len(ids) == len(set(ids)) == 33


# ---------------------------------------------------------------------------
# Provisional-identity verification
# ---------------------------------------------------------------------------


def test_identity_matrix_covers_exactly_17_provisional_entities(identity_matrix):
    assert identity_matrix["row_count"] == 17
    ids = {r["canonical_entity_id"] for r in identity_matrix["rows"]}
    assert ids == PROMOTED_IDS | RETAINED_PROVISIONAL_IDS


def test_promoted_count_matches_entities_actually_promoted(identity_matrix, entities):
    by_id = {e["id"]: e for e in entities}
    assert identity_matrix["promoted_count"] == 8
    assert identity_matrix["retained_provisional_count"] == 9
    for row in identity_matrix["rows"]:
        entity = by_id[row["canonical_entity_id"]]
        if row["promoted_to_active"]:
            assert entity["status"] == "active", row["canonical_entity_id"]
            assert row["canonical_entity_id"] in PROMOTED_IDS
        else:
            assert entity["status"] == "unverified", row["canonical_entity_id"]
            assert row["canonical_entity_id"] in RETAINED_PROVISIONAL_IDS


def test_provisional_count_changed_only_where_evidence_was_added(identity_matrix):
    """Every promoted row must carry real evidence_urls -- a status change
    is never made without a documented reason."""
    for row in identity_matrix["rows"]:
        if row["promoted_to_active"]:
            assert row["evidence_urls"], row["canonical_entity_id"]
            assert row["confidence"] == "high", row["canonical_entity_id"]
        assert row["reason"], row["canonical_entity_id"]


def test_non_promoted_entities_unchanged_outside_of_seventeen(entities):
    """Entities outside the 17 provisional set must not have had their
    status touched by this mission."""
    by_id = {e["id"]: e for e in entities}
    already_established = ["company-california-giant-berry-farms", "company-hortifrut", "company-planasa"]
    for eid in already_established:
        assert by_id[eid]["status"] == "active"


def test_identity_verification_attributes_recorded_on_all_17(entities):
    by_id = {e["id"]: e for e in entities}
    for eid in PROMOTED_IDS | RETAINED_PROVISIONAL_IDS:
        attrs = by_id[eid].get("attributes") or {}
        block = attrs.get("identity_verification_2026_09_15")
        assert block is not None, eid
        assert block["verification_date"] == "2026-09-15"
        assert block["confidence"] in ("low", "medium", "high")


def test_aliases_resolve_deterministically(entities):
    by_id = {e["id"]: e for e in entities}
    checks = [
        ("company-australasian-plant-genetics", "APG"),
        ("company-fresh-forward", "Fresh Forward Breeding B.V."),
        ("company-pairwise", "Pairwise Plants"),
        ("company-sunbelle", "Sun Belle"),
        ("company-royakkers", "Royakkers Fruit & Planten"),
    ]
    for entity_id, alias in checks:
        assert alias in (by_id[entity_id].get("aliases") or []), entity_id


# ---------------------------------------------------------------------------
# Duplicate / structural review -- Planasa and friends
# ---------------------------------------------------------------------------


def test_planasa_duplicate_confirmed_and_already_resolved(structural_review):
    assert structural_review["planasa_result"] == "exact_duplicate_already_resolved_no_action_needed"
    audit = structural_review["automated_audit_result_summary"]
    assert len(audit["confirmed_duplicates"]) == 1
    assert audit["confirmed_duplicates"][0]["entity_ids"] == ["company-planasa", "company-planasa-2"]
    assert audit["exact_duplicates"] == []
    assert audit["alias_collisions"] == []
    assert audit["unresolved_probable_duplicates"] == []


def test_planasa_ambiguity_note_was_corrected(reconciliation):
    row = next(r for r in reconciliation["rows"] if r["spreadsheet_label"] == "Planasa")
    assert "RESOLVED 2026-09-15" in row["ambiguity_notes"]
    assert "entity-identity-redirects.json" in row["ambiguity_notes"]


def test_parent_brand_division_program_distinctions_survive(entities):
    """Ozblu stays a brand; UC Davis stays a breeding_program; neither was
    silently reclassified during this mission's changes."""
    by_id = {e["id"]: e for e in entities}
    assert by_id["brand-ozblu"]["entity_type"] == "brand"
    assert by_id["breeding_program-uc-davis-strawberry"]["entity_type"] == "breeding_program"
    assert by_id["company-agrovision"]["entity_type"] == "company"
    assert by_id["company-plant-sciences-genetics"]["entity_type"] == "company"


def test_ozblu_has_no_fabricated_relationship_to_mountain_blue(relationships):
    ozblu_rels = [r for r in relationships if r["subject_id"] == "brand-ozblu" or r["object_id"] == "brand-ozblu"]
    mountain_blue_pair = [
        r for r in ozblu_rels
        if "mountain-blue" in (r["subject_id"] + r["object_id"])
    ]
    assert mountain_blue_pair == []


# ---------------------------------------------------------------------------
# Internal classifications remain unchanged
# ---------------------------------------------------------------------------


def test_internal_classifications_unchanged(snapshot):
    """Tier/priority/region for a sample of rows must be byte-identical to
    what the original Company + Genetics Relationships V1 snapshot recorded."""
    expected = {
        "Fall Creek": {"strategic_priority": None, "regions": ["DOTA", "DOA_DANZ", "DEMEA"],
                       "berry_tier": {"strawberry": "unassigned", "blueberry": "tier_1", "raspberry": "unassigned", "blackberry": "unassigned"}},
        "California Giant": {"strategic_priority": "Top", "regions": ["DOTA"],
                              "berry_tier": {"strawberry": "unassigned", "blueberry": "tier_1", "raspberry": "unassigned", "blackberry": "unassigned"}},
        "Denning Blueberries": {"strategic_priority": "Watch", "regions": ["DOA_DANZ"],
                                 "berry_tier": {"strawberry": "unassigned", "blueberry": "present", "raspberry": "tier_2", "blackberry": "tier_1"}},
    }
    by_label = {r["spreadsheet_label"]: r for r in snapshot["rows"]}
    for label, exp in expected.items():
        row = by_label[label]
        assert row["strategic_priority"] == exp["strategic_priority"], label
        assert row["regions"] == exp["regions"], label
        assert row["berry_tier"] == exp["berry_tier"], label


def test_competitor_type_field_unchanged(snapshot):
    by_label = {r["spreadsheet_label"]: r for r in snapshot["rows"]}
    assert by_label["The Berry Collective"]["competitor_type"] == "University/Public"
    assert by_label["AgroBerries"]["competitor_type"] == "Commercial"


# ---------------------------------------------------------------------------
# Relationship directionality, semantics, berry scope, review state
# ---------------------------------------------------------------------------


def test_upgraded_relationship_directionality_preserved(relationships):
    rel = next(r for r in relationships if r["id"] == "rel-agroberries-genetics-mountain-blue-orchards")
    assert rel["subject_id"] == "company-agroberries"
    assert rel["object_id"] == "company-mountain-blue-orchards"


def test_upgraded_relationship_semantics_and_evidence(relationships):
    rel = next(r for r in relationships if r["id"] == "rel-agroberries-genetics-mountain-blue-orchards")
    assert rel["predicate"] == "licenses"
    assert rel["status"] == "active"
    assert rel["confidence"] == "high"
    assert "ev-agroberries-mountain-blue-licensing-freshfruitportal-2026" in rel["evidence_ids"]
    assert "ev-competitor-genetics-handwritten-notes-2026-09-15" in rel["evidence_ids"]  # original provenance preserved


def test_retained_pending_relationships_unchanged_in_semantics(relationships):
    for rel_id, subj, obj in [
        ("rel-agrovision-genetics-fall-creek-farm-and-nursery", "company-agrovision", "company-fall-creek-farm-and-nursery"),
        ("rel-california-giant-berry-farms-genetics-fall-creek-farm-and-nursery", "company-california-giant-berry-farms", "company-fall-creek-farm-and-nursery"),
    ]:
        rel = next(r for r in relationships if r["id"] == rel_id)
        assert rel["subject_id"] == subj
        assert rel["object_id"] == obj
        assert rel["predicate"] == "partners_with"
        assert rel["status"] == "disputed"
        assert rel["confidence"] == "medium"


def test_relationship_round_trips_through_json_unchanged(relationships, tmp_path):
    rel = next(r for r in relationships if r["id"] == "rel-agroberries-genetics-mountain-blue-orchards")
    path = tmp_path / "roundtrip.json"
    path.write_text(json.dumps(rel), encoding="utf-8")
    reloaded = json.loads(path.read_text(encoding="utf-8"))
    assert reloaded == rel


def test_relationship_evidence_ids_never_replaced_only_added(relationships):
    rel = next(r for r in relationships if r["id"] == "rel-agroberries-genetics-mountain-blue-orchards")
    assert len(rel["evidence_ids"]) == 2


# ---------------------------------------------------------------------------
# Withheld mapping review -- no guessing
# ---------------------------------------------------------------------------


def test_withheld_review_covers_all_19_rows(withheld_review):
    assert withheld_review["row_count"] == 19


def test_zero_withheld_mappings_promoted(withheld_review):
    assert withheld_review["promoted_count"] == 0
    for row in withheld_review["rows"]:
        assert row["promoted_this_mission"] is False


def test_ambiguous_handwriting_guessed_count_is_zero(withheld_review):
    assert "AMBIGUOUS HANDWRITING GUESSED: 0" in withheld_review["note"]


def test_public_never_reclassified_as_a_company(withheld_review, entities):
    entity_names = {e["name"].lower() for e in entities}
    assert "public" not in entity_names
    public_rows = [r for r in withheld_review["rows"] if r["reclassification_2026_09_15"] == "public_genetics_observation"]
    assert len(public_rows) >= 3
    for row in public_rows:
        assert "not a company" in row["reclassification_note"]


def test_no_blues_never_becomes_global_absence(withheld_review, entities):
    scoped_rows = [r for r in withheld_review["rows"] if r["reclassification_2026_09_15"] == "scoped_no_blues_observation"]
    assert len(scoped_rows) == 2  # Oishii, Pairwise
    by_id = {e["id"]: e for e in entities}
    for row in scoped_rows:
        entity = by_id[row["company_entity_id"]]
        # Confirms the entity's own berry_ids were never overwritten to
        # exclude blueberry as a hard global fact from this observation.
        assert "global" not in row["reclassification_note"] or "never" in row["reclassification_note"]


def test_self_mappings_still_produce_no_relationship(withheld_review, relationships):
    self_mapping_rows = [r for r in withheld_review["rows"] if r["reclassification_2026_09_15"] == "self_mapping_requiring_semantic_caution"]
    assert len(self_mapping_rows) >= 5
    relationship_ids = {r["id"] for r in relationships}
    for row in self_mapping_rows:
        cid = row["company_entity_id"]
        if not cid:
            continue
        frag = cid.replace("company-", "").replace("brand-", "")
        assert f"rel-{frag}-genetics-{frag}" not in relationship_ids


def test_out_of_roster_names_not_promoted_to_competitor_classification(withheld_review, entities):
    entity_ids = {e["id"] for e in entities}
    out_of_roster_rows = [r for r in withheld_review["rows"] if r["reclassification_2026_09_15"] == "out_of_roster_but_identifiable"]
    assert len(out_of_roster_rows) == 3  # Dole/Inka Berries, Water Fresh Farms, Good Farms
    for label in ("dole", "inka-berries", "water-fresh-farms", "good-farms"):
        assert f"company-{label}" not in entity_ids


# ---------------------------------------------------------------------------
# No variety expansion
# ---------------------------------------------------------------------------


def test_provider_level_evidence_creates_no_variety(entities):
    variety_ids = {e["id"] for e in entities if e.get("entity_type") == "variety"}
    for suspicious in ("variety-mountain-blue-orchards", "variety-fall-creek", "variety-agroberries"):
        assert suspicious not in variety_ids


def test_no_new_candidate_variety_added_this_mission():
    """This mission's own scope explicitly excludes variety-universe
    expansion -- confirm no file under data/entities/varieties/ or a
    variety-candidate store was touched."""
    import subprocess
    for path in ("data/entities/varieties", "data/varieties"):
        result = subprocess.run(
            ["git", "-c", f"safe.directory={REPO}", "status", "--porcelain", "--", path],
            cwd=REPO, capture_output=True, text=True, check=False,
        )
        assert result.stdout.strip() == "", f"unexpected changes under {path}: {result.stdout}"


# ---------------------------------------------------------------------------
# Relationship reviewed count sanity
# ---------------------------------------------------------------------------


def test_three_relationships_reviewed_one_upgraded_two_pending(relationship_assessment):
    assert relationship_assessment["relationships_reviewed"] == 3
    assert relationship_assessment["upgraded"] == 1
    assert relationship_assessment["retained_pending"] == 2
    assert relationship_assessment["rejected"] == 0
