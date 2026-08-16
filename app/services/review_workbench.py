"""Read-only composition for the existing Evidence review queue.

The workbench is deliberately not a review repository or workflow.  It joins
inbox drafts to already-published parents, Sources, and linked entities for
display, then leaves every decision to the existing publish/reject routes.
"""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from math import floor
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


REVIEW_KINDS = {"all", "atomic", "publication"}
REVIEW_STATES = {"pending", "rejected", "all"}
REVIEW_SORTS = {"timestamp", "newest", "source", "parent"}


def format_timestamp(seconds: Any) -> str:
    if not isinstance(seconds, (int, float)) or isinstance(seconds, bool) or seconds < 0:
        return "—"
    total = floor(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def format_locator(locator: dict[str, Any] | None) -> str:
    locator = locator or {}
    start = format_timestamp(locator.get("start_seconds"))
    end = locator.get("end_seconds")
    return f"{start}–{format_timestamp(end)}" if end is not None else start


def timestamp_source_url(source_url: str | None, start_seconds: Any) -> str | None:
    """Return a timestamp link only for URLs whose platform supports it.

    This is host/provider-aware, never Source-ID-aware.  Unsupported podcast
    hosts keep their ordinary source URL rather than receiving a fabricated
    timestamp parameter.
    """

    if not source_url or not isinstance(start_seconds, (int, float)) or start_seconds < 0:
        return None
    parsed = urlparse(source_url)
    host = (parsed.hostname or "").lower()
    if host not in {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "www.youtu.be"}:
        return None
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["t"] = str(floor(start_seconds))
    return urlunparse(parsed._replace(query=urlencode(query)))


def _normalized_statement(record: dict[str, Any]) -> str:
    return " ".join(str(record.get("summary") or record.get("title") or "").casefold().split())


def _group_key(record: dict[str, Any]) -> tuple[str, str]:
    provenance = record.get("transcript_provenance") or {}
    return record.get("parent_evidence_id") or "unresolved-parent", provenance.get("transcript_id") or "unknown-transcript"


def _source_label(parent: dict[str, Any], sources: dict[str, dict[str, Any]]) -> str:
    source = sources.get(parent.get("source_id")) or {}
    return source.get("label") or source.get("name") or parent.get("source_name") or "Unknown source"


def _record_state(record: dict[str, Any], *, trusted: bool) -> str:
    if trusted or record.get("status") == "published":
        return "approved"
    if record.get("status") == "rejected" or record.get("review_state") == "rejected":
        return "rejected"
    return "pending"


def _same_span_or_overlap(left: dict[str, Any], right: dict[str, Any]) -> bool:
    a = left.get("artifact_locator") or {}
    b = right.get("artifact_locator") or {}
    a_start, b_start = a.get("start_seconds"), b.get("start_seconds")
    if not isinstance(a_start, (int, float)) or not isinstance(b_start, (int, float)):
        return False
    a_end = a.get("end_seconds") if isinstance(a.get("end_seconds"), (int, float)) else a_start
    b_end = b.get("end_seconds") if isinstance(b.get("end_seconds"), (int, float)) else b_start
    return a_start <= b_end and b_start <= a_end


def _duplicate_warnings(records: list[dict[str, Any]]) -> dict[str, list[dict[str, str]]]:
    warnings: dict[str, list[dict[str, str]]] = defaultdict(list)
    for index, left in enumerate(records):
        for right in records[index + 1 :]:
            reasons = []
            if _normalized_statement(left) and _normalized_statement(left) == _normalized_statement(right):
                reasons.append("same normalized statement")
            if _same_span_or_overlap(left, right):
                reasons.append("overlapping transcript span")
            if not reasons:
                continue
            reason = " and ".join(reasons)
            warnings[left["id"]].append({"id": right["id"], "reason": reason})
            warnings[right["id"]].append({"id": left["id"], "reason": reason})
    return warnings


def _card(
    record: dict[str, Any],
    *,
    parent: dict[str, Any],
    source_label: str,
    entities: dict[str, dict[str, Any]],
    berry_labels: dict[str, str],
    state: str,
) -> dict[str, Any]:
    locator = record.get("artifact_locator") or {}
    geography_ids = set(record.get("geography_ids") or [])
    berry_ids = record.get("berry_ids") or []
    entity_ids = [value for value in (record.get("entity_ids") or []) if value not in geography_ids]
    extraction = record.get("extraction_provenance") or {}
    transcript = record.get("transcript_provenance") or {}
    return {
        "record": record,
        "state": state,
        "statement": record.get("summary") or record.get("title") or "",
        "excerpt": record.get("transcript_excerpt"),
        "locator_label": format_locator(locator),
        "speaker_label": locator.get("speaker_label"),
        "source_at_timestamp": timestamp_source_url(parent.get("source_url"), locator.get("start_seconds")),
        "entities": [entities[value] for value in entity_ids if value in entities],
        "geographies": [entities[value] for value in geography_ids if value in entities],
        "berries": [
            {"id": value, "name": (entities.get(value) or {}).get("name") or berry_labels.get(value, value)}
            for value in berry_ids
        ],
        "parent": parent,
        "source_label": source_label,
        "extraction": extraction,
        "transcript": transcript,
        "context_before": record.get("transcript_context_before"),
        "context_after": record.get("transcript_context_after"),
    }


def build_review_workbench(
    *,
    drafts: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    entities: list[dict[str, Any]],
    berry_labels: dict[str, str],
    filters: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    """Build grouped queue data using one bulk list per repository family."""

    filters = filters or {}
    kind = filters.get("kind") if filters.get("kind") in REVIEW_KINDS else "all"
    state_filter = filters.get("state") if filters.get("state") in REVIEW_STATES else "pending"
    sort = filters.get("sort") if filters.get("sort") in REVIEW_SORTS else "timestamp"
    source_filter = filters.get("source") or ""
    parent_filter = filters.get("parent") or ""
    media_filter = filters.get("media_format") or ""
    berry_filter = filters.get("berry") or ""
    geography_filter = filters.get("geography") or ""
    model_filter = filters.get("model") or ""
    version_filter = filters.get("version") or ""

    parents = {record["id"]: record for record in evidence if record.get("id")}
    source_index = {record["id"]: record for record in sources if record.get("id")}
    entity_index = {record["id"]: record for record in entities if record.get("id")}
    trusted_atomic = [
        record for record in evidence
        if record.get("evidence_role") == "atomic_evidence" and record.get("status") == "published"
    ]
    draft_atomic = [record for record in drafts if record.get("evidence_role") == "atomic_evidence"]

    grouped_history: dict[tuple[str, str], list[tuple[dict[str, Any], bool]]] = defaultdict(list)
    for record in draft_atomic:
        grouped_history[_group_key(record)].append((record, False))
    for record in trusted_atomic:
        grouped_history[_group_key(record)].append((record, True))

    groups = []
    option_sources: dict[str, str] = {}
    option_parents: dict[str, str] = {}
    option_media: set[str] = set()
    option_models: set[str] = set()
    option_versions: set[str] = set()
    for (parent_id, transcript_id), history in grouped_history.items():
        parent = deepcopy(parents.get(parent_id) or {
            "id": parent_id,
            "title": f"Unresolved parent: {parent_id}",
            "source_name": "Unknown source",
        })
        source_label = _source_label(parent, source_index)
        source_id = parent.get("source_id") or history[0][0].get("source_id") or ""
        option_sources[source_id or source_label] = source_label
        option_parents[parent_id] = parent.get("title") or parent_id
        if parent.get("media_format"):
            option_media.add(parent["media_format"])
        for record, _trusted in history:
            provenance = record.get("extraction_provenance") or {}
            if provenance.get("model"):
                option_models.add(provenance["model"])
            if provenance.get("prompt_version"):
                option_versions.add(provenance["prompt_version"])

        def matches(record: dict[str, Any], state: str) -> bool:
            provenance = record.get("extraction_provenance") or {}
            if state_filter != "all" and state != state_filter:
                return False
            if source_filter and source_filter not in {source_id, source_label}:
                return False
            if parent_filter and parent_filter != parent_id:
                return False
            if media_filter and parent.get("media_format") != media_filter:
                return False
            if berry_filter and berry_filter not in (record.get("berry_ids") or []):
                return False
            if geography_filter and geography_filter not in (record.get("geography_ids") or []):
                return False
            if model_filter and provenance.get("model") != model_filter:
                return False
            if version_filter and provenance.get("prompt_version") != version_filter:
                return False
            return True

        visible = [(record, _record_state(record, trusted=trusted)) for record, trusted in history]
        visible = [(record, state) for record, state in visible if matches(record, state)]
        if kind == "publication":
            visible = []
        if not visible and not (parent_filter == parent_id and kind in {"all", "atomic"}):
            continue

        pending_records = [record for record, trusted in history if _record_state(record, trusted=trusted) == "pending"]
        warnings = _duplicate_warnings(pending_records)
        cards = [
            _card(
                record,
                parent=parent,
                source_label=source_label,
                entities=entity_index,
                berry_labels=berry_labels,
                state=state,
            )
            for record, state in visible
        ]
        for card in cards:
            card["duplicate_warnings"] = warnings.get(card["record"]["id"], [])

        if sort == "newest":
            cards.sort(key=lambda card: card["record"].get("captured_date") or "", reverse=True)
        else:
            cards.sort(key=lambda card: (card["record"].get("artifact_locator") or {}).get("start_seconds", float("inf")))

        states = [_record_state(record, trusted=trusted) for record, trusted in history]
        groups.append({
            "key": f"{parent_id}:{transcript_id}",
            "parent": parent,
            "parent_id": parent_id,
            "transcript_id": transcript_id,
            "source_label": source_label,
            "cards": cards,
            "progress": {
                "total": len(states),
                "approved": states.count("approved"),
                "rejected": states.count("rejected"),
                "remaining": states.count("pending"),
                "reviewed": states.count("approved") + states.count("rejected"),
            },
        })

    if sort == "newest":
        groups.sort(key=lambda group: max((card["record"].get("captured_date") or "" for card in group["cards"]), default=""), reverse=True)
    elif sort == "source":
        groups.sort(key=lambda group: (group["source_label"].casefold(), group["parent"].get("title", "").casefold()))
    else:
        groups.sort(key=lambda group: group["parent"].get("title", "").casefold())

    generic = [record for record in drafts if record.get("evidence_role") != "atomic_evidence"]
    if state_filter == "pending":
        generic = [record for record in generic if record.get("status", "draft") != "rejected"]
    elif state_filter == "rejected":
        generic = [record for record in generic if record.get("status") == "rejected"]
    if kind == "atomic":
        generic = []
    elif kind == "publication":
        generic = [record for record in generic if record.get("evidence_role") == "publication_artifact"]
    if source_filter:
        generic = [record for record in generic if source_filter in {record.get("source_id"), record.get("source_name")}]
    if parent_filter:
        generic = []
    if media_filter:
        generic = [record for record in generic if record.get("media_format") == media_filter]
    if berry_filter:
        generic = [record for record in generic if berry_filter in (record.get("berry_ids") or [])]
    if geography_filter:
        generic = [record for record in generic if geography_filter in (record.get("geography_ids") or [])]
    if sort == "newest":
        generic.sort(key=lambda record: record.get("captured_date") or "", reverse=True)
    elif sort == "source":
        generic.sort(key=lambda record: (record.get("source_name") or "").casefold())
    else:
        generic.sort(key=lambda record: (record.get("title") or "").casefold())

    return {
        "groups": groups,
        "generic_drafts": generic,
        "filters": {**filters, "kind": kind, "state": state_filter, "sort": sort},
        "options": {
            "sources": sorted(({"id": key, "label": value} for key, value in option_sources.items()), key=lambda value: value["label"].casefold()),
            "parents": sorted(({"id": key, "label": value} for key, value in option_parents.items()), key=lambda value: value["label"].casefold()),
            "media_formats": sorted(option_media),
            "models": sorted(option_models),
            "versions": sorted(option_versions),
            "berries": sorted(({"id": key, "label": value} for key, value in berry_labels.items()), key=lambda value: value["label"]),
            "geographies": sorted(
                ({"id": record["id"], "label": record["name"]} for record in entities if record.get("entity_type") == "geography"),
                key=lambda value: value["label"].casefold(),
            ),
        },
    }
