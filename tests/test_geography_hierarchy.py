"""Geographic Intelligence Resolution V1.

app.services.geography_hierarchy reads ONLY explicit, stored "part_of"
Relationship records -- never infers containment from entity names,
attributes.region text, or ISO codes at query time. These tests cover
the resolver module directly (descendants/ancestors/cycle-safety/
provenance) and scripts/generate_geography_containment.py's own
validation (idempotency, cycle rejection, conflicting-parent
preservation, missing-entity skip).
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.geography_hierarchy import (
    geography_ancestors,
    geography_descendants,
    geography_scope_match,
    matched_geography_ids,
    resolve_geography_scope,
)


def _rel(subject_id: str, predicate: str, object_id: str, *, status: str = "active") -> dict:
    return {
        "id": f"rel-{subject_id}-{predicate}-{object_id}",
        "record_type": "relationship",
        "subject_id": subject_id,
        "predicate": predicate,
        "object_id": object_id,
        "status": status,
        "evidence_ids": ["ev-fixture"],
    }


_FLAT_RELATIONSHIPS = [
    _rel("geography-spain", "part_of", "geography-europe"),
    _rel("geography-portugal", "part_of", "geography-europe"),
    _rel("geography-united-states", "part_of", "geography-north-america"),
    # Non-containment predicate involving geographies must never be
    # treated as hierarchy.
    _rel("company-acme", "operates_in", "geography-spain"),
]


# --- 1-7. Resolver correctness ----------------------------------------


def test_europe_descendants_include_spain_and_portugal():
    descendants = geography_descendants("geography-europe", relationships=_FLAT_RELATIONSHIPS)
    assert descendants == {"geography-spain", "geography-portugal"}


def test_direct_europe_still_in_all_ids():
    scope = resolve_geography_scope("geography-europe", relationships=_FLAT_RELATIONSHIPS)
    assert "geography-europe" in scope.all_ids


def test_unrelated_geography_excluded_from_descendants():
    descendants = geography_descendants("geography-europe", relationships=_FLAT_RELATIONSHIPS)
    assert "geography-morocco" not in descendants
    assert "geography-united-states" not in descendants


def test_child_query_does_not_include_siblings():
    scope = resolve_geography_scope("geography-spain", relationships=_FLAT_RELATIONSHIPS)
    assert scope.all_ids == {"geography-spain"}
    assert "geography-portugal" not in scope.all_ids


def test_operates_in_predicate_never_treated_as_containment():
    # company-acme operates_in geography-spain must never make
    # company-acme a "descendant" of Spain, or vice versa give Spain any
    # relationship to company-acme as if it were geographic containment.
    descendants = geography_descendants("geography-spain", relationships=_FLAT_RELATIONSHIPS)
    assert descendants == set()


def test_missing_hierarchy_resolves_to_direct_only():
    scope = resolve_geography_scope("geography-morocco", relationships=_FLAT_RELATIONSHIPS)
    assert scope.all_ids == {"geography-morocco"}
    assert scope.descendant_ids == frozenset()


def test_ancestors_walk_is_reverse_of_descendants():
    ancestors = geography_ancestors("geography-spain", relationships=_FLAT_RELATIONSHIPS)
    assert ancestors == {"geography-europe"}
    assert geography_ancestors("geography-europe", relationships=_FLAT_RELATIONSHIPS) == set()


def test_geography_scope_match_rejects_americas_majority_with_stray_europe_tag():
    europe = {"geography-europe", "geography-united-kingdom", "geography-spain"}
    assert geography_scope_match(
        ["geography-peru", "geography-mexico", "geography-united-kingdom"],
        europe,
    ) is False
    assert geography_scope_match(["geography-spain"], europe) is True
    assert geography_scope_match(["geography-united-kingdom"], europe) is True
    assert geography_scope_match(["geography-spain", "geography-peru"], europe) is False


# --- 8. Cycle safety -----------------------------------------------------


def test_descendant_walk_is_cycle_safe():
    cyclic = [
        _rel("geography-a", "part_of", "geography-b"),
        _rel("geography-b", "part_of", "geography-a"),
    ]
    # Must terminate and return a bounded, sane result rather than
    # looping forever or raising.
    result = geography_descendants("geography-a", relationships=cyclic)
    assert result <= {"geography-a", "geography-b"}


def test_ancestor_walk_is_cycle_safe():
    cyclic = [
        _rel("geography-a", "part_of", "geography-b"),
        _rel("geography-b", "part_of", "geography-a"),
    ]
    result = geography_ancestors("geography-a", relationships=cyclic)
    assert result <= {"geography-a", "geography-b"}


# --- 13. Provenance --------------------------------------------------------


def test_matched_geography_ids_shows_actual_linked_geography_not_query_geography():
    record = {"id": "ev-1", "geography_ids": ["geography-spain"], "entity_ids": []}
    scope_ids = frozenset({"geography-europe", "geography-spain", "geography-portugal"})
    matched = matched_geography_ids(record, scope_ids)
    assert matched == ("geography-spain",)
    assert "geography-europe" not in matched


def test_matched_geography_ids_checks_entity_ids_too():
    record = {"id": "ev-2", "geography_ids": [], "entity_ids": ["geography-portugal", "company-x"]}
    matched = matched_geography_ids(record, frozenset({"geography-portugal"}))
    assert matched == ("geography-portugal",)


# --- Migration script: authoring, idempotency, validation ------------------


def _seed_geography(tmp_path: Path, geography_id: str, name: str) -> None:
    path = tmp_path / "entities" / "geographies" / f"{geography_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "id": geography_id, "record_type": "entity", "entity_type": "geography",
                "name": name, "aliases": [], "status": "active", "description": "",
                "roles": [], "berry_ids": [], "evidence_ids": [], "fact_ids": [],
                "relationship_ids": [], "attributes": {},
            }
        ),
        encoding="utf-8",
    )


def _seed_data_dir(tmp_path: Path) -> Path:
    data_dir = tmp_path / "data"
    (data_dir / "evidence").mkdir(parents=True)
    (data_dir / "relationships").mkdir(parents=True)
    _seed_geography(data_dir, "geography-testland", "Testland")
    _seed_geography(data_dir, "geography-testcontinent", "Testcontinent")
    return data_dir


def test_migration_script_authors_valid_relationship(tmp_path: Path, monkeypatch):
    from scripts import generate_geography_containment as migration

    data_dir = _seed_data_dir(tmp_path)
    monkeypatch.setattr(migration, "COUNTRY_TO_CONTINENT", {"geography-testland": "geography-testcontinent"})
    result = migration.run(data_dir=data_dir, dry_run=False)
    assert result["written_relationships"] == ["rel-testland-part-of-testcontinent"]
    rel_path = data_dir / "relationships" / "rel-testland-part-of-testcontinent.json"
    assert rel_path.is_file()
    record = json.loads(rel_path.read_text(encoding="utf-8"))
    assert record["predicate"] == "part_of"
    assert record["subject_id"] == "geography-testland"
    assert record["object_id"] == "geography-testcontinent"
    assert record["evidence_ids"]  # never empty -- schema requires minItems 1
    evidence_path = data_dir / "evidence" / f"{migration.REFERENCE_EVIDENCE_ID}.json"
    assert evidence_path.is_file()


def test_migration_script_is_idempotent(tmp_path: Path, monkeypatch):
    from scripts import generate_geography_containment as migration

    data_dir = _seed_data_dir(tmp_path)
    monkeypatch.setattr(migration, "COUNTRY_TO_CONTINENT", {"geography-testland": "geography-testcontinent"})
    migration.run(data_dir=data_dir, dry_run=False)
    second = migration.run(data_dir=data_dir, dry_run=False)
    assert second["written_relationships"] == []
    assert second["skipped_existing"] == [("geography-testland", "geography-testcontinent")]
    rel_files = list((data_dir / "relationships").glob("rel-testland-part-of-*.json"))
    assert len(rel_files) == 1


def test_migration_script_skips_when_target_entity_missing(tmp_path: Path, monkeypatch):
    from scripts import generate_geography_containment as migration

    data_dir = _seed_data_dir(tmp_path)
    monkeypatch.setattr(migration, "COUNTRY_TO_CONTINENT", {"geography-testland": "geography-nonexistent"})
    result = migration.run(data_dir=data_dir, dry_run=False)
    assert result["written_relationships"] == []
    assert result["skipped_missing_entity"] == [("geography-testland", "geography-nonexistent")]


def test_migration_script_preserves_existing_conflicting_parent(tmp_path: Path, monkeypatch):
    from scripts import generate_geography_containment as migration

    data_dir = _seed_data_dir(tmp_path)
    _seed_geography(data_dir, "geography-otherparent", "Other Parent")
    existing = migration._relationship("geography-testland", "geography-otherparent")
    (data_dir / "relationships" / f"{existing['id']}.json").write_text(json.dumps(existing), encoding="utf-8")
    (data_dir / "evidence" / f"{migration.REFERENCE_EVIDENCE_ID}.json").write_text(
        json.dumps(migration._reference_evidence(["geography-testland", "geography-otherparent"], [existing["id"]])),
        encoding="utf-8",
    )
    monkeypatch.setattr(migration, "COUNTRY_TO_CONTINENT", {"geography-testland": "geography-testcontinent"})
    result = migration.run(data_dir=data_dir, dry_run=False)
    assert result["written_relationships"] == []
    assert result["rejected_conflicting_parent"] == [("geography-testland", "geography-testcontinent", "geography-otherparent")]
    # The pre-existing edge must be untouched.
    reloaded = json.loads((data_dir / "relationships" / f"{existing['id']}.json").read_text(encoding="utf-8"))
    assert reloaded["object_id"] == "geography-otherparent"


def test_migration_script_rejects_cycle(tmp_path: Path, monkeypatch):
    from scripts import generate_geography_containment as migration

    data_dir = _seed_data_dir(tmp_path)
    existing = migration._relationship("geography-testcontinent", "geography-testland")
    (data_dir / "relationships" / f"{existing['id']}.json").write_text(json.dumps(existing), encoding="utf-8")
    (data_dir / "evidence" / f"{migration.REFERENCE_EVIDENCE_ID}.json").write_text(
        json.dumps(migration._reference_evidence(["geography-testland", "geography-testcontinent"], [existing["id"]])),
        encoding="utf-8",
    )
    monkeypatch.setattr(migration, "COUNTRY_TO_CONTINENT", {"geography-testland": "geography-testcontinent"})
    result = migration.run(data_dir=data_dir, dry_run=False)
    assert result["written_relationships"] == []
    assert result["rejected_cycle"] == [("geography-testland", "geography-testcontinent")]


# --- 15. Existing Geography workspace backward compatibility ---------------
# This mission does not modify geography_workspace.py -- these are
# regression guards, not new-behavior tests, over the real deployed
# corpus (which now has real part_of relationships from the migration
# script run against data/).


def test_geography_workspace_europe_page_still_renders():
    client = TestClient(app)
    page = client.get("/geographies/geography-europe")
    assert page.status_code == 200


def test_geography_workspace_spain_page_still_renders_and_links_region():
    client = TestClient(app)
    page = client.get("/geographies/geography-spain")
    assert page.status_code == 200
    assert "Europe" in page.text


def test_geography_index_page_still_renders():
    client = TestClient(app)
    page = client.get("/geographies")
    assert page.status_code == 200
