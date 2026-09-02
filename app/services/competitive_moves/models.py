"""Competitive Move objects derived from Radar Developments.

Not a second event system. LIVE plane only — never Evidence.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.services.emerging_radar.models import TRUST_LIVE

MOVE_TYPES = (
    "EXPANSION",
    "MARKET_ENTRY",
    "GENETICS_LAUNCH",
    "VARIETY_COMMERCIALIZATION",
    "LICENSING",
    "PARTNERSHIP",
    "ACQUISITION / INVESTMENT",
    "LEADERSHIP",
    "R&D / TECHNOLOGY",
    "PBR / IP",
    "RETAIL_PROGRAM",
    "SUPPLY / PRODUCTION_SHIFT",
    "LEGAL / COMPETITIVE_CONSTRAINT",
    "OTHER",
)

MOVE_LABELS = {
    "EXPANSION": "Expansion",
    "MARKET_ENTRY": "Market entry",
    "GENETICS_LAUNCH": "Genetics launch",
    "VARIETY_COMMERCIALIZATION": "Variety commercialization",
    "LICENSING": "Licensing",
    "PARTNERSHIP": "Partnership",
    "ACQUISITION / INVESTMENT": "Acquisition / investment",
    "LEADERSHIP": "Leadership",
    "R&D / TECHNOLOGY": "R&D / technology",
    "PBR / IP": "PBR / IP",
    "RETAIL_PROGRAM": "Retail program",
    "SUPPLY / PRODUCTION_SHIFT": "Supply / production shift",
    "LEGAL / COMPETITIVE_CONSTRAINT": "Legal / competitive constraint",
    "OTHER": "Other",
}

TRUST_LIVE_MOVE = "LIVE / UNREVIEWED MOVE"

BOARD_SECTIONS: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    ("most_active", "Most active competitors", "Who is moving, by distinct move types and recency — not an activity score.", ()),
    ("expansion", "Expansion", "Production, packing, and supply-footprint moves.", ("EXPANSION", "SUPPLY / PRODUCTION_SHIFT")),
    ("genetics_ip", "Genetics / IP", "Launches, commercialization, licensing, and rights filings.", ("GENETICS_LAUNCH", "VARIETY_COMMERCIALIZATION", "LICENSING", "PBR / IP", "R&D / TECHNOLOGY")),
    ("market_entry", "Market entry", "New geographies and market-access developments.", ("MARKET_ENTRY",)),
    ("partnerships", "Partnerships", "Alliances, platforms, and capital events.", ("PARTNERSHIP", "ACQUISITION / INVESTMENT")),
    ("leadership", "Leadership", "Innovation and executive appointments.", ("LEADERSHIP",)),
)

PATTERN_THEMES = (
    ("GENETICS / COMMERCIALIZATION", frozenset({"GENETICS_LAUNCH", "VARIETY_COMMERCIALIZATION", "LICENSING", "PBR / IP", "PARTNERSHIP"})),
    ("EXPANSION / MARKET FOOTPRINT", frozenset({"EXPANSION", "MARKET_ENTRY", "SUPPLY / PRODUCTION_SHIFT", "RETAIL_PROGRAM"})),
    ("LEADERSHIP + GEOGRAPHY", frozenset({"LEADERSHIP", "MARKET_ENTRY", "EXPANSION"})),
    ("IP / LEGAL CONSTRAINT", frozenset({"PBR / IP", "LEGAL / COMPETITIVE_CONSTRAINT"})),
)


@dataclass
class TimelineRow:
    date: str
    move_type: str
    what_happened: str
    source: str
    geography: str
    variety_or_berry: str
    trust_state: str
    development_id: str
    href: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CompetitiveMove:
    id: str
    company_id: str
    company_name: str
    move_type: str
    title: str
    what_happened: str
    why_move: tuple[str, ...]
    first_seen: str
    latest_update: str
    geography_ids: tuple[str, ...] = ()
    geography_labels: tuple[str, ...] = ()
    berry_ids: tuple[str, ...] = ()
    berry_labels: tuple[str, ...] = ()
    variety_ids: tuple[str, ...] = ()
    variety_names: tuple[str, ...] = ()
    supporting_development_ids: tuple[str, ...] = ()
    supporting_sources: list[dict[str, Any]] = field(default_factory=list)
    trusted_context: list[dict[str, Any]] = field(default_factory=list)
    market_context: dict[str, Any] | None = None
    strategic_questions: tuple[dict[str, str], ...] = ()
    provenance: tuple[str, ...] = ()
    exa_mattered: bool = False
    corroboration: str = "ONE SOURCE"
    trust_state: str = TRUST_LIVE_MOVE
    development_trust_state: str = TRUST_LIVE
    timeline: list[TimelineRow] = field(default_factory=list)

    @property
    def move_label(self) -> str:
        return MOVE_LABELS.get(self.move_type, self.move_type)

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["move_label"] = self.move_label
        payload["timeline"] = [row.as_dict() if hasattr(row, "as_dict") else row for row in self.timeline]
        return payload


@dataclass
class CompanyPattern:
    company_id: str
    company_name: str
    theme: str
    label: str
    supporting_move_types: tuple[str, ...]
    supporting_move_ids: tuple[str, ...]
    why: str
    latest_update: str
    move_count: int

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CompanyMomentum:
    company_id: str
    company_name: str
    move_count: int
    move_types: tuple[str, ...]
    latest_update: str
    geographies: tuple[str, ...]
    berries: tuple[str, ...]
    href: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["move_type_labels"] = [MOVE_LABELS.get(item, item) for item in self.move_types]
        return payload


@dataclass
class MovesBoard:
    generated_at: str
    freshness_label: str
    cache_status: str
    trust_label: str
    moves: list[CompetitiveMove]
    patterns: list[CompanyPattern]
    momentum: list[CompanyMomentum]
    sections: list[dict[str, Any]]
    featured_timeline: dict[str, Any] | None
    stats: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "freshness_label": self.freshness_label,
            "cache_status": self.cache_status,
            "trust_label": self.trust_label,
            "moves": [row.as_dict() for row in self.moves],
            "patterns": [row.as_dict() for row in self.patterns],
            "momentum": [row.as_dict() for row in self.momentum],
            "sections": self.sections,
            "featured_timeline": self.featured_timeline,
            "stats": self.stats,
        }
