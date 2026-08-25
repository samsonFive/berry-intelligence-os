"""Analyst Review Session: operational navigation only. Not a trust object."""

from __future__ import annotations

import json
import secrets
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

from app.queries.pending_review import PendingReviewQueryService
from app.services.analyst_queue import load_state
from app.services.morning_brief import assign_buckets, assign_pending_triage, brief_last_seen, rank_item, _parse_stamp as parse_brief_stamp
from app.services.review_events import load_review_events
from app.services.source_fidelity_recovery import load_recovery_artifacts
from app.services.source_fidelity_workbench import build_queue_rows, review_status

SESSION_DIRNAME = "review_sessions"
CURRENT_NAME = "current.json"
SESSION_SIZES = (5, 10, 25)
QUEUE_TYPES = ("publication", "source_fidelity", "atomic")
CONTINUE_PATH = "/review-ops/session/continue"
HISTORY_LIMIT = 5
EMPTY_QUEUE_MESSAGES = {
    "publication": "No pending publications matched this session's filters.",
    "source_fidelity": "No unresolved Source Fidelity items matched this session's filters.",
    "atomic": "No Atomic review batches available. Extraction remains disabled.",
}
FORBIDDEN_KEYS = {
    "article", "transcript", "transcript_segments", "transcript_excerpt",
    "raw_content", "raw_html", "source_text", "publisher_description",
    "paragraphs", "segments", "body", "reader",
}

TERMINAL_FIDELITY = {"affirmed", "rejected", "needs_investigation"}
TERMINAL_PUBLICATION = {"published", "rejected"}
TERMINAL_ATOMIC = {"published", "rejected"}


def session_dir(inbox_dir: Path) -> Path:
    return Path(inbox_dir) / SESSION_DIRNAME


def continue_href() -> str:
    return CONTINUE_PATH


def is_session_return(path: str | None) -> bool:
    text = str(path or "")
    return text.startswith("/review-ops/session")


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_current_pointer(inbox_dir: Path) -> str:
    return str(_read_json(session_dir(inbox_dir) / CURRENT_NAME).get("session_id") or "")


def load_session(inbox_dir: Path, session_id: str | None = None) -> dict[str, Any] | None:
    sid = session_id or load_current_pointer(inbox_dir)
    if not sid:
        return None
    path = session_dir(inbox_dir) / f"{sid}.json"
    if not path.is_file():
        return None
    blob = _read_json(path)
    return blob if blob.get("session_id") else None


def _without_bodies(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _without_bodies(item) for key, item in value.items() if key not in FORBIDDEN_KEYS}
    if isinstance(value, list):
        return [_without_bodies(item) for item in value]
    return value


def save_session(inbox_dir: Path, session: dict[str, Any]) -> dict[str, Any]:
    sid = str(session.get("session_id") or "")
    cleaned = _without_bodies(session)
    cleaned["session_id"] = sid
    _write_json(session_dir(inbox_dir) / f"{sid}.json", cleaned)
    _write_json(session_dir(inbox_dir) / CURRENT_NAME, {"session_id": sid})
    return cleaned


def _item_href(queue: str, item_id: str) -> str:
    encoded = quote(CONTINUE_PATH, safe="")
    if queue == "publication":
        return f"/review/{item_id}?return_to={encoded}"
    if queue == "source_fidelity":
        return f"/source-fidelity/{item_id}?return_to={encoded}"
    return f"/review?kind=atomic&parent={quote(item_id)}&return_to={encoded}"


def _publication_items(
    *,
    inbox_dir: Path,
    pending_service: PendingReviewQueryService,
    entities: dict[str, dict[str, Any]],
    sources: dict[str, dict[str, Any]],
    berry_labels: dict[str, str],
    berry_id: str,
    source: str,
    completeness: str,
    bucket: str,
    size: int,
) -> list[dict[str, Any]]:
    snapshot = pending_service.list_pending(
        entities=entities,
        sources=sources,
        berry_id=berry_id,
        source=source,
        completeness=completeness,
    )
    today = date.today()
    last_seen = brief_last_seen(inbox_dir)
    ctx = {
        "entities": entities,
        "entities_by_name": {str(e.get("name") or "").casefold(): e for e in entities.values() if e.get("name")},
        "berry_labels": berry_labels,
        "state": load_state(inbox_dir),
        "signals": [],
        "sources": {str(row.get("id") or ""): row for row in sources.values()},
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
                [rank_item(record, ctx=ctx, compact=True) for record in snapshot.records],
                key=lambda item: int(item.get("score") or 0),
                reverse=True,
            )
        ),
        state=ctx["state"],
    )
    open_pending = [item for item in ranked if item.get("triage_bucket") != "dismissed" and item.get("id")]
    if bucket:
        open_pending = [item for item in open_pending if item.get("triage_bucket") == bucket]
    return [
        {"id": str(item["id"]), "kind": "publication", "href": _item_href("publication", str(item["id"]))}
        for item in open_pending[:size]
    ]


