"""Finished-report discovery fails closed and never serves arbitrary paths."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.report_library import get_finished_report, list_finished_reports


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
