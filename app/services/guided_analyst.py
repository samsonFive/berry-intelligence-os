"""Read-only guided-analyst helpers. GET/render never mutates trust."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from app.services.chronology import parse_stamp
from app.services.variety_universe.candidates import load_variety_candidates
from app.services.watchlist import load_watches

VARIETY_WAITING_STATES = frozenset({"possible_alias", "unknown"})


def count_phrase(count: int, singular: str, plural: str | None = None) -> str:
    noun = singular if count == 1 else (plural or f"{singular}s")
    return f"{count:,} {noun}"


def nav_count_labels(counts: dict[str, Any]) -> dict[str, str]:
    """Semantic labels for displayed nav/queue counts. Never imply deletion."""

    review_now = int(counts.get("review_now") or 0)
    atomic = int(counts.get("atomic_pending") or 0)
    variety = int(counts.get("variety_identity") or 0)
    emerging = int(counts.get("emerging_signals") or 0)
    brief = int(counts.get("brief_action") or 0)
    reading = int(counts.get("reading_action") or 0)
    testing = int(counts.get("testing_action") or 0)
    monitoring = int(counts.get("monitoring_inventory") or 0)
    alerts = int(counts.get("signal_alerts") or 0)
    return {
        "review_now": count_phrase(
            review_now, "Publication awaiting review", "Publications awaiting review"
        ),
        "atomic_pending": count_phrase(
            atomic,
            "Atomic Evidence proposal awaiting review",
            "Atomic Evidence proposals awaiting review",
        ),
        "variety_identity": count_phrase(
            variety, "Variety identity awaiting review", "Variety identities awaiting review"
        ),
        "emerging_signals": count_phrase(
            emerging, "Signal candidate awaiting review", "Signal candidates awaiting review"
        ),
        "brief_action": count_phrase(
            brief,
            "item new since last Morning Brief",
            "items new since last Morning Brief",
        ),
        "reading_action": count_phrase(
            reading, "item remaining in the Reading Queue", "items remaining in the Reading Queue"
        ),
        "testing_action": count_phrase(
            testing, "item remaining in Claim testing", "items remaining in Claim testing"
        ),
        "monitoring_inventory": count_phrase(
            monitoring, "item on the Monitoring queue", "items on the Monitoring queue"
        ),
        "signal_alerts": count_phrase(alerts, "open Signal alert", "open Signal alerts"),
    }


def atomic_pending_count(records: list[dict[str, Any]]) -> int:
    return sum(
        1
        for record in records
        if record.get("evidence_role") == "atomic_evidence"
        and record.get("status", "draft") != "rejected"
    )


def variety_identity_waiting_count(inbox_dir: Path) -> int:
    """Unresolved candidate identities. Distinct/confirmed/rejected are not waiting."""

    waiting = 0
    for row in load_variety_candidates(inbox_dir):
        if row.get("status") == "rejected":
            continue
        if row.get("identity_state") in VARIETY_WAITING_STATES:
            waiting += 1
    return waiting


def watch_monitoring_snapshot(*, inbox_dir: Path) -> dict[str, Any]:
    """Watchlist presence only. Never marks a Watch seen."""

    watches = load_watches(inbox_dir)
    unchecked = sum(1 for row in watches if not row.get("last_seen_at"))
    return {
        "watch_count": len(watches),
        "unchecked_count": unchecked,
        "has_watches": bool(watches),
    }


def build_attention_queues(
    *,
    publication_waiting: int,
    publication_since_brief: int | None,
    atomic_waiting: int,
    variety_waiting: int,
    source_failing: int,
    source_overdue: int,
    source_blocked: int,
    retrying: int,
    authoring_mode: bool,
) -> list[dict[str, Any]]:
    """Today attention cards. Waiting totals only; no invented last-visit deltas."""

    source_problems = source_failing + source_overdue + source_blocked
    queues = [
        {
            "key": "publication",
            "title": "Publication Review",
            "href": "/pending",
            "waiting": publication_waiting,
            "waiting_label": count_phrase(
                publication_waiting,
                "Publication awaiting review",
                "Publications awaiting review",
            ),
            "recent_label": (
                count_phrase(
                    publication_since_brief,
                    "new since last Morning Brief",
                    "new since last Morning Brief",
                )
                if publication_since_brief is not None
                else ""
            ),
            "contains": "Newly discovered Publications that have not yet been accepted into the trusted intelligence workflow.",
            "after": "Continue/promote means the Publication may proceed to downstream evidence processing. Rejecting it does not erase the original Source record. Dismiss hides a draft from triage and keeps the file.",
            "action": "Open Publication Review",
            "empty": "No Publications are waiting for review.",
            "show": True,
        },
        {
            "key": "atomic",
            "title": "Atomic Evidence Review",
            "href": "/review?kind=atomic",
            "waiting": atomic_waiting,
            "waiting_label": count_phrase(
                atomic_waiting,
                "Atomic Evidence proposal awaiting review",
                "Atomic Evidence proposals awaiting review",
            ),
            "recent_label": "",
            "contains": "Proposed individual intelligence statements extracted from a trusted Publication. Each proposal is AI PROPOSED until a human reviews it.",
            "after": "Reviewing one statement accepts or rejects that statement only. It does not publish the parent Publication, create a Signal, or delete the source wording.",
            "action": "Open Atomic Review",
            "empty": "No Atomic Evidence proposals are available. Automated extraction remains disabled or unqualified until a qualified model and trusted source bodies are available.",
            "show": authoring_mode or atomic_waiting > 0,
        },
        {
            "key": "variety",
            "title": "Variety Identity Review",
            "href": "/varieties/candidates",
            "waiting": variety_waiting,
            "waiting_label": count_phrase(
                variety_waiting,
                "Variety identity awaiting review",
                "Variety identities awaiting review",
            ),
            "recent_label": "",
            "contains": "Public cultivar names discovered as CANDIDATE identities — not trusted Varieties.",
            "after": "A decision records DISTINCT, POSSIBLE ALIAS, UNKNOWN, or CONFIRMED SAME. Confirming identity does not invent a new trusted Variety.",
            "action": "Open Variety identity review",
            "empty": "No Variety identities are waiting for review.",
            "show": authoring_mode or variety_waiting > 0,
        },
        {
            "key": "sources",
            "title": "Source problems",
            "href": "/sources",
            "waiting": source_problems,
            "waiting_label": count_phrase(
                source_problems, "Source needing operator attention", "Sources needing operator attention"
            ),
            "recent_label": "",
            "contains": (
                f"{source_failing} failing · {source_overdue} overdue · {source_blocked} blocked"
                if source_problems
                else "No Sources are currently failing, overdue, or blocked."
            ),
            "after": "Opening Source Health does not retry collection or change trust. Check or pause a Source from its row.",
            "action": "Open Source Health",
            "empty": "No Sources are currently failing, overdue, or blocked.",
            "show": True,
        },
    ]
    if retrying:
        queues.append(
            {
                "key": "retry",
                "title": "Collection retry / operator action",
                "href": "/collection-ops",
                "waiting": retrying,
                "waiting_label": count_phrase(
                    retrying, "Source currently retrying", "Sources currently retrying"
                ),
                "recent_label": "",
                "contains": "Sources in retry/backoff. This is OPERATOR ACTION status, not a review queue.",
                "after": "Viewing Collection Ops never starts a run, retries a Source, or clears a lock.",
                "action": "Open Collection Ops",
                "empty": "",
                "show": True,
            }
        )
    return [row for row in queues if row.get("show")]


def freshness_clock_label(value: Any) -> str:
    """Honest display for a freshness ISO stamp. Empty if unknown."""

    parsed = parse_stamp(value)
    if parsed is None:
        return ""
    return parsed.strftime("%b %d, %Y, %H:%M UTC")
