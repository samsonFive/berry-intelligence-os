"""Cheap, read-only review-capacity economics and backpressure simulation.

The report deliberately separates recorded human decisions from operational
queue measurements and from simulated policy effects. It never mutates a
draft, changes trust, or treats an unreviewed draft as useful/kept evidence.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timezone
import json
from pathlib import Path
from statistics import median
from typing import Any, Iterable

from app.services.article_dedup import normalize_canonical_url, normalize_title
from app.services.review_events import MINIMUM_RATE_SAMPLE, review_event_analytics


UTC = timezone.utc
BACKLOG_THRESHOLDS = {"warning": 750, "high": 1000, "critical": 1500}
AGE_BUCKETS = ((1, "0_1_days"), (7, "2_7_days"), (30, "8_30_days"), (45, "31_45_days"))


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def load_json_objects(folder: Path, *, recursive: bool = False) -> list[dict[str, Any]]:
    pattern = "**/*.json" if recursive else "*.json"
    return [payload for path in sorted(folder.glob(pattern)) if (payload := _load_json(path)) is not None]


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        try:
            parsed = datetime.combine(date.fromisoformat(text[:10]), datetime.min.time())
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _queue_stamp(record: dict[str, Any]) -> datetime | None:
    provenance = record.get("discovery_provenance") or {}
    for value in (
        provenance.get("first_seen_at"),
        record.get("created_at"),
        record.get("captured_date"),
        record.get("published_date"),
    ):
        if parsed := _parse_datetime(value):
            return parsed
    return None


def _queue_age_days(record: dict[str, Any], now: datetime) -> int | None:
    stamp = _queue_stamp(record)
    return max(0, (now.date() - stamp.date()).days) if stamp else None


def _event_age_days(record: dict[str, Any], now: datetime) -> int | None:
    stamp = _parse_datetime(record.get("published_date"))
    return max(0, (now.date() - stamp.date()).days) if stamp else None


def _age_bucket(age: int | None) -> str:
    if age is None:
        return "unknown"
    for maximum, label in AGE_BUCKETS:
        if age <= maximum:
            return label
    return "over_45_days"


def _source_class(source: dict[str, Any]) -> str:
    adapter = str((source.get("discovery") or {}).get("adapter") or "")
    if adapter.startswith("government_"):
        return "government_regulatory"
    if adapter == "news_search_rss":
        return "news_search"
    if adapter == "article_rss":
        return "publisher_rss"
    if adapter in {"podcast_rss", "youtube_feed"}:
        return "spoken_media"
    entity_types = [str(value) for value in (source.get("entity_types") or []) if value]
    return entity_types[0] if entity_types else str(source.get("type") or "unknown")


def _query_family(source: dict[str, Any]) -> str:
    return str((source.get("discovery") or {}).get("adapter") or "manual_or_unconfigured")


def _access_limitation(record: dict[str, Any], source: dict[str, Any]) -> str:
    adapter = _query_family(source)
    article = record.get("article") or {}
    final_url = str(article.get("final_url") or "")
    source_url = str(record.get("source_url") or "")
    if adapter == "news_search_rss" and (
        "consent.google.com" in final_url or "news.google.com/rss/articles" in source_url
    ):
        return "google_news_body_unverifiable"
    if record.get("media_format") in {"podcast", "video", "conference_video"}:
        transcript = record.get("transcript") or {}
        if transcript.get("status") not in {"ready", "available", "complete"}:
            return "transcript_unavailable"
    if record.get("media_format") == "web_article" and not (article.get("paragraphs") or []):
        return "article_body_unavailable"
    return "none_observed"


def _cluster_key(record: dict[str, Any]) -> str:
    url = normalize_canonical_url(record.get("source_url") or (record.get("article") or {}).get("final_url"))
    if url and "news.google.com/rss/articles" not in url:
        return f"url:{url}"
    title = normalize_title(record.get("title"))
    day = str(record.get("published_date") or "")[:10]
    return f"title_date:{title}:{day}" if title and day else f"id:{record.get('id')}"


def _backlog_level(total: int) -> str:
    if total >= BACKLOG_THRESHOLDS["critical"]:
        return "critical"
    if total >= BACKLOG_THRESHOLDS["high"]:
        return "high"
    if total >= BACKLOG_THRESHOLDS["warning"]:
        return "warning"
    return "normal"


def _entity_labels(record: dict[str, Any], entities: dict[str, dict[str, Any]], kind: str) -> list[str]:
    labels = []
    for entity_id in record.get("entity_ids") or []:
        entity = entities.get(str(entity_id)) or {}
        if entity.get("entity_type") == kind:
            labels.append(str(entity.get("name") or entity_id))
    return list(dict.fromkeys(labels))


def _increment(counter: Counter[str], values: Iterable[Any], *, empty: str = "unattributed") -> None:
    normalized = [str(value) for value in values if value is not None and value != ""]
    for value in normalized or [empty]:
        counter[value] += 1


def _ranked(counter: Counter[str]) -> list[dict[str, Any]]:
    return [{"key": key, "count": count} for key, count in counter.most_common()]


def _recorded_decisions(
    *,
    drafts: list[dict[str, Any]],
    trusted: list[dict[str, Any]],
    analyst_state: dict[str, Any],
    now: datetime,
    review_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if review_events is not None:
        current_publication_drafts = [
            row for row in drafts
            if row.get("evidence_role") == "publication_artifact"
            and row.get("status") != "rejected" and row.get("review_state") != "rejected"
        ]
        analytics = review_event_analytics(review_events, current_publication_drafts=current_publication_drafts)
        actions = analytics["counts_by_action"]
        return {
            **analytics,
            "published": actions.get("publish", 0),
            "rejected": actions.get("reject", 0),
            "dismissed_from_triage": sum(row.get("workflow") == "publication_triage" and row.get("action") == "dismiss" for row in review_events),
            "deferred": sum(row.get("workflow") == "claim_testing" and row.get("action") == "defer" for row in review_events),
            "pass": sum(row.get("workflow") == "claim_testing" and row.get("action") == "pass" for row in review_events),
            "fail": sum(row.get("workflow") == "claim_testing" and row.get("action") == "fail" for row in review_events),
            "missing_instrumentation": [
                "Publication Save combines draft editing with keep intent, so it is not counted as an outcome.",
                "Dismiss/defer rationale categories are not collected on every workflow.",
                "Pre-ledger current states remain known state, not fabricated historical events.",
            ],
        }
    published = [
        record for record in trusted
        if record.get("evidence_role") == "publication_artifact"
        and record.get("status") == "published"
        and (record.get("reviewed_at") or record.get("reviewed_by") or record.get("review_outcome"))
    ]
    rejected = [
        record for record in drafts
        if record.get("status") == "rejected" or record.get("review_state") == "rejected"
    ]
    pending_actions = list((analyst_state.get("pending") or {}).values())
    dismissed = [row for row in pending_actions if isinstance(row, dict) and row.get("state") == "dismissed"]
    testing_actions = list((analyst_state.get("testing") or {}).values())
    passed = [row for row in testing_actions if isinstance(row, dict) and row.get("state") == "pass"]
    failed = [row for row in testing_actions if isinstance(row, dict) and row.get("state") == "fail"]
    deferred = [row for row in testing_actions if isinstance(row, dict) and row.get("state") == "defer"]
    dates = [
        stamp for record in [*published, *rejected]
        if (stamp := _parse_datetime(record.get("reviewed_at"))) is not None
    ]
    total_decisions = len(published) + len(rejected)
    observation_days = max(1, (now.date() - min(dates).date()).days + 1) if dates else None
    enough_for_rates = total_decisions >= 10 and bool(observation_days and observation_days >= 2)
    return {
        "category": "OBSERVED",
        "published": len(published),
        "rejected": len(rejected),
        "dismissed_from_triage": len(dismissed),
        "deferred": len(deferred),
        "pass": len(passed),
        "fail": len(failed),
        "dated_publish_or_reject_decisions": len(dates),
        "observation_days": observation_days,
        "review_completions_per_day": round(total_decisions / observation_days, 2) if enough_for_rates and observation_days else None,
        "publish_rate": round(len(published) / total_decisions, 4) if enough_for_rates else None,
        "reject_rate": round(len(rejected) / total_decisions, 4) if enough_for_rates else None,
        "rates_measurable": enough_for_rates,
        "measurement_note": (
            "Recorded decision volume is insufficient for publish/reject throughput or yield rates."
            if not enough_for_rates else "Rates use only recorded publication review decisions."
        ),
        "missing_instrumentation": [
            "append-only review event ledger with draft id, action, timestamp, reviewer, source id, and pre-action queue bucket",
            "explicit save/keep event distinct from draft edit",
            "consistent publish/reject decision timestamp on every publication draft outcome",
            "reason/category for dismiss and defer actions",
            "arrival-to-decision duration captured at decision time",
        ],
    }


def _arrival_metrics(run_records: list[dict[str, Any]], current_total: int, now: datetime) -> dict[str, Any]:
    runs: list[dict[str, Any]] = []
    snapshots: list[dict[str, Any]] = []
    for record in run_records:
        pipeline = str(record.get("pipeline") or "article_spoken_legacy")
        if pipeline == "runtime_backup":
            continue
        counts = record.get("counts") if isinstance(record.get("counts"), dict) else {}
        created = record.get("drafts_created")
        if not isinstance(created, int):
            created = counts.get("publication_drafts_created")
        stamp = _parse_datetime(record.get("completed_at") or record.get("started_at"))
        if isinstance(created, int) and stamp:
            runs.append({"at": stamp.isoformat(timespec="seconds"), "pipeline": pipeline, "drafts_created": created})
        awaiting = counts.get("publication_awaiting_review")
        if isinstance(awaiting, int) and stamp:
            snapshots.append({"at": stamp.isoformat(timespec="seconds"), "backlog": awaiting})
    unique_runs: list[dict[str, Any]] = []
    seen_runs: set[tuple[str, str, int]] = set()
    for row in sorted(runs, key=lambda value: value["at"]):
        identity = (row["pipeline"], row["at"], row["drafts_created"])
        if identity not in seen_runs:
            unique_runs.append(row)
            seen_runs.add(identity)
    # The dispatcher persists its own pipeline result while the invoked legacy
    # collection runner also persists a run. They describe one creation event,
    # not two. Prefer the registry record when timestamps/counts overlap.
    registry_runs = [row for row in unique_runs if row["pipeline"] != "article_spoken_legacy"]
    runs = [
        row for row in unique_runs
        if row["pipeline"] != "article_spoken_legacy"
        or not any(
            candidate["drafts_created"] == row["drafts_created"]
            and abs((_parse_datetime(candidate["at"]) - _parse_datetime(row["at"])).total_seconds()) <= 600
            for candidate in registry_runs
        )
    ]
    snapshots.sort(key=lambda row: row["at"])
    created_values = [row["drafts_created"] for row in runs]
    start = _parse_datetime(runs[0]["at"]) if runs else None
    period_days = max(1 / 24, (now - start).total_seconds() / 86400) if start else None
    first_snapshot = snapshots[0] if snapshots else None
    net_growth = current_total - int(first_snapshot["backlog"]) if first_snapshot else None
    snapshot_start = _parse_datetime(first_snapshot["at"]) if first_snapshot else None
    growth_days = max(1 / 24, (now - snapshot_start).total_seconds() / 86400) if snapshot_start else None
    return {
        "runs_observed": len(runs),
        "drafts_created_in_observed_runs": sum(created_values),
        "mean_drafts_per_run": round(sum(created_values) / len(created_values), 2) if created_values else None,
        "median_drafts_per_run": round(float(median(created_values)), 2) if created_values else None,
        "drafts_per_day": round(sum(created_values) / period_days, 2) if period_days else None,
        "drafts_per_week": round(sum(created_values) / period_days * 7, 2) if period_days else None,
        "first_backlog_snapshot": first_snapshot,
        "latest_persisted_snapshot": snapshots[-1] if snapshots else None,
        "current_backlog": current_total,
        "net_backlog_growth_from_first_snapshot": net_growth,
        "net_backlog_growth_per_day": round(net_growth / growth_days, 2) if net_growth is not None and growth_days else None,
        "run_history": runs,
        "new_since_last_run": runs[-1]["drafts_created"] if runs else None,
        "note": "Arrival metrics use persisted run records; manual draft creation outside those runs is not attributed to a run.",
    }


def _simulate(
    rows: list[dict[str, Any]],
    clusters: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    decisions: dict[str, str] = {}
    reasons: Counter[str] = Counter()
    cluster_representatives: set[str] = set()
    for key, members in clusters.items():
        members.sort(key=lambda row: (row["protected"], row["queue_stamp"] or "", row["id"]), reverse=True)
        if members:
            cluster_representatives.add(members[0]["id"])
    by_source_unprotected: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if not row["protected"]:
            by_source_unprotected[row["source_id"]].append(row)
    source_rank: dict[str, int] = {}
    adjacent_rank: dict[str, int] = {}
    for source_id, members in by_source_unprotected.items():
        members.sort(key=lambda row: (row["queue_stamp"] or "", row["id"]), reverse=True)
        adjacent_seen = 0
        for index, row in enumerate(members, 1):
            source_rank[row["id"]] = index
            if row["tier"] == "adjacent":
                adjacent_seen += 1
                adjacent_rank[row["id"]] = adjacent_seen
    for row in rows:
        reason = "surface"
        cluster = clusters[row["cluster_key"]]
        if len(cluster) > 1 and row["id"] not in cluster_representatives and not row["rare_or_regulatory"]:
            reason = "defer_exact_reprint_secondary"
        elif not row["protected"] and row["tier"] == "adjacent" and adjacent_rank.get(row["id"], 0) > 10:
            reason = "defer_adjacent_source_overflow"
        elif not row["protected"] and source_rank.get(row["id"], 0) > 25:
            reason = "defer_unprotected_source_overflow"
        elif not row["protected"] and (row["queue_age_days"] or 0) > 45:
            reason = "defer_old_unprotected"
        decisions[row["id"]] = reason
        reasons[reason] += 1
    deferred = [row for row in rows if decisions[row["id"]] != "surface"]
    by_source = Counter(row["source_id"] for row in deferred)
    by_class = Counter(row["source_class"] for row in deferred)
    by_tier = Counter(row["tier"] for row in deferred)
    protected_surface = sum(1 for row in rows if row["protected"] and decisions[row["id"]] == "surface")
    unique_direct_or_uncertain_lost = sum(
        1 for row in rows
        if row["tier"] in {"direct", "uncertain"}
        and len(clusters[row["cluster_key"]]) == 1
        and decisions[row["id"]] != "surface"
    )
    return {
        "category": "SIMULATED_POLICY_EFFECT",
        "automatic_throttling_enabled": False,
        "simulation_mode": "as_if_backlog_were_critical",
        "would_defer": len(deferred),
        "would_surface": len(rows) - len(deferred),
        "protected_items_surface": protected_surface,
        "direct_or_uncertain_unique_events_lost": unique_direct_or_uncertain_lost,
        "unique_cluster_representative_preserved": True,
        "deferred_by_reason": dict(reasons - Counter({"surface": reasons.get("surface", 0)})),
        "deferred_by_source": _ranked(by_source),
        "deferred_by_source_class": _ranked(by_class),
        "deferred_by_relevance_tier": _ranked(by_tier),
        "interpretation": "This is a deterministic attention simulation, not a prediction of analyst decisions or truth.",
        "enablement_decision": "OFF: recorded review outcomes are insufficient and the simulation has not proven real keep/reject economics.",
        "item_actions": decisions,
    }


def build_review_capacity_report(
    *,
    drafts: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    entities: list[dict[str, Any]],
    trusted: list[dict[str, Any]],
    run_records: list[dict[str, Any]],
    analyst_state: dict[str, Any] | None = None,
    discovered: list[dict[str, Any]] | None = None,
    now: datetime | None = None,
    include_items: bool = False,
    review_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    instant = (now or datetime.now(UTC)).astimezone(UTC)
    active = [
        record for record in drafts
        if record.get("evidence_role") == "publication_artifact"
        and record.get("status") != "rejected"
        and record.get("review_state") != "rejected"
    ]
    source_index = {str(row.get("id")): row for row in sources if row.get("id")}
    entity_index = {str(row.get("id")): row for row in entities if row.get("id")}
    class_source_counts = Counter(_source_class(row) for row in sources if row.get("enabled", True))
    counters = {key: Counter() for key in (
        "source", "source_class", "berry", "geography", "media_type", "relevance_tier",
        "direct_adjacent", "age", "event_age", "query_family", "company", "variety",
        "review_priority", "access_limitation",
    )}
    clusters: dict[str, list[dict[str, Any]]] = defaultdict(list)
    rows: list[dict[str, Any]] = []
    queue_ages: list[int] = []
    oldest: dict[str, Any] | None = None
    for record in active:
        source_id = str(record.get("source_id") or "unknown")
        source = source_index.get(source_id) or {}
        source_class = _source_class(source)
        query_family = _query_family(source)
        tier = str(record.get("relevance_tier") or "unclassified")
        queue_age = _queue_age_days(record, instant)
        event_age = _event_age_days(record, instant)
        if queue_age is not None:
            queue_ages.append(queue_age)
        companies = _entity_labels(record, entity_index, "company")
        varieties = _entity_labels(record, entity_index, "variety")
        rare_or_regulatory = source_class == "government_regulatory" or class_source_counts[source_class] <= 2
        high_source = source.get("monitoring_priority") == "high"
        explicit_priority = any(
            (record.get("priority") or {}).get(dimension, {}).get("level") == "high"
            for dimension in ("reading", "monitoring")
        )
        protected_reasons = []
        if tier in {"direct", "uncertain"}:
            protected_reasons.append(tier)
        if high_source:
            protected_reasons.append("high_priority_source")
        if rare_or_regulatory:
            protected_reasons.append("rare_or_regulatory_source_class")
        if companies or varieties:
            protected_reasons.append("explicit_company_or_variety")
        if explicit_priority:
            protected_reasons.append("explicit_high_review_or_monitoring_priority")
        protected = bool(protected_reasons)
        if queue_age is not None and queue_age > 45:
            review_priority = "review_soon" if protected else "backlog"
        elif tier == "direct" and (high_source or rare_or_regulatory or companies or varieties):
            review_priority = "review_now"
        elif protected or tier in {"direct", "uncertain"}:
            review_priority = "review_soon"
        else:
            review_priority = "backlog"
        cluster_key = _cluster_key(record)
        row = {
            "id": str(record.get("id") or ""),
            "title": str(record.get("title") or ""),
            "source_id": source_id,
            "source_class": source_class,
            "query_family": query_family,
            "tier": tier,
            "queue_age_days": queue_age,
            "event_age_days": event_age,
            "queue_stamp": _queue_stamp(record).isoformat(timespec="seconds") if _queue_stamp(record) else None,
            "review_priority": review_priority,
            "protected": protected,
            "protected_reasons": protected_reasons,
            "rare_or_regulatory": rare_or_regulatory,
            "cluster_key": cluster_key,
            "access_limitation": _access_limitation(record, source),
        }
        rows.append(row)
        clusters[cluster_key].append(row)
        counters["source"][source_id] += 1
        counters["source_class"][source_class] += 1
        _increment(counters["berry"], record.get("berry_ids") or [])
        _increment(counters["geography"], record.get("geography_ids") or [])
        counters["media_type"][str(record.get("media_format") or "unknown")] += 1
        counters["relevance_tier"][tier] += 1
        counters["direct_adjacent"][tier if tier in {"direct", "adjacent"} else "other"] += 1
        counters["age"][_age_bucket(queue_age)] += 1
        counters["event_age"][_age_bucket(event_age)] += 1
        counters["query_family"][query_family] += 1
        _increment(counters["company"], companies)
        _increment(counters["variety"], varieties)
        counters["review_priority"][review_priority] += 1
        counters["access_limitation"][row["access_limitation"]] += 1
        if oldest is None or (queue_age is not None and queue_age > (oldest.get("queue_age_days") or -1)):
            oldest = {"id": row["id"], "title": row["title"], "queue_age_days": queue_age, "source_id": source_id}

    cluster_excess = sum(max(0, len(values) - 1) for values in clusters.values())
    duplicate_clusters = [
        {"cluster_key": key, "count": len(values), "representative": values[0]["title"], "source_ids": sorted({row["source_id"] for row in values})}
        for key, values in clusters.items() if len(values) > 1
    ]
    duplicate_clusters.sort(key=lambda row: row["count"], reverse=True)
    discovered_by_source: Counter[str] = Counter()
    irrelevant_by_source: Counter[str] = Counter()
    for item in discovered or []:
        sid = str(item.get("source_id") or "unknown")
        discovered_by_source[sid] += 1
        if (item.get("relevance_screening") or {}).get("decision") == "skip":
            irrelevant_by_source[sid] += 1
    publication_events = [
        row for row in (review_events or [])
        if row.get("workflow") == "publication_review" and row.get("action") in {"publish", "reject"}
    ]
    trusted_by_source = Counter(str(row.get("source_id") or "unknown") for row in publication_events if row.get("action") == "publish")
    rejected_by_source = Counter(str(row.get("source_id") or "unknown") for row in publication_events if row.get("action") == "reject")
    direct_by_source = Counter(row["source_id"] for row in rows if row["tier"] == "direct")
    adjacent_by_source = Counter(row["source_id"] for row in rows if row["tier"] == "adjacent")
    duplicate_by_source: Counter[str] = Counter()
    for cluster in clusters.values():
        for row in cluster[1:]:
            duplicate_by_source[row["source_id"]] += 1
    source_economics = []
    for source_id, pending in counters["source"].most_common():
        decided = trusted_by_source[source_id] + rejected_by_source[source_id]
        source = source_index.get(source_id) or {}
        source_economics.append({
            "source_id": source_id,
            "label": source.get("label") or source_id,
            "source_class": _source_class(source),
            "query_family": _query_family(source),
            "pending_backlog": pending,
            "discovered_items": discovered_by_source[source_id] if discovered is not None else None,
            "irrelevant_discovered_items": irrelevant_by_source[source_id] if discovered is not None else None,
            "direct_pending": direct_by_source[source_id],
            "adjacent_pending": adjacent_by_source[source_id],
            "duplicate_reprint_excess": duplicate_by_source[source_id],
            "recorded_published": trusted_by_source[source_id],
            "recorded_rejected": rejected_by_source[source_id],
            "recorded_decisions": decided,
            "publish_rate": round(trusted_by_source[source_id] / decided, 4) if decided >= MINIMUM_RATE_SAMPLE else None,
            "reject_rate": round(rejected_by_source[source_id] / decided, 4) if decided >= MINIMUM_RATE_SAMPLE else None,
            "yield_measurable": decided >= MINIMUM_RATE_SAMPLE,
        })
    query_economics = []
    for family, pending in counters["query_family"].most_common():
        family_sources = {sid for sid, source in source_index.items() if _query_family(source) == family}
        decided = sum(trusted_by_source[sid] + rejected_by_source[sid] for sid in family_sources)
        query_economics.append({
            "query_family": family,
            "pending_backlog": pending,
            "source_count": len(family_sources),
            "discovered_items": sum(discovered_by_source[sid] for sid in family_sources) if discovered is not None else None,
            "irrelevant_discovered_items": sum(irrelevant_by_source[sid] for sid in family_sources) if discovered is not None else None,
            "duplicate_reprint_excess": sum(duplicate_by_source[sid] for sid in family_sources),
            "recorded_decisions": decided,
            "yield_measurable": decided >= MINIMUM_RATE_SAMPLE,
        })
    observed = _recorded_decisions(
        drafts=drafts, trusted=trusted, analyst_state=analyst_state or {}, now=instant,
        review_events=review_events,
    )
    arrival = _arrival_metrics(run_records, len(active), instant)
    simulation = _simulate(rows, clusters)
    report = {
        "generated_at": instant.isoformat(timespec="seconds"),
        "policy": {
            "automatic_throttling_enabled": False,
            "thresholds": BACKLOG_THRESHOLDS,
            "current_level": _backlog_level(len(active)),
            "critical_behavior": "continue discovery; emit warning; simulate deferral only; do not suppress or delete drafts",
        },
        "observed_review_events": observed,
        "derived_operational_metrics": {
            "category": "DERIVED_OPERATIONAL_METRICS",
            "backlog_total": len(active),
            "backlog_level": _backlog_level(len(active)),
            "median_queue_age_days": round(float(median(queue_ages)), 2) if queue_ages else None,
            "oldest_open_item": oldest,
            "new_since_last_run": arrival["new_since_last_run"],
            "arrival": arrival,
            "composition": {key: _ranked(counter) for key, counter in counters.items()},
            "duplicate_reprint": {
                "clusters": len(duplicate_clusters),
                "excess_items": cluster_excess,
                "top_clusters": duplicate_clusters[:25],
            },
            "source_economics": source_economics,
            "query_family_economics": query_economics,
            "interpretation": "These are queue/load measurements, not review yield or trust scores.",
        },
        "simulated_policy_effect": simulation,
        "priority_trust_boundary": "Review priority controls attention only. It never changes source_authority, information_confidence, status, review_state, or trusted data.",
        "aging_policy": {
            "0_7_days": "current",
            "8_30_days": "maturing",
            "31_45_days": "aging",
            "over_45_days": "older backlog unless protected; age alone never rejects or discards",
        },
    }
    if include_items:
        actions = report["simulated_policy_effect"].pop("item_actions")
        report["simulated_policy_effect"]["items"] = [
            {**row, "simulated_action": actions[row["id"]]}
            for row in rows
        ]
    else:
        report["simulated_policy_effect"].pop("item_actions")
    return report
