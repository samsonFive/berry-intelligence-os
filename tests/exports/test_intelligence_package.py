from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys

import pytest

from app.composition import get_repositories
from app.exports.intelligence_package import (
    FAMILIES,
    IntelligencePackageExporter,
    canonical_records,
    import_package,
    load_package_records,
    validate_package,
)
from app.repositories.paths import DEFAULT_DATA_DIR, SCHEMAS_DIR
from app.services.publication_scope import FAMILIES as PUBLIC_FAMILIES
from tests.repositories.test_json_repository_contract import (
    _assessment_record, _entity_record, _fact_record, _recommendation_record,
    _relationship_record, _signal_record,
)
from tests.repositories.test_memory_backend_consumers import seeded_memory


@pytest.fixture(scope="module")
def live_package(tmp_path_factory):
    output = tmp_path_factory.mktemp("intelligence-package") / "package"
    exporter = IntelligencePackageExporter(
        get_repositories(DEFAULT_DATA_DIR, SCHEMAS_DIR), SCHEMAS_DIR,
        generated_on="2026-08-14T12:00:00Z",
    )
    manifest = exporter.export(output)
    return output, manifest, exporter


def test_package_manifest_structure_families_order_and_no_drafts(live_package) -> None:
    output, manifest, _exporter = live_package
    assert manifest["package_version"] == "1.0.0"
    assert manifest["format"] == "json"
    assert manifest["review_state_included"] == ["published", "proposed"]
    assert manifest["exclusions"]["entity"]["count"] == 5
    assert manifest["exclusions"]["evidence"]["count"] == 3
    records = load_package_records(output)
    assert set(records) == set(FAMILIES)
    assert all([record["id"] for record in values] == sorted(record["id"] for record in values) for values in records.values())
    assert all(record.get("status") == "published" for record in records["evidence"])
    assert not (output / "inbox").exists()
    assert manifest["counts"]["source"] == len(records["sources"])


def test_export_is_content_deterministic(live_package, tmp_path: Path) -> None:
    first, first_manifest, exporter = live_package
    second = tmp_path / "second"
    second_manifest = exporter.export(second)
    assert first_manifest == second_manifest
    assert load_package_records(first) == load_package_records(second)
    assert (first / "source-lineage.json").read_bytes() == (second / "source-lineage.json").read_bytes()


def test_lineage_and_validator_accept_live_export(live_package) -> None:
    output, _manifest, _exporter = live_package
    lineage = json.loads((output / "source-lineage.json").read_text())
    assert lineage["chains"]
    assert all(not values for values in lineage["orphan_check"].values())
    assert validate_package(output, SCHEMAS_DIR) == []


def test_validator_detects_intentional_dangling_reference(live_package, tmp_path: Path) -> None:
    source, _manifest, _exporter = live_package
    output = tmp_path / "damaged"
    shutil.copytree(source, output)
    fact_path = next((output / "facts").glob("*.json"))
    fact = json.loads(fact_path.read_text())
    fact["evidence_ids"] = ["ev-intentionally-missing"]
    fact_path.write_text(json.dumps(fact, indent=2) + "\n")
    errors = validate_package(output, SCHEMAS_DIR)
    assert "source-lineage.json does not match package records" in errors
    assert "orphan_check is not empty" in errors


def test_export_round_trips_all_supported_content_through_fresh_repositories(live_package, tmp_path: Path) -> None:
    output, _manifest, exporter = live_package
    fresh = get_repositories(tmp_path / "fresh-data", SCHEMAS_DIR)
    import_package(output, fresh)
    imported = canonical_records({family: getattr(fresh, family).list() for family in FAMILIES})
    expected, _exclusions = exporter.collect()
    assert imported == canonical_records(expected)


def test_exporter_reads_core_data_only_via_repository_interfaces(tmp_path: Path) -> None:
    real = get_repositories(DEFAULT_DATA_DIR, SCHEMAS_DIR)
    calls = []

    class Spy:
        def __getattr__(self, name):
            repository = getattr(real, name)
            return type("RepoSpy", (), {"list": lambda self, n=name, r=repository: calls.append(n) or r.list()})()

    IntelligencePackageExporter(Spy(), SCHEMAS_DIR, generated_on="2026-08-14T12:00:00Z").export(tmp_path / "package")
    assert set(FAMILIES).issubset(calls)
    assert set(calls).issubset(PUBLIC_FAMILIES)
    assert len(calls) == len(set(calls))


