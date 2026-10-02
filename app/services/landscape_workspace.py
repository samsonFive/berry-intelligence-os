"""Read-only selection over existing Landscape records; saved views store selectors only."""
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode
from uuid import uuid4

from app.services import company_directory, personal_digest
from app.services.analyst_state_io import atomic_json, serialized_write
from app.services.berries.landscape import SEED_FIXTURE_EVIDENCE_IDS
from app.services.chronology import parse_stamp
from app.services.geography_hierarchy import record_geography_ids, resolve_geography_scope
from app.services.html_text import decode_html_text
from app.services.source_body import looks_like_interstitial
from app.services.variety_workspace import ROLE_BUCKETS

SECTIONS = {"companies": "Companies", "varieties": "Varieties", "sources": "Latest sources", "signals": "Signals", "assessments": "Assessments"}
FIELDS = ("berry", "company", "variety", "countries", "list", "tier", "favorites", "window", "start", "end", "section")
VIEW_FILE = "landscape_views.json"


def values(params, key):
    raw = params.getlist(key) if hasattr(params, "getlist") else params.get(key, [])
    raw = raw if isinstance(raw, (list, tuple)) else [raw]
    return list(dict.fromkeys(part.strip() for value in raw for part in str(value).split(",") if part.strip()))


def parameters(params, *, entities, companies, berries, state):
    filters = {key: ",".join(values(params, key)) for key in FIELDS}
    for field in ("berry", "company", "variety", "countries", "section"):
        choices = values(params, field + "_choice")
        if choices:
            filters[field] = ",".join(choices)
    allowed = {"berry": set(berries), "company": set(companies), "section": set(SECTIONS),
               "variety": {key for key, row in entities.items() if row.get("entity_type") == "variety"},
               "countries": {key for key, row in entities.items() if row.get("entity_type") == "geography"}}
    for field, choices in allowed.items():
        if set(values(filters, field)) - choices:
            raise ValueError(f"A saved {field} selection is unavailable; reset or choose current records")
    if filters["tier"] not in {"", *company_directory.TIERS} or filters["favorites"] not in {"", "1"}:
        raise ValueError("Choose supported company filters")
    if filters["list"] and filters["list"] not in {row["id"] for row in personal_digest.company_lists(state)}:
        raise ValueError("Company list is unavailable")
    if filters["window"] not in {"", "7d", "30d", "ytd", "custom"}:
        raise ValueError("Choose a supported source date range")
    if not filters["section"] and not params.get("configured"):
        filters["section"] = ",".join(SECTIONS)
    return filters


def source_window(filters, today):
    start = {"7d": today - timedelta(days=6), "30d": today - timedelta(days=29), "ytd": today.replace(month=1, day=1)}.get(filters["window"])
    end = today
    if filters["window"] == "custom":
        try:
            start = date.fromisoformat(filters["start"]) if filters["start"] else None
            end = date.fromisoformat(filters["end"]) if filters["end"] else today
        except ValueError:
            raise ValueError("Choose valid source dates") from None
        if start and start > end:
            raise ValueError("Start date must come before end date")
    return start, min(end, today)


