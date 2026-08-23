"""Company Compare V1 -- presentation only, derived from existing trusted
objects. No score, no ranking: shows real Company<->Variety relationship
roles, rights/IP, commercial and geographic footprint, and Signal/
Assessment presence side by side, reusing the exact same helpers Variety
Compare V1 already proved (variety_footprint, present_variety_intelligence,
the ROLE_BUCKETS role-distinction discipline, and the shared source_type
humanization) rather than re-deriving any of that logic."""

from __future__ import annotations

from typing import Any

from app.services.intelligence_feed import present_feed_item
from app.services.variety_workspace import (
    ROLE_BUCKETS,
    ROLE_LABEL,
    SOURCE_TYPE_LABEL,
    _is_observation,
    _is_rights_record,
    _party,
    _rights_kind,
    present_variety_intelligence,
    variety_footprint,
)

COMPARE_MAX_COMPANIES = 4
RECENT_INTELLIGENCE_LIMIT = 5


def _humanize_source_type(source_type: str) -> str:
    if not source_type:
        return "Unspecified source"
    return SOURCE_TYPE_LABEL.get(source_type, source_type.replace("_", " ").title())


def _company_portfolio_roles(
    company_id: str, *, relationships: list[dict[str, Any]], entities: dict[str, dict[str, Any]]
) -> dict[str, list[dict[str, Any]]]:
    """Which varieties this Company holds each real role toward, never
    collapsed to a generic "has variety". Mirrors variety_footprint()'s own
    role-bucket discipline, read from the Company's own outgoing edges."""
    roles: dict[str, list[dict[str, Any]]] = {bucket: [] for bucket, _pred, _label in ROLE_BUCKETS}
    predicate_to_bucket = {pred: bucket for bucket, pred, _label in ROLE_BUCKETS}
    seen_per_bucket: dict[str, set[str]] = {bucket: set() for bucket, _pred, _label in ROLE_BUCKETS}
    for rel in relationships:
        if rel.get("subject_id") != company_id:
            continue
        bucket = predicate_to_bucket.get(rel.get("predicate"))
        if not bucket:
            continue
        variety = entities.get(str(rel.get("object_id") or ""))
        if not variety or variety.get("entity_type") != "variety":
            continue
        if variety["id"] in seen_per_bucket[bucket]:
            continue
        party = _party(variety)
        if party:
            seen_per_bucket[bucket].add(variety["id"])
            roles[bucket].append(party)
    return roles


