"""Template adapter for /today Daily Intelligence Briefing."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode


def _reader_href(item: dict[str, Any], *, query_string: str) -> str:
    if item.get("kind") == "source":
        return item.get("reader_href") or item.get("diagnostic_url") or "/sources"
    item_id = str(item.get("id") or "")
    if not item_id:
        return item.get("reader_href") or "/today"
    parts = []
    if query_string:
        parts.append(query_string)
    parts.append(urlencode({"reader": item_id}))
    return "/today?" + "&".join(parts)


def _map_item(item: dict[str, Any], *, query_string: str) -> dict[str, Any]:
    row = dict(item)
    row["reader_href"] = _reader_href(row, query_string=query_string)
    # Template alias for recency label if needed.
    row.setdefault("recency_label", row.get("recency_label") or "")
    return row


def _map_reader(reader: dict[str, Any] | None) -> dict[str, Any] | None:
    if not reader:
        return None
    row = dict(reader)
    mode = row.get("reader_mode") or "body_unavailable"
    aliases = {
        "body_available": "readable",
        "body_partial": "partial",
        "transcript_available": "transcript",
    }
    row["reader_mode"] = aliases.get(mode, mode)
    row.setdefault("reader_paragraphs", row.get("reader_paragraphs") or [])
    row.setdefault("reader_transcript", row.get("reader_transcript") or "")
    row.setdefault("reader_notice", row.get("reader_notice") or "")
    return row


def present_briefing_page(briefing: dict[str, Any]) -> dict[str, Any]:
    query = briefing.get("query_string") or ""
    bands = []
    for band in briefing.get("what_changed_bands") or []:
        bands.append({
            **band,
            "entries": [_map_item(item, query_string=query) for item in band.get("entries") or []],
        })
    page = dict(briefing)
    page["what_changed_bands"] = bands
    page["needs_attention"] = [_map_item(i, query_string=query) for i in briefing.get("needs_attention") or []]
    page["historical_context"] = [_map_item(i, query_string=query) for i in briefing.get("historical_context") or []]
    page["unknown_publication_dates"] = [
        _map_item(i, query_string=query) for i in briefing.get("unknown_publication_dates") or []
    ]
    page["selected_reader"] = _map_reader(briefing.get("selected_reader"))
    page["filter_options"] = briefing.get("filter_options") or {}
    page["coverage_pulse"] = briefing.get("coverage_pulse") or {}
    page["recency_labels"] = {
        k: v for k, v in (briefing.get("recency_labels") or {}).items() if k in {"0-30", "31-60", "61-90"}
    }
    page["prototype_fixture_used"] = False
    page["fixture_dependency"] = None
    page["thumbs_mutations_implemented"] = 0
    return page
