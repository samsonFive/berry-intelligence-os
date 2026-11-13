"""Finished artifacts remain private, directly downloadable, and unchanged on read."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.services.report_builder.reports_store import create_report


@pytest.fixture
def library(monkeypatch, tmp_path: Path):
    root = tmp_path / "reports"
    root.mkdir()
    html = '<!doctype html><title>Finished report</title><a href="https://example.org/source" target="_blank" rel="noopener noreferrer">Source</a>'
    pdf = b"%PDF-1.4\nfinished artifact\n%%EOF\n"
    (root / "profile.html").write_text(html, encoding="utf-8")
    (root / "profile.pdf").write_bytes(pdf)
    (root / "library.json").write_text(json.dumps({"reports": [{
        "id": "test-variety", "title": "Finished variety report", "subtitle": "Variety and commercial profile",
        "summary": "Identity, production, fruit quality, and open questions.",
        "published_date": "2026-11-13", "berry_id": "berry-blackberry", "page_count": 4,
        "files": {"html": "profile.html", "pdf": "profile.pdf"},
    }]}), encoding="utf-8")
    monkeypatch.setattr(main, "REPORT_LIBRARY_DIR", root)
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path / "inbox")
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    monkeypatch.setenv("BIOS_REMOTE_INTERACTIVE", "false")
    monkeypatch.delenv("BIOS_BASIC_AUTH", raising=False)

    def no_provider(*args, **kwargs):
        raise AssertionError("Reading a finished report must not initiate research or generation")

    monkeypatch.setattr(main, "maybe_untrusted_completer", no_provider)
    monkeypatch.setattr(main, "_build_packet_and_coverage", no_provider)
    return root, html, pdf, TestClient(main.app)


def test_finished_report_is_visible_without_drafts_and_in_each_status(library):
    root, _, _, client = library
    before = {path: path.read_bytes() for path in root.iterdir()}
    for status in ("working", "draft", "active", "archived", "all"):
        response = client.get(f"/reports?status={status}")
        assert response.status_code == 200
        assert "Research reports" in response.text
        assert "Finished variety report" in response.text
        assert 'href="/reports/library/test-variety"' in response.text
        assert 'href="/reports/library/test-variety/download.pdf" download' in response.text
    assert {path: path.read_bytes() for path in root.iterdir()} == before
    assert not list(main.INBOX_DIR.rglob("*.json"))


def test_existing_working_reports_remain_available(library):
    _, _, _, client = library
    record = create_report(main.INBOX_DIR, title="Existing draft", report_type="company_brief", scope={}, sections=[])
    response = client.get("/reports")
    assert response.status_code == 200
    assert 'href="/reports/new"' in response.text
    assert f'href="/reports/{record["id"]}"' in response.text
    assert "Finished variety report" in response.text


def test_report_preview_and_exact_pdf_download(library):
    _, html, pdf, client = library
    page = client.get("/reports/library/test-variety")
    assert page.status_code == 200
    assert '<iframe' in page.text
    assert 'src="/reports/library/test-variety/document"' in page.text
    assert 'title="Finished variety report report"' in page.text
    assert 'sandbox="allow-popups allow-popups-to-escape-sandbox"' in page.text
    assert "Download PDF" in page.text
    document = client.get("/reports/library/test-variety/document")
    assert document.status_code == 200
    assert document.text == html
    assert document.headers["content-type"].startswith("text/html")
    assert "frame-ancestors 'self'" in document.headers["content-security-policy"]
    download = client.get("/reports/library/test-variety/download.pdf")
    assert download.status_code == 200
    assert download.content == pdf
    assert download.headers["content-type"] == "application/pdf"
    assert download.headers["content-disposition"] == 'attachment; filename="profile.pdf"'
    assert download.headers["cache-control"] == "private, no-cache"
    assert download.headers["x-content-type-options"] == "nosniff"


@pytest.mark.parametrize("suffix", ["", "/document", "/download.pdf", "/download.xlsx"])
def test_missing_or_unavailable_report_is_not_served(library, suffix):
    root, _, _, client = library
    assert client.get(f"/reports/library/not-listed{suffix}").status_code == 404
    (root / "profile.pdf").unlink()
    assert client.get(f"/reports/library/test-variety{suffix}").status_code == 404


@pytest.mark.parametrize("suffix", ["", "/document", "/download.pdf", "/download.xlsx"])
def test_finished_reports_obey_existing_readonly_boundary(library, monkeypatch, suffix):
    _, _, _, client = library
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    assert client.get(f"/reports/library/test-variety{suffix}").status_code == 403


@pytest.mark.parametrize("suffix", ["", "/document", "/download.pdf", "/download.xlsx"])
def test_anonymous_remote_requests_cannot_read_finished_artifacts(library, monkeypatch, suffix):
    _, _, _, client = library
    monkeypatch.setenv("BIOS_REMOTE_INTERACTIVE", "true")
    monkeypatch.setenv("BIOS_REVIEW_USERNAME", "report-library-test")
    monkeypatch.setenv("BIOS_REVIEW_PASSWORD", "temporary-test-password")
    monkeypatch.setenv("BIOS_SESSION_SECRET", "report-library-test-session-secret-at-least-32-chars")
    response = client.get(f"/reports/library/test-variety{suffix}", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"].startswith("/login?next=")
    assert b"finished artifact" not in response.content


def test_reports_stay_out_of_public_static_build():
    source = Path("scripts/build_static.py").read_text(encoding="utf-8")
    assert '"/reports"' not in source
    assert "/reports/" not in source


def test_optional_workbook_button_and_exact_download(library):
    root, _, _, client = library
    workbook = b"PK\x03\x04finished spreadsheet artifact"
    (root / "profile.xlsx").write_bytes(workbook)
    catalog = json.loads((root / "library.json").read_text(encoding="utf-8"))
    catalog["reports"][0]["files"]["xlsx"] = "profile.xlsx"
    (root / "library.json").write_text(json.dumps(catalog), encoding="utf-8")
    before = {path: path.read_bytes() for path in root.iterdir()}
    for route in ("/reports", "/reports/library/test-variety"):
        response = client.get(route)
        assert response.status_code == 200
        assert 'href="/reports/library/test-variety/download.xlsx" download' in response.text
        assert "Download Excel" in response.text
    download = client.get("/reports/library/test-variety/download.xlsx")
    assert download.status_code == 200
    assert download.content == workbook
    assert download.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert download.headers["content-disposition"] == 'attachment; filename="profile.xlsx"'
    assert download.headers["cache-control"] == "private, no-cache"
    assert download.headers["x-content-type-options"] == "nosniff"
    assert {path: path.read_bytes() for path in root.iterdir()} == before


def test_missing_optional_workbook_hides_only_excel_action(library):
    root, _, pdf, client = library
    catalog = json.loads((root / "library.json").read_text(encoding="utf-8"))
    catalog["reports"][0]["files"]["xlsx"] = "missing.xlsx"
    (root / "library.json").write_text(json.dumps(catalog), encoding="utf-8")
    for route in ("/reports", "/reports/library/test-variety"):
        response = client.get(route)
        assert response.status_code == 200
        assert "Download Excel" not in response.text
        assert "Download PDF" in response.text
    assert client.get("/reports/library/test-variety/download.xlsx").status_code == 404
    assert client.get("/reports/library/test-variety/download.pdf").content == pdf


def _private_report(report_id="private-report"):
    root = main.INBOX_DIR / "finished_reports"
    root.mkdir(parents=True)
    assets = {
        "html": b"<!doctype html><title>Private report</title><p>Retained research</p>",
        "pdf": b"%PDF-1.4\nprivate finished artifact\n%%EOF\n",
        "xlsx": b"PK\x03\x04private finished spreadsheet",
    }
    for extension, payload in assets.items():
        (root / f"private.{extension}").write_bytes(payload)
    (root / "library.json").write_text(json.dumps({"reports": [{
        "id": report_id, "title": "Private finished research", "subtitle": "Dated report",
        "summary": "A privately installed report.", "published_date": "2026-11-13",
        "berry_id": "berry-strawberry", "page_count": 23,
        "files": {extension: f"private.{extension}" for extension in assets},
    }]}), encoding="utf-8")
    return root, assets


def test_packaged_and_private_reports_share_index_reader_and_downloads(library):
    packaged, _, _, client = library
    private, assets = _private_report()
    before = {path: path.read_bytes() for root in (packaged, private) for path in root.iterdir()}
    index = client.get("/reports")
    assert index.status_code == 200
    assert "Finished variety report" in index.text
    assert "Private finished research" in index.text
    assert 'href="/reports/library/private-report/download.xlsx"' in index.text
    page = client.get("/reports/library/private-report")
    assert page.status_code == 200
    assert 'src="/reports/library/private-report/document"' in page.text
    for endpoint, extension in (("document", "html"), ("download.pdf", "pdf"), ("download.xlsx", "xlsx")):
        response = client.get(f"/reports/library/private-report/{endpoint}")
        assert response.status_code == 200
        assert response.content == assets[extension]
        assert response.headers["cache-control"] == "private, no-cache"
        assert response.headers["x-content-type-options"] == "nosniff"
    assert {path: path.read_bytes() for root in (packaged, private) for path in root.iterdir()} == before


@pytest.mark.parametrize("suffix", ["", "/document", "/download.pdf", "/download.xlsx"])
def test_duplicate_packaged_and_private_report_id_is_not_served(library, suffix):
    _, _, _, client = library
    _private_report("test-variety")
    response = client.get("/reports")
    assert response.status_code == 200
    assert "Finished variety report" not in response.text
    assert "Private finished research" not in response.text
    assert client.get(f"/reports/library/test-variety{suffix}").status_code == 404


@pytest.mark.parametrize("suffix", ["", "/document", "/download.pdf", "/download.xlsx"])
@pytest.mark.parametrize("access", ["readonly", "anonymous"])
def test_private_catalog_obeys_existing_reports_access_controls(library, monkeypatch, suffix, access):
    _, _, _, client = library
    _private_report()
    if access == "readonly":
        monkeypatch.setattr(main, "AUTHORING_MODE", False)
        expected = 403
    else:
        monkeypatch.setenv("BIOS_REMOTE_INTERACTIVE", "true")
        monkeypatch.setenv("BIOS_REVIEW_USERNAME", "report-library-test")
        monkeypatch.setenv("BIOS_REVIEW_PASSWORD", "temporary-test-password")
        monkeypatch.setenv("BIOS_SESSION_SECRET", "report-library-test-session-secret-at-least-32-chars")
        expected = 302
    response = client.get(f"/reports/library/private-report{suffix}", follow_redirects=False)
    assert response.status_code == expected
    assert b"private finished artifact" not in response.content
    assert b"private finished spreadsheet" not in response.content
