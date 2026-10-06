"""Private reading workspace. Saves, consumption and subscriptions stay independent.

No acquisition, extraction or canonical writes occur while building this view.
Company lists share the existing feed-first analyst store; reading continues to
use analyst_queue_state.json, including legacy dispositions and review history.
"""
from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.services import analyst_queue, feed_first, company_source_scope
from app.services.feed_first_live import CACHE_SUBDIR
from app.services.analyst_state_io import serialized_write

PRIORITIES = {"high", "medium", "low", "none"}
PROGRESS_LABELS = {
    "unread": "Unread", "saved": "Unread", "in_progress": "In progress",
    "read": "Completed", "dismissed": "Dismissed", "promoted": "Promoted",
}


def retained_news(inbox_dir: Path) -> list[dict[str, Any]]:
    """Read retained daily caches, newest version per exact ID; never fetch."""
    records: dict[str, dict[str, Any]] = {}
    paths = list((Path(inbox_dir) / CACHE_SUBDIR).glob("????-??-??.json")) + list((Path(inbox_dir) / "news_packets" / "captures").glob("packet-*.json"))
    for path in sorted(paths, key=lambda path: path.stat().st_mtime):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(payload, dict):
            continue
        for record in payload.get("records") or []:
            if not isinstance(record, dict):
                continue
            item_id = str(record.get("id") or "")
            if feed_first.SAFE_ID_RE.fullmatch(item_id):
                # Cached discovery is never promoted by a supplied status string.
                records[item_id] = {**record, "status": "unreviewed"}
    return list(records.values())


def source_records(published: list[dict[str, Any]], inbox_dir: Path, *, include_private: bool = True) -> dict[str, dict[str, Any]]:
    records = {str(row["id"]): row for row in retained_news(inbox_dir)} if include_private else {}
    for row in published:
        if not row.get("id") or row.get("status") != "published":
            continue
        item_id = str(row["id"])
        cached = records.get(item_id) or {}
        # Same source identity may supply a preview image, never cached prose,
        # entity assignments, priority or a different trust classification.
        image = feed_first.safe_image_url(cached) if cached.get("source_url") == row.get("source_url") else ""
        if image and not feed_first.safe_image_url(row):
            row = {**row, "article": {**(row.get("article") or {}), "image_url": image}}
        records[item_id] = row
    if include_private:
        from app.services.feed_first_reader import attach_capture_previews
        records = attach_capture_previews(records, inbox_dir)
    return records


def company_lists(state: dict[str, Any]) -> list[dict[str, Any]]:
    subscriptions = set(state.get("digest_subscriptions") or [])
    return sorted([
        {**row, "id": key, "subscribed": key in subscriptions}
        for key, row in (state.get("company_lists") or {}).items()
        if isinstance(row, dict) and not row.get("archived")
    ], key=lambda row: str(row.get("name") or "").casefold())


@serialized_write
def edit_list(inbox_dir: Path, *, action: str, list_id: str = "", name: str = "",
              company_ids: list[str] | None = None, allowed_companies: set[str]) -> str:
    state = feed_first.load_state(inbox_dir)
    lists = state.setdefault("company_lists", {})
    subscriptions = set(state.get("digest_subscriptions") or [])
    if action == "create":
        list_id = "list-" + uuid4().hex[:16]
    elif list_id not in lists or lists[list_id].get("archived"):
        raise ValueError("Company list not found")
    if action in {"create", "edit"}:
        name = name.strip()
        if not name or len(name) > 80:
            raise ValueError("Choose a list name of 1–80 characters")
        if any(row.get("name", "").casefold() == name.casefold() and key != list_id and not row.get("archived") for key, row in lists.items()):
            raise ValueError("A list with that name already exists")
        members = sorted(set(company_ids or []))
        if not set(members) <= allowed_companies:
            raise ValueError("Choose companies from the directory")
        lists[list_id] = {**lists.get(list_id, {}), "name": name, "company_ids": members,
                          "updated_at": datetime.now(UTC).isoformat(), "archived": False}
    elif action == "subscribe":
        subscriptions.add(list_id)
    elif action == "unsubscribe":
        subscriptions.discard(list_id)
    elif action == "archive":
        lists[list_id]["archived"] = True
        subscriptions.discard(list_id)
    else:
        raise ValueError("Unknown list action")
    state["digest_subscriptions"] = sorted(subscriptions)
    feed_first.save_state(inbox_dir, state)
    return list_id


