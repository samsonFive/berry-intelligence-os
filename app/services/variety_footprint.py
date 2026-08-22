"""Variety Commercial Footprint -- derived, read-only queries.

Variety Intelligence Backbone V1 mission (2026-08-21). Everything here is a
pure function over caller-supplied record lists (entities, relationships,
published Evidence, and -- explicitly, separately -- untrusted inbox
drafts). Nothing here writes anything or persists a derived conclusion;
per the mission's own instruction, "do not persist derived conclusions
unnecessarily" -- a caller (a future CLI, route, or test) re-derives this
on every call from the current record set.

Trust discipline: `published_evidence` and `inbox_drafts` are always kept
as two distinct parameters and the returned shapes never merge them into
one undifferentiated "evidence" list -- every returned observation/evidence
item carries its own `trust` marker ("published" or "draft/pending
review"). A market/commercial observation existing (even many of them)
never becomes a Fact by appearing here; this module answers "what does the
record set say", not "what should be believed".
"""

from __future__ import annotations

from typing import Any


def _by_id(entities: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {e["id"]: e for e in entities if e.get("id")}


def _entity_ids_of(record: dict[str, Any]) -> set[str]:
    ids = set(record.get("entity_ids") or [])
    obs = record.get("commercial_observation") or {}
    for key in ("retailer_entity_id", "variety_entity_id", "marketer_entity_id"):
        value = obs.get(key)
        if isinstance(value, str) and value:
            ids.add(value)
    return ids


def _relationships_touching(relationships: list[dict[str, Any]], entity_id: str) -> list[dict[str, Any]]:
    return [r for r in relationships if r.get("subject_id") == entity_id or r.get("object_id") == entity_id]


def _observation_records(records: list[dict[str, Any]], variety_id: str) -> list[dict[str, Any]]:
    return [
        r
        for r in records
        if (r.get("commercial_observation") or {}).get("variety_entity_id") == variety_id
        or (variety_id in (r.get("entity_ids") or []) and r.get("intake_type") == "commercial_observation")
    ]


def variety_footprint(
    variety_id: str,
    *,
    entities: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
    published_evidence: list[dict[str, Any]],
    inbox_drafts: list[dict[str, Any]] | None = None,
    story_threads: list[dict[str, Any]] | None = None,
    signals: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """For one Variety: breeder/owner/rights-holder/marketer relationships
    (kept as SEPARATE role buckets, never collapsed to one "company"),
    berries, countries observed (derived from geography_ids on evidence/
    observations that also name this variety -- the same derivation
    principle app/services/berries/geography.py's entity_regions() already
    uses for the general case), retailers/channels observed, first/latest
    observation dates, and the supporting record set itself. Never raises
    for an unknown variety_id -- returns an empty-shaped footprint, since
    "no data yet" is a legitimate, common answer, not an error."""
    inbox_drafts = inbox_drafts or []
    story_threads = story_threads or []
    signals = signals or []
    entity_index = _by_id(entities)
    variety = entity_index.get(variety_id)

    rels = _relationships_touching(relationships, variety_id)
    roles: dict[str, list[str]] = {}
    for rel in rels:
        if rel.get("object_id") != variety_id:
            continue
        roles.setdefault(rel.get("predicate") or "unknown", []).append(rel.get("subject_id"))

    pvr_evidence = [
        r
        for r in published_evidence
        if variety_id in (r.get("entity_ids") or []) and r.get("source_type") in {"plant_breeders_rights_record", "patent_record"}
    ]
    pvr_drafts = [
        r
        for r in inbox_drafts
        if variety_id in (r.get("entity_ids") or []) and r.get("source_type") in {"plant_breeders_rights_record", "patent_record"}
    ]

    published_obs = _observation_records(published_evidence, variety_id)
    draft_obs = _observation_records(inbox_drafts, variety_id)
    all_obs = [{"trust": "published", **r} for r in published_obs] + [{"trust": "draft (pending review)", **r} for r in draft_obs]

    countries: set[str] = set()
    retailers: set[str] = set()
    observed_dates: list[str] = []
    for obs in all_obs:
        countries.update(obs.get("geography_ids") or [])
        detail = obs.get("commercial_observation") or {}
        retailer_id = detail.get("retailer_entity_id")
        if retailer_id:
            retailers.add(retailer_id)
        observed_at = detail.get("observed_at") or obs.get("captured_date")
        if observed_at:
            observed_dates.append(observed_at)

    related_threads = [t for t in story_threads if variety_id in ((t.get("member_entity_ids") or []) + [])]
    related_signals = [s for s in signals if variety_id in (s.get("entity_ids") or [])]

    berries = list((variety or {}).get("berry_ids") or [])

    return {
        "variety_id": variety_id,
        "known": variety is not None,
        "name": (variety or {}).get("name"),
        "aliases": (variety or {}).get("aliases") or [],
        "berries": berries,
        "roles": {
            # Never collapsed to one "owner" -- develops/owns/licenses/
            # markets are kept as separate buckets, each naming the
            # subject-company id(s) real relationship data supports for
            # that specific role. A company may legitimately appear in
            # more than one bucket (Driscoll's both develops and owns
            # variety-drisblueseventeen -- two separately evidenced facts).
            "breeder": roles.get("develops", []),
            "owner_rights_holder": roles.get("owns", []),
            "licensee": roles.get("licenses", []),
            "marketer": roles.get("markets", []),
            "grower": roles.get("grows", []),
            "distributor": roles.get("distributes", []),
        },
        "rights_filings": {
            "published": [
                {"id": r["id"], "title": r.get("title"), "source_type": r.get("source_type"), "published_date": r.get("published_date")}
                for r in pvr_evidence
            ],
            "draft_pending_review": [
                {"id": r["id"], "title": r.get("title"), "source_type": r.get("source_type")} for r in pvr_drafts
            ],
        },
        "countries_observed": sorted(countries),
        "retailers_observed": sorted(retailers),
        "first_observed": min(observed_dates) if observed_dates else None,
        "latest_observed": max(observed_dates) if observed_dates else None,
        "commercial_observations": [
            {
                "id": obs["id"],
                "trust": obs["trust"],
                "retailer_entity_id": (obs.get("commercial_observation") or {}).get("retailer_entity_id"),
                "market_country": (obs.get("commercial_observation") or {}).get("market_country"),
                "observed_at": (obs.get("commercial_observation") or {}).get("observed_at"),
                "source_url": obs.get("source_url"),
            }
            for obs in all_obs
        ],
        "story_threads": [{"id": t.get("id"), "title": t.get("title")} for t in related_threads],
        "signals": [{"id": s.get("id"), "title": s.get("title")} for s in related_signals],
    }


def varieties_observed_in_market(
    *,
    country_geo_id: str,
    berry_id: str | None = None,
    entities: list[dict[str, Any]],
    published_evidence: list[dict[str, Any]],
    inbox_drafts: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """'Which varieties have been observed in commercial channels in
    market X?' -- real answer, drafts included but labeled, per the
    mission's Section 11 competitive-query proof requirement."""
    inbox_drafts = inbox_drafts or []
    entity_index = _by_id(entities)
    hits: dict[str, dict[str, Any]] = {}
    for trust_label, records in (("published", published_evidence), ("draft (pending review)", inbox_drafts)):
        for record in records:
            if record.get("intake_type") != "commercial_observation":
                continue
            if country_geo_id not in (record.get("geography_ids") or []):
                continue
            detail = record.get("commercial_observation") or {}
            variety_id = detail.get("variety_entity_id")
            if not variety_id:
                continue
            variety = entity_index.get(variety_id)
            if berry_id and variety and berry_id not in (variety.get("berry_ids") or []):
                continue
            entry = hits.setdefault(
                variety_id,
                {"variety_id": variety_id, "name": (variety or {}).get("name"), "observations": []},
            )
            entry["observations"].append({"evidence_id": record.get("id"), "trust": trust_label})
    return sorted(hits.values(), key=lambda row: row["name"] or "")


def varieties_with_ip_activity_and_commercial_observation(
    *,
    entities: list[dict[str, Any]],
    published_evidence: list[dict[str, Any]],
    inbox_drafts: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """'Which varieties have BOTH IP activity (patent/PVR Evidence) AND at
    least one commercial observation?' -- the two evidence classes this
    mission connects for the first time. Both sides required; a variety
    with only one or the other is correctly excluded, not partially
    counted."""
    inbox_drafts = inbox_drafts or []
    entity_index = _by_id(entities)
    all_records = [{"trust": "published", **r} for r in published_evidence] + [
        {"trust": "draft (pending review)", **r} for r in inbox_drafts
    ]
    ip_varieties: set[str] = set()
    observed_varieties: set[str] = set()
    for record in all_records:
        eids = _entity_ids_of(record)
        if record.get("source_type") in {"plant_breeders_rights_record", "patent_record"}:
            for eid in eids:
                if (entity_index.get(eid) or {}).get("entity_type") == "variety":
                    ip_varieties.add(eid)
        if record.get("intake_type") == "commercial_observation":
            detail = record.get("commercial_observation") or {}
            variety_id = detail.get("variety_entity_id")
            if variety_id:
                observed_varieties.add(variety_id)
    both = ip_varieties & observed_varieties
    return [
        {"variety_id": vid, "name": (entity_index.get(vid) or {}).get("name")}
        for vid in sorted(both)
    ]


def competing_varieties_in_berry_market(
    *,
    berry_id: str,
    country_geo_id: str | None,
    entities: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
    published_evidence: list[dict[str, Any]],
    inbox_drafts: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """'Which companies have competing varieties in this berry (optionally
    scoped to one observed market)?' -- groups varieties (matched by
    berry_id, and by commercial observation in country_geo_id when given)
    by their real breeder/owner company, via existing develops/owns
    relationships. Never invents a competitive-intensity score; returns
    the grouped real facts only."""
    inbox_drafts = inbox_drafts or []
    entity_index = _by_id(entities)
    if country_geo_id:
        observed = varieties_observed_in_market(
            country_geo_id=country_geo_id,
            berry_id=berry_id,
            entities=entities,
            published_evidence=published_evidence,
            inbox_drafts=inbox_drafts,
        )
        variety_ids = {row["variety_id"] for row in observed}
    else:
        variety_ids = {
            e["id"] for e in entities if e.get("entity_type") == "variety" and berry_id in (e.get("berry_ids") or [])
        }

    by_company: dict[str, dict[str, Any]] = {}
    for variety_id in variety_ids:
        for rel in relationships:
            # Broader than variety_footprint()'s role buckets on purpose:
            # "which companies have competing varieties" is answered by any
            # real commercial/legal association (breeder, rights holder, or
            # marketer -- not only develops/owns), since a marketer-only
            # link is still a real competitive signal for this specific
            # question. variety_footprint() itself still keeps every role
            # in its own separate, unmerged bucket.
            if rel.get("object_id") != variety_id or rel.get("predicate") not in {"develops", "owns", "markets"}:
                continue
            company_id = rel.get("subject_id")
            company = entity_index.get(company_id)
            entry = by_company.setdefault(
                company_id,
                {"company_id": company_id, "company_name": (company or {}).get("name"), "varieties": []},
            )
            variety_name = (entity_index.get(variety_id) or {}).get("name")
            if variety_name not in entry["varieties"]:
                entry["varieties"].append(variety_name)
    return sorted(
        [row for row in by_company.values() if len(row["varieties"]) >= 1],
        key=lambda row: row["company_name"] or "",
    )
