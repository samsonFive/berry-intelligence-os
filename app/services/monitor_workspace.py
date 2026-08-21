"""V2 Monitor workspace: Watches (inventory), Alerts (action), Source Health.

Presentation only. Does not create a Watch/Alert store, mutate trusted
records, confirm Signals, or rank Morning Brief / Story Threads.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.services.analyst_queue import is_open_signal_alert, load_state
from app.services.intelligence_feed import present_feed_item
from app.services.morning_brief import brief_last_seen
from app.services.signal_review import EMERGING_STATUSES
from app.services.source_freshness import (
    BLOCKED,
    CURRENT,
    DUE,
    FAILING,
    MANUAL,
    QUIET,
    STALE,
    FRESHNESS_LABELS,
    classify_source_freshness,
    is_discoverable,
)

WATCH_ENTITY_TYPES = {"company", "variety", "geography", "person"}
WATCH_ACTIVITY_LIMIT = 4
RETRY_HINT_FILE_CAP = 2000

HEALTH_BUCKETS = (
    (FAILING, "Failing", "Last collection attempt failed. This is not a quiet source."),
    (BLOCKED, "Blocked", "The publisher rejected the check (access-control / bot-wall)."),
    (STALE, "Stale", "Discoverable, but no successful collection has landed recently — or ever."),
    (DUE, "Due for a check", "Cadence window has elapsed; the source is waiting for a run."),
    (QUIET, "Healthy but quiet", "Checked successfully within cadence; no new items that run."),
    (CURRENT, "Healthy", "Checked successfully within cadence and found activity."),
    (MANUAL, "Not configured for discovery", "No discovery adapter. Manual / reference review only."),
)


def _stamp(record: dict[str, Any]) -> str:
    return str(
        record.get("published_date")
        or record.get("captured_date")
        or record.get("first_seen_at")
        or record.get("proposed_at")
        or record.get("created_at")
        or ""
    )


def _newer_than(stamp: str, last_seen_at: str | None) -> bool:
    if not stamp or not last_seen_at:
        return False
    return stamp[:19] > last_seen_at[:19]


def watched_entities(
    record: dict[str, Any],
    entities: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    watched: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entity_id in record.get("entity_ids") or []:
        text = str(entity_id or "")
        if not text or text in seen:
            continue
        entity = entities.get(text) or {}
        kind = str(entity.get("entity_type") or "")
        if kind not in WATCH_ENTITY_TYPES:
            continue
        seen.add(text)
        watched.append(
            {
                "id": text,
                "name": entity.get("name") or text,
                "entity_type": kind,
                "href": f"/entities/{kind}/{text}",
            }
        )
    return watched


def _index_by_entity(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        for entity_id in record.get("entity_ids") or []:
            text = str(entity_id or "")
            if text:
                index.setdefault(text, []).append(record)
    return index


def _activity_cards(
    records: list[dict[str, Any]],
    *,
    entities: dict[str, dict[str, Any]],
    berry_labels: dict[str, str],
    exclude_id: str,
) -> list[dict[str, Any]]:
    unique: dict[str, dict[str, Any]] = {}
    for record in records:
        item_id = str(record.get("id") or "")
        if not item_id or item_id == exclude_id or item_id in unique:
            continue
        unique[item_id] = record
    ranked = sorted(unique.values(), key=_stamp, reverse=True)[:WATCH_ACTIVITY_LIMIT]
    cards: list[dict[str, Any]] = []
    for record in ranked:
        card = present_feed_item(record, entities=entities, berry_labels=berry_labels)
        card["show_reading_actions"] = False
        card["show_pending_actions"] = False
        cards.append(card)
    return cards


def enrich_watch_items(
    items: list[dict[str, Any]],
    *,
    entities: dict[str, dict[str, Any]],
    berry_labels: dict[str, str],
    published: list[dict[str, Any]],
    drafts: list[dict[str, Any]] | None = None,
    signals: list[dict[str, Any]] | None = None,
    candidates: list[dict[str, Any]] | None = None,
    last_seen_at: str | None = None,
) -> list[dict[str, Any]]:
    """Attach entity/activity/signal context without Brief or thread ranking."""

    activity_pool = list(published) + list(drafts or [])
    by_entity = _index_by_entity(activity_pool)
    signal_rows = list(signals or [])
    emerging = [
        candidate
        for candidate in (candidates or [])
        if str(candidate.get("status") or "") in EMERGING_STATUSES
    ]
    enriched: list[dict[str, Any]] = []
    for item in items:
        watch_id = str(item.get("id") or "")
        watched = watched_entities(item, entities)
        watched_ids = {row["id"] for row in watched}
        related: list[dict[str, Any]] = []
        for entity_id in watched_ids:
            related.extend(by_entity.get(entity_id) or [])
        if not watched_ids:
            related.extend(record for record in activity_pool if str(record.get("id") or "") == watch_id)
        activity = _activity_cards(
            related,
            entities=entities,
            berry_labels=berry_labels,
            exclude_id=watch_id,
        )
        open_signals = [
            signal
            for signal in signal_rows
            if str(signal.get("status") or "") == "proposed"
            and (
                watch_id in (signal.get("evidence_ids") or [])
                or watched_ids.intersection(str(value) for value in (signal.get("entity_ids") or []))
            )
        ]
        open_candidates = [
            candidate
            for candidate in emerging
            if watched_ids.intersection(str(value) for value in (candidate.get("entity_ids") or []))
            or watch_id in (candidate.get("supporting_evidence_ids") or [])
        ]
        latest = activity[0] if activity else None
        new_count = sum(1 for card in activity if _newer_than(str(card.get("date") or ""), last_seen_at))
        berry_names = [
            berry_labels.get(berry_id) or berry_id.removeprefix("berry-").title()
            for berry_id in (item.get("berry_ids") or [])
            if berry_id
        ]
        row = dict(item)
        row.update(
            {
                "watched_entities": watched,
                "watch_type": watched[0]["entity_type"] if len(watched) == 1 else ("mixed" if watched else "evidence"),
                "berry_context": berry_names,
                "recent_activity": activity,
                "open_signal_count": len(open_signals),
                "open_candidate_count": len(open_candidates),
                "open_candidates": open_candidates[:3],
                "new_since_last_count": new_count,
                "last_development": (latest or {}).get("title") or item.get("last_signal") or "",
                "last_development_at": (latest or {}).get("date") or item.get("last_signal_at") or item.get("last_check") or "",
                "last_seen_at": last_seen_at,
            }
        )
        enriched.append(row)
    return enriched


def present_monitor_alerts(
    *,
    signals: list[dict[str, Any]],
    state: dict[str, dict[str, dict[str, Any]]],
    watches: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    health_rows: list[dict[str, Any]] | None = None,
    entities: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Action items derived from existing stores. No new persistence."""

    entities = entities or {}
    signal_alerts: list[dict[str, Any]] = []
    for signal in signals:
        if not is_open_signal_alert(signal, state):
            continue
        evidence_ids = [str(value) for value in (signal.get("evidence_ids") or []) if value]
        signal_alerts.append(
            {
                "id": signal.get("id"),
                "title": signal.get("title") or signal.get("id"),
                "kind": "proposed_signal",
                "decision_href": f"/signals/{signal.get('id')}",
                "reader_item_id": evidence_ids[0] if evidence_ids else "",
                "why": "Proposed Signal — confirm or dismiss. This does not create an Assessment.",
            }
        )

    watched_ids: set[str] = set()
    watch_evidence_ids = {str(watch.get("id") or "") for watch in watches if watch.get("id")}
    for watch in watches:
        watched_ids.update(row["id"] for row in (watch.get("watched_entities") or []))
    candidate_alerts: list[dict[str, Any]] = []
    for candidate in candidates:
        if str(candidate.get("status") or "") not in EMERGING_STATUSES:
            continue
        entity_ids = {str(value) for value in (candidate.get("entity_ids") or []) if value}
        evidence_ids = {str(value) for value in (candidate.get("supporting_evidence_ids") or []) if value}
        if not (
            (watched_ids and entity_ids.intersection(watched_ids))
            or (watch_evidence_ids and evidence_ids.intersection(watch_evidence_ids))
        ):
            continue
        subject = entities.get(next(iter(entity_ids), "")) or {}
        candidate_alerts.append(
            {
                "id": candidate.get("id"),
                "title": candidate.get("title") or candidate.get("id"),
                "kind": "signal_candidate",
                "decision_href": f"/signals/candidates/{candidate.get('id')}?return_to=/queues/monitoring",
                "why": "Open Signal Candidate on a watched entity. Watch does not confirm it.",
                "subject": subject.get("name") or "",
            }
        )

    activity_alerts: list[dict[str, Any]] = []
    for watch in watches:
        count = int(watch.get("new_since_last_count") or 0)
        if count <= 0:
            continue
        activity_alerts.append(
            {
                "id": watch.get("id"),
                "title": watch.get("watch_what") or watch.get("title") or watch.get("id"),
                "kind": "watch_activity",
                "decision_href": f"/queues/monitoring#watch-{watch.get('id')}",
                "reader_item_id": ((watch.get("recent_activity") or [{}])[0] or {}).get("id") or "",
                "why": f"{count} new item(s) since last brief visit. Read in context; do not treat the Watch as an alert.",
            }
        )

    source_alerts: list[dict[str, Any]] = []
    for row in health_rows or []:
        state_code = str((row.get("freshness") or {}).get("state") or "")
        if state_code not in {FAILING, BLOCKED}:
            continue
        source_alerts.append(
            {
                "id": row.get("id"),
                "title": row.get("label") or row.get("id"),
                "kind": "source_health",
                "decision_href": f"/sources#source-{row.get('id')}",
                "why": (row.get("freshness") or {}).get("reason") or FRESHNESS_LABELS.get(state_code, state_code),
            }
        )

    groups = [
        {
            "key": "signals",
            "label": "Proposed signals",
            "count": len(signal_alerts),
            "blurb": "Trusted Signal records still proposed. Confirm / Dismiss is the existing alert action workflow.",
            "rows": signal_alerts,
        },
        {
            "key": "candidates",
            "label": "Signal candidates on watches",
            "count": len(candidate_alerts),
            "blurb": "Untrusted candidates. Deep-link to Signal Review. A Watch never confirms a Signal.",
            "rows": candidate_alerts,
        },
        {
            "key": "watch_activity",
            "label": "New watch activity",
            "count": len(activity_alerts),
            "blurb": "Something changed on an inventory Watch. Open the Reader; do not decide here.",
            "rows": activity_alerts,
        },
        {
            "key": "sources",
            "label": "Sources needing attention",
            "count": len(source_alerts),
            "blurb": "Collection failed or was blocked. Open Source Health. This is not intelligence recall.",
            "rows": source_alerts,
        },
    ]
    return groups


