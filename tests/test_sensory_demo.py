"""Simulated ratings retain real typed identities without entering the canonical model."""
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
import shutil

import pytest

from app.services import sensory_demo as demo
from app.services import investigation_export as export


def _copy_brand_identities(data_dir):
    """Copy only the fixture's six typed identity records into a runtime tree."""
    fixture = json.loads(demo.DEMO_PATH.read_text(encoding="utf-8"))
    source = Path(__file__).resolve().parents[1] / "data" / "entities"
    for profile in fixture["brand_profiles"]:
        ref = profile["canonical_entity"]
        folder = "companies" if ref["type"] == "company" else "brands"
        destination = data_dir / "entities" / folder / (ref["id"] + ".json")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / folder / destination.name, destination)
    return fixture


@pytest.mark.parametrize("explicit_data", [None, ""])
def test_fixture_and_export_use_runtime_data_with_no_explicit_data_dir(tmp_path, monkeypatch, explicit_data):
    runtime = tmp_path / "runtime"
    fixture = _copy_brand_identities(runtime / "data")
    monkeypatch.setenv("BIOS_RUNTIME_DIR", str(runtime))
    if explicit_data is None:
        monkeypatch.delenv("BIOS_DATA_DIR", raising=False)
    else:
        monkeypatch.setenv("BIOS_DATA_DIR", explicit_data)

    assert demo.load_fixture() == fixture
    assert export._load_demo() == fixture

    # A missing runtime identity must not silently resolve against repo/data.
    (runtime / "data/entities/brands/brand-fruitist.json").unlink()
    for loader in (demo.load_fixture, export._load_demo):
        with pytest.raises(ValueError, match="isolated synthetic fixture"):
            loader()


def test_explicit_data_dir_takes_precedence_over_runtime_for_fixture_and_export(tmp_path, monkeypatch):
    selected_data = tmp_path / "selected-data"
    fixture = _copy_brand_identities(selected_data)
    monkeypatch.setenv("BIOS_DATA_DIR", str(selected_data))
    monkeypatch.setenv("BIOS_RUNTIME_DIR", str(tmp_path / "missing-runtime"))

    assert demo.load_fixture() == fixture
    assert export._load_demo() == fixture


def test_invalid_explicit_data_dir_does_not_fall_back_to_runtime_or_repo(tmp_path, monkeypatch):
    runtime = tmp_path / "runtime"
    _copy_brand_identities(runtime / "data")
    selected_data = tmp_path / "selected-data"
    _copy_brand_identities(selected_data)
    invalid = selected_data / "entities/brands/brand-fruitist.json"
    record = json.loads(invalid.read_text(encoding="utf-8"))
    record["entity_type"] = "company"
    invalid.write_text(json.dumps(record), encoding="utf-8")
    monkeypatch.setenv("BIOS_DATA_DIR", str(selected_data))
    monkeypatch.setenv("BIOS_RUNTIME_DIR", str(runtime))

    for loader in (demo.load_fixture, export._load_demo):
        with pytest.raises(ValueError, match="isolated synthetic fixture"):
            loader()


def test_explicit_entities_dir_still_overrides_environment(tmp_path, monkeypatch):
    selected_data = tmp_path / "selected-data"
    fixture = _copy_brand_identities(selected_data)
    monkeypatch.setenv("BIOS_DATA_DIR", str(tmp_path / "missing-data"))
    monkeypatch.setenv("BIOS_RUNTIME_DIR", str(tmp_path / "missing-runtime"))

    assert demo.load_fixture(entities_dir=selected_data / "entities") == fixture


