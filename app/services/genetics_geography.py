"""Classify in-scope vs related cross-geography genetics — not a hard geo block.

A geography-scoped genetics answer may keep an extra-regional item when it
shares an explicit Variety, breeding program, IP family, or multi-company
platform with in-scope activity. A lone Company match is not enough.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Iterable, Mapping

IN_SCOPE = "IN-SCOPE"
CROSS_GEO = "CROSS-GEOGRAPHY RELATED"
GLOBAL_PLATFORM = "GLOBAL / PLATFORM CONTEXT"
OUT_OF_SCOPE = "OUT-OF-SCOPE"

_GENETICS_KINDS = {
    "GENETICS_LAUNCH",
    "VARIETY_LAUNCH",
    "GENETICS_INNOVATION",
    "R&D / TECHNOLOGY",
    "VARIETY_COMMERCIALIZATION",
    "LICENSING",
    "PBR / IP",
    "PBR",
    "PATENT",
    "PBR / PVP",
}


def _as_ids(values: Any) -> set[str]:
    return {str(value) for value in (values or []) if value}


def _kind(row: Mapping[str, Any]) -> str:
    return str(row.get("move_type") or row.get("event_type") or row.get("structured_kind") or "")


def _company_ids(row: Mapping[str, Any]) -> set[str]:
    ids = {str(value) for value in (row.get("company_ids") or []) if str(value).startswith("company-")}
    if row.get("company_id"):
        ids.add(str(row["company_id"]))
    ids.update(
        str(value)
        for value in (row.get("entity_ids") or [])
        if str(value).startswith("company-")
    )
    return ids


def _parse_day(value: Any) -> date | None:
    text = str(value or "")[:10]
    if len(text) < 10:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _event_day(row: Mapping[str, Any]) -> date | None:
    for key in ("published_date", "event_date", "effective_date", "date", "latest_update", "first_seen"):
        stamp = _parse_day(row.get(key))
        if stamp:
            return stamp
    return None


def _row_id(row: Mapping[str, Any]) -> str:
    return str(row.get("id") or "")


def _title(row: Mapping[str, Any]) -> str:
    return str(row.get("title") or row.get("what_happened") or _row_id(row))


def is_genetics_kind(row: Mapping[str, Any]) -> bool:
    kind = _kind(row)
    if kind in _GENETICS_KINDS:
        return True
    if row.get("patent_filing") or row.get("cpvo_filing"):
        return True
    return bool(genetics_object_ids(row))


def genetics_object_ids(row: Mapping[str, Any]) -> set[str]:
    """Explicit genetics objects only — never inferred from a Company catalog."""
    ids = _as_ids(row.get("variety_ids"))
    for value in row.get("entity_ids") or []:
        text = str(value)
        if text.startswith("variety-") or text.startswith("breeding_program-"):
            ids.add(text)
    if row.get("patent_filing") or row.get("cpvo_filing") or _kind(row) in {"PATENT", "PBR / PVP", "PBR"}:
        if _row_id(row):
            ids.add(f"ip:{_row_id(row)}")
    return ids


def platform_partner_ids(row: Mapping[str, Any]) -> set[str]:
    """Companies on a genetics/platform event. A lone company is not a platform."""
    companies = _company_ids(row)
    if len(companies) >= 2:
        return companies
    if is_genetics_kind(row):
        return companies
    return set()


def _geography_ids(row: Mapping[str, Any]) -> set[str]:
    from app.services.geography_hierarchy import record_geography_ids

    return record_geography_ids(row)


def _in_scope_geo(row: Mapping[str, Any], scope_geo_ids: Iterable[str]) -> bool:
    from app.services.geography_hierarchy import geography_scope_match

    scope = {str(value) for value in (scope_geo_ids or []) if value}
    if not scope:
        return True
    return geography_scope_match(_geography_ids(row), scope)


def _berry_ok(row: Mapping[str, Any], berry_id: str | None) -> bool:
    if not berry_id:
        return True
    berries = {str(value) for value in (row.get("berry_ids") or row.get("market_ids") or []) if value}
    if berries and berry_id not in berries:
        return False
    if not berries:
        return False
    return True


def _geo_labels(row: Mapping[str, Any], entities: Mapping[str, dict[str, Any]] | None = None) -> list[str]:
    labels = [str(value) for value in (row.get("geography_labels") or []) if value]
    if labels:
        return labels
    entities = entities or {}
    names = []
    for geo_id in sorted(_geography_ids(row)):
        name = (entities.get(geo_id) or {}).get("name") or geo_id.removeprefix("geography-").replace("-", " ")
        names.append(str(name))
    return names


def _object_label(object_id: str, entities: Mapping[str, dict[str, Any]] | None = None) -> str:
    entities = entities or {}
    if object_id.startswith("ip:"):
        return f"IP family {object_id[3:]}"
    entity = entities.get(object_id) or {}
    return str(entity.get("name") or object_id)


def _connection_reason(
    row: Mapping[str, Any],
    *,
    in_objects: set[str],
    in_partners: set[str],
    entities: Mapping[str, dict[str, Any]] | None = None,
) -> str:
    shared_objects = sorted(genetics_object_ids(row) & in_objects)
    shared_partners = sorted(platform_partner_ids(row) & in_partners)
    parts: list[str] = []
    for object_id in shared_objects[:3]:
        if object_id.startswith("variety-"):
            parts.append(f"same Variety: {_object_label(object_id, entities)}")
        elif object_id.startswith("breeding_program-"):
            parts.append(f"same breeding platform: {_object_label(object_id, entities)}")
        elif object_id.startswith("ip:"):
            parts.append(f"same IP family: {_object_label(object_id, entities)}")
        else:
            parts.append(f"same genetics object: {_object_label(object_id, entities)}")
    if len(shared_partners) >= 2:
        names = [_object_label(cid, entities) for cid in shared_partners[:4]]
        parts.append("same licensing / genetics platform (" + ", ".join(names) + ")")
    return "; ".join(parts) or "explicit genetics relationship with in-scope activity"


def _continents(geo_ids: set[str]) -> set[str]:
    continents = set()
    for geo_id in geo_ids:
        text = geo_id.removeprefix("geography-")
        if text in {"europe", "germany", "spain", "united-kingdom", "netherlands", "portugal", "france", "italy", "poland"}:
            continents.add("europe")
        elif text in {"peru", "mexico", "united-states", "canada", "chile", "americas", "north-america", "south-america", "brazil", "argentina", "colombia"}:
            continents.add("americas")
        elif text in {"china", "japan", "australia", "new-zealand", "apac"}:
            continents.add("apac")
        elif text in {"morocco", "egypt", "south-africa", "africa"}:
            continents.add("africa")
    return continents


def classify_row(
    row: Mapping[str, Any],
    *,
    scope_geo_ids: Iterable[str],
    berry_id: str | None,
    in_objects: set[str],
    in_partners: set[str],
    entities: Mapping[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    payload = dict(row)
    if not _berry_ok(row, berry_id):
        payload["_geo_class"] = OUT_OF_SCOPE
        payload["_geo_reason"] = "Different berry, or no explicit berry on the record."
        return payload
    if _in_scope_geo(row, scope_geo_ids):
        payload["_geo_class"] = IN_SCOPE
        payload["_geo_reason"] = "Directly occurred in the requested geography."
        payload["_geo_labels"] = _geo_labels(row, entities)
        return payload
    objects = genetics_object_ids(row)
    partners = platform_partner_ids(row)
    shared_objects = objects & in_objects
    shared_partners = partners & in_partners
    platform_hit = len(shared_partners) >= 2 and len(partners) <= 6
    if not shared_objects and not platform_hit:
        payload["_geo_class"] = OUT_OF_SCOPE
        payload["_geo_reason"] = "No explicit Variety, platform, IP, or multi-company program link — company match alone is not enough."
        return payload
    continents = _continents(_geography_ids(row))
    geo_class = GLOBAL_PLATFORM if len(continents) >= 2 else CROSS_GEO
    payload["_geo_class"] = geo_class
    payload["_geo_reason"] = _connection_reason(
        row, in_objects=in_objects, in_partners=in_partners, entities=entities
    )
    payload["_geo_labels"] = _geo_labels(row, entities)
    return payload


def _in_scope_keys(rows: Iterable[Mapping[str, Any]]) -> tuple[set[str], set[str]]:
    objects: set[str] = set()
    partners: set[str] = set()
    for row in rows:
        objects.update(genetics_object_ids(row))
        partners.update(platform_partner_ids(row))
    return objects, partners


def classify_candidates(
    rows: Iterable[Mapping[str, Any]],
    *,
    scope_geo_ids: Iterable[str],
    berry_id: str | None,
    entities: Mapping[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    material = [dict(row) for row in rows if _berry_ok(row, berry_id)]
    in_scope = [row for row in material if _in_scope_geo(row, scope_geo_ids)]
    objects, partners = _in_scope_keys(in_scope)
    classified = [
        classify_row(
            row,
            scope_geo_ids=scope_geo_ids,
            berry_id=berry_id,
            in_objects=objects,
            in_partners=partners,
            entities=entities,
        )
        for row in material
    ]
    return classified, objects, partners


def _footprints(
    classified: list[Mapping[str, Any]],
    *,
    in_objects: set[str],
    in_partners: set[str],
    entities: Mapping[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    entities = entities or {}
    groups: dict[str, list[Mapping[str, Any]]] = {}
    for row in classified:
        if row.get("_geo_class") == OUT_OF_SCOPE:
            continue
        keys = genetics_object_ids(row) & in_objects
        partners = platform_partner_ids(row)
        if keys:
            for key in sorted(keys):
                groups.setdefault(key, []).append(row)
        elif len(partners & in_partners) >= 2:
            groups.setdefault("platform:" + "+".join(sorted(partners & in_partners)[:4]), []).append(row)
    out: list[dict[str, Any]] = []
    for key, rows in groups.items():
        geos: list[str] = []
        companies: list[str] = []
        varieties: list[str] = []
        rights: list[str] = []
        commercial: list[str] = []
        stamps = [_event_day(row) for row in rows if _event_day(row)]
        for row in rows:
            for geo in _geo_labels(row, entities):
                if geo not in geos:
                    geos.append(geo)
            for company_id in _company_ids(row):
                name = (entities.get(company_id) or {}).get("name") or company_id
                if name not in companies:
                    companies.append(str(name))
            for variety_id in genetics_object_ids(row):
                if variety_id.startswith("variety-"):
                    label = _object_label(variety_id, entities)
                    if label not in varieties:
                        varieties.append(label)
                if variety_id.startswith("ip:") and variety_id[3:] not in rights:
                    rights.append(variety_id[3:])
            if _kind(row) in {"VARIETY_COMMERCIALIZATION", "RETAIL_PROGRAM", "LICENSING"}:
                commercial.append(_title(row))
        if len(geos) < 2:
            continue
        out.append({
            "object_id": key,
            "object_kind": (
                "variety" if key.startswith("variety-")
                else "breeding_program" if key.startswith("breeding_program-")
                else "ip" if key.startswith("ip:")
                else "platform"
            ),
            "label": _object_label(key.removeprefix("platform:").split("+")[0], entities) if key.startswith("platform:") else _object_label(key, entities),
            "first_observed": min(stamps).isoformat() if stamps else "",
            "latest_observed": max(stamps).isoformat() if stamps else "",
            "geographies_observed": geos,
            "companies": companies,
            "varieties": varieties,
            "pbr_ip": rights,
            "commercialization_events": commercial[:6],
            "source_ids": [_row_id(row) for row in rows if _row_id(row)][:8],
        })
    out.sort(key=lambda row: row.get("latest_observed") or "", reverse=True)
    return out[:6]


def _propagation(footprints: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in footprints:
        geos = list(row.get("geographies_observed") or [])
        if len(geos) < 2:
            continue
        out.append({
            "text": (
                "Berry OS observes the same genetics/commercialization platform appearing across "
                + ", ".join(geos[:-1]) + (", and " if len(geos) > 1 else "") + geos[-1] + "."
            ),
            "kind": "GEOGRAPHIC PROPAGATION",
            "source_ids": list(row.get("source_ids") or []),
            "object_id": row.get("object_id"),
        })
    return out


def _timeline(classified: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    dated = []
    for row in classified:
        if row.get("_geo_class") == OUT_OF_SCOPE:
            continue
        stamp = _event_day(row)
        if not stamp:
            continue
        dated.append({
            "date": stamp.isoformat(),
            "geography": ", ".join(row.get("_geo_labels") or []) or "geography unstated",
            "genetics_development": _title(row),
            "relationship": row.get("_geo_reason") or "",
            "geo_class": row.get("_geo_class"),
            "id": _row_id(row),
            "kind": _kind(row) or "OTHER",
        })
    dated.sort(key=lambda row: row["date"])
    return dated[:16]


def _expansion_vs_new(classified: list[Mapping[str, Any]], scope_geo_ids: Iterable[str]) -> list[dict[str, Any]]:
    """In-scope later items that continue an earlier extra-regional program."""
    extra = [row for row in classified if row.get("_geo_class") in {CROSS_GEO, GLOBAL_PLATFORM}]
    extra_objects = set()
    extra_partners: set[str] = set()
    extra_days: list[date] = []
    for row in extra:
        extra_objects.update(genetics_object_ids(row))
        extra_partners.update(platform_partner_ids(row))
        stamp = _event_day(row)
        if stamp:
            extra_days.append(stamp)
    if not extra_objects and len(extra_partners) < 2:
        return []
    earliest_extra = min(extra_days) if extra_days else None
    out = []
    for row in classified:
        if row.get("_geo_class") != IN_SCOPE or not is_genetics_kind(row):
            continue
        stamp = _event_day(row)
        shared = genetics_object_ids(row) & extra_objects
        shared_partners = platform_partner_ids(row) & extra_partners
        if not shared and len(shared_partners) < 2:
            continue
        if earliest_extra and stamp and stamp < earliest_extra:
            continue
        out.append({
            "change_type": "GENETICS_GEOGRAPHIC_EXPANSION",
            "what_changed": (
                f"Geographic expansion of an existing genetics program — {_title(row)}. "
                "This is the same program appearing in the requested geography, not a new isolated genetics event."
            ),
            "before": "The same Variety, platform, or licensing program was already observed outside this geography.",
            "now": _title(row),
            "evidence_basis": "Shared explicit genetics object or multi-company platform across geographies.",
            "coverage_notes": "Do not read this as a claim that the program will expand further.",
            "supporting_ids": [_row_id(row), *(_row_id(item) for item in extra if _row_id(item))][:8],
            "first_observed": (earliest_extra.isoformat() if earliest_extra else ""),
            "last_updated": stamp.isoformat() if stamp else "",
        })
    return out[:3]


def build_genetics_geography(
    scope: Any,
    packet: Mapping[str, Any],
    rows: Iterable[Mapping[str, Any]],
    *,
    entities: Mapping[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    scope_geo = tuple(getattr(scope, "geography_ids", None) or (packet.get("scope") or {}).get("geography_ids") or ())
    berry_id = getattr(scope, "berry_id", None) or (packet.get("scope") or {}).get("berry_id")
    entity_index = dict(entities or {})
    for row in packet.get("companies") or []:
        if row.get("id"):
            entity_index.setdefault(str(row["id"]), row)
    for row in packet.get("varieties") or []:
        if row.get("id"):
            entity_index.setdefault(str(row["id"]), row)
    for row in packet.get("geographies") or []:
        if row.get("id"):
            entity_index.setdefault(str(row["id"]), row)
    classified, in_objects, in_partners = classify_candidates(
        rows,
        scope_geo_ids=scope_geo,
        berry_id=berry_id,
        entities=entity_index,
    )
    in_scope = [row for row in classified if row.get("_geo_class") == IN_SCOPE]
    related = [row for row in classified if row.get("_geo_class") == CROSS_GEO]
    global_rows = [row for row in classified if row.get("_geo_class") == GLOBAL_PLATFORM]
    excluded = [row for row in classified if row.get("_geo_class") == OUT_OF_SCOPE]
    footprints = _footprints(
        classified,
        in_objects=in_objects,
        in_partners=in_partners,
        entities=entity_index,
    )
    return {
        "in_scope": [_present_row(row) for row in in_scope],
        "cross_geography_related": [_present_row(row) for row in related],
        "global_platform_context": [_present_row(row) for row in global_rows],
        "excluded": [
            {"id": _row_id(row), "title": _title(row), "reason": row.get("_geo_reason"), "geo_class": OUT_OF_SCOPE}
            for row in excluded
            if _row_id(row)
        ][:12],
        "footprints": footprints,
        "propagation": _propagation(footprints),
        "timeline": _timeline(classified),
        "program_expansions": _expansion_vs_new(classified, scope_geo),
        "classified_rows": classified,
    }


def _present_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": _row_id(row),
        "title": _title(row),
        "date": (_event_day(row).isoformat() if _event_day(row) else ""),
        "geography": ", ".join(row.get("_geo_labels") or []),
        "relationship": row.get("_geo_reason") or "",
        "geo_class": row.get("_geo_class"),
        "kind": _kind(row) or "OTHER",
        "source_ids": [_row_id(row)] if _row_id(row) else [],
    }


def genetics_geography_for(
    scope: Any,
    packet: Mapping[str, Any],
    *,
    entities: Mapping[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Official read seam for Ask Berry OS and War Room. Creates no store and no UI."""
    from app.services.change_scenario import _copy_rows

    model = build_genetics_geography(scope, packet, _copy_rows(packet), entities=entities)
    return {
        "in_scope": model["in_scope"],
        "cross_geography_related": model["cross_geography_related"],
        "global_platform_context": model["global_platform_context"],
        "excluded": model["excluded"],
        "footprints": model["footprints"],
        "propagation": model["propagation"],
        "timeline": model["timeline"],
        "program_expansions": model["program_expansions"],
        "what_this_may_mean": _what_this_may_mean(model),
        "watch_next": _watch_next(model),
    }


