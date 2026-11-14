"""Read the allowlisted library of finished, downloadable reports.

``root`` is the repository's ``reports/`` directory. Its ``library.json``
contains ``{"reports": [...]}``; each entry names one HTML preview and PDF,
and may name an optional Excel workbook under that directory. This is an artifact catalog, separate from generated
report drafts and the trusted intelligence stores. Reading it never writes
files, refreshes research, or regenerates a report.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Iterable
from datetime import date
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

_SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")


def _valid_slug(value: Any) -> bool:
    return isinstance(value, str) and _SLUG.fullmatch(value) is not None


def _asset(root: Path, value: Any, extension: str) -> Path | None:
    if not isinstance(value, str) or not value or "\x00" in value:
        return None
    # Check both path syntaxes so the same catalog is safe on Windows and
    # Unix, including drive-relative paths and backslash traversal.
    windows = PureWindowsPath(value)
    posix = PurePosixPath(value)
    if windows.drive or windows.root or posix.is_absolute():
        return None
    if ".." in windows.parts or ".." in posix.parts:
        return None
    if posix.suffix.lower() != extension:
        return None
    try:
        target = (root / value).resolve(strict=True)
        if not target.is_relative_to(root) or not target.is_file():
            return None
        if target.suffix.lower() != extension:
            return None
        return target
    except (OSError, RuntimeError, ValueError):
        return None


def _present(root: Path, entry: Any) -> dict[str, Any] | None:
    if not isinstance(entry, dict) or not _valid_slug(entry.get("id")):
        return None
    title = entry.get("title")
    if not isinstance(title, str) or not title.strip():
        return None
    subtitle = entry.get("subtitle", "")
    summary = entry.get("summary", "")
    if not isinstance(subtitle, str) or not isinstance(summary, str):
        return None
    published_date = entry.get("published_date")
    if not isinstance(published_date, str) or not _DATE.fullmatch(published_date):
        return None
    try:
        date.fromisoformat(published_date)
    except ValueError:
        return None
    berry_id = entry.get("berry_id")
    if not _valid_slug(berry_id):
        return None
    page_count = entry.get("page_count")
    if type(page_count) is not int or page_count < 1:
        return None
    files = entry.get("files")
    if not isinstance(files, dict):
        return None
    html = _asset(root, files.get("html"), ".html")
    pdf = _asset(root, files.get("pdf"), ".pdf")
    if html is None or pdf is None:
        return None
    # Optional formats must not make a valid HTML/PDF report disappear when
    # their files are unavailable. They use the same confined-path allowlist.
    xlsx = _asset(root, files.get("xlsx"), ".xlsx")
    assets = {"html": html, "pdf": pdf}
    if xlsx is not None:
        assets["xlsx"] = xlsx
    reader = _asset(root, files.get("reader"), ".json")
    if reader is not None:
        assets["reader"] = reader
    coverage = _asset(root, files.get("coverage"), ".html")
    coverage_xlsx = _asset(root, files.get("coverage_xlsx"), ".xlsx")
    if coverage is not None:
        assets["coverage"] = coverage
    if coverage_xlsx is not None:
        assets["coverage_xlsx"] = coverage_xlsx
    script_hash = entry.get("coverage_script_sha256")
    if not isinstance(script_hash, str) or not re.fullmatch(r"[A-Za-z0-9+/]{43}=", script_hash):
        script_hash = None
    slug = entry["id"]
    href = f"/reports/library/{slug}"
    return {
        "id": slug,
        "title": title.strip(),
        "subtitle": subtitle.strip(),
        "summary": summary.strip(),
        "published_date": published_date,
        "berry_id": berry_id,
        "page_count": page_count,
        "files": assets,
        "href": href,
        "html_href": f"{href}/document",
        "download_href": f"{href}/download.pdf",
        "xlsx_download_href": f"{href}/download.xlsx" if xlsx is not None else None,
        "coverage_href": f"{href}/coverage" if coverage is not None else None,
        "coverage_xlsx_href": f"{href}/coverage.xlsx" if coverage_xlsx is not None else None,
        "coverage_script_sha256": script_hash if coverage is not None else None,
    }


def list_finished_reports(root: Path) -> list[dict[str, Any]]:
    """Return valid catalog entries, newest first; unavailable entries disappear.

    Both files must exist inside ``root``. Ambiguous duplicate IDs, malformed
    metadata, and paths escaping that root are never exposed.
    """
    try:
        root = Path(root).resolve(strict=True)
        if not root.is_dir():
            return []
        manifest = (root / "library.json").resolve(strict=True)
        if not manifest.is_relative_to(root) or not manifest.is_file():
            return []
        catalog = json.loads(manifest.read_text(encoding="utf-8-sig"))
    except (OSError, RuntimeError, UnicodeError, ValueError):
        return []
    if not isinstance(catalog, dict) or not isinstance(catalog.get("reports"), list):
        return []
    entries = catalog["reports"]
    counts = Counter(
        entry["id"] for entry in entries if isinstance(entry, dict) and _valid_slug(entry.get("id"))
    )
    rows = []
    for entry in entries:
        if not isinstance(entry, dict) or not _valid_slug(entry.get("id")) or counts[entry["id"]] != 1:
            continue
        row = _present(root, entry)
        if row is not None:
            rows.append(row)
    rows.sort(key=lambda row: (row["published_date"], row["id"]), reverse=True)
    return rows


def get_finished_report(root: Path, report_id: str) -> dict[str, Any] | None:
    """Resolve an allowlisted report ID without interpreting it as a path."""
    if not _valid_slug(report_id):
        return None
    return next((row for row in list_finished_reports(root) if row["id"] == report_id), None)


def list_combined_finished_reports(roots: Iterable[Path]) -> list[dict[str, Any]]:
    """Combine packaged and private catalogs without allowing either to shadow.

    Each catalog retains its own asset boundary. Duplicate valid IDs across
    distinct roots are omitted, while unavailable catalogs and entries leave
    unrelated reports visible. Repeating the same physical root is harmless.
    """
    rows = []
    seen_roots = set()
    for candidate in roots:
        try:
            root = Path(candidate).resolve()
        except (OSError, RuntimeError, ValueError):
            continue
        if root in seen_roots:
            continue
        seen_roots.add(root)
        rows.extend(list_finished_reports(root))
    counts = Counter(row["id"] for row in rows)
    return sorted(
        (row for row in rows if counts[row["id"]] == 1),
        key=lambda row: (row["published_date"], row["id"]),
        reverse=True,
    )


def get_combined_finished_report(roots: Iterable[Path], report_id: str) -> dict[str, Any] | None:
    """Resolve one unambiguous report across independently confined catalogs."""
    if not _valid_slug(report_id):
        return None
    return next((row for row in list_combined_finished_reports(roots) if row["id"] == report_id), None)
