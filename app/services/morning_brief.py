"""Morning intelligence brief: deterministic attention ranking over existing records.

This is display composition. It does not invent relevance scores, create a
second object store, change trust state, or mark items read when viewed.

Deltas reuse persisted ``meta.brief.last_seen_at`` (and a compact source-state
snapshot in the same object). That is not a new event store.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
import re
from typing import Any

from app.services.analyst_queue import (
    READING_ACTIVE,
    READING_LABELS,
    READING_RESOLVED,
    is_open_signal_alert,
    is_pending_dismissed,
    load_state,
    monitoring_state,
    present_queue_item,
    proposal_state,
    reading_state,
    save_state,
    signal_alert_state,
    MONITORING_ACTIVE,
)
from app.services.draft_attribution import (
    attribute_draft,
    build_attribution_match_index,
    watch_match_quality,
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
from app.services.source_freshness import CURRENT, DUE, FAILING, STALE
from app.services.signal_review import emerging_signals, present_candidates
from app.services.publication_review_workspace import completeness_display_label
from app.services.story_threads import (
    compress_entries,
    group_story_threads,
    threads_by_item_id,
)

BUCKETS = (
    ("top_priority", "Top priority"),
    ("needs_review", "Needs review"),
    ("saved", "Saved for later"),
    ("adjacent", "Adjacent"),
    ("backlog", "Backlog / older"),
)
WATCH_ENTITY_TYPES = {"company", "variety", "geography", "person"}
PENDING_TRIAGE_BUCKETS = (
    ("review_now", "Review now"),
    ("review_soon", "Review soon"),
    ("adjacent", "Adjacent / context"),
    ("likely_ignore", "Likely ignore"),
    ("older_backlog", "Older backlog"),
)
TOP_PER_CLUSTER = 2
TOP_DEVELOPMENTS_LIMIT = 7
NEW_DEVELOPMENTS_LIMIT = 10
IMPORTANT_LIMIT = 7
COMPANY_DELTA_LIMIT = 8
LEGAL_SUFFIX_RE = re.compile(
    r",?\s+(s\.?a\.?|pty ltd|llc|b\.v\.|inc\.?|ltd\.?|gmbh|holdings.*|group.*)$",
    re.IGNORECASE,
)
BERRY_TITLE_TERMS = (
    "blueberry",
    "blueberries",
    "arándano",
    "arandano",
    "strawberry",
    "strawberries",
    "raspberry",
    "raspberries",
    "blackberry",
    "blackberries",
    "berry",
    "berries",
)
DELTA_GROUPS = (
    ("new_discovery", "New discovery"),
    ("new_review_ready", "New review-ready"),
    ("new_trusted", "New trusted intelligence"),
    ("new_signal", "New signal"),
    ("watch_activity", "Watch activity"),
    ("source_change", "Source failure / recovery"),
)


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
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        day = _parse_day(raw)
        return datetime(day.year, day.month, day.day) if day else None


def record_date(record: dict[str, Any]) -> str:
    from app.services.chronology import meaningful_date_text

    return meaningful_date_text(record) or str(
        record.get("published_date") or record.get("captured_date") or ""
    )

def activity_stamp(record: dict[str, Any], *, first_seen_at: str | None = None) -> datetime | None:
    """When this record became visible to the analyst, not merely its story date."""

    extra = _parse_stamp(first_seen_at or str(record.get("first_seen_at") or ""))
    if extra:
        return extra
    stamp = None
    for key in ("captured_date", "reviewed_at", "proposed_at", "updated_at"):
        stamp = _parse_stamp(str(record.get(key) or ""))
        if stamp:
            break
    if stamp is None:
        stamp = _parse_stamp(record_date(record))
    if stamp and stamp.time() == datetime.min.time():
        return datetime.combine(stamp.date(), datetime.max.time().replace(microsecond=0))
    return stamp


def frontier_date(records: list[dict[str, Any]]) -> date:
    days = [_parse_day(record_date(record)) for record in records]
    known = [day for day in days if day]
    return max(known) if known else date.today()


def brief_meta(inbox_dir) -> dict[str, Any]:
    return dict(((load_state(inbox_dir).get("meta") or {}).get("brief") or {}))


def brief_last_seen(inbox_dir) -> str | None:
    value = str(brief_meta(inbox_dir).get("last_seen_at") or "").strip()
    return value or None


def previous_source_states(inbox_dir) -> dict[str, str]:
    raw = brief_meta(inbox_dir).get("source_states") or {}
    if not isinstance(raw, dict):
        return {}
    return {str(key): str(value) for key, value in raw.items() if key and value}


def mark_brief_seen(
    inbox_dir,
    *,
    source_states: dict[str, str] | None = None,
) -> str:
    """Record that the analyst opened the brief. Does not change reading or trust."""

    state = load_state(inbox_dir)
    now = _now()
    brief = dict((state.get("meta") or {}).get("brief") or {})
    brief.update(
        {
            "last_seen_at": now,
            "updated_at": now,
            "action": "viewed",
        }
    )
    if source_states is not None:
        brief["source_states"] = source_states
    state.setdefault("meta", {})["brief"] = brief
    save_state(inbox_dir, state)
    return now


def _priority_level(record: dict[str, Any], dimension: str = "reading") -> str:
    return str(((record.get("priority") or {}).get(dimension) or {}).get("level") or "none")


def _name_needles(entity: dict[str, Any]) -> list[str]:
    names = [str(entity.get("name") or "")]
    names.extend(str(alias) for alias in (entity.get("aliases") or []) if alias)
    names.extend(str(alias) for alias in (entity.get("also_known_as") or []) if alias)
    compact = LEGAL_SUFFIX_RE.sub("", str(entity.get("name") or "")).strip()
    if compact:
        names.append(compact)
    needles: list[str] = []
    seen: set[str] = set()
    for name in names:
        folded = name.casefold().strip()
        if len(folded) < 4 or folded in seen:
            continue
        seen.add(folded)
        needles.append(folded)
    needles.sort(key=len, reverse=True)
    return needles


def title_matched_entities(
    record: dict[str, Any],
    entities: dict[str, dict[str, Any]],
    match_index=None,
) -> list[dict[str, Any]]:
    title = str(record.get("title") or "").casefold()
    if not title:
        return []
    if match_index is not None:
        from app.services.draft_attribution import indexed_title_matched_entity_ids

        return [
            entities[entity_id]
            for entity_id in indexed_title_matched_entity_ids(title, entities, match_index)
            if entity_id in entities
        ]
    hits: list[tuple[int, dict[str, Any]]] = []
    seen: set[str] = set()
    for entity in entities.values():
        if entity.get("entity_type") not in WATCH_ENTITY_TYPES:
            continue
        entity_id = str(entity.get("id") or "")
        if not entity_id or entity_id in seen:
            continue
        for needle in _name_needles(entity):
            if needle in title:
                hits.append((len(needle), entity))
                seen.add(entity_id)
                break
    hits.sort(key=lambda row: row[0], reverse=True)
    return [entity for _length, entity in hits]


def _title_key(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()


def primary_subject(
    record: dict[str, Any],
    entities: dict[str, dict[str, Any]],
    sources: dict[str, dict[str, Any]] | None = None,
    match_index=None,
) -> dict[str, Any] | None:
    """Single presentation subject from deterministic evidence.

    Title company beats newsroom identity. Body-only mentions and stored
    ``entity_ids`` without a title/newsroom hit are not the primary subject.
    Does not use AI suggested entities.
    """

    attribution = attribute_draft(
        record, entities, sources=sources, match_index=match_index, include_body=False
    )
    primary = attribution.get("primary") or {}
    entity_id = str(primary.get("id") or "")
    if not entity_id:
        return None
    return entities.get(entity_id)


def is_berry_relevant(record: dict[str, Any]) -> bool:
    if record.get("relevance_tier") == "adjacent":
        return False
    screening = record.get("relevance_screening") or {}
    if screening.get("decision") == "skip":
        return False
    if record.get("relevance_tier") == "direct":
        return True
    if record.get("berry_ids") or screening.get("likely_berry_ids"):
        return True
    title = str(record.get("title") or "").casefold()
    return any(term in title for term in BERRY_TITLE_TERMS)


def _cluster_key(record: dict[str, Any], entities: dict[str, dict[str, Any]], primary: dict[str, Any] | None) -> str:
    if primary and primary.get("entity_type") == "company":
        return str(primary.get("id") or "")
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
    match_index=None,
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
        subject = primary_subject(record, entities, match_index=match_index)
        if subject and subject.get("entity_type") in WATCH_ENTITY_TYPES:
            ids.add(str(subject.get("id")))
    return ids


def _hot_entity_ids(
    *,
    watch_entities: set[str],
    signals: list[dict[str, Any]],
    drafts: list[dict[str, Any]],
    last_seen: str | None,
    state: dict[str, dict[str, dict[str, Any]]],
    entities: dict[str, dict[str, Any]],
    first_seen_by_discovered: dict[str, str] | None = None,
    sources: dict[str, dict[str, Any]] | None = None,
    match_index=None,
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
        stamp = activity_stamp(
            draft,
            first_seen_at=(first_seen_by_discovered or {}).get(str(draft.get("discovered_item_id") or "")),
        )
        if seen_at and stamp and stamp <= seen_at:
            continue
        subject = primary_subject(draft, entities, sources=sources, match_index=match_index)
        if subject and subject.get("entity_type") == "company" and str(subject.get("id")) in watch_entities:
            hot.add(str(subject.get("id")))
    return hot


def _source_snapshot(freshness_by_source: dict[str, dict[str, Any]]) -> dict[str, str]:
    return {
        str(source_id): str((row or {}).get("state") or "")
        for source_id, row in (freshness_by_source or {}).items()
        if source_id and (row or {}).get("state")
    }


def rank_item(
    record: dict[str, Any],
    *,
    ctx: dict[str, Any],
    compact: bool = False,
) -> dict[str, Any]:
    entities: dict[str, dict[str, Any]] = ctx["entities"]
    state = ctx["state"]
    item_id = str(record.get("id") or "")
    if compact:
        presented = {
            key: record.get(key)
            for key in (
                "id", "title", "headline", "status", "review_state", "evidence_role",
                "source_id", "source_name", "source_type", "intake_type", "monitoring_priority",
                "source_url", "canonical_url", "published_date", "captured_date", "date",
                "berry_ids", "entity_ids", "geography_ids", "evidence_links", "entity_link_suggestions",
                "relevance_tier", "relevance_screening", "priority", "tags", "summary",
                "why_it_matters", "publisher_description", "ai_enrichment", "media_format",
                "_pending_completeness", "_pending_word_count", "_pending_paragraph_count",
                "_pending_language", "_pending_author", "_pending_source_attribution",
            )
            if record.get(key) is not None
        }
        enrichment = record.get("ai_enrichment") or {}
        feed = {
            "relevance_band": _relevance_band(str(enrichment.get("topical_relevance") or "")),
            "tags": enrichment.get("suggested_tags") or record.get("tags") or [],
            "kind": record.get("_pending_kind") or classify_kind(record),
            "source_url": record.get("source_url") or record.get("canonical_url") or "",
            "pending": trust_state(record) in {"pending", "attention", "disputed"},
        }
    else:
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
    today: date = ctx["today"]
    age_days = (frontier - item_day).days if item_day else 999
    calendar_age = (today - item_day).days if item_day else 999
    cutoff: datetime | None = ctx.get("since_cutoff")
    first_seen = (ctx.get("first_seen_by_discovered") or {}).get(str(record.get("discovered_item_id") or ""))
    stamp = activity_stamp(record, first_seen_at=first_seen)
    new_since = bool(cutoff and stamp and stamp > cutoff)
    sources = ctx.get("sources") or {}
    attribution = attribute_draft(
        record, entities, sources=sources, match_index=ctx.get("match_index")
    )
    primary_meta = attribution.get("primary") or {}
    primary_id = str(primary_meta.get("id") or "")
    primary = entities.get(primary_id) if primary_id else None
    if "_pending_title_entity_ids" in record:
        title_hits = [
            entities[str(entity_id)]
            for entity_id in (record.get("_pending_title_entity_ids") or [])
            if str(entity_id) in entities
        ]
    else:
        title_hits = title_matched_entities(record, entities, match_index=ctx.get("match_index"))
    watch_match, watch_entity_id = watch_match_quality(attribution, ctx["watch_entities"])
    chips = entity_chips(record, entities, by_name=ctx.get("entities_by_name"))
    for suggestion in attribution.get("suggested") or []:
        if suggestion.get("id") and suggestion["id"] not in {chip.get("id") for chip in chips}:
            chips.append(
                {
                    "id": suggestion["id"],
                    "name": suggestion.get("name") or suggestion["id"],
                    "entity_type": suggestion.get("entity_type") or "company",
                    "suggested": True,
                    "method": suggestion.get("method") or "",
                }
            )
    companies = [chip for chip in chips if chip.get("entity_type") == "company"]
    varieties = [chip for chip in chips if chip.get("entity_type") == "variety"]
    tags = {str(tag).casefold() for tag in (record.get("tags") or feed.get("tags") or [])}
    source = sources.get(str(record.get("source_id") or "")) or {}
    source_priority = str(source.get("monitoring_priority") or "")
    kind = record.get("_pending_kind") or feed.get("kind") or classify_kind(record)
    trusted_keys = ctx.get("trusted_title_keys") or set()
    title_key = _title_key(str(record.get("title") or ""))
    duplicate_of_trusted = bool(title_key and title_key in trusted_keys and record.get("status") != "published")
    reasons: list[str] = []
    decision_reasons: list[str] = []
    score = 0

    if tier == "adjacent":
        score -= 20
        reasons.append("adjacent intelligence")
    elif tier == "direct":
        score += 14
        reasons.append("direct berry intelligence")
        decision_reasons.append("direct berry intelligence")
    if is_berry_direct(record) and tier != "adjacent":
        score += 8
        if "direct berry intelligence" not in reasons:
            reasons.append("direct berry intelligence")
        if "direct berry intelligence" not in decision_reasons:
            decision_reasons.append("direct berry intelligence")
    if is_berry_relevant(record) and "direct berry intelligence" not in reasons and tier != "adjacent":
        score += 6
        reasons.append("berry-relevant coverage")

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

    watch_name = str((entities.get(watch_entity_id) or {}).get("name") or watch_entity_id or "")
    primary_kind = str((primary or {}).get("entity_type") or (attribution.get("primary") or {}).get("entity_type") or "")
    if watch_match == "primary" and primary_kind == "company":
        score += 40
        reasons.append(f"{watch_name} watch")
        decision_reasons.append("tracked company primary subject")
        decision_reasons.append("active watch")
        if watch_entity_id in ctx["hot_entities"]:
            score += 8
    elif watch_match == "primary" and primary_kind == "variety":
        score += 28
        reasons.append(f"{watch_name} watch")
        decision_reasons.append("active watch")
    elif watch_match == "primary" and primary_kind == "geography":
        score += 12
        reasons.append(f"primary geography watch · {watch_name}")
    elif watch_match == "mention":
        score += 4
        reasons.append(f"mentions watched {watch_name}")

    if new_since:
        score += 16
        reasons.append("new since last check")
    if kind == "article" and calendar_age <= 7 and is_berry_relevant(record):
        score += 28
        reasons.append("current article")
        decision_reasons.append("current article")
    if calendar_age <= 1:
        score += 20
        reasons.append("published today")
    elif calendar_age <= 2:
        score += 16
        reasons.append("published this cycle")
    elif calendar_age <= 7:
        score += 10
        reasons.append("published this week")
    elif calendar_age <= 14:
        score += 4
    elif calendar_age > 400:
        score -= 12

    if trust in {"pending", "attention", "disputed"}:
        score += 18
        reasons.append("needs a trust decision")
    if primary and primary.get("entity_type") == "company":
        score += 8
        reasons.append("linked company")
        if "tracked company primary subject" not in decision_reasons:
            decision_reasons.append("tracked company primary subject")
        if "newsroom" in str(record.get("source_name") or "").casefold():
            score += 6
            reasons.append("company newsroom")
    elif companies:
        score += 3
    if varieties:
        score += 6
        reasons.append("variety / genetics")
    if "registry" in tags and not varieties and kind != "patent":
        score -= 22
        reasons.append("reference register")
    if "tier-1" in tags:
        score += 6
        reasons.append("tier-1 tagged")
    if source_priority == "high":
        score += 10
        reasons.append("high-priority source")
        decision_reasons.append("high-authority source")
    elif source_priority == "medium":
        score += 5
    if tags & MARKET_TAGS:
        score += 4
    if reading == "unread":
        score += 4
    if not is_berry_relevant(record) and kind == "article":
        score -= 24
        reasons.append("generic produce coverage")
    if duplicate_of_trusted:
        score += 10
        reasons.append("unresolved duplicate warning")
        decision_reasons.append("corroborates existing Evidence")
        decision_reasons.append("unresolved duplicate warning")

    cluster = _cluster_key(record, entities, primary)
    primary_chip = None
    if primary:
        primary_chip = {
            "id": str(primary.get("id") or ""),
            "name": str(primary.get("name") or primary.get("id") or ""),
            "entity_type": str(primary.get("entity_type") or "company"),
            "method": str(primary_meta.get("method") or "title_match"),
            "location": str(primary_meta.get("location") or "title"),
        }
    elif primary_meta.get("entity_type") == "market":
        primary_chip = {
            "id": "",
            "name": str(primary_meta.get("name") or "Markets / supply"),
            "entity_type": "market",
            "method": str(primary_meta.get("method") or "market_tag"),
            "location": "tags",
        }
    completeness_class = str(record.get("_pending_completeness") or "")
    if not completeness_class:
        stored = record.get("source_completeness") if isinstance(record.get("source_completeness"), dict) else {}
        completeness_class = str(stored.get("class") or "")
    presented.update(
        {
            "score": score,
            "reasons": reasons,
            "decision_reasons": list(dict.fromkeys(decision_reasons)),
            "why_ranked": ("Because: " + " · ".join(reasons[:4])) if reasons else "Because: tagged for reading",
            "why_decision": (
                "Why this needs your decision: " + " · ".join(dict.fromkeys(decision_reasons))
                if decision_reasons
                else ""
            ),
            "age_days": age_days,
            "calendar_age": calendar_age,
            "new_since_last": new_since,
            "kind": kind,
            "kind_label": feed.get("kind_label"),
            "trust": trust,
            "trust_label": feed.get("trust_label"),
            "relevance_tier": tier,
            "relevance_band": band,
            "tags": list(record.get("tags") or feed.get("tags") or []),
            "entities": chips,
            "companies": companies,
            "primary_subject": primary_chip,
            "attribution_method": str((primary_chip or {}).get("method") or ""),
            "attribution_suggestions": attribution.get("suggested") or [],
            "attribution_mentions": attribution.get("mentions") or [],
            "watch_match": watch_match,
            "watch_match_entity_id": watch_entity_id or "",
            "duplicate_of_trusted": duplicate_of_trusted,
            "title_companies": [
                {
                    "id": str(entity.get("id") or ""),
                    "name": str(entity.get("name") or entity.get("id") or ""),
                    "entity_type": str(entity.get("entity_type") or "company"),
                }
                for entity in title_hits
                if entity.get("entity_type") == "company"
            ],
            "company_href": f"/entities/company/{primary_chip['id']}" if primary_chip and primary_chip.get("entity_type") == "company" and primary_chip.get("id") else (
                f"/entities/company/{companies[0]['id']}" if companies else ""
            ),
            "completeness_class": completeness_class,
            "completeness_label": completeness_display_label(completeness_class) if completeness_class else "",
            "source_attribution_label": record.get("_pending_source_attribution") or "",
            "source_word_count": record.get("_pending_word_count") or 0,
            "source_paragraph_count": record.get("_pending_paragraph_count") or 0,
            "source_language": record.get("_pending_language") or "",
            "cluster": cluster,
            "reading_state": reading,
            "reading_label": READING_LABELS.get(reading, reading),
            "source_url": feed.get("source_url") or record.get("source_url") or record.get("canonical_url") or "",
            "pending": feed.get("pending"),
            "change_label": "",
            "delta_kind": "",
        }
    )
    presented["change_label"] = _delta_label(presented)
    return presented


def _hydrate_pending_previews(
    pending_triage: dict[str, Any],
    *,
    records_by_id: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> None:
    """Build rich single-item cards only after bucket selection and slicing."""

    for bucket in pending_triage.get("buckets") or []:
        hydrated: list[dict[str, Any]] = []
        for item in bucket.get("entries") or []:
            if item.get("is_thread"):
                hydrated.append(item)
                continue
            record = records_by_id.get(str(item.get("id") or ""))
            if record is None:
                hydrated.append(item)
                continue
            full = rank_item(record, ctx=ctx)
            # Bucket assignment may append duplicate/overflow reasons and can
            # adjust score.  Preserve the already-decided compact result.
            for key in (
                "score", "reasons", "decision_reasons", "why_ranked", "why_decision",
                "bucket", "triage_bucket", "delta_kind",
            ):
                if key in item:
                    full[key] = item[key]
            hydrated.append(full)
        bucket["entries"] = hydrated


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
        old = int(item.get("age_days") or 0) > 14 and not item.get("new_since_last")
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


def assign_pending_triage(ranked: list[dict[str, Any]], *, state: dict[str, dict[str, dict[str, Any]]]) -> list[dict[str, Any]]:
    """Deterministic pending buckets. Not an opaque AI score."""

    for item in ranked:
        item_id = str(item.get("id") or "")
        if is_pending_dismissed(item_id, state):
            item["triage_bucket"] = "dismissed"
            continue
        screening = item.get("relevance_screening") or {}
        skip = screening.get("decision") == "skip" or "generic produce coverage" in (item.get("reasons") or [])
        adjacent = item.get("relevance_tier") == "adjacent"
        calendar_age = int(item.get("calendar_age") or 0)
        primary = item.get("primary_subject") or {}
        recent = calendar_age <= 45
        company_or_variety = primary.get("entity_type") in {"company", "variety"} and bool(primary.get("id"))
        company_primary = primary.get("entity_type") == "company" and bool(primary.get("id"))
        geography_primary = primary.get("entity_type") == "geography"
        primary_company_watch = item.get("watch_match") == "primary" and company_primary
        high_value_recent = (
            (company_or_variety and recent)
            or (primary_company_watch and recent)
            or ("high reading priority" in (item.get("reasons") or []) and recent)
            or (item.get("duplicate_of_trusted") and recent)
        )
        berryish = is_berry_relevant(item) or item.get("relevance_tier") == "direct"
        if adjacent and not primary_company_watch:
            item["triage_bucket"] = "adjacent"
        elif calendar_age > 45:
            item["triage_bucket"] = "older_backlog"
        elif skip and not company_primary and not primary_company_watch:
            item["triage_bucket"] = "likely_ignore"
        elif berryish and high_value_recent and not geography_primary:
            item["triage_bucket"] = "review_now"
        elif berryish:
            item["triage_bucket"] = "review_soon"
        else:
            item["triage_bucket"] = "likely_ignore"
        if item["triage_bucket"] == "review_now" and not item.get("why_decision"):
            fallback = [reason for reason in (item.get("reasons") or []) if reason]
            item["why_decision"] = "Why this needs your decision: " + " · ".join(fallback[:4]) if fallback else "Why this needs your decision: pending trust decision"
    cluster_now: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in ranked:
        if item.get("triage_bucket") != "review_now":
            continue
        cluster_now[str(item.get("cluster") or item.get("id") or "")].append(item)
    for items in cluster_now.values():
        def _keep_rank(row: dict[str, Any]) -> tuple[int, int]:
            newsroom = 1 if "newsroom" in str(row.get("source_name") or "").casefold() else 0
            return (newsroom, int(row.get("score") or 0))
        items.sort(key=_keep_rank, reverse=True)
        for extra in items[1:]:
            extra["triage_bucket"] = "review_soon"
            extra["reasons"] = list(extra.get("reasons") or []) + ["similar coverage already ranked"]
            extra["why_ranked"] = "Because: " + " · ".join((extra.get("reasons") or [])[-4:])
    return ranked


def _pending_triage_groups(
    ranked: list[dict[str, Any]],
    threads_by_id: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    by_key: dict[str, list[dict[str, Any]]] = {key: [] for key, _ in PENDING_TRIAGE_BUCKETS}
    dismissed = 0
    for item in ranked:
        key = str(item.get("triage_bucket") or "review_soon")
        if key == "dismissed":
            dismissed += 1
            continue
        by_key.setdefault(key, []).append(item)
    buckets = []
    counts = {"dismissed": dismissed}
    open_total = 0
    occupied: set[str] = set()
    index = threads_by_id or {}
    for key, label in PENDING_TRIAGE_BUCKETS:
        entries = by_key.get(key) or []
        entries.sort(key=lambda row: int(row.get("score") or 0), reverse=True)
        raw_count = len(entries)
        counts[key] = raw_count
        open_total += raw_count
        if key in {"review_now", "review_soon"} and index:
            presented, used = compress_entries(entries, index, occupied_ids=occupied)
            occupied |= used
            preview = presented[:20]
        else:
            presented = entries
            preview = entries[:20]
        story_count = len(presented)
        buckets.append(
            {
                "key": key,
                "label": label,
                "entries": preview,
                "count": raw_count,
                "story_count": story_count,
                "remainder": max(0, len(presented) - len(preview)),
                "allow_bulk_dismiss": key in {"likely_ignore", "older_backlog"},
            }
        )
    counts["total"] = open_total
    return {"counts": counts, "buckets": buckets}


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


def _attribution_companies(item: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    primary = item.get("primary_subject") or {}
    if primary.get("entity_type") == "company" and primary.get("id"):
        rows.append(primary)
        seen.add(str(primary["id"]))
    for company in item.get("title_companies") or []:
        company_id = str(company.get("id") or "")
        if not company_id or company_id in seen:
            continue
        rows.append(company)
        seen.add(company_id)
    return rows


def _company_deltas(ranked: list[dict[str, Any]], *, limit: int = COMPANY_DELTA_LIMIT) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    preferred = [item for item in ranked if item.get("new_since_last") and is_berry_relevant(item)]
    fallback = [
        item
        for item in ranked
        if item not in preferred
        and (
            item.get("bucket") in {"top_priority", "needs_review", "saved"}
            or item.get("triage_bucket") in {"review_now", "review_soon"}
            or item.get("new_since_last")
            or int(item.get("calendar_age") or 0) <= 14
        )
    ]
    for item in preferred + fallback:
        for company in _attribution_companies(item):
            company_id = str(company.get("id") or "")
            if not company_id:
                continue
            if company_id not in grouped:
                grouped[company_id] = {
                    "id": company_id,
                    "name": company.get("name") or company_id,
                    "href": f"/entities/company/{company_id}",
                    "bullets": [],
                    "new_count": 0,
                }
                order.append(company_id)
            bullets = grouped[company_id]["bullets"]
            if any(existing.get("id") == item.get("id") for existing in bullets):
                continue
            bullets.append(
                {
                    "id": item.get("id"),
                    "label": item.get("change_label") or _delta_label(item),
                    "title": item.get("title"),
                    "href": item.get("href"),
                    "source_name": item.get("source_name"),
                    "date": item.get("date"),
                    "new_since_last": bool(item.get("new_since_last")),
                }
            )
            if item.get("new_since_last"):
                grouped[company_id]["new_count"] += 1
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


def _compress_company_deltas(
    deltas: list[dict[str, Any]],
    threads_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    if not threads_by_id:
        return deltas
    for company in deltas:
        bullets = list(company.get("bullets") or [])
        seen: set[str] = set()
        compressed: list[dict[str, Any]] = []
        for bullet in bullets:
            bullet_id = str(bullet.get("id") or "")
            if not bullet_id or bullet_id in seen:
                continue
            thread = threads_by_id.get(bullet_id)
            member_ids = {str(member_id) for member_id in (thread.get("member_ids") if thread else []) or []}
            local = [row for row in bullets if str(row.get("id") or "") in member_ids] if thread else []
            if thread and len(local) > 1:
                compressed.append(
                    {
                        "id": thread.get("id"),
                        "label": f"Developing: {thread.get('title')}",
                        "title": thread.get("title"),
                        "href": thread.get("href"),
                        "source_name": f"{len(local)} sources",
                        "date": thread.get("latest") or thread.get("date"),
                        "new_since_last": any(row.get("new_since_last") for row in local),
                        "is_thread": True,
                    }
                )
                seen |= {str(row.get("id") or "") for row in local}
                continue
            compressed.append(bullet)
            seen.add(bullet_id)
        company["bullets"] = compressed[:4]
        company["count"] = len(compressed)
    return deltas


def _compress_ranked_list(
    entries: list[dict[str, Any]],
    threads_by_id: dict[str, dict[str, Any]],
    *,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    compressed, _ = compress_entries(entries, threads_by_id)
    return compressed[:limit] if limit else compressed


def _compress_watch_activity(
    rows: list[dict[str, Any]],
    threads_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    for bucket in rows:
        raw_entries = list(bucket.get("entries") or [])
        if threads_by_id:
            compressed, _ = compress_entries(raw_entries, threads_by_id)
        else:
            compressed = raw_entries
        story_count = len(compressed)
        item_count = int(bucket.get("item_count") or len(raw_entries))
        emerging_count = int(bucket.get("emerging_signal_count") or 0)
        bucket["story_count"] = story_count
        bucket["entries"] = compressed[:4]
        happened_parts = []
        if emerging_count:
            happened_parts.append(
                f"{emerging_count} emerging signal" + ("" if emerging_count == 1 else "s")
            )
        if story_count:
            noun = "story" if story_count == 1 else "stories"
            happened_parts.append(f"{story_count} developing {noun}")
        if item_count:
            item_noun = "item" if item_count == 1 else "items"
            happened_parts.append(f"{item_count} source {item_noun}")
        if happened_parts:
            bucket["happened"] = " · ".join(happened_parts)
        if story_count and story_count < item_count:
            item_noun = "item" if item_count == 1 else "items"
            bucket["kind_summary"] = f"{item_count} source {item_noun}"
    return rows


def _watch_activity(
    *,
    published: list[dict[str, Any]],
    ranked: list[dict[str, Any]],
    signals: list[dict[str, Any]],
    entities: dict[str, dict[str, Any]],
    state: dict[str, dict[str, dict[str, Any]]],
    last_seen: str | None,
    signal_candidates: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    watch_entities = _watch_entity_ids(published, state, entities)
    if not watch_entities:
        return []
    seen_at = _parse_stamp(last_seen)
    by_entity: dict[str, dict[str, Any]] = {}

    def _bucket_for(entity_id: str) -> dict[str, Any]:
        entity = entities.get(entity_id) or {}
        return by_entity.setdefault(
            entity_id,
            {
                "id": entity_id,
                "name": entity.get("name") or entity_id,
                "entity_type": entity.get("entity_type") or "company",
                "href": f"/entities/{entity.get('entity_type') or 'company'}/{entity_id}",
                "entries": [],
                "signals": [],
                "emerging_signals": [],
            },
        )

    for item in ranked:
        if item.get("bucket") == "backlog" and not item.get("new_since_last"):
            continue
        if item.get("watch_match") != "primary":
            continue
        primary = item.get("primary_subject") or {}
        entity_id = str(primary.get("id") or "")
        if entity_id and entity_id in watch_entities:
            bucket = _bucket_for(entity_id)
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
            bucket = _bucket_for(str(entity_id))
            bucket["signals"].append(
                {
                    "id": signal.get("id"),
                    "title": signal.get("title"),
                    "href": f"/signals/{signal.get('id')}",
                    "kind_label": "signal",
                }
            )
    for candidate in signal_candidates or []:
        if not candidate.get("is_emerging"):
            continue
        primary = str(candidate.get("primary_entity_id") or "")
        if not primary or primary.startswith("trait-"):
            continue
        entity_ids = {primary}
        for entity_id in entity_ids:
            if entity_id not in watch_entities:
                continue
            bucket = _bucket_for(entity_id)
            if candidate.get("id") in {row.get("id") for row in bucket["emerging_signals"]}:
                continue
            bucket["emerging_signals"].append(
                {
                    "id": candidate.get("id"),
                    "title": candidate.get("label") or candidate.get("reason"),
                    "href": candidate.get("href"),
                    "kind_label": "emerging signal",
                    "support_label": candidate.get("support_label"),
                }
            )
    rows = []
    for bucket in by_entity.values():
        item_count = len(bucket["entries"])
        signal_count = len(bucket["signals"])
        emerging_count = len(bucket["emerging_signals"])
        if item_count == 0 and signal_count == 0 and emerging_count == 0:
            continue
        kind_counts = Counter(str(item.get("kind_label") or item.get("kind") or "item") for item in bucket["entries"])
        kind_bits = [f"{count} {label.lower()}" for label, count in kind_counts.most_common(3)]
        if emerging_count:
            kind_bits.append(f"{emerging_count} emerging signal" + ("" if emerging_count == 1 else "s"))
        if signal_count:
            kind_bits.append(f"{signal_count} patent signal" if signal_count == 1 else f"{signal_count} signals")
        if last_seen:
            signal_label = f"{signal_count} new signal{'s' if signal_count != 1 else ''} since last check"
        else:
            signal_label = f"{signal_count} open signal{'s' if signal_count != 1 else ''}"
        new_items = sum(1 for item in bucket["entries"] if item.get("new_since_last"))
        bucket["item_count"] = item_count
        bucket["signal_count"] = signal_count
        bucket["emerging_signal_count"] = emerging_count
        bucket["new_item_count"] = new_items
        bucket["signal_label"] = signal_label
        bucket["kind_summary"] = " · ".join(kind_bits) if kind_bits else f"{item_count} current item{'s' if item_count != 1 else ''}"
        bucket["happened"] = (
            f"{new_items} new item{'s' if new_items != 1 else ''}"
            if last_seen
            else f"{item_count} current item{'s' if item_count != 1 else ''}"
        )
        bucket["entries"] = bucket["entries"][:8]
        rows.append(bucket)
    rows.sort(key=lambda row: (row["new_item_count"], row["signal_count"], row["item_count"]), reverse=True)
    return rows[:8]


def _section_items(ranked: list[dict[str, Any]], predicate) -> list[dict[str, Any]]:
    return [item for item in ranked if predicate(item)][:8]


def _present_discovered(
    record: dict[str, Any],
    *,
    ctx: dict[str, Any],
    draft: dict[str, Any] | None,
) -> dict[str, Any]:
    source = ctx["sources"].get(str(record.get("source_id") or "")) or {}
    attribution = attribute_draft(
        record,
        ctx["entities"],
        sources=ctx.get("sources") or {},
        match_index=ctx.get("match_index"),
    )
    title_hits = title_matched_entities(record, ctx["entities"], match_index=ctx.get("match_index"))
    primary = primary_subject(
        record, ctx["entities"], sources=ctx.get("sources") or {}, match_index=ctx.get("match_index")
    )
    screening = record.get("relevance_screening") or {}
    href = f"/intelligence/{draft['id']}" if draft else (record.get("canonical_url") or record.get("source_url") or "/work-queue?filter=articles")
    date_value = record.get("published_date") or record.get("first_seen_at") or ""
    item = {
        "id": record.get("id"),
        "title": record.get("title") or record.get("id"),
        "href": href,
        "source_name": source.get("label") or record.get("source_name") or record.get("source_id") or "",
        "source_id": record.get("source_id"),
        "source_url": record.get("canonical_url") or record.get("source_url") or "",
        "date": str(date_value)[:10],
        "kind": "article" if record.get("media_format") == "web_article" else classify_kind(record),
        "kind_label": "Article" if record.get("media_format") == "web_article" else "Discovery",
        "trust": "pending",
        "trust_label": "Pending",
        "status": "discovered",
        "relevance_tier": screening.get("relevance_tier") or record.get("relevance_tier"),
        "new_since_last": True,
        "why": screening.get("reason") or record.get("description") or "",
        "why_ranked": "Because: new staged discovery since last check",
        "change_label": "new staged discovery",
        "delta_kind": "new_discovery",
        "entities": [],
        "companies": [],
        "title_companies": [
            {
                "id": str(entity.get("id") or ""),
                "name": str(entity.get("name") or entity.get("id") or ""),
                "entity_type": str(entity.get("entity_type") or "company"),
            }
            for entity in title_hits
            if entity.get("entity_type") == "company"
        ],
        "primary_subject": {
            "id": str(primary.get("id") or ""),
            "name": str(primary.get("name") or primary.get("id") or ""),
            "entity_type": str(primary.get("entity_type") or "company"),
            "method": str((attribution.get("primary") or {}).get("method") or "title_match"),
        }
        if primary
        else None,
        "attribution_method": str((attribution.get("primary") or {}).get("method") or ""),
        "watch_match": watch_match_quality(attribution, ctx.get("watch_entities") or set())[0],
        "score": 40 if is_berry_relevant(record) else 8,
        "is_active": False,
        "needs_consume": False,
        "pending": True,
        "bucket": "needs_review",
        "reading_label": "",
        "tags": [],
        "discovered": True,
    }
    if item["primary_subject"] and item["primary_subject"].get("entity_type") == "company":
        item["company_href"] = f"/entities/company/{item['primary_subject']['id']}"
    else:
        item["company_href"] = ""
    if is_berry_relevant(record):
        item["why_ranked"] = "Because: new berry-relevant discovery since last check"
        item["change_label"] = "new berry coverage"
    return item


def _source_deltas(
    *,
    freshness_by_source: dict[str, dict[str, Any]],
    previous_states: dict[str, str],
    discovered: list[dict[str, Any]],
    sources: dict[str, dict[str, Any]],
    cutoff: datetime | None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    new_by_source: dict[str, int] = defaultdict(int)
    berry_by_source: dict[str, int] = defaultdict(int)
    for item in discovered:
        stamp = activity_stamp(item) or _parse_stamp(str(item.get("first_seen_at") or ""))
        if cutoff and stamp and stamp <= cutoff:
            continue
        if cutoff and not stamp:
            continue
        if not cutoff:
            continue
        source_id = str(item.get("source_id") or "")
        if not source_id:
            continue
        new_by_source[source_id] += 1
        if is_berry_relevant(item):
            berry_by_source[source_id] += 1

    seen_ids: set[str] = set()
    for source_id, freshness in (freshness_by_source or {}).items():
        now_state = str((freshness or {}).get("state") or "")
        prev = previous_states.get(source_id)
        label = str((sources.get(source_id) or {}).get("label") or source_id)
        href = "/sources"
        if prev == FAILING and now_state in {CURRENT, DUE}:
            rows.append({"id": source_id, "name": label, "href": href, "label": f"{label} recovered", "kind": "recovery"})
            seen_ids.add(source_id)
        elif now_state == FAILING and prev != FAILING:
            if prev is None and not previous_states:
                rows.append({"id": source_id, "name": label, "href": href, "label": f"{label} blocked / failing", "kind": "failure"})
                seen_ids.add(source_id)
            elif prev and prev != FAILING:
                rows.append({"id": source_id, "name": label, "href": href, "label": f"{label} blocked / failing", "kind": "failure"})
                seen_ids.add(source_id)
        elif prev in {STALE, FAILING} and now_state == CURRENT:
            if source_id not in seen_ids:
                rows.append({"id": source_id, "name": label, "href": href, "label": f"{label} recovered", "kind": "recovery"})
                seen_ids.add(source_id)

    produced = []
    for source_id, count in sorted(new_by_source.items(), key=lambda row: row[1], reverse=True):
        if count < 1:
            continue
        label = str((sources.get(source_id) or {}).get("label") or source_id)
        berry = berry_by_source.get(source_id) or 0
        detail = f"{label} produced {count} new item{'s' if count != 1 else ''}"
        if berry and berry != count:
            detail += f" ({berry} berry-relevant)"
        produced.append(
            {
                "id": source_id,
                "name": label,
                "href": "/work-queue?filter=articles",
                "label": detail,
                "kind": "produced",
                "count": count,
            }
        )
    rows.extend(produced[:6])
    return rows[:8]


def _trust_transitions(
    *,
    published: list[dict[str, Any]],
    signals: list[dict[str, Any]],
    recommendations: list[dict[str, Any]],
    state: dict[str, dict[str, dict[str, Any]]],
    cutoff: datetime | None,
    entities: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    if not cutoff:
        return []
    rows: list[dict[str, Any]] = []
    for record in published:
        reviewed = _parse_stamp(str(record.get("reviewed_at") or ""))
        if not reviewed or reviewed <= cutoff:
            continue
        if record.get("status") != "published":
            continue
        rows.append(
            {
                "id": record.get("id"),
                "title": record.get("title") or record.get("id"),
                "href": f"/intelligence/{record.get('id')}",
                "label": "Pending → trusted",
                "detail": record.get("source_name") or "",
            }
        )
    for signal in signals:
        entry = (state.get("signals") or {}).get(str(signal.get("id") or "")) or {}
        stamp = _parse_stamp(str(entry.get("updated_at") or ""))
        alert_state = signal_alert_state(str(signal.get("id") or ""), state)
        if not stamp or stamp <= cutoff:
            continue
        if alert_state == "confirmed":
            rows.append(
                {
                    "id": signal.get("id"),
                    "title": signal.get("title") or signal.get("id"),
                    "href": f"/signals/{signal.get('id')}",
                    "label": "Proposed signal → confirmed",
                    "detail": "",
                }
            )
        elif alert_state == "dismissed":
            rows.append(
                {
                    "id": signal.get("id"),
                    "title": signal.get("title") or signal.get("id"),
                    "href": f"/signals/{signal.get('id')}",
                    "label": "Proposed signal → dismissed",
                    "detail": "",
                }
            )
    for record in recommendations:
        item_id = str(record.get("id") or "")
        entry = (state.get("proposals") or {}).get(item_id) or {}
        stamp = _parse_stamp(str(entry.get("updated_at") or ""))
        if not stamp or stamp <= cutoff:
            continue
        status = proposal_state(item_id, state)
        if status == "accepted":
            rows.append(
                {
                    "id": item_id,
                    "title": record.get("title") or item_id,
                    "href": f"/recommendations/{item_id}",
                    "label": "Position proposal → accepted",
                    "detail": "",
                }
            )
        elif status == "rejected":
            rows.append(
                {
                    "id": item_id,
                    "title": record.get("title") or item_id,
                    "href": f"/recommendations/{item_id}",
                    "label": "Position proposal → rejected",
                    "detail": "",
                }
            )
    return rows[:8]


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
    freshness_by_source: dict[str, dict[str, Any]] | None = None,
    discovered: list[dict[str, Any]] | None = None,
    recommendations: list[dict[str, Any]] | None = None,
    mark_seen: bool = False,
    include_signal_candidates: bool = True,
    mode: str = "full",
) -> dict[str, Any]:
    entity_index = entities or {}
    signal_rows = signals or []
    draft_rows = [
        draft
        for draft in (drafts or [])
        if draft.get("evidence_role") != "atomic_evidence" and draft.get("status", "draft") != "rejected"
    ]
    extra_pending = list(unvalidated or [])
    discovered_rows = [
        item
        for item in (discovered or [])
        if item.get("record_type") == "discovered_media_item" or item.get("media_format") or item.get("first_seen_at")
    ]
    state = load_state(inbox_dir)
    last_seen = brief_last_seen(inbox_dir)
    prior_source_states = previous_source_states(inbox_dir)
    today = date.today()
    if last_seen:
        since_cutoff = _parse_stamp(last_seen)
    else:
        since_cutoff = datetime.combine(today - timedelta(days=1), datetime.min.time())
    reading_records = [
        record
        for record in published
        if _priority_level(record, "reading") != "none"
    ]
    pending_pool = draft_rows + extra_pending
    universe = reading_records + pending_pool
    frontier = frontier_date(universe or published)
    match_index = build_attribution_match_index(entity_index) if entity_index else None
    watch_entities = _watch_entity_ids(published, state, entity_index, match_index=match_index)
    first_seen_by_discovered = {
        str(item.get("id")): str(item.get("first_seen_at") or "")
        for item in discovered_rows
        if item.get("id") and item.get("first_seen_at")
    }
    source_index = {str(source.get("id")): source for source in (sources or []) if source.get("id")}
    hot_entities = _hot_entity_ids(
        watch_entities=watch_entities,
        signals=signal_rows,
        drafts=pending_pool,
        last_seen=last_seen,
        state=state,
        entities=entity_index,
        first_seen_by_discovered=first_seen_by_discovered,
        sources=source_index,
        match_index=match_index,
    )
    trusted_title_keys = {
        _title_key(str(record.get("title") or ""))
        for record in published
        if record.get("status") == "published" and record.get("title")
    }
    ctx = {
        "entities": entity_index,
        "entities_by_name": {
            str(entity.get("name") or "").casefold(): entity
            for entity in entity_index.values()
            if entity.get("name")
        },
        "berry_labels": berry_labels or {},
        "state": state,
        "signals": signal_rows,
        "sources": source_index,
        "frontier": frontier,
        "today": today,
        "last_seen": last_seen,
        "since_cutoff": since_cutoff,
        "watch_entities": watch_entities,
        "hot_entities": hot_entities,
        "first_seen_by_discovered": first_seen_by_discovered,
        "trusted_title_keys": trusted_title_keys,
        "match_index": match_index,
    }
    ranked_reading: list[dict[str, Any]] = []
    if mode != "pending":
        ranked_reading = assign_buckets(
            sorted(
                [rank_item(record, ctx=ctx) for record in reading_records],
                key=lambda item: int(item.get("score") or 0),
                reverse=True,
            )
        )
    ranked_pending = assign_pending_triage(
        assign_buckets(
            sorted(
                [rank_item(record, ctx=ctx, compact=mode == "pending") for record in pending_pool],
                key=lambda item: int(item.get("score") or 0),
                reverse=True,
            )
        ),
        state=state,
    )
    open_pending = [item for item in ranked_pending if item.get("triage_bucket") != "dismissed"]
    for item in ranked_pending:
        reviewed = _parse_stamp(str(item.get("reviewed_at") or ""))
        if item.get("status") == "published" and item.get("new_since_last") and reviewed and since_cutoff and reviewed > since_cutoff:
            item["delta_kind"] = "new_trusted"
        elif item.get("new_since_last"):
            item["delta_kind"] = "new_review_ready"
    for item in ranked_reading:
        if item.get("new_since_last") and item.get("trust") == "trusted":
            item["delta_kind"] = "new_trusted"
        elif item.get("new_since_last"):
            item["delta_kind"] = "new_review_ready"

    reading_groups = _bucket_groups(ranked_reading)
    counts = {group["key"]: group["count"] for group in reading_groups}
    counts["unresolved"] = sum(1 for item in ranked_reading if item.get("reading_state") in READING_ACTIVE)
    counts["needs_review"] = counts.get("needs_review", 0) + sum(
        1 for item in open_pending if item.get("bucket") == "needs_review"
    )
    counts["new_since_last"] = sum(1 for item in ranked_reading + open_pending if item.get("new_since_last"))

    if mode in {"nav", "pending"}:
        threads_by_id: dict[str, dict[str, Any]] = {}
        if mode == "pending":
            thread_pool = [
                item
                for item in open_pending
                if item.get("triage_bucket") in {"review_now", "review_soon"}
            ]
            pending_threads = group_story_threads(thread_pool)
            threads_by_id = threads_by_item_id(pending_threads)
        pending_triage = _pending_triage_groups(ranked_pending, threads_by_id or None)
        if mode == "pending":
            _hydrate_pending_previews(
                pending_triage,
                records_by_id={str(record.get("id") or ""): record for record in pending_pool if record.get("id")},
                ctx=ctx,
            )
        counts["review_now"] = int(pending_triage["counts"].get("review_now") or 0)
        counts["pending_open"] = int(pending_triage["counts"].get("total") or 0)
        counts["brief_action"] = int(counts.get("top_priority") or 0)
        counts["emerging_signals"] = 0
        if include_signal_candidates:
            evidence_by_id = {
                str(record.get("id")): record
                for record in list(published) + list(draft_rows) + list(extra_pending)
                if record.get("id")
            }
            candidate_cards = present_candidates(
                inbox_dir,
                evidence_by_id=evidence_by_id,
                entities=entity_index,
                watch_entities=watch_entities,
            )
            counts["emerging_signals"] = len(emerging_signals(candidate_cards))
        return {
            "generated_at": _now(),
            "last_seen_at": last_seen,
            "frontier": frontier.isoformat(),
            "counts": counts,
            "reading_buckets": reading_groups,
            "pending_triage": pending_triage,
            "emerging_signals": [],
            "story_threads": [],
            "mode": mode,
        }

    draft_by_discovered = {
        str(draft.get("discovered_item_id")): draft
        for draft in draft_rows
        if draft.get("discovered_item_id")
    }
    draft_ids = {str(draft.get("id")) for draft in draft_rows if draft.get("id")}
    new_discoveries: list[dict[str, Any]] = []
    discovery_total = 0
    for item in discovered_rows:
        stamp = activity_stamp(item) or _parse_stamp(str(item.get("first_seen_at") or ""))
        if not (since_cutoff and stamp and stamp > since_cutoff):
            continue
        discovery_total += 1
        linked_draft = draft_by_discovered.get(str(item.get("id") or ""))
        if linked_draft and str(linked_draft.get("id")) in draft_ids:
            continue
        presented = _present_discovered(item, ctx=ctx, draft=linked_draft)
        new_discoveries.append(presented)

    ranked_all = ranked_reading + open_pending
    new_review_ready = [
        item
        for item in open_pending
        if item.get("new_since_last") and item.get("status") != "published"
    ]
    new_trusted = [
        item
        for item in ranked_all
        if item.get("delta_kind") == "new_trusted" or (
            item.get("new_since_last") and item.get("trust") == "trusted" and item.get("status") == "published"
        )
    ]
    new_signals = []
    for signal in signal_rows:
        stamp = _parse_stamp(str(signal.get("proposed_at") or signal.get("created_at") or ""))
        if since_cutoff and stamp and stamp > since_cutoff and is_open_signal_alert(signal, state):
            new_signals.append(
                {
                    "id": signal.get("id"),
                    "title": signal.get("title"),
                    "href": f"/signals/{signal.get('id')}",
                    "date": str(signal.get("proposed_at") or "")[:10],
                    "kind_label": "Signal",
                    "trust_label": "Proposed",
                    "why_ranked": "Because: new proposed signal since last check",
                    "change_label": "new signal",
                    "delta_kind": "new_signal",
                    "source_name": "",
                    "new_since_last": True,
                    "status": "proposed",
                    "is_active": False,
                    "needs_consume": False,
                    "entities": [],
                }
            )

    new_pool = [
        item
        for item in ranked_all
        if item.get("new_since_last") and is_berry_relevant(item) and item.get("relevance_tier") != "adjacent"
        and "generic produce coverage" not in (item.get("reasons") or [])
    ]
    new_pool.sort(key=lambda item: (int(item.get("score") or 0), str(item.get("date") or "")), reverse=True)
    seen_new: set[str] = set()
    new_developments: list[dict[str, Any]] = []
    for item in new_pool:
        item_id = str(item.get("id") or "")
        if not item_id or item_id in seen_new:
            continue
        seen_new.add(item_id)
        new_developments.append(item)
        if len(new_developments) >= NEW_DEVELOPMENTS_LIMIT:
            break

    important = []
    seen_important = {str(item.get("id")) for item in new_developments}
    for item in ranked_reading:
        item_id = str(item.get("id") or "")
        if item_id in seen_important:
            continue
        if item.get("reading_state") not in READING_ACTIVE:
            continue
        if item.get("bucket") in {"top_priority", "saved"} or (
            item.get("bucket") == "backlog" and int(item.get("score") or 0) >= 50
        ):
            important.append(item)
            seen_important.add(item_id)
        if len(important) >= IMPORTANT_LIMIT:
            break

    top = new_developments[:TOP_DEVELOPMENTS_LIMIT] if last_seen and new_developments else [
        item for item in ranked_reading if item.get("bucket") == "top_priority"
    ][:TOP_DEVELOPMENTS_LIMIT]
    if len(top) < 3:
        extra = [item for item in open_pending if item.get("triage_bucket") == "review_now"]
        top = (top + extra)[:TOP_DEVELOPMENTS_LIMIT]

    genetics = _section_items(
        ranked_reading + open_pending,
        lambda item: item.get("kind") == "patent" or any(chip.get("entity_type") == "variety" for chip in (item.get("entities") or [])),
    )
    markets = _section_items(
        ranked_reading + open_pending,
        lambda item: bool({str(tag).casefold() for tag in (item.get("tags") or [])} & MARKET_TAGS),
    )
    story_threads = group_story_threads(ranked_reading + open_pending)
    threads_by_id = threads_by_item_id(story_threads)
    evidence_by_id = {
        str(record.get("id")): record
        for record in list(published) + list(draft_rows) + list(extra_pending)
        if record.get("id")
    }
    candidate_cards: list[dict[str, Any]] = []
    if include_signal_candidates:
        candidate_cards = present_candidates(
            inbox_dir,
            evidence_by_id=evidence_by_id,
            entities=entity_index,
            watch_entities=watch_entities,
        )
    emerging = emerging_signals(candidate_cards)
    counts["emerging_signals"] = len(emerging)
    new_developments = _compress_ranked_list(new_developments, threads_by_id, limit=NEW_DEVELOPMENTS_LIMIT)
    important = _compress_ranked_list(important, threads_by_id, limit=IMPORTANT_LIMIT)
    top = _compress_ranked_list(top, threads_by_id, limit=TOP_DEVELOPMENTS_LIMIT)
    new_review_ready = _compress_ranked_list(new_review_ready, threads_by_id)
    pending_triage = _pending_triage_groups(ranked_pending, threads_by_id)
    needs_decision = next((group["entries"] for group in pending_triage["buckets"] if group["key"] == "review_now"), [])
    counts["review_now"] = pending_triage["counts"].get("review_now", 0)
    counts["pending_open"] = pending_triage["counts"].get("total", 0)
    watch_rows = _compress_watch_activity(
        _watch_activity(
            published=published,
            ranked=ranked_reading + open_pending,
            signals=signal_rows,
            entities=entity_index,
            state=state,
            last_seen=last_seen,
            signal_candidates=candidate_cards,
        ),
        threads_by_id,
    )
    source_changes = _source_deltas(
        freshness_by_source=freshness_by_source or {},
        previous_states=prior_source_states,
        discovered=discovered_rows,
        sources=source_index,
        cutoff=since_cutoff if last_seen else None,
    )
    transitions = _trust_transitions(
        published=published,
        signals=signal_rows,
        recommendations=recommendations or [],
        state=state,
        cutoff=since_cutoff if last_seen else None,
        entities=entity_index,
    )

    berry_discoveries = [
        item
        for item in new_discoveries
        if "berry-relevant" in str(item.get("why_ranked") or "").casefold()
        or is_berry_relevant({"title": item.get("title"), "relevance_tier": item.get("relevance_tier")})
    ]

    since_groups = [
        {
            "key": "new_discovery",
            "label": "New discovery",
            "count": discovery_total,
            "entries": berry_discoveries[:8],
            "remainder": max(0, discovery_total - len(berry_discoveries[:8])),
        },
        {
            "key": "new_review_ready",
            "label": "New review-ready",
            "count": len(new_review_ready),
            "entries": new_review_ready[:8],
            "remainder": max(0, len(new_review_ready) - 8),
        },
        {
            "key": "new_trusted",
            "label": "New trusted intelligence",
            "count": len(new_trusted),
            "entries": new_trusted[:8],
            "remainder": max(0, len(new_trusted) - 8),
        },
        {
            "key": "new_signal",
            "label": "New signal",
            "count": len(new_signals),
            "entries": new_signals[:8],
            "remainder": 0,
        },
        {
            "key": "watch_activity",
            "label": "Watch activity",
            "count": sum(
                1
                for row in watch_rows
                if row.get("new_item_count") or row.get("signal_count") or row.get("emerging_signal_count")
            ),
            "entries": [],
            "remainder": 0,
        },
        {
            "key": "source_change",
            "label": "Source failure / recovery",
            "count": len(source_changes),
            "entries": [],
            "remainder": 0,
        },
    ]
    since_counts = {group["key"]: group["count"] for group in since_groups}
    since_counts["total"] = (
        since_counts["new_discovery"]
        + since_counts["new_review_ready"]
        + since_counts["new_trusted"]
        + since_counts["new_signal"]
        + since_counts["source_change"]
    )
    counts["since_last"] = since_counts["total"]
    counts["new_developments"] = len(new_developments)
    counts["important"] = len(important)
    counts["discovery_total"] = discovery_total

    snapshot = _source_snapshot(freshness_by_source or {})
    if mark_seen:
        mark_brief_seen(inbox_dir, source_states=snapshot or None)
    return {
        "generated_at": _now(),
        "last_seen_at": last_seen,
        "frontier": frontier.isoformat(),
        "counts": counts,
        "reading_buckets": reading_groups,
        "top_developments": top,
        "new_developments": new_developments,
        "important": important,
        "watch_activity": watch_rows,
        "emerging_signals": emerging,
        "company_deltas": _compress_company_deltas(
            _company_deltas(ranked_reading + open_pending),
            threads_by_id,
        ),
        "story_threads": story_threads,
        "genetics": genetics,
        "markets": markets,
        "needs_decision": needs_decision,
        "pending_triage": pending_triage,
        "source_coverage": source_coverage or {},
        "source_changes": source_changes,
        "trust_transitions": transitions,
        "since_last": {
            "last_seen_at": last_seen,
            "cutoff": since_cutoff.isoformat(timespec="seconds") if since_cutoff else None,
            "counts": since_counts,
            "groups": since_groups,
        },
        "unresolved": counts["unresolved"],
    }