def retry_hints_by_source(inbox_dir: Path | None) -> dict[str, dict[str, Any]]:
    """Cheap per-source retry overlay from collection-runner item state."""

    if inbox_dir is None:
        return {}
    ops = Path(inbox_dir) / "operations" / "items"
    if not ops.is_dir():
        return {}
    hints: dict[str, dict[str, Any]] = {}
    for index, path in enumerate(ops.glob("*.json")):
        if index >= RETRY_HINT_FILE_CAP:
            break
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        source_id = str(payload.get("source_id") or "")
        retry_count = payload.get("retry_count") or 0
        next_at = payload.get("next_eligible_retry_at")
        if not source_id or (not retry_count and not next_at):
            continue
        prior = hints.get(source_id) or {}
        if int(retry_count or 0) >= int(prior.get("retry_count") or 0):
            hints[source_id] = {
                "retry_count": int(retry_count or 0),
                "next_eligible_retry_at": next_at,
            }
    return hints


def failing_source_health_rows(
    sources: list[dict[str, Any]],
    *,
    inbox_dir: Path | None,
) -> list[dict[str, Any]]:
    """FAILING/BLOCKED only, from per-source discovery JSON — not a discovered-item scan."""

    from app.services.media_discovery import read_source_discovery_state

    rows: list[dict[str, Any]] = []
    if inbox_dir is None:
        return rows
    for source in sources:
        source_id = str(source.get("id") or "")
        if not source_id:
            continue
        freshness = classify_source_freshness(
            source,
            discovery_state=read_source_discovery_state(inbox_dir, source_id),
        ).as_dict()
        if freshness.get("state") not in {FAILING, BLOCKED}:
            continue
        rows.append({"id": source_id, "label": source.get("label") or source_id, "freshness": freshness})
    return rows


