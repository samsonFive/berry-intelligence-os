"""Saved-ledger export invariants; fixtures contain invented public examples."""

from copy import deepcopy
from datetime import datetime
from io import BytesIO
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from openpyxl import load_workbook
from pypdf import PdfReader
import pytest

from app.services.report_builder.company_news_export import (
    company_news_view,
    render_company_news_pdf,
    render_company_news_xlsx,
)


@pytest.fixture
def review():
    return {
        "schema_version": 1, "from_date": "2025-07-01", "through_date": "2026-11-13",
        "as_of": "2026-11-13", "created_at": "2026-11-13T10:00:00+00:00", "status": "partial",
        "berry_id": "berry-strawberry", "topic": "Breeding and retail", "source_scope": "combined",
        "companies": [
            {"key": "co-alpha", "requested_name": "Alpha", "canonical_name": "Alpha Seeds", "company_id": "company-alpha",
             "resolution": "resolved", "disposition": "has_findings", "archive_status": "complete", "web_status": "partial", "notes": ["One publisher blocked access."]},
            {"key": "co-quiet", "requested_name": "Quiet Research", "canonical_name": "Quiet Research", "company_id": "company-quiet",
             "resolution": "resolved", "disposition": "no_qualifying_findings", "archive_status": "complete", "web_status": "complete", "notes": []},
            {"key": "co-unknown", "requested_name": "Unknown Farm", "canonical_name": "", "company_id": None,
             "resolution": "unresolved", "disposition": "identity_unresolved", "archive_status": "complete", "web_status": "not_requested", "notes": ["Identity remains unresolved."]},
        ],
        "sources": [
            {"id": "src-one", "title": "Alpha's new variety announcement", "url": "https://example.com/alpha?lang=en&crop=berry",
             "published_date": "2026-06-15", "publication_date_basis": "publisher", "origin": "archive", "trust_class": "APPROVED SOURCE",
             "capture_status": "body_supported", "eligibility": "dated_finding", "qualification": "Company statement; no independent performance trial.",
             "company_keys": ["co-alpha"], "source_version": "sha256:example-one", "passage_locator": "paragraph 2", "evidence_id": "ev-synthetic-one"},
            {"id": "src-two", "title": "Market programme interview", "url": "https://example.org/interview", "published_date": "2026-06-17",
             "publication_date_basis": "publisher", "origin": "web", "trust_class": "LIVE / UNREVIEWED", "capture_status": "body_supported",
             "eligibility": "dated_finding", "qualification": "Interview records the stated plan.", "company_keys": ["co-alpha"]},
            {"id": "src-metadata", "title": "Undated directory result", "url": "https://example.net/directory", "published_date": "",
             "publication_date_basis": "unknown", "origin": "web", "trust_class": "LIVE / UNREVIEWED", "capture_status": "metadata_only",
             "eligibility": "undated", "qualification": "A directory listing does not establish a new development.", "company_keys": ["co-unknown"]},
        ],
        "entries": [
            {"id": "entry-included", "company_key": "co-alpha", "company_id": "company-alpha", "headline": "Prior unedited headline",
             "summary": "Prior unedited summary", "news_angle": "Prior unedited angle", "qualification": "Prior unedited qualification",
             "published_date": "2026-06-15", "event_date": "Trials planned for 2027", "entry_type": "development", "included": True,
             "review_status": "reviewed", "source_ids": ["src-one", "src-two"],
             "edits": {"headline": "Analyst-selected headline", "summary": "Analyst summary of a newly announced programme.",
                       "news_angle": "A new route to licensed trial material.", "qualification": "Plans are not completed commercial adoption."}},
            {"id": "entry-excluded", "company_key": "co-alpha", "company_id": "company-alpha", "headline": "Excluded candidate headline",
             "summary": "Excluded candidate summary", "news_angle": "", "qualification": "Review found this was background context.",
             "published_date": "2026-05-13", "event_date": "", "entry_type": "lead", "included": False, "review_status": "reviewed", "source_ids": ["src-one"]},
            {"id": "entry-undated", "company_key": "co-unknown", "company_id": None, "headline": "Unresolved undated lead",
             "summary": "Metadata only", "news_angle": "", "qualification": "Identity not resolved; publication date unavailable.",
             "published_date": "", "event_date": "Not stated", "entry_type": "lead", "included": False, "review_status": "unreviewed", "source_ids": ["src-metadata"]},
        ],
    }


