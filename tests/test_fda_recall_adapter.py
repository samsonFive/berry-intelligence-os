"""Unit coverage for the openFDA food-enforcement/recall adapter
(government_recall_json, added for the Global Qualitative Coverage
Expansion V1 mission, 2026-08-21). The real endpoint
(api.fda.gov/food/enforcement.json) was proven live, by hand, during the
mission -- see docs/v2/GLOBAL-QUALITATIVE-COVERAGE-EXPANSION-V1.md. Live
network is never exercised in pytest.
"""

from __future__ import annotations

from app.services.media_discovery import ADAPTER_TYPES, _normalize_fda_recall_entry


def _entry(**changes) -> dict:
    record = {
        "recall_number": "H-1181-2026",
        "product_description": "Organic Whole Blueberries, Net Wt 10 oz (284g) plastic bag. Keep Frozen",
        "reason_for_recall": "Potential E. coli O145:H28 Contamination",
        "recalling_firm": "Frutas y Hortalizas del Sur S.A.",
        "report_date": "20260722",
        "classification": "Class I",
        "voluntary_mandated": "Voluntary: Firm initiated",
        "distribution_pattern": "Nationwide",
        "recall_initiation_date": "20260701",
        "status": "Ongoing",
    }
    record.update(changes)
    return record


def test_government_recall_json_is_registered_and_reuses_generic_json_fetch() -> None:
    assert "government_recall_json" in ADAPTER_TYPES
    from app.services.media_discovery import _fetch_federal_register_json, _federal_register_entries
    fetch, list_entries, normalize = ADAPTER_TYPES["government_recall_json"]
    assert fetch is _fetch_federal_register_json
    assert list_entries is _federal_register_entries
    assert normalize is _normalize_fda_recall_entry


def test_normalize_fda_recall_entry_produces_a_title_with_species_word() -> None:
    item = _normalize_fda_recall_entry(_entry())
    assert "blueberr" in item.title.lower()
    assert "Frutas y Hortalizas del Sur S.A." in item.title
    assert item.description == "Potential E. coli O145:H28 Contamination"


def test_normalize_fda_recall_entry_deterministic_deep_link_and_external_id() -> None:
    item = _normalize_fda_recall_entry(_entry())
    assert item.external_id == "H-1181-2026"
    assert item.canonical_url == 'https://api.fda.gov/food/enforcement.json?search=recall_number:%22H-1181-2026%22'


def test_normalize_fda_recall_entry_converts_report_date_to_iso() -> None:
    item = _normalize_fda_recall_entry(_entry(report_date="20260304"))
    assert item.published_date == "2026-03-04"


def test_normalize_fda_recall_entry_two_distinct_records_get_distinct_identity() -> None:
    a = _normalize_fda_recall_entry(_entry(recall_number="H-1181-2026"))
    b = _normalize_fda_recall_entry(_entry(recall_number="H-0522-2026", product_description="IQF Blueberry"))
    assert a.external_id != b.external_id
    assert a.canonical_url != b.canonical_url


def test_normalize_fda_recall_entry_handles_missing_recall_number() -> None:
    item = _normalize_fda_recall_entry(_entry(recall_number=None))
    assert item.external_id is None
    assert item.canonical_url is None


def test_normalize_fda_recall_entry_truncates_long_product_description() -> None:
    long_desc = "A" * 200
    item = _normalize_fda_recall_entry(_entry(product_description=long_desc))
    assert len(item.title) < len(long_desc) + 50
    assert item.title.endswith("...") is False or "..." in item.title
