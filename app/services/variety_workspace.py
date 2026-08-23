"""V2 Variety Intelligence workspace — presentation only.

Consumes Variety Backbone query services (`variety_footprint` and friends)
without persisting derived conclusions, mutating schemas, or calling a
footprint once per index card. Draft commercial observations stay labeled
as pending review; they are never Facts.
"""

from __future__ import annotations

from typing import Any

from app.services.berries.variety import variety_patent_link, variety_trait_profile
from app.services.intelligence_feed import present_feed_item
from app.services.variety_footprint import (
    competing_varieties_in_berry_market,
    variety_footprint,
    varieties_observed_in_market,
    varieties_with_ip_activity_and_commercial_observation,
)

ROLE_BUCKETS = (
    ("breeder", "develops", "Breeder"),
    ("owner_rights_holder", "owns", "Owner / rights holder"),
    ("licensee", "licenses", "Licensee"),
    ("marketer", "markets", "Marketer"),
    ("grower", "grows", "Grower"),
    ("distributor", "distributes", "Distributor"),
)
ROLE_PREDICATE = {bucket: predicate for bucket, predicate, _label in ROLE_BUCKETS}
ROLE_LABEL = {bucket: label for bucket, _predicate, label in ROLE_BUCKETS}
INCOMING_ROLE_PREDICATES = {predicate for _bucket, predicate, _label in ROLE_BUCKETS}

UK_GEO_ID = "geography-united-kingdom"
UK_PILOT_NAMED_IDS = ("variety-zara", "variety-victoria")
UK_PILOT_EXPECTED_TOTAL = 18
UK_PILOT_EXPECTED_NAMED = 2
UK_PILOT_EXPECTED_UNNAMED = 16

VIEWS = ("index", "compete", "observations")

# Variety Profile Intelligence V2 -- a small, closed-vocabulary mapping from
# the real trait entity catalog (data/entities/traits/*.json, 13 records) to
# a coarser display group. This is NOT NLP over free text: it is a lookup
# over already-curated, stable trait entity ids. A trait id not listed here
# (e.g. a future 14th trait entity) is not silently mis-grouped -- it falls
# into "Other observations" until someone deliberately adds it below.
TRAIT_GROUP_BUCKETS = (
    ("product_sensory", "Product / sensory", (
        "trait-eating-quality",
        "trait-fruit-color",
        "trait-fruit-size",
        "trait-soluble-solids",
        "trait-titratable-acidity",
    )),
    ("postharvest_quality", "Postharvest / quality", (
        "trait-fruit-firmness",
        "trait-postharvest-shelf-life",
    )),
    ("production_agronomic", "Production / agronomic", (
        "trait-machine-harvest-suitability",
        "trait-chilling-requirement",
        "trait-flowering-habit",
        "trait-fruiting-habit",
        "trait-yield",
        "trait-disease-susceptibility",
    )),
)
TRAIT_TO_GROUP: dict[str, tuple[str, str]] = {
    trait_id: (bucket, label)
    for bucket, label, trait_ids in TRAIT_GROUP_BUCKETS
    for trait_id in trait_ids
}

# Humanizes the real, already-structured Evidence.source_type field for
# attribution display. This is not a new attribution taxonomy -- current
# schema has no field distinguishing "retailer feedback" from "marketer
# feedback" from "company self-report" more finely than source_type already
# does (see TD register: no structured attribution-role field exists yet).
SOURCE_TYPE_LABEL: dict[str, str] = {
    "company_press_release": "Company self-report",
    "trade_press": "Trade press (third-party)",
    "patent_record": "Patent registry",
    "plant_breeders_rights_record": "Plant breeders' rights registry",
    "news_search": "News / press coverage",
    "industry_podcast": "Industry podcast",
    "discovered_media": "Discovered media",
    "private_equity_press_release": "Private equity press release",
    "development_finance_press_release": "Development finance press release",
}


def _by_id(entities: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(entity["id"]): entity for entity in entities if entity.get("id")}


def _name(entity: dict[str, Any] | None, fallback: str = "") -> str:
    if not entity:
        return fallback
    return str(entity.get("name") or fallback)


def _stamp(record: dict[str, Any]) -> str:
    return str(
        record.get("published_date")
        or record.get("captured_date")
        or (record.get("commercial_observation") or {}).get("observed_at")
        or ""
    )


def _is_observation(record: dict[str, Any]) -> bool:
    if record.get("intake_type") == "commercial_observation":
        return True
    return bool(record.get("commercial_observation"))


def _is_rights_record(record: dict[str, Any]) -> bool:
    return record.get("source_type") in {"plant_breeders_rights_record", "patent_record"}


