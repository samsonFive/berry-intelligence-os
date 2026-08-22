"""Normalize plant-patent bibliographic records without commercial inference."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any

from app.services.berries.variety import _normalize_patent_number

CULTIVAR_RE = re.compile(
    r"(?:named|variety named)\s+['\"‘’“”]([^'\"‘’“”]+)['\"‘’“”]",
    re.IGNORECASE,
)
BOTANICAL_RE = re.compile(
    r"\b((?:Vaccinium|Fragaria|Rubus)(?:\s+[×x]\s+|\s+)[A-Za-z][A-Za-z.\-]*)",
    re.IGNORECASE,
)
KIND_RE = re.compile(r"(P[23]|A1|B[12])$", re.IGNORECASE)
HTML_TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")

PATENT_DOES_NOT_PROVE = (
    "commercialization or planted acreage",
    "market adoption or sales success",
    "commercial launch timing",
    "that an inventor owns the IP (assignee/applicant may differ)",
    "licensee identity or exclusive territory",
)


def strip_markup(value: str | None) -> str:
    text = HTML_TAG_RE.sub("", value or "")
    return WHITESPACE_RE.sub(" ", text).strip()


def parse_iso_date(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = value.strip()[:10]
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", candidate):
        return candidate
    if re.fullmatch(r"\d{8}", value.strip()):
        raw = value.strip()
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
    return None


def names_as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [strip_markup(str(item)) for item in value if str(item).strip()]
    text = strip_markup(str(value))
    if not text:
        return []
    parts = re.split(r"\s*;\s*|\s+\band\b\s+", text)
    return [part.strip(" ,") for part in parts if part.strip(" ,")]


def extract_cultivar_name(title: str, abstract: str = "") -> str | None:
    for haystack in (title, abstract):
        match = CULTIVAR_RE.search(haystack or "")
        if match:
            name = match.group(1).strip()
            if name:
                return name
    return None


def extract_botanical_name(title: str, abstract: str = "") -> str | None:
    for haystack in (title, abstract):
        match = BOTANICAL_RE.search(haystack or "")
        if match:
            return re.sub(r"\s+", " ", match.group(1)).strip(" .")
    return None


def extract_kind_code(publication_number: str) -> str | None:
    match = KIND_RE.search(publication_number.replace(" ", "").upper())
    return match.group(1).upper() if match else None


def canonical_publication_number(value: str) -> str:
    compact = re.sub(r"[^A-Za-z0-9]", "", value or "").upper()
    return compact


def draft_id_for_publication(publication_number: str) -> str:
    slug = canonical_publication_number(publication_number).lower()
    return f"ev-patent-{slug}"


def google_patents_url(publication_number: str) -> str:
    return f"https://patents.google.com/patent/{canonical_publication_number(publication_number)}/en"


def content_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def normalize_discovery_hit(hit: dict[str, Any], *, acquired_at: datetime | None = None) -> dict[str, Any]:
    """Turn a discovery adapter hit into a patent_filing object.

    `hit` fields: publication_number, title, snippet/abstract, filing_date,
    publication_date, grant_date, inventor(s), assignee(s), applicant(s),
    source_url, acquisition_method, application_number, botanical_name.
    """

    acquired = (acquired_at or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    title = strip_markup(hit.get("title") or "")
    abstract = strip_markup(hit.get("abstract") or hit.get("snippet") or "")
    publication_number = canonical_publication_number(str(hit.get("publication_number") or ""))
    if not publication_number:
        raise ValueError("publication_number is required")
    inventors = names_as_list(hit.get("inventors") if hit.get("inventors") is not None else hit.get("inventor"))
    assignees = names_as_list(hit.get("assignees") if hit.get("assignees") is not None else hit.get("assignee"))
    applicants = names_as_list(hit.get("applicants") if hit.get("applicants") is not None else hit.get("applicant"))
    # Never copy inventors onto assignee/applicant.
    filing = {
        "publication_number": publication_number,
        "application_number": hit.get("application_number") or None,
        "title": title,
        "filing_date": parse_iso_date(hit.get("filing_date")),
        "publication_date": parse_iso_date(hit.get("publication_date") or hit.get("grant_date")),
        "grant_date": parse_iso_date(hit.get("grant_date")),
        "inventors": inventors,
        "applicants": applicants,
        "assignees": assignees,
        "botanical_name": strip_markup(hit.get("botanical_name"))
        or extract_botanical_name(title, abstract)
        or None,
        "cultivar_name": hit.get("cultivar_name") or extract_cultivar_name(title, abstract),
        "abstract": abstract or None,
        "jurisdiction": hit.get("jurisdiction") or ("US" if publication_number.startswith("US") else "unknown"),
        "kind_code": extract_kind_code(publication_number),
        "claims_locator": hit.get("claims_locator") or google_patents_url(publication_number),
        "source_url": hit.get("source_url") or google_patents_url(publication_number),
        "acquired_at": acquired,
        "acquisition_method": hit.get("acquisition_method") or "google_patents_json",
    }
    filing["content_sha256"] = content_hash(
        {key: value for key, value in filing.items() if key not in {"acquired_at", "content_sha256"}}
    )
    return filing


def patent_numbers_equivalent(left: str, right: str) -> bool:
    return _normalize_patent_number(left) == _normalize_patent_number(right)
