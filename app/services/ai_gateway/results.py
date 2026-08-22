"""Normalized result shapes every provider adapter returns.

Domain code receives these dataclasses -- never a provider-native response
object, a raw `httpx.Response`, or a vendor SDK type. A new provider adapter
only needs to populate the same shapes; nothing downstream changes.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NormalizedUsage:
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None


@dataclass(frozen=True)
class NormalizedChatResponse:
    """The provider-neutral shape of one structured chat/completion call."""

    content: str
    provider: str
    model: str | None
    usage: NormalizedUsage
    latency_seconds: float
    request_id: str | None = None


@dataclass(frozen=True)
class SearchHit:
    title: str
    url: str
    snippet: str
    published_date: str | None = None


@dataclass(frozen=True)
class SearchResponse:
    provider: str
    query: str
    hits: tuple[SearchHit, ...]
    latency_seconds: float
    request_id: str | None = None


@dataclass(frozen=True)
class ResearchCitation:
    url: str
    title: str | None = None


@dataclass(frozen=True)
class ResearchResponse:
    provider: str
    model: str | None
    content: str
    citations: tuple[ResearchCitation, ...]
    web_enabled: bool
    usage: NormalizedUsage
    latency_seconds: float
    request_id: str | None = None