def _fidelity_items(
    *,
    inbox_dir: Path,
    published: list[dict[str, Any]],
    artifacts: list[dict[str, Any]] | None,
    entities: dict[str, dict[str, Any]],
    size: int,
) -> list[dict[str, Any]]:
    rows = build_queue_rows(
        artifacts if artifacts is not None else load_recovery_artifacts(Path(inbox_dir) / "source_fidelity" / "artifacts"),
        {str(row.get("id")): row for row in published if row.get("id")},
        filters={"state": "pending"},
        entities=entities,
    )
    pending = [row for row in rows if row.get("review_state") == "pending"]
    return [
        {
            "id": str(row["trusted"]["id"]),
            "kind": "source_fidelity",
            "href": _item_href("source_fidelity", str(row["trusted"]["id"])),
        }
        for row in pending[:size]
    ]


def _atomic_items(atomic_drafts: list[dict[str, Any]], size: int) -> list[dict[str, Any]]:
    batches: dict[str, int] = {}
    for row in atomic_drafts:
        if row.get("evidence_role") != "atomic_evidence":
            continue
        if row.get("status") in TERMINAL_ATOMIC:
            continue
        parent = str(row.get("parent_evidence_id") or "unresolved-parent")
        batches[parent] = batches.get(parent, 0) + 1
    ordered = sorted(batches.items(), key=lambda item: (-item[1], item[0]))
    return [
        {
            "id": parent,
            "kind": "atomic_batch",
            "href": _item_href("atomic", parent),
            "proposition_count": count,
        }
        for parent, count in ordered[:size]
    ]


