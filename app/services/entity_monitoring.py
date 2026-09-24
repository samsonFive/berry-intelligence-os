"""Transparent entity monitoring profiles over existing public Evidence.

This module adds no collector and creates no trusted record. It explains the
bounded terms used to associate already-published Evidence with an entity,
reusing the conservative alias-recall rules that protect the canonical corpus.
"""

from __future__ import annotations

import re
from typing import Any

from app.services.entity_alias_recall import linked_evidence_for_entity
from app.services.feed_first import SIGNAL_TYPE_LABELS, signal_type

MAX_TERMS = 12
WEAK_TERMS = {
    "blue",
    "fresh",
    "green",
    "international",
    "premium",
    "sunrise",
    "global",
    "group",
}


def _clean_term(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _quoted(value: str) -> str:
    return f'"{value.replace(chr(34), "")}"'


def _is_weak(value: str) -> bool:
    words = re.findall(r"[a-z0-9]+", value.casefold())
    return (
        not words
        or len(value) < 4
        or (len(words) == 1 and (len(words[0]) <= 4 or words[0] in WEAK_TERMS))
    )


def build_monitoring_profile(
    entity: dict[str, Any],
    *,
    profile: dict[str, Any] | None = None,
    related_terms: list[str] | None = None,
) -> dict[str, Any]:
    """Build an inspectable, bounded expression; never execute it implicitly."""
    profile = profile or {}
    raw_terms = [
        entity.get("name"),
        profile.get("canonical_name"),
        *(entity.get("aliases") or []),
        *(profile.get("aliases") or []),
        *(related_terms or []),
    ]
    terms: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in raw_terms:
        value = _clean_term(raw)
        folded = value.casefold()
        if not value or folded in seen:
            continue
        seen.add(folded)
        terms.append(
            {
                "value": value,
                "kind": "canonical" if not terms else "alias_or_related",
                "weak": _is_weak(value),
            }
        )
        if len(terms) >= MAX_TERMS:
            break

    context_terms = [
        _clean_term(value).removeprefix("berry-")
        for value in (entity.get("berry_ids") or profile.get("crops") or [])
        if _clean_term(value)
    ]
    if not context_terms:
        context_terms = ["berry", "berries"]
    context_expression = " OR ".join(_quoted(value) for value in context_terms[:6])
    clauses = []
    for term in terms:
        clause = _quoted(term["value"])
        if term["weak"]:
            clause = f"({clause} AND ({context_expression}))"
        clauses.append(clause)
    expression = " OR ".join(clauses) or _quoted(str(entity.get("id") or ""))
    return {
        "enabled": bool(profile.get("monitoring_enabled", True)),
        "terms": terms,
        "context_terms": context_terms[:6],
        "exclusions": ["Raspberry Pi", "BlackBerry device"],
        "expression": expression,
        "explanation": (
            "Canonical names and strong aliases match directly. Short or generic "
            "aliases require berry context; exclusions suppress known technology noise."
        ),
    }


def monitored_public_signals(
    entity: dict[str, Any],
    records: list[dict[str, Any]],
    *,
    entities: dict[str, dict[str, Any]],
    limit: int = 12,
) -> list[dict[str, Any]]:
    """Present provenance-preserving public matches from the existing corpus."""
    rows = linked_evidence_for_entity(entity, records, entities=entities)
    rows.sort(
        key=lambda row: (
            str(row.get("published_date") or ""),
            str(row.get("id") or ""),
        ),
        reverse=True,
    )
    diverse: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    seen_families: set[str] = set()
    for record in rows:
        family = signal_type(record)
        if family in seen_families:
            continue
        diverse.append(record)
        selected_ids.add(str(record.get("id") or ""))
        seen_families.add(family)
        if len(diverse) >= limit:
            break
    for record in rows:
        record_id = str(record.get("id") or "")
        if record_id in selected_ids:
            continue
        diverse.append(record)
        selected_ids.add(record_id)
        if len(diverse) >= limit:
            break
    diverse.sort(
        key=lambda row: (
            str(row.get("published_date") or ""),
            str(row.get("id") or ""),
        ),
        reverse=True,
    )

    presented = []
    for record in diverse:
        family = signal_type(record)
        mechanism = str(record.get("link_mechanism") or "entity_id")
        if mechanism == "alias_recall":
            reason = (
                f"Alias “{record.get('link_matched_alias')}” matched "
                f"{record.get('link_matched_field')}"
            )
        else:
            reason = "Canonical entity link on published Evidence"
        presented.append(
            {
                "id": record.get("id"),
                "title": record.get("title") or record.get("id"),
                "signal_type": family,
                "signal_label": SIGNAL_TYPE_LABELS[family],
                "publisher": record.get("source_name") or "Unknown source",
                "published_date": record.get("published_date") or "",
                "source_url": record.get("source_url") or "",
                "summary": record.get("summary") or "",
                "geography_ids": list(record.get("geography_ids") or []),
                "match_reason": reason,
                "review_state": "published",
                "reader_href": f"/today?item={record.get('id')}",
            }
        )
    return presented