def book(review, **kwargs):
    return load_workbook(BytesIO(render_company_news_xlsx(review, **kwargs)), data_only=False)


def pdf_text(payload):
    reader = PdfReader(BytesIO(payload))
    return reader, "\n".join(page.extract_text() for page in reader.pages)


def test_view_resolves_edits_and_retains_every_roster_outcome(review):
    before = deepcopy(review)
    view = company_news_view(review)
    assert [row["name"] for row in view["companies"]] == ["Alpha Seeds", "Quiet Research", "Unknown Farm"]
    assert view["counts"] == {"companies": 3, "entries": 3, "included": 1, "excluded": 2, "sources": 3, "included_leads": 0}
    assert view["included_entries"][0]["headline"] == "Analyst-selected headline"
    assert view["included_entries"][0]["analyst_edited"] is True
    assert view["companies"][1]["outcome"] == "No qualifying findings captured"
    assert view["companies"][2]["outcome"] == "Identity unresolved"
    assert [row["reference"] for row in view["sources"]] == ["S01", "S02", "S03"]
    assert review == before


def test_workbook_retains_decisions_typed_dates_and_source_trace(review):
    workbook = book(review)
    assert workbook.sheetnames == ["Companies", "Developments", "Scope"]
    companies, entries, sources = workbook.worksheets
    assert companies["A8"].value == "Unknown Farm"
    assert companies["E7"].value == "No qualifying findings captured"
    assert companies["H6"].value == 1
    assert companies["I6"].value == 1
    assert entries["A6"].value == "entry-included"
    assert entries["E6"].value == "Analyst-selected headline"
    assert entries["H6"].value == "Plans are not completed commercial adoption."
    assert entries["C6"].value == datetime(2026, 6, 15)
    assert entries["D6"].value == "Trials planned for 2027"
    assert entries["J6"].value == "Yes"
    assert entries["J7"].value == "No"
    assert entries["E7"].value == "Excluded candidate headline"
    assert entries["C8"].value is None
    assert entries["N8"].value == "Date not recorded"
    assert entries["I6"].hyperlink.location == "'Scope'!A8"
    assert sources["C8"].value == datetime(2026, 6, 15)
    assert sources["D8"].value == "publisher"
    assert sources["F9"].value == "LIVE / UNREVIEWED"
    assert sources["G10"].value == "Metadata only"
    assert sources["I10"].value == "A directory listing does not establish a new development."
    assert sources["J8"].hyperlink.target == review["sources"][0]["url"]
    assert sources["J9"].hyperlink.target == review["sources"][1]["url"]
    assert sources["J10"].hyperlink.target == review["sources"][2]["url"]
    assert sources["L8"].value == "sha256:example-one"


def test_workbook_has_readable_filters_freeze_panes_and_date_formats(review):
    workbook = book(review)
    assert workbook["Companies"].freeze_panes == "C6"
    assert workbook["Developments"].freeze_panes == "D6"
    assert workbook["Scope"].freeze_panes == "B8"
    assert workbook["Companies"].auto_filter.ref == "A5:K8"
    assert workbook["Developments"].auto_filter.ref == "A5:O8"
    assert workbook["Scope"].auto_filter.ref == "A7:M10"
    assert workbook["Developments"]["C6"].number_format == "yyyy-mm-dd"
    assert workbook["Developments"]["F6"].alignment.wrap_text
    assert workbook["Developments"].column_dimensions["F"].width == 88
    assert workbook["Companies"]["A5"].font.bold
    assert workbook["Companies"]["A6"].border.left.style == "thin"


@pytest.mark.parametrize("payload", ["=HYPERLINK(\"https://bad.example\",\"click\")", "+DDE", "-2+3", "@SUM(A1:A9)"])
def test_untrusted_text_never_becomes_an_excel_formula(review, payload):
    review["companies"][0]["canonical_name"] = payload
    review["entries"][0]["edits"]["summary"] = payload
    review["sources"][0]["title"] = payload
    output = render_company_news_xlsx(review, title=payload)
    workbook = load_workbook(BytesIO(output), data_only=False)
    for sheet, coordinate in (("Companies", "A1"), ("Companies", "A6"), ("Developments", "F6"), ("Scope", "B8")):
        assert workbook[sheet][coordinate].value == payload
        assert workbook[sheet][coordinate].data_type == "s"
    with ZipFile(BytesIO(output)) as archive:
        for name in archive.namelist():
            if name.startswith("xl/worksheets/") and name.endswith(".xml"):
                assert "<f>" not in archive.read(name).decode()


