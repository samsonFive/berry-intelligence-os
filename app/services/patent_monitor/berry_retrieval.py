"""Bounded berry-genetics patent retrieval report.

Prefers USPTO Open Data Portal when BIOS_USPTO_ODP_API_KEY is set.
Falls back to the public Google Patents JSON path. Never writes trusted
Evidence. Never auto-promotes identity.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from app.services.authoritative_registries.events import classify_patent_event
from app.services.patent_monitor.berry_queries import BERRY_ODP_QUERIES, GOOGLE_PATENTS_QUERIES
from app.services.patent_monitor.entity_link import suggest_entity_links
from app.services.patent_monitor.google_patents import search_google_patents
from app.services.patent_monitor.relevance import relevance_decision
from app.services.patent_monitor.uspto_odp import odp_available, search_uspto_odp


def _load_entities(data_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    root = data_dir / "entities"
    if not root.is_dir():
        return rows
    for path in root.rglob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict) and payload.get("id"):
            rows.append(payload)
    return rows


def _newest(filings: list[dict[str, Any]]) -> str | None:
    dates = []
    for row in filings:
        for key in ("publication_date", "grant_date", "filing_date"):
            value = str(row.get(key) or "").strip()
            if value:
                dates.append(value[:10])
    return max(dates) if dates else None


def run_bounded_berry_retrieval(
    *,
    data_dir: Path,
    limit: int = 8,
    odp_search: Callable[..., dict[str, Any]] | None = None,
    google_search: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    entities = _load_entities(data_dir)
    use_odp = odp_available()
    provider = "uspto_odp" if use_odp else "google_patents_json"
    queries = BERRY_ODP_QUERIES if use_odp else GOOGLE_PATENTS_QUERIES
    searcher = odp_search or (search_uspto_odp if use_odp else None)
    google = google_search or search_google_patents
    filings: dict[str, dict[str, Any]] = {}
    failed: list[str] = []
    false_positives = 0
    for name, query in queries:
        try:
            if use_odp:
                result = searcher(query, limit=limit) if searcher else {"hits": []}
            else:
                result = google(query, num=limit)
        except Exception as exc:  # noqa: BLE001 -- isolate one query
            failed.append(f"{name}: {type(exc).__name__}")
            continue
        for hit in result.get("hits") or []:
            decision = relevance_decision(hit)
            if not decision["relevant"]:
                false_positives += 1
                continue
            number = str(hit.get("publication_number") or "")
            if number:
                filings[number] = {**hit, "berry_ids": decision["berry_ids"], "query_name": name}

    rows = list(filings.values())
    assignees: dict[str, int] = {}
    matched_entities: set[str] = set()
    novel: list[str] = []
    events: dict[str, int] = {}
    for filing in rows:
        for name in filing.get("assignees") or []:
            assignees[str(name)] = assignees.get(str(name), 0) + 1
        suggestions = suggest_entity_links(filing, entities)
        for suggestion in suggestions:
            if suggestion.get("match_entity_id"):
                matched_entities.add(str(suggestion["match_entity_id"]))
            elif suggestion.get("role") in {"assignee", "applicant"} and suggestion.get("name"):
                novel.append(str(suggestion["name"]))
        overlay = classify_patent_event(filing)
        events[overlay["event_kind"]] = events.get(overlay["event_kind"], 0) + 1

    return {
        "state": "ok" if rows or not failed else "partial",
        "provider": provider,
        "available": True,
        "odp_key_present": use_odp,
        "reason": None if use_odp else "BIOS_USPTO_ODP_API_KEY absent; used public Google Patents JSON",
        "queries": [name for name, _query in queries],
        "applications_or_grants": len(rows),
        "assignees": sorted(assignees, key=lambda name: (-assignees[name], name)),
        "assignee_counts": assignees,
        "newest_publication": _newest(rows),
        "canonical_entity_matches": len(matched_entities),
        "matched_entity_ids": sorted(matched_entities),
        "novel_entities": sorted(set(novel)),
        "false_positives": false_positives,
        "event_counts": events,
        "failed_queries": failed,
        "sample": [
            {
                "publication_number": row.get("publication_number"),
                "title": row.get("title"),
                "assignees": row.get("assignees"),
                "publication_date": row.get("publication_date") or row.get("grant_date"),
                "berry_ids": row.get("berry_ids"),
                "query_name": row.get("query_name"),
                "trust_state": "UNREVIEWED_PATENT",
            }
            for row in rows[:12]
        ],
        "auto_confirmed": False,
        "trust_state": "UNREVIEWED_PATENT",
    }
