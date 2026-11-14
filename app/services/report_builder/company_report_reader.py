"""Plain-text presentation for private company-news reports.

The native reader never researches, changes trust, or edits its input. Authored
reports and generated company-review snapshots share this view model so that
reading does not depend on a PDF-like iframe. The caller owns file confinement
and authentication; only an explicitly allowlisted JSON asset may be loaded.
"""
from __future__ import annotations

import json
import re
import unicodedata
from copy import deepcopy
from pathlib import Path
from typing import Any

from app.services.map_regions import public_source_url

MAX_READER_BYTES = 16 * 1024 * 1024
MAX_COMPANIES = 100
MAX_STORIES = 20000
MAX_SOURCES = 50000
_KEY = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
_DISPOSITIONS = {
    "pending": "Not researched yet",
    "has_findings": "Findings to review",
    "no_qualifying_findings": "No qualifying finding",
    "leads_only": "Reporting leads",
    "identity_unresolved": "Identity unresolved",
    "identity_ambiguous": "Identity needs clarification",
    "incomplete": "Research incomplete",
    "blocked": "Retrieval blocked",
}
_RESEARCH_STATUS = {
    "pending": "Not searched yet",
    "complete": "Searched within the configured bounds",
    "partial": "Partial search",
    "failed": "Search failed",
    "blocked": "Retrieval blocked",
    "not_requested": "Not requested",
}


def _text(value: Any, maximum: int = 20000) -> str:
    if value is None:
        return ""
    if not isinstance(value, str) or len(value) > maximum:
        raise ValueError("Invalid company report text")
    return value.strip()


