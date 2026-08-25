"""Analyst Watchlist + Monitoring Workspace V1 -- private monitoring
interest in existing trusted objects (Company/Variety/Geography/
Strategic Question). A Watch is navigation/state only, never a trust
object: it never creates Fact/Evidence/Signal/Assessment and never
mutates any canonical record. Reuses the exact same trusted-only inputs
and per-object-type derivation every other presenter in this codebase
already proved (Company Compare/Portfolio, Geography, Strategic
Question) rather than inventing a competing monitoring model.

Persisted the same way `inbox/analyst_queue_state.json` already is (see
AGENTS.md: "Reading state ... is independent of trust. Do not create
another reading-state store.") -- one shared, private, atomically
written JSON file, not a second per-object trust schema."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.services.company_workspace import _humanize_source_type
from app.services.variety_workspace import _party

STATE_FILENAME = "watchlist_state.json"
WATCH_TYPES = ("company", "variety", "geography", "strategic_question")
RECENT_LIMIT = 5


def state_path(inbox_dir: Path) -> Path:
    return Path(inbox_dir) / STATE_FILENAME


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _read(inbox_dir: Path) -> list[dict[str, Any]]:
    path = state_path(inbox_dir)
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    watches = payload.get("watches") if isinstance(payload, dict) else None
    if not isinstance(watches, list):
        return []
    return [row for row in watches if isinstance(row, dict) and row.get("watch_type") and row.get("object_id")]


def _write(inbox_dir: Path, watches: list[dict[str, Any]]) -> None:
    path = state_path(inbox_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps({"watches": watches}, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def load_watches(inbox_dir: Path) -> list[dict[str, Any]]:
    return _read(inbox_dir)


def is_watched(inbox_dir: Path, watch_type: str, object_id: str) -> bool:
    return any(
        row.get("watch_type") == watch_type and row.get("object_id") == object_id
        for row in _read(inbox_dir)
    )


def add_watch(inbox_dir: Path, watch_type: str, object_id: str) -> list[dict[str, Any]]:
    if watch_type not in WATCH_TYPES or not object_id:
        raise ValueError("unsupported watch type or missing object id")
    watches = _read(inbox_dir)
    if any(row.get("watch_type") == watch_type and row.get("object_id") == object_id for row in watches):
        return watches  # idempotent -- duplicate watch is a no-op, not an error
    watches.append({"watch_type": watch_type, "object_id": object_id, "created_at": _now(), "last_seen_at": None})
    _write(inbox_dir, watches)
    return watches


def remove_watch(inbox_dir: Path, watch_type: str, object_id: str) -> list[dict[str, Any]]:
    watches = [
        row for row in _read(inbox_dir)
        if not (row.get("watch_type") == watch_type and row.get("object_id") == object_id)
    ]
    _write(inbox_dir, watches)
    return watches


def mark_watch_seen(inbox_dir: Path, watch_type: str, object_id: str) -> list[dict[str, Any]]:
    """Explicit only -- called when the analyst actually opens the watched
    object's canonical page from the Watchlist, never merely because the
    Watchlist page itself rendered (mission Section 17)."""
    watches = _read(inbox_dir)
    changed = False
    for row in watches:
        if row.get("watch_type") == watch_type and row.get("object_id") == object_id:
            row["last_seen_at"] = _now()
            changed = True
    if changed:
        _write(inbox_dir, watches)
    return watches


def _linked_by_entity_ids(records: list[dict[str, Any]], object_id: str) -> list[dict[str, Any]]:
    return [r for r in records if object_id in (r.get("entity_ids") or [])]


def _company_or_variety_evidence(published_evidence: list[dict[str, Any]], object_id: str) -> list[dict[str, Any]]:
    return _linked_by_entity_ids(published_evidence, object_id)


def _geography_evidence(published_evidence: list[dict[str, Any]], object_id: str) -> list[dict[str, Any]]:
    return [
        r for r in published_evidence
        if object_id in (r.get("geography_ids") or []) or object_id in (r.get("entity_ids") or [])
    ]


def _sq_linked(records: list[dict[str, Any]], sq_id: str) -> list[dict[str, Any]]:
    return [r for r in records if sq_id in (r.get("strategic_question_ids") or [])]


def _new_evidence_count(evidence: list[dict[str, Any]], last_seen_at: str | None) -> int:
    """Only real-world published_date counts as "new" -- a captured-only
    (no published_date) record never counts, so a historical reacquisition
    can never masquerade as a new development, matching the same
    Evidence date-preference discipline the Intelligence Timeline already
    established (published_date only, no captured_date fallback)."""
    if not last_seen_at:
        return len(evidence)
    return sum(1 for r in evidence if str(r.get("published_date") or "") > last_seen_at[:10])


def _new_assessment_count(assessments: list[dict[str, Any]], last_seen_at: str | None) -> int:
    """Assessment.created_at is a reliable, already-established semantic
    date (see Intelligence Timeline: "created_at as its genuine semantic
    date, not a fallback"). Signal has no comparably reliable date field
    (first_seen/last_updated are ~0% populated in the real corpus per
    earlier missions this session), so "new Signal" is deliberately not
    claimed here -- signal_count stays a plain total rather than a
    fabricated freshness claim."""
    if not last_seen_at:
        return len(assessments)
    return sum(1 for a in assessments if str(a.get("created_at") or "") > last_seen_at)


def _company_monitoring_health(
    object_id: str,
    *,
    sources: list[dict[str, Any]],
    inbox_dir: Path | None,
) -> dict[str, Any] | None:
    """Only surfaced when a real, existing direct Source link exists
    (Source.linked_competitor_ids) -- never inferred for a Company with no
    such link, per mission Section 14/19."""
    from app.services.monitor_workspace import failing_source_health_rows

    linked_source_ids = {
        str(s.get("id") or "")
        for s in sources
        if object_id in (s.get("linked_competitor_ids") or [])
    }
    if not linked_source_ids:
        return None
    failing = failing_source_health_rows(sources, inbox_dir=inbox_dir)
    degraded = [row for row in failing if str(row.get("id") or "") in linked_source_ids]
    if not degraded:
        return {"status": "current"}
    return {"status": "degraded", "reason": str(degraded[0].get("reason") or degraded[0].get("status") or "")}


def present_watch(
    watch: dict[str, Any],
    *,
    entities: dict[str, dict[str, Any]],
    published_evidence: list[dict[str, Any]],
    signals: list[dict[str, Any]],
    assessments: list[dict[str, Any]],
    recommendations: list[dict[str, Any]],
    strategic_questions: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    berry_labels: dict[str, str],
    inbox_dir: Path | None = None,
) -> dict[str, Any] | None:
    """One bounded, body-free watch card. Returns None when the watched
    object no longer resolves (deleted/renamed id) rather than raising --
    a stale watch pointer is a legitimate, honestly-shown state, not an
    error that should break the whole Watchlist page."""
    watch_type = str(watch.get("watch_type") or "")
    object_id = str(watch.get("object_id") or "")
    last_seen_at = watch.get("last_seen_at")

    if watch_type == "strategic_question":
        sq = next((q for q in strategic_questions if q.get("id") == object_id), None)
        if sq is None:
            return None
        sq_evidence = _sq_linked(published_evidence, object_id)
        sq_signals = _sq_linked(signals, object_id)
        sq_assessments = _sq_linked(assessments, object_id)
        sq_recommendations = _sq_linked(recommendations, object_id)
        dates = [str(r.get("published_date") or "") for r in sq_evidence if r.get("published_date")]
        berry_ids = [str(b) for b in (sq.get("berry_ids") or []) if b]
        return {
            "watch_type": watch_type,
            "object_id": object_id,
            "name": sq.get("title") or object_id,
            "href": f"/strategic-questions/{object_id}",
            "open_href": f"/watches/open?watch_type={watch_type}&object_id={object_id}",
            "berries": [berry_labels.get(b, b) for b in berry_ids],
            "last_seen_at": last_seen_at,
            "never_seen": last_seen_at is None,
            "latest_activity": max(dates) if dates else "",
            "new_evidence_count": _new_evidence_count(sq_evidence, last_seen_at),
            "new_assessment_count": _new_assessment_count(sq_assessments, last_seen_at),
            "evidence_count": len(sq_evidence),
            "signal_count": len(sq_signals),
            "assessment_count": len(sq_assessments),
            "recommendation_count": len(sq_recommendations),
            "would_change_our_view": sorted(
                {a.get("would_change_our_view") for a in sq_assessments if a.get("would_change_our_view")}
            ),
            "monitoring": None,
        }

    entity = entities.get(object_id)
    if not entity or entity.get("entity_type") != watch_type:
        return None
    if watch_type == "geography":
        linked_evidence = _geography_evidence(published_evidence, object_id)
    else:
        linked_evidence = _company_or_variety_evidence(published_evidence, object_id)
    linked_signals = _linked_by_entity_ids(signals, object_id)
    linked_assessments = _linked_by_entity_ids(assessments, object_id)
    dates = [str(r.get("published_date") or "") for r in linked_evidence if r.get("published_date")]
    berry_ids = [str(b) for b in (entity.get("berry_ids") or []) if b]

    if watch_type == "company":
        href = f"/entities/company/{object_id}"
        open_href = f"/watches/open?watch_type=company&object_id={object_id}"
        monitoring = _company_monitoring_health(object_id, sources=sources, inbox_dir=inbox_dir)
    elif watch_type == "variety":
        href = f"/entities/variety/{object_id}"
        open_href = f"/watches/open?watch_type=variety&object_id={object_id}"
        monitoring = None
    else:
        href = f"/geographies/{object_id}"
        open_href = f"/watches/open?watch_type=geography&object_id={object_id}"
        monitoring = None

    source_type_counts: dict[str, int] = {}
    for record in linked_evidence:
        label = _humanize_source_type(str(record.get("source_type") or ""))
        source_type_counts[label] = source_type_counts.get(label, 0) + 1

    return {
        "watch_type": watch_type,
        "object_id": object_id,
        "name": entity.get("name") or object_id,
        "href": href,
        "open_href": open_href,
        "berries": [berry_labels.get(b, b) for b in berry_ids],
        "last_seen_at": last_seen_at,
        "never_seen": last_seen_at is None,
        "latest_activity": max(dates) if dates else "",
        "new_evidence_count": _new_evidence_count(linked_evidence, last_seen_at),
        "new_assessment_count": _new_assessment_count(linked_assessments, last_seen_at),
        "evidence_count": len(linked_evidence),
        "signal_count": len(linked_signals),
        "assessment_count": len(linked_assessments),
        "source_type_counts": sorted(source_type_counts.items(), key=lambda kv: -kv[1]),
        "monitoring": monitoring,
    }


def watchlist_index(
    *,
    inbox_dir: Path,
    entities: dict[str, dict[str, Any]],
    published_evidence: list[dict[str, Any]],
    signals: list[dict[str, Any]],
    assessments: list[dict[str, Any]],
    recommendations: list[dict[str, Any]],
    strategic_questions: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    berry_labels: dict[str, str],
    watch_type_filter: str = "",
    has_new_only: bool = False,
    sort: str = "new_first",
) -> list[dict[str, Any]]:
    """The Watchlist workspace's own row set -- default sort favors watches
    with genuinely new intelligence, then most recent activity, never a
    hidden relevance score. Alphabetical is available as an explicit
    alternative (mission Section 16)."""
    cards = []
    for watch in load_watches(inbox_dir):
        if watch_type_filter and watch.get("watch_type") != watch_type_filter:
            continue
        card = present_watch(
            watch,
            entities=entities,
            published_evidence=published_evidence,
            signals=signals,
            assessments=assessments,
            recommendations=recommendations,
            strategic_questions=strategic_questions,
            sources=sources,
            berry_labels=berry_labels,
            inbox_dir=inbox_dir,
        )
        if card is None:
            continue
        card["has_new"] = bool(card["new_evidence_count"] or card.get("new_assessment_count"))
        if has_new_only and not card["has_new"]:
            continue
        cards.append(card)

    if sort == "alphabetical":
        cards.sort(key=lambda c: c["name"])
    else:
        # Stable two-pass sort: newest activity first (secondary), then
        # watches with genuinely new intelligence first (primary) -- ties
        # within each group keep the newest-activity order from pass one.
        cards.sort(key=lambda c: str(c["latest_activity"]), reverse=True)
        cards.sort(key=lambda c: not c["has_new"])
    return cards
