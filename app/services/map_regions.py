"""Shared private profile-region annotations over canonical geographic edges.

This is analyst working state, never a second published relationship/trust store.
An annotation cannot approve a relationship. Automated collection never writes it.
"""
import json
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

from app.services.analyst_state_io import atomic_json, serialized_write
from app.services.geography_hierarchy import resolve_geography_scope
from app.services.feed_first_reader import is_public_http_url


def public_source_url(value):
    value = str(value or "")
    try:
        from urllib.parse import urlsplit
        parts = urlsplit(value)
        return value if not parts.username and not parts.password and is_public_http_url(value) else ""
    except ValueError:
        return ""

FILENAME = "profile_region_annotations.json"
ACTIVITIES = {
    "company": ("Operations (unspecified)", "Growing", "Breeding / research", "Packing / processing", "Sales / distribution", "Headquarters"),
    "variety": ("Growing (unspecified)", "Commercial growing", "Trial", "Announced planting", "Historical growing"),
}


def load(inbox_dir):
    path = Path(inbox_dir) / FILENAME
    if not path.exists():
        return {"version": 1, "entries": {}, "history": []}
    # Fail visibly rather than overwrite a damaged history with an empty store.
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("version") != 1 or not isinstance(value.get("entries"), dict) or not isinstance(value.get("history"), list):
        raise ValueError("Region history cannot be read; restore the saved file before editing")
    return value


def catalog(entities, relationships, records, private=None):
    records = {r["id"]: r for r in records if r.get("id")}
    rows = {}
    for rel in relationships:
        actor, place = entities.get(rel.get("subject_id"), {}), entities.get(rel.get("object_id"), {})
        kind = actor.get("entity_type")
        if kind not in ACTIVITIES or place.get("entity_type") != "geography":
            continue
        predicate = rel.get("predicate")
        if predicate not in ({"operates_in"} if kind == "company" else {"grows", "trials"}):
            continue
        key = rel.get("id")
        if not key or rel.get("status") not in {"active", "historical", "disputed"}:
            continue
        support = [records[eid] for eid in rel.get("evidence_ids", []) if eid in records]
        rows[key] = {"id": key, "entity_id": actor["id"], "geography_id": place["id"],
                     "activity": "Operations (unspecified)" if kind == "company" else "Trial" if predicate == "trials" else "Growing (unspecified)",
                     "status": rel["status"], "observed_on": rel.get("effective_date") or "", "source_date": "",
                     "source_id": support[0]["id"] if support else "", "source_url": public_source_url(support[0].get("source_url")) if support else "",
                     "evidence_ids": rel.get("evidence_ids", []), "locality": "", "notes": rel.get("notes") or "",
                     "basis": "Existing relationship", "revision": 0,
                     "scope_note": "Relationship scope needs review" if "substituted predicate" in (rel.get("notes") or "").lower() else ""}
    for key, row in (private or {}).get("entries", {}).items():
        if row.get("removed"):
            rows.pop(key, None)
        else:
            rows[key] = {**row, "basis": "User annotation · not reviewed"}
    result = []
    for row in rows.values():
        actor, place = entities.get(row.get("entity_id"), {}), entities.get(row.get("geography_id"), {})
        if actor.get("entity_type") not in ACTIVITIES or place.get("entity_type") != "geography":
            continue
        result.append({**row, "name": actor["name"], "kind": actor["entity_type"], "country": place["name"],
                       "berry_ids": actor.get("berry_ids") or [], "profile_url": f"/entities/{actor['entity_type']}/{actor['id']}",
                       "source_url": public_source_url(row.get("source_url"))})
    return result


def scoped(rows, query, relationships, state, *, kind, company="", list_id="", tier="", status="", activity="", entity_id="", as_of=""):
    scope = set()
    for key in query.geography_ids:
        scope.update(resolve_geography_scope(key, relationships=relationships).all_ids)
    from app.services.personal_digest import company_lists
    groups = company_lists(state)
    group = next((row for row in groups if row["id"] == list_id), None)
    if list_id and group is None:
        raise ValueError("Company list is unavailable")
    result = []
    for row in rows:
        if row["kind"] != kind or (scope and row["geography_id"] not in scope) or (query.country_codes and not scope):
            continue
        if entity_id and row["entity_id"] != entity_id:
            continue
        if as_of and row.get("observed_on") and row["observed_on"] > as_of:
            continue
        if query.commodities() and not set(query.commodities()).intersection(row["berry_ids"]):
            continue
        if status and row["status"] != status or activity and row["activity"] != activity:
            continue
        # Company scope on varieties uses actual stored roles, never photo associations.
        actors = {row["entity_id"]} if kind == "company" else {
            rel["subject_id"] for rel in relationships if rel.get("object_id") == row["entity_id"]
            and rel.get("predicate") in {"owns", "develops", "licenses", "grows", "trials", "markets", "distributes"}
            and rel.get("status") == "active"}
        if company and company not in actors or group and not actors.intersection(group.get("company_ids", [])):
            continue
        if tier and not any((state.get("entity_tiers", {}).get(key) or "untiered") == tier for key in actors):
            continue
        result.append(row)
    return sorted(result, key=lambda row: (row["name"].casefold(), row["country"].casefold(), row["id"]))


