"""Deterministic Variety identity resolution.

Never merges records. Never returns CONFIRMED_SAME from text matching.
Exact folded name/alias/code/registration matches are POSSIBLE_ALIAS and
require human review. Contiguous-token overlap without an exact match is
UNKNOWN. No similarity scores, no model inference.
"""

from __future__ import annotations

import unicodedata
from functools import lru_cache
from typing import Any

from app.services.patent_monitor.entity_link import _fold
from app.services.identity_read_model import with_identity_catalog_index

STATE_CONFIRMED_SAME = "confirmed_same"
STATE_POSSIBLE_ALIAS = "possible_alias"
STATE_DISTINCT = "distinct"
STATE_UNKNOWN = "unknown"
STATE_REJECTED = "rejected"

HUMAN_STATES = {
    STATE_CONFIRMED_SAME,
    STATE_POSSIBLE_ALIAS,
    STATE_DISTINCT,
    STATE_UNKNOWN,
    STATE_REJECTED,
}

LABELS = {
    STATE_CONFIRMED_SAME: "CONFIRMED SAME VARIETY",
    STATE_POSSIBLE_ALIAS: "POSSIBLE ALIAS / NEEDS REVIEW",
    STATE_DISTINCT: "DISTINCT",
    STATE_UNKNOWN: "UNKNOWN",
    STATE_REJECTED: "REJECTED",
}

_MIN_FOLD = 3

_IDENTITY_ATTRIBUTE_ROLES = (
    ("trade_name", "trade_name"),
    ("commercial_name", "commercial_name"),
    ("denomination", "denomination"),
    ("selection_code", "breeder_code"),
    ("breeder_code", "breeder_code"),
    ("patent_number", "registration"),
    ("patent_id", "registration"),
    ("rights_id", "registration"),
)
_REGISTRATION_ATTRIBUTES = ("patent_number", "patent_id", "rights_id", "cpvo_application_number", "grant_number")
_CATALOG_MATCH_ATTRIBUTES = tuple(dict.fromkeys(
    [key for key, _role in _IDENTITY_ATTRIBUTE_ROLES] + list(_REGISTRATION_ATTRIBUTES)
))
_SIGNATURE_SCALARS = (str, int, float, bool, type(None))
_CANDIDATE_NAME_ROLES = (
    ("candidate_name", "candidate_name"), ("denomination", "denomination"),
    ("trade_name", "trade_name"), ("breeder_code", "breeder_code"), ("alias", "alias"),
)
_CANDIDATE_REGISTRATION_KEYS = ("registration_id", "application_number", "grant_number", "patent_number")
_CANDIDATE_REGISTRATION_DETAIL_KEYS = ("application_number", "grant_number", "registration_number")


def _fold_variety_identity(value: str) -> str:
    if not value.isascii():
        normalized = unicodedata.normalize("NFKC", value.casefold())
        if any(
            not char.isascii() and char.isalpha() and not unicodedata.name(char, "").startswith("LATIN")
            for char in normalized
        ):
            # Keep scripts that the legacy Latin fold would drop. Do not
            # transliterate or equate a written name with a translation.
            tokens = "".join(
                char if char.isalnum() or unicodedata.category(char).startswith("M") else " "
                for char in normalized
            )
            return " ".join(tokens.split())
    return _fold(value)


@lru_cache(maxsize=4096)
def _fold_short_identity(value: str) -> str:
    return _fold_variety_identity(value)


def fold_identity(value: str | None) -> str:
    # Cache only a bounded literal string transformation. Matching, catalog
    # fields and human decisions are always evaluated from the current records.
    value = value or ""
    if isinstance(value, str) and len(value) <= 256:
        return _fold_short_identity(value)
    return _fold_variety_identity(value)


def _identity_strings(variety: dict[str, Any]) -> list[tuple[str, str]]:
    attrs = variety.get("attributes") or {}
    values: list[tuple[str, str]] = []
    name = str(variety.get("name") or "").strip()
    if name:
        values.append((name, "canonical_name"))
    for alias in variety.get("aliases") or []:
        text = str(alias).strip()
        if text:
            values.append((text, "alias"))
    for key, role in _IDENTITY_ATTRIBUTE_ROLES:
        text = str(attrs.get(key) or "").strip()
        if text:
            values.append((text, role))
    return values


