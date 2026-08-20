"""Deterministic source-independence clustering for Evidence.

Real problem this exists to solve (Corroboration + Signal Formation
mission, 2026-08-19): a Hortifrut/Naturipe genetics-platform announcement
with Mountain Blue Orchards produced three real Evidence records in
canonical -- the trusted first-party write-up (source_name "Hortifrut
S.A."), a fresh pull from the same company's newsroom RSS feed onboarded
this session (source_id "source-20260819-hortifrut-newsroom"), and
FreshFruitPortal's trade-press coverage published the same day. All three
report the same underlying announcement. Naively counting evidence_ids on
a Signal ("3 sources say this") would silently inflate confidence for
what is really one origin repeated three times -- exactly the "three
reprints of one press release are not three independent corroborating
sources" failure mode this module exists to prevent.

This module never mutates Evidence and never decides trust on its own --
it only computes, deterministically, which Evidence records most likely
share a single underlying origin, and how many *distinct* origins a set
of records actually represents. That count (not the raw evidence count)
is what a Signal's independence should be judged against.
"""

from __future__ import annotations

import re
from typing import Any

MIN_TOKEN_LENGTH = 4
MIN_TITLE_TOKENS_FOR_FAST_PATH = 3
TITLE_SUMMARY_JACCARD_THRESHOLD = 0.2
TITLE_ONLY_JACCARD_THRESHOLD = 0.6
DATE_WINDOW_DAYS = 5

_STOPWORDS = {
    "with", "from", "that", "this", "have", "will", "their", "about",
    "into", "over", "after", "before", "than", "then", "your", "were",
    "been", "more", "most", "some", "such", "also", "amid", "amidst",
}


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", (text or "").casefold())
    return {w for w in words if len(w) >= MIN_TOKEN_LENGTH and w not in _STOPWORDS}


def _content_tokens(record: dict[str, Any]) -> set[str]:
    parts = [record.get("title") or "", record.get("summary") or "", record.get("why_it_matters") or ""]
    return _tokens(" ".join(parts))


def _title_tokens(record: dict[str, Any]) -> set[str]:
    return _tokens(record.get("title") or "")


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _dates_close(a: dict[str, Any], b: dict[str, Any], *, window_days: int = DATE_WINDOW_DAYS) -> bool:
    from datetime import date as _date

    def _parse(value: Any) -> "_date | None":
        if not isinstance(value, str) or not value:
            return None
        try:
            return _date.fromisoformat(value[:10])
        except ValueError:
            return None

    date_a, date_b = _parse(a.get("published_date")), _parse(b.get("published_date"))
    if date_a is None or date_b is None:
        return False
    return abs((date_a - date_b).days) <= window_days


def same_origin(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """True when two Evidence records most likely trace to one underlying
    origin (the same outlet, or the same announcement/filing relayed by
    different publishers) rather than two independently-observed
    developments. Deterministic and conservative: when in doubt, this
    returns False (records count as independent) rather than silently
    collapsing real corroboration -- the risk this module guards against
    is inflation, not under-counting."""
    if a.get("id") == b.get("id"):
        return False
    source_id_a, source_id_b = a.get("source_id"), b.get("source_id")
    if source_id_a and source_id_b and source_id_a == source_id_b:
        return True
    name_a, name_b = a.get("source_name"), b.get("source_name")
    if name_a and name_b and name_a == name_b:
        return True
    entities_a, entities_b = set(a.get("entity_ids") or []), set(b.get("entity_ids") or [])
    shared_entities = entities_a & entities_b
    # Real case found auditing real candidate output (Signal-Candidate
    # Calibration, 2026-08-19): EastFruit republished a Fruitnet/Eurofruit
    # story about Fall Creek's Romanian land acquisition 4 days later --
    # EastFruit's own summary literally says "According Fruitnet". Titles
    # were "Fall Creek reveals Romanian acquisition[ - EastFruit]",
    # title-only Jaccard 0.83, but the DATE_WINDOW_DAYS gate (then 1 day)
    # killed the match before the text check ever ran, and the combined
    # title+summary+why_it_matters similarity (0.15) was diluted by each
    # outlet's own added detail. A near-identical headline is checked
    # first and, if strong enough, overrides the date gate entirely --
    # still requires at least one shared entity, so two different
    # companies' near-identical generic-template headlines ("X launches
    # new Y variety") can't false-merge just from boilerplate phrasing.
    title_tokens_a, title_tokens_b = _title_tokens(a), _title_tokens(b)
    if (
        shared_entities
        and len(title_tokens_a) >= MIN_TITLE_TOKENS_FOR_FAST_PATH
        and len(title_tokens_b) >= MIN_TITLE_TOKENS_FOR_FAST_PATH
        and _jaccard(title_tokens_a, title_tokens_b) >= TITLE_ONLY_JACCARD_THRESHOLD
    ):
        return True
    if not _dates_close(a, b):
        return False
    similarity = _jaccard(_content_tokens(a), _content_tokens(b))
    # Real-world same-event coverage from different outlets paraphrases
    # heavily -- a curated internal write-up, a press-release-style
    # newsroom post, and a trade-press blurb about the identical
    # Hortifrut/Naturipe/Mountain Blue Orchards deal (2026-07-30) only
    # share ~10-13% of their significant tokens, well under a strict
    # similarity bar. Two *specific* companies named in both records on
    # the same day is already a narrow, unlikely coincidence on its own;
    # requiring it *in addition* to a high text-overlap bar was silently
    # undercounting real same-origin coverage as independent. Either a
    # meaningfully shared cast of named entities, or real text overlap
    # (for cases with weaker entity tagging), is enough alongside the
    # same-day gate.
    return len(shared_entities) >= 2 or similarity >= TITLE_SUMMARY_JACCARD_THRESHOLD


def independent_clusters(records: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Group records into same-origin clusters via same_origin(), using
    union-find so origin-sharing is transitive (A~B and B~C clusters all
    three even if A and C alone wouldn't have matched)."""
    parent: dict[str, str] = {r["id"]: r["id"] for r in records if r.get("id")}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: str, y: str) -> None:
        root_x, root_y = find(x), find(y)
        if root_x != root_y:
            parent[root_y] = root_x

    for i, a in enumerate(records):
        a_id = a.get("id")
        if not a_id:
            continue
        for b in records[i + 1 :]:
            b_id = b.get("id")
            if not b_id:
                continue
            if same_origin(a, b):
                union(a_id, b_id)

    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        record_id = record.get("id")
        if not record_id:
            continue
        grouped.setdefault(find(record_id), []).append(record)
    return list(grouped.values())


def independence_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Summary used both by human signal review and by the candidate
    generator: how many genuinely distinct origins does this evidence set
    represent, and which records were folded together as the same origin."""
    clusters = independent_clusters(records)
    return {
        "total_evidence_count": len(records),
        "independent_source_count": len(clusters),
        "clusters": [
            {
                "evidence_ids": [r["id"] for r in cluster],
                "origin_label": (cluster[0].get("source_name") or cluster[0].get("source_id") or cluster[0].get("id")),
            }
            for cluster in clusters
        ],
    }
