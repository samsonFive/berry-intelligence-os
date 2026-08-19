"""Morning intelligence brief: deterministic attention ranking over existing records.

This is display composition. It does not invent relevance scores, create a
second object store, change trust state, or mark items read when viewed.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from app.services.analyst_queue import (
    READING_ACTIVE,
    READING_LABELS,
    READING_RESOLVED,
    is_open_signal_alert,
    load_state,
    monitoring_state,
    present_queue_item,
    reading_state,
    save_state,
    MONITORING_ACTIVE,
)
from app.services.intelligence_feed import (
    MARKET_TAGS,
    classify_kind,
    entity_chips,
    is_berry_direct,
    present_feed_item,
    trust_state,
)
from app.services.review_workbench import _relevance_band

BUCKETS = (
    ("top_priority", "Top priority"),
    ("needs_review", "Needs review"),
    ("saved", "Saved for later"),
    ("adjacent", "Adjacent"),
    ("backlog", "Backlog / older"),
)
WATCH_ENTITY_TYPES = {"company", "variety", "geography", "person"}
TOP_PER_CLUSTER = 2
TOP_DEVELOPMENTS_LIMIT = 7
COMPANY_DELTA_LIMIT = 8


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _parse_day(value: str | None) -> date | None:
    raw = str(value or "")[:10]
    if len(raw) < 10:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _parse_stamp(value: str | None) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", ""))
    except ValueError:
        day = _parse_day(raw)
        return datetime(day.year, day.month, day.day) if day else None


def record_date(record: dict[str, Any]) -> str:
    return str(record.get("published_date") or record.get("captured_date") or "")


def frontier_date(records: list[dict[str, Any]]) -> date:
    days = [_parse_day(record_date(record)) for record in records]
    known = [day for day in days if day]
    return max(known) if known else date.today()


def brief_last_seen(inbox_dir) -> str | None:
    state = load_state(inbox_dir)
    value = str(((state.get("meta") or {}).get("brief") or {}).get("last_seen_at") or "").strip()
    return value or None


def mark_brief_seen(inbox_dir) -> str:
    """Record that the analyst opened the brief. Does not change reading or trust."""

    state = load_state(inbox_dir)
    now = _now()
    state.setdefault("meta", {})["brief"] = {
        "last_seen_at": now,
        "updated_at": now,
        "action": "viewed",
    }
    save_state(inbox_dir, state)
    return now


def _priority_level(record: dict[str, Any], dimension: str = "reading") -> str:
    return str(((record.get("priority") or {}).get(dimension) or {}).get("level") or "none")


def _cluster_key(record: dict[str, Any], entities: dict[str, dict[str, Any]]) -> str:
    for entity_id in record.get("entity_ids") or []:
        entity = entities.get(entity_id) or {}
        if entity.get("entity_type") == "company":
            return str(entity.get("id") or entity_id)
    title = str(record.get("title") or "").casefold()
    return title[:48] or str(record.get("id") or "")


def _delta_label(item: dict[str, Any]) -> str:
    kind = item.get("kind")
    tags = {str(tag).casefold() for tag in (item.get("tags") or [])}
    if kind == "patent":
        return "new patent activity"
    if tags & MARKET_TAGS:
        return "market / supply coverage"
    if kind == "spoken":
        return "new spoken-media coverage"
    if kind == "article":
        return "new trade coverage"
    why = str(item.get("why") or "").strip()
    if why:
        return why.split(".")[0][:140]
    return str(item.get("title") or "Evidence")[:140]


def _watch_entity_ids(
    published: list[dict[str, Any]],
    state: dict[str, dict[str, dict[str, Any]]],
    entities: dict[str, dict[str, Any]],
) -> set[str]:
    ids: set[str] = set()
    for record in published:
        if _priority_level(record, "monitoring") == "none":
            continue
        if monitoring_state(str(record.get("id") or ""), state) not in MONITORING_ACTIVE:
            continue
        for entity_id in record.get("entity_ids") or []:
            entity = entities.get(entity_id) or {}
            if entity.get("entity_type") in WATCH_ENTITY_TYPES:
                ids.add(str(entity_id))
    return ids


def _hot_entity_ids(
    *,
    watch_entities: set[str],
    signals: list[dict[str, Any]],
    drafts: list[dict[str, Any]],
    last_seen: str | None,
    state: dict[str, dict[str, dict[str, Any]]],
) -> set[str]:
    hot: set[str] = set()
    seen_at = _parse_stamp(last_seen)
    for signal in signals:
        if not is_open_signal_alert(signal, state):
            continue
        for entity_id in signal.get("entity_ids") or []:
            if entity_id in watch_entities:
                hot.add(str(entity_id))
    for draft in drafts:
        stamp = _parse_stamp(record_date(draft) or draft.get("captured_date"))
        if seen_at and stamp and stamp <= seen_at:
            continue
        for entity_id in draft.get("entity_ids") or []:
            if entity_id in watch_entities:
                hot.add(str(entity_id))
    return hot


def rank_item(
    record: dict[str, Any],
    *,
    ctx: dict[str, Any],
) -> dict[str, Any]:
    entities: dict[str, dict[str, Any]] = ctx["entities"]
    state = ctx["state"]
    item_id = str(record.get("id") or "")
    presented = present_queue_item(
        record,
        dimension="reading",
        state=state,
        entities=entities,
        berry_labels=ctx["berry_labels"],
        signals=ctx.get("signals") or [],
    )
    feed = present_feed_item(record, entities=entities, berry_labels=ctx["berry_labels"])
    reading = reading_state(item_id, state)
    trust = trust_state(record)
    tier = record.get("relevance_tier")
    band = feed.get("relevance_band") or _relevance_band(str((record.get("ai_enrichment") or {}).get("topical_relevance") or ""))
    level = _priority_level(record, "reading")
    item_day = _parse_day(record_date(record))
    frontier: date = ctx["frontier"]
    age_days = (frontier - item_day).days if item_day else 999
    last_seen_at = _parse_stamp(ctx.get("last_seen"))
    item_stamp = _parse_stamp(record_date(record))
    new_since = bool(last_seen_at and item_stamp and item_stamp > last_seen_at)
    linked_ids = {str(entity_id) for entity_id in (record.get("entity_ids") or []) if entity_id}
    watch_hit = sorted(linked_ids & ctx["watch_entities"])
    hot_hit = sorted(linked_ids & ctx["hot_entities"])
    chips = entity_chips(record, entities)
    companies = [chip for chip in chips if chip.get("entity_type") == "company"]
    varieties = [chip for chip in chips if chip.get("entity_type") == "variety"]
    tags = {str(tag).casefold() for tag in (record.get("tags") or feed.get("tags") or [])}
    source = ctx["sources"].get(str(record.get("source_id") or "")) or {}
    source_priority = str(source.get("monitoring_priority") or "")
    reasons: list[str] = []
    score = 0

    if tier == "adjacent":
        score -= 20
        reasons.append("adjacent intelligence")
    elif tier == "direct":
        score += 14
        reasons.append("direct berry intelligence")
    if is_berry_direct(record) and tier != "adjacent":
        score += 8
        if "direct berry intelligence" not in reasons:
            reasons.append("direct berry intelligence")

    if level == "high":
        score += 24
        reasons.append("high reading priority")
    elif level == "medium":
        score += 12
        reasons.append("medium reading priority")
    elif level == "low":
        score += 4

    band_score = {"High": 12, "Relevant": 6, "Moderate": 3, "Low": 0}.get(band, 0)
    score += band_score
    if band == "High":
        reasons.append("high relevance")

    if hot_hit:
        score += 36
        names = [str((entities.get(eid) or {}).get("name") or eid) for eid in hot_hit[:2]]
        reasons.append(f"{names[0]} watch" if names else "active watch")
    elif watch_hit and trust != "trusted":
        score += 18
        names = [str((entities.get(eid) or {}).get("name") or eid) for eid in watch_hit[:2]]
        reasons.append(f"{names[0]} watch" if names else "active watch")

    if new_since:
        score += 16
        reasons.append("new since last check")
    if age_days <= 2:
        score += 20
        reasons.append("published this cycle")
    elif age_days <= 7:
        score += 10
        reasons.append("published this week")
    elif age_days <= 14:
        score += 4
    elif age_days > 400:
        score -= 12

    if trust in {"pending", "attention", "disputed"}:
        score += 18
        reasons.append("needs a trust decision")
    if companies:
        score += 8
        reasons.append("linked company")
    if varieties:
        score += 6
        reasons.append("variety / genetics")
    if "registry" in tags and not varieties and feed.get("kind") != "patent":
        score -= 22
        reasons.append("reference register")
    if "tier-1" in tags:
        score += 6
        reasons.append("tier-1 tagged")
    if source_priority == "high":
        score += 10
        reasons.append("high-priority source")
    elif source_priority == "medium":
        score += 5
    if tags & MARKET_TAGS:
        score += 4
    if reading == "unread":
        score += 4

    cluster = _cluster_key(record, entities)
    presented.update(
        {
            "score": score,
            "reasons": reasons,
            "why_ranked": ("Because: " + " · ".join(reasons[:4])) if reasons else "Because: tagged for reading",
            "age_days": age_days,
            "new_since_last": new_since,
            "kind": feed.get("kind"),
            "kind_label": feed.get("kind_label"),
            "trust": trust,
            "trust_label": feed.get("trust_label"),
            "relevance_tier": tier,
            "relevance_band": band,
            "tags": list(record.get("tags") or feed.get("tags") or []),
            "entities": chips,
            "companies": companies,
            "company_href": f"/entities/company/{companies[0]['id']}" if companies else "",
            "cluster": cluster,
            "reading_state": reading,
            "reading_label": READING_LABELS.get(reading, reading),
            "source_url": feed.get("source_url") or record.get("source_url") or "",
            "pending": feed.get("pending"),
        }
    )
    return presented


def assign_buckets(ranked: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Split ranked reading items into attention buckets. Non-destructive."""

    cluster_counts: dict[str, int] = defaultdict(int)
    seen_titles: list[str] = []
    for item in ranked:
        reading = item.get("reading_state")
        trust = item.get("trust")
        if reading in READING_RESOLVED:
            item["bucket"] = "completed"
            continue
        if reading == "saved":
            item["bucket"] = "saved"
            continue
        if item.get("relevance_tier") == "adjacent":
            item["bucket"] = "adjacent"
            continue
        if trust in {"pending", "attention", "disputed"} and item.get("status") != "published":
            item["bucket"] = "needs_review"
            continue
        if reading not in READING_ACTIVE:
            item["bucket"] = "backlog"
            continue
        title_key = str(item.get("title") or "").casefold()[:48]
        redundant = any(title_key and title_key == prior for prior in seen_titles)
        overflow = cluster_counts[str(item.get("cluster") or "")] >= TOP_PER_CLUSTER
        old = int(item.get("age_days") or 0) > 14
        if redundant:
            item["reasons"] = list(item.get("reasons") or []) + ["similar coverage already ranked"]
            item["why_ranked"] = "Because: " + " · ".join(item["reasons"][-4:])
            item["bucket"] = "backlog"
            item["score"] = int(item.get("score") or 0) - 18
        elif old:
            item["bucket"] = "backlog"
        elif overflow:
            item["reasons"] = list(item.get("reasons") or []) + ["other coverage this cycle"]
            item["why_ranked"] = "Because: " + " · ".join((item.get("reasons") or [])[:4])
            item["bucket"] = "backlog"
            item["score"] = int(item.get("score") or 0) - 8
        else:
            item["bucket"] = "top_priority"
            cluster_counts[str(item.get("cluster") or "")] += 1
            if title_key:
                seen_titles.append(title_key)
    return ranked