def model(*, contexts, entities, companies, relationships, evidence, region_rows, state, params, berries, today=None):
    """Project existing company/variety/analysis rows, retaining explicit role and date bases.

    Country inventory uses active stored operating/growing/trial relationships.
    Date range applies only to sources; standing portfolios and analyses remain.
    No name guesses, photo candidates, live acquisition or trust mutations occur.
    """
    filters = parameters(params, entities=entities, companies=companies, berries=berries, state=state)
    selected_berries = set(values(filters, "berry")) or set(berries)
    company_scope, variety_scope = set(values(filters, "company")), set(values(filters, "variety"))
    geo_scope = set()
    for key in values(filters, "countries"):
        geo_scope.update(resolve_geography_scope(key, relationships=relationships).all_ids)
    start, end = source_window(filters, today or datetime.now(UTC).date())
    company_rows, variety_rows, analysis = {}, {}, {"signals": {}, "assessments": {}}
    for berry in sorted(selected_berries):
        context = contexts[berry]
        for field, target in (("competitive_field", company_rows), ("variety_rollup", variety_rows)):
            for row in context[field]:
                target.setdefault(row["entity"]["id"], row)
        for field, target in analysis.items():
            for row in context[field]:
                target.setdefault(row["id"], row)
    role_names = {predicate: label for _, predicate, label in ROLE_BUCKETS}
    roles = {}
    for rel in relationships:
        if rel.get("status") == "active" and rel.get("predicate") in role_names and rel.get("object_id") in variety_rows:
            roles.setdefault(rel["object_id"], []).append({"company_id": rel["subject_id"], "label": role_names[rel["predicate"]]})
    inventory_places = {}
    for row in region_rows:
        if row.get("basis") == "Existing relationship" and row.get("status") == "active":
            inventory_places.setdefault(row["entity_id"], set()).add(row["geography_id"])

    def marked(key):
        return (not company_scope or key in company_scope) and company_directory.matches_marks(
            [key], state, favorites=filters["favorites"], tier=filters["tier"], list_id=filters["list"])

    # Intersect personal filters on the same company before applying them to linked records.
    eligible_companies = {key for key in companies if marked(key)}
    company_restricted = bool(company_scope or filters["favorites"] or filters["tier"] or filters["list"])
    selected_varieties = {}
    for key, row in variety_rows.items():
        if variety_scope and key not in variety_scope:
            continue
        if geo_scope and not geo_scope.intersection(inventory_places.get(key, set())):
            continue
        if company_restricted and not any(role["company_id"] in eligible_companies for role in roles.get(key, [])):
            continue
        selected_varieties[key] = row
    selected_companies = {}
    for key, row in company_rows.items():
        if key not in eligible_companies:
            continue
        if geo_scope and not geo_scope.intersection(inventory_places.get(key, set())):
            continue
        if variety_scope and not any(role["company_id"] == key for vid in variety_scope for role in roles.get(vid, [])):
            continue
        selected_companies[key] = row

    def source_matches(row):
        linked = set(row.get("entity_ids") or []) | set(row.get("company_ids") or [])
        return ((not selected_berries or bool(selected_berries.intersection(row.get("berry_ids") or [])))
                and (not geo_scope or bool(geo_scope.intersection(record_geography_ids(row))))
                and (not company_restricted or bool(eligible_companies.intersection(linked)))
                and (not variety_scope or bool(variety_scope.intersection(linked))))

    source_rows, undated, supporting = [], [], {}
    for row in evidence:
        if row.get("status") != "published" or row["id"] in SEED_FIXTURE_EVIDENCE_IDS or not source_matches(row):
            continue
        supporting[row["id"]] = row
        stamp = parse_stamp(row.get("published_date"))
        if not stamp:
            undated.append({"id": row["id"], "title": row.get("title") or row.get("source_name") or "Untitled source"})
            continue
        if stamp.date() > end or start and stamp.date() < start:
            continue
        summary = decode_html_text(row.get("summary") or "")
        summary_blocked = looks_like_interstitial(summary)
        source_rows.append({"id": row["id"], "title": row.get("title") or row.get("source_name") or "Untitled source",
                            "source_name": row.get("source_name") or "Source not recorded", "date": stamp.date().isoformat(),
                            "summary": "" if summary_blocked else summary, "summary_blocked": summary_blocked,
                            "entity_ids": row.get("entity_ids") or []})
    source_rows.sort(key=lambda row: (row["date"], row["id"]), reverse=True)
    source_counts = {}
    for row in source_rows:
        for key in row["entity_ids"]:
            source_counts[key] = source_counts.get(key, 0) + 1

    def shown_analysis(row):
        linked = set(row.get("entity_ids") or [])
        explicit_berries = set(row.get("market_ids") or row.get("berry_ids") or [])
        if explicit_berries and not selected_berries.intersection(explicit_berries):
            return False
        if company_restricted and not linked.intersection(eligible_companies) or variety_scope and not linked.intersection(variety_scope):
            return False
        explicit = record_geography_ids(row)
        # An explicitly scoped analysis must not borrow a conflicting geographic scope.
        if not geo_scope:
            return True
        if explicit:
            return bool(geo_scope.intersection(explicit))
        return any(eid in supporting for eid in row.get("evidence_ids") or [])

    panels = {field: sorted([row for row in rows.values() if shown_analysis(row)], key=lambda row: row.get("title", "").casefold()) for field, rows in analysis.items()}
    panels["companies"] = [{**companies.get(key, row["entity"]), "source_count": source_counts.get(key, 0),
                            "variety_count": sum(any(r["company_id"] == key for r in roles.get(vid, [])) for vid in selected_varieties),
                            "places": [entities[gid]["name"] for gid in sorted(inventory_places.get(key, set())) if gid in entities]}
                           for key, row in sorted(selected_companies.items(), key=lambda item: item[1]["entity"]["name"].casefold())]
    panels["varieties"] = [{**row["entity"], "source_count": source_counts.get(key, 0),
                            "roles": [{**r, "name": companies.get(r["company_id"], {}).get("name", "Organization unavailable")} for r in roles.get(key, [])],
                            "places": [entities[gid]["name"] for gid in sorted(inventory_places.get(key, set())) if gid in entities]}
                           for key, row in sorted(selected_varieties.items(), key=lambda item: item[1]["entity"]["name"].casefold())]
    panels["sources"] = source_rows
    chips = [berries[key] for key in sorted(values(filters, "berry"))]
    chips.extend(entities.get(key, companies.get(key, {})).get("name", "Unavailable selection") for field in ("company", "variety", "countries") for key in values(filters, field))
    for field in ("tier", "favorites", "list"):
        if filters[field]:
            chips.append(company_directory.TIERS[filters[field]] if field == "tier" else "Favorites" if field == "favorites" else next(g["name"] for g in personal_digest.company_lists(state) if g["id"] == filters[field]))
    return {"filters": filters, "panels": panels, "sections": values(filters, "section"), "section_choices": SECTIONS,
            "chips": chips, "undated_sources": undated, "source_start": start, "source_end": end,
            "query": {**filters, "configured": "1"}, "excluded_company_count": len(company_rows) - len(selected_companies)}


