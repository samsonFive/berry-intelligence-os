"""Bounded planning and private staging for current-page source reacquisition.

Current content is never treated as the historic reviewed artifact. Planning is
body-free and deterministic; execution creates a pending Source Fidelity Review
artifact without editing trusted Evidence.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable
from urllib.parse import urlparse

from app.services.article_acquisition import ArticleBody
from app.services.article_dedup import normalize_canonical_url, normalize_title
from app.services.extraction_backlog import berry_group, source_type_group
from app.services.source_fidelity_recovery import trusted_identity, trusted_identity_sha256


REACQUISITION_VERSION = "selective-source-reacquisition-v1"
OUTCOMES = {
    "EXACT_STABLE_SOURCE", "LIKELY_SAME_ARTICLE_CHANGED_FORMATTING",
    "CONTENT_CHANGED", "URL_REDIRECTED", "PAYWALLED", "REMOVED",
    "UNAVAILABLE", "AMBIGUOUS",
}


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _evidence_refs(records: Iterable[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for record in records:
        for field in ("evidence_ids", "counterevidence_ids"):
            counts.update(str(value) for value in record.get(field) or [] if value)
    return counts


def _source_likelihood(record: dict[str, Any]) -> tuple[str, int, str]:
    url = str(record.get("source_url") or "")
    host = (urlparse(url).hostname or "").casefold()
    group = source_type_group(record)
    if not url:
        return "UNLIKELY", 0, "no source URL is recorded"
    if host == "news.google.com":
        return "LOW", 0, "Google News wrapper requires publisher-URL resolution"
    if group == "company newsroom":
        return "HIGH", 3, "company newsroom pages often retain full owned articles"
    if group == "trade press":
        return "MEDIUM", 2, "trade press is often rich but may be paywalled or bot-protected"
    if group == "academic":
        return "MEDIUM", 2, "academic pages often retain abstracts or documents but access varies"
    if group == "government registry":
        return "HIGH", 3, "government/registry URLs are generally stable and structured"
    if group == "interview/podcast/video":
        return "LOW", 1, "spoken sources require a transcript artifact, not page chrome"
    return "MEDIUM", 1, "a source URL exists, with unknown historic source-type yield"


def prioritize_record(
    record: dict[str, Any], *, entities: dict[str, dict[str, Any]],
    signal_refs: Counter[str], assessment_refs: Counter[str],
) -> dict[str, Any]:
    """Explain every component; the total is ordering support, never truth."""
    evidence_id = str(record.get("id") or "")
    reasons: list[dict[str, Any]] = []

    def add(component: str, points: int, reason: str) -> None:
        if points:
            reasons.append({"component": component, "points": points, "reason": reason})

    signals = signal_refs[evidence_id]
    assessments = assessment_refs[evidence_id]
    add("signal_support", min(10, signals * 5), f"supports {signals} confirmed Signal(s)")
    add("assessment_support", min(8, assessments * 4), f"supports {assessments} Assessment(s)")

    linked = [entities[eid] for eid in record.get("entity_ids") or [] if eid in entities]
    companies = [row for row in linked if row.get("entity_type") == "company"]
    varieties = [row for row in linked if row.get("entity_type") == "variety"]
    add("linked_companies", min(4, len(companies)), f"links {len(companies)} strategic Company record(s)")
    add("linked_varieties", min(6, len(varieties) * 2), f"links {len(varieties)} Variety record(s)")

    berries = list(record.get("berry_ids") or [])
    if "berry-blackberry" in berries:
        add("blackberry_gap", 7, "Blackberry has zero extraction-ready sources")
    if "berry-raspberry" in berries:
        add("raspberry_gap", 6, "Raspberry extraction-ready coverage is near zero")
    if len(set(berries)) > 1:
        add("multi_berry", 2, f"covers {len(set(berries))} berries")

    downstream = signals + assessments
    add("multi_downstream_use", min(3, max(0, downstream - 1)), f"referenced by {downstream} downstream analytical object(s)")

    raw_date = str(record.get("published_date") or "")[:10]
    try:
        years = max(0, (date.today() - date.fromisoformat(raw_date)).days // 365)
    except ValueError:
        years = 99
    if years <= 1:
        add("recentness", 3, "published within roughly one year")
    elif years <= 3:
        add("recentness", 2, "published within roughly three years")
    elif years <= 6:
        add("recentness", 1, "published within roughly six years")

    availability, source_points, availability_reason = _source_likelihood(record)
    add("likely_source_yield", source_points, availability_reason)
    if record.get("source_url"):
        add("source_url_present", 2, "source URL is recorded")

    score = sum(row["points"] for row in reasons)
    priority = "HIGH" if score >= 11 else "MEDIUM" if score >= 6 else "LOW"
    known_failure = (
        (record.get("discovery_provenance") or {}).get("acquisition_failure_category")
        if isinstance(record.get("discovery_provenance"), dict) else None
    )
    return {
        "evidence_id": evidence_id,
        "source_url": record.get("source_url"),
        "source_type": record.get("source_type") or "unknown",
        "source_type_group": source_type_group(record),
        "berry": berry_group(record),
        "berry_ids": berries,
        "linked_entity_count": len(linked),
        "linked_company_count": len(companies),
        "linked_variety_count": len(varieties),
        "signal_count": signals,
        "assessment_count": assessments,
        "priority": priority,
        "priority_points": score,
        "priority_reasons": reasons,
        "likely_availability": availability,
        "realistic_reacquisition_candidate": priority == "HIGH" and availability in {"HIGH", "MEDIUM"},
        "availability_reason": availability_reason,
        "known_failure_state": known_failure,
        "existing_summary_sha256": _sha256(str(record.get("summary") or "")),
        "expected_review_path": "SOURCE_FIDELITY_REVIEW",
    }


def build_inventory(
    thin_records: list[dict[str, Any]], *, entities: list[dict[str, Any]],
    signals: list[dict[str, Any]], assessments: list[dict[str, Any]],
) -> dict[str, Any]:
    entity_index = {str(row.get("id")): row for row in entities if row.get("id")}
    signal_refs = _evidence_refs(signals)
    assessment_refs = _evidence_refs(assessments)
    items = [
        prioritize_record(
            record, entities=entity_index, signal_refs=signal_refs,
            assessment_refs=assessment_refs,
        )
        for record in thin_records
    ]
    items.sort(key=lambda row: (-row["priority_points"], row["evidence_id"]))
    return {
        "contract_version": REACQUISITION_VERSION,
        "counts": dict(sorted(Counter(row["priority"] for row in items).items())),
        "by_berry": dict(sorted(Counter(row["berry"] for row in items).items())),
        "by_source_type": dict(sorted(Counter(row["source_type_group"] for row in items).items())),
        "by_availability": dict(sorted(Counter(row["likely_availability"] for row in items).items())),
        "realistic_high_priority": sum(row["realistic_reacquisition_candidate"] for row in items),
        "realistic_high_priority_by_berry": dict(sorted(Counter(
            row["berry"] for row in items if row["realistic_reacquisition_candidate"]
        ).items())),
        "realistic_high_priority_by_source_type": dict(sorted(Counter(
            row["source_type_group"] for row in items if row["realistic_reacquisition_candidate"]
        ).items())),
        "items": items,
        "trust_notice": "Planning only. Priority is explainable operational triage, not analyst truth.",
    }


def select_pilot(items: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    if limit not in {10, 25}:
        raise ValueError("pilot limit must be 10 or 25")
    eligible = [
        row for row in items
        if row.get("source_url") and row.get("likely_availability") in {"HIGH", "MEDIUM"}
    ]
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    # Coverage first, using the best candidate in each actual berry group.
    for berry in ("Blackberry", "Raspberry", "Strawberry", "Blueberry", "Multi-berry"):
        match = next((row for row in eligible if row["berry"] == berry and row["evidence_id"] not in seen), None)
        if match:
            selected.append(match)
            seen.add(match["evidence_id"])
    # Then add source-type diversity before filling by priority.
    for group in ("company newsroom", "trade press", "academic", "government registry", "interview/podcast/video", "other"):
        if len(selected) >= limit:
            break
        match = next((row for row in eligible if row["source_type_group"] == group and row["evidence_id"] not in seen), None)
        if match:
            selected.append(match)
            seen.add(match["evidence_id"])
    for row in eligible:
        if len(selected) >= limit:
            break
        if row["evidence_id"] not in seen:
            selected.append(row)
            seen.add(row["evidence_id"])
    return selected


def pilot_manifest(items: list[dict[str, Any]], limit: int) -> dict[str, Any]:
    selected = select_pilot(items, limit)
    low_success = {"HIGH": 0.5, "MEDIUM": 0.2, "LOW": 0.05, "UNLIKELY": 0.0}
    high_success = {"HIGH": 0.8, "MEDIUM": 0.6, "LOW": 0.2, "UNLIKELY": 0.0}
    allowed = (
        "evidence_id", "source_url", "source_type", "source_type_group", "berry",
        "berry_ids", "linked_entity_count", "linked_company_count",
        "linked_variety_count", "signal_count", "assessment_count", "priority",
        "priority_points", "priority_reasons", "likely_availability",
        "realistic_reacquisition_candidate",
        "availability_reason", "known_failure_state", "existing_summary_sha256",
        "expected_review_path",
    )
    return {
        "manifest": f"REACQUISITION-PILOT-{limit}",
        "contract_version": REACQUISITION_VERSION,
        "network_acquisition_performed": False,
        "entries": [{key: row.get(key) for key in allowed} for row in selected],
        "estimated_ready_additions": {
            "low": round(sum(low_success.get(row["likely_availability"], 0) for row in selected)),
            "high": round(sum(high_success.get(row["likely_availability"], 0) for row in selected)),
            "basis": "Planning range only: HIGH availability 50-80%, MEDIUM 20-60%; no claim about analyst affirmation or observed yield.",
        },
        "trust_notice": "Body-free private plan. Execution requires an explicit network flag; every acquired artifact remains pending Source Fidelity Review.",
    }


def _tokens(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", value.casefold()) if len(token) > 3}


def compare_current_artifact(trusted: dict[str, Any], body: ArticleBody) -> dict[str, Any]:
    trusted_url = normalize_canonical_url(trusted.get("source_url"))
    final_url = normalize_canonical_url(body.final_url or body.source_url)
    title_match = bool(body.title and normalize_title(body.title) == normalize_title(trusted.get("title")))
    trusted_date = str(trusted.get("published_date") or "")[:10]
    current_date = str(body.published_date or "")[:10]
    date_match = bool(trusted_date and current_date and trusted_date == current_date)
    summary_tokens = _tokens(str(trusted.get("summary") or ""))
    body_tokens = _tokens(body.full_text)
    overlap = len(summary_tokens & body_tokens) / max(1, len(summary_tokens))
    historic_hash = (
        (trusted.get("article") or {}).get("content_sha256")
        if isinstance(trusted.get("article"), dict) else None
    )
    if historic_hash and historic_hash == body.content_sha256:
        outcome = "EXACT_STABLE_SOURCE"
    elif trusted_url != final_url:
        outcome = "URL_REDIRECTED" if (title_match or overlap >= 0.5) else "AMBIGUOUS"
    elif title_match and (date_match or not current_date) and overlap >= 0.5:
        outcome = "LIKELY_SAME_ARTICLE_CHANGED_FORMATTING"
    elif title_match or overlap >= 0.5:
        outcome = "CONTENT_CHANGED"
    else:
        outcome = "AMBIGUOUS"
    return {
        "outcome": outcome,
        "canonical_url_match": trusted_url == final_url,
        "title_match": title_match,
        "publication_date_match": date_match,
        "summary_token_overlap": round(overlap, 4),
        "historic_body_hash_match": bool(historic_hash and historic_hash == body.content_sha256),
        "source_name": trusted.get("source_name"),
        "trusted_url": trusted.get("source_url"),
        "final_url": body.final_url or body.source_url,
    }


def build_reacquired_artifact(trusted: dict[str, Any], body: ArticleBody) -> dict[str, Any]:
    comparison = compare_current_artifact(trusted, body)
    article = body.as_dict()
    artifact_hash = _sha256(json.dumps({"article": article}, sort_keys=True, ensure_ascii=False, separators=(",", ":")))
    return {
        "source_fidelity_artifact_schema_version": 1,
        "source_artifact_id": f"source-artifact-{artifact_hash[:20]}",
        "evidence_id": trusted["id"],
        "trusted_identity": trusted_identity(trusted),
        "trusted_identity_sha256": trusted_identity_sha256(trusted),
        "match_class": "REACQUIRED_CURRENT_SOURCE",
        "identity_proof": [key for key, value in comparison.items() if key.endswith("_match") and value],
        "reacquisition_classification": comparison,
        "artifact_type": "article",
        "source_title": body.title,
        "source_url": body.source_url,
        "final_url": body.final_url,
        "source_id": trusted.get("source_id"),
        "source_name": trusted.get("source_name"),
        "published_date": body.published_date,
        "body_sha256": body.content_sha256,
        "source_text_sha256": body.content_sha256,
        "source_artifact_sha256": artifact_hash,
        "source_chars": len(body.full_text),
        "language": body.language,
        "author": body.author,
        "acquisition": deepcopy(article.get("acquisition") or {}),
        "recovered_from": {
            "source": "current_public_page",
            "locator": body.final_url or body.source_url,
            "candidate_id": trusted["id"],
            "recovery_method": "explicit_bounded_current_source_reacquisition",
        },
        "artifact": {"article": article},
        "review": {"status": "pending", "reviewed_by": None, "reviewed_at": None},
        "reacquired_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "trust_notice": "Current content is separate from historic Evidence and untrusted until explicit Source Fidelity Review affirmation.",
    }


def classify_acquisition_failure(category: str, message: str = "") -> str:
    normalized = str(category or "").casefold()
    if normalized == "paywall":
        return "PAYWALLED"
    if normalized == "http_error" and any(code in message for code in ("404", "410")):
        return "REMOVED"
    if normalized == "redirect_error":
        return "URL_REDIRECTED"
    if normalized in {
        "blocked", "interstitial", "script_rendered", "timeout", "http_error",
        "transport_error", "empty_body", "malformed_html", "unsupported_media",
    }:
        return "UNAVAILABLE"
    return "AMBIGUOUS"
