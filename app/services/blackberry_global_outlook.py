"""Private, dated leadership research with live links into the shared inventory.

The research package is authored content, not canonical genetics, acreage or
verified Facts. Opening or filtering this read model performs no acquisition,
promotion, alias resolution or writes.
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlencode

from app.services.map_regions import public_source_url

PATH = "/landscapes/global/blackberry/2027"
PACKAGE = Path("blackberry_global_2027/overview.json")
HABITS = {"primocane": "Primocane", "floricane": "Floricane", "unknown": "Not established"}
CATEGORIES = {
    "commercial_supply": "Commercial supply", "planting": "Planting / expansion",
    "license": "Licensing", "trial": "Trials", "nursery": "Nursery availability",
    "rights": "Variety rights", "platform": "Commercial platform",
}
REGIONS = {"north-america": "North America", "latin-america": "Latin America",
           "europe": "Europe", "mea": "Middle East and Africa", "asia-pacific": "Asia-Pacific"}
_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
_SOURCE_ID = re.compile(r"[A-Za-z0-9]+(?:[-_][A-Za-z0-9]+)*\Z")


def available(inbox_dir):
    return (Path(inbox_dir) / PACKAGE).is_file()


def load(inbox_dir):
    root = Path(inbox_dir).resolve()
    path = (root / PACKAGE).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        return None
    if path.stat().st_size > 6_000_000:
        raise ValueError("The blackberry research package exceeds the supported size.")
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise ValueError("The blackberry research package could not be read.") from exc
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ValueError("The blackberry research package has an unsupported format.")
    if not _day(data.get("as_of")):
        raise ValueError("The blackberry research package needs its research date.")
    for key in ("sources", "companies", "varieties", "commitments", "developments", "regions", "executive_findings"):
        if not isinstance(data.get(key, []), list) or any(not isinstance(row, dict) for row in data.get(key, [])):
            raise ValueError("The blackberry research package contains a malformed section.")
        ids = [row.get("id") for row in data.get(key, []) if row.get("id")]
        identifier = _SOURCE_ID if key == "sources" else _ID
        if any(not isinstance(item, str) or not identifier.fullmatch(item) for item in ids) or len(ids) != len(set(ids)):
            raise ValueError("The blackberry research package contains ambiguous identifiers.")
    for field, section in (("source_ids", "sources"), ("company_ids", "companies"), ("variety_ids", "varieties")):
        known = {row.get("id") for row in data.get(section, [])}
        for rows in (data.get(key, []) for key in ("companies", "varieties", "commitments", "developments", "regions", "executive_findings")):
            for row in rows:
                values = row.get(field, [])
                if not isinstance(values, list) or any(not isinstance(value, str) or value not in known for value in values):
                    raise ValueError("The blackberry research package contains an unresolved reference.")
    return data


def _day(value):
    try:
        return date.fromisoformat(str(value)).isoformat()
    except ValueError:
        return ""


def _ids(row, key):
    value = row.get(key, [])
    return {str(item) for item in value if isinstance(item, str)} if isinstance(value, list) else set()


def href(filters=None, **changes):
    params = {key: value for key, value in (filters or {}).items() if value}
    params.update(changes)
    return PATH + ("?" + urlencode({key: value for key, value in params.items() if value}) if any(params.values()) else "")


def _profile(row, entities, kind):
    entity = entities.get(row.get("entity_id")) or {}
    if entity.get("entity_type") != kind:
        return ""
    # A reviewed name bridge must already identify the canonical blackberry.
    if kind == "variety" and "berry-blackberry" not in (entity.get("berry_ids") or []):
        return ""
    return f"/entities/{kind}/{entity['id']}"


def model(data, params, entities):
    filters = {key: str(params.get(key) or "").strip()[:160]
               for key in ("region", "habit", "category", "company", "variety", "q")}
    companies = {row["id"]: dict(row) for row in data.get("companies", []) if row.get("id")}
    varieties = {row["id"]: dict(row) for row in data.get("varieties", []) if row.get("id")}
    for field, choices in (("region", REGIONS), ("habit", HABITS), ("category", CATEGORIES),
                           ("company", companies), ("variety", varieties)):
        if filters[field] and filters[field] not in choices:
            raise ValueError(f"Choose a supported {field.replace('_', ' ')}.")
    sources = {row["id"]: {**row, "url": public_source_url(row.get("url")),
                            "published_date": _day(row.get("published_date"))}
               for row in data.get("sources", []) if row.get("id")}

    def cited(row):
        return [sources[key] for key in row.get("source_ids", []) if key in sources]

    def matches(row, extra=""):
        return (not filters["q"] or filters["q"].casefold() in
                (" ".join(str(row.get(key) or "") for key in
                          ("name", "title", "aliases", "summary", "notable_reason", "outlook_2027", "scale", "implication"))
                 + " " + extra).casefold())

    for key, row in companies.items():
        row.update(profile_href=_profile(row, entities, "company"), sources=cited(row),
                   href=href(filters, company=key, variety=""))
    for key, row in varieties.items():
        row["companies"] = [companies[item] for item in row.get("company_ids", []) if item in companies]
        row.update(profile_href=_profile(row, entities, "variety"), sources=cited(row),
                   href=href(filters, variety=key, company=""),
                   habit_label=HABITS.get(row.get("habit"), "Not established"))
        row["region_labels"] = [REGIONS[item] for item in row.get("regions", []) if item in REGIONS]
        report_url = str(row.get("report_url") or "")
        row["report_href"] = (report_url if re.fullmatch(r"/reports/library/[a-z0-9-]+", report_url)
                              else public_source_url(report_url))

    # Filter whole commitment records. A worldwide license never creates a
    # planting location; regional scope is only the package's attributed scope.
    commitments = []
    matched_commitment_varieties = set()
    for original in data.get("commitments", []):
        row = dict(original)
        linked_varieties = _ids(row, "variety_ids")
        linked_companies = _ids(row, "company_ids")
        if filters["region"] and filters["region"] not in _ids(row, "regions"):
            continue
        if filters["category"] and row.get("category") != filters["category"]:
            continue
        if filters["company"] and filters["company"] not in linked_companies:
            continue
        if filters["variety"] and filters["variety"] not in linked_varieties:
            continue
        if filters["habit"] and not any(varieties.get(key, {}).get("habit") == filters["habit"] for key in linked_varieties):
            continue
        names = " ".join(varieties[key]["name"] for key in linked_varieties if key in varieties)
        names += " " + " ".join(companies[key]["name"] for key in linked_companies if key in companies)
        if not matches(row, names):
            continue
        row.update(sources=cited(row), category_label=CATEGORIES.get(row.get("category"), "Other commitment"),
                   date=_day(row.get("date")),
                   varieties=[varieties[key] for key in row.get("variety_ids", []) if key in varieties],
                   companies=[companies[key] for key in row.get("company_ids", []) if key in companies])
        commitments.append(row)
        matched_commitment_varieties.update(linked_varieties)
    commitments.sort(key=lambda row: (row["date"], row.get("title", "")), reverse=True)

    visible_varieties = []
    for key, row in varieties.items():
        if filters["region"] and filters["region"] not in _ids(row, "regions"):
            continue
        if filters["habit"] and row.get("habit") != filters["habit"]:
            continue
        if filters["company"] and filters["company"] not in _ids(row, "company_ids"):
            continue
        if filters["variety"] and filters["variety"] != key:
            continue
        if filters["category"] and key not in matched_commitment_varieties:
            continue
        if not matches(row, " ".join(company["name"] for company in row["companies"])):
            # A matching commitment can explain a variety's inclusion.
            if not (filters["q"] and key in matched_commitment_varieties):
                continue
        row["commitments"] = [item for item in commitments if key in _ids(item, "variety_ids")]
        visible_varieties.append(row)

    visible_company_ids = {item for row in visible_varieties for item in _ids(row, "company_ids")}
    visible_company_ids.update(item for row in commitments for item in _ids(row, "company_ids"))
    visible_companies = [row for key, row in companies.items() if key in visible_company_ids
                         or not any(filters.values()) or filters["company"] == key]
    regions = [{**row, "href": href(filters, region=row["id"], company="", variety=""), "sources": cited(row)}
               for row in data.get("regions", []) if row.get("id") in REGIONS]
    selected_region = next((row for row in regions if row["id"] == filters["region"]), None)

    developments = []
    scope_varieties = {row["id"] for row in visible_varieties}
    for original in data.get("developments", []):
        row = dict(original)
        if filters["region"] and filters["region"] not in _ids(row, "regions"):
            continue
        if filters["company"] and filters["company"] not in _ids(row, "company_ids"):
            continue
        if filters["variety"] and filters["variety"] not in _ids(row, "variety_ids"):
            continue
        if (filters["habit"] or filters["category"]) and not scope_varieties.intersection(_ids(row, "variety_ids")):
            continue
        if filters["q"] and not matches(row) and not scope_varieties.intersection(_ids(row, "variety_ids")):
            continue
        row.update(sources=cited(row), date=_day(row.get("date")))
        developments.append(row)
    developments.sort(key=lambda row: (row["date"], row.get("title", "")), reverse=True)
    report_id = str((data.get("report") or {}).get("id") or "")
    report = ({"href": f"/reports/library/{report_id}",
               "download_href": f"/reports/library/{report_id}/download.pdf"} if _ID.fullmatch(report_id) else {})
    selected_variety = varieties.get(filters["variety"])
    selected_company = companies.get(filters["company"])
    return {"title": data.get("title") or "Global blackberry outlook 2027", "as_of": data["as_of"],
            "season": data.get("season") or "2027", "filters": filters, "path": PATH,
            "habits": HABITS, "categories": CATEGORIES, "region_choices": REGIONS,
            "company_choices": list(companies.values()), "variety_choices": list(varieties.values()),
            "findings": [{**row, "sources": cited(row)} for row in data.get("executive_findings", [])],
            "varieties": visible_varieties, "companies": visible_companies, "commitments": commitments,
            "developments": developments, "regions": regions, "selected_region": selected_region,
            "selected_variety": selected_variety, "selected_company": selected_company,
            "sources": list(sources.values()), "report": report, "limitations": data.get("limitations", []),
            "clear_focus_href": href(filters, company="", variety=""), "scope_variety_ids": scope_varieties,
            "scope_company_ids": visible_company_ids}


def related_news(records, view, *, today=None, limit=8):
    """Newest known source dates, exact existing links/URLs, no invented joins."""
    today = today or date.today()
    varieties = view["variety_choices"]
    companies = view["company_choices"]
    canonical_ids = {row.get("entity_id") for row in varieties if row["id"] in view["scope_variety_ids"]}
    canonical_ids.update(row.get("entity_id") for row in companies if row["id"] in view["scope_company_ids"])
    canonical_ids.discard(None)
    canonical_ids.discard("")
    # A selected company must not widen back to all companies associated with
    # a multi-party cultivar. Its exact source links still provide recall.
    if view["selected_company"]:
        canonical_ids = {view["selected_company"].get("entity_id")} - {None, ""}
    elif view["selected_variety"]:
        canonical_ids = {view["selected_variety"].get("entity_id")} - {None, ""}
    source_urls = {source["url"] for row in [*view["varieties"], *view["commitments"], *view["developments"]]
                   for source in row.get("sources", []) if source.get("url")}
    narrowed = any(view["filters"].values())
    matched = []
    for row in records:
        if not row.get("id") or row.get("status") in {"rejected", "archived"}:
            continue
        if row.get("archived") or row.get("rejected"):
            continue
        crops = _ids(row, "berry_ids")
        if crops and "berry-blackberry" not in crops:
            continue
        linked = bool(canonical_ids.intersection(_ids(row, "entity_ids")))
        exact_source = bool(public_source_url(row.get("source_url")) in source_urls)
        if narrowed and not (linked or exact_source):
            continue
        if not narrowed and not ("berry-blackberry" in crops or linked or exact_source):
            continue
        stamp = _day(str(row.get("published_date") or "")[:10])
        if stamp and stamp > today.isoformat():
            continue
        matched.append((stamp, row))
    matched.sort(key=lambda pair: (pair[0], pair[1]["id"]), reverse=True)
    return [row for _, row in matched[:limit]], len(matched)
