"""Intelligence Front Page V1 -- unified editorial front-page projection.

The authenticated homepage (`/today`) previously showed only published
Evidence, Signal, and Assessment rows (see build_today() in
app/services/today.py) -- nothing upstream of Publication Review was
visible at all. That is the literal cause of the "stale homepage" product
problem this module fixes: fresh, source-backed material can sit in the
review queue for hours while the homepage shows nothing newer than the
last analyst-reviewed item.

This module does not add a second data repository. It composes existing
services: app.services.today.build_today() for the freshness/worth-
revisiting/last-seen machinery, app.services.intelligence_feed's
present_feed_item/classify_kind/entity_chips for Publication/Evidence
presentation (deliberately reusing its TRUST_LABELS vocabulary as the
*source* for this module's own five front-page trust labels, so the two
vocabularies stay consistent rather than diverging), app.services.
chronology's meaningful_stamp/date_label for captured-vs-published
honesty, and app.services.geography_hierarchy's resolve_geography_scope
for region containment (Europe includes Spain; Spain does not include
France).

FIVE ITEM KINDS, FIVE TRUST LABELS

The mission's five front-page item kinds map one-to-one onto its five
required trust labels -- there is no additional classification to invent:

    publication_fresh    -> "FRESH / UNREVIEWED"
    publication_pending  -> "SOURCE-BACKED / AWAITING REVIEW"
    evidence              -> "REVIEWED EVIDENCE"
    signal                 -> "SIGNAL"
    assessment              -> "ASSESSMENT"

The publication_fresh/publication_pending split uses the *already
present* source_completeness.class field (schemas/evidence.schema.json):
a draft with real substantive content (FULL_ARTICLE, FULL_TRANSCRIPT, or
STRUCTURED_REGISTRY) is "source-backed" and sitting in the analyst review
queue; anything thinner (THIN_DESCRIPTION, NO_CONTENT, or the field
absent because the pipeline hasn't finished processing it yet) is "fresh
/ unreviewed" -- newly collected, not yet substantively captured. This is
a deterministic, already-modeled field, not an invented confidence score.

RANKING (TOP STORIES)

No opaque numeric importance score. The sort key is an explainable tuple,
most-significant factor first, documented here so the ordering can be
read off the code:

    1. recency band rank        (today > last_3_days > last_7_days > last_14_days > older)
    2. already has a Signal/Assessment layered on top of it (a more developed story)
    3. introduces a canonical entity that has no other evidence anywhere in the corpus
    4. number of distinct canonical entities linked (cross-entity relevance)
    5. exact timestamp, as a final tiebreak

DEDUPLICATION

Items are clustered only by two deterministic, non-speculative signals:
a shared normalized source_url, or an explicit evidence_ids link (a
Signal/Assessment pointing at the Evidence it was built from). Within a
cluster, the highest-value representative (Assessment > Signal > Evidence
> pending Publication > fresh Publication) is what Top Stories shows;
the rest of the cluster is available as `underlying` on that item.
Speculative semantic/topical clustering is explicitly out of scope for
V1 -- see docs/v2/TECHNICAL-DEBT-REGISTER.md.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.services.chronology import date_label, meaningful_stamp, parse_stamp
from app.services.evidence_claim_review import trust_tier_label
from app.services.geography_hierarchy import resolve_geography_scope
from app.services.intelligence_feed import MARKET_TAGS, classify_kind, entity_chips
from app.services.today import WORTH_REVISITING_LIMIT, build_today, recency_band

SINCE_YESTERDAY_WINDOW_HOURS = 24

FRONT_TRUST_LABELS: dict[str, str] = {
    "publication_fresh": "FRESH / UNREVIEWED",
    "publication_pending": "SOURCE-BACKED / AWAITING REVIEW",
    "evidence": "REVIEWED EVIDENCE",
    "signal": "SIGNAL",
    "assessment": "ASSESSMENT",
}

# Representative rank for deduplication -- higher wins the Top Stories slot.
_LAYER_RANK = {
    "publication_fresh": 0,
    "publication_pending": 1,
    "evidence": 2,
    "signal": 3,
    "assessment": 4,
}

_SOURCE_BACKED_COMPLETENESS = {"FULL_ARTICLE", "FULL_TRANSCRIPT", "STRUCTURED_REGISTRY"}

_BAND_RANK = {"today": 3, "last_3_days": 2, "last_7_days": 1, "last_14_days": 0}

REGIONS: dict[str, str] = {
    "geography-americas": "Americas",
    "geography-europe": "Europe",
    "geography-africa": "Africa",
    "geography-apac": "APAC",
}

_RESEARCH_SOURCE_TYPES = {"academic", "government_registry"}


def _publication_front_kind(record: dict[str, Any]) -> str:
    completeness = record.get("source_completeness") or {}
    if completeness.get("class") in _SOURCE_BACKED_COMPLETENESS:
        return "publication_pending"
    return "publication_fresh"


def _normalized_source_key(record: dict[str, Any]) -> str:
    url = str(record.get("source_url") or "").strip().rstrip("/")
    if url:
        return url.split("?", 1)[0].casefold()
    return f"id:{record.get('id')}"


def _geography_ids(record: dict[str, Any]) -> list[str]:
    explicit = [str(v) for v in (record.get("geography_ids") or []) if v]
    from_entities = [
        str(v) for v in (record.get("entity_ids") or []) if str(v).startswith("geography-")
    ]
    seen: list[str] = []
    for value in explicit + from_entities:
        if value not in seen:
            seen.append(value)
    return seen


def _introduces_new_entity(entity_ids: list[str], item_id: str, entity_index: dict[str, dict[str, Any]]) -> bool:
    for entity_id in entity_ids:
        entity = entity_index.get(entity_id)
        if not entity:
            continue
        evidence_ids = entity.get("evidence_ids") or []
        if item_id in evidence_ids and len(evidence_ids) <= 1:
            return True
    return False


def _project(
    record: dict[str, Any],
    *,
    front_kind: str,
    when: datetime | None,
    origin: str,
    href: str,
    summary: str,
    now: datetime,
    entity_index: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    entity_ids = [str(v) for v in (record.get("entity_ids") or []) if v]
    berry_ids = [str(v) for v in (record.get("berry_ids") or record.get("market_ids") or []) if v]
    geography_ids = _geography_ids(record)
    chips = entity_chips(record, entity_index)
    band = recency_band(when, now=now) if when else None
    captured_at = parse_stamp(record.get("captured_date"))
    captured_band = recency_band(captured_at, now=now) if captured_at else None
    trust_label = FRONT_TRUST_LABELS[front_kind]
    if front_kind == "evidence" and record.get("evidence_role") == "publication_artifact":
        # Trusted Evidence Semantics Repair V1: a published Publication
        # with no analyst-approved factual claim is an APPROVED SOURCE,
        # not REVIEWED EVIDENCE -- see evidence_claim_review.py. Legacy
        # evidence_role=None records are untouched (unconditional
        # "REVIEWED EVIDENCE" above), so this narrows, never widens, what
        # counts as reviewed.
        trust_label = trust_tier_label(record)
    return {
        "id": record.get("id"),
        "front_kind": front_kind,
        "trust_label": trust_label,
        "title": record.get("title") or record.get("id"),
        "source_name": record.get("source_name") or "",
        "source_type": record.get("source_type") or "",
        "when": when.isoformat() if when else None,
        "date_basis_label": date_label(origin) if when else "Date unknown",
        "captured_only": origin == "captured",
        "exact_date": when.strftime("%b %d, %Y") if when else "",
        "band": band,
        # Distinct from `band` (world/event recency): how recently the
        # PIPELINE captured this item, regardless of how old the real-world
        # publication date is. A historical-backfill Publication captured
        # today about a 2019 article is not "news" (band stays keyed off
        # published_date, so it never masquerades as Top Stories) but it IS
        # something the review queue just received today -- that is what
        # Emerging/Unreviewed specifically surfaces captured_band for.
        "captured_band": captured_band,
        "berry_ids": berry_ids,
        "geography_ids": geography_ids,
        "entity_ids": entity_ids,
        "entities": chips,
        "tags": [str(t).casefold() for t in (record.get("tags") or [])],
        "summary": summary,
        "href": href,
        "dedup_key": _normalized_source_key(record),
        "introduces_new_entity": _introduces_new_entity(entity_ids, str(record.get("id") or ""), entity_index),
        "media_kind": classify_kind(record),
        "underlying": [],
    }


def _rank_key(item: dict[str, Any]) -> tuple:
    band_rank = _BAND_RANK.get(item.get("band"), -1)
    has_layer = 1 if item.get("underlying") else 0
    new_entity = 1 if item.get("introduces_new_entity") else 0
    entity_count = min(len(item.get("entity_ids") or []), 8)
    return (band_rank, has_layer, new_entity, entity_count, item.get("when") or "")


def _capture_rank_key(item: dict[str, Any]) -> tuple:
    """Emerging/Unreviewed ranks by how recently the pipeline captured an
    item, not by its (possibly old, e.g. historical-backfill) world date --
    that is the whole point of the section."""

    captured_rank = _BAND_RANK.get(item.get("captured_band"), -1)
    return (captured_rank, item.get("when") or "")


def _dedupe(items: list[dict[str, Any]], evidence_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Cluster by shared normalized source_url, or by a Signal/Assessment's
    own evidence_ids pointing at Evidence already in the item set."""

    clusters: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for item in items:
        key = item["dedup_key"]
        if key not in clusters:
            clusters[key] = []
            order.append(key)
        clusters[key].append(item)

    # Fold Signal/Assessment items into the cluster of any Evidence they
    # explicitly cite, using the raw record's evidence_ids (not a
    # semantic guess).
    evidence_key_by_id = {
        item["id"]: item["dedup_key"] for item in items if item["front_kind"] == "evidence"
    }
    merged: dict[str, str] = {}
    for item in items:
        if item["front_kind"] not in {"signal", "assessment"}:
            continue
        record = evidence_by_id.get(item["id"]) or {}
        for cited in record.get("evidence_ids") or []:
            target_key = evidence_key_by_id.get(cited)
            if target_key and target_key != item["dedup_key"]:
                merged[item["dedup_key"]] = target_key
                break

    representatives: list[dict[str, Any]] = []
    for key in order:
        final_key = merged.get(key, key)
        if final_key != key and final_key in clusters:
            clusters[final_key].extend(clusters[key])
            clusters[key] = []

    for key in order:
        members = clusters.get(key) or []
        if not members:
            continue
        members.sort(key=lambda i: _LAYER_RANK.get(i["front_kind"], 0), reverse=True)
        best, rest = members[0], members[1:]
        best = dict(best)
        best["underlying"] = [
            {"id": m["id"], "front_kind": m["front_kind"], "trust_label": m["trust_label"], "href": m["href"]}
            for m in rest
        ]
        representatives.append(best)
    return representatives


