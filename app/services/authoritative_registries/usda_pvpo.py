"""USDA Plant Variety Protection Office — structured monthly status report.

There is no documented public PVPO API (verified 2026-09-01 against AMS
PVPO pages). Public structured access is the monthly Application Status
Report XLSX. ePVP is applicant-only. CMS/POD are search UIs, not APIs.
This module parses the XLSX and maps berry rows onto variety-candidate
fields. It never writes trusted Evidence or onboarded Sources.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any, BinaryIO, Callable

from openpyxl import load_workbook

from app.services.variety_universe.registry_import import import_registry_rows

STATUS_REPORT_URL = "https://www.ams.usda.gov/sites/default/files/media/PVPOApplicationStatus.xlsx"
SOURCE_ID = "usda-pvpo-application-status"
SOURCE_LABEL = "USDA PVPO Application Status Report"
JURISDICTION = "US"
NO_PUBLIC_API = True
UPDATE_CADENCE = "monthly"

# Header is row 2; column A is empty. Documented by live 2026-09-01 file.
HEADER_ROW = 2
COL = {
    "application_number": 2,
    "variety_name": 3,
    "experimental_name": 4,
    "scientific_name": 5,
    "common_name": 6,
    "applicant": 7,
    "application_date": 8,
    "certificate_status": 10,
    "status_date": 11,
    "issued_date": 12,
}

BERRY_COMMON = {
    "blueberry": "berry-blueberry",
    "blueberry, rootstock": "berry-blueberry",
    "strawberry": "berry-strawberry",
    "raspberry": "berry-raspberry",
    "blackberry": "berry-blackberry",
}
SCI_HINTS = (
    ("vaccinium", "berry-blueberry"),
    ("fragaria", "berry-strawberry"),
    ("rubus idaeus", "berry-raspberry"),
    ("rubus occidentalis", "berry-raspberry"),
    ("rubus ursinus", "berry-blackberry"),
    ("rubus allegheniensis", "berry-blackberry"),
)


class UsdaPvpoError(RuntimeError):
    pass


def berry_id_for(*, common_name: str, scientific_name: str) -> str | None:
    common = (common_name or "").strip().lower()
    if common in BERRY_COMMON:
        return BERRY_COMMON[common]
    sci = (scientific_name or "").strip().lower()
    for hint, berry_id in SCI_HINTS:
        if hint in sci:
            return berry_id
    return None


def _cell(ws: Any, row: int, key: str) -> Any:
    return ws.cell(row, COL[key]).value


def parse_status_workbook(data: bytes | BinaryIO | Path) -> list[dict[str, Any]]:
    """Parse the monthly AMS XLSX. Berry rows only. No HTML scrape."""
    if isinstance(data, Path):
        workbook = load_workbook(data, data_only=True)
    elif isinstance(data, (bytes, bytearray)):
        workbook = load_workbook(BytesIO(data), data_only=True)
    else:
        workbook = load_workbook(data, data_only=True)
    sheet = workbook[workbook.sheetnames[0]]
    header = [sheet.cell(HEADER_ROW, col).value for col in range(1, 14)]
    if "Application #" not in header and "Variety Name" not in header:
        raise UsdaPvpoError("PVPO status workbook is missing the Application # / Variety Name header")
    rows: list[dict[str, Any]] = []
    for index in range(HEADER_ROW + 1, (sheet.max_row or 0) + 1):
        common = str(_cell(sheet, index, "common_name") or "").strip()
        scientific = str(_cell(sheet, index, "scientific_name") or "").strip()
        berry_id = berry_id_for(common_name=common, scientific_name=scientific)
        if not berry_id:
            continue
        application_number = str(_cell(sheet, index, "application_number") or "").strip()
        name = str(_cell(sheet, index, "variety_name") or "").strip()
        if not application_number or not name:
            continue
        issued = _cell(sheet, index, "issued_date")
        rows.append(
            {
                "candidate_name": name,
                "denomination": name,
                "trade_name": str(_cell(sheet, index, "experimental_name") or "").strip(),
                "berry_id": berry_id,
                "crop": common,
                "scientific_name": scientific,
                "applicant": str(_cell(sheet, index, "applicant") or "").strip(),
                "breeder_owner": str(_cell(sheet, index, "applicant") or "").strip(),
                "application_number": application_number,
                "grant_number": application_number if issued else "",
                "application_date": str(_cell(sheet, index, "application_date") or ""),
                "grant_date": str(issued or ""),
                "status_date": str(_cell(sheet, index, "status_date") or ""),
                "registration_status": str(_cell(sheet, index, "certificate_status") or "").strip(),
                "jurisdiction": JURISDICTION,
                "geography_id": "geography-united-states",
                "source_id": SOURCE_ID,
                "source_label": SOURCE_LABEL,
                "source_url": STATUS_REPORT_URL,
                "source_type": "plant_breeders_rights_record",
                "source_tier": "tier_1_national_register",
            }
        )
    return rows


def fetch_status_report(*, get: Callable[..., Any] | None = None, timeout: float = 45.0) -> bytes:
    import httpx

    fetcher = get or httpx.get
    response = fetcher(
        STATUS_REPORT_URL,
        timeout=timeout,
        headers={"User-Agent": "berry-intelligence-os-pvpo/0.1"},
        follow_redirects=True,
    )
    response.raise_for_status()
    return response.content


def import_berry_rows(
    rows: list[dict[str, Any]],
    *,
    varieties: list[dict[str, Any]],
    inbox_dir: Path,
) -> dict[str, Any]:
    """Inbox Variety candidates only. Never trusted Evidence."""
    return import_registry_rows(rows, varieties=varieties, inbox_dir=inbox_dir)