@pytest.fixture
def repositories_with_private_support():
    repositories, entity, evidence, fact = seeded_memory()
    private_entity = {**_entity_record("private"), "publication_scope": "private", "name": "PRIVATE ENTITY CANARY"}
    private_source = {**repositories.sources.list()[0], "id": "source-private-package", "publication_scope": "private"}
    private_evidence = {**evidence, "id": "ev-private-package", "publication_scope": "private",
                        "title": "PRIVATE SOURCE CANARY", "summary": "PRIVATE BODY CANARY",
                        "source_id": private_source["id"], "entity_ids": [private_entity["id"]]}
    private_fact = {**_fact_record("private"), "publication_scope": "private",
                    "statement": "PRIVATE FACT CANARY", "evidence_ids": [private_evidence["id"]]}
    mixed_fact = {**_fact_record("mixed"), "statement": "MIXED SUPPORT CANARY",
                  "evidence_ids": [evidence["id"], private_evidence["id"]]}
    relationship = {**_relationship_record("private"), "subject_id": entity["id"],
                    "object_id": private_entity["id"], "evidence_ids": [private_evidence["id"]]}
    assessment = {**_assessment_record("private"), "fact_ids": [mixed_fact["id"]]}
    recommendation = {**_recommendation_record("private"), "assessment_ids": [assessment["id"]]}
    signal = {**_signal_record("private"), "evidence_ids": [evidence["id"], private_evidence["id"]]}
    repositories.entities.create(private_entity)
    repositories.sources.create(private_source)
    repositories.evidence.create(private_evidence)
    repositories.facts.create_many([private_fact, mixed_fact])
    repositories.relationships.create(relationship)
    repositories.assessments.create(assessment)
    repositories.recommendations.create(recommendation)
    repositories.signals.create(signal)
    repositories.entities.update(entity["id"], {**entity,
        "evidence_ids": [evidence["id"], private_evidence["id"]],
        "fact_ids": [fact["id"], private_fact["id"], mixed_fact["id"]],
        "relationship_ids": [relationship["id"]],
        "attributes": {**entity["attributes"], "private_link": "/intelligence/" + private_evidence["id"]}})
    private_ids = {row["id"] for row in (private_entity, private_source, private_evidence, private_fact,
                                           mixed_fact, relationship, assessment, recommendation, signal)}
    return repositories, private_ids


def assert_public_package(output: Path, private_ids: set[str]) -> None:
    materialized = "\n".join(path.read_text(encoding="utf-8") for path in output.rglob("*.json"))
    assert all(key not in materialized for key in private_ids)
    assert "CANARY" not in materialized
    records = load_package_records(output)
    assert [row["id"] for row in records["evidence"]] == ["ev-contract-test-a"]
    assert [row["id"] for row in records["facts"]] == ["fact-contract-test-a"]
    entity = next(row for row in records["entities"] if row["id"] == "company-contract-test-a")
    assert entity["evidence_ids"] == ["ev-contract-test-a"]
    assert entity["fact_ids"] == ["fact-contract-test-a"]
    assert records["assessments"] == records["recommendations"] == records["signals"] == []
    assert validate_package(output, SCHEMAS_DIR) == []


def test_public_package_withholds_private_reviewed_sources_transitive_conclusions_and_backlinks(
    repositories_with_private_support, tmp_path: Path,
) -> None:
    repositories, private_ids = repositories_with_private_support
    before = {family: getattr(repositories, family).list() for family in FAMILIES}
    output = tmp_path / "public-package"
    manifest = IntelligencePackageExporter(repositories, SCHEMAS_DIR).export(output)
    assert manifest["scope"]["filter"]["publication_scope"] == "public"
    assert_public_package(output, private_ids)
    assert {family: getattr(repositories, family).list() for family in FAMILIES} == before


def test_export_cli_uses_the_same_public_boundary(repositories_with_private_support, tmp_path: Path, monkeypatch) -> None:
    from scripts import export_intelligence_package

    repositories, private_ids = repositories_with_private_support
    output = tmp_path / "cli-package"
    monkeypatch.setattr(export_intelligence_package, "get_repositories", lambda *_args: repositories)
    monkeypatch.setattr(sys, "argv", ["export_intelligence_package.py", "--output", str(output)])
    assert export_intelligence_package.main() == 0
    assert_public_package(output, private_ids)


def test_reusing_exporter_takes_a_fresh_public_snapshot(tmp_path: Path) -> None:
    repositories, _entity, evidence, _fact = seeded_memory()
    exporter = IntelligencePackageExporter(repositories, SCHEMAS_DIR)
    assert exporter.collect()[0]["evidence"] == [evidence]
    repositories.evidence.update(evidence["id"], {**evidence, "publication_scope": "private"})
    records, _exclusions = exporter.collect()
    assert records["evidence"] == records["facts"] == []


@pytest.mark.parametrize("family", ["entities", "evidence", "facts"])
def test_validator_rejects_explicit_private_records(family: str, tmp_path: Path) -> None:
    repositories, _entity, _evidence, _fact = seeded_memory()
    output = tmp_path / "tampered"
    IntelligencePackageExporter(repositories, SCHEMAS_DIR).export(output)
    path = next((output / family).rglob("*.json"))
    record = json.loads(path.read_text(encoding="utf-8"))
    record["publication_scope"] = "private"
    path.write_text(json.dumps(record), encoding="utf-8")
    assert f"package includes non-public record: {family}:{record['id']}" in validate_package(output, SCHEMAS_DIR)
