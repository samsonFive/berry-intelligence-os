"""Deterministic Variety identity resolution.

Never merges records. Never returns CONFIRMED_SAME from text matching.
Exact folded name/alias/code/registration matches are POSSIBLE_ALIAS and
require human review. Contiguous-token overlap without an exact match is
UNKNOWN. No similarity scores, no model inference.
"""

from __future__ import annotations

from typing import Any

from app.services.patent_monitor.entity_link import _fold

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


def fold_identity(value: str | None) -> str:
    return _fold(value or "")


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
    for key, role in (
        ("trade_name", "trade_name"),
        ("commercial_name", "commercial_name"),
        ("denomination", "denomination"),
        ("selection_code", "breeder_code"),
        ("breeder_code", "breeder_code"),
        ("patent_number", "registration"),
        ("patent_id", "registration"),
        ("rights_id", "registration"),
    ):
        text = str(attrs.get(key) or "").strip()
        if text:
            values.append((text, role))
    return values


def _registration_ids(variety: dict[str, Any]) -> set[str]:
    attrs = variety.get("attributes") or {}
    out: set[str] = set()
    for key in ("patent_number", "patent_id", "rights_id", "cpvo_application_number", "grant_number"):
        text = str(attrs.get(key) or "").strip()
        if text:
            out.add(fold_identity(text))
    return {item for item in out if item}


def candidate_registration_ids(candidate: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for key in (
        "registration_id",
        "application_number",
        "grant_number",
        "patent_number",
    ):
        text = str(candidate.get(key) or "").strip()
        if text:
            out.add(fold_identity(text))
    registration = candidate.get("registration") or {}
    if isinstance(registration, dict):
        for key in ("application_number", "grant_number", "registration_number"):
            text = str(registration.get(key) or "").strip()
            if text:
                out.add(fold_identity(text))
    return {item for item in out if item}


def candidate_query_names(candidate: dict[str, Any]) -> list[tuple[str, str]]:
    values: list[tuple[str, str]] = []
    for key, role in (
        ("candidate_name", "candidate_name"),
        ("denomination", "denomination"),
        ("trade_name", "trade_name"),
        ("breeder_code", "breeder_code"),
        ("alias", "alias"),
    ):
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
