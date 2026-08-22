"""Private, append-only human review event records.

Events contain identifiers and operational provenance only. They deliberately
do not copy draft text and are never part of the static publication build.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from typing import Any

EVENTS_DIRNAME = "review_events"
MINIMUM_RATE_SAMPLE = 30


@dataclass(frozen=True)
class EventAppendResult:
    event: dict[str, Any]
    path: Path
    created: bool


def _stamp(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=parsed.tzinfo or UTC).astimezone(UTC)


def _values(subject: dict[str, Any], key: str) -> list[str]:
    value = subject.get(key) or []
    if not isinstance(value, list):
        value = [value]
    return list(dict.fromkeys(str(item) for item in value if item))


def _source_class(source: dict[str, Any]) -> str | None:
    explicit = str(source.get("source_class") or source.get("category") or "")
    if explicit:
        return explicit
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
    return entity_types[0] if entity_types else (str(source.get("type") or "") or None)


def _query_provenance(source: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    discovery = source.get("discovery") if isinstance(source.get("discovery"), dict) else {}
    adapter = str(discovery.get("adapter") or source.get("adapter") or "") or None
    family = str(discovery.get("query_family") or source.get("query_family") or adapter or "") or None
    params = discovery.get("params") if isinstance(discovery.get("params"), dict) else {}
    query = discovery.get("query") or params.get("query")
    return family, str(query) if query else None, adapter


def append_review_event(
    inbox_dir: Path,
    *,
    workflow: str,
    object_id: str,
    object_type: str,
    action: str,
    prior_state: str,
    new_state: str,
    actor: str,
    subject: dict[str, Any] | None = None,
    source: dict[str, Any] | None = None,
    reason_category: str | None = None,
    occurred_at: str | None = None,
) -> EventAppendResult:
    subject, source = subject or {}, source or {}
    if not re.fullmatch(r"[a-z][a-z0-9_]{1,63}", workflow):
        raise ValueError("invalid review-event workflow")
    root = Path(inbox_dir) / EVENTS_DIRNAME / workflow
    object_key = hashlib.sha256(object_id.encode("utf-8")).hexdigest()[:24]
    object_dir = root / object_key
    previous = load_review_events(inbox_dir, workflow=workflow, object_id=object_id)
    previous_id = previous[-1]["id"] if previous else None
    if previous:
        latest = previous[-1]
        retry_fields = ("workflow", "object_id", "object_type", "action", "prior_state", "new_state", "actor", "reason_category")
        requested = {
            "workflow": workflow, "object_id": object_id, "object_type": object_type,
            "action": action, "prior_state": prior_state, "new_state": new_state,
            "actor": actor, "reason_category": reason_category,
        }
        if all(latest.get(key) == requested.get(key) for key in retry_fields):
            return EventAppendResult(event=latest, path=object_dir / f"{latest['id']}.json", created=False)
    identity = {
        "workflow": workflow, "object_id": object_id, "object_type": object_type,
        "action": action, "prior_state": prior_state, "new_state": new_state,
        "actor": actor, "reason_category": reason_category, "previous_event_id": previous_id,
    }
    event_id = "rev-" + hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:32]
    provenance = subject.get("discovery_provenance") if isinstance(subject.get("discovery_provenance"), dict) else {}
    query_family, query_identifier, mechanism = _query_provenance(source)
    entered = provenance.get("first_seen_at") or subject.get("created_at") or subject.get("captured_date")
    event = {
        "id": event_id,
        "record_type": "review_event",
        "occurred_at": occurred_at or datetime.now(UTC).isoformat(timespec="seconds"),
        "actor": actor,
        "workflow": workflow,
        "object_id": object_id,
        "object_type": object_type,
        "action": action,
        "prior_state": prior_state,
        "new_state": new_state,
        "source_id": subject.get("source_id"),
        "source_class": _source_class(source),
        "query_family": query_family,
        "query_identifier": query_identifier,
        "discovery_mechanism": mechanism,
        "berry_ids": _values(subject, "berry_ids"),
        "geography_ids": _values(subject, "geography_ids"),
        "entity_ids": _values(subject, "entity_ids"),
        "media_type": subject.get("media_format") or subject.get("source_type"),
        "relevance_tier": subject.get("relevance_tier"),
        "discovered_item_id": subject.get("discovered_item_id"),
        "pipeline_run_id": provenance.get("run_id") or subject.get("collection_run_id") or subject.get("pipeline_run_id"),
        "queue_entered_at": entered,
        "reason_category": reason_category,
        "previous_event_id": previous_id,
    }
    object_dir.mkdir(parents=True, exist_ok=True)
    path = object_dir / f"{event_id}.json"
    try:
        with path.open("x", encoding="utf-8") as handle:
            json.dump(event, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        created = True
    except FileExistsError:
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing != event:
            raise RuntimeError(f"review event collision: {event_id}")
        event, created = existing, False
    return EventAppendResult(event=event, path=path, created=created)


def remove_created_event(result: EventAppendResult) -> None:
    """Compensate a state write failure; never removes a pre-existing event."""
    if result.created and result.path.is_file():
        result.path.unlink()


def load_review_events(
    inbox_dir: Path, *, workflow: str | None = None, object_id: str | None = None
) -> list[dict[str, Any]]:
    root = Path(inbox_dir) / EVENTS_DIRNAME
    if workflow:
        root /= workflow
    if not root.is_dir():
        return []
    events: list[dict[str, Any]] = []
    for path in root.rglob("*.json"):
        try:
            event = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if event.get("record_type") != "review_event":
            continue
        if object_id is not None and event.get("object_id") != object_id:
            continue
        events.append(event)
    events.sort(key=lambda row: (str(row.get("occurred_at") or ""), str(row.get("id") or "")))
    return events


def review_event_analytics(
    events: list[dict[str, Any]], *, current_publication_drafts: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    counts = Counter(str(row.get("action") or "unknown") for row in events)
    workflows = Counter(str(row.get("workflow") or "unknown") for row in events)
    publication = [row for row in events if row.get("workflow") == "publication_review" and row.get("action") in {"publish", "reject"}]
    dated = [_stamp(row.get("occurred_at")) for row in publication]
    dated = [stamp for stamp in dated if stamp]
    ages = []
    for row in events:
        start, end = _stamp(row.get("queue_entered_at")), _stamp(row.get("occurred_at"))
        if start and end and end >= start:
            ages.append((end - start).total_seconds() / 86400)
    observation_days = max(1, (max(dated).date() - min(dated).date()).days + 1) if dated else None
    measurable = len(publication) >= MINIMUM_RATE_SAMPLE and bool(observation_days and observation_days >= 2)
    reviewed = {str(row.get("object_id")) for row in publication}
    current = current_publication_drafts or []
    return {
        "category": "OBSERVED",
        "total_observed_decisions": len(events),
        "last_decision_at": events[-1].get("occurred_at") if events else None,
        "counts_by_action": dict(counts),
        "counts_by_workflow": dict(workflows),
        "counts_by_source": dict(Counter(str(row.get("source_id") or "unattributed") for row in events)),
        "counts_by_source_class": dict(Counter(str(row.get("source_class") or "unattributed") for row in events)),
        "counts_by_query_family": dict(Counter(str(row.get("query_family") or "unattributed") for row in events)),
        "reviewed_current_publication_objects": sum(1 for row in current if str(row.get("id")) in reviewed),
        "unreviewed_current_publication_objects": sum(1 for row in current if str(row.get("id")) not in reviewed),
        "median_review_age_days": round(float(median(ages)), 2) if ages else None,
        "publication_decision_sample": len(publication),
        "observation_days": observation_days,
        "publish_rate": round(sum(row.get("action") == "publish" for row in publication) / len(publication), 4) if measurable else None,
        "reject_rate": round(sum(row.get("action") == "reject" for row in publication) / len(publication), 4) if measurable else None,
        "rates_measurable": measurable,
        "minimum_rate_sample": MINIMUM_RATE_SAMPLE,
        "measurement_note": "Rates require at least 30 publication decisions across at least two observed days; counts remain usable earlier.",
        "historical_note": "Current object state is not treated as a historical review event; no inferred backfill is included.",
    }
