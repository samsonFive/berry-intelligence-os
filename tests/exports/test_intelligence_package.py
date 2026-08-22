from __future__ import annotations

import json
from pathlib import Path
import shutil

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
    assert calls == list(FAMILIES)
