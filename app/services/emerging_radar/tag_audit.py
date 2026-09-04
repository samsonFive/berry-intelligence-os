"""Bounded Radar tag-quality audit. Review candidates, not a second ontology.

Reuses EntityResolver — the same function that writes geography/berry tags.
Does not invent company-catalog or geography-catalog inheritance.
Does not mutate Change/Scenario matchers.
"""

from __future__ import annotations

from typing import Any, Iterable

from app.services.emerging_radar.cache import edition_from_cache, load_cache, write_cache
from app.services.emerging_radar.cluster import (
    TAG_ORIGIN_CURATED,
    TAG_ORIGIN_EXPLICIT,
    TAG_ORIGIN_INFERRED_PLACE,
    TAG_ORIGIN_NATIONALITY,
    TAG_ORIGIN_STALE,
    TITLE_STRONG_EVENTS,
    EntityResolver,
    _what_happened,
    classify_event_type,
)
from app.services.emerging_radar.models import Development, RadarEdition

DIRECT_ORIGINS = frozenset({TAG_ORIGIN_EXPLICIT, TAG_ORIGIN_INFERRED_PLACE, TAG_ORIGIN_CURATED})

RULE_NATIONALITY_VS_PLACE = "nationality_vs_place"
RULE_TITLE_COUNTRY_CONFLICT = "title_country_conflict"
RULE_MISSING_INFERRED_PLACE = "missing_inferred_place"
RULE_STALE_UNPROVENANCED = "stale_unprovenanced"
RULE_EVENT_TYPE_TITLE_STRONG = "event_type_title_strong"
RULE_BERRY_NOT_IN_TEXT = "berry_not_in_text"


def _source_text(development: Development) -> tuple[str, str]:
    title = development.title or ""
    snippets = [source.snippet or "" for source in development.sources if source.snippet]
    return title, " ".join(snippets)


def resolve_development(development: Development, *, resolver: EntityResolver | None = None) -> dict[str, Any]:
    resolver = resolver or EntityResolver()
    title, snippet = _source_text(development)
    return resolver.resolve(f"{title} {snippet}", title=title, snippet=snippet)


def _provenance_for(resolved: dict[str, Any], field: str, value: str) -> dict[str, str] | None:
    for row in resolved.get("tag_provenance") or ():
        if row.get("field") == field and row.get("value") == value:
            return row
    return None


def _is_deterministic_geo_repair(stored: tuple[str, ...], resolved: dict[str, Any]) -> bool:
    derived = tuple(resolved.get("geography_ids") or ())
    if stored == derived:
        return False
    title_explicit = {
        row["value"]
        for row in resolved.get("tag_provenance") or ()
        if row.get("field") == "geography"
        and row.get("origin") in DIRECT_ORIGINS
        and row.get("text_field") == "title"
    }
    dropped = set(stored) - set(derived)
    added = set(derived) - set(stored)
    for geo_id in dropped:
        if geo_id in title_explicit:
            return False
        row = _provenance_for(resolved, "geography", geo_id)
        if row and row.get("origin") not in {TAG_ORIGIN_NATIONALITY, None} and row.get("text_field") == "title":
            return False
    for geo_id in added:
        row = _provenance_for(resolved, "geography", geo_id)
        if not row or row.get("origin") not in DIRECT_ORIGINS:
            return False
    return True


def audit_development(development: Development, *, resolver: EntityResolver | None = None) -> dict[str, Any] | None:
    """Return one review candidate, or None when tags agree with evidence text."""
    resolved = resolve_development(development, resolver=resolver)
    title, snippet = _source_text(development)
    combined = f"{title} {snippet}".casefold()
    flags: list[dict[str, Any]] = []
    stored_geos = tuple(development.geography_ids)
    derived_geos = tuple(resolved.get("geography_ids") or ())
    stored_berries = tuple(development.berry_ids)
    derived_berries = tuple(resolved.get("berry_ids") or ())

    if stored_geos != derived_geos:
        nationality = [
            row
            for row in resolved.get("tag_provenance") or ()
            if row.get("field") == "geography" and row.get("origin") == TAG_ORIGIN_NATIONALITY
        ]
        inferred = [
            row
            for row in resolved.get("tag_provenance") or ()
            if row.get("field") == "geography" and row.get("origin") == TAG_ORIGIN_INFERRED_PLACE
        ]
        if nationality and inferred:
            rule = RULE_NATIONALITY_VS_PLACE
            why = (
                "Source names a place (or country) as the event location, but the "
                "stored direct geography came from a company nationality mention."
            )
        elif any(row.get("text_field") == "title" for row in inferred) and set(stored_geos) - set(derived_geos):
            rule = RULE_MISSING_INFERRED_PLACE
            why = "Title names a known production place that was not stored as that country."
        else:
            rule = RULE_TITLE_COUNTRY_CONFLICT
            why = "Stored geography does not match country/place nouns in the title and snippet."
        flags.append(
            {
                "field": "geography",
                "stored": list(stored_geos),
                "evidence_derived": list(derived_geos),
                "rule": rule,
                "why": why,
                "repair_eligible": _is_deterministic_geo_repair(stored_geos, resolved),
            }
        )

    if not development.tag_provenance and stored_geos:
        flags.append(
            {
                "field": "geography",
                "stored": list(stored_geos),
                "evidence_derived": list(derived_geos),
                "rule": RULE_STALE_UNPROVENANCED,
                "why": "Persisted geography has no tag provenance — likely a pre-audit cache row.",
                "repair_eligible": _is_deterministic_geo_repair(stored_geos, resolved),
            }
        )

    title_type = classify_event_type(title, title=title)
    if title_type in TITLE_STRONG_EVENTS and development.event_type != title_type:
        flags.append(
            {
                "field": "event_type",
                "stored": development.event_type,
                "evidence_derived": title_type,
                "rule": RULE_EVENT_TYPE_TITLE_STRONG,
                "why": "Headline classifies as a strong event type; the stored type came from snippet wording.",
                "repair_eligible": True,
            }
        )

    extra_berries = [berry_id for berry_id in stored_berries if berry_id not in derived_berries]
    if extra_berries:
        flags.append(
            {
                "field": "berry",
                "stored": list(stored_berries),
                "evidence_derived": list(derived_berries),
                "rule": RULE_BERRY_NOT_IN_TEXT,
                "why": (
                    "Stored berry is not named in the title or snippet. Company or "
                    "geography catalogs must not widen berry scope."
                ),
                "repair_eligible": False,
            }
        )

    if not flags:
        return None

    nationality_spans = [
        row.get("span")
        for row in resolved.get("tag_provenance") or ()
        if row.get("origin") == TAG_ORIGIN_NATIONALITY
    ]
    return {
        "id": development.id,
        "title": development.title,
        "href": f"/radar/{development.id}",
        "suspect_fields": [flag["field"] for flag in flags],
        "flags": flags,
        "provenance": list(resolved.get("tag_provenance") or ()),
        "repair_eligible": any(flag.get("repair_eligible") for flag in flags),
        "source_excerpt": (snippet or title)[:280],
        "nationality_spans": nationality_spans,
        "combined_preview": combined[:160],
    }


