"""AI-Assisted Report Builder V1 -- report persistence.

Stores a report's RESOLVED SCOPE (selection ids only, same discipline as
app.services.saved_brief_packs: TD-097's "selection, not resolved
content"), its section text (both the AI-generated draft and any
analyst edit, kept as two separate fields so a regenerate never
clobbers an edit silently), and provenance metadata (provider/model/
timestamps). Never duplicates Evidence/article/transcript bodies or any
other resolved intelligence content -- reopening a report always
re-resolves its packet live against current trusted data, exactly like
a Saved Brief Pack, unless the analyst has edited a section (an edited
section's text is preserved verbatim and is never silently overwritten
by a later packet change; only an explicit "regenerate this section"
action replaces it).

Persisted privately under inbox/reports/ (same precedent as
inbox/brief_packs/ and inbox/watchlist_state.json). Not wired into
build_static.py.
"""

from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DIRNAME = "reports"
STATUSES = ("draft", "active", "archived")


def reports_dir(inbox_dir: Path) -> Path:
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


def list_reports(inbox_dir: Path, *, status: str | None = None) -> list[dict[str, Any]]:
    folder = reports_dir(inbox_dir)
    if not folder.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for path in folder.glob("rp-*.json"):
        blob = _read(path)
        if not blob.get("id"):
            continue
        if status and str(blob.get("status") or "draft") != status:
            continue
        rows.append(blob)
    rows.sort(key=lambda r: str(r.get("updated_at") or r.get("created_at") or ""), reverse=True)
    return rows


def load_report(inbox_dir: Path, report_id: str) -> dict[str, Any] | None:
    if not report_id:
        return None
    path = reports_dir(inbox_dir) / f"{report_id}.json"
    if not path.is_file():
        return None
    blob = _read(path)
    return blob if blob.get("id") else None


def create_report(
    inbox_dir: Path,
    *,
    title: str,
    report_type: str,
    scope: dict[str, Any],
    sections: list[dict[str, Any]],
) -> dict[str, Any]:
    now = _now()
    report_id = "rp-" + secrets.token_hex(8)
    record = {
        "id": report_id,
        "title": (title or "").strip() or "Untitled report",
        "report_type": report_type,
        "scope": scope,
        "sections": sections,
        "external_research_appendix": [],
        "research_batches": [],
        "status": "draft",
        "created_at": now,
        "updated_at": now,
    }
    _write(reports_dir(inbox_dir) / f"{report_id}.json", record)
    return record


def save_report_edits(
    inbox_dir: Path,
    report_id: str,
    *,
    title: str | None = None,
    sections: list[dict[str, Any]] | None = None,
    status: str | None = None,
) -> dict[str, Any] | None:
    existing = load_report(inbox_dir, report_id)
    if existing is None:
        return None
    if title is not None:
        existing["title"] = title.strip() or existing["title"]
    if sections is not None:
        existing["sections"] = sections
    if status is not None and status in STATUSES:
        existing["status"] = status
    existing["updated_at"] = _now()
    _write(reports_dir(inbox_dir) / f"{report_id}.json", existing)
    return existing


def replace_section(
    inbox_dir: Path,
    report_id: str,
    section_id: str,
    *,
    generated_prose: str,
    citation_ids: list[str],
    status: str,
    provider: str | None,
    model: str | None,
) -> dict[str, Any] | None:
    """Regenerate exactly one section -- every other section (including any
    analyst edit on them) is left untouched."""
    existing = load_report(inbox_dir, report_id)
    if existing is None:
        return None
    sections = existing.get("sections") or []
    found = False
    for section in sections:
        if section.get("section_id") == section_id:
            section["generated_prose"] = generated_prose
            section["edited_prose"] = None
            section["citation_ids"] = citation_ids
            section["status"] = status
            section["provider"] = provider
            section["model"] = model
            section["generated_at"] = _now()
            found = True
            break
    if not found:
        return None
    existing["sections"] = sections
    existing["updated_at"] = _now()
    _write(reports_dir(inbox_dir) / f"{report_id}.json", existing)
    return existing


def append_research_batch(
    inbox_dir: Path,
    report_id: str,
    *,
    gap_keys: list[str],
    entries: list[dict[str, Any]],
    status_messages: dict[str, str],
) -> dict[str, Any] | None:
    """One explicit 'Research missing public information' (or 'Research
    again') action -- always a new batch, never overwriting or silently
    refreshing a prior one, so a saved report retains every public
    research packet it has ever used. `entries` are appended to the flat
    `external_research_appendix` (each auto-assigned an id and stamped
    with this batch's id) for simple listing/PDF rendering; `gap_keys`/
    `status_messages` are retained on the batch record alone so the
    workspace can show exactly what was asked and what came back, even
    for a gap that returned zero citable sources."""
    existing = load_report(inbox_dir, report_id)
    if existing is None:
        return None
    batch_id = "rb-" + secrets.token_hex(6)
    now = _now()
    stamped_entries = []
    for entry in entries:
        stamped = dict(entry)
        stamped.setdefault("id", "rf-" + secrets.token_hex(6))
        stamped["batch_id"] = batch_id
        stamped.setdefault("reviewed", False)
        stamped.setdefault("included_in_report", False)
        stamped.setdefault("sent_to_review_draft_id", None)
        stamped_entries.append(stamped)
    appendix = existing.get("external_research_appendix") or []
    appendix.extend(stamped_entries)
    existing["external_research_appendix"] = appendix
    batches = existing.get("research_batches") or []
    batches.append(
        {
            "id": batch_id,
            "requested_at": now,
            "gap_keys": list(gap_keys),
            "status_messages": dict(status_messages),
            "finding_count": len(stamped_entries),
        }
    )
    existing["research_batches"] = batches
    existing["updated_at"] = now
    _write(reports_dir(inbox_dir) / f"{report_id}.json", existing)
    return existing


def update_research_finding(
    inbox_dir: Path,
    report_id: str,
    finding_id: str,
    **updates: Any,
) -> dict[str, Any] | None:
    """Toggle per-finding state (`reviewed`, `included_in_report`,
    `sent_to_review_draft_id`) without touching any other finding or
    batch. Only keys already present on a finding row may be set."""
    existing = load_report(inbox_dir, report_id)
    if existing is None:
        return None
    appendix = existing.get("external_research_appendix") or []
    found = False
    for entry in appendix:
        if entry.get("id") == finding_id:
            entry.update(updates)
            found = True
            break
    if not found:
        return None
    existing["external_research_appendix"] = appendix
    existing["updated_at"] = _now()
    _write(reports_dir(inbox_dir) / f"{report_id}.json", existing)
    return existing


def find_research_finding(report: dict[str, Any], finding_id: str) -> dict[str, Any] | None:
    for entry in report.get("external_research_appendix") or []:
        if entry.get("id") == finding_id:
            return entry
    return None


def archive_report(inbox_dir: Path, report_id: str) -> dict[str, Any] | None:
    return save_report_edits(inbox_dir, report_id, status="archived")


def present_report_row(report: dict[str, Any]) -> dict[str, Any]:
    return {
        **report,
        "href": f"/reports/{report.get('id')}",
        "section_count": len(report.get("sections") or []),
    }