def _portfolio_variety_ids(roles: dict[str, list[dict[str, Any]]]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for parties in roles.values():
        for party in parties:
            vid = party.get("id")
            if vid and vid not in seen:
                seen.add(vid)
                ordered.append(vid)
    return ordered


def present_company_compare(
    company_ids: list[str],
    *,
    entities: dict[str, dict[str, Any]],
    relationships: list[dict[str, Any]],
    published_evidence: list[dict[str, Any]],
    facts: list[dict[str, Any]],
    evidence_by_id: dict[str, dict[str, Any]],
    signals: list[dict[str, Any]],
    assessments: list[dict[str, Any]],
    berry_labels: dict[str, str],
) -> dict[str, Any]:
    """Company Compare V1 -- a side-by-side, trusted-intelligence-only
    comparison workspace for up to COMPARE_MAX_COMPANIES companies. Callers
    pass already-loaded base lists (the same ones every other entity route
    already fetches once); this function performs no new corpus scan of
    its own. No synthetic score, no winner: the analyst interprets the
    evidence."""
    entity_list = list(entities.values())
    seen: set[str] = set()
    deduped_ids: list[str] = []
    for cid in company_ids:
        if cid and cid not in seen:
            seen.add(cid)
            deduped_ids.append(cid)
    selected_ids = deduped_ids[:COMPARE_MAX_COMPANIES]
    overflow_ids = deduped_ids[COMPARE_MAX_COMPANIES:]

    cards: list[dict[str, Any]] = []
    invalid_ids: list[str] = []

    for cid in selected_ids:
        company = entities.get(cid)
        if not company or company.get("entity_type") != "company":
            invalid_ids.append(cid)
            continue

        roles = _company_portfolio_roles(cid, relationships=relationships, entities=entities)
        portfolio_variety_ids = _portfolio_variety_ids(roles)
        portfolio_varieties = [entities[vid] for vid in portfolio_variety_ids if vid in entities]

        # Berry portfolio: reuse the exact same field the Company profile
        # page already renders as chips (entity.berry_ids) -- not
        # re-derived here, so Compare never diverges from what the
        # single-company profile itself already shows for that company.
        berry_ids = [str(b) for b in (company.get("berry_ids") or []) if b]

        rights_published: list[dict[str, Any]] = []
        rights_seen: set[str] = set()
        countries: set[str] = set()
        retailers: set[str] = set()
        commercial_obs_count = 0
        product_group_counts: dict[str, int] = {}
        product_group_labels: dict[str, str] = {}
        intelligence_evidence_ids: set[str] = set()

        for variety in portfolio_varieties:
            vid = variety["id"]
            footprint = variety_footprint(
                vid,
                entities=entity_list,
                relationships=relationships,
                published_evidence=published_evidence,
                signals=signals,
            )
            for row in footprint.get("rights_filings", {}).get("published") or []:
                if row.get("id") and row["id"] not in rights_seen:
                    rights_seen.add(row["id"])
                    enriched = dict(row)
                    enriched["kind"] = _rights_kind(row)
                    enriched["variety_name"] = variety.get("name")
                    enriched["variety_href"] = f"/entities/variety/{vid}"
                    enriched["href"] = f"/evidence/{row['id']}"
                    rights_published.append(enriched)
            countries.update(footprint.get("countries_observed") or [])
            retailers.update(footprint.get("retailers_observed") or [])
            commercial_obs_count += len(footprint.get("commercial_observations") or [])

            variety_facts = [f for f in facts if vid in (f.get("entity_ids") or [])]
            vi = present_variety_intelligence(
                variety, entities=entities, facts=variety_facts, evidence_by_id=evidence_by_id
            )
            for group in vi["groups"]:
                product_group_counts[group["key"]] = product_group_counts.get(group["key"], 0) + len(group["rows"])
                product_group_labels[group["key"]] = group["label"]
                for row in group["rows"]:
                    if row.get("evidence_id"):
                        intelligence_evidence_ids.add(row["evidence_id"])

        company_linked_evidence = [r for r in published_evidence if cid in (r.get("entity_ids") or [])]

        # Rights/IP or commercial observations linked directly to the
        # company itself (rare, but real when present) join the same
        # already-deduplicated sets rather than a second parallel list.
        for record in company_linked_evidence:
            if _is_rights_record(record) and record.get("id") not in rights_seen:
                rights_seen.add(record["id"])
                rights_published.append(
                    {
                        "id": record["id"],
                        "title": record.get("title"),
                        "kind": _rights_kind(record),
                        "published_date": record.get("published_date"),
                        "variety_name": None,
                        "variety_href": "",
                        "href": f"/evidence/{record['id']}",
                    }
                )
            if _is_observation(record):
                commercial_obs_count += 1
                countries.update(record.get("geography_ids") or [])

        rights_published.sort(key=lambda r: str(r.get("published_date") or ""), reverse=True)

        geo_relationship_ids = {
            str(rel.get("object_id"))
            for rel in relationships
            if rel.get("subject_id") == cid and rel.get("predicate") == "operates_in"
        }
        geo_ids = countries | geo_relationship_ids
        geographies = [
            _party(entities.get(gid)) or {"id": gid, "name": gid, "href": ""} for gid in sorted(geo_ids)
        ]
        retailer_parties = [party for party in (_party(entities.get(rid)) for rid in sorted(retailers)) if party]

        company_facts = [f for f in facts if cid in (f.get("entity_ids") or [])]
        company_signals = [s for s in signals if cid in (s.get("entity_ids") or [])]
        company_assessments = [a for a in assessments if cid in (a.get("entity_ids") or [])]

        source_type_counts: dict[str, int] = {}
        for record in company_linked_evidence:
            label = _humanize_source_type(str(record.get("source_type") or ""))
            source_type_counts[label] = source_type_counts.get(label, 0) + 1

        recent_sorted = sorted(
            company_linked_evidence,
            key=lambda r: str(r.get("published_date") or r.get("captured_date") or ""),
            reverse=True,
        )[:RECENT_INTELLIGENCE_LIMIT]
        recent_cards = [present_feed_item(r, entities=entities, berry_labels=berry_labels) for r in recent_sorted]

        source_ids = {r.get("id") for r in company_linked_evidence if r.get("id")} | intelligence_evidence_ids | rights_seen
        dates = [
            d
            for d in (
                [r.get("published_date") for r in company_linked_evidence]
                + [r.get("published_date") for r in rights_published]
            )
            if d
        ]
        coverage = {
            "evidence_count": len(company_linked_evidence),
            "fact_count": len(company_facts),
            "signal_count": len(company_signals),
            "assessment_count": len(company_assessments),
            "variety_count": len(portfolio_varieties),
            "geography_count": len(geo_ids),
            "source_count": len(source_ids),
            "latest_date": max(dates) if dates else "",
        }

        product_groups = [
            {"key": key, "label": product_group_labels[key], "count": count}
            for key, count in product_group_counts.items()
        ]

        cards.append(
            {
                "id": cid,
                "href": f"/entities/company/{cid}",
                "timeline_href": f"/entities/company/{cid}#intelligence-timeline",
                "name": company.get("name") or cid,
                "aliases": list(company.get("aliases") or []),
                "berry_ids": berry_ids,
                "berries": [berry_labels.get(b, b) for b in berry_ids],
                "roles": roles,
                "portfolio_variety_ids": portfolio_variety_ids,
                "rights_published": rights_published,
                "geographies": geographies,
                "retailers": retailer_parties,
                "commercial_observation_count": commercial_obs_count,
                "product_groups": product_groups,
                "signals": [
                    {"id": s.get("id"), "title": s.get("title"), "status": s.get("status"), "href": f"/signals/{s['id']}"}
                    for s in company_signals
                ],
                "assessments": [
                    {
                        "id": a.get("id"),
                        "title": a.get("title"),
                        "confidence": a.get("confidence"),
                        "href": f"/assessments/{a['id']}",
                    }
                    for a in company_assessments
                ],
                "recent_cards": recent_cards,
                "coverage": coverage,
                "source_type_counts": sorted(source_type_counts.items(), key=lambda kv: -kv[1]),
            }
        )

    role_matrix = _build_role_matrix(cards)

    return {
        "companies": cards,
        "invalid_ids": invalid_ids,
        "overflow_ids": overflow_ids,
        "role_labels": ROLE_LABEL,
        "role_matrix": role_matrix,
        "count": len(cards),
        "max_reached": len(cards) >= COMPARE_MAX_COMPANIES,
    }


def _build_role_matrix(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Only roles actually represented by at least one compared company --
    avoids a giant sparse table of every possible role bucket."""
    rows: list[dict[str, Any]] = []
    for bucket, _predicate, label in ROLE_BUCKETS:
        counts = [len(card["roles"].get(bucket) or []) for card in cards]
        if any(counts):
            rows.append({"bucket": bucket, "label": label, "counts": counts})
    return rows