def _strings(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > 100:
        raise ValueError("Invalid company report notes")
    return [_text(item) for item in value if item]


def _list(value: Any, maximum: int) -> list:
    if not isinstance(value, list) or len(value) > maximum:
        raise ValueError("Company report exceeds reader bounds")
    return value


def _key(name: str, index: int, seen: set[str], requested: Any = None) -> str:
    if requested is not None:
        key = _text(requested, 160)
        if not _KEY.fullmatch(key):
            raise ValueError("Invalid company reader key")
    else:
        ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
        key = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")[:100]
        key = key or f"company-{index + 1}"
        original = key
        suffix = 2
        while key in seen:
            key = f"{original}-{suffix}"
            suffix += 1
    if key in seen:
        raise ValueError("Duplicate company reader key")
    seen.add(key)
    return key


def _source(row: Any) -> dict:
    if not isinstance(row, dict):
        raise ValueError("Invalid company report source")
    url = _text(row.get("url") or row.get("source_url"), 4000)
    safe_url = public_source_url(url)
    return {
        "label": _text(row.get("label") or row.get("title") or "Supporting source", 1000),
        "url": safe_url,
        "link_unavailable": bool(url and not safe_url),
        "publication_date": _text(row.get("published_date") or row.get("publication_date"), 1000),
        "publication_date_basis": _text(row.get("publication_date_basis"), 250),
        "origin": _text(row.get("origin"), 100),
        "trust_class": _text(row.get("trust_class"), 250),
        "capture_status": _text(row.get("capture_status"), 250),
        "excerpt": _text(row.get("excerpt") or row.get("passage")),
    }


def _story(row: Any, key: str, index: int) -> dict:
    if not isinstance(row, dict):
        raise ValueError("Invalid company report story")
    headline = _text(row.get("headline"), 6000)
    if not headline:
        raise ValueError("Company report story needs a headline")
    entry_id = _text(row.get("id"), 200)
    story_key = entry_id if _KEY.fullmatch(entry_id) else f"{key}-story-{index + 1}"
    sources = [_source(source) for source in _list(row.get("sources", []), MAX_SOURCES)]
    return {
        "key": story_key,
        "id": entry_id,
        "number": index + 1,
        "headline": headline,
        "publication_date": _text(row.get("publication_date") or row.get("published_date"), 1000),
        "event_date": _text(row.get("event_date"), 6000),
        "summary": _text(row.get("summary")),
        "why_it_matters": _text(row.get("why_it_matters") or row.get("news_angle")),
        "caveat": _text(row.get("caveat") or row.get("qualification")),
        "entry_type": _text(row.get("entry_type"), 100),
        "review_status": _text(row.get("review_status"), 250),
        "analyst_edited": row.get("analyst_edited") is True,
        "included": row.get("included") if isinstance(row.get("included"), bool) else None,
        "sources": sources,
    }


def present_authored_company_report(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate an authored report without dropping findings or qualifications."""
    if not isinstance(payload, dict):
        raise ValueError("Invalid company report")
    companies = _list(payload.get("companies"), MAX_COMPANIES)
    if not companies:
        raise ValueError("Company report needs at least one company")
    title = _text(payload.get("title"), 1000)
    if not title:
        raise ValueError("Company report needs a title")
    seen: set[str] = set()
    rows = []
    for index, company in enumerate(companies):
        if not isinstance(company, dict):
            raise ValueError("Invalid company report company")
        name = _text(company.get("name"), 500)
        if not name:
            raise ValueError("Company report needs a company name")
        key = _key(name, index, seen, company.get("key"))
        stories = [_story(story, key, number) for number, story in enumerate(_list(company.get("stories", []), MAX_STORIES))]
        rows.append({
            "key": key,
            "name": name,
            "canonical_name": _text(company.get("canonical_name"), 500),
            "identity_label": _text(company.get("identity_label"), 250),
            "position": index + 1,
            "status": _text(company.get("status"), 500),
            "overview": _text(company.get("overview")),
            "platform": _text(company.get("platform")),
            "stories": stories,
            "story_count": len(stories),
            "follow_up": _text(company.get("follow_up")),
            "excluded": _text(company.get("excluded")),
            "notes": _strings(company.get("notes")),
            "archive_status": _text(company.get("archive_status"), 100),
            "archive_status_label": _RESEARCH_STATUS.get(company.get("archive_status"), _text(company.get("archive_status"), 100).replace("_", " ")),
            "web_status": _text(company.get("web_status"), 100),
            "web_status_label": _RESEARCH_STATUS.get(company.get("web_status"), _text(company.get("web_status"), 100).replace("_", " ")),
        })
    story_count = sum(row["story_count"] for row in rows)
    story_keys = [story["key"] for row in rows for story in row["stories"]]
    if len(story_keys) != len(set(story_keys)):
        raise ValueError("Duplicate company report entry key")
    source_count = sum(len(story["sources"]) for row in rows for story in row["stories"])
    if story_count > MAX_STORIES or source_count > MAX_SOURCES:
        raise ValueError("Company report exceeds reader bounds")
    executive = []
    for item in _list(payload.get("executive", []), 20):
        if not isinstance(item, dict):
            raise ValueError("Invalid report overview")
        executive.append({"title": _text(item.get("title"), 6000), "body": _text(item.get("body"))})
    return {
        "title": title,
        "subtitle": _text(payload.get("subtitle"), 2000),
        "as_of": _text(payload.get("as_of"), 1000),
        "scope": _text(payload.get("scope")),
        "executive": executive,
        "companies": rows,
        "company_count": len(rows),
        "story_count": story_count,
        "source_count": source_count,
        "unique_source_count": len({source["url"] for row in rows for story in row["stories"] for source in story["sources"] if source["url"]}),
        "priorities": _strings(payload.get("priorities")),
        "methodology": _strings(payload.get("methodology")),
        "coverage_notes": _strings(payload.get("coverage_notes")),
        "is_working": bool(payload.get("is_working", False)),
        "overview_label": _text(payload.get("overview_label") or "The main developments", 250),
    }


def load_company_report_reader(path: Path | None) -> dict[str, Any] | None:
    """Read one optional, already confined JSON asset; malformed data falls back."""
    if path is None:
        return None
    try:
        path = Path(path)
        if not path.is_file() or path.stat().st_size > MAX_READER_BYTES:
            return None
        with path.open("rb") as stream:
            body = stream.read(MAX_READER_BYTES + 1)
        if len(body) > MAX_READER_BYTES:
            return None
        payload = json.loads(body.decode("utf-8-sig"))
        if isinstance(payload, dict) and payload.get("schema_version") == 1 and "entries" in payload:
            return present_company_review(payload)
        return present_authored_company_report(payload)
    except (OSError, UnicodeError, ValueError, TypeError):
        return None


def select_company_reader(reader: dict[str, Any], company_key: str | None = None) -> dict[str, Any]:
    """Select one company with explicit navigation; unknown keys fail visibly."""
    companies = reader["companies"]
    if not company_key:
        return {"current_company": None, "previous_company": None, "next_company": None, "unknown_company": False}
    index = next((i for i, row in enumerate(companies) if row["key"] == company_key), None)
    if index is None:
        return {"current_company": None, "previous_company": None, "next_company": None, "unknown_company": True}
    return {
        "current_company": companies[index],
        "previous_company": companies[index - 1] if index else None,
        "next_company": companies[index + 1] if index + 1 < len(companies) else None,
        "unknown_company": False,
    }


def present_company_review(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Adapt a saved generated-review snapshot to the same read-only renderer."""
    if not isinstance(snapshot, dict) or snapshot.get("schema_version") != 1:
        raise ValueError("Invalid company review snapshot")
    companies = _list(snapshot.get("companies"), MAX_COMPANIES)
    sources = _list(snapshot.get("sources", []), MAX_SOURCES)
    from app.services.report_builder.company_news import effective_entry
    raw_entries = _list(snapshot.get("entries", []), MAX_STORIES)
    if any(not isinstance(entry, dict) for entry in raw_entries):
        raise ValueError("Invalid company review entry")
    entries = [effective_entry(entry) for entry in raw_entries]
    source_map = {row["id"]: row for row in sources if isinstance(row, dict) and isinstance(row.get("id"), str)}
    if len(source_map) != len(sources):
        raise ValueError("Company review source references are ambiguous")
    rows = []
    keys = set()
    for company in companies:
        if not isinstance(company, dict) or not isinstance(company.get("key"), str) or company["key"] in keys:
            raise ValueError("Company review company references are ambiguous")
        key = company["key"]
        keys.add(key)
        stories = []
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError("Invalid company review entry")
            if entry.get("company_key") != key:
                continue
            refs = _list(entry.get("source_ids", []), MAX_SOURCES)
            if any(not isinstance(ref, str) or ref not in source_map for ref in refs):
                raise ValueError("Company review source reference is missing")
            story = deepcopy(entry)
            story["sources"] = [source_map[ref] for ref in refs]
            stories.append(story)
        stories.sort(key=lambda story: (story.get("included") is True, str(story.get("published_date") or "")), reverse=True)
        included = [row for row in stories if row.get("included") is True]
        disposition = _text(company.get("disposition"), 100)
        identity_label = ""
        if company.get("identity_verification_required") is True:
            identity_label = "Unverified directory identity" if company.get("identity_status") == "unverified" else "Identity review required"
        rows.append({
            "key": key,
            "name": company.get("requested_name") or company.get("canonical_name"),
            "canonical_name": company.get("canonical_name"),
            "identity_label": identity_label,
            "status": identity_label or _DISPOSITIONS.get(disposition, disposition.replace("_", " ").capitalize()),
            "overview": included[0].get("headline") if included else (identity_label or _DISPOSITIONS.get(disposition) or "Research outcome not recorded"),
            "stories": stories,
            "notes": company.get("notes", []),
            "archive_status": company.get("archive_status", ""),
            "web_status": company.get("web_status", ""),
        })
    if any(entry.get("company_key") not in keys for entry in entries):
        raise ValueError("Company review entry has no requested company")
    included_entries = [entry for entry in entries if entry.get("included") is True]
    included_entries.sort(key=lambda entry: str(entry.get("published_date") or ""), reverse=True)
    name_by_key = {row["key"]: row["name"] for row in rows}
    executive = [{
        "title": entry.get("headline", ""),
        "body": f"{name_by_key[entry['company_key']]} — {entry.get('summary') or ''}",
    } for entry in included_entries[:3]]
    period = f"{_text(snapshot.get('from_date'), 100)} to {_text(snapshot.get('through_date'), 100)}"
    topic = _text(snapshot.get("topic"), 2000)
    payload = {
        "title": "Company news review",
        "subtitle": topic or period,
        "scope": f"Publication window: {period}." + (f" Focus: {topic}" if topic else ""),
        "as_of": snapshot.get("as_of", ""),
        "executive": executive,
        "companies": rows,
        "is_working": True,
        "overview_label": "Latest reported developments",
        "coverage_notes": ["This saved research draft requires analyst review. Findings and leads retain their source attribution and qualifications; no claim is approved by opening or exporting this report."],
    }
    return present_authored_company_report(payload)
