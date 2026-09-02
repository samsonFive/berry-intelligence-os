"""Authoritative event overlay on existing registry/patent records.

Decision (Phase 2): do not create a new object type.

PVP and patent events are time-based structured intelligence, not news
articles and not Publications. Existing records already carry the fields:

- Variety candidates (inbox/variety_candidates) hold USDA/CPVO
  application, grant, status, and dates.
- Patent-monitor discovery hits / review drafts hold publication,
  grant, assignee, and filing dates.

This module classifies those existing records into event kinds. It never
auto-merges identity and never writes trusted Evidence.
"""

from __future__ import annotations

from typing import Any

PVP_APPLICATION_FILED = "PVP_APPLICATION_FILED"
PVP_GRANTED = "PVP_GRANTED"
PVP_STATUS_CHANGED = "PVP_STATUS_CHANGED"
PATENT_APPLICATION_PUBLISHED = "PATENT_APPLICATION_PUBLISHED"
PATENT_GRANTED = "PATENT_GRANTED"
ASSIGNMENT_OWNERSHIP_CHANGE = "ASSIGNMENT_OWNERSHIP_CHANGE"

EVENT_KINDS = (
    PVP_APPLICATION_FILED,
    PVP_GRANTED,
    PVP_STATUS_CHANGED,
    PATENT_APPLICATION_PUBLISHED,
    PATENT_GRANTED,
    ASSIGNMENT_OWNERSHIP_CHANGE,
)

# Existing record types that can carry an event overlay.
HOST_VARIETY_CANDIDATE = "variety_candidate"
HOST_PATENT_FILING = "patent_filing"

DECISION = {
    "new_object_type": False,
    "host_records": [HOST_VARIETY_CANDIDATE, HOST_PATENT_FILING],
    "publication_semantics": False,
    "auto_canonical_merge": False,
    "trust_promotion": False,
    "rationale": (
        "Variety candidates already model registry identity proposals. "
        "Patent-monitor filings already model USPTO/Google Patents discovery. "
        "An event_kind + event_date overlay is enough for time-based "
        "intelligence without a third object family."
    ),
}


def classify_pvp_event(row: dict[str, Any]) -> dict[str, Any]:
    status = str(row.get("registration_status") or row.get("status") or "").lower()
    issued = str(row.get("grant_date") or row.get("issued_date") or "").strip()
    filed = str(row.get("application_date") or row.get("filing_date") or "").strip()
    status_date = str(row.get("status_date") or "").strip()
    if issued or "issued" in status or "granted" in status or "certificate" in status and "pending" not in status:
        kind = PVP_GRANTED
        event_date = issued or status_date or filed
    elif any(token in status for token in ("abandon", "expired", "terminated", "withdrawn", "denied")):
        kind = PVP_STATUS_CHANGED
        event_date = status_date or issued or filed
    else:
        kind = PVP_APPLICATION_FILED
        event_date = filed or status_date
    return {
        "event_kind": kind,
        "event_date": event_date or None,
        "host_record_type": HOST_VARIETY_CANDIDATE,
        "trust_state": "UNREVIEWED_REGISTRY",
    }


def classify_patent_event(filing: dict[str, Any]) -> dict[str, Any]:
    granted = str(filing.get("grant_date") or "").strip()
    published = str(filing.get("publication_date") or "").strip()
    assignment_changed = bool(filing.get("assignment_changed") or filing.get("previous_assignee"))
    if assignment_changed:
        kind = ASSIGNMENT_OWNERSHIP_CHANGE
        event_date = str(filing.get("assignment_date") or published or granted)
    elif granted:
        kind = PATENT_GRANTED
        event_date = granted
    else:
        kind = PATENT_APPLICATION_PUBLISHED
        event_date = published or str(filing.get("filing_date") or "")
    return {
        "event_kind": kind,
        "event_date": event_date or None,
        "host_record_type": HOST_PATENT_FILING,
        "trust_state": "UNREVIEWED_PATENT",
    }


def attach_event(record: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Copy-on-write overlay. Does not confirm identity."""
    updated = dict(record)
    updated["authoritative_event"] = overlay
    updated["auto_confirmed"] = False
    return updated