def _is_structural_reference(record: dict[str, Any]) -> bool:
    """True for reference/structural Evidence (e.g. the UN M49 geography
    citations) explicitly tagged "structural" -- these back a Relationship
    record, not a competitive-intelligence development, and must never
    occupy a Top Stories slot just because they were captured today.

    Deliberately NOT keyed on priority.reading.level == "none": most of
    the real published Evidence corpus (1143 of 1269 in a full local
    check) carries that same "none" reading level for unrelated reasons
    (bulk import, no analyst triage yet) and would be wrongly hidden from
    the front page if that field were used here."""

    tags = {str(t).casefold() for t in (record.get("tags") or [])}
    return "structural" in tags


def _region_gaps(regions: dict[str, dict[str, Any]], window_label: str) -> list[str]:
    return [
        f"No fresh {label} items in the {window_label}."
        for _key, data in regions.items()
        for label in [data["label"]]
        if not data["rows"]
    ]


def build_front_page(
    *,
    published: list[dict[str, Any]],
    drafts: list[dict[str, Any]],
    signals: list[dict[str, Any]],
    assessments: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    entities: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
    inbox_dir: Path,
    data_dir: Path,
    coverage_watch: dict[str, Any] | None = None,
    berry_id: str = "",
    now: datetime | None = None,
) -> dict[str, Any]:
    instant = (now or datetime.now(UTC)).astimezone(UTC)
    entity_index = {e["id"]: e for e in entities if e.get("id")}
    evidence_by_id = {str(r.get("id")): r for r in published}
    for record in signals:
        evidence_by_id.setdefault(str(record.get("id")), record)
    for record in assessments:
        evidence_by_id.setdefault(str(record.get("id")), record)

    today_page = build_today(
        published=published,
        signals=signals,
        assessments=assessments,
        sources=sources,
        inbox_dir=inbox_dir,
        data_dir=data_dir,
        berry_id=berry_id,
        now=instant,
    )

    items: list[dict[str, Any]] = []

    for record in drafts:
        if record.get("evidence_role") != "publication_artifact":
            continue
        if _is_structural_reference(record):
            continue
        if berry_id and berry_id != "global" and berry_id not in (record.get("berry_ids") or []):
            continue
        when, origin = meaningful_stamp(record)
        items.append(
            _project(
                record,
                front_kind=_publication_front_kind(record),
                when=when,
                origin=origin,
                href=f"/intelligence/{record.get('id')}",
                summary=(record.get("publisher_description") or "")[:400],
                now=instant,
                entity_index=entity_index,
            )
        )

    for record in published:
        if record.get("status") != "published":
            continue
        if _is_structural_reference(record):
            continue
        if berry_id and berry_id != "global" and berry_id not in (record.get("berry_ids") or []):
            continue
        when, origin = meaningful_stamp(record)
        items.append(
            _project(
                record,
                front_kind="evidence",
                when=when,
                origin=origin,
                href=f"/evidence/{record.get('id')}",
                summary=((record.get("card") or {}).get("summary") or record.get("summary") or "")[:400],
                now=instant,
                entity_index=entity_index,
            )
        )

    for record in signals:
        if berry_id and berry_id != "global" and berry_id not in (record.get("berry_ids") or []):
            continue
        when = parse_stamp(record.get("first_seen") or record.get("last_updated"))
        items.append(
            _project(
                record,
                front_kind="signal",
                when=when,
                origin="first_seen",
                href=f"/signals/{record.get('id')}",
                summary=(record.get("observation") or "")[:400],
                now=instant,
                entity_index=entity_index,
            )
        )

    for record in assessments:
        if berry_id and berry_id != "global" and berry_id not in (record.get("berry_ids") or record.get("market_ids") or []):
            continue
        when = parse_stamp(record.get("created_at"))
        items.append(
            _project(
                record,
                front_kind="assessment",
                when=when,
                origin="created_at",
                href=f"/assessments/{record.get('id')}",
                summary=(record.get("rationale") or record.get("why_it_matters") or "")[:400],
                now=instant,
                entity_index=entity_index,
            )
        )

    deduped = _dedupe(items, evidence_by_id)
    # Every section below is scoped to the same 14-day recency window Today
    # already uses (today.py's BANDS) -- "Top Stories" means stories from
    # now, not a backfill of month-old Assessments dressed up as news. An
    # item outside the window simply isn't a front-page candidate; the
    # stale-state message below is how its absence gets explained instead
    # of silently disappearing.
    banded = [i for i in deduped if i["band"]]
    ranked = sorted(banded, key=_rank_key, reverse=True)
    top_stories = ranked[:16]
    stale_reason = None
    if not banded:
        freshness = today_page.get("freshness") or {}
        pending_count = sum(
            1 for i in items if i["front_kind"] in {"publication_fresh", "publication_pending"}
        )
        collection_label = freshness.get("last_collection_label") or "unknown"
        stale_reason = (
            f"No new intelligence in the last {today_page['window_days']} days. "
            f"Last successful collection: {collection_label}. "
            f"{pending_count} Publication draft(s) await review."
        )

    cutoff = instant - timedelta(hours=SINCE_YESTERDAY_WINDOW_HOURS)
    # Ground-truth counts use the full, un-deduplicated item set -- Top
    # Stories collapses a story that produced both a Publication and later
    # an Evidence/Signal into one representative card, but "what changed"
    # and the trust totals below must still count everything that changed.
    since_yesterday = {
        "cutoff": cutoff.isoformat(),
        "window_hours": SINCE_YESTERDAY_WINDOW_HOURS,
        "new_publications": [i for i in items if i["front_kind"].startswith("publication") and i["when"] and i["when"] > cutoff.isoformat()],
        "newly_reviewed_evidence": [i for i in items if i["front_kind"] == "evidence" and i["when"] and i["when"] > cutoff.isoformat()],
        "new_signals": [i for i in items if i["front_kind"] == "signal" and i["when"] and i["when"] > cutoff.isoformat()],
        "new_assessments": [i for i in items if i["front_kind"] == "assessment" and i["when"] and i["when"] > cutoff.isoformat()],
    }
    since_yesterday["total"] = sum(
        len(since_yesterday[key])
        for key in ("new_publications", "newly_reviewed_evidence", "new_signals", "new_assessments")
    )

    by_region: dict[str, dict[str, Any]] = {}
    for geo_id, label in REGIONS.items():
        scope_ids = resolve_geography_scope(geo_id, relationships=relationships).all_ids
        region_items = [
            i for i in banded if set(i["geography_ids"]) & scope_ids or set(i["entity_ids"]) & scope_ids
        ]
        region_items = sorted(region_items, key=_rank_key, reverse=True)[:10]
        by_region[geo_id] = {"label": label, "rows": region_items}
    region_gaps = _region_gaps(by_region, f"last {today_page['window_days']} days")

    by_berry: dict[str, dict[str, Any]] = {}
    from app.main import BERRIES  # local import: avoid a module-load cycle with app.main

    for bid, label in BERRIES.items():
        berry_items = sorted(
            [i for i in banded if bid in i["berry_ids"]], key=_rank_key, reverse=True
        )[:10]
        by_berry[bid] = {"label": label, "rows": berry_items}
    berry_gaps = _region_gaps(by_berry, f"last {today_page['window_days']} days")

    competitor_moves = sorted(
        [i for i in banded if any(chip.get("entity_type") == "company" for chip in i["entities"])],
        key=_rank_key,
        reverse=True,
    )[:12]
    variety_genetics = sorted(
        [
            i
            for i in banded
            if any(chip.get("entity_type") in {"variety", "breeding_program", "trait"} for chip in i["entities"])
        ],
        key=_rank_key,
        reverse=True,
    )[:12]
    market_trade = sorted(
        [i for i in banded if set(i["tags"]) & MARKET_TAGS], key=_rank_key, reverse=True
    )[:12]
    research_regulation = sorted(
        [
            i
            for i in banded
            if i["source_type"] in _RESEARCH_SOURCE_TYPES or i.get("media_kind") == "patent"
        ],
        key=_rank_key,
        reverse=True,
    )[:12]
    # Emerging/Unreviewed surfaces what the pipeline just captured for
    # review, not just what happens to also be recent world news -- a
    # historical-backfill Publication (real article, old published_date,
    # captured today) belongs here even though it correctly never reaches
    # Top Stories/By Region/By Berry (those stay keyed on world recency).
    recently_captured = {
        i["id"]: i
        for i in deduped
        if i["front_kind"].startswith("publication") and i["captured_band"]
    }
    for i in banded:
        if i["front_kind"].startswith("publication"):
            recently_captured.setdefault(i["id"], i)
    emerging_unreviewed = sorted(recently_captured.values(), key=_capture_rank_key, reverse=True)[:16]
    trusted_intelligence = sorted(
        [i for i in banded if i["front_kind"] in {"evidence", "signal", "assessment"}],
        key=_rank_key,
        reverse=True,
    )[:16]

    sections = [
        {"key": "top_stories", "label": "Top Stories", "rows": top_stories},
        {"key": "competitor_moves", "label": "Competitor Moves", "rows": competitor_moves},
        {"key": "variety_genetics", "label": "Variety & Genetics Watch", "rows": variety_genetics},
        {"key": "market_trade", "label": "Market / Supply / Trade", "rows": market_trade},
        {"key": "research_regulation", "label": "Research / Regulation", "rows": research_regulation},
        {"key": "emerging_unreviewed", "label": "Emerging / Unreviewed", "rows": emerging_unreviewed},
        {"key": "trusted_intelligence", "label": "Trusted Intelligence", "rows": trusted_intelligence},
    ]
    sections = [s for s in sections if s["rows"]]

    return {
        "generated_at": instant.isoformat(),
        "berry_id": berry_id,
        "window_days": today_page["window_days"],
        "quiet": not banded and not emerging_unreviewed,
        "stale_reason": stale_reason,
        "top_stories": top_stories,
        "since_yesterday": since_yesterday,
        "by_region": by_region,
        "region_gaps": region_gaps,
        "by_berry": by_berry,
        "berry_gaps": berry_gaps,
        "sections": sections,
        "coverage_watch": coverage_watch,
        "freshness": today_page["freshness"],
        "worth_revisiting": today_page["worth_revisiting"][:WORTH_REVISITING_LIMIT],
        "last_seen_at": today_page["last_seen_at"],
        "item_count": len(items),
        "trust_counts": {
            "publication_fresh": sum(1 for i in items if i["front_kind"] == "publication_fresh"),
            "publication_pending": sum(1 for i in items if i["front_kind"] == "publication_pending"),
            "evidence": sum(1 for i in items if i["front_kind"] == "evidence"),
            "signal": sum(1 for i in items if i["front_kind"] == "signal"),
            "assessment": sum(1 for i in items if i["front_kind"] == "assessment"),
        },
    }