def inclusion(record: dict[str, Any], state: dict[str, Any], reading: dict[str, Any], *, linked_companies=None) -> list[dict[str, str]]:
    item_id = str(record.get("id") or "")
    origins = []
    if feed_first.decision_for(item_id, state)["saved"]:
        origins.append({"key": "saved", "label": "Saved by you"})
    priority = ((record.get("priority") or {}).get("reading") or {}).get("level")
    entry = (reading.get("reading") or {}).get(item_id) or {}
    # Merely remembering a Reader position is not an instruction to enqueue.
    explicit_reading = bool(entry) and ("state" in entry or "action" in entry or "reader_positions" not in entry)
    if priority in {"high", "medium", "low"} or explicit_reading:
        origins.append({"key": "queue", "label": "Reading queue"})
    companies = (linked_companies if linked_companies is not None else
                 set(record.get("entity_ids") or []) | set(record.get("company_ids") or []))
    for row in company_lists(state):
        if row["subscribed"] and companies.intersection(row.get("company_ids") or []):
            origins.append({"key": row["id"], "label": row["name"]})
    return origins


def digest_model(*, records: dict[str, dict[str, Any]], entities: dict[str, dict[str, Any]],
                 state: dict[str, Any], reading: dict[str, Any], params: dict[str, str],
                 today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    filters = {key: str(params.get(key) or "") for key in ("q", "status", "origin", "berry", "country", "window", "start", "end", "priority", "tier", "favorites", "list")}
    from app.services.company_directory import matches_marks, TIERS
    if filters["favorites"] not in {"", "1"} or filters["tier"] and filters["tier"] not in TIERS:
        raise ValueError("Choose supported company filters")
    filters["status"] = filters["status"] or "active"
    starts = {"7d": today - timedelta(days=6), "30d": today - timedelta(days=29), "ytd": today.replace(month=1, day=1)}
    start = starts.get(filters["window"])
    end = today if start else None
    if filters["window"] == "custom":
        try:
            start = date.fromisoformat(filters["start"]) if filters["start"] else None
            end = date.fromisoformat(filters["end"]) if filters["end"] else None
        except ValueError:
            raise ValueError("Choose valid start and end dates") from None
        if start and end and start > end:
            raise ValueError("Start date must come before end date")
    berries = set(filter(None, filters["berry"].split(",")))
    countries = set(filter(None, filters["country"].split(",")))
    universe = dict(records)
    subjects = company_source_scope.candidates(entities, state, filters, subscribed=True)
    source_links = {}
    # Keep the personal marks visible even if a source cache has been removed.
    for item_id in set(state.get("decisions", {})) | set(reading.get("reading", {})):
        if item_id not in universe and inclusion({"id": item_id}, state, reading):
            universe[item_id] = {"id": item_id, "title": "Source no longer available", "missing_source": True}
    all_cards = []
    for item_id, record in universe.items():
        linked, mentions = company_source_scope.links(record, subjects)
        origins = inclusion(record, state, reading, linked_companies=linked)
        if not origins:
            continue
        source_links[item_id] = linked
        preview = {key: value for key, value in record.items() if key not in {"article", "transcript", "transcript_excerpt", "images", "reader_capture"}}
        preview["article"] = {"image_url": feed_first.safe_image_url(record)}
        card = feed_first.present_item(preview, entities_by_id=entities, state=state, filters=feed_first.parse_filters({}))
        entry = (reading.get("reading") or {}).get(item_id) or {}
        # The old feed's read flag means opened, not consumption completed.
        # Preserve that flag without turning an opened saved story into done.
        progress = analyst_queue.reading_state(item_id, reading)
        priority = entry.get("priority", ((record.get("priority") or {}).get("reading") or {}).get("level", "none"))
        card.update(origins=origins, progress=progress, progress_label=PROGRESS_LABELS[progress],
                    company_mentions=mentions,
                    reading_priority=priority if priority in PRIORITIES else "none",
                    trusted=company_source_scope.source_reviewed(record), missing_source=bool(record.get("missing_source")))
        all_cards.append(card)
    counts = {"total": len(all_cards), "active": sum(c["progress"] in analyst_queue.READING_ACTIVE for c in all_cards),
              "completed": sum(c["progress"] in {"read", "promoted"} for c in all_cards)}
    cards = []
    for card in all_cards:
        if filters["status"] == "active" and card["progress"] not in analyst_queue.READING_ACTIVE:
            continue
        if filters["status"] == "completed" and card["progress"] not in {"read", "promoted"}:
            continue
        if filters["status"] not in {"active", "completed", "all", ""} and card["progress"] != filters["status"]:
            continue
        if filters["origin"] and filters["origin"] not in {row["key"] for row in card["origins"]}:
            continue
        if filters["priority"] and card["reading_priority"] != filters["priority"]:
            continue
        if berries and not berries.intersection(card["crops"]):
            continue
        if countries and not countries.intersection(card["geographies"]):
            continue
        if filters["q"].casefold() not in (card["headline"] + " " + card["deck"] + " " + card["source_name"]).casefold():
            continue
        stamp = str(card["published_at"] or "")[:10]
        if start and (not stamp or stamp < start.isoformat()):
            continue
        if end and (not stamp or stamp > end.isoformat()):
            continue
        linked = source_links[card["id"]]
        if not matches_marks(linked, state, favorites=filters["favorites"], tier=filters["tier"], list_id=filters["list"]):
            continue
        cards.append(card)
    cards.sort(key=lambda row: (row["published_at"] or "", row["id"]), reverse=True)
    try:
        page = max(1, int(params.get("page") or 1))
    except ValueError:
        page = 1
    pages = max(1, (len(cards) + 35) // 36)
    page = min(page, pages)
    return {"cards": cards[(page - 1) * 36:page * 36], "matching": len(cards), "counts": counts,
            "filters": filters, "page": page, "pages": pages, "lists": company_lists(state)}


@serialized_write
def set_personal_decision(inbox_dir: Path, item_id: str, action: str) -> None:
    if not feed_first.SAFE_ID_RE.fullmatch(item_id):
        raise ValueError("Invalid story")
    state = feed_first.load_state(inbox_dir)
    current = dict((state.get("decisions") or {}).get(item_id) or {})
    if action in {"save", "unsave"}:
        current["saved"] = action == "save"
    elif action in {"useful", "not_relevant", "clear_feedback"}:
        current["reaction"] = {"useful": "up", "not_relevant": "down", "clear_feedback": None}[action]
    else:
        raise ValueError("Unknown personal action")
    # Deliberately no extraction, read-completion side effect or trust mutation.
    state.setdefault("decisions", {})[item_id] = current
    feed_first.save_state(inbox_dir, state)


@serialized_write
def save_reader_location(inbox_dir: Path, item_id: str, *, mode: str, position: Any) -> None:
    if mode not in {"article", "brief"} or not feed_first.SAFE_ID_RE.fullmatch(item_id):
        raise ValueError("Invalid reader location")
    try:
        offset = max(0, min(1_000_000, int(position)))
    except (TypeError, ValueError, OverflowError):
        raise ValueError("Invalid reader location") from None
    state = analyst_queue.load_state(inbox_dir)
    entry = state.setdefault("reading", {}).setdefault(item_id, {})
    entry["reader_mode"] = mode
    entry["reader_positions"] = {**(entry.get("reader_positions") or {}), mode: offset}
    analyst_queue.save_state(inbox_dir, state)