def _what_this_may_mean(model: Mapping[str, Any]) -> list[dict[str, Any]]:
    out = []
    if model.get("program_expansions"):
        ids = [sid for row in model["program_expansions"] for sid in row.get("supporting_ids") or []]
        out.append({
            "text": "An in-scope item may be geographic expansion of an existing genetics program rather than a brand-new genetics event.",
            "source_ids": ids[:8],
        })
    if model.get("propagation"):
        ids = [sid for row in model["propagation"] for sid in row.get("source_ids") or []]
        out.append({
            "text": (
                "The same genetics or commercialization platform is visible in more than one geography. "
                "That can mark a development → licensing → multi-geography commercialization path. "
                "It is not, by itself, evidence of a global strategy."
            ),
            "source_ids": ids[:8],
        })
    return out


def _watch_next(model: Mapping[str, Any]) -> list[dict[str, Any]]:
    ids = [
        sid
        for row in list(model.get("cross_geography_related") or []) + list(model.get("in_scope") or [])
        for sid in row.get("source_ids") or []
    ]
    if not ids:
        return []
    return [{
        "text": "Additional geographic commercialization is a development to watch.",
        "why_plausible": "The same genetics object or multi-company platform already appears in more than one geography.",
        "would_confirm": "A later dated commercialization or licensing record appears in another geography for the same Variety or platform.",
        "would_refute": "Later items stay in the original geography with no further licensing or commercialization record.",
        "watch": "Competitive Moves classified as licensing, commercialization, or variety launch for the same genetics object.",
        "source_ids": ids[:8],
    }]


def wants_genetics_geography(scope: Any) -> bool:
    topics = tuple(getattr(scope, "topics", None) or ())
    geos = tuple(getattr(scope, "geography_ids", None) or ())
    intelligence = str(getattr(scope, "intelligence_type", "") or "")
    return bool(geos) and ("genetics" in topics or "rights_ip" in topics or intelligence == "ip_genetics")
