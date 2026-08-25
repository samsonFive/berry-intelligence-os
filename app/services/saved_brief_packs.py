"""Saved Brief Packs V1 -- stores an analyst's Brief Pack SELECTION and
COMPOSITION state only (title, context note, berry, time window, and the
exact same canonical ids the query-string pack already carries: TD-097),
never duplicated intelligence content. No article/Fact/Evidence/Signal/
Assessment/Company/Variety body is ever snapshotted here -- only ids.

A Saved Brief Pack is not a trust object and not a historical snapshot.
Reopening one always resolves the same selection against CURRENT
trusted data (a "LIVE BRIEF"), exactly the same way a bookmarked
/brief-pack URL already does today. If the underlying data changed
(a new Evidence captured, an Assessment moved from AI PROPOSED to
REVIEWED, an object removed), the reopened pack reflects that -- it
never silently freezes an old view. Full historical snapshotting stays
out of V1 scope; Print -> PDF remains the archival mechanism.

Persisted privately under inbox/brief_packs/ (operator-scoped state,
same precedent as inbox/watchlist_state.json and inbox/review_sessions/
-- see AGENTS.md's "Reading state ... is independent of trust" rule).
Not wired into build_static.py."""

from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DIRNAME = "brief_packs"
STATUSES = ("active", "archived")


def packs_dir(inbox_dir: Path) -> Path:
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


def list_packs(inbox_dir: Path, *, status: str = "active") -> list[dict[str, Any]]:
    """No ranking -- newest-updated first, the same honest ordering
    Review Session history and the Watchlist default sort both use."""
    folder = packs_dir(inbox_dir)
    if not folder.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for path in folder.glob("bp-*.json"):
        blob = _read(path)
        if blob.get("id") and str(blob.get("status") or "active") == status:
            rows.append(blob)
    rows.sort(key=lambda r: str(r.get("updated_at") or r.get("created_at") or ""), reverse=True)
    return rows


def load_pack(inbox_dir: Path, pack_id: str) -> dict[str, Any] | None:
    if not pack_id:
        return None
    path = packs_dir(inbox_dir) / f"{pack_id}.json"
    if not path.is_file():
        return None
    blob = _read(path)
    return blob if blob.get("id") else None


def save_pack(
    inbox_dir: Path,
    *,
    pack_id: str = "",
    title: str,
    context_note: str,
    berry_id: str,
    window_days: int,
    company_ids: list[str],
    variety_ids: list[str],
    signal_ids: list[str],
    assessment_ids: list[str],
    concept_slugs: list[str],
    strategic_question_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Save As (no pack_id) creates a new record; Save Changes (pack_id
    given) updates that record in place. Either way, only selection
    fields are written -- never resolved/rendered pack content."""
    now = _now()
    if pack_id:
        existing = load_pack(inbox_dir, pack_id)
        if existing is None:
            raise ValueError("unknown pack id")
        created_at = existing.get("created_at") or now
        status = existing.get("status") or "active"
    else:
        pack_id = "bp-" + secrets.token_hex(8)
        created_at = now
        status = "active"
    record = {
        "id": pack_id,
        "title": (title or "").strip() or "Untitled brief pack",
        "context_note": context_note or "",
        "berry_id": berry_id or "",
        "window_days": int(window_days) if window_days else 14,
        "company_ids": [v for v in company_ids if v],
        "variety_ids": [v for v in variety_ids if v],
        "signal_ids": [v for v in signal_ids if v],
        "assessment_ids": [v for v in assessment_ids if v],
        "concept_slugs": [v for v in concept_slugs if v],
        "strategic_question_ids": [v for v in (strategic_question_ids or []) if v],
        "status": status,
        "created_at": created_at,
        "updated_at": now,
    }
    _write(packs_dir(inbox_dir) / f"{pack_id}.json", record)
    return record


def duplicate_pack(inbox_dir: Path, pack_id: str) -> dict[str, Any] | None:
    """New id, same selections -- never shares storage with the source
    pack, so editing the copy can never mutate the original."""
    existing = load_pack(inbox_dir, pack_id)
    if existing is None:
        return None
    return save_pack(
        inbox_dir,
        title=f"{existing.get('title') or 'Untitled brief pack'} (copy)",
        context_note=str(existing.get("context_note") or ""),
        berry_id=str(existing.get("berry_id") or ""),
        window_days=int(existing.get("window_days") or 14),
        company_ids=list(existing.get("company_ids") or []),
        variety_ids=list(existing.get("variety_ids") or []),
        signal_ids=list(existing.get("signal_ids") or []),
        assessment_ids=list(existing.get("assessment_ids") or []),
        concept_slugs=list(existing.get("concept_slugs") or []),
        strategic_question_ids=list(existing.get("strategic_question_ids") or []),
    )


def archive_pack(inbox_dir: Path, pack_id: str) -> dict[str, Any] | None:
    """The safe, reversible removal path for V1 -- no permanent delete
    route exists, so a mistaken archive is never a data-loss incident."""
    existing = load_pack(inbox_dir, pack_id)
    if existing is None:
        return None
    existing["status"] = "archived"
    existing["updated_at"] = _now()
    _write(packs_dir(inbox_dir) / f"{pack_id}.json", existing)
    return existing


def unarchive_pack(inbox_dir: Path, pack_id: str) -> dict[str, Any] | None:
    existing = load_pack(inbox_dir, pack_id)
    if existing is None:
        return None
    existing["status"] = "active"
    existing["updated_at"] = _now()
    _write(packs_dir(inbox_dir) / f"{pack_id}.json", existing)
    return existing


def pack_query_string(pack: dict[str, Any]) -> str:
    """Expands a saved pack's selection into the exact same query
    parameters /brief-pack already accepts -- the one and only place a
    saved pack turns into a page render, so there is no second
    rendering path to keep in sync with compose_brief_pack()."""
    from urllib.parse import urlencode

    params = {
        "title": pack.get("title") or "",
        "context_note": pack.get("context_note") or "",
        "berry": pack.get("berry_id") or "",
        "days": pack.get("window_days") or 14,
        "companies": ",".join(pack.get("company_ids") or []),
        "varieties": ",".join(pack.get("variety_ids") or []),
        "signals": ",".join(pack.get("signal_ids") or []),
        "assessments": ",".join(pack.get("assessment_ids") or []),
        "concepts": ",".join(pack.get("concept_slugs") or []),
        "pack_id": pack.get("id") or "",
    }
    return urlencode(params)


def present_pack_row(pack: dict[str, Any]) -> dict[str, Any]:
    """Saved Brief Packs index row -- open/present both go through the
    exact same /brief-pack query string a bookmarked URL already used
    (TD-097), so there is no second rendering path. Selection counts
    are descriptive only, never a readiness/completeness score."""
    qs = pack_query_string(pack)
    return {
        **pack,
        "open_href": f"/brief-pack?{qs}",
        "present_href": f"/brief-pack?{qs}&present=1",
        "selection_count": sum(
            len(pack.get(field) or [])
            for field in ("company_ids", "variety_ids", "signal_ids", "assessment_ids", "concept_slugs")
        ),
    }
