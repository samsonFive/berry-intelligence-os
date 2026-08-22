"""Unit coverage for the SEC EDGAR full-text search adapter
(sec_edgar_search_json, added for the Unknown-Event Discovery + Query
Coverage V3 mission, 2026-08-23). The real endpoint (efts.sec.gov) and the
real CIK-scoped precision finding were proven live, by hand, during the
mission -- see docs/v2/UNKNOWN-EVENT-DISCOVERY-V3.md. Live network is never
exercised in pytest.
"""

from __future__ import annotations

from app.services.media_discovery import ADAPTER_TYPES, _normalize_sec_edgar_entry, _sec_edgar_entries


def _hit(**changes) -> dict:
    record = {
        "_id": "0001802974-26-000031:exh991avoq22026earningsrel.htm",
        "_source": {
            "ciks": ["0001802974"],
            "period_ending": "2026-06-08",
            "display_names": ["Mission Produce, Inc.  (AVO)  (CIK 0001802974)"],
            "root_forms": ["8-K"],
            "file_date": "2026-06-08",
            "form": "8-K",
            "adsh": "0001802974-26-000031",
            "file_type": "EX-99.1",
            "items": ["2.02", "8.01", "9.01"],
        },
    }
    record.update(changes)
    return record


def test_sec_edgar_search_json_is_registered_and_reuses_generic_json_fetch() -> None:
    assert "sec_edgar_search_json" in ADAPTER_TYPES
    from app.services.media_discovery import _fetch_federal_register_json
    fetch, list_entries, normalize = ADAPTER_TYPES["sec_edgar_search_json"]
    assert fetch is _fetch_federal_register_json
    assert list_entries is _sec_edgar_entries
    assert normalize is _normalize_sec_edgar_entry


def test_sec_edgar_entries_reads_nested_hits_hits_key() -> None:
    parsed = {"hits": {"hits": [_hit(), _hit(_id="0001802974-26-000020:exh991avoq12026earningsrel.htm")]}}
    assert len(_sec_edgar_entries(parsed)) == 2
    assert _sec_edgar_entries({"results": [_hit()]}) == []  # wrong shape on purpose
    assert _sec_edgar_entries(None) == []


def test_normalize_sec_edgar_entry_builds_real_synthetic_title() -> None:
    item = _normalize_sec_edgar_entry(_hit())
    assert "Mission Produce" in item.title
    assert "8-K" in item.title


def test_normalize_sec_edgar_entry_title_includes_file_date_for_distinctness() -> None:
    """Real regression: a company with several years of quarterly 8-Ks
    reuses the identical EX-99.1 exhibit type on every filing -- a title
    built from company+form+file_type alone produced 27 real, distinct
    filings under one identical title in the real review queue. file_date
    is the one field that actually distinguishes them."""
    a = _normalize_sec_edgar_entry(_hit())
    b = _normalize_sec_edgar_entry(_hit(
        _id="0001193125-26-013366:d47538dex991.htm",
        _source={**_hit()["_source"], "adsh": "0001193125-26-013366", "file_date": "2026-01-15"},
    ))
    assert a.title != b.title
    assert "2026-06-08" in a.title
    assert "2026-01-15" in b.title


def test_normalize_sec_edgar_entry_constructs_real_working_document_url() -> None:
    item = _normalize_sec_edgar_entry(_hit())
    assert item.canonical_url == (
        "https://www.sec.gov/Archives/edgar/data/1802974/000180297426000031/exh991avoq22026earningsrel.htm"
    )
    assert item.published_date == "2026-06-08"


def test_normalize_sec_edgar_entry_two_distinct_filings_get_distinct_identity() -> None:
    a = _normalize_sec_edgar_entry(_hit())
    b = _normalize_sec_edgar_entry(_hit(
        _id="0001802974-26-000020:exh991avoq12026earningsrel.htm",
        _source={**_hit()["_source"], "adsh": "0001802974-26-000020", "file_date": "2026-03-12"},
    ))
    assert a.external_id != b.external_id
    assert a.canonical_url != b.canonical_url


def test_normalize_sec_edgar_entry_carries_form_items_and_cik_in_raw_metadata() -> None:
    item = _normalize_sec_edgar_entry(_hit())
    assert item.raw_metadata["form"] == "8-K"
    assert item.raw_metadata["items"] == ["2.02", "8.01", "9.01"]
    assert item.raw_metadata["cik"] == "0001802974"


def test_normalize_sec_edgar_entry_handles_missing_ciks_or_filename() -> None:
    item = _normalize_sec_edgar_entry(_hit(_source={**_hit()["_source"], "ciks": []}))
    assert item.canonical_url is None

    item2 = _normalize_sec_edgar_entry(_hit(_id="0001802974-26-000031"))  # no ":filename" suffix
    assert item2.canonical_url is None