def present_source_health_rows(
    sources: list[dict[str, Any]],
    *,
    freshness_by_source: dict[str, dict[str, Any]],
    entity_type_labels: dict[str, str],
    berry_labels: dict[str, str],
    region_labels: dict[str, str],
    cadence_labels: dict[str, str],
    retry_hints: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    retry_hints = retry_hints or {}
    rows: list[dict[str, Any]] = []
    for source in sources:
        source_id = str(source.get("id") or "")
        freshness = dict(freshness_by_source.get(source_id) or {})
        classes = [
            entity_type_labels.get(key) or key
            for key in (source.get("entity_types") or [])
            if key
        ]
        berries = [
            berry_labels.get(key) or key
            for key in (source.get("berry_ids") or [])
            if key
        ]
        regions = [
            region_labels.get(key) or key
            for key in (source.get("region_coverage") or [])
            if key
        ]
        adapter = ((source.get("discovery") or {}).get("adapter") or "") if is_discoverable(source) else ""
        rows.append(
            {
                **source,
                "freshness": freshness,
                "health_state": freshness.get("state") or MANUAL,
                "health_label": freshness.get("label") or FRESHNESS_LABELS[MANUAL],
                "source_class_labels": classes,
                "berry_labels": berries,
                "region_labels": regions,
                "cadence_label": cadence_labels.get(str(source.get("update_cadence") or ""), source.get("update_cadence") or "—"),
                "discoverable": is_discoverable(source),
                "adapter": adapter,
                "retry": retry_hints.get(source_id) or {},
            }
        )
    return rows


def group_source_health(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_state: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_state.setdefault(str(row.get("health_state") or MANUAL), []).append(row)
    groups: list[dict[str, Any]] = []
    for state, label, copy in HEALTH_BUCKETS:
        items = by_state.get(state) or []
        groups.append(
            {
                "key": state.lower(),
                "state": state,
                "label": label,
                "blurb": copy,
                "count": len(items),
                "rows": items,
            }
        )
    return groups


def monitor_page_model(
    *,
    watch_items: list[dict[str, Any]],
    entities: dict[str, dict[str, Any]],
    berry_labels: dict[str, str],
    published: list[dict[str, Any]],
    drafts: list[dict[str, Any]] | None,
    signals: list[dict[str, Any]],
    candidates: list[dict[str, Any]] | None,
    inbox_dir: Path | None,
    health_rows: list[dict[str, Any]] | None = None,
    include_drafts: bool = True,
) -> dict[str, Any]:
    if inbox_dir is not None:
        last_seen = brief_last_seen(inbox_dir)
        state = load_state(inbox_dir)
    else:
        last_seen = None
        state = {"signals": {}, "monitoring": {}, "meta": {}}
    watches = enrich_watch_items(
        watch_items,
        entities=entities,
        berry_labels=berry_labels,
        published=published,
        drafts=(drafts or []) if include_drafts else [],
        signals=signals,
        candidates=candidates or [],
        last_seen_at=last_seen,
    )
    alerts = present_monitor_alerts(
        signals=signals,
        state=state,
        watches=watches,
        candidates=candidates or [],
        health_rows=health_rows,
        entities=entities,
    )
    return {
        "watch_items": watches,
        "monitor_alerts": alerts,
        "alert_action_count": sum(group["count"] for group in alerts if group["key"] in {"signals", "sources"}),
        "last_seen_at": last_seen,
    }
