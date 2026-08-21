"""Cadence-aware freshness classification for a monitored Source.

Extends the existing operational-status model (app/services/collection_status.py,
app/services/media_discovery.py's per-source discovery state) rather than
building a parallel dashboard. The key distinction this module exists to
make legible to an analyst: "no new stories since we last checked" (CURRENT
or DUE, depending on cadence) is not the same fact as "we haven't actually
managed to check this source lately" (STALE or FAILING) -- both can look
identical from a headline count alone, but they call for very different
operator action.

A source's discovery `update_cadence` governs what "on time" means: a
weekly trade-press feed is not stale after one quiet day, and a quarterly
data release is not stale after a quiet month. Freshness state is always
computed from `last_success_at` (a check that actually completed), never
from `last_checked_at` alone (an attempt, which may have failed).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

CURRENT = "CURRENT"
DUE = "DUE"
STALE = "STALE"
FAILING = "FAILING"
BLOCKED = "BLOCKED"
QUIET = "QUIET"
MANUAL = "MANUAL"

FRESHNESS_LABELS = {
    CURRENT: "Current",
    DUE: "Due for a check",
    STALE: "Stale",
    FAILING: "Failing",
    BLOCKED: "Blocked",
    QUIET: "Quiet",
    MANUAL: "Manual / non-automated",
}

# Text signals confirming the *publisher itself* rejected the request (a
# bot-wall or access-control response), not a transport/parse failure on
# our end. Deliberately narrow and status-code-anchored -- this only
# labels an already-captured error string, it never changes how the
# request was made (no user-agent spoofing, no bypass logic). Real example
# this exists for: Growing Produce's WAF returning 403 Forbidden to the
# collector's honest, self-identifying User-Agent (see
# app/services/article_acquisition.py's ARTICLE_FETCH_USER_AGENT).
_BLOCKED_SIGNALS = (
    "403 forbidden",
    "401 unauthorized",
    "access denied",
    "access to this page has been denied",
)

# Canonical home for cadence-to-days; app/main.py imports this rather than
# keeping its own copy, so the UI's "next check due" math and this module's
# freshness classification can never silently drift apart.
SOURCE_CADENCE_DAYS: dict[str, int] = {
    "realtime": 1,
    "weekly": 7,
    "biweekly": 14,
    "monthly": 30,
    "quarterly": 90,
    "annual": 365,
    # event_driven has no fixed schedule -- never "due", only checked manually.
}


def _parse_date(value: Any) -> date | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


def _looks_blocked(error_text: str | None) -> bool:
    if not error_text:
        return False
    lowered = error_text.lower()
    return any(signal in lowered for signal in _BLOCKED_SIGNALS)


def is_discoverable(source: dict[str, Any]) -> bool:
    discovery = source.get("discovery") or {}
    return bool(discovery.get("adapter") and (discovery.get("feed_url") or discovery.get("feed_urls")))


@dataclass(frozen=True)
class SourceFreshness:
    state: str
    label: str
    last_checked_at: str | None
    last_success_at: str | None
    next_check_due: str | None
    latest_item_published_at: str | None
    latest_item_captured_at: str | None
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "label": self.label,
            "last_checked_at": self.last_checked_at,
            "last_success_at": self.last_success_at,
            "next_check_due": self.next_check_due,
            "latest_item_published_at": self.latest_item_published_at,
            "latest_item_captured_at": self.latest_item_captured_at,
            "reason": self.reason,
        }


def classify_source_freshness(
    source: dict[str, Any],
    *,
    discovery_state: dict[str, Any] | None,
    latest_item_published_at: str | None = None,
    latest_item_captured_at: str | None = None,
    today: date | None = None,
) -> SourceFreshness:
    today = today or date.today()
    last_checked_at = (discovery_state or {}).get("last_checked_at")
    last_success_at = (discovery_state or {}).get("last_success_at")
    cadence = source.get("update_cadence")
    cadence_days = SOURCE_CADENCE_DAYS.get(cadence)

    if not is_discoverable(source):
        return SourceFreshness(
            state=MANUAL, label=FRESHNESS_LABELS[MANUAL],
            last_checked_at=last_checked_at, last_success_at=last_success_at, next_check_due=None,
            latest_item_published_at=latest_item_published_at, latest_item_captured_at=latest_item_captured_at,
            reason="No discovery adapter configured; this source is reviewed manually, not automatically checked.",
        )

    if discovery_state is None:
        return SourceFreshness(
            state=STALE, label=FRESHNESS_LABELS[STALE],
            last_checked_at=None, last_success_at=None, next_check_due=None,
            latest_item_published_at=latest_item_published_at, latest_item_captured_at=latest_item_captured_at,
            reason="Discoverable, but no discovery run has ever been recorded for this source.",
        )

    if (discovery_state or {}).get("status") == "error":
        error_text = discovery_state.get("error")
        if _looks_blocked(error_text):
            return SourceFreshness(
                state=BLOCKED, label=FRESHNESS_LABELS[BLOCKED],
                last_checked_at=last_checked_at, last_success_at=last_success_at, next_check_due=None,
                latest_item_published_at=latest_item_published_at, latest_item_captured_at=latest_item_captured_at,
                reason=error_text,
            )
        return SourceFreshness(
            state=FAILING, label=FRESHNESS_LABELS[FAILING],
            last_checked_at=last_checked_at, last_success_at=last_success_at, next_check_due=None,
            latest_item_published_at=latest_item_published_at, latest_item_captured_at=latest_item_captured_at,
            reason=error_text or "Most recent discovery attempt failed.",
        )

    if not last_success_at:
        return SourceFreshness(
            state=STALE, label=FRESHNESS_LABELS[STALE],
            last_checked_at=last_checked_at, last_success_at=None, next_check_due=None,
            latest_item_published_at=latest_item_published_at, latest_item_captured_at=latest_item_captured_at,
            reason="Discovery has been attempted but has never yet completed successfully.",
        )

    last_success_date = _parse_date(last_success_at)
    if cadence_days is None or last_success_date is None:
        return SourceFreshness(
            state=CURRENT, label=FRESHNESS_LABELS[CURRENT],
            last_checked_at=last_checked_at, last_success_at=last_success_at, next_check_due=None,
            latest_item_published_at=latest_item_published_at, latest_item_captured_at=latest_item_captured_at,
            reason="Event-driven or uncadenced source; last check succeeded and no fixed schedule applies.",
        )

    due_date = last_success_date + timedelta(days=cadence_days)
    due_iso = due_date.isoformat()
    if today < due_date:
        # "new" is only present on runs that actually recorded per-source
        # counts (app/services/media_discovery.py's discovery-state write).
        # A source that checked fine but found nothing new is QUIET, not a
        # weaker form of CURRENT -- an analyst reading "no new stories"
        # should not have to wonder whether the check even ran. Missing
        # "new" (older/legacy state) falls back to CURRENT rather than
        # guessing.
        new_count = (discovery_state or {}).get("new")
        if new_count == 0:
            return SourceFreshness(
                state=QUIET, label=FRESHNESS_LABELS[QUIET],
                last_checked_at=last_checked_at, last_success_at=last_success_at, next_check_due=due_iso,
                latest_item_published_at=latest_item_published_at, latest_item_captured_at=latest_item_captured_at,
                reason=f"Checked successfully within its {cadence or 'expected'} cadence; no new items found.",
            )
        return SourceFreshness(
            state=CURRENT, label=FRESHNESS_LABELS[CURRENT],
            last_checked_at=last_checked_at, last_success_at=last_success_at, next_check_due=due_iso,
            latest_item_published_at=latest_item_published_at, latest_item_captured_at=latest_item_captured_at,
            reason=f"Checked successfully within its {cadence or 'expected'} cadence.",
        )

    overdue_days = (today - due_date).days
    if overdue_days > cadence_days:
        return SourceFreshness(
            state=STALE, label=FRESHNESS_LABELS[STALE],
            last_checked_at=last_checked_at, last_success_at=last_success_at, next_check_due=due_iso,
            latest_item_published_at=latest_item_published_at, latest_item_captured_at=latest_item_captured_at,
            reason=f"Overdue by {overdue_days} days -- more than a full {cadence or ''} cycle past its last successful check.",
        )
    return SourceFreshness(
        state=DUE, label=FRESHNESS_LABELS[DUE],
        last_checked_at=last_checked_at, last_success_at=last_success_at, next_check_due=due_iso,
        latest_item_published_at=latest_item_published_at, latest_item_captured_at=latest_item_captured_at,
        reason=f"Past its {cadence or 'expected'} cadence window; due for another check.",
    )


def aggregate_source_coverage(freshness_by_source: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Compact analyst-facing summary across every discoverable source's
    already-computed freshness (SourceFreshness.as_dict(), e.g.
    app/main.py's sources_page_context() freshness_by_source) -- "SOURCE
    COVERAGE / N current / N due / N failing" (Continuous Intelligence
    Refresh, 2026-08-18). Reuses classify_source_freshness()'s own
    per-source state rather than re-deriving freshness; this is purely an
    aggregation. Deliberately does NOT report a "next scheduled refresh" --
    this module has no way to know whether a recurring scheduler is
    actually installed or what its real cadence is, and fabricating a
    next-run time was explicitly ruled out. A caller that knows the real
    scheduler configuration (e.g. the deployed bios-collection.timer's
    OnCalendar=) may report that separately."""
    counts = {CURRENT: 0, DUE: 0, STALE: 0, FAILING: 0, BLOCKED: 0, QUIET: 0, MANUAL: 0}
    last_refresh: str | None = None
    for freshness in freshness_by_source.values():
        state = freshness.get("state")
        counts[state] = counts.get(state, 0) + 1
        success_at = freshness.get("last_success_at")
        if success_at and (last_refresh is None or success_at > last_refresh):
            last_refresh = success_at
    return {
        "sources_total": len(freshness_by_source),
        "current": counts[CURRENT],
        "due": counts[DUE],
        "stale": counts[STALE],
        "failing": counts[FAILING],
        "blocked": counts[BLOCKED],
        "quiet": counts[QUIET],
        "manual": counts[MANUAL],
        "last_refresh_at": last_refresh,
    }