def create_session(
    inbox_dir: Path,
    *,
    queue: str,
    size: int,
    pending_service: PendingReviewQueryService,
    entities: dict[str, dict[str, Any]],
    sources: dict[str, dict[str, Any]],
    published: list[dict[str, Any]],
    atomic_drafts: list[dict[str, Any]],
    berry_labels: dict[str, str] | None = None,
    berry_id: str = "",
    source: str = "",
    completeness: str = "",
    bucket: str = "",
    fidelity_artifacts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if queue not in QUEUE_TYPES:
        raise ValueError("unsupported review session queue")
    if int(size) not in SESSION_SIZES:
        raise ValueError("unsupported review session size")
    if queue == "publication":
        items = _publication_items(
            inbox_dir=inbox_dir,
            pending_service=pending_service,
            entities=entities,
            sources=sources,
            berry_labels=berry_labels or {},
            berry_id=berry_id,
            source=source,
            completeness=completeness,
            bucket=bucket,
            size=size,
        )
    elif queue == "source_fidelity":
        items = _fidelity_items(
            inbox_dir=inbox_dir,
            published=published,
            artifacts=fidelity_artifacts,
            entities=entities,
            size=size,
        )
    else:
        items = _atomic_items(atomic_drafts, size)
    session = {
        "session_id": "rs-" + secrets.token_hex(8),
        "created_at": _now(),
        "queue": queue,
        "size": int(size),
        "status": "active",
        "filters": {
            "berry_id": berry_id,
            "source": source,
            "completeness": completeness,
            "bucket": bucket,
        },
        "items": items,
        "completed": {},
        "skipped": [],
        "current_id": items[0]["id"] if items else "",
        "outcomes": {},
    }
    if not items:
        session["status"] = "empty"
        session["completed_at"] = _now()
    return save_session(inbox_dir, session)


def _live_outcome(
    queue: str,
    item_id: str,
    *,
    drafts_by_id: dict[str, dict[str, Any]],
    artifacts_by_id: dict[str, dict[str, Any]],
    events: list[dict[str, Any]],
) -> str | None:
    if queue == "publication":
        draft = drafts_by_id.get(item_id)
        if draft is not None:
            status = str(draft.get("status") or draft.get("review_state") or "")
            if status in TERMINAL_PUBLICATION:
                return "rejected" if status == "rejected" else "published"
            return None
        for row in events:
            if str(row.get("object_id") or "") != item_id:
                continue
            action = str(row.get("action") or "")
            if action in {"publish", "approve"}:
                return "published"
            if action == "reject":
                return "rejected"
        return "reviewed"
    if queue == "source_fidelity":
        artifact = artifacts_by_id.get(item_id) or {}
        status = review_status(artifact) if artifact else ""
        if status in TERMINAL_FIDELITY:
            return status
        return None
    pending = [
        row for row in drafts_by_id.values()
        if row.get("evidence_role") == "atomic_evidence"
        and str(row.get("parent_evidence_id") or "unresolved-parent") == item_id
        and str(row.get("status") or "") not in TERMINAL_ATOMIC
    ]
    if pending:
        return None
    actions = [str(row.get("action") or "") for row in events if str(row.get("object_id") or "") in {
        str(draft.get("id") or "") for draft in drafts_by_id.values()
        if str(draft.get("parent_evidence_id") or "") == item_id
    } or str(row.get("object_id") or "") == item_id]
    if any(action == "reject" for action in actions) and not any(action in {"publish", "approve"} for action in actions):
        return "rejected"
    return "reviewed"


def reconcile_session(
    inbox_dir: Path,
    session: dict[str, Any],
    *,
    drafts: list[dict[str, Any]],
    artifacts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    drafts_by_id = {str(row.get("id") or ""): row for row in drafts if row.get("id")}
    artifact_rows = artifacts if artifacts is not None else load_recovery_artifacts(
        Path(inbox_dir) / "source_fidelity" / "artifacts"
    )
    artifacts_by_id = {str(row.get("evidence_id") or ""): row for row in artifact_rows}
    events = load_review_events(inbox_dir)
    queue = str(session.get("queue") or "")
    completed = dict(session.get("completed") or {})
    outcomes = dict(session.get("outcomes") or {})
    for item in session.get("items") or []:
        item_id = str(item.get("id") or "")
        if not item_id or item_id in completed:
            continue
        live = _live_outcome(
            queue, item_id, drafts_by_id=drafts_by_id, artifacts_by_id=artifacts_by_id, events=events,
        )
        if live:
            completed[item_id] = {"at": _now(), "source": "reconciled"}
            outcomes[item_id] = live
    session["completed"] = completed
    session["outcomes"] = outcomes
    skipped = {str(item) for item in (session.get("skipped") or [])}
    remaining = [
        item for item in (session.get("items") or [])
        if str(item.get("id") or "") not in completed and str(item.get("id") or "") not in skipped
    ]
    session["current_id"] = remaining[0]["id"] if remaining else ""
    if not remaining:
        if session.get("status") not in {"stopped"}:
            session["status"] = "complete" if (session.get("items") or []) else "empty"
            session["completed_at"] = session.get("completed_at") or _now()
    return save_session(inbox_dir, session)


def skip_current(inbox_dir: Path, session: dict[str, Any]) -> dict[str, Any]:
    current = str(session.get("current_id") or "")
    skipped = list(session.get("skipped") or [])
    if current and current not in skipped:
        skipped.append(current)
    session["skipped"] = skipped
    completed = session.get("completed") or {}
    remaining = [
        item for item in (session.get("items") or [])
        if str(item.get("id") or "") not in completed and str(item.get("id") or "") not in set(skipped)
    ]
    session["current_id"] = remaining[0]["id"] if remaining else ""
    if not remaining:
        session["status"] = "complete"
        session["completed_at"] = session.get("completed_at") or _now()
    return save_session(inbox_dir, session)


def stop_session(inbox_dir: Path, session: dict[str, Any]) -> dict[str, Any]:
    session["status"] = "stopped"
    session["stopped_at"] = _now()
    return save_session(inbox_dir, session)


def present_session(session: dict[str, Any]) -> dict[str, Any]:
    items = list(session.get("items") or [])
    completed = session.get("completed") or {}
    skipped = list(session.get("skipped") or [])
    outcomes = session.get("outcomes") or {}
    counts: dict[str, int] = {}
    for value in outcomes.values():
        counts[str(value)] = counts.get(str(value), 0) + 1
    return {
        "session_id": session.get("session_id"),
        "queue": session.get("queue"),
        "status": session.get("status"),
        "size": len(items),
        "requested_size": session.get("size"),
        "completed_count": len(completed),
        "skipped_count": len(skipped),
        "remaining_count": max(0, len(items) - len(completed) - len(skipped)),
        "current_id": session.get("current_id"),
        "current_href": next((item.get("href") for item in items if item.get("id") == session.get("current_id")), continue_href()),
        "items": items,
        "outcomes": counts,
        "filters": session.get("filters") or {},
        "created_at": session.get("created_at"),
        "empty_message": EMPTY_QUEUE_MESSAGES.get(str(session.get("queue") or ""), "Nothing matched this session."),
    }


def list_recent_sessions(inbox_dir: Path, *, limit: int = HISTORY_LIMIT) -> list[dict[str, Any]]:
    """Modest recent-session history (not a second audit system -- review
    events remain the real audit trail). Excludes the currently active
    session, which Review Operations already shows via its own resume
    card, so the two lists never duplicate the same row."""
    folder = session_dir(inbox_dir)
    if not folder.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for path in folder.glob("rs-*.json"):
        blob = _read_json(path)
        if blob.get("session_id") and blob.get("status") != "active":
            rows.append(blob)
    rows.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
    return [present_session(row) for row in rows[:limit]]
