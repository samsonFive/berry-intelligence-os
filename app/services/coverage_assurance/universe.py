"""Body-free Source Universe / Coverage Registry.

A row is a publisher, registry, or resource that is strategically relevant
whether or not it is currently an onboarded Source. Article bodies are never
stored. Overlaying `sources.json` does not write this file.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.services.coverage_assurance.classes import SOURCE_CLASS_LABELS, source_class_of
from app.services.recall_audit.classify import hostname, publisher_hosts

BERRY_SCOPE = (
    "berry-blueberry",
    "berry-raspberry",
    "berry-strawberry",
    "berry-blackberry",
)

BERRY_LABELS = {
    "berry-blueberry": "Blueberry",
    "berry-raspberry": "Raspberry",
    "berry-strawberry": "Strawberry",
    "berry-blackberry": "Blackberry",
    "blueberry": "Blueberry",
    "raspberry": "Raspberry",
    "strawberry": "Strawberry",
    "blackberry": "Blackberry",
}

GEOGRAPHY_BUCKETS = (
    ("eu", "EU / Europe"),
    ("uk", "UK"),
    ("za", "South Africa"),
    ("us", "United States"),
    ("canada", "Canada"),
    ("mexico", "Mexico"),
    ("chile", "Chile"),
    ("peru", "Peru"),
    ("au_nz", "Australia / New Zealand"),
    ("other", "Other canonical regions"),
)

_GEO_ALIASES = {
    "eu": "eu",
    "europe": "eu",
    "eu/europe": "eu",
    "geography-europe": "eu",
    "uk": "uk",
    "united kingdom": "uk",
    "gb": "uk",
    "geography-united-kingdom": "uk",
    "za": "za",
    "south africa": "za",
    "geography-south-africa": "za",
    "africa": "other",
    "us": "us",
    "usa": "us",
    "united states": "us",
    "geography-united-states": "us",
    "canada": "canada",
    "geography-canada": "canada",
    "mexico": "mexico",
    "geography-mexico": "mexico",
    "chile": "chile",
    "geography-chile": "chile",
    "peru": "peru",
    "geography-peru": "peru",
    "au": "au_nz",
    "nz": "au_nz",
    "australia": "au_nz",
    "new zealand": "au_nz",
    "australia/new zealand": "au_nz",
    "geography-australia": "au_nz",
    "geography-new-zealand": "au_nz",
    "north_america": "other",
    "south_america": "other",
    "asia_pacific": "other",
    "global": "other",
}

_BERRY_ALIASES = {
    "blueberry": "berry-blueberry",
    "berry-blueberry": "berry-blueberry",
    "raspberry": "berry-raspberry",
    "berry-raspberry": "berry-raspberry",
    "strawberry": "berry-strawberry",
    "berry-strawberry": "berry-strawberry",
    "blackberry": "berry-blackberry",
    "berry-blackberry": "berry-blackberry",
}


def berry_tokens(values: Any) -> set[str]:
    tokens: set[str] = set()
    if isinstance(values, str):
        values = [values]
    for item in values or []:
        mapped = _BERRY_ALIASES.get(str(item).strip().casefold())
        if mapped:
            tokens.add(mapped)
        elif str(item).startswith("berry-"):
            tokens.add(str(item))
    return tokens


def geography_tokens(values: Any) -> set[str]:
    tokens: set[str] = set()
    if isinstance(values, str):
        values = [values]
    for item in values or []:
        mapped = _GEO_ALIASES.get(str(item).strip().casefold())
        if mapped:
            tokens.add(mapped)
    return tokens


def universe_path(data_dir: Path) -> Path:
    return Path(data_dir) / "configuration" / "source_universe.json"


def load_universe(data_dir: Path) -> dict[str, Any]:
    path = universe_path(data_dir)
    if not path.is_file():
        return {"schema_version": 1, "entries": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {"schema_version": 1, "entries": []}
    entries = payload.get("entries") or []
    normalized = []
    for row in entries:
        if not isinstance(row, dict):
            continue
        host = hostname(row.get("hostname") or row.get("domain"))
        if not host:
            continue
        item = dict(row)
        item["hostname"] = host
        item.pop("body", None)
        item.pop("article_body", None)
        item.pop("html", None)
        if item.get("source_class") not in SOURCE_CLASS_LABELS:
            item["source_class"] = item.get("source_class") or "trade_press"
        item["berry_scope"] = sorted(berry_tokens(item.get("berry_scope") or item.get("berry_ids")))
        item["geography"] = sorted(geography_tokens(item.get("geography") or item.get("geography_ids")))
        normalized.append(item)
    payload["entries"] = normalized
    return payload


def overlay_source(source: dict[str, Any], universe_row: dict[str, Any] | None) -> dict[str, Any]:
    """Merge an onboarded Source into a universe-shaped row. Does not write."""
    hosts = sorted(publisher_hosts(source))
    host = hosts[0] if hosts else hostname((source.get("url") or source.get("value")))
    row = dict(universe_row or {})
    row.setdefault("id", f"su-{source.get('id')}")
    row["hostname"] = host or row.get("hostname") or ""
    row["display_name"] = row.get("display_name") or source.get("label") or source.get("id")
    row["known_source_id"] = source.get("id")
    row["source_class"] = row.get("source_class") or source_class_of(source)
    berries = berry_tokens(row.get("berry_scope")) | berry_tokens(source.get("berry_ids"))
    row["berry_scope"] = sorted(berries)
    geos = geography_tokens(row.get("geography")) | geography_tokens(source.get("region_coverage"))
    row["geography"] = sorted(geos)
    row.setdefault("discovery_basis", "onboarded_source")
    row.setdefault("expected_content_type", source.get("type"))
    row["variety_dense"] = bool(row.get("variety_dense"))
    return row