@pytest.mark.parametrize("bad_url", ["javascript:alert(1)", "file:///private/path", "https://name:password@example.com/private", "http://127.0.0.1/private", "https://example.com/\nprivate"])
def test_unsafe_source_links_are_never_exported_as_hyperlinks(review, bad_url):
    review["sources"][0]["url"] = bad_url
    workbook = book(review)
    assert workbook["Scope"]["J8"].hyperlink is None
    assert workbook["Scope"]["J8"].value is None
    assert workbook["Scope"]["A8"].value == "S01 · src-one"


@pytest.mark.parametrize("source_ids", [["missing-source"], ["src-one", "missing-source"], []])
def test_included_item_with_broken_or_empty_source_links_refuses_exports(review, source_ids):
    review["entries"][0]["source_ids"] = source_ids
    view = company_news_view(review)
    assert view["included_entries"][0]["missing_source_ids"] == [identity for identity in source_ids if identity == "missing-source"]
    with pytest.raises(ValueError, match="included item has missing source references"):
        render_company_news_xlsx(review)
    with pytest.raises(ValueError, match="included item has missing source references"):
        render_company_news_pdf(review)


def test_excluded_item_with_missing_reference_remains_visible_without_relinking(review):
    review["entries"][0]["source_ids"] = ["missing-source"]
    review["entries"][0]["included"] = False
    workbook = book(review)
    assert workbook["Developments"]["O6"].value == "missing-source"
    assert workbook["Developments"]["I6"].hyperlink is None
    _, text = pdf_text(render_company_news_pdf(review))
    assert "Missing reference: missing-source" not in text


def test_analyst_edited_dates_remain_visible_with_window_qualification(review):
    review["entries"][0]["edits"]["published_date"] = "2025-06-01"
    review["entries"][0]["edits"]["event_date"] = "Completion not confirmed"
    workbook = book(review)
    assert workbook["Developments"]["C6"].value == datetime(2025, 6, 1)
    assert workbook["Developments"]["D6"].value == "Completion not confirmed"
    assert workbook["Developments"]["N6"].value == "Outside requested window"
    _, text = pdf_text(render_company_news_pdf(review))
    assert "Completion not confirmed" in text
    assert "outside the requested window" in text
    assert "2025-06-01" in text


def test_known_event_date_is_a_native_date_without_becoming_publication_date(review):
    review["entries"][0]["edits"]["event_date"] = "2027-01-13"
    workbook = book(review)
    assert workbook["Developments"]["C6"].value == datetime(2026, 6, 15)
    assert workbook["Developments"]["D6"].value == datetime(2027, 1, 13)
    assert workbook["Developments"]["N6"].value == "Within requested window"


def test_pdf_uses_included_effective_entries_and_clear_source_qualifications(review):
    payload = render_company_news_pdf(review, title="Synthetic breeding news")
    reader, text = pdf_text(payload)
    assert payload.startswith(b"%PDF-")
    assert "Synthetic breeding news" in text
    assert "Analyst-selected headline" in text
    assert "Analyst summary of a newly announced programme." in text
    assert "A new route to licensed trial material." in text
    assert "Plans are not completed commercial adoption." in text
    assert "Prior unedited headline" not in text
    assert "Prior unedited summary" not in text
    assert "Excluded candidate headline" not in text
    assert "Excluded candidate summary" not in text
    assert "Quiet Research" in text and "No qualifying findings captured" in text
    assert "Unknown Farm" in text and "Identity unresolved" in text
    assert "LIVE / UNREVIEWED" in text and "Dated finding" in text
    assert "Undated directory result" not in text
    assert "Working report; source review remains separate" in text
    assert len(reader.outline) >= 5
    urls = [str(annotation.get_object().get("/A", {}).get("/URI", ""))
            for page in reader.pages for annotation in page.get("/Annots", [])]
    assert review["sources"][0]["url"] in urls
    assert review["sources"][1]["url"] in urls


