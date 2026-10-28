"""Bulk coverage must retain the single-profile photo identity/reuse gates."""
from copy import deepcopy
from datetime import date

import pytest

from app.services import variety_photos as photos


def catalog():
    return [
        {"id": "strawberry-keepsake", "name": "Keepsake", "berry_ids": ["berry-strawberry"]},
        {"id": "blueberry-keepsake", "name": "Keepsake", "berry_ids": ["berry-blueberry"]},
        {"id": "strawberry-other", "name": "Other Keepsake", "berry_ids": ["berry-strawberry"]},
    ]


def sources():
    photo = {"image_url": "https://example.org/fruit.jpg", "source_url": "https://example.org/keepsake",
             "credit": "Named publisher", "caption": "Keepsake fruit", "named_variety": "Keepsake",
             "berry_id": "berry-strawberry", "reuse": "unknown", "license_url": "", "reuse_note": "",
             "checked_on": date.today().isoformat(), "kind": "fruit"}
    return [{"id": "original-source", "company_ids": [], "names": [
        {"candidate_name": "Keepsake", "berry_id": "berry-strawberry", "photos": [photo]}]}]


@pytest.mark.parametrize("case", ["exact", "ambiguous", "code_conflict", "held", "duplicate"])
def test_bulk_lookup_retains_each_existing_profile_result(case):
    varieties, observed = catalog(), sources()
    if case == "ambiguous":
        varieties.append({**varieties[0], "id": "second-strawberry-keepsake"})
    elif case == "code_conflict":
        observed[0]["names"][0].update(breeder_code="ABC123", trade_name="Keepsake")
        observed.append({"id": "conflicting-source", "company_ids": [], "names": [
            {"candidate_name": "Keepsake", "berry_id": "berry-strawberry", "breeder_code": "XYZ456",
             "trade_name": "Keepsake"}]})
    elif case == "held":
        observed[0]["names"][0]["identity_notes"] = ["Name pairing needs review"]
    elif case == "duplicate":
        other = deepcopy(observed[0]); other["id"] = "second-source"
        other["names"][0]["photos"][0]["caption"] = "Later source caption"
        observed.append(other)
    original = deepcopy((varieties, observed))
    actual = photos.catalog_source_photos(sources=observed, varieties=varieties)
    assert actual == {v["id"]: photos.source_photos(v, sources=observed, varieties=varieties) for v in varieties}
    assert not actual["blueberry-keepsake"] and not actual["strawberry-other"]
    if case in {"ambiguous", "code_conflict", "held"}:
        assert not actual["strawberry-keepsake"]
    else:
        assert len(actual["strawberry-keepsake"]) == 1
        assert actual["strawberry-keepsake"][0]["reuse"] == "unknown"
        if case == "duplicate":
            assert actual["strawberry-keepsake"][0]["caption"] == "Later source caption"
    assert (varieties, observed) == original


def test_each_source_photo_is_validated_once_and_edits_apply_on_next_call(monkeypatch):
    varieties, observed = catalog(), sources()
    varieties += [{"id": f"unrelated-{n}", "name": f"Other berry {n}", "berry_ids": ["berry-strawberry"]}
                  for n in range(65)]
    validate, calls = photos.validate_photo, []
    def counted(raw):
        calls.append(raw["named_variety"])
        return validate(raw)
    monkeypatch.setattr(photos, "validate_photo", counted)
    first = photos.catalog_source_photos(sources=observed, varieties=varieties)
    assert calls == ["Keepsake"]
    first["strawberry-keepsake"][0]["caption"] = "Local display mutation"
    observed[0]["names"][0]["photos"][0]["caption"] = "Source edit"
    second = photos.catalog_source_photos(sources=observed, varieties=varieties)
    assert second["strawberry-keepsake"][0]["caption"] == "Source edit"
    varieties.append({**varieties[0], "id": "new-ambiguous-name"})
    assert not photos.catalog_source_photos(sources=observed, varieties=varieties)["strawberry-keepsake"]


def test_invalid_photo_fails_the_inventory_instead_of_disappearing():
    observed = sources()
    observed[0]["names"][0]["photos"][0]["image_url"] = "http://127.0.0.1/private-image"
    with pytest.raises(ValueError, match="public"):
        photos.catalog_source_photos(sources=observed, varieties=catalog())
    assert photos.catalog_source_photos(sources=observed, varieties=[]) == {}
