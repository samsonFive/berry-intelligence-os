"""Private Review Operations cockpit. Counts and links only — no trust actions."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from app.queries.pending_review import PendingReviewQueryService
from app.services.analyst_queue import load_state
from app.services.morning_brief import (
    assign_buckets,
    assign_pending_triage,
    brief_last_seen,
    rank_item,
    _parse_stamp as parse_brief_stamp,
)
from app.services.review_events import load_review_events
from app.services.source_fidelity_recovery import load_recovery_artifacts
from app.services.source_fidelity_workbench import build_queue_rows, staged_at

AGE_BUCKETS = (
    ("today", "Today", 0, 1),
    ("d1_3", "1–3 days", 1, 4),
    ("d4_7", "4–7 days", 4, 8),
    ("d8_30", "8–30 days", 8, 31),
    ("d30", "30+ days", 31, None),
)

EVENT_LABELS = {
    ("publication_review", "publish"): "Published",
    ("publication_review", "reject"): "Rejected",
    ("source_fidelity_review", "affirmed"): "Source artifact affirmed",
    ("source_fidelity_review", "rejected"): "Source artifact rejected",
    ("source_fidelity_review", "needs_investigation"): "Source artifact needs investigation",
    ("atomic_evidence_review", "approve"): "Atomic approved",
    ("atomic_evidence_review", "reject"): "Atomic rejected",
    ("atomic_evidence_review", "publish"): "Atomic approved",
}

ATOMIC_OMIT = {
    "article", "transcript", "transcript_segments", "transcript_excerpt",
    "raw_content", "raw_html", "source_text", "publisher_description",
    "attachments", "source_artifact",
}


def _parse_day(value: Any) -> date | None:
    text = str(value or "")[:10]
    if len(text) < 10:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _parse_stamp(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return _parse_day(value) and datetime.combine(_parse_day(value), datetime.min.time(), tzinfo=UTC)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _age_days(value: Any, today: date) -> int | None:
    day = _parse_day(value)
    if day is None:
        stamp = _parse_stamp(value)
        day = stamp.date() if stamp else None
    if day is None:
        return None
    return max(0, (today - day).days)


def _bucket_key(days: int | None) -> str:
    if days is None:
        return "unknown"
    for key, _label, start, end in AGE_BUCKETS:
        if days >= start and (end is None or days < end):
            return key
    return "unknown"


def _age_counts(rows: list[int | None]) -> list[dict[str, Any]]:
    tallies = Counter(_bucket_key(days) for days in rows)
    return [
        {"key": key, "label": label, "count": int(tallies.get(key) or 0)}
        for key, label, _start, _end in AGE_BUCKETS
    ]


def _slim_atomic(record: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if key not in ATOMIC_OMIT}


def _publication_entered(record: dict[str, Any]) -> str:
    return str(
        record.get("captured_date")
        or record.get("created_at")
        or record.get("submitted_at")
        or record.get("published_date")
        or ""
    )


def _matches_age(days: int | None, age_filter: str) -> bool:
    if not age_filter:
        return True
    return _bucket_key(days) == age_filter


def _event_label(event: dict[str, Any]) -> str:
    workflow = str(event.get("workflow") or "")
    action = str(event.get("action") or "")
    return EVENT_LABELS.get((workflow, action), f"{workflow} · {action}".strip(" ·"))


def _extraction_disabled(extraction_gate: dict[str, Any] | None) -> bool:
    gate = extraction_gate or {}
    if "runnable" in gate:
        return not bool(gate.get("runnable"))
    return not bool(gate.get("enabled"))


def build_review_operations(
    *,
    inbox_dir: Path,
    pending_service: PendingReviewQueryService,
    entities: dict[str, dict[str, Any]],
    sources: dict[str, dict[str, Any]],
    published: list[dict[str, Any]],
    atomic_drafts: list[dict[str, Any]],
    fidelity_artifacts: list[dict[str, Any]] | None = None,
    review_events: list[dict[str, Any]] | None = None,
    extraction_gate: dict[str, Any] | None = None,
    berry_id: str = "",
    source: str = "",
    age: str = "",
    berry_labels: dict[str, str] | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    today = today or date.today()
    snapshot = pending_service.list_pending(
        entities=entities,
        sources=sources,
        berry_id=berry_id,
        source=source,
    )
    pub_rows = list(snapshot.records)
    if age:
        pub_rows = [row for row in pub_rows if _matches_age(_age_days(_publication_entered(row), today), age)]

    state = load_state(inbox_dir)
    last_seen = brief_last_seen(inbox_dir)
    source_index = {str(row.get("id") or ""): row for row in sources.values()}
    ctx = {
        "entities": entities,
        "entities_by_name": {
            str(entity.get("name") or "").casefold(): entity
            for entity in entities.values()
            if entity.get("name")
        },
        "berry_labels": berry_labels or {},
        "state": state,
        "signals": [],
        "sources": source_index,
        "frontier": today,
        "today": today,
        "last_seen": last_seen,
        "since_cutoff": parse_brief_stamp(last_seen) if last_seen else None,
        "watch_entities": set(),
        "hot_entities": set(),
        "first_seen_by_discovered": {},
        "trusted_title_keys": set(),
    }
    ranked = assign_pending_triage(
        assign_buckets(
            sorted(
                [rank_item(record, ctx=ctx, compact=True) for record in pub_rows],
                key=lambda item: int(item.get("score") or 0),
                reverse=True,
            )
        ),
        state=state,
    )
    open_pending = [item for item in ranked if item.get("triage_bucket") != "dismissed"]
    review_now = [item for item in open_pending if item.get("triage_bucket") == "review_now"]
    next_pub = (review_now or open_pending or [None])[0]
    pub_ages = [_age_days(_publication_entered(row), today) for row in pub_rows]
    oldest_pub = None
    if pub_rows:
        oldest = max(pub_rows, key=lambda row: _age_days(_publication_entered(row), today) or -1)
        oldest_pub = {
            "id": oldest.get("id"),
            "age_days": _age_days(_publication_entered(oldest), today),
            "href": f"/review/{oldest.get('id')}" if oldest.get("id") else "/pending",
        }
    full_article = sum(1 for row in pub_rows if row.get("_pending_completeness") == "FULL_ARTICLE")
    pub_reasons = []
    if full_article:
        pub_reasons.append("FULL ARTICLE AVAILABLE")
    if any("berry-raspberry" in (row.get("berry_ids") or []) or "berry-blackberry" in (row.get("berry_ids") or []) for row in pub_rows):
        pub_reasons.append("RASPBERRY / BLACKBERRY UNDERCOVERAGE")
    if next_pub and next_pub.get("why_decision"):
        pub_reasons.append(str(next_pub["why_decision"]))
    pub_health = "empty" if not open_pending else ("backlog building" if any((days or 0) >= 8 for days in pub_ages) else "healthy")

    artifacts = fidelity_artifacts if fidelity_artifacts is not None else load_recovery_artifacts(
        Path(inbox_dir) / "source_fidelity" / "artifacts"
    )
    trusted_by_id = {str(row.get("id")): row for row in published if row.get("id")}
    fidelity_all = build_queue_rows(artifacts, trusted_by_id, filters={}, entities=entities)
    if berry_id:
        fidelity_all = [row for row in fidelity_all if berry_id in {*(trusted_by_id.get(row["trusted"]["id"], {}).get("berry_ids") or [])}]
    if source:
        fidelity_all = [
            row for row in fidelity_all
            if source in {str(row.get("source_name") or ""), str(row["trusted"].get("source_id") or "")}
        ]
    fidelity_pending = [row for row in fidelity_all if row["review_state"] == "pending"]
    if age:
        fidelity_pending = [
            row for row in fidelity_pending
            if _matches_age(_age_days(row.get("staged_at") or staged_at(row.get("artifact") or {}), today), age)
        ]
    fidelity_status = Counter(str(row["review_state"]) for row in fidelity_all)
    next_fid = fidelity_pending[0] if fidelity_pending else None
    fid_ages = [_age_days(row.get("staged_at"), today) for row in fidelity_pending]
    oldest_fid = None
    if fidelity_pending:
        oldest_row = max(fidelity_pending, key=lambda row: _age_days(row.get("staged_at"), today) or -1)
        oldest_fid = {
            "id": oldest_row["trusted"]["id"],
            "age_days": _age_days(oldest_row.get("staged_at"), today),
            "href": f"/source-fidelity/{oldest_row['trusted']['id']}",
        }
    fid_reasons = []
    if next_fid:
        fid_reasons.extend(next_fid.get("priority_reasons") or [])
        match = str(next_fid.get("match_class") or "")
        if "EXACT" in match:
            fid_reasons.append("EXACT SOURCE MATCH")

    atomic = [_slim_atomic(row) for row in atomic_drafts if row.get("evidence_role") == "atomic_evidence"]
    if berry_id:
        atomic = [row for row in atomic if berry_id in (row.get("berry_ids") or [])]
    if source:
        atomic = [row for row in atomic if source in {str(row.get("source_id") or ""), str(row.get("source_name") or "")}]
    pending_atomic = [row for row in atomic if row.get("status", "draft") != "rejected" and row.get("status") != "published"]
    approved_atomic = [row for row in atomic if row.get("status") == "published"]
    rejected_atomic = [row for row in atomic if row.get("status") == "rejected"]
    if age:
        pending_atomic = [
            row for row in pending_atomic
            if _matches_age(_age_days(row.get("captured_date") or row.get("created_at"), today), age)
        ]
    batches: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in pending_atomic:
        batches[str(row.get("parent_evidence_id") or "unresolved-parent")].append(row)
    next_parent = None
    next_batch_size = 0
    if batches:
        next_parent, members = max(batches.items(), key=lambda item: len(item[1]))
        next_batch_size = len(members)
    atomic_ages = [_age_days(row.get("captured_date") or row.get("created_at"), today) for row in pending_atomic]
    oldest_atomic = None
    if pending_atomic:
        oldest_a = max(pending_atomic, key=lambda row: _age_days(row.get("captured_date") or row.get("created_at"), today) or -1)
        oldest_atomic = {
            "id": oldest_a.get("id"),
            "age_days": _age_days(oldest_a.get("captured_date") or oldest_a.get("created_at"), today),
            "href": f"/review?kind=atomic&parent={oldest_a.get('parent_evidence_id') or ''}",
        }
    atomic_reasons = []
    if next_batch_size:
        atomic_reasons.append(f"SOURCE BATCH WITH {next_batch_size} PROPOSALS")

    events = review_events if review_events is not None else load_review_events(inbox_dir)
    interesting = [
        event for event in events
        if (str(event.get("workflow") or ""), str(event.get("action") or "")) in EVENT_LABELS
    ]
    interesting.sort(key=lambda row: str(row.get("occurred_at") or ""), reverse=True)
    cutoff = parse_brief_stamp(last_seen) if last_seen else None
    activity = []
    for event in interesting[:12]:
        stamp = parse_brief_stamp(event.get("occurred_at"))
        activity.append(
            {
                "id": event.get("id"),
                "label": _event_label(event),
                "workflow": event.get("workflow"),
                "action": event.get("action"),
                "object_id": event.get("object_id"),
                "occurred_at": event.get("occurred_at"),
                "since_last_session": bool(cutoff and stamp and stamp > cutoff),
            }
        )

    extraction_off = _extraction_disabled(extraction_gate)
    blocked = []
    if extraction_off:
        blocked.append({"code": "ATOMIC_EXTRACTION_DISABLED", "detail": "No new Atomic proposals expected."})
    if not fidelity_pending:
        blocked.append({"code": "SOURCE_FIDELITY_EMPTY", "detail": "No pending source-fidelity artifacts."})
    if pub_health == "empty":
        blocked.append({"code": "PUBLICATION_REVIEW_EMPTY", "detail": "No pending publication drafts."})
    elif pub_health == "backlog building":
        blocked.append({"code": "PUBLICATION_REVIEW_BACKLOG", "detail": "Publication Review backlog building."})

    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "filters": {"berry": berry_id, "source": source, "age": age},
        "last_seen_at": last_seen,
        "publication": {
            "pending": len(open_pending),
            "review_now": len(review_now),
            "inventory": snapshot.inventory_count,
            "oldest": oldest_pub,
            "age_buckets": _age_counts(pub_ages),
            "next_href": f"/review/{next_pub['id']}" if next_pub and next_pub.get("id") else "/pending",
            "queue_href": "/pending",
            "reasons": pub_reasons[:4],
            "health": pub_health,
            "body_records_omitted": snapshot.body_records_omitted,
        },
        "source_fidelity": {
            "pending": len(fidelity_pending),
            "needs_investigation": int(fidelity_status.get("needs_investigation") or 0),
            "affirmed": int(fidelity_status.get("affirmed") or 0),
            "rejected": int(fidelity_status.get("rejected") or 0),
            "oldest": oldest_fid,
            "age_buckets": _age_counts(fid_ages),
            "next_href": f"/source-fidelity/{next_fid['trusted']['id']}" if next_fid else "/source-fidelity",
            "queue_href": "/source-fidelity",
            "reasons": list(dict.fromkeys(fid_reasons))[:4],
            "health": "empty" if not fidelity_pending else "pending work",
        },
        "atomic": {
            "pending": len(pending_atomic),
            "approved": len(approved_atomic),
            "rejected": len(rejected_atomic),
            "batches": len(batches),
            "oldest": oldest_atomic,
            "age_buckets": _age_counts(atomic_ages),
            "next_href": f"/review?kind=atomic&parent={next_parent}" if next_parent else "/review?kind=atomic",
            "queue_href": "/review?kind=atomic",
            "reasons": atomic_reasons,
            "extraction_disabled": extraction_off,
            "health": "blocked" if extraction_off and not pending_atomic else ("empty" if not pending_atomic else "pending work"),
        },
        "activity": activity,
        "blocked": blocked,
        "workload": {
            "publications": len(open_pending),
            "source_fidelity": len(fidelity_pending),
            "atomic": f"{len(pending_atomic)} propositions across {len(batches)} source batches",
        },
    }
