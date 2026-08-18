"""Deterministic patent party → Entity suggestions.

Never creates Entities. Inventors are unresolved unless a Person entity
already exists. Assignee is not inferred from inventor name.
"""

from __future__ import annotations

import re
import unicodedata
from app.services.patent_monitor.relevance import berry_ids_for_filing

ORG_TYPES = ("company", "breeding_program", "brand")
VARIETY_TYPES = ("variety",)
PATENT_TYPES = ("patent",)
PERSON_TYPES = ("person",)

SKIP_ASSIGNEE_NAMES = {"", "n/a", "not available", "unknown"}


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    compact = re.sub(r"[^a-z0-9]+", " ", ascii_only.casefold())
    compact = re.sub(
        r"\b(inc|incorporated|llc|l l c|ltd|limited|sa|s a|pty|b v|corp|corporation|company|co)\b",
        " ",
        compact,
    )
    return re.sub(r"\s+", " ", compact).strip()


def _names_for(entity: dict[str, Any]) -> list[str]:
    values = [entity.get("name") or ""]
    values.extend(entity.get("aliases") or [])
    return [value for value in values if isinstance(value, str) and value.strip()]


def _index(entities: list[dict[str, Any]], types: tuple[str, ...]) -> list[tuple[str, str, dict[str, Any]]]:
    rows: list[tuple[str, str, dict[str, Any]]] = []
    for entity in entities:
        if entity.get("entity_type") not in types or not entity.get("id"):
            continue
        for name in _names_for(entity):
            folded = _fold(name)
            if len(folded) < 4:
                continue
            rows.append((folded, entity["id"], entity))
    rows.sort(key=lambda row: len(row[0]), reverse=True)
    return rows


def _match_name(
    name: str,
    index: list[tuple[str, str, dict[str, Any]]],
    *,
    filing_berry_ids: list[str] | None = None,
    require_berry_overlap: bool = False,
) -> tuple[str, str] | None:
    folded = _fold(name)
    if len(folded) < 4:
        return None
    matches: list[tuple[int, int, str, str]] = []
    type_rank = {
        "company": 0,
        "brand": 1,
        "breeding_program": 2,
        "variety": 0,
        "patent": 0,
        "person": 0,
    }
    folded_tokens = folded.split()
    filing_berries = set(filing_berry_ids or [])
    for candidate, entity_id, entity in index:
        if require_berry_overlap:
            entity_berries = set(entity.get("berry_ids") or [])
            if entity_berries and filing_berries and not (entity_berries & filing_berries):
                continue
        entity_type = entity.get("entity_type") or ""
        candidate_tokens = candidate.split()
        if folded == candidate:
            matches.append((0, type_rank.get(entity_type, 9), entity_id, "high"))
            continue
        if len(candidate_tokens) == 1 and len(candidate) >= 8 and candidate_tokens[0] in folded_tokens:
            matches.append((1, type_rank.get(entity_type, 9), entity_id, "medium"))
            continue
        # Alias/shorter official name contained in the filing string
        # ("Fall Creek" ⊂ "Fall Creek Farm & Nursery, Inc.").
        # Do not match the reverse: a short filing name is not the longer
        # breeding-program title ("Driscoll's, Inc." ⊄ programme name).
        if len(candidate_tokens) >= 2 and _contiguous(candidate_tokens, folded_tokens):
            matches.append((1, type_rank.get(entity_type, 9), entity_id, "medium"))
    if not matches:
        return None
    matches.sort()
    _rank, _type, entity_id, confidence = matches[0]
    return entity_id, confidence


def _contiguous(needle: list[str], haystack: list[str]) -> bool:
    if not needle or len(needle) > len(haystack):
        return False
    size = len(needle)
    return any(haystack[index : index + size] == needle for index in range(len(haystack) - size + 1))


def suggest_entity_links(
    filing: dict[str, Any],
    entities: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    org_index = _index(entities, ORG_TYPES)
    variety_index = _index(entities, VARIETY_TYPES)
    patent_index = _index(entities, PATENT_TYPES)
    person_index = _index(entities, PERSON_TYPES)
    filing_berries = berry_ids_for_filing(filing)
    suggestions: list[dict[str, Any]] = []

    def add(
        name: str,
        role: str,
        index: list[tuple[str, str, dict[str, Any]]],
        *,
        require_berry_overlap: bool = False,
    ) -> None:
        cleaned = (name or "").strip()
        if not cleaned or cleaned.casefold() in SKIP_ASSIGNEE_NAMES:
            return
        matched = _match_name(
            cleaned,
            index,
            filing_berry_ids=filing_berries,
            require_berry_overlap=require_berry_overlap,
        )
        if matched:
            entity_id, confidence = matched
            suggestions.append(
                {
                    "name": cleaned,
                    "role": role,
                    "match_entity_id": entity_id,
                    "match_status": "matched",
                    "confidence": confidence,
                }
            )
        else:
            suggestions.append(
                {
                    "name": cleaned,
                    "role": role,
                    "match_entity_id": None,
                    "match_status": "unresolved",
                    "confidence": "low" if role == "inventor" else "medium",
                }
            )

    for assignee in filing.get("assignees") or []:
        add(assignee, "assignee", org_index)
    for applicant in filing.get("applicants") or []:
        if applicant in (filing.get("assignees") or []):
            continue
        add(applicant, "applicant", org_index)
    for inventor in filing.get("inventors") or []:
        add(inventor, "inventor", person_index)
    if filing.get("cultivar_name"):
        add(str(filing["cultivar_name"]), "variety", variety_index, require_berry_overlap=True)
    if filing.get("publication_number"):
        add(str(filing["publication_number"]), "patent", patent_index, require_berry_overlap=True)
    return suggestions


def matched_entity_ids(suggestions: list[dict[str, Any]]) -> list[str]:
    ids: list[str] = []
    for suggestion in suggestions:
        if suggestion.get("match_status") != "matched":
            continue
        if suggestion.get("role") == "inventor":
            continue
        entity_id = suggestion.get("match_entity_id")
        if isinstance(entity_id, str) and entity_id not in ids:
            ids.append(entity_id)
    return ids
