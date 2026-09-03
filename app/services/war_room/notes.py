"""War Room session takeaways -- private, lightweight notes only.

Mirrors `saved_brief_packs.py`'s exact persistence discipline (one atomic
JSON file per record, id/created_at/updated_at envelope, canonical-id
scope fields + one free-text field, never duplicated intelligence
content) rather than reusing that module's own object: a Saved Brief
Pack's schema has no geography_ids field, and War Room scope always
carries one -- extending Brief Packs' shape for this would touch a
delicate, already-shipped object outside this feature's blast radius.
Same pattern, deliberately not the same object.

Not a trust object, not a canonical Strategic Question (creating those
has no route anywhere in this app today -- see
app/repositories/json/strategic_questions.py's own docstring; adding one
is a real, separate capability this V1 does not build). A takeaway is
private working-session state, exactly like a Saved Brief Pack.
"""

from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DIRNAME = "war_room_sessions"


def _notes_dir(inbox_dir: Path) -> Path:
    return Path(inbox_dir) / DIRNAME


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _read(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def list_notes_for_scope(
    inbox_dir: Path, *, berry_id: str | None, geography_ids: tuple[str, ...], company_ids: tuple[str, ...]
) -> list[dict[str, Any]]:
    folder = _notes_dir(inbox_dir)
    if not folder.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for path in folder.glob("wrs-*.json"):
        blob = _read(path)
        if not blob.get("id"):
            continue
        if berry_id and blob.get("berry_id") != berry_id:
            continue
        if geography_ids and not set(blob.get("geography_ids") or []) & set(geography_ids):
            continue
        if company_ids and not set(blob.get("company_ids") or []) & set(company_ids):
            continue
        rows.append(blob)
    rows.sort(key=lambda r: str(r.get("created_at") or ""), reverse=True)
    return rows


def add_note(
    inbox_dir: Path,
    *,
    text: str,
    berry_id: str | None,
    geography_ids: tuple[str, ...],
    company_ids: tuple[str, ...],
) -> dict[str, Any]:
    clean = (text or "").strip()
    if not clean:
        raise ValueError("a takeaway needs text")
    note_id = "wrs-" + secrets.token_hex(8)
    record = {
        "id": note_id,
        "text": clean[:2000],
        "berry_id": berry_id or "",
        "geography_ids": [g for g in geography_ids if g],
        "company_ids": [c for c in company_ids if c],
        "created_at": _now(),
    }
    _write(_notes_dir(inbox_dir) / f"{note_id}.json", record)
    return record
