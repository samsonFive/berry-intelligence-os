"""Conservative, non-mutating text recall for trusted entity Evidence.

Structured ``entity_ids`` remain authoritative. Text fallback exists only
to recall older trusted Evidence that predates an Entity record, and every
fallback result carries diagnostics distinguishing it from a reviewed link.
Variety names require stronger grounding than Company names because many
cultivar denominations are ordinary words, people names, or places.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import re
from typing import Any, Iterable

MIN_ALIAS_LENGTH = 4
TEXT_FIELDS = ("title", "headline", "summary", "excerpt", "why_it_matters")

_VARIETY_CONTEXT = re.compile(
    r"\b(?:variet(?:y|ies)|cultivar(?:s)?|selection(?:s)?|denomination(?:s)?|"
    r"commercial\s+name(?:s)?|brand\s+name(?:s)?)\b",
    re.IGNORECASE,
)
_VARIETY_LIST_CONTEXT = re.compile(
    r"\b(?:variety\s+(?:list|index|register)|register\s+index|lists?\b.{0,40}\bdenominations?|"
    r"mapping\b|maps?\b.{0,30}\b(?:codes?|names?)|codes?\s+to\s+(?:brand\s+)?names?|"
    r"brand\s+name\s+and\s+selection\s+code\s+pairs?)\b",
    re.IGNORECASE,
)
_BERRY_CONTEXT = re.compile(
    r"\b(?:blueberr(?:y|ies)|strawberr(?:y|ies)|raspberr(?:y|ies)|"
    r"blackberr(?:y|ies)|caneberr(?:y|ies)|berries|berry)\b",
    re.IGNORECASE,
)
_COMPANY_ACTION_AFTER = re.compile(
    r"^\s*(?:['’]s\s+)?(?:has\s+|is\s+|will\s+|to\s+)?(?:"
    r"acquir(?:e|es|ed|ing)|announce(?:s|d)?|appoint(?:s|ed)?|buy|buys|bought|"
    r"complete(?:s|d)?|expand(?:s|ed|ing)?|invest(?:s|ed|ing)?|join(?:s|ed)?|"
    r"launch(?:es|ed)?|license(?:s|d)?|market(?:s|ed|ing)?|open(?:s|ed)?|"
    r"own(?:s|ed)?|partner(?:s|ed|ing)?|plan(?:s|ned)?|protect(?:s|ed)?|"
    r"report(?:s|ed)?|rebrand(?:s|ed)?|sell(?:s|ing)?|showcase(?:s|d)?|"
    r"strengthen(?:s|ed|ing)?|unveil(?:s|ed)?)\b",
    re.IGNORECASE,
)
_COMPANY_CONTEXT_BEFORE = re.compile(
    r"(?:\b(?:by|from|of|with|at|for|owned\s+by|acquired\s+by|partner(?:s|ed)?\s+with)\s+|"
    r"\b(?:company|group|business|firm|breeder|grower|producer|nursery|brand)\s+)$",
    re.IGNORECASE,
)
_PLACE_BEFORE = re.compile(
    r"\b(?:in|from|across|near|at|around|throughout)\s+$",
    re.IGNORECASE,
)
_PLACE_AFTER = re.compile(
    r"^\s*\b(?:state|province|territory|region|market)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class TextMatch:
    alias: str
    field: str
    start: int
    end: int
    match_type: str


def _identity_values(entity: dict[str, Any]) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for raw in [entity.get("name"), *(entity.get("aliases") or [])]:
        if not isinstance(raw, str):
            continue
        value = raw.strip()
        folded = value.casefold()
        if len(value) < MIN_ALIAS_LENGTH or folded in seen:
            continue
        seen.add(folded)
        values.append(value)
    return sorted(values, key=lambda value: (-len(value), value.casefold()))


def _alias_source(alias: str) -> str:
    pieces: list[str] = []
    for char in alias:
        if char in {"'", "’"}:
            pieces.append("['’]")
        elif char.isspace():
            if not pieces or pieces[-1] != r"\s+":
                pieces.append(r"\s+")
        elif char in {"®", "™"}:
            pieces.append(r"[®™]?")
        else:
            pieces.append(re.escape(char))
    return rf"(?<!\w){''.join(pieces)}(?!\w)"


@lru_cache(maxsize=1024)
def _alias_pattern(alias: str) -> re.Pattern[str]:
    return re.compile(_alias_source(alias), re.IGNORECASE)


def _fold_identity(value: str) -> str:
    value = value.replace("’", "'").replace("®", "").replace("™", "")
    return " ".join(re.findall(r"[\w']+", value.casefold()))


def _record_fields(record: dict[str, Any]) -> Iterable[tuple[str, str]]:
    for field in TEXT_FIELDS:
        value = record.get(field)
        if isinstance(value, str) and value:
            yield field, value


def _entity_map(entities: dict[str, dict[str, Any]] | Iterable[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    if entities is None:
        return {}
    if isinstance(entities, dict):
        return entities
    return {str(entity.get("id")): entity for entity in entities if entity.get("id")}


def _other_variety_patterns(entity: dict[str, Any], entities: dict[str, dict[str, Any]]) -> list[re.Pattern[str]]:
    own = {_fold_identity(value) for value in _identity_values(entity)}
    patterns: list[re.Pattern[str]] = []
    seen: set[str] = set()
    for other in entities.values():
        if other.get("entity_type") != "variety" or other.get("id") == entity.get("id"):
            continue
        for value in _identity_values(other):
            folded = _fold_identity(value)
            if folded in own or folded in seen:
                continue
            if any(re.search(rf"(?:^|\s){re.escape(alias)}(?:$|\s)", folded) for alias in own):
                seen.add(folded)
                patterns.append(_alias_pattern(value))
    return patterns


def _geography_patterns(entities: dict[str, dict[str, Any]]) -> list[re.Pattern[str]]:
    values: set[str] = set()
    for entity in entities.values():
        if entity.get("entity_type") != "geography":
            continue
        values.update(_identity_values(entity))
    return [_alias_pattern(value) for value in sorted(values, key=lambda item: (-len(item), item.casefold()))]


def _inside_other_variety(text: str, start: int, end: int, patterns: list[re.Pattern[str]]) -> bool:
    return any(match.start() <= start and match.end() >= end for pattern in patterns for match in pattern.finditer(text))


def _looks_geographic(
    text: str, start: int, end: int, geography_patterns: list[re.Pattern[str]]
) -> bool:
    before = text[max(0, start - 48) : start]
    after = text[end : min(len(text), end + 48)]
    if _PLACE_BEFORE.search(before) or _PLACE_AFTER.search(after):
        return True
    comma_target = re.match(r"^\s*,\s*", after)
    if comma_target:
        suffix = after[comma_target.end() :]
        return any(pattern.match(suffix) for pattern in geography_patterns)
    return False


def _berry_compatible(entity: dict[str, Any], record: dict[str, Any], text: str) -> bool:
    entity_berries = {str(value) for value in (entity.get("berry_ids") or []) if value}
    record_berries = {str(value) for value in (record.get("berry_ids") or []) if value}
    if entity_berries and record_berries:
        return bool(entity_berries & record_berries)
    return bool(_BERRY_CONTEXT.search(text))


def _variety_match(
    entity: dict[str, Any],
    record: dict[str, Any],
    *,
    other_varieties: list[re.Pattern[str]],
    geography_patterns: list[re.Pattern[str]] | None = None,
    aliases: list[str] | None = None,
) -> TextMatch | None:
    aliases = aliases if aliases is not None else _identity_values(entity)
    geography_patterns = geography_patterns or []
    for field, text in _record_fields(record):
        for alias in aliases:
            for occurrence in _alias_pattern(alias).finditer(text):
                if _inside_other_variety(text, occurrence.start(), occurrence.end(), other_varieties):
                    continue
                if _looks_geographic(text, occurrence.start(), occurrence.end(), geography_patterns):
                    continue
                context = text[max(0, occurrence.start() - 120) : min(len(text), occurrence.end() + 120)]
                before = text[max(0, occurrence.start() - 48) : occurrence.start()]
                if (
                    len(re.findall(r"[\w]+", alias)) == 1
                    and re.search(r"[A-Z][\w.'’ -]+,\s*$", before)
                    and not _VARIETY_CONTEXT.search(context)
                ):
                    continue
                if field == "title" and _fold_identity(text) == _fold_identity(alias):
                    structured_geography = list(record.get("geography_ids") or []) + [
                        value
                        for value in (record.get("entity_ids") or [])
                        if str(value).startswith("geography-")
                    ]
                    if structured_geography:
                        continue
                    return TextMatch(alias, field, occurrence.start(), occurrence.end(), "exact_strong_identity")
                if not _berry_compatible(entity, record, text):
                    continue
                if (
                    _VARIETY_CONTEXT.search(context)
                    or _BERRY_CONTEXT.search(context)
                    or _VARIETY_LIST_CONTEXT.search(text)
                ):
                    return TextMatch(alias, field, occurrence.start(), occurrence.end(), "contextual_alias")
    return None


def _company_match(
    entity: dict[str, Any], record: dict[str, Any], *, aliases: list[str] | None = None
) -> TextMatch | None:
    aliases = aliases if aliases is not None else _identity_values(entity)
    source_name = str(record.get("source_name") or "")
    identity_names = {_fold_identity(value) for value in aliases}
    has_legal_identity = any(
        len(re.findall(r"[\w]+", value)) > 1 or bool(re.search(r"[^\w\s]", value))
        for value in aliases
    )
    for field, text in _record_fields(record):
        for alias in aliases:
            for occurrence in _alias_pattern(alias).finditer(text):
                if field == "title" or _fold_identity(source_name) in identity_names:
                    return TextMatch(alias, field, occurrence.start(), occurrence.end(), "exact_strong_identity")
                words = re.findall(r"[\w]+", alias)
                distinctive = (
                    has_legal_identity
                    or len(words) > 1
                    or len(alias) >= 9
                    or bool(re.search(r"[^\w\s]", alias))
                )
                if distinctive and field != "why_it_matters":
                    return TextMatch(alias, field, occurrence.start(), occurrence.end(), "contextual_alias")
                before = text[max(0, occurrence.start() - 48) : occurrence.start()]
                after = text[occurrence.end() : min(len(text), occurrence.end() + 48)]
                if _COMPANY_CONTEXT_BEFORE.search(before) or _COMPANY_ACTION_AFTER.search(after):
                    return TextMatch(alias, field, occurrence.start(), occurrence.end(), "contextual_alias")
    return None


def match_evidence_to_entity(
    entity: dict[str, Any],
    record: dict[str, Any],
    *,
    entities: dict[str, dict[str, Any]] | Iterable[dict[str, Any]] | None = None,
) -> TextMatch | None:
    """Return the first deterministic fallback match, never an explicit link."""
    entity_id = str(entity.get("id") or "")
    if entity_id and entity_id in (record.get("entity_ids") or []):
        return None
    if entity.get("entity_type") == "variety":
        index = _entity_map(entities)
        return _variety_match(
            entity,
            record,
            other_varieties=_other_variety_patterns(entity, index),
            geography_patterns=_geography_patterns(index),
        )
    if entity.get("entity_type") == "company":
        return _company_match(entity, record)
    return None


def alias_linked_evidence(
    entity: dict[str, Any],
    records: list[dict[str, Any]],
    *,
    already_linked_ids: set[str],
    entities: dict[str, dict[str, Any]] | Iterable[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Safely recalled trusted Evidence, returned as diagnostic shallow copies."""
    matches: list[dict[str, Any]] = []
    entity_type = entity.get("entity_type")
    aliases = _identity_values(entity)
    other_varieties = (
        _other_variety_patterns(entity, _entity_map(entities))
        if entity_type == "variety"
        else []
    )
    geography_patterns = _geography_patterns(_entity_map(entities)) if entity_type == "variety" else []
    for record in records:
        record_id = record.get("id")
        if not record_id or record_id in already_linked_ids:
            continue
        if entity_type == "variety":
            matched = _variety_match(
                entity,
                record,
                other_varieties=other_varieties,
                geography_patterns=geography_patterns,
                aliases=aliases,
            )
        elif entity_type == "company":
            matched = _company_match(entity, record, aliases=aliases)
        else:
            matched = None
        if matched is None:
            continue
        matches.append({
            **record,
            "link_mechanism": "alias_recall",
            "link_match_type": matched.match_type,
            "link_matched_alias": matched.alias,
            "link_matched_field": matched.field,
        })
    return matches


def linked_evidence_for_entity(
    entity: dict[str, Any],
    published: list[dict[str, Any]],
    *,
    entities: dict[str, dict[str, Any]] | Iterable[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Structured links first, then conservative deterministic text recall."""
    entity_id = entity["id"]
    direct = [{**record, "link_mechanism": "entity_id"} for record in published if entity_id in (record.get("entity_ids") or [])]
    direct_ids = {str(record["id"]) for record in direct if record.get("id")}
    recalled = alias_linked_evidence(entity, published, already_linked_ids=direct_ids, entities=entities)
    return direct + recalled
