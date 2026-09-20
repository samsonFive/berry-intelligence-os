"""Repair and track the 2026-09-18 berry breeding seed without trusting it.

The seed is research, not a competitor master. This module:

- repairs contaminated ``monitoring_status`` URLs;
- refuses to promote ``resolved_website`` to an official domain;
- keeps Candidate-review rows visibly unverified;
- keeps registry/source-system rows out of competitor counts;
- matches existing trusted companies by name/alias/domain and never overwrites them;
- generates mention + official-site watches for tracking.

Does not write ``data/entities/``.
"""

from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

SEED_RELATIVE = Path("data/imports/berry-breeding-seed-2026-09-18/berry_breeding_entities.json")
REGISTRY_ENTITY_TYPE = "registry/source system"
REGISTRY_VERIFICATION = "verified-primary"

VERIFICATION_MAP = {
    "Verified-primary": "verified-primary",
    "Verified-secondary": "verified-secondary",
    "Candidate-review": "candidate-review",
}
TIER_MAP = {
    "Tier 1": "tier1",
    "Tier 2": "tier2",
    "Tier 3": "tier3",
    "Watch": "watch",
    "Muted": "muted",
}
CROP_FLAGS = ("strawberry", "blueberry", "raspberry", "blackberry")


def default_seed_path() -> Path:
    return Path(__file__).resolve().parents[2] / SEED_RELATIVE


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value != value:
        return ""
    text = str(value).strip()
    if text.casefold() == "nan":
        return ""
    return text


def is_http_url(value: Any) -> bool:
    text = _text(value)
    parsed = urlparse(text)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def hostname_of(url: str) -> str:
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    return host


