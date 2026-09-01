"""Canonical entity identity integrity.

Read-only audit and deterministic ID canonicalization. Never invents a
match from similarity. Never auto-merges. CONFIRMED_DUPLICATE is only
emitted for exact folded-name/alias collisions, explicit redirects, or
an explicit merged_into pointer already on the record.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from app.services.global_search import _names_for_entity
from app.services.patent_monitor.entity_link import _fold
from app.services.variety_universe.identity import (
    _identity_strings,
    _registration_ids,
    candidate_query_names,
    candidate_registration_ids,
    fold_identity,
)

STATE_CONFIRMED_DUPLICATE = "confirmed_duplicate"
STATE_LIKELY_RELATED = "likely_related"
STATE_DISTINCT = "distinct"
STATE_UNKNOWN = "unknown"

LABELS = {
    STATE_CONFIRMED_DUPLICATE: "CONFIRMED DUPLICATE",
    STATE_LIKELY_RELATED: "LIKELY RELATED / NEEDS REVIEW",
    STATE_DISTINCT: "DISTINCT",
    STATE_UNKNOWN: "UNKNOWN",
}

REDIRECTS_RELATIVE = Path("configuration") / "entity-identity-redirects.json"
_MIN_FOLD = 3
_DUPLICATE_ID_RE = re.compile(r"-(?:2|copy|duplicate|old)$", re.IGNORECASE)
_ID_FIELD_KEYS = ("entity_ids", "company_ids", "variety_ids", "geography_ids")


def fold_name(value: str | None) -> str:
    return _fold(value or "")


def load_identity_redirects(data_dir: Path | None) -> list[dict[str, Any]]:
    if data_dir is None:
        return []
    path = Path(data_dir) / REDIRECTS_RELATIVE
    if not path.is_file():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("redirects") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict) and row.get("retired_id") and row.get("surviving_id")]


def redirect_map(redirects: list[dict[str, Any]] | None) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for row in redirects or []:
        retired = str(row.get("retired_id") or "").strip()
        surviving = str(row.get("surviving_id") or "").strip()
        if retired and surviving and retired != surviving:
            mapping[retired] = surviving
    return mapping


def merged_into_id(entity: dict[str, Any] | None) -> str:
    if not entity:
        return ""
    attrs = entity.get("attributes") or {}
    return str(attrs.get("merged_into") or entity.get("merged_into") or "").strip()


def is_retired_entity(entity: dict[str, Any] | None, *, redirects: dict[str, str] | None = None) -> bool:
    if not entity:
        return False
    entity_id = str(entity.get("id") or "")
    if merged_into_id(entity):
        return True
    return bool(entity_id and redirects and entity_id in redirects)


def retired_entity_ids(
    entities: list[dict[str, Any]],
    *,
    redirects: list[dict[str, Any]] | dict[str, str] | None = None,
) -> set[str]:
    mapping = redirects if isinstance(redirects, dict) else redirect_map(redirects)
    retired = set(mapping)
    for entity in entities:
        entity_id = str(entity.get("id") or "")
        if entity_id and is_retired_entity(entity, redirects=mapping):
            retired.add(entity_id)
    return retired


def canonical_entity_id(
    entity_id: str,
    *,
    entities: dict[str, dict[str, Any]] | list[dict[str, Any]] | None = None,
    redirects: list[dict[str, Any]] | dict[str, str] | None = None,
) -> str:
    """Follow explicit redirects / merged_into. Cycles stop on the first repeat."""
    current = str(entity_id or "").strip()
    if not current:
        return ""
    index = entities if isinstance(entities, dict) else {str(row["id"]): row for row in (entities or []) if row.get("id")}
    mapping = redirects if isinstance(redirects, dict) else redirect_map(redirects)
    seen: set[str] = set()
    while current and current not in seen:
        seen.add(current)
        nxt = mapping.get(current) or merged_into_id(index.get(current))
        if not nxt or nxt == current:
            break
        current = nxt
    return current


def living_entities(
    entities: list[dict[str, Any]],
    *,
    redirects: list[dict[str, Any]] | dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    retired = retired_entity_ids(entities, redirects=redirects)
    return [row for row in entities if str(row.get("id") or "") not in retired]


def match_named_entity(
    name: str,
    entity_type: str,
    entities: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, tuple[str, ...]]:
    """Exact folded name/alias match. Multiple hits stay ambiguous."""
    query = (name or "").strip()
    if not query:
        return None, ()
    folded = fold_name(query)
    if len(folded) < _MIN_FOLD:
        return None, ()
    hits: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in entities:
        if row.get("entity_type") != entity_type or not row.get("id"):
            continue
        canonical, aliases = _names_for_entity(row)
        surfaces = [canonical, *aliases]
        if any(fold_name(surface) == folded for surface in surfaces if fold_name(surface)):
            entity_id = str(row["id"])
            if entity_id not in seen:
                seen.add(entity_id)
                hits.append(row)
    if len(hits) == 1:
        return hits[0], ()
    if len(hits) > 1:
        return None, tuple(str(row["id"]) for row in hits)
    return None, ()


def _website_host(entity: dict[str, Any]) -> str:
    attrs = entity.get("attributes") or {}
    for key in ("website", "url", "homepage", "domain"):
        raw = str(attrs.get(key) or "").strip()
        if not raw:
            continue
        parsed = urlparse(raw if "://" in raw else f"https://{raw}")
        host = (parsed.hostname or "").casefold()
        if host.startswith("www."):
            host = host[4:]
        return host
    return ""


def _relationship_signature(entity_id: str, relationships: list[dict[str, Any]]) -> frozenset[tuple[str, str, str]]:
    sig: set[tuple[str, str, str]] = set()
    for rel in relationships:
        subject = str(rel.get("subject_id") or "")
        obj = str(rel.get("object_id") or "")
        predicate = str(rel.get("predicate") or "")
        if not predicate:
            continue
        if subject == entity_id and obj:
            sig.add(("out", predicate, obj))
        if obj == entity_id and subject:
            sig.add(("in", predicate, subject))
    return frozenset(sig)


def _pair_key(left: str, right: str) -> tuple[str, str]:
    return (left, right) if left <= right else (right, left)


def _issue(
    *,
    state: str,
    entity_type: str,
    entity_ids: tuple[str, ...],
    reason: str,
    matched_value: str = "",
) -> dict[str, Any]:
    return {
        "state": state,
        "label": LABELS[state],
        "entity_type": entity_type,
        "entity_ids": list(entity_ids),
        "reason": reason,
        "matched_value": matched_value,
    }


def _company_phrase_buckets(entities: list[dict[str, Any]]) -> dict[str, list[str]]:
    buckets: dict[str, list[str]] = {}
    for entity in entities:
        if entity.get("entity_type") != "company" or not entity.get("id"):
            continue
        entity_id = str(entity["id"])
        canonical, aliases = _names_for_entity(entity)
        for surface in (canonical, *aliases):
            folded = fold_name(surface)
            if len(folded) < _MIN_FOLD:
                continue
            bucket = buckets.setdefault(folded, [])
            if entity_id not in bucket:
                bucket.append(entity_id)
    return buckets


def _variety_phrase_buckets(entities: list[dict[str, Any]]) -> dict[str, list[tuple[str, str]]]:
    buckets: dict[str, list[tuple[str, str]]] = {}
    for entity in entities:
        if entity.get("entity_type") != "variety" or not entity.get("id"):
            continue
        entity_id = str(entity["id"])
        for text, role in _identity_strings(entity):
            if role == "registration":
                continue
            folded = fold_identity(text)
            if len(folded) < _MIN_FOLD:
                continue
            bucket = buckets.setdefault(folded, [])
            if not any(item[0] == entity_id for item in bucket):
                bucket.append((entity_id, role))
    return buckets


def audit_entity_identity(
    entities: list[dict[str, Any]],
    *,
    relationships: list[dict[str, Any]] | None = None,
    candidates: list[dict[str, Any]] | None = None,
    redirects: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Body-free integrity report. No similarity scores."""
    relationships = relationships or []
    candidates = candidates or []
    mapping = redirect_map(redirects)
    companies = [row for row in entities if row.get("entity_type") == "company" and row.get("id")]
    varieties = [row for row in entities if row.get("entity_type") == "variety" and row.get("id")]
    living_companies = living_entities(companies, redirects=mapping)
    living_varieties = living_entities(varieties, redirects=mapping)

    company_issues: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str, str, str]] = set()

    def add_company(issue: dict[str, Any]) -> None:
        ids = list(issue["entity_ids"])
        if len(ids) >= 2:
            key = (*_pair_key(ids[0], ids[1]), issue["reason"])
        else:
            key = (ids[0] if ids else "", "", issue["reason"])
        if key in seen_pairs:
            return
        seen_pairs.add(key)
        company_issues.append(issue)

    name_buckets: dict[str, list[str]] = {}
    for company in living_companies:
        folded = fold_name(str(company.get("name") or ""))
        if len(folded) >= _MIN_FOLD:
            name_buckets.setdefault(folded, []).append(str(company["id"]))
    for folded, ids in name_buckets.items():
        if len(ids) > 1:
            add_company(
                _issue(
                    state=STATE_CONFIRMED_DUPLICATE,
                    entity_type="company",
                    entity_ids=tuple(sorted(ids)),
                    reason="exact_normalized_name",
                    matched_value=folded,
                )
            )

    for folded, ids in _company_phrase_buckets(living_companies).items():
        if len(ids) > 1:
            add_company(
                _issue(
                    state=STATE_CONFIRMED_DUPLICATE,
                    entity_type="company",
                    entity_ids=tuple(sorted(ids)),
                    reason="alias_collision",
                    matched_value=folded,
                )
            )

    hosts: dict[str, list[str]] = {}
    for company in living_companies:
        host = _website_host(company)
        if host and host != "example.invalid":
            hosts.setdefault(host, []).append(str(company["id"]))
    for host, ids in hosts.items():
        if len(ids) > 1:
            add_company(
                _issue(
                    state=STATE_LIKELY_RELATED,
                    entity_type="company",
                    entity_ids=tuple(sorted(ids)),
                    reason="shared_website_domain",
                    matched_value=host,
                )
            )

    signatures: dict[frozenset[tuple[str, str, str]], list[str]] = {}
    company_folds = {
        str(company["id"]): fold_name(str(company.get("name") or ""))
        for company in living_companies
    }
    for company in living_companies:
        sig = _relationship_signature(str(company["id"]), relationships)
        if len(sig) >= 2:
            signatures.setdefault(sig, []).append(str(company["id"]))
    for ids in signatures.values():
        if len(ids) < 2:
            continue
        folds = {company_folds.get(entity_id, "") for entity_id in ids}
        if len(folds) == 1 and next(iter(folds)):
            add_company(
                _issue(
                    state=STATE_LIKELY_RELATED,
                    entity_type="company",
                    entity_ids=tuple(sorted(ids)),
                    reason="identical_relationship_set",
                )
            )

    living_ids = {str(row["id"]) for row in living_companies}
    for company in companies:
        entity_id = str(company["id"])
        if not _DUPLICATE_ID_RE.search(entity_id):
            continue
        base = _DUPLICATE_ID_RE.sub("", entity_id)
        if base in living_ids or base in mapping.values() or mapping.get(entity_id):
            survivor = mapping.get(entity_id) or (base if base in living_ids else "")
            add_company(
                _issue(
                    state=STATE_CONFIRMED_DUPLICATE if (survivor or mapping.get(entity_id)) else STATE_LIKELY_RELATED,
                    entity_type="company",
                    entity_ids=tuple(sorted({entity_id, survivor} if survivor else {entity_id})),
                    reason="duplicate_id_suffix",
                    matched_value=entity_id,
                )
            )

    for row in redirects or []:
        retired = str(row.get("retired_id") or "")
        surviving = str(row.get("surviving_id") or "")
        if str(row.get("state") or "") == STATE_CONFIRMED_DUPLICATE and retired.startswith("company-"):
            add_company(
                _issue(
                    state=STATE_CONFIRMED_DUPLICATE,
                    entity_type="company",
                    entity_ids=tuple(sorted({retired, surviving})),
                    reason="explicit_redirect",
                    matched_value=retired,
                )
            )

    variety_issues: list[dict[str, Any]] = []
    variety_seen: set[tuple[str, str, str]] = set()

    def add_variety(issue: dict[str, Any]) -> None:
        ids = issue["entity_ids"][:2]
        if len(ids) < 2:
            key = (ids[0] if ids else "", "", issue["reason"])
        else:
            key = (*_pair_key(ids[0], ids[1]), issue["reason"])
        if key in variety_seen:
            return
        variety_seen.add(key)
        variety_issues.append(issue)

    for folded, rows in _variety_phrase_buckets(living_varieties).items():
        ids = [item[0] for item in rows]
        if len(ids) > 1:
            roles = {item[1] for item in rows}
            reason = "alias_collision"
            if roles <= {"breeder_code"} or "breeder_code" in roles and len(roles) <= 2:
                reason = "breeder_code_collision"
            if roles & {"canonical_name"} and len(roles) == 1:
                reason = "canonical_name_collision"
            add_variety(
                _issue(
                    state=STATE_CONFIRMED_DUPLICATE,
                    entity_type="variety",
                    entity_ids=tuple(sorted(ids)),
                    reason=reason,
                    matched_value=folded,
                )
            )

    reg_buckets: dict[str, list[str]] = {}
    for variety in living_varieties:
        for reg in _registration_ids(variety):
            reg_buckets.setdefault(reg, []).append(str(variety["id"]))
    for reg, ids in reg_buckets.items():
        unique_ids = sorted(set(ids))
        if len(unique_ids) > 1:
            add_variety(
                _issue(
                    state=STATE_CONFIRMED_DUPLICATE,
                    entity_type="variety",
                    entity_ids=tuple(unique_ids),
                    reason="registration_id_collision",
                    matched_value=reg,
                )
            )

    candidate_conflicts: list[dict[str, Any]] = []
    for candidate in candidates:
        if candidate.get("status") == "rejected":
            continue
        matches: list[str] = []
        cand_regs = candidate_registration_ids(candidate)
        for variety in living_varieties:
            variety_id = str(variety["id"])
            if cand_regs and cand_regs & _registration_ids(variety):
                matches.append(variety_id)
                continue
            for text, _role in candidate_query_names(candidate):
                folded = fold_identity(text)
                if len(folded) < _MIN_FOLD:
                    continue
                if any(fold_identity(item) == folded for item, _vr in _identity_strings(variety)):
                    matches.append(variety_id)
                    break
        unique_matches = sorted(set(matches))
        if unique_matches:
            candidate_conflicts.append(
                {
                    "state": STATE_LIKELY_RELATED if len(unique_matches) == 1 else STATE_UNKNOWN,
                    "label": LABELS[STATE_LIKELY_RELATED] if len(unique_matches) == 1 else LABELS[STATE_UNKNOWN],
                    "candidate_id": candidate.get("id"),
                    "candidate_name": candidate.get("candidate_name"),
                    "entity_ids": unique_matches,
                    "reason": "candidate_canonical_identity_match",
                }
            )

    confirmed_companies = [row for row in company_issues if row["state"] == STATE_CONFIRMED_DUPLICATE]
    probable_companies = [row for row in company_issues if row["state"] == STATE_LIKELY_RELATED]
    confirmed_varieties = [row for row in variety_issues if row["state"] == STATE_CONFIRMED_DUPLICATE]
    return {
        "companies": {
            "count": len(living_companies),
            "exact_duplicates": [row for row in confirmed_companies if row["reason"] == "exact_normalized_name"],
            "alias_collisions": [row for row in confirmed_companies if row["reason"] == "alias_collision"],
            "unresolved_probable_duplicates": probable_companies,
            "confirmed_duplicates": confirmed_companies,
            "issues": company_issues,
        },
        "varieties": {
            "count": len(living_varieties),
            "canonical_collisions": confirmed_varieties,
            "candidate_canonical_conflicts": candidate_conflicts,
            "issues": variety_issues,
        },
        "redirects": list(redirects or []),
        "notes": [
            "States are exact-evidence only. No similarity scores.",
            "LIKELY RELATED / NEEDS REVIEW is not a merge instruction.",
        ],
    }


def rewrite_id_list(values: list[Any] | tuple[Any, ...] | None, mapping: dict[str, str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in values or []:
        current = mapping.get(str(raw), str(raw))
        if current and current not in seen:
            seen.add(current)
            out.append(current)
    return out


def rewrite_record_entity_ids(record: dict[str, Any], mapping: dict[str, str]) -> dict[str, Any]:
    """Rewrite explicit ID fields only. Never touches title/summary/body."""
    updated = dict(record)
    for key in _ID_FIELD_KEYS:
        if key in updated:
            updated[key] = rewrite_id_list(updated.get(key), mapping)
    for key in ("subject_id", "object_id", "primary_entity_id"):
        value = updated.get(key)
        if value:
            updated[key] = mapping.get(str(value), str(value))
    return updated