def test_brand_fixture_keeps_typed_references_and_legacy_saved_ids():
    fixture = demo.load_fixture()
    assert [(row["id"], row["value"]) for row in fixture["specimens"]] == [
        ("demo-specimen-amber", 5.8), ("demo-specimen-birch", 6.4), ("demo-specimen-clover", 4.6),
        ("demo-specimen-dune", 7.0), ("demo-specimen-elm", 5.2), ("demo-specimen-fern", 6.1)]
    assert [(row["id"], row["canonical_entity"]) for row in fixture["brand_profiles"]] == [
        ("demo-brand-driscolls", {"type": "company", "id": "company-driscolls"}),
        ("demo-brand-fruitist", {"type": "brand", "id": "brand-fruitist"}),
        ("demo-brand-ozblu", {"type": "brand", "id": "brand-ozblu"}),
        ("demo-brand-naturipe", {"type": "company", "id": "company-naturipe-farms"}),
        ("demo-brand-wish-farms", {"type": "company", "id": "company-wish-farms"}),
        ("demo-brand-california-giant", {"type": "company", "id": "company-california-giant-berry-farms"})]
    for row in fixture["brand_profiles"]:
        assert row["synthetic"] and row["label"] == "SIMULATED · " + row["brand_label"]
        assert "simulated sensory value" in row["identity_basis"]["note"]
        assert set(row["values"]) == set(demo.METRIC_IDS)
        assert all(4 <= value <= 8 and Decimal(str(value)).as_tuple().exponent >= -2 for value in row["values"].values())
    intensity = fixture["metrics"][:-1]
    assert all((row["scale_type"], row["minimum_label"], row["maximum_label"]) == ("intensity", "Very low", "Very high") for row in intensity)
    liking = fixture["metrics"][-1]
    assert (liking["id"], liking["scale_type"], liking["minimum_label"], liking["maximum_label"]) == (
        "overall_liking", "hedonic", "Dislike extremely", "Like extremely")


@pytest.mark.parametrize("value", [True, "6.4", 3.99, 8.01, 6.123, float("nan"), float("inf")])
def test_brand_demo_rejects_nonfixture_or_precision_ambiguous_values(value):
    fixture = demo.load_fixture()
    fixture["brand_profiles"][0]["values"]["sweetness"] = value
    with pytest.raises(ValueError, match="isolated synthetic fixture"):
        demo.validate_fixture(fixture)


def test_intensity_cannot_silently_become_a_liking_scale_or_a_company_a_brand():
    fixture = demo.load_fixture()
    fixture["metrics"][0]["maximum_label"] = "Like extremely"
    with pytest.raises(ValueError, match="isolated synthetic fixture"):
        demo.validate_fixture(fixture)
    fixture = demo.load_fixture()
    fixture["brand_profiles"][0]["canonical_entity"]["type"] = "brand"
    with pytest.raises(ValueError, match="isolated synthetic fixture"):
        demo.validate_fixture(fixture)


def test_selected_fixture_preserves_namespaces_membership_and_does_not_mutate():
    fixture = demo.load_fixture()
    before = deepcopy(fixture)
    result = demo.selected_fixture(fixture, ["demo-specimen-amber", "demo-brand-wish-farms"])
    assert [row["id"] for row in result["specimens"]] == ["demo-specimen-amber"]
    assert [row["id"] for row in result["brand_profiles"]] == ["demo-brand-wish-farms"]
    result["brand_profiles"][0]["values"]["aroma"] = 4
    assert fixture == before
    complete = demo.selected_fixture(fixture, [])
    assert len(complete["specimens"]) == len(complete["brand_profiles"]) == 6
    for selected in (["company-driscolls"], ["demo-brand-unavailable"], ["demo-brand-../other"]):
        with pytest.raises(ValueError, match="selected demo specimens are unavailable"):
            demo.selected_fixture(fixture, selected)


def test_loading_and_selecting_is_readonly_for_fixture_and_canonical_identities():
    root = Path(__file__).resolve().parents[1]
    files = [demo.DEMO_PATH, root / "data/entities/companies/company-driscolls.json", root / "data/entities/brands/brand-fruitist.json"]
    before = {file: file.read_bytes() for file in files}
    fixture = demo.load_fixture()
    demo.selected_fixture(fixture, ["demo-brand-driscolls", "demo-brand-fruitist"])
    assert all(file.read_bytes() == value for file, value in before.items())
