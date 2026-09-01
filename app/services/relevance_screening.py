"""Cheap pre-transcription relevance triage.

This is operational screening, not trusted intelligence. Scores use title,
publisher description, source, and date only. Whisper/transcription should
not run on clearly irrelevant items.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.services.deterministic_tagging import infer_berry_ids_from_text

HIGH_WEIGHT_TERMS: tuple[tuple[str, int], ...] = (
    ("blueberries", 8),
    ("blueberry", 8),
    ("strawberries", 7),
    ("strawberry", 7),
    ("raspberries", 7),
    ("raspberry", 7),
    ("blackberries", 7),
    ("blackberry", 7),
    ("arándano", 8),
    ("arandano", 8),
    ("cultivar", 6),
    ("pbr", 6),
    ("variety", 5),
    ("varieties", 5),
    ("breeding", 6),
    ("genetics", 6),
    ("genetic", 5),
)

MEDIUM_WEIGHT_TERMS: tuple[tuple[str, int], ...] = (
    ("grower", 3),
    ("growers", 3),
    ("acreage", 3),
    ("yield", 3),
    ("pricing", 3),
    ("price", 2),
    ("season", 2),
    ("retail", 2),
    ("shipper", 3),
    ("exporter", 3),
    ("export", 2),
    ("production", 2),
    ("harvest", 3),
    ("packing", 2),
    ("chile", 2),
    ("peru", 2),
    ("mexico", 2),
    ("morocco", 2),
    ("spain", 2),
    ("poland", 2),
    ("california", 2),
    ("oregon", 2),
    ("washington", 2),
    ("michigan", 2),
    ("florida", 2),
    ("georgia", 2),
)

LOW_WEIGHT_TERMS: tuple[tuple[str, int], ...] = (
    ("disease", 1),
    ("shelf life", 1),
    ("consumer", 1),
    ("technology", 1),
    ("automation", 1),
    ("packaging", 1),
    ("irrigation", 1),
    ("fertilizer", 1),
)

STRONG_BERRY_RE = re.compile(
    r"\b(blueberr(?:y|ies)|strawberr(?:y|ies)|raspberr(?:y|ies)|blackberr(?:y|ies)|ar[aá]ndanos?|cultivar|breeding|genetics?)\b",
    re.IGNORECASE,
)


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def process_threshold() -> int:
    return _int_env("BERRY_RELEVANCE_PROCESS_THRESHOLD", 8)


def skip_threshold() -> int:
    return _int_env("BERRY_RELEVANCE_SKIP_THRESHOLD", 3)


def _haystack(item: dict[str, Any]) -> str:
    parts = [
        str(item.get("title") or ""),
        str(item.get("summary") or ""),
        str(item.get("description") or ""),
        str(item.get("source_name") or ""),
        str(item.get("source_id") or ""),
    ]
    return " ".join(parts).lower()


def _score_terms(text: str, terms: tuple[tuple[str, int], ...]) -> tuple[int, list[str]]:
    score = 0
    hits: list[str] = []
    for term, weight in terms:
        if term in text:
            score += weight
            hits.append(term)
    return score, hits


def _recency_bonus(item: dict[str, Any]) -> int:
    published = str(item.get("published_at") or item.get("published_date") or "").strip()
    if not published:
        return 0
    try:
        if "T" in published:
            dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(published).replace(tzinfo=timezone.utc)
    except ValueError:
        return 0
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    age_days = (datetime.now(timezone.utc) - dt).days
    if age_days <= 14:
        return 2
    if age_days <= 45:
        return 1
    return 0


@dataclass(frozen=True)
class RelevanceScreen:
    score: int
    decision: str
    reason: str
    likely_berry_ids: list[str] = field(default_factory=list)
    likely_topics: list[str] = field(default_factory=list)
    matched_terms: list[str] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "decision": self.decision,
            "reason": self.reason,
            "likely_berry_ids": list(self.likely_berry_ids),
            "likely_topics": list(self.likely_topics),
            "matched_terms": list(self.matched_terms),
            "screener_provenance": dict(self.provenance),
        }


def screen_discovered_item(item: dict[str, Any]) -> RelevanceScreen:
    text = _haystack(item)
    high_score, high_hits = _score_terms(text, HIGH_WEIGHT_TERMS)
    medium_score, medium_hits = _score_terms(text, MEDIUM_WEIGHT_TERMS)
    low_score, low_hits = _score_terms(text, LOW_WEIGHT_TERMS)
    recency = _recency_bonus(item)
    score = high_score + medium_score + low_score + recency
    berries = infer_berry_ids_from_text(text)
    topics = []
    if high_hits:
        topics.append("berry-cultivar-signal")
    if medium_hits:
        topics.append("production-market-signal")
    if low_hits:
        topics.append("adjacent-ag-signal")

    process_at = process_threshold()
    skip_at = skip_threshold()
    strong = bool(STRONG_BERRY_RE.search(text)) or bool(berries)

    if strong or score >= process_at:
        decision = "process"
        reason = (
            "strong berry/cultivar signal"
            if strong
            else f"score {score} >= process threshold {process_at}"
        )
    elif score <= skip_at:
        decision = "skip"
        reason = f"score {score} <= skip threshold {skip_at} and no strong berry signal"
    else:
        decision = "borderline"
        reason = f"score {score} between skip {skip_at} and process {process_at}"

    return RelevanceScreen(
        score=score,
        decision=decision,
        reason=reason,
        likely_berry_ids=berries,
        likely_topics=topics,
        matched_terms=high_hits + medium_hits + low_hits,
        provenance={
            "screener": "deterministic-relevance-v1",
            "process_threshold": process_at,
            "skip_threshold": skip_at,
            "recency_bonus": recency,
            "trust_state": "untrusted_triage",
        },
    )
