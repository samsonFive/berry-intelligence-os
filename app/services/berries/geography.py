"""Berries geography-region bucketing (V2 Phase 2B.2, moved from
app/main.py -- V2 Phase 1.5B/2A's own "documented hybrid" classification:
the bucket-then-aggregate mechanism is Core-shaped, but the region-name
lookup table itself is Berries-authored, so the whole unit lives here
rather than split across layers).

Also holds berry_label() -- small, pure, Berries-id-shaped string
formatting with no reason to live anywhere else.

Moved verbatim; behavior is unchanged. Pure functions -- no repository or
DATA_DIR access, so no composition/circular-import concerns.
"""

from __future__ import annotations

from typing import Any

REGIONS = ["Americas", "Europe", "Oceania", "Middle East & Africa"]

# Default region assignment by geography name. Deliberately not exhaustive --
# anything not listed here (e.g. China, present in real imported data) has no
# default region rather than being guessed into the wrong bucket. Always
# overridable per-geography via attributes.region (see geography_region()).
REGION_LOOKUP = {
    "united states": "Americas", "canada": "Americas", "mexico": "Americas",
    "peru": "Americas", "chile": "Americas", "colombia": "Americas",
    "brazil": "Americas", "argentina": "Americas", "uruguay": "Americas",
    "north america": "Americas", "south america": "Americas",
    "europe": "Europe", "spain": "Europe", "portugal": "Europe",
    "germany": "Europe", "netherlands": "Europe", "france": "Europe",
    "poland": "Europe", "italy": "Europe", "united kingdom": "Europe", "uk": "Europe",
    "australia": "Oceania", "new zealand": "Oceania", "oceania": "Oceania",
    "morocco": "Middle East & Africa", "south africa": "Middle East & Africa",
    "zambia": "Middle East & Africa", "zimbabwe": "Middle East & Africa",
    "egypt": "Middle East & Africa", "kenya": "Middle East & Africa",
    "nigeria": "Middle East & Africa", "israel": "Middle East & Africa",
    "saudi arabia": "Middle East & Africa", "uae": "Middle East & Africa",
    "united arab emirates": "Middle East & Africa",
}


def berry_label(berry_id: str) -> str:
    return berry_id.removeprefix("berry-").replace("_", " ").replace("-", " ").title()


def geography_region(geography_entity: dict[str, Any]) -> str | None:
    """A geography's region: an explicit attributes.filter_region override
    always wins (so a wrong or missing default is one edit away to fix),
    otherwise the fixed lookup table by name.

    Deliberately namespaced as "filter_region", not "region": real imported
    geography entities already carry their own attributes.region using a
    different taxonomy (e.g. "Asia-Pacific", "Latin America") for their own
    purposes. Reusing that key silently adopted their values as if they were
    corrections to this app's four-bucket scheme, which they were never
    intended to be -- found by checking Australia's derived region live and
    getting "Asia-Pacific" back instead of "Oceania"."""
    override = (geography_entity.get("attributes") or {}).get("filter_region")
    if override:
        return override
    return REGION_LOOKUP.get(geography_entity.get("name", "").strip().lower())


def evidence_regions(record: dict[str, Any], entities: dict[str, dict[str, Any]]) -> set[str]:
    """A geography can be associated with evidence two ways: the dedicated
    geography_ids array, or just as one of the general entity_ids -- real
    imported data (predating the geography_ids field) only ever does the
    latter, so both are checked rather than trusting one convention."""
    geo_ids = set(record.get("geography_ids") or [])
    for eid in record.get("entity_ids") or []:
        entity = entities.get(eid)
        if entity and entity.get("entity_type") == "geography":
            geo_ids.add(eid)
    regions = set()
    for gid in geo_ids:
        geo = entities.get(gid)
        if geo:
            region = geography_region(geo)
            if region:
                regions.add(region)
    return regions


def entity_regions(
    entity: dict[str, Any],
    entities: dict[str, dict[str, Any]],
    evidence: list[dict[str, Any]],
) -> set[str]:
    """Which regions an entity touches. A geography entity has its own
    region. Any other entity's regions are derived, not stored: the union of
    regions from every geography linked (via geography_ids) to evidence that
    also links this entity -- so a variety grown/tested/reported on across
    three continents shows all three automatically, with no extra field to
    keep in sync."""
    if entity.get("entity_type") == "geography":
        region = geography_region(entity)
        return {region} if region else set()
    regions: set[str] = set()
    for record in evidence:
        if entity.get("id") in (record.get("entity_ids") or []):
            regions |= evidence_regions(record, entities)
    return regions