def _registration_ids(variety: dict[str, Any]) -> set[str]:
    attrs = variety.get("attributes") or {}
    out: set[str] = set()
    for key in _REGISTRATION_ATTRIBUTES:
        text = str(attrs.get(key) or "").strip()
        if text:
            out.add(fold_identity(text))
    return {item for item in out if item}


def candidate_registration_ids(candidate: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for key in _CANDIDATE_REGISTRATION_KEYS:
        text = str(candidate.get(key) or "").strip()
        if text:
            out.add(fold_identity(text))
    registration = candidate.get("registration") or {}
    if isinstance(registration, dict):
        for key in _CANDIDATE_REGISTRATION_DETAIL_KEYS:
            text = str(registration.get(key) or "").strip()
            if text:
                out.add(fold_identity(text))
    return {item for item in out if item}


def candidate_query_names(candidate: dict[str, Any]) -> list[tuple[str, str]]:
    values: list[tuple[str, str]] = []
    for key, role in _CANDIDATE_NAME_ROLES:
        text = str(candidate.get(key) or "").strip()
        if text:
            values.append((text, role))
    for alias in candidate.get("aliases") or []:
        text = str(alias).strip()
        if text:
            values.append((text, "alias"))
    return values


def _berries(record: dict[str, Any]) -> set[str]:
    berries = {str(item) for item in (record.get("berry_ids") or []) if item}
    berry = str(record.get("berry_id") or "").strip()
    if berry:
        berries.add(berry)
    return berries


def _contiguous(needle: list[str], haystack: list[str]) -> bool:
    if not needle or len(needle) > len(haystack):
        return False
    size = len(needle)
    return any(haystack[index : index + size] == needle for index in range(len(haystack) - size + 1))


def _catalog_record_signature(variety: dict[str, Any]) -> tuple:
    """Validate supported matching inputs before optional preparation.

    Whole-record equality against an owned copy checks freshness on reuse.
    The attribute lists above are shared with the matcher, rather than a second
    independently maintained list of identity fields.
    """
    if type(variety) is not dict:
        raise TypeError("Unsupported catalog record for optional lookup preparation")
    name, entity_type = variety.get("name"), variety.get("entity_type")
    aliases, attrs = variety.get("aliases") or [], variety.get("attributes") or {}
    berry_ids = variety.get("berry_ids") or []
    if (type(name) not in (str, type(None))
            or type(entity_type) not in (str, type(None))
            or type(aliases) not in (list, tuple)
            or type(attrs) is not dict
            or type(berry_ids) not in (list, tuple, set, frozenset)):
        raise TypeError("Unsupported catalog input for optional lookup preparation")
    values = tuple(attrs.get(key) for key in _CATALOG_MATCH_ATTRIBUTES)
    # Numeric values use the original path: Python equality treats True, 1
    # and 1.0 as equal, while their identity strings can differ. Plain text
    # and null fields make whole-record equality safe for matching inputs.
    if any(type(value) not in (str, type(None))
           for value in (*aliases, *berry_ids, variety.get("berry_id"), variety.get("id"), *values)):
        raise TypeError("Unsupported identity value for optional lookup preparation")
    return (entity_type, str(variety.get("id") or ""), name,
            tuple(str(alias).strip() for alias in aliases),
            frozenset(_berries(variety)),
            tuple(str(value or "").strip() for value in values))


def _index_candidate_supported(candidate: dict[str, Any]) -> bool:
    """Avoid consuming iterators or coercing opaque objects before the matcher."""
    if type(candidate) is not dict:
        return False
    aliases, berries = candidate.get("aliases") or [], candidate.get("berry_ids") or []
    if type(aliases) not in (list, tuple) or type(berries) not in (list, tuple, set, frozenset):
        return False
    values = [candidate.get(key) for key, _role in _CANDIDATE_NAME_ROLES]
    values.extend(candidate.get(key) for key in _CANDIDATE_REGISTRATION_KEYS)
    values.extend([*aliases, *berries, candidate.get("berry_id")])
    registration = candidate.get("registration")
    if registration is not None and type(registration) is not dict:
        return False
    registration = registration or {}
    if isinstance(registration, dict):
        if type(registration) is not dict:
            return False
        values.extend(registration.get(key) for key in _CANDIDATE_REGISTRATION_DETAIL_KEYS)
    return all(type(value) in _SIGNATURE_SCALARS for value in values)


@with_identity_catalog_index
def resolve_identity(
    candidate: dict[str, Any],
    varieties: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return an identity resolution. CONFIRMED_SAME is never produced here."""
    query_names = candidate_query_names(candidate)
    query_folds = [(fold_identity(text), text, role) for text, role in query_names]
    query_folds = [row for row in query_folds if len(row[0]) >= _MIN_FOLD]
    candidate_regs = candidate_registration_ids(candidate)
    candidate_berries = _berries(candidate)

    exact: list[dict[str, Any]] = []
    token_overlap: list[dict[str, Any]] = []

    for variety in varieties:
        if variety.get("entity_type") not in (None, "variety"):
            continue
        variety_id = str(variety.get("id") or "")
        if not variety_id:
            continue
        variety_berries = _berries(variety)
        if candidate_berries and variety_berries and not (candidate_berries & variety_berries):
            continue
        variety_regs = _registration_ids(variety)
        shared_regs = candidate_regs & variety_regs
        if shared_regs:
            exact.append(
                {
                    "variety_id": variety_id,
                    "variety_name": variety.get("name") or variety_id,
                    "matched_on": "registration_identifier",
                    "matched_value": sorted(shared_regs)[0],
                    "reason": "same_registration_identifier",
                }
            )
            continue
        for folded, original, role in query_folds:
            for variety_text, variety_role in _identity_strings(variety):
                variety_fold = fold_identity(variety_text)
                if len(variety_fold) < _MIN_FOLD:
                    continue
                if folded == variety_fold:
                    exact.append(
                        {
                            "variety_id": variety_id,
                            "variety_name": variety.get("name") or variety_id,
                            "matched_on": f"{role}->{variety_role}",
                            "matched_value": original,
                            "reason": "exact_identity_string",
                        }
                    )
                    break
            else:
                continue
            break
        else:
            for folded, original, role in query_folds:
                folded_tokens = folded.split()
                for variety_text, variety_role in _identity_strings(variety):
                    variety_fold = fold_identity(variety_text)
                    variety_tokens = variety_fold.split()
                    if len(variety_tokens) >= 2 and _contiguous(variety_tokens, folded_tokens):
                        token_overlap.append(
                            {
                                "variety_id": variety_id,
                                "variety_name": variety.get("name") or variety_id,
                                "matched_on": f"{role}->{variety_role}",
                                "matched_value": original,
                                "reason": "contiguous_token_overlap",
                            }
                        )
                        break
                    if len(folded_tokens) >= 2 and _contiguous(folded_tokens, variety_tokens):
                        token_overlap.append(
                            {
                                "variety_id": variety_id,
                                "variety_name": variety.get("name") or variety_id,
                                "matched_on": f"{role}->{variety_role}",
                                "matched_value": original,
                                "reason": "contiguous_token_overlap",
                            }
                        )
                        break

    if exact:
        primary = exact[0]
        return {
            "identity_state": STATE_POSSIBLE_ALIAS,
            "identity_label": LABELS[STATE_POSSIBLE_ALIAS],
            "candidate_canonical_match": primary["variety_id"],
            "match_reason": primary["reason"],
            "matched_value": primary["matched_value"],
            "matches": exact,
            "auto_confirmed": False,
        }
    if token_overlap:
        primary = token_overlap[0]
        return {
            "identity_state": STATE_UNKNOWN,
            "identity_label": LABELS[STATE_UNKNOWN],
            "candidate_canonical_match": None,
            "match_reason": primary["reason"],
            "matched_value": primary["matched_value"],
            "matches": token_overlap,
            "auto_confirmed": False,
        }
    return {
        "identity_state": STATE_DISTINCT,
        "identity_label": LABELS[STATE_DISTINCT],
        "candidate_canonical_match": None,
        "match_reason": "no_canonical_identity_match",
        "matched_value": "",
        "matches": [],
        "auto_confirmed": False,
    }
