"""Development-first Radar objects. Live plane only — never Evidence."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

EVENT_TYPES = (
    "LEADERSHIP",
    "PARTNERSHIP",
    "LICENSING",
    "VARIETY_LAUNCH",
    "GENETICS_INNOVATION",
    "PRODUCTION_EXPANSION",
    "MARKET_ACCESS",
    "PBR",
    "PATENT",
    "REGULATORY",
    "LEGAL",
    "SUPPLY_CHANGE",
    "RETAIL_PROGRAM",
    "RESEARCH",
    "OTHER",
)

CORROBORATION_SHAPES = (
    "ONE SOURCE",
    "MULTIPLE INDEPENDENT SOURCES",
    "OFFICIAL + PRESS",
    "REGISTRY + PRESS",
    "COMPANY CLAIM + INDEPENDENT REPORT",
    "COMMUNITY / CHATTER — UNVERIFIED",
)

TRUST_LIVE = "LIVE / UNREVIEWED DEVELOPMENT"
TRUST_EVIDENCE = "TRUSTED EVIDENCE"
TRUST_ASSESSMENT = "ASSESSMENT"

WEAK_SIGNAL_LABEL = "COMMUNITY / CHATTER — UNVERIFIED"

EVOLUTION_KINDS = ("FIRST_SEEN", "LATEST_UPDATE", "NEW_SOURCE", "NEW_FACT", "STATUS_CHANGE")

SECTION_DEFS: tuple[tuple[str, str, str], ...] = (
    ("emerging_now", "Emerging now", "Things moving that may matter before they become obvious."),
    ("worth_watching", "Worth watching", "Single-source or early items that still name a real actor."),
    ("genetics_varieties", "Genetics & varieties", "Launches, breeding, and genetics innovation."),
    ("competitor_moves", "Competitor moves", "Leadership, partnerships, and licensing."),
    ("market_supply", "Market / supply", "Production, trade, retail programs, and supply pressure."),
    ("regulatory_ip", "Regulatory / IP", "PBR, patents, legal, and regulatory moves."),
    ("weak_signals", "Weak signals", "Public social discovery. Unverified unless corroborated."),
    ("recently_corroborated", "Recently corroborated", "A second independent source has now shown up."),
)

CACHE_TTL_SECONDS = 3600
RADAR_WINDOW = "30d"


@dataclass
class SourceRef:
    url: str
    title: str
    publisher: str
    domain: str
    published_date: str | None
    provider: str
    query_id: str
    snippet: str = ""
    official: bool = False
    registry: bool = False
    social: bool = False
    company_claim: bool = False
    syndicated: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EvolutionEvent:
    at: str
    kind: str
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Development:
    id: str
    title: str
    event_type: str
    what_happened: str
    first_seen: str
    latest_update: str
    event_date: str | None
    company_ids: tuple[str, ...] = ()
    variety_ids: tuple[str, ...] = ()
    geography_ids: tuple[str, ...] = ()
    berry_ids: tuple[str, ...] = ()
    company_names: tuple[str, ...] = ()
    variety_names: tuple[str, ...] = ()
    geography_labels: tuple[str, ...] = ()
    berry_labels: tuple[str, ...] = ()
    tag_provenance: tuple[dict[str, str], ...] = ()
    sources: list[SourceRef] = field(default_factory=list)
    live_hit_urls: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    assessment_ids: tuple[str, ...] = ()
    corroboration: str = "ONE SOURCE"
    status: str = "emerging"
    provenance: tuple[str, ...] = ()
    radar_reasons: tuple[str, ...] = ()
    trust_state: str = TRUST_LIVE
    weak_signal_label: str | None = None
    proposed_related_ids: tuple[str, ...] = ()
    market_context: dict[str, Any] | None = None
    trusted_context: list[dict[str, Any]] = field(default_factory=list)
    google_stack_would_find: bool = False
    watchlist_matches: tuple[dict[str, Any], ...] = ()
    evolution: list[EvolutionEvent] = field(default_factory=list)
    section: str = "worth_watching"
    source_count: int = 0
    independent_source_count: int = 0
    publisher_diversity: int = 0

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return payload


@dataclass
class RadarEdition:
    generated_at: str
    window: str
    latency_seconds: float
    freshness_label: str
    cache_status: str
    expires_at: str | None
    trust_label: str
    developments: list[Development]
    sections: list[dict[str, Any]]
    stats: dict[str, Any]
    query_failures: list[dict[str, str]] = field(default_factory=list)
    provider_telemetry: dict[str, dict[str, int]] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "window": self.window,
            "latency_seconds": self.latency_seconds,
            "freshness_label": self.freshness_label,
            "cache_status": self.cache_status,
            "expires_at": self.expires_at,
            "trust_label": self.trust_label,
            "developments": [row.as_dict() for row in self.developments],
            "sections": self.sections,
            "stats": self.stats,
            "query_failures": self.query_failures,
            "provider_telemetry": self.provider_telemetry,
        }


def development_from_dict(row: dict[str, Any]) -> Development:
    sources = [SourceRef(**item) if not isinstance(item, SourceRef) else item for item in row.get("sources") or []]
    evolution = [
        EvolutionEvent(**item) if not isinstance(item, EvolutionEvent) else item
        for item in row.get("evolution") or []
    ]
    known = {key: row[key] for key in Development.__dataclass_fields__ if key in row and key not in {"sources", "evolution"}}
    for key in (
        "company_ids",
        "variety_ids",
        "geography_ids",
        "berry_ids",
        "company_names",
        "variety_names",
        "geography_labels",
        "berry_labels",
        "tag_provenance",
        "live_hit_urls",
        "evidence_ids",
        "assessment_ids",
        "provenance",
        "radar_reasons",
        "proposed_related_ids",
        "watchlist_matches",
    ):
        if key in known and isinstance(known[key], list):
            known[key] = tuple(known[key])
    return Development(sources=sources, evolution=evolution, **known)
