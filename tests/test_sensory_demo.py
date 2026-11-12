"""Simulated ratings retain real typed identities without entering the canonical model."""
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

import pytest

from app.services import sensory_demo as demo


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