def _rights_kind(record: dict[str, Any]) -> str:
    source_type = str(record.get("source_type") or "")
    blob = " ".join(
        [
            str(record.get("source_name") or ""),
            str(record.get("title") or ""),
            str(record.get("source_id") or ""),
        ]
    ).casefold()
    if "cpvo" in blob or "community plant variety" in blob:
        return "CPVO"
    if "uspto" in blob or source_type == "patent_record" or "plant patent" in blob:
        return "USPTO"
    if source_type == "plant_breeders_rights_record":
        if "cfia" in blob or "canada" in blob:
            return "CFIA PBR"
        return "PVR"
    return "Other filing"


def _party(entity: dict[str, Any] | None) -> dict[str, str]:
    if not entity or not entity.get("id"):
        return {}
    return {
        "id": str(entity["id"]),
        "name": _name(entity),
        "href": f"/entities/{entity.get('entity_type')}/{entity['id']}",
        "entity_type": str(entity.get("entity_type") or ""),
    }


def identity_fields(variety: dict[str, Any]) -> dict[str, Any]:
    attrs = variety.get("attributes") or {}
    canonical = str(variety.get("name") or variety.get("id") or "")
    aliases_raw = [str(value) for value in (variety.get("aliases") or []) if value]
    commercial = str(attrs.get("trade_name") or attrs.get("commercial_name") or "").strip()
    denomination = str(attrs.get("denomination") or "").strip()
    breeder_code = str(attrs.get("selection_code") or attrs.get("breeder_code") or "").strip()
    commercial_names: list[str] = []
    if commercial and commercial.casefold() != canonical.casefold():
        commercial_names.append(commercial)
    skip = {canonical.casefold(), *(name.casefold() for name in commercial_names)}
    aliases = [value for value in aliases_raw if value.casefold() not in skip]
    return {
        "canonical_name": canonical,
        "aliases": aliases,
        "commercial_names": commercial_names,
        "denomination": denomination if denomination.casefold() != canonical.casefold() else "",
        "breeder_code": breeder_code,
        "package_note": str(attrs.get("package_note") or "").strip(),
    }


