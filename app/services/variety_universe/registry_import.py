"""Structured registry-row import → inbox Variety candidates.

Accepts already-parsed public registry/catalog rows. Does not scrape HTML
from templates or routes. Does not write trusted data/. A row without a
source id/url is rejected. Exact duplicates of an existing candidate or
canonical registration identifier are recorded as duplicates, not new
candidates. Identity is resolved but never auto-confirmed.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from app.services.variety_universe.candidates import (
    CANDIDATE_RECORD_TYPE,
    persist_variety_candidates,
)
from app.services.variety_universe.identity import (
    LABELS,
    STATE_REJECTED,
    fold_identity,
    resolve_identity,
)

ALLOWED_SOURCE_TIERS = {
    "tier_1_registry",
    "tier_1_breeder_catalog",
    "tier_1_patent_pvr",
    "tier_1_national_register",
    "tier_2_trial",
    "tier_2_technical_sheet",
    "tier_2_nursery_catalog",
    "tier_2_grower_program",
    "tier_3_trade_press",
    "tier_3_retail_disclosure",
    "tier_3_conference",
    "weak_noncanonical_lead",
}

WEAK_TIERS = {"weak_noncanonical_lead"}


class RegistryImportError(ValueError):
    pass


def candidate_id_for(row: dict[str, Any]) -> str:
    seed = "|".join(
        [
            fold_identity(str(row.get("jurisdiction") or "")),
            fold_identity(str(row.get("application_number") or row.get("grant_number") or row.get("registration_id") or "")),
            fold_identity(str(row.get("candidate_name") or row.get("denomination") or "")),
            fold_identity(str(row.get("berry_id") or "")),
            fold_identity(str(row.get("source_id") or "")),
        ]
    )
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]
    return f"vcand-{digest}"


def validate_source(row: dict[str, Any]) -> str | None:
    source_id = str(row.get("source_id") or "").strip()
    source_url = str(row.get("source_url") or "").strip()
    if not source_id and not source_url:
        return "no-source candidate rejected"
    tier = str(row.get("source_tier") or "").strip()
    if tier and tier not in ALLOWED_SOURCE_TIERS:
        return f"unknown source_tier {tier!r}"
    return None


def build_candidate(
    row: dict[str, Any],
    *,
    varieties: list[dict[str, Any]],
    discovered_at: str | None = None,
) -> dict[str, Any]:
    rejection = validate_source(row)
    stamp = discovered_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    name = str(row.get("candidate_name") or row.get("denomination") or "").strip()
    if not name and not rejection:
        rejection = "candidate name missing"
    payload: dict[str, Any] = {
        "id": row.get("id") or candidate_id_for(row),
        "record_type": CANDIDATE_RECORD_TYPE,
        "status": "proposed",
        "candidate_name": name,
        "berry_id": row.get("berry_id") or "",
        "berry_ids": [row["berry_id"]] if row.get("berry_id") else list(row.get("berry_ids") or []),
        "source_id": row.get("source_id") or "",
        "source_type": row.get("source_type") or "",
        "source_tier": row.get("source_tier") or "",
        "source_label": row.get("source_label") or row.get("source_id") or "",
        "source_url": row.get("source_url") or "",
        "jurisdiction": row.get("jurisdiction") or "",
        "geography_id": row.get("geography_id") or "",
        "breeder_owner": row.get("breeder_owner") or row.get("applicant") or "",
        "applicant": row.get("applicant") or "",
        "breeder_code": row.get("breeder_code") or row.get("breeders_reference") or "",
        "denomination": row.get("denomination") or "",
        "trade_name": row.get("trade_name") or "",
        "aliases": list(row.get("aliases") or []),
        "application_number": row.get("application_number") or "",
        "grant_number": row.get("grant_number") or "",
        "registration": {
            "jurisdiction": row.get("jurisdiction") or "",
            "application_number": row.get("application_number") or "",
            "grant_number": row.get("grant_number") or "",
            "application_date": row.get("application_date") or "",
            "grant_date": row.get("grant_date") or row.get("granting_date") or "",
            "status": row.get("registration_status") or row.get("title_status") or "",
            "expiry": row.get("expiration_date") or "",
            "official_registry_source": row.get("source_id") or "",
        },
        "deployment": row.get("deployment") or {},
        "knowledge": row.get("knowledge") or {},
        "discovered_at": stamp,
        "human_gated": False,
        "auto_confirmed": False,
        "proposed_relationships": list(row.get("proposed_relationships") or []),
    }
    if rejection:
        payload["status"] = "rejected"
        payload["identity_state"] = STATE_REJECTED
        payload["identity_label"] = LABELS[STATE_REJECTED]
        payload["rejection_reason"] = rejection
        payload["candidate_canonical_match"] = None
        payload["match_reason"] = rejection
        payload["matches"] = []
        return payload
    resolution = resolve_identity(payload, varieties)
    payload.update(
        {
            "identity_state": resolution["identity_state"],
            "identity_label": resolution["identity_label"],
            "candidate_canonical_match": resolution["candidate_canonical_match"],
            "match_reason": resolution["match_reason"],
            "matched_value": resolution.get("matched_value") or "",
            "matches": resolution["matches"],
            "auto_confirmed": False,
        }
    )
    return payload


def import_registry_rows(
    rows: list[dict[str, Any]],
    *,
    varieties: list[dict[str, Any]],
    inbox_dir: Path,
    discovered_at: str | None = None,
) -> dict[str, Any]:
    built = [build_candidate(row, varieties=varieties, discovered_at=discovered_at) for row in rows]
    duplicates = [row for row in built if row.get("match_reason") == "same_registration_identifier"]
    exact_name_dupes = [
        row
        for row in built
        if row.get("identity_state") == "possible_alias" and row.get("match_reason") == "exact_identity_string"
    ]
    rejected = [row for row in built if row.get("status") == "rejected"]
    persistable = [row for row in built if row.get("status") != "rejected"]
    written = persist_variety_candidates(persistable, inbox_dir=inbox_dir)
    return {
        "input_count": len(rows),
        "built_count": len(built),
        "written_count": len(written),
        "rejected_count": len(rejected),
        "exact_canonical_duplicates": len(exact_name_dupes),
        "registration_duplicates": len(duplicates),
        "distinct_new": sum(1 for row in persistable if row.get("identity_state") == "distinct"),
        "possible_alias": sum(1 for row in persistable if row.get("identity_state") == "possible_alias"),
        "unknown": sum(1 for row in persistable if row.get("identity_state") == "unknown"),
        "candidates": built,
        "written_ids": [path.stem for path in written],
    }


def load_registry_rows(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("rows"), list):
        return [row for row in payload["rows"] if isinstance(row, dict)]
    raise RegistryImportError(f"unsupported registry fixture shape: {path}")
