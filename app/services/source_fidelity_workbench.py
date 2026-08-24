"""Analyst-facing Source Fidelity Review projections. Does not change trust."""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from urllib.parse import urlencode

from app.services.extraction_backlog import classify_record
from app.services.source_completeness import source_completeness
from app.services.source_fidelity_recovery import effective_record_for_extraction


IDENTITY_PROOF_LABELS = {
    "EXACT_IDENTITY_MATCH": "Exact Evidence ID",
    "EXACT_CANONICAL_URL": "Exact canonical URL",
    "EXACT_URL_MATCH": "Exact canonical URL",
    "LINEAGE_MATCH": "Discovered-item / source-artifact lineage",
    "EXACT_TITLE_SOURCE_DATE_ONLY": "Title + source + date only (weak)",
    "REUSED_BODY_HASH_ACROSS_DISTINCT_PUBLICATIONS": "Repeated body hash across distinct publications",
    "REACQUIRED_CURRENT_SOURCE": "Reacquired from the current public page",
    "canonical_url_match": "Canonical URL match",
    "title_match": "Title match",
    "publication_date_match": "Publication-date match",
    "historic_body_hash_match": "Historic body-hash match",
}

QUEUE_META_KEYS = (
    "source_fidelity_artifact_schema_version",
    "source_artifact_id",
    "evidence_id",
    "match_class",
    "identity_proof",
    "artifact_type",
    "source_title",
    "source_url",
    "final_url",
    "source_id",
    "source_name",
    "published_date",
    "source_chars",
    "language",
    "author",
    "acquisition",
    "recovered_from",
    "review",
    "reacquisition_classification",
    "reacquired_at",
    "body_sha256",
    "source_text_sha256",
    "source_artifact_sha256",
    "trust_notice",
)


def review_status(artifact: dict[str, Any]) -> str:
    blob = artifact.get("review") if isinstance(artifact.get("review"), dict) else {}
    return str(blob.get("status") or "pending")


def recovered_from(artifact: dict[str, Any]) -> dict[str, Any]:
    blob = artifact.get("recovered_from") if isinstance(artifact.get("recovered_from"), dict) else {}
    return blob


def recovery_kind(artifact: dict[str, Any]) -> str:
    match = str(artifact.get("match_class") or "")
    origin = str(recovered_from(artifact).get("source") or "").casefold()
    if (
        match == "REACQUIRED_CURRENT_SOURCE"
        or origin in {"current_public_page", "live_public_page"}
        or artifact.get("reacquisition_classification")
        or artifact.get("reacquired_at")
    ):
        return "reacquired_current"
    return "historic_recovery"


def _article(artifact: dict[str, Any]) -> dict[str, Any]:
    payload = artifact.get("artifact") if isinstance(artifact.get("artifact"), dict) else {}
    article = payload.get("article") if isinstance(payload.get("article"), dict) else {}
    return article


def _transcript(artifact: dict[str, Any]) -> dict[str, Any]:
    payload = artifact.get("artifact") if isinstance(artifact.get("artifact"), dict) else {}
    transcript = payload.get("transcript") if isinstance(payload.get("transcript"), dict) else {}
    return transcript


def paragraphs(artifact: dict[str, Any]) -> list[dict[str, Any]]:
    rows = _article(artifact).get("paragraphs") or []
    return [row for row in rows if isinstance(row, dict)]


def segments(artifact: dict[str, Any]) -> list[dict[str, Any]]:
    rows = _transcript(artifact).get("segments") or []
    return [row for row in rows if isinstance(row, dict)]


def queue_projection(artifact: dict[str, Any]) -> dict[str, Any]:
    """Metadata only — never copy article/transcript bodies onto the list path."""
    projected = {key: deepcopy(artifact.get(key)) for key in QUEUE_META_KEYS if key in artifact}
    projected["review_status"] = review_status(artifact)
    projected["recovery_kind"] = recovery_kind(artifact)
    projected["paragraph_count"] = len(paragraphs(artifact))
    projected["segment_count"] = len(segments(artifact))
    projected["has_body"] = False
    return projected


