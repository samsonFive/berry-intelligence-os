"""Map workspace projections; snapshot annotations require explicit selection."""
import json
from pathlib import Path

from app.services import global_explorer, map_regions, news_workspace
from app.services.geography_hierarchy import resolve_geography_scope
from app.services.market_statistics_reference import identified_groups, flag_label

SNAPSHOT_SCOPE_KEYS = ("view", "layer", "company", "list", "tier", "favorites", "region_status", "activity", "region_entity", "region_asof", "q", "window", "start", "end", "tz")


def snapshot_regions(query, entities, relationships, records, state, params, *, inbox_dir=None, authoring=False):
    """Reuse shared region scope without starting research or exposing its raw store."""
    filters = news_workspace.parameters(params)
    layer = str(params.get("layer") or "news")
    status, activity = str(params.get("region_status") or ""), str(params.get("activity") or "")
    entity_id, as_of = str(params.get("region_entity") or ""), str(params.get("region_asof") or "")
    if layer not in {"news", "companies", "varieties"} or status not in {"", "proposed", "active", "historical", "disputed"}:
        raise ValueError("Choose a supported map layer and location status")
    if activity and activity not in sum(map_regions.ACTIVITIES.values(), ()):
        raise ValueError("Choose a supported activity")
    if entity_id and entities.get(entity_id, {}).get("entity_type") != ("variety" if layer == "varieties" else "company"):
        raise ValueError("Choose a profile for this map layer")
    if as_of:
        from datetime import date
        if date.fromisoformat(as_of).isoformat() != as_of:
            raise ValueError("Use an observed-by date in YYYY-MM-DD format")
    private = map_regions.load(inbox_dir) if authoring and inbox_dir else None
    rows = map_regions.catalog(entities, relationships, records, private)
    kinds = ("company", "variety") if layer == "news" else ("variety",) if layer == "varieties" else ("company",)
    sources = {r['id']: r for r in records if r.get('id')}
    return [{**row, 'source_date': row.get('source_date') or sources.get(row.get('source_id'), {}).get('published_date') or ''}
            for kind in kinds for row in map_regions.scoped(rows, query, relationships, state, kind=kind,
            company=filters["company"], list_id=filters["list"], tier=filters["tier"], favorites=filters["favorites"],
            status=status, activity=activity, entity_id=entity_id, as_of=as_of)]


def statistics(query, entities, records, relationships=(), *, inbox_dir=None, authoring=False):
    """Public reference context and existing published Trade observations, no sums."""
    source = Path(__file__).resolve().parents[2] / "data" / "configuration" / "market_statistics_reference.json"
    scope = set()
    for key in query.geography_ids:
        scope.update(resolve_geography_scope(key, relationships=relationships).all_ids)
    groups = []
    from app.services.map_statistics_refresh import references
    reference_groups = references(json.loads(source.read_text(encoding="utf-8"))["groups"], inbox_dir, authoring)
    for group in identified_groups(reference_groups):
        if query.geography_ids and group["country_id"] not in scope or query.country_codes and not scope:
            continue
        if query.commodities() and group["berry_id"] not in query.commodities():
            continue
        group["metrics"] = [{**metric, "status_label": flag_label(metric["source_flag"])} if "source_flag" in metric else metric for metric in group["metrics"]]
        groups.append(group)
    trades = []
    for record in records:
        observation = record.get("trade_observation") or {}
        if not observation or not news_workspace.source_reviewed(record):
            continue
        geo = observation.get("reporter_geography_id")
        if query.geography_ids and geo not in scope or query.country_codes and not scope:
            continue
        if query.commodities() and not set(query.commodities()).intersection(record.get("berry_ids") or []):
            continue
        series = observation.get("series") or []
        latest = max(series, key=lambda r: r.get("period") or "", default=None)
        if latest is None:
            continue
        trades.append({"id": record["id"], "country": entities.get(geo, {}).get("name") or observation.get("reporter_name") or "Unknown reporter",
                       "source": record.get("source_name") or "Trade source", "source_url": map_regions.public_source_url(record.get("source_url")),
                       "published_date": record.get("published_date") or "Unknown", "accessed_at": (observation.get("source_provenance") or {}).get("retrieved_at") or "Unknown",
                       "does_not_prove": record.get("does_not_prove") or [], "observation": observation, "latest": latest})
    # Explicit country/crop gaps, never a zero value. Global coverage is intentionally partial.
    wanted = query.commodities() or tuple("berry-" + key for key in ("blueberry", "strawberry", "raspberry", "blackberry"))
    places = [(key, entities[key]["name"]) for key in query.geography_ids]
    places += [("iso:" + code, global_explorer.boundary_countries()[code]) for code in query.country_codes]
    gaps = [f"{name} · {berry.removeprefix('berry-').title()}: no production reference recorded"
            for geo, name in places for berry in wanted if not any(g["country_id"] == geo and g["berry_id"] == berry for g in groups)]
    if not places:
        gaps = [f"{berry.removeprefix('berry-').title()}: no production reference in the initial dataset"
                for berry in wanted if not any(g["berry_id"] == berry for g in groups)]
    return {"groups": groups, "trades": trades, "gaps": gaps}