def audit_developments(
    developments: Iterable[Development],
    *,
    entities: Iterable[dict[str, Any]] = (),
) -> list[dict[str, Any]]:
    resolver = EntityResolver(entities)
    return [row for row in (audit_development(item, resolver=resolver) for item in developments) if row]


def apply_deterministic_repair(development: Development, *, resolver: EntityResolver | None = None) -> bool:
    """Apply only fully supported geography / title-strong event repairs."""
    resolved = resolve_development(development, resolver=resolver)
    changed = False
    if _is_deterministic_geo_repair(tuple(development.geography_ids), resolved):
        development.geography_ids = tuple(resolved.get("geography_ids") or ())
        development.geography_labels = tuple(resolved.get("geography_labels") or ())
        changed = True
    title, _snippet = _source_text(development)
    title_type = classify_event_type(title, title=title)
    if title_type in TITLE_STRONG_EVENTS and development.event_type != title_type:
        development.event_type = title_type
        development.what_happened = _what_happened(
            development.title,
            title_type,
            development.company_names or development.variety_names,
        )
        changed = True
    if resolved.get("tag_provenance"):
        development.tag_provenance = tuple(resolved["tag_provenance"])
    elif development.geography_ids and not development.tag_provenance:
        development.tag_provenance = tuple(
            {
                "field": "geography",
                "value": geo_id,
                "origin": TAG_ORIGIN_STALE,
                "span": "",
                "text_field": "cache",
            }
            for geo_id in development.geography_ids
        )
    return changed


def rehydrate_developments(
    developments: list[Development],
    *,
    entities: Iterable[dict[str, Any]] = (),
) -> list[Development]:
    """In-memory repair of cached Developments. Does not write the cache."""
    resolver = EntityResolver(entities)
    for development in developments:
        apply_deterministic_repair(development, resolver=resolver)
    return developments


def audit_radar_cache(
    *,
    inbox_dir=None,
    entities: Iterable[dict[str, Any]] = (),
    apply_repairs: bool = False,
) -> dict[str, Any]:
    """Read-only audit of the Radar inbox cache unless apply_repairs is set.

    GET surfaces must pass apply_repairs=False.
    """
    edition = edition_from_cache(inbox_dir=inbox_dir)
    if edition is None:
        return {
            "cache_status": "empty",
            "development_count": 0,
            "candidate_count": 0,
            "candidates": [],
            "repaired_ids": [],
        }
    developments = list(edition.developments)
    resolver = EntityResolver(entities)
    # Audit against persisted tags before in-memory repair so operators see
    # the defect. edition_from_cache may already have rehydrated — compare
    # to the raw cache when present.
    raw = load_cache(inbox_dir)
    raw_rows = ((raw.get("edition") or {}).get("developments") or []) if isinstance(raw, dict) else []
    if raw_rows:
        from app.services.emerging_radar.models import development_from_dict

        audit_rows = [development_from_dict(item) for item in raw_rows if isinstance(item, dict)]
    else:
        audit_rows = developments
    candidates = audit_developments(audit_rows, entities=entities)
    repaired_ids: list[str] = []
    if apply_repairs:
        for development in developments:
            if apply_deterministic_repair(development, resolver=resolver):
                repaired_ids.append(development.id)
        edition.developments = developments
        write_cache(edition, inbox_dir=inbox_dir)
    return {
        "cache_status": edition.cache_status,
        "development_count": len(audit_rows),
        "candidate_count": len(candidates),
        "candidates": candidates,
        "repaired_ids": repaired_ids,
    }


def persist_repaired_edition(edition: RadarEdition, *, inbox_dir=None, entities: Iterable[dict[str, Any]] = ()) -> list[str]:
    repaired = []
    resolver = EntityResolver(entities)
    for development in edition.developments:
        if apply_deterministic_repair(development, resolver=resolver):
            repaired.append(development.id)
    if repaired and inbox_dir is not None:
        write_cache(edition, inbox_dir=inbox_dir)
    return repaired
