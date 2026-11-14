"""Finished-report discovery fails closed and never serves arbitrary paths."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.report_library import (
    get_combined_finished_report,
    get_finished_report,
    list_combined_finished_reports,
    list_finished_reports,
)


def _entry(**overrides):
    entry = {
        "id": "regina-blackberry",
        "title": "Regina blackberry",
        "subtitle": "Variety and commercial profile",
        "summary": "Available details and questions for further investigation.",
        "published_date": "2026-11-13",
        "berry_id": "berry-blackberry",
        "page_count": 4,
        "files": {"html": "assets/regina.html", "pdf": "assets/regina.pdf"},
    }
    entry.update(overrides)
    return entry


def _library(tmp_path: Path, entries=None) -> Path:
    root = tmp_path / "reports"
    (root / "assets").mkdir(parents=True)
    (root / "assets/regina.html").write_text('<a href="https://example.org">Source</a>', encoding="utf-8")
    (root / "assets/regina.pdf").write_bytes(b"%PDF-1.7\nfixture")
    _catalog(root, [_entry()] if entries is None else entries)
    return root


def _catalog(root: Path, entries) -> None:
    (root / "library.json").write_text(json.dumps({"reports": entries}), encoding="utf-8")


def test_catalog_exposes_only_registered_artifacts_and_computed_links(tmp_path: Path):
    root = _library(tmp_path)
    (root / "assets/unregistered.pdf").write_bytes(b"%PDF")
    before = {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}
    rows = list_finished_reports(root)
    assert len(rows) == 1
    report = get_finished_report(root, "regina-blackberry")
    assert report == rows[0]
    assert report["files"] == {
        "html": (root / "assets/regina.html").resolve(),
        "pdf": (root / "assets/regina.pdf").resolve(),
    }
    assert report["href"] == "/reports/library/regina-blackberry"
    assert report["html_href"] == "/reports/library/regina-blackberry/document"
    assert report["download_href"] == "/reports/library/regina-blackberry/download.pdf"
    assert get_finished_report(root, "unregistered") is None
    assert before == {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def test_newest_first_and_untrusted_fields_cannot_override_paths(tmp_path: Path):
    root = _library(tmp_path, [
        _entry(id="older", published_date="2025-12-31"),
        _entry(href="https://untrusted.test", download_href="/etc/passwd", extra="hidden"),
    ])
    reports = list_finished_reports(root)
    assert [report["id"] for report in reports] == ["regina-blackberry", "older"]
    assert reports[0]["href"].startswith("/reports/library/")
    assert "extra" not in reports[0]


@pytest.mark.parametrize("slug", ["../regina", "regina/blackberry", "Regina", "regina--blackberry", "-regina", "regina-", "regina_blackberry", "regina?file=foo", "regina%2fsecret", "regina\n", "", None, ["regina"]])
def test_invalid_ids_are_not_paths_or_catalog_entries(tmp_path: Path, slug):
    root = _library(tmp_path, [_entry(id=slug)])
    assert list_finished_reports(root) == []
    assert get_finished_report(root, slug) is None


@pytest.mark.parametrize("path", [
    "../outside.pdf", "assets/../assets/regina.pdf", r"assets\..\assets\regina.pdf",
    "/outside.pdf", r"C:\outside.pdf", "C:outside.pdf", r"\outside.pdf",
    r"\\server\share\outside.pdf", "assets/regina.html", "assets/missing.pdf", "", None,
])
def test_asset_paths_reject_absolute_traversal_wrong_type_and_missing(tmp_path: Path, path):
    root = _library(tmp_path, [_entry(files={"html": "assets/regina.html", "pdf": path})])
    (tmp_path / "outside.pdf").write_bytes(b"%PDF")
    assert list_finished_reports(root) == []
    assert get_finished_report(root, "regina-blackberry") is None


def test_symlink_escape_is_not_served(tmp_path: Path):
    root = _library(tmp_path)
    external = tmp_path / "outside.pdf"
    external.write_bytes(b"%PDF")
    link = root / "assets/escaped.pdf"
    try:
        link.symlink_to(external)
    except (OSError, NotImplementedError):
        pytest.skip("Creating symlinks is not permitted on this host")
    _catalog(root, [_entry(files={"html": "assets/regina.html", "pdf": "assets/escaped.pdf"})])
    assert list_finished_reports(root) == []


def test_missing_asset_does_not_hide_other_valid_reports(tmp_path: Path):
    root = _library(tmp_path, [
        _entry(id="missing", files={"html": "absent.html", "pdf": "assets/regina.pdf"}),
        _entry(),
    ])
    assert [report["id"] for report in list_finished_reports(root)] == ["regina-blackberry"]


@pytest.mark.parametrize("overrides", [
    {"title": " "}, {"title": []}, {"subtitle": {}}, {"summary": None},
    {"published_date": "2026-02-30"}, {"published_date": "20261113"},
    {"published_date": None}, {"berry_id": []}, {"page_count": True},
    {"page_count": 0}, {"page_count": "4"}, {"files": []},
])
def test_malformed_metadata_is_not_exposed(tmp_path: Path, overrides):
    root = _library(tmp_path, [_entry(**overrides)])
    assert list_finished_reports(root) == []


def test_duplicate_ids_fail_closed_without_hiding_distinct_reports(tmp_path: Path):
    root = _library(tmp_path, [_entry(), _entry(title="Conflicting report"), _entry(id="another")])
    assert get_finished_report(root, "regina-blackberry") is None
    assert [report["id"] for report in list_finished_reports(root)] == ["another"]


@pytest.mark.parametrize("payload", ["not json", "[]", '{"reports": {}}', '{"reports": null}', '{}', '[{"id":"regina"}]'])
def test_malformed_catalog_is_empty(tmp_path: Path, payload):
    root = _library(tmp_path)
    (root / "library.json").write_text(payload, encoding="utf-8")
    assert list_finished_reports(root) == []


def test_absent_catalog_or_reports_directory_is_empty(tmp_path: Path):
    assert list_finished_reports(tmp_path / "absent") == []
    assert list_finished_reports(tmp_path) == []


def test_invalid_utf8_catalog_is_empty(tmp_path: Path):
    root = _library(tmp_path)
    (root / "library.json").write_bytes(b"\xff\xfe\x00")
    assert list_finished_reports(root) == []


def test_optional_workbook_is_allowlisted_with_computed_link(tmp_path: Path):
    root = _library(tmp_path)
    workbook = root / "assets/regina.xlsx"
    workbook.write_bytes(b"PK\x03\x04finished workbook")
    _catalog(root, [_entry(
        files={"html": "assets/regina.html", "pdf": "assets/regina.pdf", "xlsx": "assets/regina.xlsx"},
        xlsx_download_href="https://untrusted.test/arbitrary.xlsx",
    )])
    report = get_finished_report(root, "regina-blackberry")
    assert report["files"]["xlsx"] == workbook.resolve()
    assert report["xlsx_download_href"] == "/reports/library/regina-blackberry/download.xlsx"


@pytest.mark.parametrize("workbook", [
    "assets/missing.xlsx", "assets/regina.pdf", "../outside.xlsx",
    "assets/../outside.xlsx", r"assets\..\outside.xlsx", "/outside.xlsx",
    r"C:\outside.xlsx", "C:outside.xlsx", r"\\server\share\outside.xlsx",
    "assets/directory.xlsx", "", None, {"path": "assets/regina.xlsx"},
])
def test_unavailable_or_invalid_optional_workbook_preserves_pdf_report(tmp_path: Path, workbook):
    root = _library(tmp_path)
    (tmp_path / "outside.xlsx").write_bytes(b"PK\x03\x04private workbook")
    (root / "assets/directory.xlsx").mkdir()
    _catalog(root, [_entry(files={"html": "assets/regina.html", "pdf": "assets/regina.pdf", "xlsx": workbook})])
    report = get_finished_report(root, "regina-blackberry")
    assert report is not None
    assert "xlsx" not in report["files"]
    assert report["xlsx_download_href"] is None


def test_optional_workbook_symlink_cannot_escape_report_directory(tmp_path: Path):
    root = _library(tmp_path)
    external = tmp_path / "outside.xlsx"
    external.write_bytes(b"PK\x03\x04private workbook")
    try:
        (root / "assets/escaped.xlsx").symlink_to(external)
    except (OSError, NotImplementedError):
        pytest.skip("Creating symlinks is not permitted on this host")
    _catalog(root, [_entry(files={"html": "assets/regina.html", "pdf": "assets/regina.pdf", "xlsx": "assets/escaped.xlsx"})])
    report = get_finished_report(root, "regina-blackberry")
    assert report is not None
    assert "xlsx" not in report["files"]


def test_combined_catalogs_keep_each_root_and_sort_newest_first(tmp_path: Path):
    packaged = _library(tmp_path / "packaged", [_entry(id="packaged", published_date="2025-01-01")])
    private = _library(tmp_path / "private", [_entry(id="private")])
    before = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    rows = list_combined_finished_reports([packaged, private])
    assert [row["id"] for row in rows] == ["private", "packaged"]
    assert rows[0]["files"]["pdf"] == (private / "assets/regina.pdf").resolve()
    assert rows[1]["files"]["pdf"] == (packaged / "assets/regina.pdf").resolve()
    assert get_combined_finished_report([packaged, private], "private") == rows[0]
    assert get_combined_finished_report([packaged, private], "../private") is None
    assert {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()} == before


def test_duplicate_valid_ids_across_catalogs_fail_closed_without_shadowing(tmp_path: Path):
    packaged = _library(tmp_path / "packaged", [_entry(), _entry(id="packaged-only")])
    private = _library(tmp_path / "private", [_entry(), _entry(id="private-only")])
    rows = list_combined_finished_reports([packaged, private])
    assert {row["id"] for row in rows} == {"packaged-only", "private-only"}
    assert get_combined_finished_report([packaged, private], "regina-blackberry") is None


def test_missing_private_catalog_is_read_only_and_does_not_hide_packaged_reports(tmp_path: Path):
    packaged = _library(tmp_path / "packaged")
    private = tmp_path / "missing" / "finished_reports"
    assert list_combined_finished_reports([packaged, private]) == list_finished_reports(packaged)
    assert not private.exists()
    assert list_combined_finished_reports([packaged, packaged]) == list_finished_reports(packaged)


@pytest.mark.parametrize("format", ["html", "pdf", "xlsx"])
def test_combined_catalog_cannot_borrow_an_asset_from_another_root(tmp_path: Path, format):
    packaged = _library(tmp_path / "packaged")
    (packaged / "assets/regina.xlsx").write_bytes(b"PK\x03\x04packaged workbook")
    private = _library(tmp_path / "private", [_entry(id="private")])
    files = {"html": "assets/regina.html", "pdf": "assets/regina.pdf"}
    files[format] = str(packaged / "assets" / f"regina.{format}")
    _catalog(private, [_entry(id="private", files=files)])
    rows = list_combined_finished_reports([packaged, private])
    assert get_combined_finished_report([packaged, private], "regina-blackberry") is not None
    if format == "xlsx":
        assert {row["id"] for row in rows} == {"regina-blackberry", "private"}
        assert get_combined_finished_report([packaged, private], "private")["xlsx_download_href"] is None
    else:
        assert [row["id"] for row in rows] == ["regina-blackberry"]


def test_unavailable_duplicate_in_private_catalog_does_not_shadow_valid_packaged_id(tmp_path: Path):
    packaged = _library(tmp_path / "packaged")
    private = _library(tmp_path / "private")
    (private / "assets/regina.pdf").unlink()
    assert list_combined_finished_reports([packaged, private]) == list_finished_reports(packaged)


def test_coverage_attachments_use_confined_assets_and_computed_links(tmp_path):
    root = _library(tmp_path)
    (root / "assets/review.html").write_text("<h1>Coverage review</h1>", encoding="utf-8")
    (root / "assets/review.xlsx").write_bytes(b"PKcoverage workbook")
    _catalog(root, [_entry(files={"html": "assets/regina.html", "pdf": "assets/regina.pdf",
        "coverage": "assets/review.html", "coverage_xlsx": "assets/review.xlsx"}, coverage_href="https://untrusted.test")])
    row = get_finished_report(root, "regina-blackberry")
    assert row["coverage_href"] == "/reports/library/regina-blackberry/coverage"
    assert row["coverage_xlsx_href"] == "/reports/library/regina-blackberry/coverage.xlsx"
    assert row["files"]["coverage"] == (root / "assets/review.html").resolve()


@pytest.mark.parametrize("asset", ["../outside.html", "assets/regina.pdf", "C:outside.html", None])
def test_invalid_coverage_attachment_preserves_finished_report(tmp_path, asset):
    root = _library(tmp_path, [_entry(files={"html": "assets/regina.html", "pdf": "assets/regina.pdf", "coverage": asset})])
    (tmp_path / "outside.html").write_text("Private unrelated content", encoding="utf-8")
    row = get_finished_report(root, "regina-blackberry")
    assert row is not None and row["coverage_href"] is None and "coverage" not in row["files"]