def build_variety_indexes(
    *,
    varieties: list[dict[str, Any]],
    entities: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
    published_evidence: list[dict[str, Any]],
    inbox_drafts: list[dict[str, Any]] | None = None,
    signals: list[dict[str, Any]] | None = None,
    candidates: list[dict[str, Any]] | None = None,
    facts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """One-pass indexes for the Variety index. Does not call variety_footprint."""

    inbox_drafts = inbox_drafts or []
    signals = signals or []
    candidates = candidates or []
    facts = facts or []
    entity_index = _by_id(entities)
    variety_ids = {str(row["id"]) for row in varieties if row.get("id")}

    roles: dict[str, dict[str, list[str]]] = {
        vid: {bucket: [] for bucket, _predicate, _label in ROLE_BUCKETS} for vid in variety_ids
    }
    for rel in relationships:
        variety_id = str(rel.get("object_id") or "")
        predicate = rel.get("predicate")
        subject_id = str(rel.get("subject_id") or "")
        if variety_id not in roles or predicate not in INCOMING_ROLE_PREDICATES or not subject_id:
            continue
        bucket = next(bucket for bucket, pred, _label in ROLE_BUCKETS if pred == predicate)
        if subject_id not in roles[variety_id][bucket]:
            roles[variety_id][bucket].append(subject_id)

    rights: dict[str, dict[str, Any]] = {
        vid: {"published": 0, "draft": 0, "kinds": []} for vid in variety_ids
    }
    observations: dict[str, dict[str, Any]] = {
        vid: {
            "published": 0,
            "draft": 0,
            "countries": set(),
            "retailers": set(),
            "latest": "",
        }
        for vid in variety_ids
    }
    unnamed_obs: list[dict[str, Any]] = []
    recent: dict[str, dict[str, str]] = {}

    def _note_recent(variety_id: str, record: dict[str, Any]) -> None:
        stamp = _stamp(record)
        current = recent.get(variety_id) or {}
        if stamp and stamp >= str(current.get("date") or ""):
            recent[variety_id] = {
                "date": stamp,
                "title": str(record.get("title") or ""),
                "id": str(record.get("id") or ""),
                "trust": "published" if record.get("status") == "published" else "draft",
            }

    def _walk(records: list[dict[str, Any]], trust: str) -> None:
        draft = trust != "published"
        for record in records:
            eids = {str(value) for value in (record.get("entity_ids") or []) if value}
            touching = eids & variety_ids
            for variety_id in touching:
                _note_recent(variety_id, record)
            if _is_rights_record(record):
                kind = _rights_kind(record)
                for variety_id in touching:
                    bucket = rights[variety_id]
                    if draft:
                        bucket["draft"] += 1
                    else:
                        bucket["published"] += 1
                    if kind not in bucket["kinds"]:
                        bucket["kinds"].append(kind)
            if not _is_observation(record):
                continue
            detail = record.get("commercial_observation") or {}
            variety_id = detail.get("variety_entity_id")
            presented = present_observation(record, entities=entity_index, trust=trust)
            if not variety_id:
                unnamed_obs.append(presented)
                continue
            variety_id = str(variety_id)
            if variety_id not in observations:
                continue
            bucket = observations[variety_id]
            if draft:
                bucket["draft"] += 1
            else:
                bucket["published"] += 1
            bucket["countries"].update(record.get("geography_ids") or [])
            if detail.get("market_country"):
                bucket["countries"].add(str(detail["market_country"]))
            retailer_id = detail.get("retailer_entity_id")
            if retailer_id:
                bucket["retailers"].add(str(retailer_id))
            observed = str(detail.get("observed_at") or _stamp(record) or "")
            if observed > str(bucket["latest"] or ""):
                bucket["latest"] = observed

    _walk(published_evidence, "published")
    _walk(inbox_drafts, "draft (pending review)")

    signal_counts: dict[str, dict[str, int]] = {vid: {"signals": 0, "candidates": 0} for vid in variety_ids}
    for signal in signals:
        for eid in signal.get("entity_ids") or []:
            vid = str(eid)
            if vid in signal_counts:
                signal_counts[vid]["signals"] += 1
    for candidate in candidates:
        for eid in candidate.get("entity_ids") or []:
            vid = str(eid)
            if vid in signal_counts:
                signal_counts[vid]["candidates"] += 1

    # Variety Profile Intelligence V2: one more single pass, same shape as
    # the roles/rights/observations walks above -- counts real trait-tagged
    # Facts per variety (see TRAIT_TO_GROUP) without calling
    # present_variety_intelligence() or variety_footprint() per card.
    product_evidence: dict[str, int] = {vid: 0 for vid in variety_ids}
    for fact in facts:
        fact_entity_ids = {str(value) for value in (fact.get("entity_ids") or []) if value}
        if not any(str(eid).startswith("trait-") for eid in fact_entity_ids):
            continue
        for variety_id in fact_entity_ids & variety_ids:
            product_evidence[variety_id] += 1

    return {
        "roles": roles,
        "rights": rights,
        "observations": observations,
        "unnamed_observations": unnamed_obs,
        "recent": recent,
        "signal_counts": signal_counts,
        "product_evidence": product_evidence,
        "entity_index": entity_index,
    }


def _role_parties(role_ids: list[str], entity_index: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    parties = []
    seen: set[str] = set()
    for entity_id in role_ids:
        if entity_id in seen:
            continue
        seen.add(entity_id)
        party = _party(entity_index.get(entity_id))
        if party:
            parties.append(party)
    return parties


def _rights_summary(rights: dict[str, Any]) -> str:
    published = int(rights.get("published") or 0)
    draft = int(rights.get("draft") or 0)
    kinds = list(rights.get("kinds") or [])
    if not published and not draft:
        return "No filings recorded"
    bits: list[str] = []
    if kinds:
        bits.append(" · ".join(kinds))
    if published:
        bits.append(f"{published} trusted")
    if draft:
        bits.append(f"{draft} pending review")
    return " · ".join(bits)


def present_variety_card(
    variety: dict[str, Any],
    *,
    indexes: dict[str, Any],
    berry_labels: dict[str, str],
) -> dict[str, Any]:
    vid = str(variety["id"])
    entity_index: dict[str, dict[str, Any]] = indexes["entity_index"]
    roles = indexes["roles"].get(vid) or {}
    rights = indexes["rights"].get(vid) or {"published": 0, "draft": 0, "kinds": []}
    obs = indexes["observations"].get(vid) or {
        "published": 0,
        "draft": 0,
        "countries": set(),
        "retailers": set(),
        "latest": "",
    }
    identity = identity_fields(variety)
    breeders = _role_parties(roles.get("breeder") or [], entity_index)
    owners = _role_parties(roles.get("owner_rights_holder") or [], entity_index)
    marketers = _role_parties(roles.get("marketer") or [], entity_index)
    market_names = []
    for geo_id in sorted(obs.get("countries") or []):
        entity = entity_index.get(str(geo_id))
        market_names.append(_name(entity, str(geo_id)))
    recent = indexes["recent"].get(vid) or {}
    signals = indexes["signal_counts"].get(vid) or {"signals": 0, "candidates": 0}
    obs_count = int(obs.get("published") or 0) + int(obs.get("draft") or 0)
    product_evidence_count = int((indexes.get("product_evidence") or {}).get(vid) or 0)
    return {
        "id": vid,
        "href": f"/entities/variety/{vid}",
        "name": identity["canonical_name"],
        "identity": identity,
        "berries": [berry_labels.get(berry_id, berry_id) for berry_id in (variety.get("berry_ids") or [])],
        "berry_ids": list(variety.get("berry_ids") or []),
        "breeders": breeders,
        "owners": owners,
        "marketers": marketers,
        "rights_summary": _rights_summary(rights),
        "has_rights": bool(rights.get("published") or rights.get("draft")),
        "has_observation": obs_count > 0,
        "observation_count": obs_count,
        "markets_observed": market_names,
        "recent": recent,
        "signal_count": int(signals.get("signals") or 0),
        "candidate_count": int(signals.get("candidates") or 0),
        "product_evidence_count": product_evidence_count,
        "has_product_evidence": product_evidence_count > 0,
    }


def present_observation(
    record: dict[str, Any],
    *,
    entities: dict[str, dict[str, Any]],
    trust: str,
) -> dict[str, Any]:
    detail = record.get("commercial_observation") or {}
    variety_id = detail.get("variety_entity_id")
    retailer_id = detail.get("retailer_entity_id")
    marketer_id = detail.get("marketer_entity_id")
    origin_id = detail.get("origin_geography_id")
    variety = entities.get(str(variety_id)) if variety_id else None
    retailer = entities.get(str(retailer_id)) if retailer_id else None
    named = bool(variety_id and variety)
    price = detail.get("price")
    currency = detail.get("currency")
    price_label = ""
    if price is not None and price != "":
        price_label = f"{currency + ' ' if currency else ''}{price}".strip()
    return {
        "id": record.get("id"),
        "trust": trust,
        "is_draft": trust != "published",
        "title": record.get("title") or "Commercial observation",
        "retailer_name": detail.get("retailer_name") or _name(retailer) or "",
        "retailer": _party(retailer),
        "channel": detail.get("channel") or "",
        "market_country": detail.get("market_country") or "",
        "observed_at": detail.get("observed_at") or record.get("captured_date") or "",
        "berry_ids": list(record.get("berry_ids") or []),
        "variety_named": named,
        "variety": _party(variety) if named else {},
        "variety_unknown": not named,
        "brand": detail.get("brand") or "",
        "marketer": _party(entities.get(str(marketer_id))) if marketer_id else {},
        "origin": _party(entities.get(str(origin_id))) if origin_id else {},
        "price_label": price_label,
        "pack_size": detail.get("pack_size") or "",
        "promotion": detail.get("promotion") or "",
        "claims": list(detail.get("claims") or []),
        "source_name": record.get("source_name") or "",
        "source_url": record.get("source_url") or "",
        "review_state": record.get("review_state") or record.get("status") or "",
        "verification_state": record.get("verification_state") or "",
        "source_authority": record.get("source_authority") or "",
        "does_not_prove": record.get("does_not_prove") or "",
        "geography_ids": list(record.get("geography_ids") or []),
        "href": f"/intelligence/{record.get('id')}" if record.get("id") else "",
        "trusted_href": f"/evidence/{record.get('id')}" if record.get("id") else "",
    }


def uk_pilot_summary(
    observations: list[dict[str, Any]],
    *,
    entities: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    uk_obs = [
        row
        for row in observations
        if UK_GEO_ID in (row.get("geography_ids") or [])
        or str(row.get("market_country") or "").casefold() in {"united kingdom", "uk", "great britain"}
    ]
    named = [row for row in uk_obs if row.get("variety_named")]
    unnamed = [row for row in uk_obs if row.get("variety_unknown")]
    berries = sorted({berry_id for row in uk_obs for berry_id in (row.get("berry_ids") or [])})
    retailers = sorted({row.get("retailer_name") or (row.get("retailer") or {}).get("name") or "" for row in uk_obs if row.get("retailer_name") or (row.get("retailer") or {}).get("name")})
    zara = entities.get("variety-zara")
    victoria = entities.get("variety-victoria")
    runtime_loaded = bool(uk_obs)
    return {
        "expected_total": UK_PILOT_EXPECTED_TOTAL,
        "expected_named": UK_PILOT_EXPECTED_NAMED,
        "expected_unnamed": UK_PILOT_EXPECTED_UNNAMED,
        "runtime_total": len(uk_obs),
        "runtime_named": len(named),
        "runtime_unnamed": len(unnamed),
        "runtime_loaded": runtime_loaded,
        "berries": berries,
        "retailers": [name for name in retailers if name],
        "named_varieties": [_party(zara), _party(victoria)],
        "honest_copy": (
            f"{len(named)} of {len(uk_obs)} UK listings name a cultivar. "
            f"{len(unnamed)} listings have no variety name — that absence is a listing fact, not global ignorance of the variety."
            if runtime_loaded
            else (
                "The 18 UK Open Food Facts observation drafts from Variety Backbone V1 live in gitignored "
                "inbox/ and are not loaded in this runtime. They are not fabricated here. Two named-variety "
                "cases remain as Variety entities: Zara (strawberry) and Victoria (blackberry). "
                "16 of 18 listings in that pilot had no cultivar name (TD-022)."
            )
        ),
    }


def berry_inventory(varieties: list[dict[str, Any]], berry_labels: dict[str, str]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {berry_id: 0 for berry_id in berry_labels}
    for variety in varieties:
        for berry_id in variety.get("berry_ids") or []:
            if berry_id in counts:
                counts[berry_id] += 1
    return [
        {
            "id": berry_id,
            "label": label,
            "count": counts.get(berry_id) or 0,
            "thin": (counts.get(berry_id) or 0) <= 1,
        }
        for berry_id, label in berry_labels.items()
    ]


def present_variety_index(
    *,
    varieties: list[dict[str, Any]],
    entities: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
    published_evidence: list[dict[str, Any]],
    berry_labels: dict[str, str],
    inbox_drafts: list[dict[str, Any]] | None = None,
    signals: list[dict[str, Any]] | None = None,
    candidates: list[dict[str, Any]] | None = None,
    facts: list[dict[str, Any]] | None = None,
    filters: dict[str, str] | None = None,
) -> dict[str, Any]:
    filters = filters or {}
    indexes = build_variety_indexes(
        varieties=varieties,
        entities=entities,
        relationships=relationships,
        published_evidence=published_evidence,
        inbox_drafts=inbox_drafts,
        signals=signals,
        candidates=candidates,
        facts=facts,
    )
    cards = [
        present_variety_card(variety, indexes=indexes, berry_labels=berry_labels) for variety in varieties
    ]
    has_rights = str(filters.get("has_rights") or "")
    has_observation = str(filters.get("has_observation") or "")
    has_product_evidence = str(filters.get("has_product_evidence") or "")
    has_signal = str(filters.get("has_signal") or "")
    if has_rights in {"1", "true", "yes"}:
        cards = [card for card in cards if card["has_rights"]]
    if has_observation in {"1", "true", "yes"}:
        cards = [card for card in cards if card["has_observation"]]
    if has_product_evidence in {"1", "true", "yes"}:
        cards = [card for card in cards if card["has_product_evidence"]]
    if has_signal in {"1", "true", "yes"}:
        cards = [card for card in cards if card["signal_count"] > 0]
    named_obs = sum(
        int(row.get("published") or 0) + int(row.get("draft") or 0)
        for row in indexes["observations"].values()
    )
    unnamed_obs = len(indexes["unnamed_observations"])
    return {
        "cards": cards,
        "berry_inventory": berry_inventory(varieties, berry_labels),
        "unnamed_observation_count": unnamed_obs,
        "observation_total_count": named_obs + unnamed_obs,
    }


def present_observation_workspace(
    *,
    entities: list[dict[str, Any]],
    published_evidence: list[dict[str, Any]],
    inbox_drafts: list[dict[str, Any]] | None = None,
    berry_labels: dict[str, str],
    berry_id: str | None = None,
) -> dict[str, Any]:
    inbox_drafts = inbox_drafts or []
    entity_index = _by_id(entities)
    rows: list[dict[str, Any]] = []
    for trust, records in (("published", published_evidence), ("draft (pending review)", inbox_drafts)):
        for record in records:
            if not _is_observation(record):
                continue
            if berry_id and berry_id not in (record.get("berry_ids") or []):
                continue
            rows.append(present_observation(record, entities=entity_index, trust=trust))
    rows.sort(key=lambda row: str(row.get("observed_at") or ""), reverse=True)
    named = [row for row in rows if row.get("variety_named")]
    unnamed = [row for row in rows if row.get("variety_unknown")]
    return {
        "observation_rows": rows,
        "named_count": len(named),
        "unnamed_count": len(unnamed),
        "uk_pilot": uk_pilot_summary(rows, entities=entity_index),
        "berry_labels": berry_labels,
    }


def present_competition(
    *,
    berry_id: str | None,
    country_geo_id: str | None,
    entities: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
    published_evidence: list[dict[str, Any]],
    inbox_drafts: list[dict[str, Any]] | None = None,
    berry_labels: dict[str, str],
    ip_and_observation: bool = False,
) -> dict[str, Any]:
    inbox_drafts = inbox_drafts or []
    overlap = varieties_with_ip_activity_and_commercial_observation(
        entities=entities,
        published_evidence=published_evidence,
        inbox_drafts=inbox_drafts,
    )
    groups: list[dict[str, Any]] = []
    observed: list[dict[str, Any]] = []
    if berry_id:
        groups = competing_varieties_in_berry_market(
            berry_id=berry_id,
            country_geo_id=country_geo_id,
            entities=entities,
            relationships=relationships,
            published_evidence=published_evidence,
            inbox_drafts=inbox_drafts,
        )
        if country_geo_id:
            observed = varieties_observed_in_market(
                country_geo_id=country_geo_id,
                berry_id=berry_id,
                entities=entities,
                published_evidence=published_evidence,
                inbox_drafts=inbox_drafts,
            )
    overlap_ids = {row["variety_id"] for row in overlap}
    overlap_names = {row.get("name") for row in overlap if row.get("name")}
    if ip_and_observation:
        groups = [
            {
                **group,
                "varieties": [name for name in group.get("varieties") or [] if name in overlap_names],
            }
            for group in groups
        ]
        groups = [group for group in groups if group.get("varieties")]
    berry_varieties = [
        entity
        for entity in entities
        if entity.get("entity_type") == "variety" and berry_id in (entity.get("berry_ids") or [])
    ] if berry_id else []
    variety_rows: list[dict[str, Any]] = []
    if berry_varieties:
        indexes = build_variety_indexes(
            varieties=berry_varieties,
            entities=entities,
            relationships=relationships,
            published_evidence=published_evidence,
            inbox_drafts=inbox_drafts,
        )
        observed_ids = {row["variety_id"] for row in observed}
        for variety in berry_varieties:
            card = present_variety_card(variety, indexes=indexes, berry_labels=berry_labels)
            if country_geo_id and observed_ids and card["id"] not in observed_ids:
                continue
            if ip_and_observation and card["id"] not in overlap_ids:
                continue
            variety_rows.append(card)
    # Real, count-based check (matches berry_inventory()'s own "thin"
    # threshold) -- not hardcoded to a specific berry. Found and fixed
    # during Caneberry Variety + Actor Expansion V1 (2026-08-22): this
    # previously read `berry_id == "berry-blackberry"` unconditionally,
    # so the "Blackberry is honestly thin" copy below would have kept
    # showing even after real evidence-grounded Variety entities made it
    # false (1 -> 5 varieties this mission).
    thin_variety_count = berry_id == "berry-blackberry" and len(berry_varieties) <= 1
    return {
        "berry_id": berry_id or "",
        "berry_label": berry_labels.get(berry_id or "", ""),
        "country_geo_id": country_geo_id or "",
        "groups": groups,
        "variety_rows": variety_rows,
        "observed_in_market": observed,
        "ip_overlap": overlap,
        "ip_overlap_empty": not overlap,
        "blackberry_thin": thin_variety_count,
        "needs_berry": not berry_id,
    }


def _network_from_relationships(
    grouped: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    network: dict[str, list[dict[str, Any]]] = {bucket: [] for bucket, _pred, _label in ROLE_BUCKETS}
    network["geography"] = []
    network["related_varieties"] = []
    network["other"] = []
    for row in grouped:
        other = row.get("other") or {}
        predicate = row.get("predicate")
        party = {
            **(_party(other) or {}),
            "predicate": predicate,
            "direction": row.get("direction"),
            "notes": row.get("notes") or "",
        }
        if predicate in INCOMING_ROLE_PREDICATES and row.get("direction") == "incoming":
            bucket = next(bucket for bucket, pred, _label in ROLE_BUCKETS if pred == predicate)
            network[bucket].append(party)
        elif other.get("entity_type") == "geography":
            network["geography"].append(party)
        elif other.get("entity_type") == "variety":
            network["related_varieties"].append(party)
        else:
            network["other"].append(party)
    return network


def _present_fact_observation(
    fact: dict[str, Any],
    *,
    entities: dict[str, dict[str, Any]],
    evidence_by_id: dict[str, dict[str, Any]],
    trait_ids: list[str],
) -> dict[str, Any]:
    evidence_ids = [str(eid) for eid in (fact.get("evidence_ids") or []) if eid]
    primary = evidence_by_id.get(evidence_ids[0]) if evidence_ids else None
    trait_names = [
        _name(entities.get(trait_id), trait_id.removeprefix("trait-").replace("-", " ").title())
        for trait_id in trait_ids
    ]
    geography = []
    if primary:
        for geo_id in primary.get("geography_ids") or []:
            party = _party(entities.get(str(geo_id)))
            if party:
                geography.append(party)
    source_type = str((primary or {}).get("source_type") or "")
    return {
        "id": fact.get("id"),
        "statement": fact.get("statement") or "",
        "classification": fact.get("classification") or "",
        "confidence": fact.get("confidence") or "",
        "fact_status": fact.get("status") or "",
        "trait_names": trait_names,
        "fact_href": f"/facts/{fact['id']}" if fact.get("id") else "",
        "evidence_id": (primary or {}).get("id") or "",
        "evidence_href": f"/evidence/{primary['id']}" if primary else "",
        "reader_href": f"/intelligence/{primary['id']}" if primary else "",
        "source_name": (primary or {}).get("source_name") or "",
        "source_type": source_type,
        "source_type_label": SOURCE_TYPE_LABEL.get(source_type, source_type.replace("_", " ").title() if source_type else "Unspecified source"),
        "source_authority": (primary or {}).get("source_authority") or "",
        "verification_state": (primary or {}).get("verification_state") or "",
        "does_not_prove": list((primary or {}).get("does_not_prove") or []),
        "published_date": (primary or {}).get("published_date") or (primary or {}).get("captured_date") or "",
        "geography": geography,
        "additional_source_count": max(len(evidence_ids) - 1, 0),
    }


def present_variety_intelligence(
    variety: dict[str, Any],
    *,
    entities: dict[str, dict[str, Any]],
    facts: list[dict[str, Any]],
    evidence_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Groups trait-tagged Facts touching this variety by product/postharvest/
    production dimension, using only the real trait entity catalog
    (data/entities/traits/*.json, TRAIT_TO_GROUP above) and real
    Fact.entity_ids co-occurrence with the variety -- no new schema, no AI
    inference, no NLP over free text. Creates no records; presentation only.

    Commercial/market observations are deliberately NOT duplicated here --
    they already have their own richer, well-established presentation in
    the Commercial footprint section (present_observation /
    _commercial_observation.html); this function only covers the product,
    postharvest, and production/agronomic dimensions that section does not.
    """
    variety_id = str(variety.get("id") or "")
    grouped: dict[str, list[dict[str, Any]]] = {bucket: [] for bucket, _label, _ids in TRAIT_GROUP_BUCKETS}
    grouped["other"] = []
    evidence_ids_seen: set[str] = set()
    geography_ids_seen: set[str] = set()
    dates: list[str] = []

    for fact in facts:
        fact_entity_ids = [str(eid) for eid in (fact.get("entity_ids") or []) if eid]
        if variety_id not in fact_entity_ids:
            continue
        trait_ids = [eid for eid in fact_entity_ids if eid.startswith("trait-")]
        if not trait_ids:
            continue
        bucket = "other"
        for trait_id in trait_ids:
            if trait_id in TRAIT_TO_GROUP:
                bucket = TRAIT_TO_GROUP[trait_id][0]
                break
        row = _present_fact_observation(fact, entities=entities, evidence_by_id=evidence_by_id, trait_ids=trait_ids)
        grouped[bucket].append(row)
        for eid in fact.get("evidence_ids") or []:
            eid = str(eid)
            evidence_ids_seen.add(eid)
            record = evidence_by_id.get(eid)
            if record:
                geography_ids_seen.update(str(g) for g in (record.get("geography_ids") or []))
                stamp = record.get("published_date") or record.get("captured_date")
                if stamp:
                    dates.append(str(stamp))

    for rows in grouped.values():
        rows.sort(key=lambda row: str(row.get("published_date") or ""), reverse=True)

    groups = [
        {"key": bucket, "label": label, "rows": grouped[bucket]}
        for bucket, label, _ids in TRAIT_GROUP_BUCKETS
        if grouped[bucket]
    ]
    if grouped["other"]:
        groups.append({"key": "other", "label": "Other observations", "rows": grouped["other"]})

    return {
        "groups": groups,
        "has_any": bool(groups),
        "coverage": {
            "observation_count": sum(len(g["rows"]) for g in groups),
            "source_count": len(evidence_ids_seen),
            "geography_count": len(geography_ids_seen),
            "latest_date": max(dates) if dates else "",
        },
    }


def present_variety_detail(
    variety: dict[str, Any],
    *,
    entities: dict[str, dict[str, Any]],
    relationships: list[dict[str, Any]],
    published_evidence: list[dict[str, Any]],
    grouped_relationships: list[dict[str, Any]],
    recent_intelligence: list[dict[str, Any]],
    berry_labels: dict[str, str],
    inbox_drafts: list[dict[str, Any]] | None = None,
    story_threads: list[dict[str, Any]] | None = None,
    signals: list[dict[str, Any]] | None = None,
    include_candidates: bool = True,
    facts: list[dict[str, Any]] | None = None,
    evidence_by_id: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    inbox_drafts = inbox_drafts or []
    facts = facts or []
    evidence_by_id = evidence_by_id or {}
    entity_list = list(entities.values())
    footprint = variety_footprint(
        variety["id"],
        entities=entity_list,
        relationships=relationships,
        published_evidence=published_evidence,
        inbox_drafts=inbox_drafts,
        story_threads=story_threads,
        signals=signals,
    )
    identity = identity_fields(variety)
    roles_resolved = {
        bucket: _role_parties(footprint.get("roles", {}).get(bucket) or [], entities)
        for bucket, _predicate, _label in ROLE_BUCKETS
    }
    observations = [
        present_observation(
            next(
                (
                    record
                    for record in list(published_evidence) + list(inbox_drafts)
                    if record.get("id") == row.get("id")
                ),
                {
                    "id": row.get("id"),
                    "commercial_observation": row,
                    "status": "published" if row.get("trust") == "published" else "draft",
                    "title": "Commercial observation",
                },
            ),
            entities=entities,
            trust=str(row.get("trust") or "published"),
        )
        for row in footprint.get("commercial_observations") or []
    ]
    patents = [entity for entity in entity_list if entity.get("entity_type") == "patent"]
    recent_cards: list[dict[str, Any]] = []
    for item in recent_intelligence:
        record = item.get("record") or {}
        if not record.get("id"):
            continue
        card = present_feed_item(record, entities=entities, berry_labels=berry_labels)
        if item.get("is_thread"):
            card["is_thread"] = True
            card["story_thread"] = item.get("thread")
            card["title"] = item.get("developing_label") or card["title"]
            if item.get("thread", {}).get("href"):
                card["href"] = item["thread"]["href"]
        recent_cards.append(card)
    rights_published = list((footprint.get("rights_filings") or {}).get("published") or [])
    rights_drafts = list((footprint.get("rights_filings") or {}).get("draft_pending_review") or [])
    for row in rights_published:
        row["kind"] = _rights_kind(row)
        row["trust"] = "published"
        row["href"] = f"/intelligence/{row['id']}"
        row["trusted_href"] = f"/evidence/{row['id']}"
    for row in rights_drafts:
        row["kind"] = _rights_kind(row)
        row["trust"] = "draft (pending review)"
        row["href"] = f"/intelligence/{row['id']}"
    countries = []
    for geo_id in footprint.get("countries_observed") or []:
        entity = entities.get(str(geo_id))
        countries.append(_party(entity) if entity else {"id": str(geo_id), "name": str(geo_id), "href": ""})
    retailers = []
    for retailer_id in footprint.get("retailers_observed") or []:
        entity = entities.get(str(retailer_id))
        if entity:
            retailers.append(_party(entity))
    berry_id = (variety.get("berry_ids") or [None])[0]
    landscape_href = f"/landscapes/berries/{str(berry_id).removeprefix('berry-')}" if berry_id else "/entities/berry"
    traits = variety_trait_profile(variety, entities)
    variety_intelligence = present_variety_intelligence(
        variety, entities=entities, facts=facts, evidence_by_id=evidence_by_id
    )
    obs_dates = [row.get("observed_at") for row in observations if row.get("observed_at")]
    obs_geo_ids = {str(g) for row in observations for g in (row.get("geography_ids") or [])}
    obs_source_ids = {row.get("id") for row in observations if row.get("id")}
    rights_dates = [row.get("published_date") for row in rights_published if row.get("published_date")]
    all_dates = [
        d for d in (
            [variety_intelligence["coverage"]["latest_date"]] + obs_dates + rights_dates
        )
        if d
    ]
    intelligence_evidence_ids = {
        row.get("evidence_id") for group in variety_intelligence["groups"] for row in group["rows"] if row.get("evidence_id")
    }
    intelligence_geo_ids = {
        g["id"] for group in variety_intelligence["groups"] for row in group["rows"] for g in row.get("geography", [])
    }
    evidence_coverage = {
        "observation_count": (
            variety_intelligence["coverage"]["observation_count"] + len(observations) + len(rights_published)
        ),
        "source_count": len(
            obs_source_ids
            | intelligence_evidence_ids
            | {row.get("id") for row in rights_published if row.get("id")}
        ),
        "geography_count": len(obs_geo_ids | intelligence_geo_ids),
        "latest_date": max(all_dates) if all_dates else "",
    }
    return {
        "identity": identity,
        "roles": roles_resolved,
        "role_labels": ROLE_LABEL,
        "footprint": footprint,
        "observations": observations,
        "variety_intelligence": variety_intelligence,
        "evidence_coverage": evidence_coverage,
        "rights_published": rights_published,
        "rights_drafts": rights_drafts,
        "countries_observed": countries,
        "retailers_observed": retailers,
        "traits": traits,
        "patent_link": variety_patent_link(variety, patents),
        "recent_cards": recent_cards,
        "network": _network_from_relationships(grouped_relationships),
        "landscape_href": landscape_href,
        "include_candidates": include_candidates,
        "uk_named_pilot": variety["id"] in UK_PILOT_NAMED_IDS,
    }
