"""Probe, benchmark, or preview the existing AI transcript extractor."""

from __future__ import annotations

import argparse
from datetime import date
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import main as app_main
from app.composition import get_repositories
from app.repositories.paths import DEFAULT_DATA_DIR, SCHEMAS_DIR
from app.services.ai_extraction import (
    ExtractionProviderError,
    OpenAICompatibleExtractionConfig,
    OpenAICompatibleExtractionProvider,
)
from app.services.extraction_evaluation import (
    EvaluationContractError,
    load_benchmark,
    probe_provider,
    run_benchmark,
    run_transcript_preview,
    write_evaluation_artifact,
)
from app.services.transcript_evidence import TranscriptArtifact, TranscriptEvidenceExtractionService


DEFAULT_BENCHMARK = ROOT / "benchmarks" / "atomic-ci-v1.json"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate the existing provider-neutral transcript extractor")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--probe", action="store_true", help="Check configured endpoint compatibility safely")
    mode.add_argument("--benchmark", action="store_true", help="Run the curated synthetic benchmark")
    mode.add_argument("--transcript", type=Path, help="Evaluate a normalized TranscriptArtifact JSON file")
    parser.add_argument("--benchmark-file", type=Path, default=DEFAULT_BENCHMARK)
    parser.add_argument("--sample-windows", type=int, help="Deterministically sample this many transcript windows")
    parser.add_argument("--full", action="store_true", help="Evaluate every transcript window")
    parser.add_argument("--persist-proposals", action="store_true", help="Explicitly use the existing Evidence proposal service")
    parser.add_argument("--parent-evidence", help="Override/bind the transcript parent Evidence ID")
    parser.add_argument("--extract-base-url", help="OpenAI-compatible base URL (or BIOS_EXTRACT_BASE_URL)")
    parser.add_argument("--model", "--extract-model", dest="extract_model", help="Model name (or BIOS_EXTRACT_MODEL)")
    parser.add_argument("--extract-api-key-env", default="BIOS_EXTRACT_API_KEY")
    parser.add_argument("--extract-timeout", type=float)
    parser.add_argument("--extract-window-chars", type=int)
    parser.add_argument("--extract-overlap-segments", type=int)
    parser.add_argument("--extract-temperature", type=float)
    parser.add_argument("--extract-max-candidates", type=int)
    parser.add_argument("--extract-max-total-candidates", type=int)
    parser.add_argument("--extract-response-format", choices=("json_schema", "json_object"))
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--inbox-dir", type=Path, default=ROOT / "inbox")
    return parser


def _config(args: argparse.Namespace) -> OpenAICompatibleExtractionConfig:
    return OpenAICompatibleExtractionConfig.from_environment(
        api_key_env=args.extract_api_key_env,
        base_url=args.extract_base_url,
        model=args.extract_model,
        timeout_seconds=args.extract_timeout,
        window_chars=args.extract_window_chars,
        overlap_segments=args.extract_overlap_segments,
        temperature=args.extract_temperature,
        max_candidates_per_window=args.extract_max_candidates,
        max_total_candidates=args.extract_max_total_candidates,
        response_format=args.extract_response_format,
    )


def _missing_configuration(args: argparse.Namespace) -> dict | None:
    base_url = args.extract_base_url or os.environ.get("BIOS_EXTRACT_BASE_URL")
    model = args.extract_model or os.environ.get("BIOS_EXTRACT_MODEL")
    if base_url and model:
        return None
    missing = []
    if not base_url:
        missing.append("BIOS_EXTRACT_BASE_URL or --extract-base-url")
    if not model:
        missing.append("BIOS_EXTRACT_MODEL or --model")
    return {
        "endpoint_configured": bool(base_url),
        "model_configured": bool(model),
        "endpoint_reachable": False,
        "compatible_response_received": False,
        "structured_output_capability": False,
        "latency_seconds": None,
        "error": "Missing configuration: " + ", ".join(missing),
    }


def _load_transcript(path: Path, parent_override: str | None) -> TranscriptArtifact:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvaluationContractError(f"could not read transcript: {exc}") from exc
    if not isinstance(payload, dict):
        raise EvaluationContractError("transcript file must contain a JSON object")
    payload = dict(payload)
    if parent_override:
        payload["parent_evidence_id"] = parent_override
    return TranscriptArtifact.from_dict(payload)


def main() -> int:
    parser = _parser()
    args = parser.parse_args()
    if args.transcript and (args.sample_windows is None) == (not args.full):
        parser.error("--transcript requires exactly one of --sample-windows or --full")
    if not args.transcript and (args.sample_windows is not None or args.full or args.parent_evidence):
        parser.error("transcript controls require --transcript")
    if args.sample_windows is not None and args.sample_windows < 1:
        parser.error("--sample-windows must be positive")
    if args.persist_proposals and (not args.transcript or not args.full):
        parser.error("--persist-proposals requires --transcript and --full")

    missing = _missing_configuration(args)
    if missing:
        print(json.dumps(missing, indent=2))
        return 1

    try:
        repositories = get_repositories(args.data_dir, SCHEMAS_DIR)
        provider = OpenAICompatibleExtractionProvider(config=_config(args), repositories=repositories)
        if args.probe:
            report = probe_provider(provider)
            print(json.dumps(report, indent=2))
            return 0 if report["compatible_response_received"] else 1
        if args.benchmark:
            report = run_benchmark(provider, load_benchmark(args.benchmark_file))
        else:
            transcript = _load_transcript(args.transcript, args.parent_evidence)
            parent = repositories.evidence.get(transcript.parent_evidence_id)
            if parent is None:
                raise EvaluationContractError(
                    f"parent Evidence not found: {transcript.parent_evidence_id}; use --parent-evidence to bind it"
                )
            if args.persist_proposals:
                validator = app_main.get_validator("evidence.schema.json")
                service = TranscriptEvidenceExtractionService(
                    repositories=repositories,
                    inbox_dir=args.inbox_dir,
                    evidence_errors=lambda record: [error.message for error in validator.iter_errors(record)],
                    provider=provider,
                    today=date.today,
                )
                result = service.run(transcript)
                report = {
                    "mode": "production_proposals",
                    "provider": provider.provenance["provider"],
                    "model": provider.provenance["model"],
                    "prompt_version": provider.provenance["prompt_version"],
                    "transcript": {
                        "transcript_id": transcript.transcript_id,
                        "transcript_sha256": transcript.content_sha256(),
                        "segment_count": len(transcript.segments),
                    },
                    "result": {
                        "candidates_found": result.candidates_found,
                        "accepted_proposal_ids": result.accepted,
                        "duplicate_proposal_ids": result.duplicates,
                        "invalid": result.invalid,
                        "provider_metrics": result.provider_metrics,
                        "provider_errors": result.provider_errors,
                    },
                }
            else:
                report = run_transcript_preview(
                    provider,
                    transcript,
                    parent,
                    sample_windows=args.sample_windows,
                )
        artifact_path = write_evaluation_artifact(report, args.inbox_dir)
        output = {**report, "evaluation_artifact": str(artifact_path)}
        print(json.dumps(output, indent=2, ensure_ascii=False))
        benchmark_unavailable = (
            report.get("mode") == "benchmark"
            and report.get("metrics", {}).get("structurally_valid_response_rate") == 0
        )
        return 1 if report.get("error") or benchmark_unavailable else 0
    except (EvaluationContractError, ExtractionProviderError, ValueError, OSError) as exc:
        print(json.dumps({"state": "error", "error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