def index_latest_item_dates(
    *,
    discovered_items: list[dict[str, Any]],
    published_evidence: list[dict[str, Any]],
) -> dict[str, tuple[str | None, str | None]]:
    """One-pass latest dates per source. Avoids O(sources × items) on Source Health."""

    published_dates: dict[str, list[str]] = {}
    captured_dates: dict[str, list[str]] = {}

    def _add(source_id: Any, published: Any, captured: Any) -> None:
        text = str(source_id or "")
        if not text:
            return
        if published:
            published_dates.setdefault(text, []).append(str(published))
        if captured:
            captured_dates.setdefault(text, []).append(str(captured))

    for item in discovered_items:
        _add(item.get("source_id"), item.get("published_date"), item.get("first_seen_at"))
    for record in published_evidence:
        _add(record.get("source_id"), record.get("published_date"), record.get("captured_date"))
    source_ids = set(published_dates) | set(captured_dates)
    return {
        source_id: (
            max(published_dates[source_id]) if source_id in published_dates else None,
            max(captured_dates[source_id]) if source_id in captured_dates else None,
        )
        for source_id in source_ids
    }


def latest_item_dates(
    *,
    discovered_items: list[dict[str, Any]],
    published_evidence: list[dict[str, Any]],
    source_id: str,
) -> tuple[str | None, str | None]:
    """Newest real publication date and newest capture date this project
    actually has on file for a source, across both pending discoveries and
    trusted published Evidence -- so "no new stories" can be judged against
    what we would show an analyst, not only what has cleared review.

    Single-source scan for callers that already hold the item lists and need
    one id (collection status). Source Health uses `index_latest_item_dates`
    once per page instead of calling this in a loop.
    """
    published_dates = [
        item.get("published_date") for item in discovered_items
        if item.get("source_id") == source_id and item.get("published_date")
    ]
    captured_dates = [
        item.get("first_seen_at") for item in discovered_items
        if item.get("source_id") == source_id and item.get("first_seen_at")
    ]
    for record in published_evidence:
        if record.get("source_id") != source_id:
            continue
        if record.get("published_date"):
            published_dates.append(record["published_date"])
        if record.get("captured_date"):
            captured_dates.append(record["captured_date"])
    return (
        max(published_dates) if published_dates else None,
        max(captured_dates) if captured_dates else None,
    )
