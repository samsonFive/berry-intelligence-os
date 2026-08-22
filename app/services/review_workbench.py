"""Read-only composition for the existing Evidence review queue.

The workbench is deliberately not a review repository or workflow.  It joins
inbox drafts to already-published parents, Sources, and linked entities for
display, then leaves every decision to the existing publish/reject routes.
"""

from __future__ import annotations

import json
from collections import defaultdict
from copy import deepcopy
from math import floor
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from app.services.media_orchestration import MediaOrchestrationError, publication_draft_id
from app.services.transcript_evidence import TranscriptArtifact, TranscriptContractError


REVIEW_KINDS = {"all", "atomic", "publication"}
REVIEW_STATES = {"pending", "rejected", "all"}
REVIEW_SORTS = {"timestamp", "newest", "source", "parent", "recent"}
REVIEW_ENRICHMENT = {"all", "enriched", "raw"}

TRANSCRIPT_METHOD_LABELS = {
    "tier_1_publisher_transcript": "Publisher transcript",
    "tier_2_youtube_human_captions": "YouTube human captions",
    "tier_2_youtube_auto_captions": "YouTube auto captions",
    "tier_3_local_speech_to_text": "Local Whisper",
}


def unknown_transcript_readiness() -> dict[str, Any]:
    """Return a fail-closed presentation record for an unresolved runtime join."""

    return {
        "state": "unknown",
        "state_label": "Status unknown",
        "analyst_label": "Review-ready without transcript",
        "method": None,
        "language": None,
        "failure_category": None,
        "retry_count": None,
        "next_retry_at": None,
        "updated_at": None,
    }


ANALYST_TRANSCRIPT_LABELS = {
    "ready": "Transcript ready",
    "not_attempted": "Review-ready without transcript",
    "unknown": "Review-ready without transcript",
    "retryable_failure": "Transcript blocked — retry possible",
    "intervention_required": "Transcript blocked — needs operator",
}


def analyst_transcript_label(readiness: dict[str, Any] | None) -> str:
    readiness = readiness or {}
    state = readiness.get("state")
    return ANALYST_TRANSCRIPT_LABELS.get(state) or readiness.get("state_label") or "Transcript status unknown"


def _display_name(value: str, entities: dict[str, dict[str, Any]], berry_labels: dict[str, str]) -> str:
    if value in berry_labels:
        return berry_labels[value]
    name = (entities.get(value) or {}).get("name")
    if name:
        return name
    if "-" in value:
        return value.split("-", 1)[-1].replace("-", " ").title()
    return value


def _relevance_band(text: str) -> str:
    folded = (text or "").strip().casefold()
    if folded.startswith("high") or folded.startswith("direct"):
        return "High"
    if folded.startswith("moderate") or folded.startswith("medium"):
        return "Moderate"
    if folded.startswith("low"):
        return "Low"
    return "Relevant" if folded else ""


def _unique_names(ids: list[Any], entities: dict[str, dict[str, Any]], berry_labels: dict[str, str]) -> list[str]:
    names: list[str] = []
    for value in ids or []:
        if not isinstance(value, str) or not value:
            continue
        name = _display_name(value, entities, berry_labels)
        if name not in names:
            names.append(name)
    return names


def attach_publication_card(
    record: dict[str, Any],
    *,
    entities: dict[str, dict[str, Any]],
    berry_labels: dict[str, str],
) -> dict[str, Any]:
    """Add analyst-facing card fields without changing stored draft JSON."""

    enrichment = record.get("ai_enrichment") or {}
    publisher = (record.get("publisher_description") or "").strip()
    why = (record.get("why_it_matters") or enrichment.get("why_it_matters") or "").strip()
    summary = (enrichment.get("concise_summary") or "").strip()
    raw_summary = (record.get("summary") or "").strip()
    if not summary and raw_summary and raw_summary != publisher:
        summary = raw_summary
    provenance = enrichment.get("model_provenance") or {}
    readiness = record.get("transcript_readiness") or unknown_transcript_readiness()
    if isinstance(readiness, dict):
        readiness["analyst_label"] = analyst_transcript_label(readiness)
        record["transcript_readiness"] = readiness
    berry_ids = list(record.get("berry_ids") or []) + list(enrichment.get("suggested_berry_ids") or [])
    entity_ids = list(record.get("entity_ids") or []) + list(enrichment.get("suggested_entity_ids") or [])
    geo_ids = list(record.get("geography_ids") or []) + list(enrichment.get("suggested_geography_ids") or [])
    relevance = (enrichment.get("topical_relevance") or "").strip()
    record["card"] = {
        "why": why,
        "summary": summary,
        "relevance": relevance,
        "relevance_band": _relevance_band(relevance),
        "berries": _unique_names(berry_ids, entities, berry_labels),
        "entities": _unique_names(entity_ids, entities, berry_labels),
        "geographies": _unique_names(geo_ids, entities, berry_labels),
        "tags": [tag for tag in (enrichment.get("suggested_tags") or record.get("tags") or []) if tag],
        "ai_untrusted": provenance.get("trust_state") == "untrusted_suggestion" or provenance.get("status") == "ok",
        "transcript_label": analyst_transcript_label(readiness),
        "transcript_state": readiness.get("state"),
    }
    return record


