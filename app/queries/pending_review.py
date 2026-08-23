"""Private, rebuildable read model for the Pending Review inventory.

The live JSON draft is the source of truth.  This module stores only the
metadata needed by the list/ranking path plus deterministic attribution that
would otherwise rescan a rich article body for every request.  Detail routes
continue to read the source draft and therefore retain the complete article.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Protocol

INDEX_VERSION = 4
INDEX_RELATIVE_PATH = Path("indexes") / "pending-review-v2.json"
_RICH_TOP_LEVEL_FIELDS = {
    "article",
    "transcript",
    "transcript_segments",
    "raw_content",
    "raw_html",
    "source_text",
    "publisher_description",
}


class PendingDraftSnapshotProvider(Protocol):
    """Storage-neutral input seam for a Pending Review query service."""

    def snapshot(
        self,
        *,
        entities: dict[str, dict[str, Any]],
        sources: dict[str, dict[str, Any]],
    ) -> "PendingDraftSnapshot": ...


@dataclass(frozen=True)
class PendingDraftSnapshot:
    records: list[dict[str, Any]]
    inventory_count: int
    parsed_records: int
    reused_records: int
    body_records_omitted: int


def _stable_digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _dependency_digest(
    entities: dict[str, dict[str, Any]],
    sources: dict[str, dict[str, Any]],
) -> str:
    entity_rows = sorted([
        {
            "id": row.get("id"),
            "name": row.get("name"),
            "entity_type": row.get("entity_type"),
            "aliases": row.get("aliases") or [],
            "also_known_as": row.get("also_known_as") or [],
        }
        for row in entities.values()
    ], key=lambda row: str(row.get("id") or ""))
    source_rows = sorted([
        {
            "id": row.get("id"),
            "label": row.get("label"),
            "linked_competitor_ids": row.get("linked_competitor_ids") or [],
        }
        for row in sources.values()
    ], key=lambda row: str(row.get("id") or ""))
    return _stable_digest({"entities": entity_rows, "sources": source_rows})


def _file_signature(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {"mtime_ns": stat.st_mtime_ns, "ctime_ns": stat.st_ctime_ns, "size": stat.st_size}


def _metadata_projection(record: dict[str, Any], attribution: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    projected = {key: value for key, value in record.items() if key not in _RICH_TOP_LEVEL_FIELDS}
    article = record.get("article") if isinstance(record.get("article"), dict) else {}
    final_url = article.get("final_url")
    if final_url and not projected.get("canonical_url") and not projected.get("source_url"):
        projected["canonical_url"] = final_url
    projected["_pending_attribution"] = attribution
    if record.get("summary") and record.get("summary") == record.get("publisher_description"):
        projected["_pending_summary_is_publisher_description"] = True
    return projected, any(key in record for key in _RICH_TOP_LEVEL_FIELDS)


class JsonPendingDraftSnapshotProvider:
    """Incremental JSON implementation of the pending inventory seam.

    The sidecar is private because it lives below ``inbox/``.  It is safe to
    delete: every entry is validated against the source filename/mtime/size,
    and entity/source matcher changes invalidate all derived attribution.
    """

    def __init__(self, inbox_dir: Path):
        self.inbox_dir = inbox_dir
        self.evidence_dir = inbox_dir / "evidence"
        self.index_path = inbox_dir / INDEX_RELATIVE_PATH

    def _read_index(self) -> dict[str, Any]:
        try:
            value = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return {}
        return value if isinstance(value, dict) else {}

    def _write_index(self, value: dict[str, Any]) -> None:
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.index_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
        temporary.replace(self.index_path)

    def snapshot(
        self,
        *,
        entities: dict[str, dict[str, Any]],
        sources: dict[str, dict[str, Any]],
    ) -> PendingDraftSnapshot:
        # Lazy import keeps the composition root free of the application
        # service import cycle (media discovery also resolves repositories
        # through that root).
        from app.services.draft_attribution import (
            attribute_draft,
            build_attribution_match_index,
            indexed_title_matched_entity_ids,
        )
        from app.services.intelligence_feed import classify_kind

        paths = sorted(self.evidence_dir.glob("*.json")) if self.evidence_dir.is_dir() else []
        match_index = build_attribution_match_index(entities)
        dependency = _dependency_digest(entities, sources)
        stored = self._read_index()
        reusable = (
            stored.get("version") == INDEX_VERSION
            and stored.get("dependency_sha256") == dependency
            and isinstance(stored.get("entries"), dict)
        )
        previous = stored.get("entries") if reusable else {}
        entries: dict[str, Any] = {}
        records: list[dict[str, Any]] = []
        parsed = 0
        reused = 0
        omitted = 0
        for path in paths:
            signature = _file_signature(path)
            cached = previous.get(path.name) if isinstance(previous, dict) else None
            if isinstance(cached, dict) and cached.get("signature") == signature and isinstance(cached.get("record"), dict):
                entry = cached
                reused += 1
            else:
                try:
                    source_record = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, ValueError, TypeError):
                    continue
                if not isinstance(source_record, dict):
                    continue
                attribution = attribute_draft(
                    source_record,
                    entities,
                    sources=sources,
                    match_index=match_index,
                )
                record, had_body = _metadata_projection(source_record, attribution)
                record["_pending_kind"] = classify_kind(source_record)
                record["_pending_title_entity_ids"] = indexed_title_matched_entity_ids(
                    str(source_record.get("title") or ""), entities, match_index
                )
                entry = {"signature": signature, "record": record, "body_omitted": had_body}
                parsed += 1
            entries[path.name] = entry
            if entry.get("body_omitted"):
                omitted += 1
            records.append(dict(entry["record"]))
        next_index = {
            "version": INDEX_VERSION,
            "dependency_sha256": dependency,
            "entries": entries,
        }
        if next_index != stored:
            self._write_index(next_index)
        records.sort(key=lambda row: str(row.get("captured_date") or ""), reverse=True)
        return PendingDraftSnapshot(
            records=records,
            inventory_count=len(records),
            parsed_records=parsed,
            reused_records=reused,
            body_records_omitted=omitted,
        )


class PendingReviewQueryService:
    """Cheap inventory/filter boundary; ranking remains a presentation concern."""

    def __init__(self, provider: PendingDraftSnapshotProvider):
        self.provider = provider

    def list_pending(
        self,
        *,
        entities: dict[str, dict[str, Any]],
        sources: dict[str, dict[str, Any]],
        ids: set[str] | None = None,
        berry_id: str = "",
        source: str = "",
    ) -> PendingDraftSnapshot:
        snapshot = self.provider.snapshot(entities=entities, sources=sources)
        rows = snapshot.records
        if ids:
            rows = [row for row in rows if str(row.get("id") or "") in ids]
        if berry_id:
            rows = [row for row in rows if berry_id in (row.get("berry_ids") or [])]
        if source:
            rows = [
                row for row in rows
                if source in {str(row.get("source_id") or ""), str(row.get("source_name") or "")}
            ]
        rows = [
            row for row in rows
            if row.get("evidence_role") != "atomic_evidence" and row.get("status", "draft") != "rejected"
        ]
        return PendingDraftSnapshot(
            records=rows,
            inventory_count=snapshot.inventory_count,
            parsed_records=snapshot.parsed_records,
            reused_records=snapshot.reused_records,
            body_records_omitted=snapshot.body_records_omitted,
        )
