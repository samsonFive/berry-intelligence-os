"""Unit coverage for the UK Food Standards Agency food-alerts adapter
(government_alert_json, added for the Global Qualitative Coverage
Expansion V2 mission, 2026-08-22). The real endpoint
(data.food.gov.uk/food-alerts) was proven live, by hand, during the
mission -- see docs/v2/GLOBAL-QUALITATIVE-COVERAGE-EXPANSION-V2.md. Live
network is never exercised in pytest.
"""

from __future__ import annotations

from app.services.media_discovery import ADAPTER_TYPES, _normalize_uk_fsa_entry, _uk_fsa_entries


def _entry(**changes) -> dict:
    record = {
        "notation": "FSA-PRIN-12-2026",
        "title": "Tesco recalls Tesco Grape & Berry Medley because of contamination with salmonella",
        "description": "Tesco is recalling Tesco Grape & Berry Medley because salmonella has been found in the product.",
        "created": "2026-02-16",
        "modified": "2026-02-16T21:14:53.556Z",
        "alertURL": "https://alerts.food.gov.uk/news-alerts/alert/fsa-prin-12-2026",
        "type": ["http://data.food.gov.uk/food-alerts/def/Alert", "http://data.food.gov.uk/food-alerts/def/PRIN"],
        "reportingBusiness": {"commonName": "Tesco"},
    }
    record.update(changes)
    return record


def test_government_alert_json_is_registered_and_reuses_generic_json_fetch() -> None:
    assert "government_alert_json" in ADAPTER_TYPES
    from app.services.media_discovery import _fetch_federal_register_json
    fetch, list_entries, normalize = ADAPTER_TYPES["government_alert_json"]
    assert fetch is _fetch_federal_register_json
    assert list_entries is _uk_fsa_entries
    assert normalize is _normalize_uk_fsa_entry


def test_uk_fsa_entries_reads_items_key_not_results() -> None:
    parsed = {"items": [_entry(), _entry(notation="FSA-PRIN-13-2026")]}
    assert len(_uk_fsa_entries(parsed)) == 2
    assert _uk_fsa_entries({"results": [_entry()]}) == []  # wrong key on purpose
    assert _uk_fsa_entries(None) == []


def test_normalize_uk_fsa_entry_keeps_real_title_and_species_word() -> None:
    item = _normalize_uk_fsa_entry(_entry())
    assert "berr" in item.title.lower()
    assert item.description.startswith("Tesco is recalling")


def test_normalize_uk_fsa_entry_uses_real_alert_url_and_notation() -> None:
    item = _normalize_uk_fsa_entry(_entry())
    assert item.external_id == "FSA-PRIN-12-2026"
    assert item.canonical_url == "https://alerts.food.gov.uk/news-alerts/alert/fsa-prin-12-2026"
    assert item.published_date == "2026-02-16"


def test_normalize_uk_fsa_entry_two_distinct_alerts_get_distinct_identity() -> None:
    a = _normalize_uk_fsa_entry(_entry(notation="FSA-PRIN-12-2026"))
    b = _normalize_uk_fsa_entry(_entry(
        notation="FSA-PRIN-13-2026", title="A different recall",
        alertURL="https://alerts.food.gov.uk/news-alerts/alert/fsa-prin-13-2026",
    ))
    assert a.external_id != b.external_id
    assert a.canonical_url != b.canonical_url


def test_normalize_uk_fsa_entry_carries_reporting_business_and_alert_types() -> None:
    item = _normalize_uk_fsa_entry(_entry())
    assert item.raw_metadata["reporting_business"] == "Tesco"
    assert "PRIN" in item.raw_metadata["alert_types"]


def test_normalize_uk_fsa_entry_handles_missing_notation() -> None:
    item = _normalize_uk_fsa_entry(_entry(notation=None))
    assert item.external_id is None
