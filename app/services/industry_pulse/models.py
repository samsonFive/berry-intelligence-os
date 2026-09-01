"""Normalized Industry Pulse discovery hits.

Discovery material only. Never Evidence. Never a Source onboard.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class DiscoveryHit:
    title: str
    url: str
    source_domain: str
    published_date: str | None
    snippet: str
    query_id: str
    query_text: str
    geography: str
    berry: str | None
    topic: str | None
    provider: str
    origin_publisher_name: str | None = None
    origin_publisher_url: str | None = None
    wrapper_url: str | None = None
    qualifying: bool = False
    qualify_reason: str = ""
    duplicate_of: str | None = None
    miss_classification: str | None = None
    miss_label: str | None = None
    collection_status: str | None = None
    known_source: bool = False
    collected: bool = False
    novel_domain: bool = False
    already_represented: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WindowSlice:
    window: str
    discovered: int
    qualifying: int
    novel: int
    known: int
    duplicates: int
    unknown_date: int
    by_geography: dict[str, dict[str, int]] = field(default_factory=dict)
    by_berry: dict[str, dict[str, int]] = field(default_factory=dict)
    query_yield_by_geography: dict[str, dict[str, int]] = field(default_factory=dict)
    query_yield_by_berry: dict[str, dict[str, int]] = field(default_factory=dict)
    miss_counts: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
