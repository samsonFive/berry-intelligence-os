"""Deterministic, private recovery of richer source artifacts for trusted Evidence."""

from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from app.services.article_dedup import normalize_canonical_url, normalize_title
from app.services.source_body import atomic_extraction_source_text, classify_source_body


RECOVERY_SCHEMA_VERSION = 1
MATCH_CLASSES = {
    "EXACT_IDENTITY_MATCH", "EXACT_URL_MATCH", "LINEAGE_MATCH",
    "AMBIGUOUS", "NO_MATCH", "CONFLICT",
}
APPLICABLE_MATCHES = {"EXACT_IDENTITY_MATCH", "EXACT_URL_MATCH", "LINEAGE_MATCH"}
DECISIONS = {"affirmed", "rejected", "needs_investigation"}


def _json_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def trusted_identity(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "evidence_id": record.get("id"),
        "title": record.get("title"),
        "source_url": record.get("source_url"),
        "normalized_source_url": normalize_canonical_url(record.get("source_url")),
        "source_id": record.get("source_id"),
        "source_name": record.get("source_name"),
        "published_date": record.get("published_date"),
    }


def trusted_identity_sha256(record: dict[str, Any]) -> str:
    return _json_hash(trusted_identity(record))


def _artifact_payload(record: dict[str, Any]) -> tuple[str | None, dict[str, Any] | None]:
    if record.get("record_type") in {"transcript_artifact", "staged_transcript"}:
        segments = record.get("segments")
        if isinstance(segments, list) and any(
            isinstance(segment, dict) and str(segment.get("text") or "").strip()
            for segment in segments
        ):
            return "transcript", {"transcript": deepcopy(record)}
    body = classify_source_body(record)
    if body["state"] == "body_available" and body["body"]:
        article = deepcopy(record.get("article") or {})
        paragraphs = article.get("paragraphs") or []
        indexes = [row.get("index") for row in paragraphs if isinstance(row, dict)]
        if indexes != list(range(len(paragraphs))):
            return None, None
        return "article", {"article": article}
    if body["transcript_text"]:
        transcript = deepcopy(record.get("transcript") or {})
        return "transcript", {"transcript": transcript}
    return None, None


def candidate_from_record(record: dict[str, Any], *, recovery_source: str, locator: str) -> dict[str, Any] | None:
    artifact_type, payload = _artifact_payload(record)
    if not artifact_type or payload is None:
        return None
    source_probe = deepcopy(record)
    if artifact_type == "transcript" and not isinstance(record.get("transcript"), dict):
        source_probe["transcript"] = deepcopy(payload["transcript"])
    source_text = atomic_extraction_source_text(source_probe)
    lineage_ids = sorted({
        str(value) for value in (
            record.get("source_artifact_id"), record.get("publication_draft_id"),
            record.get("parent_evidence_id"), record.get("discovered_item_id"),
            record.get("normalized_media_id"), record.get("item_id"),
            record.get("transcript_id"),
        ) if value
    })
    artifact_hash = _json_hash(payload)
    return {
        "candidate_id": record.get("id") or record.get("transcript_id"),
        "title": record.get("title"),
        "source_url": record.get("source_url"),
        "normalized_source_url": normalize_canonical_url(record.get("source_url")),
        "source_id": record.get("source_id"),
        "source_name": record.get("source_name"),
        "published_date": record.get("published_date"),
        "lineage_ids": lineage_ids,
        "artifact_type": artifact_type,
        "artifact": payload,
        "source_text_sha256": hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
        "source_chars": len(source_text),
        "source_artifact_sha256": artifact_hash,
        "recovery_source": recovery_source,
        "recovery_locator": locator,
        "language": (
            (record.get("article") or {}).get("language")
            or (record.get("transcript") or {}).get("language")
            or record.get("language")
        ),
        "acquisition": deepcopy(
            (record.get("article") or {}).get("acquisition")
            or (record.get("transcript") or {}).get("acquisition")
            or record.get("acquisition")
            or {}
        ),
        "author": (record.get("article") or {}).get("author"),
        "final_url": (record.get("article") or {}).get("final_url"),
    }