def load_views(inbox_dir):
    path = Path(inbox_dir) / VIEW_FILE
    if not path.exists():
        return {"version": 1, "views": {}, "history": []}
    result = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(result, dict) or result.get("version") != 1 or not isinstance(result.get("views"), dict) or not isinstance(result.get("history"), list):
        raise ValueError("Saved Landscape views cannot be read; restore the file before editing")
    for key, row in result["views"].items():
        if (not isinstance(row, dict) or row.get("id") != key or not isinstance(row.get("name"), str)
                or not isinstance(row.get("filters"), dict) or type(row.get("revision")) is not int
                or row["revision"] < 1 or type(row.get("archived")) is not bool):
            raise ValueError("Saved Landscape views cannot be read; restore the file before editing")
    return result


@serialized_write
def save_view(inbox_dir, *, name, filters, view_id="", revision="0", archive=False):
    state = load_views(inbox_dir)
    if view_id and view_id not in state["views"]:
        raise ValueError("Saved Landscape view is unavailable")
    before = state["views"].get(view_id) or {"revision": 0}
    if str(before["revision"]) != str(revision):
        raise ValueError("Saved view changed in another window; reload before saving")
    name = str(name).strip()
    if not name or len(name) > 80:
        raise ValueError("Name the view using 1–80 characters")
    if not archive and any(key != view_id and not row.get("archived") and row["name"].casefold() == name.casefold() for key, row in state["views"].items()):
        raise ValueError("This view name already exists; choose it to update its scope")
    key = view_id or "lview-" + uuid4().hex
    row = {"id": key, "name": name, "filters": {field: str(filters.get(field) or "") for field in FIELDS},
           "revision": before["revision"] + 1, "archived": archive, "updated_at": datetime.now(UTC).isoformat()}
    state["views"][key] = row
    state["history"].append({"view_id": key, "before": before, "after": row})
    atomic_json(Path(inbox_dir) / VIEW_FILE, state)
    return row


def view_href(row):
    return "/landscapes?" + urlencode({**row["filters"], "configured": "1", "saved_view": row["id"]})