def _bucket_groups(ranked: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[str, list[dict[str, Any]]] = {key: [] for key, _ in BUCKETS}
    for item in ranked:
        key = str(item.get("bucket") or "backlog")
        by_key.setdefault(key, []).append(item)
    groups = []
    for key, label in BUCKETS:
        items = by_key.get(key) or []
        items.sort(key=lambda row: int(row.get("score") or 0), reverse=True)
        groups.append({"key": key, "label": label, "entries": items, "count": len(items)})
    return groups


def _company_deltas(ranked: list[dict[str, Any]], *, limit: int = COMPANY_DELTA_LIMIT) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for item in ranked:
        if item.get("bucket") not in {"top_priority", "needs_review", "saved"} and not item.get("new_since_last"):
            if int(item.get("age_days") or 0) > 14:
                continue
        for company in item.get("companies") or []:
            company_id = str(company.get("id") or "")
            if not company_id:
                continue
            if company_id not in grouped:
                grouped[company_id] = {
                    "id": company_id,
                    "name": company.get("name") or company_id,
                    "href": f"/entities/company/{company_id}",
                    "bullets": [],
                }
                order.append(company_id)
            bullets = grouped[company_id]["bullets"]
            if any(existing.get("id") == item.get("id") for existing in bullets):
                continue
            bullets.append(
                {
                    "id": item.get("id"),
                    "label": _delta_label(item),
                    "title": item.get("title"),
                    "href": item.get("href"),
                    "source_name": item.get("source_name"),
                    "date": item.get("date"),
                }
            )
    deltas = []
    for company_id in order:
        company = grouped[company_id]
        if not company["bullets"]:
            continue
        company["count"] = len(company["bullets"])
        company["bullets"] = company["bullets"][:4]
        deltas.append(company)
        if len(deltas) >= limit:
            break
    return [row for row in deltas if row["count"] >= 1]


def _watch_activity(
    *,
    published: list[dict[str, Any]],
    ranked: list[dict[str, Any]],
    signals: list[dict[str, Any]],
    entities: dict[str, dict[str, Any]],
    state: dict[str, dict[str, dict[str, Any]]],
    last_seen: str | None,
) -> list[dict[str, Any]]:
    watch_entities = _watch_entity_ids(published, state, entities)
    if not watch_entities:
        return []
    seen_at = _parse_stamp(last_seen)
    by_entity: dict[str, dict[str, Any]] = {}
    for item in ranked:
        if item.get("bucket") == "backlog" and not item.get("new_since_last"):
            continue
        for chip in item.get("entities") or []:
            entity_id = str(chip.get("id") or "")
            if entity_id not in watch_entities:
                continue
            bucket = by_entity.setdefault(
                entity_id,
                {
                    "id": entity_id,
                    "name": chip.get("name") or entity_id,
                    "entity_type": chip.get("entity_type"),
                    "href": f"/entities/{chip.get('entity_type')}/{entity_id}",
                    "entries": [],
                    "signals": [],
                },
            )
            if item.get("id") not in {row.get("id") for row in bucket["entries"]}:
                bucket["entries"].append(item)
    for signal in signals:
        if not is_open_signal_alert(signal, state):
            continue
        stamp = _parse_stamp(str(signal.get("proposed_at") or signal.get("created_at") or ""))
        since = bool(seen_at and stamp and stamp > seen_at) or (seen_at is None)
        if not since and seen_at is not None:
            continue
        for entity_id in signal.get("entity_ids") or []:
            if entity_id not in watch_entities:
                continue
            entity = entities.get(entity_id) or {}
            bucket = by_entity.setdefault(
                str(entity_id),
                {
                    "id": entity_id,
                    "name": entity.get("name") or entity_id,
                    "entity_type": entity.get("entity_type") or "company",
                    "href": f"/entities/{entity.get('entity_type') or 'company'}/{entity_id}",
                    "entries": [],
                    "signals": [],
                },
            )
            bucket["signals"].append(
                {
                    "id": signal.get("id"),
                    "title": signal.get("title"),
                    "href": f"/signals/{signal.get('id')}",
                }
            )
    rows = []
    for bucket in by_entity.values():
        item_count = len(bucket["entries"])
        signal_count = len(bucket["signals"])
        if item_count == 0 and signal_count == 0:
            continue
        if last_seen:
            signal_label = f"{signal_count} new signal{'s' if signal_count != 1 else ''} since last check"
        else:
            signal_label = f"{signal_count} open signal{'s' if signal_count != 1 else ''}"
        bucket["item_count"] = item_count
        bucket["signal_count"] = signal_count
        bucket["signal_label"] = signal_label
        bucket["entries"] = bucket["entries"][:4]
        rows.append(bucket)
    rows.sort(key=lambda row: (row["signal_count"], row["item_count"]), reverse=True)
    return rows[:8]


def _section_items(ranked: list[dict[str, Any]], predicate) -> list[dict[str, Any]]:
    return [item for item in ranked if predicate(item)][:8]


def build_morning_brief(
    *,
    inbox_dir,
    published: list[dict[str, Any]],
    drafts: list[dict[str, Any]] | None = None,
    unvalidated: list[dict[str, Any]] | None = None,
    signals: list[dict[str, Any]] | None = None,
    entities: dict[str, dict[str, Any]] | None = None,
    sources: list[dict[str, Any]] | None = None,
    berry_labels: dict[str, str] | None = None,
    source_coverage: dict[str, Any] | None = None,
    mark_seen: bool = False,
) -> dict[str, Any]:
    entity_index = entities or {}
    signal_rows = signals or []
    draft_rows = [
        draft
        for draft in (drafts or [])
        if draft.get("evidence_role") != "atomic_evidence" and draft.get("status", "draft") != "rejected"
    ]
    extra_pending = list(unvalidated or [])
    state = load_state(inbox_dir)
    last_seen = brief_last_seen(inbox_dir)
    reading_records = [
        record
        for record in published
        if _priority_level(record, "reading") != "none"
    ]
    pending_pool = draft_rows + extra_pending
    universe = reading_records + pending_pool
    frontier = frontier_date(universe or published)
    watch_entities = _watch_entity_ids(published, state, entity_index)
    hot_entities = _hot_entity_ids(
        watch_entities=watch_entities,
        signals=signal_rows,
        drafts=pending_pool,
        last_seen=last_seen,
        state=state,
    )
    ctx = {
        "entities": entity_index,
        "berry_labels": berry_labels or {},
        "state": state,
        "signals": signal_rows,
        "sources": {str(source.get("id")): source for source in (sources or []) if source.get("id")},
        "frontier": frontier,
        "last_seen": last_seen,
        "watch_entities": watch_entities,
        "hot_entities": hot_entities,
    }
    ranked_reading = assign_buckets(
        sorted(
            [rank_item(record, ctx=ctx) for record in reading_records],
            key=lambda item: int(item.get("score") or 0),
            reverse=True,
        )
    )
    ranked_pending = assign_buckets(
        sorted(
            [rank_item(record, ctx=ctx) for record in pending_pool],
            key=lambda item: int(item.get("score") or 0),
            reverse=True,
        )
    )
    reading_groups = _bucket_groups(ranked_reading)
    counts = {group["key"]: group["count"] for group in reading_groups}
    counts["unresolved"] = sum(1 for item in ranked_reading if item.get("reading_state") in READING_ACTIVE)
    counts["needs_review"] = counts.get("needs_review", 0) + sum(
        1 for item in ranked_pending if item.get("bucket") == "needs_review"
    )
    counts["new_since_last"] = sum(1 for item in ranked_reading if item.get("new_since_last"))
    top = [item for item in ranked_reading if item.get("bucket") == "top_priority"][:TOP_DEVELOPMENTS_LIMIT]
    if len(top) < 3:
        extra = [item for item in ranked_pending if item.get("bucket") == "needs_review"]
        top = (top + extra)[:TOP_DEVELOPMENTS_LIMIT]
    genetics = _section_items(
        ranked_reading + ranked_pending,
        lambda item: item.get("kind") == "patent" or any(chip.get("entity_type") == "variety" for chip in (item.get("entities") or [])),
    )
    markets = _section_items(
        ranked_reading + ranked_pending,
        lambda item: bool({str(tag).casefold() for tag in (item.get("tags") or [])} & MARKET_TAGS),
    )
    needs_decision = [item for item in ranked_pending if item.get("bucket") == "needs_review"][:10]
    watch_rows = _watch_activity(
        published=published,
        ranked=ranked_reading + ranked_pending,
        signals=signal_rows,
        entities=entity_index,
        state=state,
        last_seen=last_seen,
    )
    if mark_seen:
        mark_brief_seen(inbox_dir)
    return {
        "generated_at": _now(),
        "last_seen_at": last_seen,
        "frontier": frontier.isoformat(),
        "counts": counts,
        "reading_buckets": reading_groups,
        "top_developments": top,
        "watch_activity": watch_rows,
        "company_deltas": _company_deltas(ranked_reading + ranked_pending),
        "genetics": genetics,
        "markets": markets,
        "needs_decision": needs_decision,
        "source_coverage": source_coverage or {},
        "unresolved": counts["unresolved"],
    }
