"""Read-only readiness inventory and deterministic Atomic extraction manifests.

The inventory applies the same source-text contract as extraction, but never
calls a model and never writes Evidence.  Manifests contain hashes and public
metadata only; source text remains in the trusted repository.
"""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import math
from typing import Any

from app.exports.intelligence_package import SEED_EVIDENCE_IDS
from app.services.ai_extraction import EXTRACTION_VERSION
from app.services.article_dedup import find_duplicate_article
from app.services.source_body import atomic_extraction_source_text, classify_source_body
from app.services.source_fidelity_recovery import effective_record_for_extraction


READINESS_VERSION = "atomic-extraction-backlog-v1"
UNBOUND_QUALIFICATION = "UNBOUND_REQUIRES_EXPLICIT_QUALIFICATION"
READY_STATES = {
    "READY_FULL_ARTICLE",
    "READY_TRANSCRIPT",
    "READY_STRUCTURED_REGISTRY",
}
REGISTRY_SOURCE_TYPES = {
    "court_record",
    "government_alert",
    "government_recall",
    "government_registry",
    "patent",
    "patent_aggregator",
    "patent_record",
    "plant_breeders_rights_record",
    "trade_statistics_record",
    "weather_climate_record",
}
STRUCTURED_FIELDS = {
    "patent_filing",
    "recall_observation",
    "trade_observation",
    "weather_observation",
}
BERRY_ORDER = (
    "Blackberry",
    "Raspberry",
    "Strawberry",
    "Blueberry",
    "Multi-berry",
    "Untagged",
)
DIFFICULTY_ORDER = ("easy", "medium", "hard")


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _percentile(values: list[int], percentile: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[max(0, math.ceil(percentile * len(ordered)) - 1)]


def _distribution(values: list[int]) -> dict[str, int | float]:
    if not values:
        return {"count": 0, "median": 0, "p75": 0, "p90": 0, "max": 0}
    ordered = sorted(values)
    middle = len(ordered) // 2
    median = (
        ordered[middle]
        if len(ordered) % 2
        else round((ordered[middle - 1] + ordered[middle]) / 2, 3)
    )
    return {
        "count": len(ordered),
        "median": median,
        "p75": _percentile(ordered, 0.75),
        "p90": _percentile(ordered, 0.90),
        "max": ordered[-1],
    }


def berry_group(record: dict[str, Any]) -> str:
    names = {
        str(value).removeprefix("berry-").casefold()
        for value in record.get("berry_ids") or []
        if str(value).removeprefix("berry-").casefold()
        in {"blueberry", "strawberry", "raspberry", "blackberry"}
    }
    if len(names) > 1:
        return "Multi-berry"
    if not names:
        return "Untagged"
    return next(iter(names)).title()


def source_type_group(record: dict[str, Any]) -> str:
    source_type = str(record.get("source_type") or "").casefold()
    media_format = str(record.get("media_format") or "").casefold()
    if media_format in {"podcast", "video", "conference_video"} or source_type in {
        "industry_podcast", "interview", "podcast", "video"
    }:
        return "interview/podcast/video"
    if source_type in REGISTRY_SOURCE_TYPES:
        return "government registry"
    if source_type in {
        "research_program_publication", "extension_publication",
        "university_trial_report", "academic", "journal_article",
    }:
        return "academic"
    if source_type in {"trade_press", "news_media", "market_analysis_report"}:
        return "trade press"
    if source_type in {
        "brand_website", "company_annual_report", "company_catalog",
        "company_press_release", "company_technical_datasheet",
        "company_website", "development_finance_press_release",
        "marketer_website", "private_equity_press_release", "press_release",
    }:
        return "company newsroom"
    return "other"


def source_language(record: dict[str, Any]) -> str:
    article = record.get("article") if isinstance(record.get("article"), dict) else {}
    transcript = record.get("transcript") if isinstance(record.get("transcript"), dict) else {}
    discovery = (
        record.get("discovery_provenance")
        if isinstance(record.get("discovery_provenance"), dict)
        else {}
    )
    for value in (
        record.get("language"), article.get("language"), transcript.get("language"),
        discovery.get("language"),
    ):
        if isinstance(value, str) and value.strip():
            return value.strip().casefold()
    return "undetermined"


def _structured_registry(record: dict[str, Any]) -> bool:
    return (
        str(record.get("source_type") or "").casefold() in REGISTRY_SOURCE_TYPES
        or any(isinstance(record.get(field), dict) for field in STRUCTURED_FIELDS)
    )


def _fidelity_cause(record: dict[str, Any], body_state: str) -> str | None:
    if record.get("id") in SEED_EVIDENCE_IDS:
        return "known_fictional_seed"
    if _structured_registry(record):
        return "registry_object"
    if record.get("media_format") in {"podcast", "video", "conference_video"}:
        return "spoken_media_missing_transcript"
    if body_state in {"access_limited", "interstitial"}:
        return "acquisition_access_failure"
    if record.get("article"):
        return "partial_body_acquisition"
    if record.get("auto_captured") or str(record.get("source_type") or "") == "news_search":
        return "pre_body_acquisition"
    if not record.get("summary"):
        return "historic_seed"
    return "historic_seed"


def _difficulty(record: dict[str, Any], chars: int) -> str:
    if (
        chars >= 650
        or berry_group(record) == "Multi-berry"
        or len(record.get("entity_ids") or []) >= 4
    ):
        return "hard"
    if chars >= 300 or len(record.get("entity_ids") or []) >= 3:
        return "medium"
    return "easy"


def classify_record(record: dict[str, Any], source_artifact: dict[str, Any] | None = None) -> dict[str, Any]:
    """Classify one trusted record without persisting derived state."""
    effective = effective_record_for_extraction(record, source_artifact)
    source_text = atomic_extraction_source_text(effective)
    body = classify_source_body(effective)
    source_chars = len(source_text)
    if record.get("id") in SEED_EVIDENCE_IDS:
        source_class = "OTHER"
        readiness = "UNSUPPORTED_ARTIFACT"
    elif body["state"] == "body_available" and body["body"]:
        source_class = "ARTICLE_FULL_BODY"
        readiness = "READY_FULL_ARTICLE"
    elif body["transcript_text"]:
        source_class = "TRANSCRIPT"
        readiness = "READY_TRANSCRIPT"
    elif _structured_registry(record) and source_text:
        source_class = "REGISTRY_STRUCTURED"
        readiness = "READY_STRUCTURED_REGISTRY"
    elif (
        source_text
        and not body["body"]
        and not body["transcript_text"]
        and not body["excerpt"]
        and record.get("summary")
    ):
        source_class = "DESCRIPTION_ONLY"
        readiness = "THIN_DESCRIPTION_ONLY"
    elif not source_text and record.get("title"):
        source_class = "TITLE_ONLY"
        readiness = "MISSING_SOURCE_CONTENT"
    elif body["state"] == "body_partial":
        source_class = "OTHER"
        readiness = "UNSUPPORTED_ARTIFACT"
    else:
        source_class = "OTHER"
        readiness = "MISSING_SOURCE_CONTENT" if not source_text else "UNSUPPORTED_ARTIFACT"
    return {
        "id": record.get("id"),
        "status": record.get("status"),
        "readiness": readiness,
        "source_class": source_class,
        "source_type": record.get("source_type") or "unknown",
        "source_type_group": source_type_group(record),
        "berry_group": berry_group(record),
        "language": source_language(record),
        "source_chars": source_chars,
        "estimated_tokens": math.ceil(source_chars / 4),
        "source_sha256": _sha256(source_text),
        "difficulty": _difficulty(record, source_chars),
        "fidelity_cause": None if readiness in READY_STATES else _fidelity_cause(record, body["state"]),
        "duplicate_of": None,
        "duplicate_basis": None,
        "source_fidelity_review": (source_artifact or {}).get("review", {}).get("status"),
        "_record": record,
    }


def _mark_duplicates(items: list[dict[str, Any]]) -> None:
    accepted_records: list[dict[str, Any]] = []
    accepted_by_hash: dict[str, str] = {}
    for item in items:
        record = item["_record"]
        explicit = record.get("duplicate_of") or record.get("superseded_by")
        duplicate_of = str(explicit) if explicit else None
        duplicate_basis = "explicit_record_link" if duplicate_of else None
        if duplicate_of is None:
            probe = {
                **record,
                "canonical_url": record.get("source_url") or (record.get("article") or {}).get("final_url"),
            }
            duplicate_of = find_duplicate_article(probe, existing_records=accepted_records)
            if duplicate_of:
                duplicate_basis = "canonical_url_or_exact_title_contract"
        if (
            duplicate_of is None
            and item["readiness"] in READY_STATES
            and item["source_chars"] >= 80
        ):
            duplicate_of = accepted_by_hash.get(item["source_sha256"])
            if duplicate_of:
                duplicate_basis = "exact_extraction_source_hash"
        if duplicate_of:
            item["readiness"] = "DUPLICATE_OR_SUPERSEDED"
            item["duplicate_of"] = duplicate_of
            item["duplicate_basis"] = duplicate_basis
            item["fidelity_cause"] = "deterministic_duplicate"
        else:
            accepted_records.append(record)
            if item["readiness"] in READY_STATES and item["source_chars"] >= 80:
                accepted_by_hash.setdefault(item["source_sha256"], str(item["id"]))


def inventory(
    records: list[dict[str, Any]],
    source_artifacts: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    trusted = sorted(
        (deepcopy(record) for record in records if record.get("status") == "published"),
        key=lambda record: str(record.get("id") or ""),
    )
    artifacts = source_artifacts or {}
    items = [classify_record(record, artifacts.get(str(record.get("id")))) for record in trusted]
    _mark_duplicates(items)
    ready = [item for item in items if item["readiness"] in READY_STATES]
    length_groups = {
        "articles": [item["source_chars"] for item in ready if item["readiness"] == "READY_FULL_ARTICLE"],
        "transcripts": [item["source_chars"] for item in ready if item["readiness"] == "READY_TRANSCRIPT"],
        "registry_structured": [item["source_chars"] for item in ready if item["readiness"] == "READY_STRUCTURED_REGISTRY"],
    }
    public_items = [{key: value for key, value in item.items() if key != "_record"} for item in items]
    duplicate_groups: dict[str, list[dict[str, str]]] = {}
    for item in public_items:
        if item["duplicate_of"]:
            duplicate_groups.setdefault(item["duplicate_of"], []).append(
                {"source_id": item["id"], "basis": item["duplicate_basis"]}
            )
    thin_hash_counts = Counter(
        item["source_sha256"]
        for item in public_items
        if item["readiness"] == "THIN_DESCRIPTION_ONLY" and item["source_chars"] >= 80
    )
    return {
        "readiness_version": READINESS_VERSION,
        "trusted_published": len(items),
        "extraction_ready": len(ready),
        "classification_counts": dict(sorted(Counter(item["readiness"] for item in items).items())),
        "source_class_counts": dict(sorted(Counter(item["source_class"] for item in items).items())),
        "berry_distribution_ready": dict(sorted(Counter(item["berry_group"] for item in ready).items())),
        "source_type_distribution_ready": dict(sorted(Counter(item["source_type_group"] for item in ready).items())),
        "language_distribution_ready": dict(sorted(Counter(item["language"] for item in ready).items())),
        "fidelity_failure_causes": dict(sorted(Counter(item["fidelity_cause"] for item in items if item["fidelity_cause"]).items())),
        "duplicates_skipped": sum(item["readiness"] == "DUPLICATE_OR_SUPERSEDED" for item in items),
        "repeated_thin_source_hash_excess": sum(count - 1 for count in thin_hash_counts.values() if count > 1),
        "duplicate_groups": [
            {"canonical_source_id": source_id, "count": len(duplicates), "duplicates": duplicates}
            for source_id, duplicates in sorted(duplicate_groups.items())
        ],
        "length_distribution": {
            name: {
                "chars": _distribution(values),
                "estimated_tokens": _distribution([math.ceil(value / 4) for value in values]),
            }
            for name, values in length_groups.items()
        },
        "items": public_items,
    }


def _manifest_order(ready: list[dict[str, Any]]) -> list[dict[str, Any]]:
    remaining = [dict(item) for item in ready]
    selected: list[dict[str, Any]] = []
    berry_counts: Counter[str] = Counter()
    type_counts: Counter[str] = Counter()
    slot = 0
    while remaining:
        desired = DIFFICULTY_ORDER[slot % len(DIFFICULTY_ORDER)]
        pool = [item for item in remaining if item["difficulty"] == desired] or remaining
        choice = min(
            pool,
            key=lambda item: (
                berry_counts[item["berry_group"]],
                type_counts[item["source_type_group"]],
                BERRY_ORDER.index(item["berry_group"]),
                -item["source_chars"],
                item["id"],
            ),
        )
        selected.append(choice)
        remaining.remove(choice)
        berry_counts[choice["berry_group"]] += 1
        type_counts[choice["source_type_group"]] += 1
        slot += 1
    return selected


def build_manifest(
    report: dict[str, Any],
    requested_size: int,
    *,
    qualification_identity: str | None = None,
    seconds_per_window: float = 121.874,
    proposals_per_source: float = 54 / 16,
) -> dict[str, Any]:
    if requested_size <= 0:
        raise ValueError("manifest size must be positive")
    ready = [item for item in report["items"] if item["readiness"] in READY_STATES]
    chosen = _manifest_order(ready)[:requested_size]
    entries = [
        {
            "position": position,
            "source_id": item["id"],
            "source_sha256": item["source_sha256"],
            "source_chars": item["source_chars"],
            "estimated_tokens": item["estimated_tokens"],
            "readiness": item["readiness"],
            "berry_group": item["berry_group"],
            "source_type_group": item["source_type_group"],
            "difficulty": item["difficulty"],
        }
        for position, item in enumerate(chosen, start=1)
    ]
    windows = sum(max(1, math.ceil(item["source_chars"] / 12000)) for item in chosen)
    corpus_fingerprint = _sha256("\n".join(f"{item['id']}:{item['source_sha256']}" for item in ready))
    return {
        "manifest_schema_version": 1,
        "manifest_id": f"atomic-extraction-pilot-{requested_size}-v1",
        "readiness_version": READINESS_VERSION,
        "extraction_version": EXTRACTION_VERSION,
        "qualification_identity": qualification_identity or UNBOUND_QUALIFICATION,
        "qualification_required_before_execution": True,
        "requested_size": requested_size,
        "selected_size": len(entries),
        "capacity_limited": len(entries) < requested_size,
        "corpus_fingerprint": corpus_fingerprint,
        "sources": entries,
        "mix": {
            "berry": dict(sorted(Counter(item["berry_group"] for item in chosen).items())),
            "source_type": dict(sorted(Counter(item["source_type_group"] for item in chosen).items())),
            "difficulty": dict(sorted(Counter(item["difficulty"] for item in chosen).items())),
        },
        "hypothetical_runtime": {
            "basis": "failed local Qwen qualification; mechanical timeout exposure, not throughput proof",
            "seconds_per_window": seconds_per_window,
            "estimated_windows": windows,
            "estimated_seconds": round(windows * seconds_per_window, 3),
        },
        "review_volume": {
            "basis": "Gold Set expected proposition density; not observed model yield",
            "proposals_per_source": proposals_per_source,
            "estimated_proposals": math.ceil(len(entries) * proposals_per_source),
        },
        "external_cost_model": {
            "formula": "(input_tokens / 1000000 * input_rate_per_million) + (output_tokens / 1000000 * output_rate_per_million)",
            "input_rate_per_million": None,
            "output_rate_per_million": None,
            "note": "Rates intentionally unpopulated; bind provider-authoritative pricing at execution planning time without transmitting source text.",
        },
        "execution_contract": {
            "resumable_by": ["source_id", "source_sha256", "extraction_version", "qualification_identity"],
            "idempotent": True,
            "failures_isolated_per_source": True,
            "proposal_trust": "untrusted_human_review_required",
            "auto_publish": False,
            "source_text_embedded": False,
            "preconditions": [
                "explicit human qualification marker matches qualification_identity",
                "current source hash matches source_sha256",
                "extraction remains proposal-only with human review",
            ],
        },
    }