@serialized_write
def edit(inbox_dir, *, payload, entities, relationships, records, facts=(), reviewer=""):
    state = load(inbox_dir)
    rows = {row["id"]: row for row in catalog(entities, relationships, records, state)}
    key = str(payload.get("id") or "")
    old = rows.get(key)
    if key and old is None:
        raise ValueError("Region no longer exists; reload before editing")
    if old and str(old["revision"]) != str(payload.get("revision", "")):
        raise ValueError("This region changed in another view; reload before saving")
    action = str(payload.get("action") or "save")
    if action not in {"save", "remove"} or action == "remove" and not old:
        raise ValueError("Choose a valid region action")
    key = key or "region-" + uuid4().hex
    if action == "remove":
        row = {**old, "removed": True}
    else:
        entity_id, geo_id = str(payload.get("entity_id") or ""), str(payload.get("geography_id") or "")
        actor = entities.get(entity_id, {})
        if actor.get("entity_type") not in ACTIVITIES or entities.get(geo_id, {}).get("entity_type") != "geography":
            raise ValueError("Choose a known company or variety and geography")
        if old and old["entity_id"] != entity_id:
            raise ValueError("An existing region cannot be moved to another profile")
        activity = str(payload.get("activity") or "")
        status = str(payload.get("status") or "proposed")
        if activity not in ACTIVITIES[actor["entity_type"]] or status not in {"proposed", "active", "historical", "disputed"}:
            raise ValueError("Choose a supported activity and location status")
        dates = {}
        for field in ("observed_on", "source_date"):
            value = str(payload.get(field) or "")
            if value:
                if date.fromisoformat(value).isoformat() != value:
                    raise ValueError("Use dates in YYYY-MM-DD format")
            dates[field] = value
        source_id = str(payload.get("source_id") or "")
        fact_id = str(payload.get("fact_id") or "")
        fact = next((f for f in facts if f.get("id") == fact_id and f.get("status") == "active" and entity_id in (f.get("entity_ids") or [])), None) if fact_id else None
        if fact_id and not fact:
            raise ValueError("Choose a reviewed statement linked to this profile")
        if fact and not source_id:
            source_id = next((key for key in fact.get("evidence_ids", []) if any(r.get("id") == key for r in records)), "")
        linked = next((r for r in records if r.get("id") == source_id), None) if source_id else None
        relationship_sources = {eid for rel in relationships if rel.get("subject_id") == entity_id for eid in rel.get("evidence_ids", [])}
        if fact:
            if source_id and source_id not in fact.get("evidence_ids", []):
                raise ValueError("Supporting source must belong to the selected statement")
            relationship_sources.update(fact.get("evidence_ids", []))
        if source_id and (not linked or entity_id not in (linked.get("entity_ids") or []) and entity_id not in (linked.get("company_ids") or []) and source_id not in relationship_sources):
            raise ValueError("Choose a source linked to this profile")
        source_url = str(payload.get("source_url") or "").strip()
        if source_url and public_source_url(source_url) != source_url:
            raise ValueError("Use a complete public http or https source link")
        if linked and not source_url:
            source_url = public_source_url(linked.get("source_url"))
        row = {"id": key, "entity_id": entity_id, "geography_id": geo_id, "activity": activity, "status": status,
               "source_id": source_id, "fact_id": fact_id, "source_url": source_url, "evidence_ids": [source_id] if source_id else [],
               "locality": str(payload.get("locality") or "").strip()[:120], "notes": str(payload.get("notes") or "").strip()[:2000], **dates}
    row["revision"] = (old or {}).get("revision", 0) + 1
    row["updated_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    state["history"].append({"action": action, "before": old, "after": row.copy(), "reviewer": reviewer, "at": row["updated_at"]})
    state["entries"][key] = row
    atomic_json(Path(inbox_dir) / FILENAME, state)
    return row
