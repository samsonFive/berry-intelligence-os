"""People Watchlist from existing public corpus — no invented people.

Reads inventor / named-breeder fields already stored on trusted entities.
Social coverage is always provider-unavailable. Mention coverage is
discovery-only (patent/program records), never active social monitoring.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

def _monogram(name: str) -> str:
    parts = [part for part in re.split(r"\s+", name.strip()) if part]
    if len(parts) >= 2:
        return (parts[0][:1] + parts[1][:1]).upper()
    return (name[:2] or "BI").upper()

NAME_KEYS = (
    "inventor",
    "named_inventors",
    "inventors_listed_on_patent",
    "lead_breeder",
)
_NAME_RE = re.compile(r"^[A-Z][A-Za-zÀ-ÿ'.\-]+(?:\s+[A-Z][A-Za-zÀ-ÿ'.\-]+){1,3}$")
_TITLE_RE = re.compile(r"^(Dr|Prof|Professor|Mr|Mrs|Ms|Miss)\.?\s+", re.IGNORECASE)
_PAREN_RE = re.compile(r"\s*\([^)]*\)\s*")
_ORG_RE = re.compile(
    r"\b(university|holdings|pty|ltd|inc|llc|group|breeding|program|company|farms?|nursery|institute|college|ab|bv|sa)\b",
    re.IGNORECASE,
)


def _as_names(value: Any) -> list[str]:
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def clean_person_name(name: str) -> str:
    """Strip titles and parenthetical notes. Does not invent a different person."""
    text = _PAREN_RE.sub(" ", str(name or "")).strip()
    text = _TITLE_RE.sub("", text).strip()
    return " ".join(text.split())


def _valid_person_name(name: str) -> bool:
    if len(name) < 5 or len(name) > 80:
        return False
    if name.lower() in {"unknown", "n/a", "none"}:
        return False
    if _ORG_RE.search(name):
        return False
    return bool(_NAME_RE.match(name))


def person_id(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-")
    return f"person-{slug}"


def discover_people(entities: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build unique people from structured inventor/breeder fields only."""
    by_id: dict[str, dict[str, Any]] = {}
    for entity in entities:
        attributes = entity.get("attributes") if isinstance(entity.get("attributes"), dict) else {}
        names: list[str] = []
        for key in NAME_KEYS:
            names.extend(_as_names(attributes.get(key)))
        crop_ids = [str(item) for item in (entity.get("berry_ids") or [])]
        for raw_name in names:
            name = clean_person_name(raw_name)
            if not _valid_person_name(name):
                continue
            pid = person_id(name)
            row = by_id.setdefault(
                pid,
                {
                    "id": pid,
                    "canonical_name": name,
                    "aliases": [],
                    "entity_ids": [],
                    "entity_names": [],
                    "crops": [],
                    "source_record_ids": [],
                    "source_record_names": [],
                    "monitoring_enabled": True,
                    "monitoring_coverage": "discovery-only",
                    "social_coverage": "provider-unavailable",
                    "verification_status": "discovery-only",
                    "watch_rationale": "Named on a public patent or breeding-program record already in the catalog.",
                    "public_profile_urls": [],
                    "profile_url": f"/people/{pid}",
                    "monogram": _monogram(name),
                },
            )
            entity_id = str(entity.get("id") or "")
            entity_name = str(entity.get("name") or entity_id)
            if entity_id and entity_id not in row["source_record_ids"]:
                row["source_record_ids"].append(entity_id)
                row["source_record_names"].append(entity_name)
            if entity.get("entity_type") in {"company", "breeding_program", "brand"} and entity_id:
                if entity_id not in row["entity_ids"]:
                    row["entity_ids"].append(entity_id)
                    row["entity_names"].append(entity_name)
            for crop in crop_ids:
                if crop and crop not in row["crops"]:
                    row["crops"].append(crop)
    people = sorted(by_id.values(), key=lambda row: row["canonical_name"].casefold())
    return people


def people_model(entities: Iterable[dict[str, Any]]) -> dict[str, Any]:
    people = discover_people(entities)
    return {
        "people": people,
        "count": len(people),
        "social_coverage": "provider-unavailable",
        "mention_coverage": "discovery-only",
        "disclosure": (
            "People are listed only when a public patent or breeding-program "
            "record in this catalog already names them. LinkedIn, Instagram, "
            "and Facebook adapters are provider-unavailable. Discovery-only "
            "is not active social monitoring."
        ),
    }


def person_by_id(entities: Iterable[dict[str, Any]], person_id_value: str) -> dict[str, Any] | None:
    for row in discover_people(entities):
        if row["id"] == person_id_value:
            return row
    return None


def match_people(text: str, people: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    hay = (text or "").casefold()
    found: list[dict[str, Any]] = []
    seen: set[str] = set()
    for person in people:
        name = str(person.get("canonical_name") or "").strip()
        pid = str(person.get("id") or "")
        if not name or len(name) < 5 or pid in seen:
            continue
        if name.casefold() in hay:
            seen.add(pid)
            found.append(person)
    return found
