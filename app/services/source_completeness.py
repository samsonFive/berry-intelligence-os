"""Deterministic source-completeness metadata, separate from Evidence trust."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.services.source_body import classify_source_body


SOURCE_COMPLETENESS_VERSION = "source-completeness-v1"
SOURCE_CLASSES = {
    "FULL_ARTICLE",
    "FULL_TRANSCRIPT",
    "STRUCTURED_REGISTRY",
    "THIN_DESCRIPTION",
    "NO_CONTENT",
}

# Kept local because source completeness is a low-level publication concern;
# importing the extraction inventory here would create a review/orchestration
# cycle. The vocabulary mirrors the canonical structured-source contract.
REGISTRY_SOURCE_TYPES = {
    "court_record", "government_alert", "government_recall",
    "government_registry", "patent", "patent_aggregator", "patent_record",
    "plant_breeders_rights_record", "trade_statistics_record",
    "weather_climate_record",
}
STRUCTURED_FIELDS = {
    "patent_filing", "recall_observation", "trade_observation",
    "weather_observation",
}

FAILURE_CLASSES = {
    "paywall": "PAYWALL",
    "blocked": "ROBOTS",
    "empty_body": "EMPTY_BODY",
    "interstitial": "INTERSTITIAL",
    "script_rendered": "SCRIPT_RENDERED",
    "removed": "REMOVED",
    "timeout": "TIMEOUT",
    "unsupported_media": "UNSUPPORTED_MEDIA",
    "transcript_unavailable": "TRANSCRIPT_UNAVAILABLE",
    "redirect_error": "REDIRECT_ERROR",
    "http_error": "HTTP_ERROR",
    "transport_error": "TRANSPORT_ERROR",
    "malformed_html": "MALFORMED_HTML",
    "repeated_body": "REPEATED_BODY",
}

RETRYABLE_FAILURES = {
    "TIMEOUT", "HTTP_ERROR", "TRANSPORT_ERROR", "REDIRECT_ERROR",
}


def _structured_registry(record: dict[str, Any]) -> bool:
    return (
        str(record.get("source_type") or "").casefold() in REGISTRY_SOURCE_TYPES
        or any(isinstance(record.get(field), dict) for field in STRUCTURED_FIELDS)
    )


def normalize_failure_category(category: str | None) -> str | None:
    if not category:
        return None
    normalized = str(category).strip().casefold().replace("-", "_")
    return FAILURE_CLASSES.get(normalized, normalized.upper())


def source_completeness(
    record: dict[str, Any], *, failure_category: str | None = None,
    operator_accepted_thin: bool | None = None,
) -> dict[str, Any]:
    """Return small inspectable metadata; never changes trust or readiness."""
    body = classify_source_body(record)
    article = record.get("article") if isinstance(record.get("article"), dict) else {}
    transcript = record.get("transcript") if isinstance(record.get("transcript"), dict) else {}
    source_artifact = record.get("source_artifact") if isinstance(record.get("source_artifact"), dict) else {}
    discovery = record.get("discovery_provenance") if isinstance(record.get("discovery_provenance"), dict) else {}
    explicit_failure = normalize_failure_category(
        failure_category
        or discovery.get("acquisition_failure_category")
        or discovery.get("failure_category")
    )
    if body["state"] == "body_available" and body["body"]:
        source_class = "FULL_ARTICLE"
    elif body["transcript_text"] or (
        source_artifact.get("kind") == "transcript"
        and source_artifact.get("status") == "captured"
        and source_artifact.get("content_sha256")
    ):
        source_class = "FULL_TRANSCRIPT"
    elif _structured_registry(record):
        source_class = "STRUCTURED_REGISTRY"
    elif body["publisher_description"] or record.get("summary"):
        source_class = "THIN_DESCRIPTION"
    else:
        source_class = "NO_CONTENT"
    return {
        "version": SOURCE_COMPLETENESS_VERSION,
        "class": source_class,
        "failure_category": explicit_failure,
        "retryable": explicit_failure in RETRYABLE_FAILURES if explicit_failure else False,
        "content_sha256": article.get("content_sha256") or transcript.get("content_sha256") or source_artifact.get("content_sha256"),
        "operator_accepted_thin": bool(operator_accepted_thin),
    }


def with_source_completeness(
    record: dict[str, Any], *, failure_category: str | None = None,
    operator_accepted_thin: bool | None = None,
) -> dict[str, Any]:
    updated = deepcopy(record)
    updated["source_completeness"] = source_completeness(
        updated,
        failure_category=failure_category,
        operator_accepted_thin=operator_accepted_thin,
    )
    return updated