def identity_proof_items(artifact: dict[str, Any]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    seen: set[str] = set()
    match = str(artifact.get("match_class") or "")
    tokens = list(artifact.get("identity_proof") or [])
    if match:
        tokens = [match, *tokens]
    for token in tokens:
        code = str(token)
        if code in seen:
            continue
        seen.add(code)
        items.append({"code": code, "label": IDENTITY_PROOF_LABELS.get(code, code.replace("_", " ").title())})
    return items


def warning_codes(artifact: dict[str, Any], trusted: dict[str, Any]) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []
    if recovery_kind(artifact) == "reacquired_current":
        warnings.append({
            "code": "REACQUIRED_LATER",
            "label": "Current page may have changed since original publication",
            "detail": "This artifact was fetched later from the live URL. It is not the historic capture.",
        })
    recovered_url = str(artifact.get("source_url") or "")
    final_url = str(artifact.get("final_url") or recovered_url)
    trusted_url = str(trusted.get("source_url") or "")
    if final_url and trusted_url and final_url.rstrip("/") != trusted_url.rstrip("/"):
        warnings.append({"code": "FINAL_URL_DIFFERS", "label": "Final URL differs", "detail": f"{trusted_url} → {final_url}"})
    elif final_url and recovered_url and final_url.rstrip("/") != recovered_url.rstrip("/"):
        warnings.append({"code": "FINAL_URL_DIFFERS", "label": "Final URL differs from requested URL", "detail": f"{recovered_url} → {final_url}"})
    artifact_title = str(artifact.get("source_title") or "")
    if artifact_title and trusted.get("title") and artifact_title.strip() != str(trusted.get("title")).strip():
        warnings.append({"code": "TITLE_CHANGED", "label": "Title changed", "detail": artifact_title})
    artifact_date = str(artifact.get("published_date") or "")[:10]
    trusted_date = str(trusted.get("published_date") or "")[:10]
    if artifact_date and trusted_date and artifact_date != trusted_date:
        warnings.append({"code": "DATE_DIFFERS", "label": "Publication date differs", "detail": f"{trusted_date} → {artifact_date}"})
    if not artifact.get("author"):
        warnings.append({"code": "AUTHOR_MISSING", "label": "Author missing", "detail": "No author was captured on the recovered artifact."})
    haystack = " ".join([
        recovered_url,
        final_url,
        str(recovered_from(artifact).get("source") or ""),
        str(recovered_from(artifact).get("locator") or ""),
    ]).casefold()
    if "news.google." in haystack or "google.com/rss" in haystack:
        warnings.append({"code": "GOOGLE_NEWS_WRAPPER", "label": "Google News wrapper", "detail": "Requested URL looks like a Google News wrapper, not a publisher page."})
    proof = {str(item) for item in (artifact.get("identity_proof") or [])}
    if "REUSED_BODY_HASH_ACROSS_DISTINCT_PUBLICATIONS" in proof:
        warnings.append({"code": "REPEATED_BODY_HASH", "label": "Repeated body hash", "detail": "The same body hash appears on distinct publications."})
    classification = artifact.get("reacquisition_classification") if isinstance(artifact.get("reacquisition_classification"), dict) else {}
    outcome = str(classification.get("outcome") or "")
    if outcome in {"CONTENT_CHANGED", "AMBIGUOUS", "URL_REDIRECTED"} or classification.get("historic_body_hash_match") is False:
        warnings.append({
            "code": "CONTENT_HASH_CONFLICT" if outcome == "CONTENT_CHANGED" else "CHANGED_OR_AMBIGUOUS",
            "label": outcome.replace("_", " ").title() if outcome else "Current page comparison warning",
            "detail": "Treat live-page identity as unverified until you inspect the body.",
        })
    if str(artifact.get("match_class") or "") in {"AMBIGUOUS", "CONFLICT"}:
        warnings.append({"code": "AMBIGUOUS_IDENTITY", "label": "Ambiguous or conflicting identity", "detail": str(artifact.get("match_class"))})
    transcript = _transcript(artifact)
    if transcript:
        language = str(transcript.get("language") or artifact.get("language") or "").casefold()
        if language and language not in {"en", "eng", "english"}:
            warnings.append({"code": "TRANSCRIPT_LANGUAGE", "label": "Transcript language limitation", "detail": str(transcript.get("language"))})
        if not any(segment.get("speaker") or segment.get("speaker_label") for segment in segments(artifact)):
            warnings.append({"code": "TRANSCRIPT_SPEAKER", "label": "Transcript speaker labels not present", "detail": "Segments are timestamped without speaker labels."})
    return warnings


def priority_reasons(trusted: dict[str, Any], *, signal_ids: set[str] | None = None) -> list[str]:
    reasons: list[str] = []
    berries = {str(item) for item in (trusted.get("berry_ids") or [])}
    if "berry-raspberry" in berries:
        reasons.append("Raspberry undercoverage")
    if "berry-blackberry" in berries:
        reasons.append("Blackberry undercoverage")
    if signal_ids and trusted.get("id") in signal_ids:
        reasons.append("Supports a signal")
    variety_ids = [str(item) for item in (trusted.get("entity_ids") or []) if str(item).startswith("variety-")]
    if len(variety_ids) >= 2:
        reasons.append("Linked to multiple varieties")
    if any(str(item).startswith("company-") for item in (trusted.get("entity_ids") or [])):
        reasons.append("High-value company linkage")
    return reasons


def consequence_preview(trusted: dict[str, Any], artifact: dict[str, Any]) -> dict[str, Any]:
    before_complete = source_completeness(trusted).get("class")
    before_ready = classify_record(trusted, None)["readiness"]
    hypothetical = deepcopy(artifact)
    review = dict(hypothetical.get("review") or {})
    review["status"] = "affirmed"
    hypothetical["review"] = review
    after_record = effective_record_for_extraction(trusted, hypothetical)
    return {
        "completeness_before": before_complete,
        "completeness_after": source_completeness(after_record).get("class"),
        "readiness_before": before_ready,
        "readiness_after": classify_record(trusted, hypothetical)["readiness"],
        "semantic_trust": trusted.get("status"),
        "atomic_created": False,
        "extraction_runs": False,
    }


def reader_payload(artifact: dict[str, Any]) -> dict[str, Any]:
    transcript = _transcript(artifact)
    return {
        "paragraphs": [
            {"index": row.get("index", index), "text": row.get("text") or ""}
            for index, row in enumerate(paragraphs(artifact))
        ],
        "segments": [
            {
                "index": row.get("index"),
                "start_seconds": row.get("start_seconds"),
                "end_seconds": row.get("end_seconds"),
                "speaker": row.get("speaker") or row.get("speaker_label") or "",
                "text": row.get("text") or "",
            }
            for row in segments(artifact)
        ],
        "language": artifact.get("language") or transcript.get("language"),
        "transcription_method": transcript.get("transcription_method") or transcript.get("source"),
        "duration": transcript.get("duration_seconds"),
    }


def staged_at(artifact: dict[str, Any]) -> str | None:
    review = artifact.get("review") if isinstance(artifact.get("review"), dict) else {}
    acquisition = artifact.get("acquisition") if isinstance(artifact.get("acquisition"), dict) else {}
    origin = recovered_from(artifact)
    return (
        artifact.get("reacquired_at")
        or review.get("reviewed_at")
        or acquisition.get("fetched_at")
        or acquisition.get("transcribed_at")
        or origin.get("recovered_at")
    )


def berry_labels(trusted: dict[str, Any]) -> list[str]:
    mapping = {
        "berry-raspberry": "Raspberry",
        "berry-blackberry": "Blackberry",
        "berry-blueberry": "Blueberry",
        "berry-strawberry": "Strawberry",
    }
    return [mapping.get(str(item), str(item)) for item in (trusted.get("berry_ids") or [])]


def named_ids(ids: list[Any], entities: dict[str, dict[str, Any]] | None = None) -> list[str]:
    entities = entities or {}
    names = []
    for item in ids:
        row = entities.get(str(item)) or {}
        names.append(str(row.get("name") or item))
    return names


def _matches_filters(row: dict[str, Any], filters: dict[str, str]) -> bool:
    status = (filters.get("state") or "pending").strip()
    if status not in {"", "all"} and row["review_state"] != status:
        return False
    if filters.get("artifact_type") and row["artifact_type"] != filters["artifact_type"]:
        return False
    if filters.get("recovery_kind") and row["recovery_kind"] != filters["recovery_kind"]:
        return False
    berry = filters.get("berry") or ""
    if berry and berry not in row["berries"] and berry not in (row["trusted"].get("berry_ids") or []):
        return False
    if filters.get("source") and filters["source"].casefold() not in str(row["source_name"]).casefold():
        return False
    if filters.get("match_class") and row["match_class"] != filters["match_class"]:
        return False
    if filters.get("warning"):
        codes = {item["code"] for item in row["warnings"]}
        if filters["warning"] not in codes:
            return False
    return True


def build_queue_rows(
    artifacts: list[dict[str, Any]],
    trusted_by_id: dict[str, dict[str, Any]],
    *,
    filters: dict[str, str] | None = None,
    entities: dict[str, dict[str, Any]] | None = None,
    signal_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    filters = filters or {}
    rows: list[dict[str, Any]] = []
    for artifact in artifacts:
        trusted = trusted_by_id.get(str(artifact.get("evidence_id") or ""))
        if not trusted:
            continue
        status = review_status(artifact)
        warnings = warning_codes(artifact, trusted)
        row = {
            "trusted": trusted,
            "artifact": queue_projection(artifact),
            "review_state": status,
            "recovery_kind": recovery_kind(artifact),
            "warnings": warnings,
            "primary_warning": warnings[0]["label"] if warnings else "",
            "priority_reasons": priority_reasons(trusted, signal_ids=signal_ids),
            "berries": berry_labels(trusted),
            "entities": named_ids(list(trusted.get("entity_ids") or []), entities),
            "staged_at": staged_at(artifact),
            "match_class": artifact.get("match_class") or "",
            "artifact_type": artifact.get("artifact_type") or "",
            "source_name": trusted.get("source_name") or artifact.get("source_name") or "",
        }
        if _matches_filters(row, filters):
            row["recovery_kind"] = row["recovery_kind"]
            row["review_state"] = row["review_state"]
            rows.append(row)
    match_rank = {
        "EXACT_IDENTITY_MATCH": 0,
        "EXACT_URL_MATCH": 1,
        "LINEAGE_MATCH": 2,
        "REACQUIRED_CURRENT_SOURCE": 3,
    }
    rows.sort(key=lambda row: (
        0 if row["review_state"] == "pending" else 1,
        match_rank.get(row["match_class"], 9),
        row["artifact_type"] != "article",
        not any(item in {"Raspberry", "Blackberry"} for item in row["berries"]),
        -int(row["artifact"].get("source_chars") or 0),
        row["trusted"]["id"],
    ))
    for index, row in enumerate(rows):
        row["prev_id"] = rows[index - 1]["trusted"]["id"] if index else ""
        row["next_id"] = rows[index + 1]["trusted"]["id"] if index + 1 < len(rows) else ""
    return rows


def filter_query(filters: dict[str, str]) -> str:
    return urlencode({key: value for key, value in filters.items() if value})


def neighbor_ids(rows: list[dict[str, Any]], evidence_id: str) -> tuple[str, str]:
    for row in rows:
        if row["trusted"]["id"] == evidence_id:
            return row.get("prev_id") or "", row.get("next_id") or ""
    return "", ""
