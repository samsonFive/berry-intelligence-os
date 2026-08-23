"""Analyst UI context: berry scope and Feed view preference.

Berry is application context, not a visual theme. Preferences persist in
cookies and, when an inbox exists, inbox/analyst_queue_state.json meta.ui.
"""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import Response

from app.services.analyst_queue import load_state, save_state

COOKIE_BERRY = "bios_berry"
COOKIE_FEED_VIEW = "bios_feed_view"
BERRY_GLOBAL = "global"
FEED_VIEWS = ("grid", "compact")
DEFAULT_FEED_VIEW = "grid"


def berry_options(berries: dict[str, str]) -> list[dict[str, str]]:
    options = [{"id": BERRY_GLOBAL, "label": "Global", "slug": ""}]
    for berry_id, label in berries.items():
        options.append(
            {
                "id": berry_id,
                "label": label,
                "slug": berry_id.removeprefix("berry-"),
            }
        )
    return options


def parse_berry(raw: str | None, berries: dict[str, str]) -> str:
    value = str(raw or "").strip()
    if not value or value == BERRY_GLOBAL:
        return BERRY_GLOBAL
    if value in berries:
        return value
    prefixed = f"berry-{value}" if not value.startswith("berry-") else value
    if prefixed in berries:
        return prefixed
    return BERRY_GLOBAL


def parse_feed_view(raw: str | None) -> str:
    value = str(raw or "").strip().casefold()
    return value if value in FEED_VIEWS else DEFAULT_FEED_VIEW


def landscape_href(berry: str) -> str:
    if berry == BERRY_GLOBAL:
        return "/landscapes"
    return f"/landscapes/berries/{berry.removeprefix('berry-')}"


def item_berry_ids(item: dict[str, Any]) -> list[str]:
    ids = [str(value) for value in (item.get("berry_ids") or []) if value]
    if ids:
        return ids
    record = item.get("record") if isinstance(item.get("record"), dict) else item
    enrichment = record.get("ai_enrichment") or {}
    combined = list(record.get("berry_ids") or []) + list(enrichment.get("suggested_berry_ids") or [])
    return [str(value) for value in combined if value]


def matches_berry_context(item: dict[str, Any], berry: str) -> bool:
    if berry == BERRY_GLOBAL:
        return True
    return berry in item_berry_ids(item)


def _cookie_value(request: Request, name: str) -> str:
    return str(request.cookies.get(name) or "")


def _stored_ui(inbox_dir) -> dict[str, str]:
    if inbox_dir is None:
        return {}
    state = load_state(inbox_dir)
    ui = ((state.get("meta") or {}).get("ui") or {})
    if not isinstance(ui, dict):
        return {}
    return {
        "berry": str(ui.get("berry") or ""),
        "feed_view": str(ui.get("feed_view") or ""),
    }


def persist_ui_prefs(inbox_dir, *, berry: str, feed_view: str) -> None:
    if inbox_dir is None:
        return
    state = load_state(inbox_dir)
    ui = dict((state.get("meta") or {}).get("ui") or {})
    ui["berry"] = berry
    ui["feed_view"] = feed_view
    state.setdefault("meta", {})["ui"] = ui
    save_state(inbox_dir, state)


def apply_ui_cookies(response: Response, *, berry: str, feed_view: str) -> None:
    response.set_cookie(COOKIE_BERRY, berry, max_age=60 * 60 * 24 * 180, samesite="lax", path="/")
    response.set_cookie(COOKIE_FEED_VIEW, feed_view, max_age=60 * 60 * 24 * 180, samesite="lax", path="/")


def read_ui_context(
    request: Request,
    berries: dict[str, str],
    *,
    inbox_dir=None,
) -> dict[str, Any]:
    stored = _stored_ui(inbox_dir)
    berry = parse_berry(
        request.query_params.get("berry") or _cookie_value(request, COOKIE_BERRY) or stored.get("berry"),
        berries,
    )
    feed_view = parse_feed_view(
        request.query_params.get("view") or _cookie_value(request, COOKIE_FEED_VIEW) or stored.get("feed_view")
    )
    label = "Global" if berry == BERRY_GLOBAL else berries.get(berry, berry)
    return {
        "berry": berry,
        "berry_label": label,
        "feed_view": feed_view,
        "landscape_href": landscape_href(berry),
        "options": berry_options(berries),
        "is_global": berry == BERRY_GLOBAL,
    }
