"""The Alert object.

An alert wraps something that already has its own trust state (a LIVE
Development, a LIVE Competitive Move, a Market Observation, or a canonical
Evidence/Signal/Assessment record) -- it never invents a new trust tier and
never mutates the record it points at. `trust_state` on the alert is always
copied verbatim from the underlying thing, so "watched" is orthogonal to
"trusted" everywhere this renders.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

TRIGGER_TYPES = (
    "NEW_DEVELOPMENT",
    "DEVELOPMENT_UPDATED",
    "NEW_COMPETITIVE_MOVE",
    "REPEATED_MOVE_PATTERN",
    "NEW_PBR_RIGHTS_EVENT",
    "NEW_PATENT_IP_EVENT",
    "MARKET_REALITY_CHANGE",
    "NEW_TRUSTED_EVIDENCE",
    "WATCHED_STRATEGIC_QUESTION_MATCH",
)

TRIGGER_LABELS: dict[str, str] = {
    "NEW_DEVELOPMENT": "New development",
    "DEVELOPMENT_UPDATED": "Development updated",
    "NEW_COMPETITIVE_MOVE": "New competitive move",
    "REPEATED_MOVE_PATTERN": "Repeated move pattern",
    "NEW_PBR_RIGHTS_EVENT": "New PBR / rights event",
    "NEW_PATENT_IP_EVENT": "New patent / IP event",
    "MARKET_REALITY_CHANGE": "Market Reality change",
    "NEW_TRUSTED_EVIDENCE": "New trusted evidence",
    "WATCHED_STRATEGIC_QUESTION_MATCH": "Watched Strategic Question match",
}

# Groupings the /watchtower page's states (mission section 7) are built
# from -- named, not scored.
TRIGGER_GROUP: dict[str, str] = {
    "NEW_DEVELOPMENT": "competitor_moves",
    "DEVELOPMENT_UPDATED": "competitor_moves",
    "NEW_COMPETITIVE_MOVE": "competitor_moves",
    "REPEATED_MOVE_PATTERN": "competitor_moves",
    "NEW_PBR_RIGHTS_EVENT": "genetics_ip",
    "NEW_PATENT_IP_EVENT": "genetics_ip",
    "MARKET_REALITY_CHANGE": "market_moves",
    "NEW_TRUSTED_EVIDENCE": "watched_questions",
    "WATCHED_STRATEGIC_QUESTION_MATCH": "watched_questions",
}

PRIORITY_HIGH = "HIGH ATTENTION"
PRIORITY_ATTENTION = "ATTENTION"
PRIORITY_FYI = "FYI"

ALERT_STATE_OPEN = "open"
ALERT_STATE_READ = "read"
ALERT_STATE_DISMISSED = "dismissed"
ALERT_STATE_SNOOZED = "snoozed"
ALERT_STATES = (ALERT_STATE_OPEN, ALERT_STATE_READ, ALERT_STATE_DISMISSED, ALERT_STATE_SNOOZED)

# Action name (as submitted by the stakeholder UI) -> resulting state.
ALERT_ACTIONS: dict[str, str] = {
    "mark_read": ALERT_STATE_READ,
    "dismiss": ALERT_STATE_DISMISSED,
    "snooze": ALERT_STATE_SNOOZED,
    "reopen": ALERT_STATE_OPEN,
}


@dataclass
class Alert:
    id: str
    trigger_type: str
    subject_type: str
    subject_id: str
    subject_label: str
    title: str
    what_happened: str
    why_triggered: tuple[str, ...]
    priority: str
    priority_reasons: tuple[str, ...]
    generated_at: str
    first_generated_at: str
    event_at: str
    sources: list[dict[str, Any]] = field(default_factory=list)
    trust_state: str = ""
    related_development_id: str | None = None
    related_move_id: str | None = None
    market_context: dict[str, Any] | None = None
    trusted_context: list[dict[str, Any]] = field(default_factory=list)
    open_href: str = ""
    ask_berry_os_href: str = ""
    create_brief_href: str = ""
    war_room_href: str = ""

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["trigger_label"] = TRIGGER_LABELS.get(self.trigger_type, self.trigger_type)
        payload["group"] = TRIGGER_GROUP.get(self.trigger_type, "watched_questions")
        return payload
