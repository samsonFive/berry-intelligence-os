"""Human-gated qualification for semantic transcript extraction models.

This module composes the existing provider and evaluation harness.  It never
writes Evidence and cannot qualify a model without a separate operator action.
Runtime artifacts belong under the gitignored ``inbox/qualifications`` tree.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

from app.services.ai_extraction import EXTRACTION_VERSION, PROMPT_VERSION, OpenAICompatibleExtractionProvider
from app.services.atomic_qualification import AtomicGoldSet, run_gold_set_benchmark
from app.services.extraction_evaluation import (
    ExtractionBenchmark,
    probe_provider,
    public_configuration,
    run_benchmark,
    run_transcript_preview,
)
from app.services.media_transcription import load_transcript_artifact, transcripts_dir
from app.services.transcript_evidence import TranscriptArtifact


QUALIFICATION_WORKFLOW_VERSION = "extraction-qualification-v2"
QUALIFICATION_ARTIFACT_SCHEMA_VERSION = 2
QUALIFICATION_MARKER_SCHEMA_VERSION = 2
GOLD_COMPARISON_SCHEMA_VERSION = 1
DEFAULT_REAL_PARENT_ID = "ev-lucentlands-scaling-blueberry-industry-2025"
UTC = timezone.utc


class QualificationError(ValueError):
    """The qualification workflow cannot safely continue."""


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_endpoint_identity(base_url: str) -> dict[str, str]:
    """Return a stable endpoint identity without userinfo, query, or fragment."""

    parsed = urlsplit(base_url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise QualificationError("extraction endpoint must be an http(s) URL with a host")
    try:
        port = f":{parsed.port}" if parsed.port is not None else ""
    except ValueError as exc:
        raise QualificationError("extraction endpoint contains an invalid port") from exc
    path = parsed.path.rstrip("/") or "/"
    display = f"{parsed.scheme}://{parsed.hostname}{port}{path}"
    return {
        "display": display,
        "sha256": hashlib.sha256(display.encode("utf-8")).hexdigest(),
    }


def _default_endpoint_family(provider: str) -> str:
    return {
        "openai-compatible": "openai-chat-completions",
        "perplexity-router": "perplexity-router-chat-completions",
        "perplexity-agent": "perplexity-agent-responses",
    }.get(provider, provider)


def qualification_configuration(
    *,
    provider: str,
    model: str,
    base_url: str,
    prompt_version: str,
    generation: dict[str, Any],
    endpoint_family: str | None = None,
    extraction_version: str = EXTRACTION_VERSION,
) -> dict[str, Any]:
    endpoint = safe_endpoint_identity(base_url)
    return {
        "provider": provider,
        "model": model,
        "endpoint_family": endpoint_family or _default_endpoint_family(provider),
        "prompt_version": prompt_version,
        "extraction_version": extraction_version,
        "endpoint_identity": endpoint,
        "generation": generation,
    }


def qualification_configuration_fingerprint(
    *,
    provider: str,
    model: str,
    base_url: str,
    prompt_version: str,
    generation: dict[str, Any],
    endpoint_family: str | None = None,
    extraction_version: str = EXTRACTION_VERSION,
) -> str:
    configuration = qualification_configuration(
        provider=provider,
        model=model,
        base_url=base_url,
        prompt_version=prompt_version,
        generation=generation,
        endpoint_family=endpoint_family,
        extraction_version=extraction_version,
    )
    return hashlib.sha256(_canonical_json(configuration).encode("utf-8")).hexdigest()


def provider_qualification_configuration(provider: OpenAICompatibleExtractionProvider) -> dict[str, Any]:
    return qualification_configuration(
        provider=provider.provenance["provider"],
        model=provider.provenance["model"],
        base_url=provider.config.base_url,
        prompt_version=provider.provenance["prompt_version"],
        generation=public_configuration(provider),
        endpoint_family=provider.provenance.get("endpoint_family", provider.provenance["provider"]),
        extraction_version=provider.provenance.get("extraction_version", EXTRACTION_VERSION),
    )


def run_gold_candidate_comparison(
    *,
    provider: OpenAICompatibleExtractionProvider,
    gold_set: AtomicGoldSet,
    gold_set_sha256: str,
    output_dir: Path,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> Path:
    """Persist a private Gold-only comparison that can never be approved.

    This path exists for model selection when the corpus has no real trusted
    transcript.  It deliberately does not emit the qualification artifact
    schema or a review packet/marker; full approval still requires every stage
    in ``run_qualification_evaluation``.
    """

    created = now().astimezone(UTC)
    configuration = provider_qualification_configuration(provider)
    fingerprint = hashlib.sha256(_canonical_json(configuration).encode("utf-8")).hexdigest()
    report = run_gold_set_benchmark(provider, gold_set)
    instant = created.strftime("%Y%m%dT%H%M%S%fZ")
    run_id = "gold-comparison-" + instant + "-" + hashlib.sha256(
        _canonical_json([fingerprint, gold_set.gold_set_id, gold_set.version, gold_set_sha256, instant]).encode()
    ).hexdigest()[:10]
    artifact = {
        "gold_candidate_comparison_schema_version": GOLD_COMPARISON_SCHEMA_VERSION,
        "run_id": run_id,
        "created_at": created.isoformat(),
        "qualification_eligible": False,
        "qualification_blocker": "Gold-only comparison omits the required synthetic benchmark and real trusted transcript stages.",
        "provider": provider.provenance["provider"],
        "model": provider.provenance["model"],
        "prompt_version": provider.provenance["prompt_version"],
        "extraction_version": provider.provenance.get("extraction_version", EXTRACTION_VERSION),
        "configuration": configuration,
        "configuration_fingerprint": fingerprint,
        "gold_set_identity": {
            "id": gold_set.gold_set_id,
            "version": gold_set.version,
            "sha256": gold_set_sha256,
            "case_count": len(gold_set.cases),
            "source_document": gold_set.source_document,
            "source_document_sha256": gold_set.source_document_sha256,
        },
        "atomic_gold_set": report,
        "trust_notice": "Comparison output is private, untrusted decision support. It cannot create a qualification marker or enable extraction.",
    }
    run_dir = output_dir / run_id
    if run_dir.exists():
        raise QualificationError(f"Gold comparison directory already exists: {run_dir}")
    run_dir.mkdir(parents=True)
    artifact_path = run_dir / "comparison.json"
    artifact_path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    digest = file_sha256(artifact_path)
    (run_dir / "comparison.sha256").write_text(f"{digest}  comparison.json\n", encoding="utf-8")
    return artifact_path


def load_cached_transcript(
    inbox_dir: Path,
    *,
    parent_evidence_id: str = DEFAULT_REAL_PARENT_ID,
    item_id: str | None = None,
    transcript_path: Path | None = None,
) -> tuple[TranscriptArtifact, Path]:
    """Load an existing normalized transcript only; never acquire or transcribe."""

    candidates: list[tuple[dict[str, Any], Path]] = []
    if transcript_path is not None:
        try:
            payload = json.loads(transcript_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise QualificationError(f"could not read cached transcript: {exc}") from exc
        candidates.append((payload, transcript_path))
    elif item_id:
        payload = load_transcript_artifact(inbox_dir, item_id)
        if payload is not None:
            candidates.append((payload, transcripts_dir(inbox_dir) / f"{item_id}.json"))
    else:
        folder = transcripts_dir(inbox_dir)
        for path in sorted(folder.glob("*.json")) if folder.exists() else []:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(payload, dict) and payload.get("parent_evidence_id") == parent_evidence_id:
                candidates.append((payload, path))
    if not candidates:
        detail = f"item {item_id!r}" if item_id else f"parent {parent_evidence_id!r}"
        raise QualificationError(
            f"no cached normalized transcript found for {detail}; qualification never retranscribes media"
        )
    if len(candidates) > 1:
        raise QualificationError("multiple cached transcripts match; select one with --transcript-file or --transcript-item")
    payload, path = candidates[0]
    if not isinstance(payload, dict):
        raise QualificationError("cached transcript must contain a JSON object")
    payload = dict(payload)
    embedded_parent = payload.get("parent_evidence_id")
    if embedded_parent is None:
        payload["parent_evidence_id"] = parent_evidence_id
    elif embedded_parent != parent_evidence_id:
        raise QualificationError(
            f"cached transcript parent mismatch: {embedded_parent!r} != {parent_evidence_id!r}"
        )
    try:
        return TranscriptArtifact.from_dict(payload), path
    except ValueError as exc:
        raise QualificationError(f"cached transcript is not a valid TranscriptArtifact: {exc}") from exc


def _link_names(repositories: Any, field_name: str, values: list[str]) -> list[dict[str, str | None]]:
    output = []
    for record_id in values:
        record = repositories.entities.get(record_id)
        output.append({"id": record_id, "name": record.get("name") if record else None})
    return output


def _enrich_real_candidates(report: dict[str, Any], transcript: TranscriptArtifact, repositories: Any) -> None:
    for candidate in report.get("candidates", []):
        indexes = candidate.get("segment_indexes", [])
        segments = [transcript.segments[index] for index in indexes if 0 <= index < len(transcript.segments)]
        speakers = {segment.speaker_label for segment in segments if segment.speaker_label}
        candidate["speaker_label"] = next(iter(speakers)) if len(speakers) == 1 else None
        candidate["links"] = {
            field: _link_names(repositories, field, candidate.get(field, []))
            for field in ("entity_ids", "geography_ids", "berry_ids")
        }


def _benchmark_complete(report: dict[str, Any], expected_cases: int) -> bool:
    cases = report.get("cases")
    return (
        isinstance(cases, list)
        and len(cases) == expected_cases
        and all(case.get("error") is None for case in cases)
        and report.get("metrics", {}).get("structurally_valid_response_rate") == 1.0
    )


def _sample_complete(report: dict[str, Any]) -> bool:
    metrics = report.get("metrics", {})
    return (
        report.get("error") is None
        and not metrics.get("errors")
        and metrics.get("invalid_candidates", 0) == 0
        and metrics.get("model_calls", 0) > 0
    )


def _warnings(benchmark_report: dict[str, Any], sample_report: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    metrics = benchmark_report.get("metrics", {})
    if metrics.get("cases_passed") != metrics.get("cases_total"):
        warnings.append("One or more synthetic cases failed deterministic semantic checks.")
    modes = metrics.get("failure_modes", {})
    if modes.get("prohibited_inference_violations"):
        warnings.append("Synthetic benchmark detected prohibited inference output.")
    if modes.get("qualifier_checks_failed"):
        warnings.append("Synthetic benchmark detected qualifier-preservation failures.")
    if sample_report.get("metrics", {}).get("duplicates_removed"):
        warnings.append("Real transcript sampling produced overlapping duplicate candidates that were removed.")
    return warnings


def run_qualification_evaluation(
    *,
    provider: OpenAICompatibleExtractionProvider,
    benchmark: ExtractionBenchmark,
    transcript: TranscriptArtifact,
    parent_evidence: dict[str, Any],
    repositories: Any,
    output_dir: Path,
    sample_windows: int = 8,
    benchmark_sha256: str,
    gold_set: AtomicGoldSet,
    gold_set_sha256: str,
    transcript_cache_path: Path | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> tuple[Path, Path]:
    """Run all qualification stages and write an immutable JSON/Markdown packet."""

    if sample_windows < 1:
        raise QualificationError("sample_windows must be positive")
    created = now().astimezone(UTC)
    configuration = provider_qualification_configuration(provider)
    configuration_fingerprint = hashlib.sha256(_canonical_json(configuration).encode("utf-8")).hexdigest()
    probe = probe_provider(provider)
    probe["probed_at"] = created.isoformat()
    benchmark_report: dict[str, Any]
    gold_set_report: dict[str, Any]
    sample_report: dict[str, Any]
    if probe.get("compatible_response_received"):
        benchmark_report = run_benchmark(provider, benchmark)
        gold_set_report = run_gold_set_benchmark(provider, gold_set)
        sample_report = run_transcript_preview(
            provider,
            transcript,
            parent_evidence,
            sample_windows=sample_windows,
        )
        _enrich_real_candidates(sample_report, transcript, repositories)
    else:
        benchmark_report = {"mode": "benchmark", "error": "endpoint probe failed", "cases": [], "metrics": {}}
        gold_set_report = {"mode": "gold_set", "error": "endpoint probe failed", "passed": False, "cases": [], "metrics": {}}
        sample_report = {"mode": "transcript_sample", "error": "endpoint probe failed", "candidates": [], "metrics": {}}
    stages = {
        "probe": bool(probe.get("compatible_response_received") and probe.get("structured_output_capability")),
        "synthetic_benchmark": _benchmark_complete(benchmark_report, len(benchmark.cases)),
        "atomic_gold_set": bool(gold_set_report.get("passed")),
        "real_transcript_sample": _sample_complete(sample_report),
    }
    complete = all(stages.values())
    instant = created.strftime("%Y%m%dT%H%M%S%fZ")
    run_basis = [
        configuration_fingerprint, benchmark.benchmark_id, benchmark.version,
        benchmark_sha256, gold_set.gold_set_id, gold_set.version,
        gold_set_sha256, transcript.content_sha256(), instant,
    ]
    run_id = "qualification-" + instant + "-" + hashlib.sha256(_canonical_json(run_basis).encode()).hexdigest()[:10]
    artifact = {
        "qualification_artifact_schema_version": QUALIFICATION_ARTIFACT_SCHEMA_VERSION,
        "workflow_version": QUALIFICATION_WORKFLOW_VERSION,
        "run_id": run_id,
        "created_at": created.isoformat(),
        "complete": complete,
        "stage_completion": stages,
        "provider": configuration["provider"],
        "model": configuration["model"],
        "prompt_version": configuration["prompt_version"],
        "extraction_version": configuration["extraction_version"],
        "configuration": configuration,
        "configuration_fingerprint": configuration_fingerprint,
        "benchmark_identity": {
            "id": benchmark.benchmark_id,
            "version": benchmark.version,
            "sha256": benchmark_sha256,
            "case_count": len(benchmark.cases),
        },
        "gold_set_identity": {
            "id": gold_set.gold_set_id,
            "version": gold_set.version,
            "sha256": gold_set_sha256,
            "case_count": len(gold_set.cases),
            "contract_version": "atomic-evidence-gold-set-v1",
            "source_document": gold_set.source_document,
            "source_document_sha256": gold_set.source_document_sha256,
        },
        "real_sample_identity": {
            "parent_evidence_id": transcript.parent_evidence_id,
            "transcript_id": transcript.transcript_id,
            "transcript_sha256": transcript.content_sha256(),
            "segment_count": len(transcript.segments),
            "cache_path_recorded": transcript_cache_path.name if transcript_cache_path else None,
            "sampling_strategy": "evenly spaced deterministic transcript-window positions",
            "requested_window_count": sample_windows,
            "semantic_stratification": False,
            "limitation": "Position sampling is reproducible but does not guarantee subject-category coverage.",
        },
        "probe": {**probe, "endpoint_identity": configuration["endpoint_identity"]},
        "synthetic_benchmark": benchmark_report,
        "atomic_gold_set": gold_set_report,
        "real_transcript_sample": sample_report,
        "automated_warnings": _warnings(benchmark_report, sample_report),
        "trust_notice": "Evaluation output is untrusted decision support. Only explicit operator approval creates a qualification marker; Evidence review remains separate.",
    }
    run_dir = output_dir / run_id
    if run_dir.exists():
        raise QualificationError(f"qualification run directory already exists: {run_dir}")
    run_dir.mkdir(parents=True)
    artifact_path = run_dir / "evaluation.json"
    artifact_path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    digest = file_sha256(artifact_path)
    (run_dir / "evaluation.sha256").write_text(f"{digest}  evaluation.json\n", encoding="utf-8")
    packet_path = run_dir / "review.md"
    packet_path.write_text(render_review_packet(artifact, digest), encoding="utf-8")
    return artifact_path, packet_path


def _format_seconds(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return "unknown"
    seconds = max(0, round(float(value)))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def render_review_packet(artifact: dict[str, Any], artifact_sha256: str) -> str:
    benchmark = artifact.get("synthetic_benchmark", {})
    metrics = benchmark.get("metrics", {})
    probe = artifact.get("probe", {})
    real = artifact.get("real_transcript_sample", {})
    lines = [
        "# Extraction Model Qualification Review",
        "",
        "> This packet supports a human qualification decision. It does not approve or trust Evidence.",
        "",
        "## Identity",
        "",
        f"- Run: `{artifact['run_id']}`",
        f"- Provider/model: `{artifact['provider']}` / `{artifact['model']}`",
        f"- Prompt: `{artifact['prompt_version']}`",
        f"- Extraction: `{artifact['extraction_version']}`",
        f"- Endpoint family: `{artifact['configuration']['endpoint_family']}`",
        f"- Endpoint: `{probe.get('endpoint_identity', {}).get('display', 'unknown')}`",
        f"- Configuration fingerprint: `{artifact['configuration_fingerprint']}`",
        f"- Evaluation SHA-256: `{artifact_sha256}`",
        f"- Complete: **{'yes' if artifact['complete'] else 'no'}**",
        "",
        "## Endpoint probe",
        "",
        f"- Compatible structured response: {probe.get('compatible_response_received', False)}",
        f"- Latency: {probe.get('latency_seconds')} seconds",
        f"- Error: {probe.get('error') or 'none'}",
        "",
        "## Synthetic benchmark",
        "",
        f"- Cases passed: {metrics.get('cases_passed', 0)} / {metrics.get('cases_total', 0)}",
        f"- Deterministic checks: {metrics.get('deterministic_checks_passed', 0)} / {metrics.get('deterministic_checks_total', 0)}",
        f"- Invalid candidates: {metrics.get('invalid_candidates', 0)}",
        f"- Duplicates removed: {metrics.get('duplicates_removed', 0)}",
        f"- Failure modes: `{json.dumps(metrics.get('failure_modes', {}), sort_keys=True)}`",
        "",
    ]
    for case in benchmark.get("cases", []):
        lines.extend([
            f"### {case.get('title', case.get('case_id', 'Case'))}",
            "",
            f"- Result: {'pass' if case.get('score', {}).get('passed') and not case.get('error') else 'review/fail'}",
            f"- Error: {case.get('error') or 'none'}",
            f"- Category: {case.get('category') or 'not specified'}",
            "",
        ])
        for candidate in case.get("candidates", []):
            lines.append(f"- `{candidate.get('normalized_statement', '')}` — {candidate.get('transcript_excerpt', '')}")
        lines.append("")
    gold = artifact.get("atomic_gold_set", {})
    lines.extend([
        "## Atomic Evidence Gold Set",
        "",
        f"- Identity: `{artifact.get('gold_set_identity', {}).get('id')}` v{artifact.get('gold_set_identity', {}).get('version')}",
        f"- Human benchmark SHA-256: `{artifact.get('gold_set_identity', {}).get('source_document_sha256')}`",
        f"- Passed deterministic thresholds: **{'yes' if gold.get('passed') else 'no'}**",
        f"- Metrics: `{json.dumps(gold.get('metrics', {}), sort_keys=True)}`",
        f"- Thresholds: `{json.dumps(gold.get('thresholds', {}), sort_keys=True)}`",
        f"- Critical overreach detected: {gold.get('critical_overreach', False)}",
        f"- Failure rate: {gold.get('failure_rate')}",
        "- Raw model responses and normalized proposals are retained in `evaluation.json`; this internal packet does not publish them.",
        "",
    ])
    lines.extend([
        "## Real transcript sample",
        "",
        f"- Transcript: `{artifact.get('real_sample_identity', {}).get('transcript_id')}`",
        f"- Segments: {artifact.get('real_sample_identity', {}).get('segment_count')}",
        f"- Windows sampled: {real.get('transcript', {}).get('sampled_window_numbers', [])}",
        f"- Sampling: {artifact.get('real_sample_identity', {}).get('sampling_strategy')}",
        f"- Limitation: {artifact.get('real_sample_identity', {}).get('limitation')}",
        "- Human rubric for every candidate: grounding, atomicity, qualifier fidelity, CI relevance, normalization, and linking.",
        "",
    ])
    for index, candidate in enumerate(real.get("candidates", []), start=1):
        links = [entry for values in candidate.get("links", {}).values() for entry in values]
        link_text = ", ".join(f"{entry.get('name') or 'unresolved'} (`{entry['id']}`)" for entry in links) or "none"
        lines.extend([
            f"### Candidate {index}",
            "",
            f"- Proposed statement: **{candidate.get('normalized_statement', '')}**",
            f"- Supporting excerpt: “{candidate.get('transcript_excerpt', '')}”",
            f"- Timestamp: {_format_seconds(candidate.get('start_seconds'))}–{_format_seconds(candidate.get('end_seconds'))}",
            f"- Speaker label: {candidate.get('speaker_label') or 'not available'}",
            f"- Links: {link_text}",
            f"- Segment indexes: {candidate.get('segment_indexes', [])}",
            f"- Provider/model/prompt: `{candidate.get('provider')}` / `{candidate.get('model')}` / `{candidate.get('prompt_version')}`",
            f"- Transcript/hash: `{artifact.get('real_sample_identity', {}).get('transcript_id')}` / `{artifact.get('real_sample_identity', {}).get('transcript_sha256')}`",
            "- Human rubric: grounding ☐  atomicity ☐  qualifier fidelity ☐  CI relevance ☐  normalization ☐  linking ☐",
            "",
        ])
    lines.extend([
        "## Operator decision",
        "",
        "Automated results never qualify a model. After reviewing this packet, use the explicit `approve` command with your operator identity.",
        "",
    ])
    return "\n".join(lines)


def _load_evaluation(path: Path) -> tuple[dict[str, Any], str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise QualificationError(f"could not read evaluation artifact: {exc}") from exc
    if not isinstance(payload, dict):
        raise QualificationError("evaluation artifact must be a JSON object")
    checksum_path = path.with_name("evaluation.sha256")
    try:
        expected = checksum_path.read_text(encoding="utf-8").split()[0]
    except (OSError, IndexError) as exc:
        raise QualificationError("evaluation checksum manifest is missing or malformed") from exc
    actual = file_sha256(path)
    if expected != actual:
        raise QualificationError("evaluation artifact integrity check failed; it is stale or has been modified")
    return payload, actual


def approve_qualification(
    evaluation_path: Path,
    *,
    operator: str,
    marker_path: Path | None = None,
    expected_provider: str | None = None,
    expected_model: str | None = None,
    expected_prompt_version: str = PROMPT_VERSION,
    expected_extraction_version: str = EXTRACTION_VERSION,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> Path:
    """Issue a runner-compatible marker after an explicit human decision."""

    operator = operator.strip()
    if not operator:
        raise QualificationError("operator identity is required")
    artifact, artifact_sha256 = _load_evaluation(evaluation_path)
    required = {
        "qualification_artifact_schema_version": QUALIFICATION_ARTIFACT_SCHEMA_VERSION,
        "workflow_version": QUALIFICATION_WORKFLOW_VERSION,
        "prompt_version": expected_prompt_version,
        "extraction_version": expected_extraction_version,
    }
    for field, expected in required.items():
        if artifact.get(field) != expected:
            raise QualificationError(f"evaluation {field} mismatch: expected {expected!r}")
    if artifact.get("complete") is not True or not all(artifact.get("stage_completion", {}).values()):
        raise QualificationError("incomplete qualification evaluation cannot be approved")
    if expected_provider and artifact.get("provider") != expected_provider:
        raise QualificationError("evaluation provider does not match the requested provider")
    if expected_model and artifact.get("model") != expected_model:
        raise QualificationError("evaluation model does not match the requested model")
    fingerprint = artifact.get("configuration_fingerprint")
    if not isinstance(fingerprint, str) or len(fingerprint) != 64:
        raise QualificationError("evaluation configuration fingerprint is missing")
    benchmark = artifact.get("benchmark_identity")
    if not isinstance(benchmark, dict) or not all(benchmark.get(key) for key in ("id", "version", "sha256")):
        raise QualificationError("evaluation benchmark identity is incomplete")
    gold_set = artifact.get("gold_set_identity")
    if not isinstance(gold_set, dict) or not all(gold_set.get(key) for key in ("id", "version", "sha256")):
        raise QualificationError("evaluation Gold Set identity is incomplete")
    if artifact.get("atomic_gold_set", {}).get("passed") is not True:
        raise QualificationError("evaluation did not pass Atomic Evidence Gold Set thresholds")
    marker_path = marker_path or evaluation_path.with_name("qualification-marker.json")
    if marker_path.exists():
        raise QualificationError(f"qualification marker already exists: {marker_path}")
    relative_artifact = os.path.relpath(evaluation_path.resolve(), marker_path.parent.resolve())
    marker = {
        "qualification_marker_schema_version": QUALIFICATION_MARKER_SCHEMA_VERSION,
        "workflow_version": QUALIFICATION_WORKFLOW_VERSION,
        "provider": artifact["provider"],
        "model": artifact["model"],
        "prompt_version": artifact["prompt_version"],
        "extraction_version": artifact["extraction_version"],
        "configuration_fingerprint": fingerprint,
        "endpoint_identity_sha256": artifact["configuration"]["endpoint_identity"]["sha256"],
        "benchmark_id": benchmark["id"],
        "benchmark_version": benchmark["version"],
        "benchmark_sha256": benchmark["sha256"],
        "gold_set_id": gold_set["id"],
        "gold_set_version": gold_set["version"],
        "gold_set_sha256": gold_set["sha256"],
        "evaluation_run_id": artifact["run_id"],
        "evaluation_artifact": relative_artifact,
        "evaluation_sha256": artifact_sha256,
        "operator_qualified": True,
        "qualified_by": operator,
        "qualified_at": now().astimezone(UTC).isoformat(),
        "trust_scope": "permission to generate untrusted atomic Evidence proposals only",
    }
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.write_text(json.dumps(marker, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return marker_path


def revoke_qualification(marker_path: Path) -> Path:
    """Revoke locally by moving the marker aside; no trusted data is touched."""

    if not marker_path.exists():
        raise QualificationError(f"qualification marker not found: {marker_path}")
    revoked = marker_path.with_name(marker_path.name + ".revoked")
    if revoked.exists():
        raise QualificationError(f"revocation target already exists: {revoked}")
    marker_path.replace(revoked)
    return revoked
