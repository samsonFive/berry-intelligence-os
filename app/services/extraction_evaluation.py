"""Untrusted evaluation tooling around the existing AI extraction provider.

Evaluation calls the production provider directly and never writes Evidence.
Only an explicit caller of TranscriptEvidenceExtractionService may promote the
same configured provider into the existing proposal workflow.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Callable

from app.services.ai_extraction import (
    PROMPT_VERSION,
    ExtractionProviderError,
    OpenAICompatibleExtractionProvider,
    build_transcript_windows,
)
from app.services.transcript_evidence import ExtractionRequest, TranscriptArtifact


EVALUATION_SCHEMA_VERSION = 1
_EXPECTATION_FIELDS = {
    "candidate_count",
    "required_phrase_groups",
    "required_qualifiers",
    "prohibited_phrases",
    "required_segment_sets",
    "expected_atomic_claims",
    "max_link_count",
    "category",
    "notes",
}


class EvaluationContractError(ValueError):
    """An evaluation fixture or transcript does not satisfy the harness contract."""


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    title: str
    segments: tuple[dict[str, Any], ...]
    expectations: dict[str, Any]


@dataclass(frozen=True)
class ExtractionBenchmark:
    benchmark_id: str
    version: int
    description: str
    cases: tuple[BenchmarkCase, ...]


def load_benchmark(path: Path) -> ExtractionBenchmark:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvaluationContractError(f"could not read benchmark: {exc}") from exc
    if not isinstance(payload, dict) or set(payload) != {"benchmark_id", "version", "description", "cases"}:
        raise EvaluationContractError("benchmark fields do not match the evaluation contract")
    if not isinstance(payload["benchmark_id"], str) or not payload["benchmark_id"].strip():
        raise EvaluationContractError("benchmark_id is required")
    if not isinstance(payload["version"], int) or payload["version"] < 1:
        raise EvaluationContractError("benchmark version must be a positive integer")
    if not isinstance(payload["description"], str) or not isinstance(payload["cases"], list) or not payload["cases"]:
        raise EvaluationContractError("benchmark description and cases are required")
    cases: list[BenchmarkCase] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(payload["cases"]):
        if not isinstance(raw, dict) or set(raw) != {"id", "title", "segments", "expectations"}:
            raise EvaluationContractError(f"cases[{index}] fields do not match the contract")
        case_id = raw["id"]
        if not isinstance(case_id, str) or not re.fullmatch(r"[a-z0-9-]+", case_id) or case_id in seen_ids:
            raise EvaluationContractError(f"cases[{index}].id must be unique lowercase kebab-case")
        seen_ids.add(case_id)
        if not isinstance(raw["title"], str) or not raw["title"].strip():
            raise EvaluationContractError(f"cases[{index}].title is required")
        segments = _validate_segments(raw["segments"], index)
        expectations = _validate_expectations(raw["expectations"], index, len(segments))
        cases.append(BenchmarkCase(case_id, raw["title"].strip(), tuple(segments), expectations))
    return ExtractionBenchmark(
        benchmark_id=payload["benchmark_id"].strip(),
        version=payload["version"],
        description=payload["description"].strip(),
        cases=tuple(cases),
    )


def _validate_segments(raw_segments: Any, case_index: int) -> list[dict[str, Any]]:
    if not isinstance(raw_segments, list) or not raw_segments:
        raise EvaluationContractError(f"cases[{case_index}].segments must be nonempty")
    segments: list[dict[str, Any]] = []
    previous_start = -1.0
    for segment_index, raw in enumerate(raw_segments):
        if not isinstance(raw, dict) or set(raw) - {"text", "start_seconds", "end_seconds", "speaker_label"}:
            raise EvaluationContractError(f"cases[{case_index}].segments[{segment_index}] is malformed")
        text = raw.get("text")
        start = raw.get("start_seconds")
        end = raw.get("end_seconds")
        if not isinstance(text, str) or not text.strip():
            raise EvaluationContractError(f"cases[{case_index}].segments[{segment_index}].text is required")
        if not isinstance(start, (int, float)) or isinstance(start, bool) or start < previous_start:
            raise EvaluationContractError(f"cases[{case_index}].segments must have ordered numeric starts")
        if end is not None and (not isinstance(end, (int, float)) or isinstance(end, bool) or end < start):
            raise EvaluationContractError(f"cases[{case_index}].segments[{segment_index}].end_seconds is invalid")
        previous_start = float(start)
        segments.append(dict(raw))
    return segments


def _validate_expectations(raw: Any, case_index: int, segment_count: int) -> dict[str, Any]:
    if not isinstance(raw, dict) or set(raw) - _EXPECTATION_FIELDS:
        raise EvaluationContractError(f"cases[{case_index}].expectations contains unsupported fields")
    count = raw.get("candidate_count")
    if not isinstance(count, dict) or set(count) != {"min", "max"}:
        raise EvaluationContractError(f"cases[{case_index}] requires candidate_count min/max")
    if any(not isinstance(count[key], int) or count[key] < 0 for key in ("min", "max")) or count["min"] > count["max"]:
        raise EvaluationContractError(f"cases[{case_index}].candidate_count is invalid")
    expectations = dict(raw)
    for field_name in ("required_phrase_groups", "required_segment_sets"):
        value = expectations.get(field_name, [])
        if not isinstance(value, list) or any(not isinstance(group, list) or not group for group in value):
            raise EvaluationContractError(f"cases[{case_index}].{field_name} must be a list of nonempty lists")
    for group in expectations.get("required_phrase_groups", []):
        if any(not isinstance(value, str) or not value for value in group):
            raise EvaluationContractError(f"cases[{case_index}].required_phrase_groups must contain text")
    for group in expectations.get("required_segment_sets", []):
        if any(not isinstance(value, int) or value < 0 or value >= segment_count for value in group):
            raise EvaluationContractError(f"cases[{case_index}].required_segment_sets is outside the transcript")
    for field_name in ("required_qualifiers", "prohibited_phrases"):
        value = expectations.get(field_name, [])
        if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
            raise EvaluationContractError(f"cases[{case_index}].{field_name} must be a string list")
    for field_name in ("expected_atomic_claims", "max_link_count"):
        value = expectations.get(field_name)
        if value is not None and (not isinstance(value, int) or value < 0):
            raise EvaluationContractError(f"cases[{case_index}].{field_name} must be a nonnegative integer")
    return expectations


def benchmark_transcript(case: BenchmarkCase) -> TranscriptArtifact:
    return TranscriptArtifact.from_dict(
        {
            "transcript_id": f"benchmark-{case.case_id}",
            "parent_evidence_id": f"ev-benchmark-{case.case_id}",
            "language": "en",
            "provenance": {
                "method": "human_provided",
                "created_by": "atomic-ci synthetic benchmark",
                "created_at": "2026-08-16",
            },
            "segments": list(case.segments),
        }
    )


def benchmark_parent(case: BenchmarkCase) -> dict[str, Any]:
    return {
        "id": f"ev-benchmark-{case.case_id}",
        "record_type": "evidence",
        "status": "published",
        "review_state": "published",
        "evidence_role": "publication_artifact",
        "source_type": "industry_podcast",
        "title": f"Synthetic benchmark: {case.title}",
        "source_name": "Synthetic Benchmark Publisher",
        "source_url": "https://example.invalid/atomic-ci-benchmark",
        "captured_date": "2026-08-16",
        "summary": "Synthetic, company-neutral extraction benchmark.",
        "submitted_by": "benchmark",
    }


def deterministic_window_sample(total_windows: int, sample_count: int) -> list[int]:
    if total_windows < 1 or sample_count < 1:
        raise ValueError("window and sample counts must be positive")
    if sample_count >= total_windows:
        return list(range(total_windows))
    if sample_count == 1:
        return [0]
    return [round(index * (total_windows - 1) / (sample_count - 1)) for index in range(sample_count)]


def candidate_preview(
    transcript: TranscriptArtifact,
    candidate: dict[str, Any],
    *,
    provider: OpenAICompatibleExtractionProvider,
) -> dict[str, Any]:
    indexes = candidate["segment_indexes"]
    selected = [transcript.segments[index] for index in indexes]
    excerpt = "\n".join(
        f"{segment.speaker_label}: {segment.text}" if segment.speaker_label else segment.text
        for segment in selected
    )
    return {
        "normalized_statement": candidate["normalized_statement"],
        "transcript_excerpt": excerpt,
        "start_seconds": selected[0].start_seconds,
        "end_seconds": selected[-1].end_seconds,
        "segment_indexes": list(indexes),
        "entity_ids": list(candidate.get("entity_ids", [])),
        "geography_ids": list(candidate.get("geography_ids", [])),
        "berry_ids": list(candidate.get("berry_ids", [])),
        "provider": provider.provenance["provider"],
        "model": provider.provenance["model"],
        "prompt_version": provider.provenance["prompt_version"],
    }


def score_case(case: BenchmarkCase, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    statements = [" ".join(candidate["normalized_statement"].casefold().split()) for candidate in candidates]
    expectations = case.expectations
    checks: dict[str, Any] = {}
    expected_count = expectations["candidate_count"]
    checks["candidate_count"] = expected_count["min"] <= len(candidates) <= expected_count["max"]
    phrase_checks = []
    for group in expectations.get("required_phrase_groups", []):
        phrase_checks.append(any(all(term.casefold() in statement for term in group) for statement in statements))
    checks["required_phrase_groups"] = phrase_checks
    qualifier_checks = {
        qualifier: any(re.search(rf"(?<!\w){re.escape(qualifier.casefold())}(?!\w)", statement) for statement in statements)
        for qualifier in expectations.get("required_qualifiers", [])
    }
    checks["required_qualifiers"] = qualifier_checks
    prohibited_hits = {
        phrase: [index for index, statement in enumerate(statements) if phrase.casefold() in statement]
        for phrase in expectations.get("prohibited_phrases", [])
    }
    checks["prohibited_inference_hits"] = {key: value for key, value in prohibited_hits.items() if value}
    support_checks = []
    candidate_spans = [set(candidate["segment_indexes"]) for candidate in candidates]
    for required in expectations.get("required_segment_sets", []):
        support_checks.append(any(set(required).issubset(span) for span in candidate_spans))
    checks["required_segment_sets"] = support_checks
    expected_atomic = expectations.get("expected_atomic_claims")
    checks["atomic_separation"] = expected_atomic is None or len(candidates) >= expected_atomic
    link_count = sum(
        len(candidate.get(field_name, []))
        for candidate in candidates
        for field_name in ("entity_ids", "geography_ids", "berry_ids")
    )
    max_links = expectations.get("max_link_count")
    checks["link_count"] = {"actual": link_count, "maximum": max_links, "passed": max_links is None or link_count <= max_links}
    booleans = [checks["candidate_count"], *phrase_checks, *qualifier_checks.values(), *support_checks]
    booleans.extend([not checks["prohibited_inference_hits"], checks["atomic_separation"], checks["link_count"]["passed"]])
    return {
        "passed": all(booleans),
        "checks_passed": sum(bool(value) for value in booleans),
        "checks_total": len(booleans),
        "checks": checks,
        "summary_like_candidates": sum(len(statement) > 300 for statement in statements),
        "excess_candidate_count": max(0, len(candidates) - expected_count["max"]),
    }


def run_benchmark(
    provider: OpenAICompatibleExtractionProvider,
    benchmark: ExtractionBenchmark,
) -> dict[str, Any]:
    case_reports: list[dict[str, Any]] = []
    totals = {
        "model_calls": 0,
        "candidates_before_validation": 0,
        "invalid_candidates": 0,
        "duplicates_removed": 0,
        "candidates_after_validation": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "elapsed_seconds": 0.0,
    }
    token_usage_seen = False
    for case in benchmark.cases:
        transcript = benchmark_transcript(case)
        error: str | None = None
        try:
            candidates = provider.extract(ExtractionRequest(transcript=transcript, parent_evidence=benchmark_parent(case)))
        except ExtractionProviderError as exc:
            candidates = []
            error = str(exc)
        metrics = provider.last_run_report.as_dict() if provider.last_run_report else {}
        for field_name in totals:
            value = metrics.get(field_name)
            if value is not None:
                totals[field_name] += value
                if field_name.endswith("tokens"):
                    token_usage_seen = True
        score = score_case(case, candidates)
        case_reports.append(
            {
                "case_id": case.case_id,
                "title": case.title,
                "category": case.expectations.get("category"),
                "error": error,
                "provider_metrics": metrics,
                "raw_model_outputs": list(getattr(provider, "last_raw_outputs", [])),
                "score": score,
                "candidates": [candidate_preview(transcript, candidate, provider=provider) for candidate in candidates],
            }
        )
    successful_responses = sum(report["error"] is None for report in case_reports)
    passed_cases = sum(report["score"]["passed"] and report["error"] is None for report in case_reports)
    checks_passed = sum(report["score"]["checks_passed"] for report in case_reports)
    checks_total = sum(report["score"]["checks_total"] for report in case_reports)
    candidate_responses = totals["candidates_before_validation"]
    zero_cases = [
        report
        for case, report in zip(benchmark.cases, case_reports)
        if case.expectations["candidate_count"]["max"] == 0
    ]
    count_correct = sum(report["score"]["checks"]["candidate_count"] for report in case_reports)
    qualifier_results = [
        passed
        for report in case_reports
        for passed in report["score"]["checks"].get("required_qualifiers", {}).values()
    ]
    for field_name in ("input_tokens", "output_tokens", "total_tokens"):
        if not token_usage_seen:
            totals[field_name] = None
    totals["elapsed_seconds"] = round(totals["elapsed_seconds"], 3)
    return {
        "mode": "benchmark",
        "provider": provider.provenance["provider"],
        "model": provider.provenance["model"],
        "prompt_version": provider.provenance["prompt_version"],
        "benchmark": {"id": benchmark.benchmark_id, "version": benchmark.version, "case_count": len(benchmark.cases)},
        "configuration": public_configuration(provider),
        "metrics": {
            **totals,
            "structurally_valid_response_rate": successful_responses / len(case_reports),
            "candidate_schema_validity_rate": (
                (candidate_responses - totals["invalid_candidates"]) / candidate_responses
                if candidate_responses
                else 1.0
            ),
            "cases_passed": passed_cases,
            "cases_total": len(case_reports),
            "expected_candidate_count_cases_correct": count_correct,
            "zero_candidate_cases_correct": sum(
                not report["candidates"] and report["error"] is None for report in zero_cases
            ),
            "zero_candidate_cases_total": len(zero_cases),
            "qualifier_checks_passed": sum(qualifier_results),
            "qualifier_checks_total": len(qualifier_results),
            "deterministic_checks_passed": checks_passed,
            "deterministic_checks_total": checks_total,
            "failure_modes": _failure_modes(case_reports),
        },
        "cases": case_reports,
    }


def run_transcript_preview(
    provider: OpenAICompatibleExtractionProvider,
    transcript: TranscriptArtifact,
    parent_evidence: dict[str, Any],
    *,
    sample_windows: int | None = None,
) -> dict[str, Any]:
    windows = build_transcript_windows(
        transcript,
        max_chars=provider.config.window_chars,
        overlap_segments=provider.config.overlap_segments,
    )
    sampled = deterministic_window_sample(len(windows), sample_windows) if sample_windows else list(range(len(windows)))
    error: str | None = None
    try:
        candidates = provider.extract_windows(
            ExtractionRequest(transcript=transcript, parent_evidence=parent_evidence),
            set(sampled),
        )
    except ExtractionProviderError as exc:
        candidates = []
        error = str(exc)
    return {
        "mode": "transcript_sample" if sample_windows else "transcript_full_preview",
        "provider": provider.provenance["provider"],
        "model": provider.provenance["model"],
        "prompt_version": provider.provenance["prompt_version"],
        "configuration": public_configuration(provider),
        "transcript": {
            "transcript_id": transcript.transcript_id,
            "transcript_sha256": transcript.content_sha256(),
            "segment_count": len(transcript.segments),
            "total_windows": len(windows),
            "sampled_window_numbers": sampled,
        },
        "error": error,
        "metrics": provider.last_run_report.as_dict() if provider.last_run_report else {},
        "raw_model_outputs": list(getattr(provider, "last_raw_outputs", [])),
        "candidates": [candidate_preview(transcript, candidate, provider=provider) for candidate in candidates],
    }


def public_configuration(provider: OpenAICompatibleExtractionProvider) -> dict[str, Any]:
    config = provider.config
    return {
        "window_chars": config.window_chars,
        "overlap_segments": config.overlap_segments,
        "temperature": config.temperature,
        "max_candidates_per_window": config.max_candidates_per_window,
        "max_total_candidates": config.max_total_candidates,
        "response_format": config.response_format,
    }


def _failure_modes(case_reports: list[dict[str, Any]]) -> dict[str, int]:
    provider_errors = [
        str(error)
        for report in case_reports
        for error in report.get("provider_metrics", {}).get("errors", [])
    ]
    scores = [report["score"] for report in case_reports]
    return {
        "invalid_json_responses": sum("invalid JSON" in error for error in provider_errors),
        "schema_violations": sum(
            int(report.get("provider_metrics", {}).get("invalid_candidates", 0)) for report in case_reports
        ),
        "unsupported_id_rejections": sum("unsupported repository ID" in error for error in provider_errors),
        "invalid_span_rejections": sum("segment_indexes" in error for error in provider_errors),
        "model_supplied_timestamp_rejections": sum(
            "unexpected fields" in error and any(field in error for field in ("start_seconds", "end_seconds", "timestamp"))
            for error in provider_errors
        ),
        "refusals": sum("refused" in error for error in provider_errors),
        "truncations": sum("truncated" in error for error in provider_errors),
        "repetitive_candidates_removed": sum(
            int(report.get("provider_metrics", {}).get("duplicates_removed", 0)) for report in case_reports
        ),
        "qualifier_checks_failed": sum(
            not passed
            for score in scores
            for passed in score["checks"].get("required_qualifiers", {}).values()
        ),
        "prohibited_inference_violations": sum(
            len(indexes)
            for score in scores
            for indexes in score["checks"].get("prohibited_inference_hits", {}).values()
        ),
        "summary_like_candidates": sum(score["summary_like_candidates"] for score in scores),
        "excess_candidates": sum(score["excess_candidate_count"] for score in scores),
        "clear_claim_misses": sum(
            not passed
            for score in scores
            for passed in score["checks"].get("required_phrase_groups", [])
        ),
    }


def probe_provider(provider: OpenAICompatibleExtractionProvider) -> dict[str, Any]:
    transcript = TranscriptArtifact.from_dict(
        {
            "transcript_id": "evaluation-probe",
            "parent_evidence_id": "ev-evaluation-probe",
            "language": "en",
            "provenance": {"method": "human_provided", "created_by": "evaluation probe", "created_at": "2026-08-16"},
            "segments": [{"text": "Hello. This is a compatibility probe with no intelligence claim.", "start_seconds": 0, "end_seconds": 1}],
        }
    )
    error: str | None = None
    try:
        provider.extract(
            ExtractionRequest(
                transcript=transcript,
                parent_evidence={"id": "ev-evaluation-probe", "title": "Safe extraction compatibility probe"},
            )
        )
    except ExtractionProviderError as exc:
        error = str(exc)
    if provider.config.api_key and error:
        error = error.replace(provider.config.api_key, "[REDACTED]")
    reachable = error is None or not any(marker in error for marker in ("transport failure", "timed out"))
    if error is None:
        failure_category = None
    elif "timed out" in error:
        failure_category = "timeout"
    elif any(code in error for code in ("(401)", "(403)")):
        failure_category = "authentication_or_authorization"
    elif "(404)" in error:
        failure_category = "endpoint_or_model_unavailable"
    elif "HTTP failure" in error:
        failure_category = "http_failure"
    elif "transport failure" in error:
        failure_category = "transport_failure"
    else:
        failure_category = "structured_response_incompatible"
    metrics = provider.last_run_report.as_dict() if provider.last_run_report else {}
    return {
        "endpoint_configured": bool(provider.config.base_url),
        "model_configured": bool(provider.config.model),
        "endpoint_reachable": reachable,
        "compatible_response_received": error is None,
        "structured_output_capability": error is None,
        "response_format": provider.config.response_format,
        "provider": provider.provenance["provider"],
        "model": provider.provenance["model"],
        "returned_model_identities": sorted(set(provider.last_response_models)),
        "prompt_version": PROMPT_VERSION,
        "latency_seconds": metrics.get("elapsed_seconds"),
        "raw_model_outputs": list(getattr(provider, "last_raw_outputs", [])),
        "failure_category": failure_category,
        "error": error,
    }


def write_evaluation_artifact(
    report: dict[str, Any],
    inbox_dir: Path,
    *,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> Path:
    instant = now().astimezone(timezone.utc)
    timestamp = instant.strftime("%Y%m%dT%H%M%S%fZ")
    identity = json.dumps(
        [
            report.get("mode"),
            report.get("model"),
            report.get("configuration"),
            report.get("benchmark"),
            report.get("transcript"),
        ],
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:10]
    run_id = f"evaluation-{timestamp}-{digest}"
    artifact = {
        "evaluation_schema_version": EVALUATION_SCHEMA_VERSION,
        "run_id": run_id,
        "created_at": instant.isoformat(),
        **report,
    }
    folder = inbox_dir / "evaluations"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{run_id}.json"
    path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