def normalize_name(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("’", "").replace("'", "").replace("`", "")
    text = text.casefold()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\b(inc|llc|ltd|limited|co|company|group|holdings)\b", " ", text)
    return " ".join(text.split())


def parse_aliases(raw: Any) -> list[str]:
    text = str(raw or "").strip()
    if not text:
        return []
    parts = re.split(r"[;|/]+", text)
    return [part.strip() for part in parts if part.strip()]


def seed_track_id(entity_id: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(entity_id or "").strip().lower()).strip("-")
    return f"seed-{slug}" if slug else "seed-unknown"


def repair_row(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize one seed row. Never treat URL-shaped status as a state."""
    monitoring_raw = _text(raw.get("monitoring_status"))
    evidence_url = _text(raw.get("evidence_url"))
    repaired_fields: list[str] = []
    if is_http_url(monitoring_raw):
        if not evidence_url:
            evidence_url = monitoring_raw
        monitoring_status = "watch"
        repaired_fields.append("monitoring_status_url")
    elif monitoring_raw.lower() == "active":
        monitoring_status = "active"
    elif monitoring_raw:
        monitoring_status = "watch"
        repaired_fields.append("monitoring_status_unknown")
    else:
        monitoring_status = "watch"

    website = _text(raw.get("website"))
    resolved_website = _text(raw.get("resolved_website"))
    official_website = website if is_http_url(website) else ""
    if resolved_website and resolved_website != official_website:
        repaired_fields.append("resolved_website_not_official")

    verification = VERIFICATION_MAP.get(str(raw.get("verification_status") or ""), "candidate-review")
    entity_type = str(raw.get("entity_type") or "private company")
    is_registry = entity_type == REGISTRY_ENTITY_TYPE or verification == REGISTRY_VERIFICATION
    if is_registry:
        verification = "verified-primary"
        entity_type = REGISTRY_ENTITY_TYPE

    name = _text(raw.get("competitor_name") or raw.get("canonical_name"))
    aliases = parse_aliases(raw.get("aliases_legacy_names"))
    crops = [crop for crop in CROP_FLAGS if raw.get(crop)]
    tier = TIER_MAP.get(str(raw.get("monitoring_tier") or ""), "tier2")
    candidate = verification == "candidate-review"
    status = "unverified"  # seed never becomes trusted publication
    if is_registry:
        status = "active"

    social = {
        "facebook_url": _text(raw.get("facebook_url")),
        "instagram_url": _text(raw.get("instagram_url")),
        "linkedin_url": _text(raw.get("linkedin_url")),
        "social_verification": _text(raw.get("social_verification")),
    }
    watches = [{"kind": "mention", "query": name, "enabled": True}]
    if official_website:
        watches.append({"kind": "official_site", "url": official_website, "enabled": True})
    if is_registry:
        watches = [{"kind": "registry_source", "url": official_website or resolved_website, "enabled": True}]

    return {
        "seed_id": str(raw.get("entity_id") or ""),
        "canonical_name": name,
        "aliases": aliases,
        "legal_name": name,
        "seed_entity_type": entity_type,
        "country_hq": _text(raw.get("country_hq")),
        "parent_or_successor": _text(raw.get("parent_or_successor")),
        "official_website": official_website,
        "resolved_website": resolved_website if is_http_url(resolved_website) else "",
        "logo_source_url": _text(raw.get("logo_image_url")),
        "logo_rights_status": "discovery-only",
        "crops": crops,
        "roles": [
            role
            for role, flag in (
                ("commercial_sales", raw.get("commercial_sales")),
                ("marketing", raw.get("marketing")),
                ("technology", raw.get("technology")),
                ("genetics", raw.get("genetics")),
                ("breeding", raw.get("breeding")),
            )
            if flag
        ],
        "global_activity": bool(raw.get("global_activity")),
        "monitoring_tier": tier,
        "monitoring_status": monitoring_status,
        "monitoring_enabled": True,
        "verification_status": verification,
        "status": status,
        "candidate": candidate,
        "is_registry": is_registry,
        "evidence_url": evidence_url if is_http_url(evidence_url) else "",
        "evidence_summary": _text(raw.get("evidence_summary")),
        "last_verified": _text(raw.get("last_verified")),
        "research_notes": _text(raw.get("research_notes")),
        "social": social,
        "watches": watches,
        "repaired_fields": repaired_fields,
        "trusted_entity_id": None,
        "id": seed_track_id(str(raw.get("entity_id") or "")),
        "entity_type": "source" if is_registry else "company",
        "competitor": not is_registry,
    }


def load_seed_rows(path: Path | None = None) -> list[dict[str, Any]]:
    seed_path = path or default_seed_path()
    payload = json.loads(seed_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("seed must be a JSON list")
    return [row for row in payload if isinstance(row, dict)]


def _existing_indexes(existing: Iterable[dict[str, Any]]) -> tuple[dict[str, str], dict[str, str]]:
    by_name: dict[str, str] = {}
    by_host: dict[str, str] = {}
    for entity in existing:
        entity_id = str(entity.get("id") or "")
        if not entity_id or entity.get("entity_type") not in {None, "company", "brand", "breeding_program"}:
            continue
        names = [entity.get("name"), *(entity.get("aliases") or [])]
        for raw in names:
            key = normalize_name(str(raw or ""))
            if key and key not in by_name:
                by_name[key] = entity_id
        attributes = entity.get("attributes") if isinstance(entity.get("attributes"), dict) else {}
        for url in (
            entity.get("website"),
            attributes.get("website"),
            attributes.get("official_website"),
        ):
            host = hostname_of(str(url or ""))
            if host and host not in by_host:
                by_host[host] = entity_id
    return by_name, by_host


def reconcile_row(row: dict[str, Any], *, by_name: dict[str, str], by_host: dict[str, str]) -> dict[str, Any]:
    matched = None
    keys = [normalize_name(row["canonical_name"]), *[normalize_name(alias) for alias in row["aliases"]]]
    for key in keys:
        if key and key in by_name:
            matched = by_name[key]
            break
    if not matched and row["official_website"]:
        host = hostname_of(row["official_website"])
        if host in by_host:
            matched = by_host[host]
    out = dict(row)
    if matched:
        out["trusted_entity_id"] = matched
        out["id"] = matched
        # Keep seed verification visible; do not inherit trusted publication.
    return out


def build_roster(
    existing: Iterable[dict[str, Any]] | None = None,
    *,
    seed_path: Path | None = None,
) -> list[dict[str, Any]]:
    by_name, by_host = _existing_indexes(existing or [])
    rows = [repair_row(raw) for raw in load_seed_rows(seed_path)]
    return [reconcile_row(row, by_name=by_name, by_host=by_host) for row in rows]


def roster_counts(roster: list[dict[str, Any]]) -> dict[str, int]:
    competitors = [row for row in roster if row["competitor"]]
    registries = [row for row in roster if row["is_registry"]]
    return {
        "seed_records": len(roster),
        "tracked_companies": len(competitors),
        "registries": len(registries),
        "candidates": sum(1 for row in competitors if row["candidate"]),
        "researched_secondary": sum(1 for row in competitors if row["verification_status"] == "verified-secondary"),
        "matched_trusted": sum(1 for row in competitors if row.get("trusted_entity_id")),
        "seed_only": sum(1 for row in competitors if not row.get("trusted_entity_id")),
        "official_site_watches": sum(
            1 for row in competitors for watch in row["watches"] if watch["kind"] == "official_site"
        ),
        "mention_watches": sum(1 for row in competitors for watch in row["watches"] if watch["kind"] == "mention"),
        "monitoring_status_repaired": sum(1 for row in roster if "monitoring_status_url" in row["repaired_fields"]),
    }


def tracked_entities(roster: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Entity-shaped rows for Today matching and chips. Registries included for mention match, not counts."""
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in roster:
        entity_id = str(item.get("id") or "")
        if not entity_id or entity_id in seen:
            continue
        seen.add(entity_id)
        rows.append(
            {
                "id": entity_id,
                "name": item["canonical_name"],
                "aliases": list(item.get("aliases") or []),
                "entity_type": item["entity_type"],
                "status": item["status"],
                "verification_status": item["verification_status"],
                "is_registry": item["is_registry"],
                "competitor": item["competitor"],
                "berry_ids": [f"berry-{crop}" for crop in item.get("crops") or []],
                "seed_id": item.get("seed_id"),
            }
        )
    return rows


def merge_entities_for_matching(
    existing: Iterable[dict[str, Any]],
    roster: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Trusted entities first; add seed-only rows. Do not replace trusted records."""
    merged: dict[str, dict[str, Any]] = {}
    for entity in existing:
        entity_id = str(entity.get("id") or "")
        if entity_id:
            merged[entity_id] = dict(entity)
    for entity in tracked_entities(roster):
        entity_id = entity["id"]
        if entity_id in merged:
            current = merged[entity_id]
            aliases = list(current.get("aliases") or [])
            for alias in entity.get("aliases") or []:
                if alias not in aliases:
                    aliases.append(alias)
            current["aliases"] = aliases
            if not current.get("verification_status"):
                current["verification_status"] = entity["verification_status"]
            continue
        merged[entity_id] = entity
    return list(merged.values())


def official_hosts(roster: list[dict[str, Any]]) -> set[str]:
    hosts: set[str] = set()
    for row in roster:
        if row.get("official_website"):
            host = hostname_of(row["official_website"])
            if host:
                hosts.add(host)
    return hosts


def official_host_map(roster: list[dict[str, Any]]) -> dict[str, str]:
    """Official website host -> roster entity id. Caps belong at the caller."""
    mapping: dict[str, str] = {}
    for row in roster:
        entity_id = str(row.get("id") or "")
        host = hostname_of(str(row.get("official_website") or ""))
        if entity_id and host and host not in mapping:
            mapping[host] = entity_id
    return mapping


def official_social_channels(row: dict[str, Any]) -> list[dict[str, str]]:
    """Seed social URLs stay discovery-only. Never marked official/verified."""
    social = row.get("social") if isinstance(row.get("social"), dict) else {}
    channels: list[dict[str, str]] = []
    for platform, key in (
        ("facebook", "facebook_url"),
        ("instagram", "instagram_url"),
        ("linkedin", "linkedin_url"),
    ):
        url = str(social.get(key) or "").strip()
        if not is_http_url(url):
            continue
        channels.append(
            {
                "platform": platform,
                "url": url,
                "official_status": "unverified",
                "coverage": "provider-unavailable",
                "source": "seed-discovery",
            }
        )
    return channels


def related_from_seed_note(row: dict[str, Any], roster: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Link parent/successor only when another roster name appears in the seed note."""
    note = str(row.get("parent_or_successor") or "").casefold()
    if len(note) < 8:
        return []
    related: list[dict[str, str]] = []
    self_id = str(row.get("id") or "")
    for other in roster:
        other_id = str(other.get("id") or "")
        if not other_id or other_id == self_id:
            continue
        name = str(other.get("canonical_name") or "").strip()
        if len(name) < 6 or name.casefold() not in note:
            continue
        related.append(
            {
                "id": other_id,
                "name": name,
                "profile_url": profile_url(other),
                "evidence": "seed parent_or_successor note",
            }
        )
    return related


def profile_url(row: dict[str, Any]) -> str:
    entity_id = str(row.get("id") or "")
    if entity_id.startswith("breeding_program-"):
        return f"/entities/breeding_program/{entity_id}?view=feed"
    if entity_id.startswith("brand-"):
        return f"/entities/brand/{entity_id}?view=feed"
    return f"/entities/company/{entity_id}?view=feed"


def filter_roster(
    roster: list[dict[str, Any]],
    *,
    crop: str = "",
    verification: str = "",
    q: str = "",
    include_registries: bool = False,
) -> list[dict[str, Any]]:
    needle = q.casefold().strip()
    rows: list[dict[str, Any]] = []
    for row in roster:
        if row["is_registry"] and not include_registries:
            continue
        if crop and crop not in row["crops"]:
            continue
        if verification and row["verification_status"] != verification:
            continue
        if needle:
            hay = " ".join(
                [row["canonical_name"], " ".join(row["aliases"]), row.get("country_hq") or "", row.get("seed_id") or ""]
            ).casefold()
            if needle not in hay:
                continue
        rows.append(row)
    rows.sort(key=lambda item: (item["canonical_name"].casefold(), item["seed_id"]))
    return rows


def following_model(
    existing: Iterable[dict[str, Any]],
    *,
    crop: str = "",
    verification: str = "",
    q: str = "",
    include_registries: bool = False,
    seed_path: Path | None = None,
    entity_tiers: dict[str, str] | None = None,
) -> dict[str, Any]:
    roster = build_roster(existing, seed_path=seed_path)
    counts = roster_counts(roster)
    rows = filter_roster(
        roster,
        crop=crop,
        verification=verification,
        q=q,
        include_registries=include_registries,
    )
    presented = []
    tiers = entity_tiers or {}
    for row in rows:
        tier = str(tiers.get(row["id"]) or row.get("monitoring_tier") or "tier2")
        presented.append(
            {
                **row,
                "profile_url": profile_url(row),
                "monogram": _monogram(row["canonical_name"]),
                "logo_url": logo_display_url(row),
                "verification_label": _verification_label(row),
                "watch_labels": [watch["kind"].replace("_", " ") for watch in row["watches"]],
                "social_channels": official_social_channels(row),
                "related_entities": related_from_seed_note(row, roster),
                "monitoring_tier": tier,
                "muted": tier == "muted",
            }
        )
    return {
        "rows": presented,
        "counts": counts,
        "registries": [row for row in roster if row["is_registry"]],
        "filters": {
            "crop": crop,
            "verification": verification,
            "q": q,
            "include_registries": include_registries,
        },
        "roster": roster,
    }


def seed_profile(entity_id: str, existing: Iterable[dict[str, Any]], *, seed_path: Path | None = None) -> dict[str, Any] | None:
    roster = build_roster(existing, seed_path=seed_path)
    for row in roster:
        if row["id"] == entity_id or row["seed_id"] == entity_id or seed_track_id(row["seed_id"]) == entity_id:
            return {
                **row,
                "profile_url": profile_url(row),
                "monogram": _monogram(row["canonical_name"]),
                "logo_url": logo_display_url(row),
                "verification_label": _verification_label(row),
                "social_channels": official_social_channels(row),
                "related_entities": related_from_seed_note(row, roster),
            }
    return None


@lru_cache(maxsize=1)
def cached_seed_rows() -> tuple[dict[str, Any], ...]:
    return tuple(repair_row(raw) for raw in load_seed_rows())


def _monogram(name: str) -> str:
    parts = [part for part in re.split(r"\s+", name.strip()) if part]
    if len(parts) >= 2:
        return (parts[0][:1] + parts[1][:1]).upper()
    return (name[:2] or "BI").upper()


def logo_display_url(row: dict[str, Any]) -> str:
    raw = str(row.get("logo_source_url") or "").strip()
    parsed = urlparse(raw)
    if parsed.scheme in {"http", "https"} and parsed.hostname and not parsed.username:
        return raw
    for key in ("official_website", "resolved_website"):
        host = (urlparse(str(row.get(key) or "")).hostname or "").removeprefix("www.")
        if host:
            return f"https://www.google.com/s2/favicons?sz=128&domain={host}"
    return ""


def _verification_label(row: dict[str, Any]) -> str:
    if row["is_registry"]:
        return "Registry / source system"
    if row["candidate"]:
        return "Candidate · unverified"
    if row["verification_status"] == "verified-secondary":
        return "Researched · secondary (not trusted publication)"
    return row["verification_status"]