def load_candidate_records(locations: Iterable[tuple[str, Path]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for label, folder in locations:
        if not folder.exists():
            continue
        for path in sorted(folder.rglob("*.json")):
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError, json.JSONDecodeError):
                continue
            if not isinstance(record, dict):
                continue
            candidate = candidate_from_record(record, recovery_source=label, locator=str(path.resolve()))
            if candidate is None:
                continue
            key = (str(candidate["candidate_id"]), candidate["source_artifact_sha256"])
            if key in seen:
                continue
            seen.add(key)
            candidates.append(candidate)
    return candidates


def _title_key(record: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        normalize_title(record.get("title")),
        str(record.get("source_id") or ""),
        str(record.get("source_name") or "").casefold(),
        str(record.get("published_date") or "")[:10],
    )


def _choose(matches: list[dict[str, Any]], match_class: str, trusted: dict[str, Any]) -> dict[str, Any]:
    if not matches:
        return {"evidence_id": trusted.get("id"), "match_class": "NO_MATCH", "candidate": None, "identity_proof": []}
    hashes = {row["source_artifact_sha256"] for row in matches}
    types = {row["artifact_type"] for row in matches}
    if len(hashes) > 1 or len(types) > 1:
        return {
            "evidence_id": trusted.get("id"), "match_class": "CONFLICT", "candidate": None,
            "identity_proof": [match_class],
            "conflicting_candidates": [
                {key: row[key] for key in ("candidate_id", "source_url", "artifact_type", "source_artifact_sha256", "recovery_source")}
                for row in matches
            ],
        }
    chosen = sorted(matches, key=lambda row: (row["recovery_source"], row["recovery_locator"]))[0]
    trusted_url = normalize_canonical_url(trusted.get("source_url"))
    if match_class == "EXACT_IDENTITY_MATCH" and trusted_url and chosen["normalized_source_url"] and trusted_url != chosen["normalized_source_url"]:
        return {
            "evidence_id": trusted.get("id"), "match_class": "CONFLICT", "candidate": None,
            "identity_proof": ["same Evidence ID but conflicting canonical URL"],
            "conflicting_candidates": [{key: chosen[key] for key in ("candidate_id", "source_url", "source_artifact_sha256", "recovery_source")}],
        }
    proof = [match_class]
    if trusted_url and trusted_url == chosen["normalized_source_url"]:
        proof.append("EXACT_CANONICAL_URL")
    return {"evidence_id": trusted.get("id"), "match_class": match_class, "candidate": chosen, "identity_proof": proof}


def match_recoveries(trusted_records: list[dict[str, Any]], candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Bulk-index and match without N×repository scans."""
    by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_url: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_lineage: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_title: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        if candidate["candidate_id"]:
            by_id[str(candidate["candidate_id"])].append(candidate)
        if candidate["normalized_source_url"]:
            by_url[candidate["normalized_source_url"]].append(candidate)
        for lineage_id in candidate["lineage_ids"]:
            by_lineage[lineage_id].append(candidate)
        by_title[_title_key(candidate)].append(candidate)

    results: list[dict[str, Any]] = []
    for trusted in sorted(trusted_records, key=lambda row: str(row.get("id") or "")):
        evidence_id = str(trusted.get("id") or "")
        url = normalize_canonical_url(trusted.get("source_url"))
        exact_id = by_id.get(evidence_id, [])
        if exact_id:
            result = _choose(exact_id, "EXACT_IDENTITY_MATCH", trusted)
        elif url and by_url.get(url):
            result = _choose(by_url[url], "EXACT_URL_MATCH", trusted)
        else:
            trusted_lineage_ids = {
                evidence_id,
                *(
                    str(value) for value in (
                        trusted.get("source_artifact_id"), trusted.get("publication_draft_id"),
                        trusted.get("discovered_item_id"), trusted.get("normalized_media_id"),
                        trusted.get("transcript_id"),
                    ) if value
                ),
            }
            lineage = []
            seen_lineage: set[tuple[str, str]] = set()
            for lineage_id in sorted(trusted_lineage_ids):
                for candidate in by_lineage.get(lineage_id, []):
                    key = (str(candidate.get("candidate_id")), candidate["source_artifact_sha256"])
                    if key not in seen_lineage:
                        seen_lineage.add(key)
                        lineage.append(candidate)
            if lineage:
                result = _choose(lineage, "LINEAGE_MATCH", trusted)
            else:
                weak = by_title.get(_title_key(trusted), [])
                result = {
                    "evidence_id": evidence_id,
                    "match_class": "AMBIGUOUS" if weak else "NO_MATCH",
                    "candidate": None,
                    "identity_proof": ["EXACT_TITLE_SOURCE_DATE_ONLY"] if weak else [],
                    "ambiguous_candidates": [
                        {key: row[key] for key in ("candidate_id", "source_url", "source_artifact_sha256", "recovery_source")}
                        for row in weak
                    ],
                }
        result["trusted_identity"] = trusted_identity(trusted)
        result["trusted_identity_sha256"] = trusted_identity_sha256(trusted)
        result["berry_ids"] = list(trusted.get("berry_ids") or [])
        result["entity_ids"] = list(trusted.get("entity_ids") or [])
        result["source_type"] = trusted.get("source_type")
        result["source_name"] = trusted.get("source_name")
        results.append(result)

    # A body repeated across three or more distinct publication URLs is not
    # credible as independent historic source fidelity. This catches reused
    # acquisition/interstitial payloads without rejecting a legitimate
    # two-publication reprint pair. Keep body-free audit metadata, but make the
    # candidates non-applicable and require investigation.
    by_body: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for result in results:
        candidate = result.get("candidate")
        if result.get("match_class") in APPLICABLE_MATCHES and candidate:
            by_body[(candidate["artifact_type"], candidate["source_text_sha256"])].append(result)
    for group in by_body.values():
        distinct_urls = {
            str((result.get("trusted_identity") or {}).get("normalized_source_url") or "")
            for result in group
        }
        distinct_urls.discard("")
        if len(group) < 3 or len(distinct_urls) < 3:
            continue
        for result in group:
            candidate = result["candidate"]
            result["match_class"] = "CONFLICT"
            result["identity_proof"] = [
                *(result.get("identity_proof") or []),
                "REUSED_BODY_HASH_ACROSS_DISTINCT_PUBLICATIONS",
            ]
            result["conflict_reason"] = "REUSED_BODY_HASH_ACROSS_DISTINCT_PUBLICATIONS"
            result["conflict_count"] = len(group)
            result["conflict_candidate_metadata"] = {
                key: candidate.get(key)
                for key in (
                    "artifact_type", "source_text_sha256", "source_artifact_sha256",
                    "source_chars", "recovery_source", "language",
                )
            }
            result["candidate"] = None
    return results


def priority_key(result: dict[str, Any]) -> tuple[Any, ...]:
    candidate = result.get("candidate") or {}
    berries = set(result.get("berry_ids") or [])
    caneberry = bool(berries & {"berry-raspberry", "berry-blackberry"})
    match_rank = {"EXACT_IDENTITY_MATCH": 0, "EXACT_URL_MATCH": 1, "LINEAGE_MATCH": 2}.get(result["match_class"], 9)
    type_rank = {"article": 0, "transcript": 1}.get(candidate.get("artifact_type"), 9)
    return (match_rank, type_rank, not caneberry, -int(candidate.get("source_chars") or 0), result["evidence_id"])


def recovery_manifest(results: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(results, key=priority_key)
    entries = []
    for result in ordered:
        candidate = result.get("candidate") or result.get("conflict_candidate_metadata") or {}
        entries.append({
            "evidence_id": result["evidence_id"],
            "match_class": result["match_class"],
            "source_artifact_id": (
                f"source-artifact-{candidate['source_artifact_sha256'][:20]}" if candidate else None
            ),
            "artifact_type": candidate.get("artifact_type"),
            "source_url": (result.get("trusted_identity") or {}).get("source_url"),
            "source_text_sha256": candidate.get("source_text_sha256"),
            "source_artifact_sha256": candidate.get("source_artifact_sha256"),
            "source_chars": candidate.get("source_chars"),
            "recovery_source": candidate.get("recovery_source"),
            "current_fidelity_state": "RECOVERABLE_PENDING_HUMAN_AFFIRMATION" if result["match_class"] in APPLICABLE_MATCHES else result["match_class"],
            "berry_ids": result.get("berry_ids") or [],
            "entity_ids": result.get("entity_ids") or [],
            "source_type": result.get("source_type"),
            "source_name": result.get("source_name"),
            "language": candidate.get("language"),
            "identity_proof": result.get("identity_proof") or [],
            "conflict_reason": result.get("conflict_reason"),
            "conflict_count": result.get("conflict_count"),
        })
    counts = Counter(row["match_class"] for row in results)
    exact = [row for row in entries if row["match_class"] in APPLICABLE_MATCHES]
    return {
        "recovery_manifest_schema_version": 1,
        "recovery_contract_version": "source-fidelity-recovery-v1",
        "counts": dict(sorted(counts.items())),
        "recoverable_articles": sum(row["artifact_type"] == "article" for row in exact),
        "recoverable_transcripts": sum(row["artifact_type"] == "transcript" for row in exact),
        "recoverable_by_berry": dict(sorted(Counter(
            berry for row in exact for berry in row["berry_ids"]
        ).items())),
        "recoverable_by_source_type": dict(sorted(Counter(
            str(row["source_type"] or "unknown") for row in exact
        ).items())),
        "recoverable_by_language": dict(sorted(Counter(
            str(row["language"] or "undetermined") for row in exact
        ).items())),
        "recoverable_by_entity": dict(sorted(Counter(
            entity for row in exact for entity in row["entity_ids"]
        ).items())),
        "entries": entries,
        "trust_notice": "Dry-run candidates only. Recovery is additive and does not affirm source fidelity or alter trusted Evidence.",
    }


def build_recovery_artifact(result: dict[str, Any], trusted: dict[str, Any]) -> dict[str, Any]:
    if result.get("match_class") not in APPLICABLE_MATCHES or not result.get("candidate"):
        raise ValueError("only deterministic exact/lineage matches can be staged")
    if result["evidence_id"] != trusted.get("id"):
        raise ValueError("trusted Evidence identity changed")
    if result["trusted_identity_sha256"] != trusted_identity_sha256(trusted):
        raise ValueError("trusted Evidence identity hash changed")
    candidate = result["candidate"]
    return {
        "source_fidelity_artifact_schema_version": RECOVERY_SCHEMA_VERSION,
        "source_artifact_id": f"source-artifact-{candidate['source_artifact_sha256'][:20]}",
        "evidence_id": trusted["id"],
        "trusted_identity": trusted_identity(trusted),
        "trusted_identity_sha256": trusted_identity_sha256(trusted),
        "match_class": result["match_class"],
        "identity_proof": result["identity_proof"],
        "artifact_type": candidate["artifact_type"],
        "source_title": candidate.get("title"),
        "source_url": candidate["source_url"],
        "final_url": candidate.get("final_url"),
        "source_id": candidate.get("source_id"),
        "source_name": candidate.get("source_name"),
        "published_date": candidate.get("published_date"),
        "body_sha256": candidate["source_text_sha256"],
        "source_text_sha256": candidate["source_text_sha256"],
        "source_artifact_sha256": candidate["source_artifact_sha256"],
        "source_chars": candidate["source_chars"],
        "language": candidate.get("language"),
        "author": candidate.get("author"),
        "acquisition": candidate.get("acquisition") or {},
        "recovered_from": {
            "source": candidate["recovery_source"],
            "locator": candidate["recovery_locator"],
            "candidate_id": candidate["candidate_id"],
            "recovery_method": "deterministic_historic_artifact_match",
        },
        "artifact": candidate["artifact"],
        "review": {"status": "pending", "reviewed_by": None, "reviewed_at": None},
        "trust_notice": "Recovered source content is private and untrusted for extraction until explicit source-fidelity affirmation.",
    }


def write_recovery_artifact(path: Path, artifact: dict[str, Any]) -> str:
    encoded = json.dumps(artifact, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing == artifact:
            return "unchanged"
        raise ValueError(f"recovery artifact conflict: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(encoded, encoding="utf-8")
    temporary.replace(path)
    return "created"


def load_recovery_artifacts(folder: Path) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    if not folder.exists():
        return artifacts
    for path in sorted(folder.glob("*.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if isinstance(value, dict) and value.get("source_fidelity_artifact_schema_version") == RECOVERY_SCHEMA_VERSION:
            artifacts.append(value)
    return artifacts


def save_recovery_decision(path: Path, before: dict[str, Any], after: dict[str, Any]) -> None:
    current = json.loads(path.read_text(encoding="utf-8"))
    if current != before:
        raise ValueError("source-fidelity artifact changed during review")
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(after, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def decide_recovery_artifact(
    artifact: dict[str, Any], trusted: dict[str, Any], *, decision: str,
    reviewer: str, reviewed_at: str | None = None,
) -> dict[str, Any]:
    if decision not in DECISIONS:
        raise ValueError("unsupported source-fidelity decision")
    if not reviewer.strip():
        raise ValueError("reviewer is required")
    if artifact.get("evidence_id") != trusted.get("id") or artifact.get("trusted_identity_sha256") != trusted_identity_sha256(trusted):
        raise ValueError("recovery artifact no longer matches trusted Evidence identity")
    updated = deepcopy(artifact)
    updated["review"] = {
        "status": decision,
        "reviewed_by": reviewer.strip(),
        "reviewed_at": reviewed_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    return updated


def effective_record_for_extraction(trusted: dict[str, Any], artifact: dict[str, Any] | None) -> dict[str, Any]:
    record = deepcopy(trusted)
    if not artifact or (artifact.get("review") or {}).get("status") != "affirmed":
        return record
    if artifact.get("evidence_id") != trusted.get("id") or artifact.get("trusted_identity_sha256") != trusted_identity_sha256(trusted):
        raise ValueError("affirmed recovery artifact does not match trusted Evidence identity")
    payload = artifact.get("artifact") or {}
    if artifact.get("artifact_type") == "article" and isinstance(payload.get("article"), dict):
        record["article"] = deepcopy(payload["article"])
    elif artifact.get("artifact_type") == "transcript" and isinstance(payload.get("transcript"), dict):
        record["transcript"] = deepcopy(payload["transcript"])
    return record