def model(*, query, records, entities, relationships, berries, facts, state, params, inbox_dir=None, authoring=False):
    layer = str(params.get("layer") or "news")
    if layer not in {"news", "companies", "varieties"}:
        raise ValueError("Choose News coverage, Company operating regions or Variety growing regions")
    status, activity = str(params.get("region_status") or ""), str(params.get("activity") or "")
    region_entity, as_of = str(params.get("region_entity") or ""), str(params.get("region_asof") or "")
    if region_entity and entities.get(region_entity, {}).get("entity_type") != ("variety" if layer == "varieties" else "company"):
        raise ValueError("Choose a profile for this map layer")
    if as_of:
        from datetime import date
        if date.fromisoformat(as_of).isoformat() != as_of:
            raise ValueError("Use an observed-by date in YYYY-MM-DD format")
    if status not in {"", "proposed", "active", "historical", "disputed"}:
        raise ValueError("Choose a supported location status")
    if activity and activity not in sum(map_regions.ACTIVITIES.values(), ()):
        raise ValueError("Choose a supported activity")
    news = news_workspace.model(records={r["id"]: r for r in records}, entities=entities, relationships=relationships, facts=facts, state=state,
                                params={**params, **query.params()})
    global_news = news_workspace.model(records={r["id"]: r for r in records}, entities=entities, relationships=relationships, facts=facts, state=state,
                                       params={**params, **query.params(), "countries": ""})
    ids = set(global_news["matching_ids"])
    result = global_explorer.explorer_model(query, [r for r in records if r["id"] in ids], entities, relationships, berries, facts=facts, state=state, present_entries=False)
    private = map_regions.load(inbox_dir) if authoring and inbox_dir else None
    catalog = map_regions.catalog(entities, relationships, records, private)
    kind = "variety" if layer == "varieties" else "company"
    rows = map_regions.scoped(catalog, query, relationships, state, kind=kind, company=news["filters"]["company"],
                             list_id=news["filters"]["list"], tier=news["filters"]["tier"], favorites=news["filters"]["favorites"], status=status, activity=activity, entity_id=region_entity, as_of=as_of)
    # Counts are over the whole scope; A–Z/search only hide table rows in the browser.
    country_rows = map_regions.scoped(catalog, global_explorer.IntelligenceQuery(berry_ids=query.commodities()), relationships, state,
                                     kind=kind, company=news["filters"]["company"], list_id=news["filters"]["list"], tier=news["filters"]["tier"], favorites=news["filters"]["favorites"], status=status, activity=activity, entity_id=region_entity, as_of=as_of)
    for country in result["countries"]:
        country_scope = resolve_geography_scope(country["id"], relationships=relationships).all_ids if not country.get("unavailable") else ()
        located = [row for row in country_rows if row["geography_id"] in country_scope]
        country["region_count"] = len(located)
        if layer != "news":
            country["berries"] = sorted({berries[key] for row in located for key in row["berry_ids"] if key in berries})
            country["companies"] = sorted({row["name"] for row in located})
    return {**result, **news, "total": news["matching"], "entries": [], "layer": layer, "region_rows": rows,
            "region_entities": sorted([e for e in entities.values() if e.get("entity_type") == kind], key=lambda e: e["name"].casefold()),
            "region_status": status, "activity": activity, "region_entity": region_entity, "region_asof": as_of, "activities": map_regions.ACTIVITIES[kind],
            "authoring_mode": authoring, "statistics": statistics(query, entities, records, relationships, inbox_dir=inbox_dir, authoring=authoring),
            "companies": sorted([e for e in entities.values() if e.get("entity_type") == "company"], key=lambda e: e["name"].casefold())}