def _attention_tuple(record: dict[str, Any]) -> tuple[int, int, str]:
    """Higher tuple sorts first when reversed: High relevance, then transcript-ready, then newest."""

    card = record.get("card") or {}
    enrichment = record.get("ai_enrichment") or {}
    band = card.get("relevance_band") or _relevance_band(enrichment.get("topical_relevance") or "")
    band_rank = {"High": 3, "Relevant": 2, "Moderate": 1, "Low": 0}.get(band, 0)
    state = card.get("transcript_state") or (record.get("transcript_readiness") or {}).get("state")
    ready = 1 if state == "ready" else 0
    date = str(record.get("published_date") or record.get("captured_date") or "")
    return (band_rank, ready, date)


def rank_publication_cards(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(records, key=_attention_tuple, reverse=True)


def build_scanner_summary(
    *,
    inbox_dir: Path,
    drafts: list[dict[str, Any]],
    published: list[dict[str, Any]],
    transcript_readiness: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Cheap, read-only scanner counts for the work-queue / review entry screens.

    Uses persisted screening and drafts. Does not orchestrate the full collection
    pipeline. Missing transcripts are not counted as failures.
    """

    discovered, _unreadable = _safe_runtime_objects(inbox_dir / "discovered_media")
    readiness = transcript_readiness if transcript_readiness is not None else load_publication_transcript_readiness(inbox_dir)
    screened = [
        item
        for item in discovered
        if isinstance(item.get("relevance_screening"), dict) and item.get("relevance_screening")
    ]
    pending_pubs = [
        draft
        for draft in drafts
        if draft.get("evidence_role") == "publication_artifact" and draft.get("status", "draft") != "rejected"
    ]
    pending_atomic = [
        draft
        for draft in drafts
        if draft.get("evidence_role") == "atomic_evidence" and draft.get("status", "draft") != "rejected"
    ]
    accepted = [
        record
        for record in published
        if record.get("evidence_role") == "publication_artifact" and record.get("status") == "published"
    ]
    transcript_ready = 0
    without_transcript = 0
    transcript_blocked = 0
    for draft in pending_pubs:
        state = (readiness.get(draft.get("id")) or {}).get("state")
        if state == "ready":
            transcript_ready += 1
        elif state in {"retryable_failure", "intervention_required"}:
            transcript_blocked += 1
        else:
            without_transcript += 1
    note = None
    if pending_pubs and transcript_ready == 0:
        if transcript_blocked:
            note = (
                f"{transcript_blocked} item(s) have a transcript acquisition blocker. "
                "Items that are review-ready without a transcript are not failures."
            )
        else:
            note = (
                "Transcripts are not ready yet. That is not a batch failure — "
                "publication review can proceed without a transcript."
            )
    return {
        "found": len(screened),
        "important": sum(1 for item in screened if (item.get("relevance_screening") or {}).get("decision") == "process"),
        "needs_review": len(pending_pubs),
        "accepted": len(accepted),
        "attention": transcript_blocked,
        "skipped": sum(1 for item in screened if (item.get("relevance_screening") or {}).get("decision") == "skip"),
        "transcript_ready": transcript_ready,
        "transcript_blocked": transcript_blocked,
        "review_ready_without_transcript": without_transcript,
        "atomic_pending": len(pending_atomic),
        "note": note,
        "has_recent_scan": bool(screened),
        "public_snapshot": False,
    }


def build_public_scanner_summary(published: list[dict[str, Any]]) -> dict[str, Any]:
    """Trusted-only scanner counts for the static public site.

    Never reads `inbox/`. Interactive review, enrichment proposals, and
    collection screening stay on the local Intelligence OS.
    """

    accepted = [record for record in published if record.get("status") == "published"]
    return {
        "found": 0,
        "important": 0,
        "needs_review": 0,
        "accepted": len(accepted),
        "attention": 0,
        "skipped": 0,
        "transcript_ready": 0,
        "transcript_blocked": 0,
        "review_ready_without_transcript": 0,
        "atomic_pending": 0,
        "has_recent_scan": False,
        "public_snapshot": True,
        "note": (
            "This public snapshot shows trusted published intelligence only. "
            "Interactive collection, enrichment, and publication review stay on the local Intelligence OS."
        ),
    }


def _safe_runtime_objects(folder: Path) -> tuple[list[dict[str, Any]], set[str]]:
    """Read one runtime collection without allowing a bad file to break review.

    The returned stems let the presentation layer distinguish an unreadable
    item-specific record from a record that genuinely does not exist. Nothing
    is repaired or written back.
    """

    records: list[dict[str, Any]] = []
    unreadable: set[str] = set()
    if not folder.exists():
        return records, unreadable
    for path in sorted(folder.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            unreadable.add(path.stem)
            continue
        if not isinstance(payload, dict):
            unreadable.add(path.stem)
            continue
        records.append(payload)
    return records, unreadable


def _valid_transcript(payload: dict[str, Any]) -> bool:
    probe = deepcopy(payload)
    if not probe.get("parent_evidence_id"):
        probe["parent_evidence_id"] = "ev-unresolved-publication-artifact"
    try:
        TranscriptArtifact.from_dict(probe)
    except TranscriptContractError:
        return False
    return True


def _latest_run_items(runs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, tuple[str, dict[str, Any]]] = {}
    for run in runs:
        timestamp = str(run.get("completed_at") or run.get("started_at") or run.get("run_id") or "")
        for item in run.get("items") or []:
            if not isinstance(item, dict) or not isinstance(item.get("item_id"), str):
                continue
            current = latest.get(item["item_id"])
            if current is None or timestamp >= current[0]:
                latest[item["item_id"]] = (timestamp, item)
    return {item_id: value[1] for item_id, value in latest.items()}


def _readiness_for_item(
    *,
    transcript: dict[str, Any] | None,
    transcript_unreadable: bool,
    operation: dict[str, Any] | None,
    operation_unreadable: bool,
    run_item: dict[str, Any] | None,
) -> dict[str, Any]:
    if transcript_unreadable or operation_unreadable:
        return unknown_transcript_readiness()

    if transcript is not None:
        if not _valid_transcript(transcript):
            return unknown_transcript_readiness()
        acquisition = transcript.get("acquisition") or {}
        provenance = transcript.get("provenance") or {}
        return {
            "state": "ready",
            "state_label": "Ready",
            "method": TRANSCRIPT_METHOD_LABELS.get(acquisition.get("tier"), "Unknown method"),
            "language": transcript.get("language") if isinstance(transcript.get("language"), str) else None,
            "failure_category": None,
            "retry_count": None,
            "next_retry_at": None,
            "updated_at": provenance.get("created_at"),
        }

    operation = operation or {}
    run_item = run_item or {}
    failure_class = operation.get("failure_class") or run_item.get("failure_class")
    transcript_status = run_item.get("transcript_status")
    updated_at = operation.get("last_attempted_at")

    if failure_class == "retryable":
        return {
            "state": "retryable_failure",
            "state_label": "Retryable failure",
            "method": None,
            "language": None,
            "failure_category": "Media acquisition challenge; retry remains available.",
            "retry_count": operation.get("retry_count") if isinstance(operation.get("retry_count"), int) else None,
            "next_retry_at": operation.get("next_eligible_retry_at"),
            "updated_at": updated_at,
        }

    if failure_class == "operator" or transcript_status == "malformed":
        return {
            "state": "intervention_required",
            "state_label": "Unavailable / intervention required",
            "method": None,
            "language": None,
            "failure_category": "Transcript acquisition requires operator intervention.",
            "retry_count": operation.get("retry_count") if isinstance(operation.get("retry_count"), int) else None,
            "next_retry_at": None,
            "updated_at": updated_at,
        }

    if transcript_status == "missing" and run_item.get("transcription_attempted") is False:
        return {
            "state": "not_attempted",
            "state_label": "Not attempted",
            "method": None,
            "language": None,
            "failure_category": None,
            "retry_count": None,
            "next_retry_at": None,
            "updated_at": updated_at,
        }

    if transcript_status == "not_applicable":
        # A written article -- no transcript concept applies at all, so
        # "unknown" would falsely suggest something is wrong or pending.
        return {
            "state": "not_applicable",
            "state_label": "Not applicable (written article)",
            "method": None,
            "language": None,
            "failure_category": None,
            "retry_count": None,
            "next_retry_at": None,
            "updated_at": updated_at,
        }

    return unknown_transcript_readiness()


def load_publication_transcript_readiness(inbox_dir: Path) -> dict[str, dict[str, Any]]:
    """Bulk-compose read-only transcript readiness keyed by publication draft.

    Four runtime collections are scanned once. Templates never touch JSON and
    this function never invokes discovery, acquisition, transcription, retry,
    or orchestration.
    """

    discovered, _unreadable_discovered = _safe_runtime_objects(inbox_dir / "discovered_media")
    transcripts, unreadable_transcripts = _safe_runtime_objects(
        inbox_dir / "discovered_media" / "_normalized_transcripts"
    )
    operations, unreadable_operations = _safe_runtime_objects(inbox_dir / "operations" / "items")
    runs, unreadable_runs = _safe_runtime_objects(inbox_dir / "operations" / "runs")

    transcript_by_item = {
        record["item_id"]: record
        for record in transcripts
        if isinstance(record.get("item_id"), str)
    }
    operation_by_item = {
        record["item_id"]: record
        for record in operations
        if isinstance(record.get("item_id"), str)
    }
    # Run filenames cannot safely reveal which items an unreadable summary
    # contains. Do not infer Not attempted from older history in that case.
    latest_run_by_item = {} if unreadable_runs else _latest_run_items(runs)
    result: dict[str, dict[str, Any]] = {}
    for item in discovered:
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id:
            continue
        try:
            draft_id = publication_draft_id(item)
        except MediaOrchestrationError:
            continue
        payload = _readiness_for_item(
            transcript=transcript_by_item.get(item_id),
            transcript_unreadable=item_id in unreadable_transcripts,
            operation=operation_by_item.get(item_id),
            operation_unreadable=item_id in unreadable_operations,
            run_item=latest_run_by_item.get(item_id),
        )
        payload["analyst_label"] = analyst_transcript_label(payload)
        result[draft_id] = payload

    return result


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
    publication_transcript_readiness: dict[str, dict[str, Any]] | None = None,
    filters: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    """Build grouped queue data using one bulk list per repository family."""

    filters = filters or {}
    publication_transcript_readiness = publication_transcript_readiness or {}
    kind = filters.get("kind") if filters.get("kind") in REVIEW_KINDS else "all"
    state_filter = filters.get("state") if filters.get("state") in REVIEW_STATES else "pending"
    sort = filters.get("sort") if filters.get("sort") in REVIEW_SORTS else "timestamp"
    enrichment_filter = filters.get("enrichment") if filters.get("enrichment") in REVIEW_ENRICHMENT else "all"
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
    for record in generic:
        source_id = record.get("source_id") or ""
        source_label = record.get("source_name") or source_id
        if source_id or source_label:
            option_sources[source_id or source_label] = source_label
        if record.get("media_format"):
            option_media.add(record["media_format"])
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
    if enrichment_filter == "enriched":
        generic = [
            record for record in generic
            if (record.get("ai_enrichment") or {}).get("model_provenance", {}).get("status") == "ok"
        ]
    elif enrichment_filter == "raw":
        generic = [
            record for record in generic
            if (record.get("ai_enrichment") or {}).get("model_provenance", {}).get("status") != "ok"
        ]
    generic_presentations = []
    for record in generic:
        presentation = deepcopy(record)
        if record.get("evidence_role") == "publication_artifact":
            presentation["transcript_readiness"] = deepcopy(
                publication_transcript_readiness.get(record.get("id")) or unknown_transcript_readiness()
            )
            attach_publication_card(presentation, entities=entity_index, berry_labels=berry_labels)
        generic_presentations.append(presentation)
    if sort == "source":
        generic_presentations.sort(key=lambda record: (record.get("source_name") or "").casefold())
    elif sort == "parent":
        generic_presentations.sort(key=lambda record: (record.get("title") or "").casefold())
    else:
        generic_presentations = rank_publication_cards(generic_presentations)

    return {
        "groups": groups,
        "generic_drafts": generic_presentations,
        "filters": {**filters, "kind": kind, "state": state_filter, "sort": sort, "enrichment": enrichment_filter},
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