def test_no_global_story_cap_and_quiet_companies_survive_both_exports(review):
    first = review["entries"][0]
    review["entries"] = [{**deepcopy(first), "id": f"entry-{index}", "edits": {"headline": f"Saved development {index}"}}
                         for index in range(26)]
    workbook = book(review)
    assert workbook["Developments"].max_row == 31
    assert workbook["Companies"]["H6"].value == 26
    assert workbook["Companies"]["A8"].value == "Unknown Farm"
    _, text = pdf_text(render_company_news_pdf(review))
    for index in range(26):
        assert f"Saved development {index}" in text
    assert "Quiet Research" in text and "Unknown Farm" in text


def test_pending_or_empty_searches_do_not_fabricate_findings(review):
    review["entries"] = []
    review["sources"] = []
    review["companies"][0].update(disposition="pending", archive_status="pending", web_status="pending", notes=[])
    workbook = book(review)
    assert workbook["Developments"].max_row == 5
    assert workbook["Companies"]["E6"].value == "Not researched yet"
    assert workbook["Companies"]["H6"].value == 0
    _, text = pdf_text(render_company_news_pdf(review))
    assert "Not researched yet" in text
    assert "No source records were captured" in text
    assert "The platform archive was searched first" not in text


def test_exports_are_provider_free_and_do_not_modify_the_snapshot(review, monkeypatch):
    import httpx
    def forbidden(*_args, **_kwargs):
        raise AssertionError("An export must not contact a provider")
    monkeypatch.setattr(httpx.Client, "send", forbidden)
    monkeypatch.setattr(httpx.AsyncClient, "send", forbidden)
    before = deepcopy(review)
    render_company_news_xlsx(review)
    render_company_news_pdf(review)
    assert review == before


def test_saved_workbook_dates_and_zip_metadata_are_stable(review):
    output = render_company_news_xlsx(review)
    assert output == render_company_news_xlsx(review)
    with ZipFile(BytesIO(output)) as archive:
        assert all(info.date_time == (1980, 1, 1, 0, 0, 0) for info in archive.infolist())
        core = ET.fromstring(archive.read("docProps/core.xml"))
        created = core.find("{http://purl.org/dc/terms/}created").text
        modified = core.find("{http://purl.org/dc/terms/}modified").text
        assert created == "2026-11-13T10:00:00Z"
        assert modified == created


@pytest.mark.parametrize("problem", ["source_duplicate", "company_duplicate", "entry_duplicate", "foreign_company", "bad_window", "unsupported_version"])
def test_corrupt_snapshot_fails_instead_of_silently_dropping_data(review, problem):
    if problem == "source_duplicate":
        review["sources"].append(deepcopy(review["sources"][0]))
    elif problem == "company_duplicate":
        review["companies"].append(deepcopy(review["companies"][0]))
    elif problem == "entry_duplicate":
        review["entries"].append(deepcopy(review["entries"][0]))
    elif problem == "foreign_company":
        review["entries"][0]["company_key"] = "not-in-roster"
    elif problem == "bad_window":
        review["from_date"] = "2027-01-01"
    else:
        review["schema_version"] = 4
    with pytest.raises(ValueError):
        company_news_view(review)


@pytest.mark.parametrize("value", ["x" * 32768, "Invalid\x01value"], ids=["long-cell", "invalid-xml-control"])
def test_excel_refuses_unpreservable_cell_text(review, value):
    review["entries"][0]["edits"]["summary"] = value
    with pytest.raises(ValueError):
        render_company_news_xlsx(review)


def test_large_exports_fail_explicitly_instead_of_truncating(review):
    review["entries"] = [{**review["entries"][0], "id": f"large-{index}"} for index in range(5001)]
    with pytest.raises(ValueError, match="workbook export limit"):
        render_company_news_xlsx(review)
    with pytest.raises(ValueError, match="PDF export limit"):
        render_company_news_pdf(review)


def test_export_source_bound_is_explicit(review):
    review["sources"] = [{**review["sources"][0], "id": f"source-{index}"} for index in range(10001)]
    with pytest.raises(ValueError, match="workbook export limit"):
        render_company_news_xlsx(review)
    review["entries"][0]["source_ids"] = [source["id"] for source in review["sources"]]
    with pytest.raises(ValueError, match="PDF source-reference limit"):
        render_company_news_pdf(review)
