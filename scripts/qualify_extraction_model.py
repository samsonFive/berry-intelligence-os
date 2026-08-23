"""Probe, evaluate, explicitly approve, or revoke an extraction model."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.composition import get_repositories
from app.repositories.paths import DEFAULT_DATA_DIR, SCHEMAS_DIR
from app.services.ai_extraction import EXTRACTION_VERSION, PROMPT_VERSION, OpenAICompatibleExtractionConfig, OpenAICompatibleExtractionProvider
from app.services.atomic_qualification import GoldSetContractError, load_atomic_gold_set
from app.services.ai_gateway.credentials import MissingCredentialError
from app.services.ai_gateway.perplexity_extraction import (
    PerplexityAgentExtractionProvider,
    PerplexityRouterExtractionProvider,
    agent_config_from_environment,
    router_config_from_environment,
)
from app.services.extraction_evaluation import load_benchmark, probe_provider
from app.services.model_qualification import (
    DEFAULT_REAL_PARENT_ID,
    QualificationError,
    approve_qualification,
    file_sha256,
    load_cached_transcript,
    provider_qualification_configuration,
    revoke_qualification,
    run_gold_candidate_comparison,
    run_qualification_evaluation,
)


DEFAULT_BENCHMARK = ROOT / "benchmarks" / "atomic-ci-v1.json"
DEFAULT_GOLD_SET = ROOT / "benchmarks" / "atomic-evidence-gold-set-v1.json"
PROVIDER_CHOICES = ("openai-compatible", "perplexity-agent", "perplexity-router")


def _provider_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--provider", choices=PROVIDER_CHOICES, default="openai-compatible")
    parser.add_argument("--endpoint", "--extract-base-url", dest="extract_base_url")
    parser.add_argument("--model", "--extract-model", dest="extract_model")
    parser.add_argument("--extract-api-key-env", default="BIOS_EXTRACT_API_KEY")
    parser.add_argument("--extract-timeout", type=float)
    parser.add_argument("--extract-window-chars", type=int)
    parser.add_argument("--extract-overlap-segments", type=int)
    parser.add_argument("--extract-temperature", type=float)
    parser.add_argument("--extract-max-candidates", type=int)
    parser.add_argument("--extract-max-total-candidates", type=int)
    parser.add_argument("--extract-response-format", choices=("json_schema", "json_object"))
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Human-gated qualification for the existing atomic transcript extractor"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    probe = commands.add_parser("probe", help="Run one non-destructive structured-output capability probe")
    _provider_options(probe)

    evaluate = commands.add_parser("evaluate", help="Run probe, 12-case benchmark, and bounded real transcript sample")
    _provider_options(evaluate)
    evaluate.add_argument("--benchmark-file", type=Path, default=DEFAULT_BENCHMARK)
    evaluate.add_argument(
        "--gold-set-file", type=Path, default=DEFAULT_GOLD_SET,
        help="Claude's Atomic Evidence Gold Set V1; required for a V2 qualification run",
    )
    evaluate.add_argument("--inbox-dir", type=Path, default=ROOT / "inbox")
    evaluate.add_argument("--output-dir", type=Path)
    evaluate.add_argument("--transcript-file", type=Path)
    evaluate.add_argument("--transcript-item")
    evaluate.add_argument("--parent-evidence", default=DEFAULT_REAL_PARENT_ID)
    evaluate.add_argument("--sample-windows", type=int, default=8)

    compare = commands.add_parser(
        "compare-gold",
        help="Run and persist a private Gold-only candidate comparison (never qualification-eligible)",
    )
    _provider_options(compare)
    compare.add_argument("--gold-set-file", type=Path, default=DEFAULT_GOLD_SET)
    compare.add_argument("--inbox-dir", type=Path, default=ROOT / "inbox")
    compare.add_argument("--output-dir", type=Path)

    approve = commands.add_parser("approve", help="Explicitly approve one complete, integrity-checked evaluation")
    approve.add_argument("--evaluation", type=Path, required=True)
    approve.add_argument("--operator", required=True)
    approve.add_argument("--provider", choices=PROVIDER_CHOICES, default="openai-compatible")
    approve.add_argument("--model", required=True)
    approve.add_argument("--prompt-version", default=PROMPT_VERSION)
    approve.add_argument("--extraction-version", default=EXTRACTION_VERSION)
    approve.add_argument("--marker", type=Path)

    revoke = commands.add_parser("revoke", help="Move a qualification marker aside so the runner cannot use it")
    revoke.add_argument("--marker", type=Path, required=True)
    return parser


def _configured_provider(
    args: argparse.Namespace, repositories: object
) -> OpenAICompatibleExtractionProvider | PerplexityAgentExtractionProvider | PerplexityRouterExtractionProvider:
    if args.provider in ("perplexity-agent", "perplexity-router"):
        model = args.extract_model or os.environ.get("BIOS_PERPLEXITY_MODEL")
        if not model:
            raise QualificationError("missing configuration: BIOS_PERPLEXITY_MODEL or --model")
        build_config = agent_config_from_environment if args.provider == "perplexity-agent" else router_config_from_environment
        config = build_config(
            base_url=args.extract_base_url,
            model=model,
            timeout_seconds=args.extract_timeout,
            window_chars=args.extract_window_chars,
            overlap_segments=args.extract_overlap_segments,
            temperature=args.extract_temperature,
            max_candidates_per_window=args.extract_max_candidates,
            max_total_candidates=args.extract_max_total_candidates,
            response_format=args.extract_response_format,
        )
        provider_cls = (
            PerplexityAgentExtractionProvider if args.provider == "perplexity-agent" else PerplexityRouterExtractionProvider
        )
        return provider_cls(config=config, repositories=repositories)

    base_url = args.extract_base_url or os.environ.get("BIOS_EXTRACT_BASE_URL")
    model = args.extract_model or os.environ.get("BIOS_EXTRACT_MODEL")
    missing = []
    if not base_url:
        missing.append("BIOS_EXTRACT_BASE_URL or --endpoint")
    if not model:
        missing.append("BIOS_EXTRACT_MODEL or --model")
    if missing:
        raise QualificationError("missing configuration: " + ", ".join(missing))
    config = OpenAICompatibleExtractionConfig.from_environment(
        api_key_env=args.extract_api_key_env,
        base_url=base_url,
        model=model,
        timeout_seconds=args.extract_timeout,
        window_chars=args.extract_window_chars,
        overlap_segments=args.extract_overlap_segments,
        temperature=args.extract_temperature,
        max_candidates_per_window=args.extract_max_candidates,
        max_total_candidates=args.extract_max_total_candidates,
        response_format=args.extract_response_format,
    )
    return OpenAICompatibleExtractionProvider(config=config, repositories=repositories)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "approve":
            marker = approve_qualification(
                args.evaluation,
                operator=args.operator,
                marker_path=args.marker,
                expected_provider=args.provider,
                expected_model=args.model,
                expected_prompt_version=args.prompt_version,
                expected_extraction_version=args.extraction_version,
            )
            print(json.dumps({"state": "qualified", "marker": str(marker)}, indent=2))
            return 0
        if args.command == "revoke":
            revoked = revoke_qualification(args.marker)
            print(json.dumps({"state": "revoked", "marker": str(revoked)}, indent=2))
            return 0

        repositories = get_repositories(args.data_dir, SCHEMAS_DIR)
        provider = _configured_provider(args, repositories)
        if args.command == "probe":
            report = probe_provider(provider)
            report["created_at"] = datetime.now(timezone.utc).isoformat()
            report["endpoint_identity"] = provider_qualification_configuration(provider)["endpoint_identity"]
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 0 if report["compatible_response_received"] else 1

        if args.command == "compare-gold":
            gold_set = load_atomic_gold_set(args.gold_set_file)
            output_dir = args.output_dir or args.inbox_dir / "qualifications" / "candidate-comparisons"
            artifact_path = run_gold_candidate_comparison(
                provider=provider,
                gold_set=gold_set,
                gold_set_sha256=file_sha256(args.gold_set_file),
                output_dir=output_dir,
            )
            artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
            report = artifact["atomic_gold_set"]
            print(json.dumps({
                "state": "gold_candidate_comparison_complete",
                "artifact": str(artifact_path),
                "qualification_eligible": False,
                "gold_set_passed": report["passed"],
                "gold_set_metrics": report["metrics"],
                "critical_overreach": report["critical_overreach"],
                "failure_rate": report["failure_rate"],
                "next_action": "Compare the private artifact; run the full evaluate workflow before any explicit approval.",
            }, indent=2, ensure_ascii=False))
            return 0 if report["passed"] else 1

        if args.sample_windows < 1:
            raise QualificationError("--sample-windows must be positive")
        parent = repositories.evidence.get(args.parent_evidence)
        if not parent or parent.get("evidence_role") != "publication_artifact":
            raise QualificationError(f"trusted publication artifact not found: {args.parent_evidence}")
        transcript, transcript_path = load_cached_transcript(
            args.inbox_dir,
            parent_evidence_id=args.parent_evidence,
            item_id=args.transcript_item,
            transcript_path=args.transcript_file,
        )
        benchmark = load_benchmark(args.benchmark_file)
        gold_set = load_atomic_gold_set(args.gold_set_file)
        output_dir = args.output_dir or args.inbox_dir / "qualifications"
        artifact_path, packet_path = run_qualification_evaluation(
            provider=provider,
            benchmark=benchmark,
            transcript=transcript,
            parent_evidence=parent,
            repositories=repositories,
            output_dir=output_dir,
            sample_windows=args.sample_windows,
            benchmark_sha256=file_sha256(args.benchmark_file),
            gold_set=gold_set,
            gold_set_sha256=file_sha256(args.gold_set_file),
            transcript_cache_path=transcript_path,
        )
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        print(json.dumps({
            "state": "evaluation_complete" if artifact["complete"] else "evaluation_incomplete",
            "evaluation": str(artifact_path),
            "review_packet": str(packet_path),
            "stage_completion": artifact["stage_completion"],
            "automated_warnings": artifact["automated_warnings"],
            "gold_set_passed": artifact["atomic_gold_set"]["passed"],
            "gold_set_metrics": artifact["atomic_gold_set"].get("metrics", {}),
            "next_action": (
                "Human-review the packet, then run the explicit approve command."
                if artifact["complete"]
                else "Correct incomplete stages and create a new evaluation; this run cannot be approved."
            ),
        }, indent=2, ensure_ascii=False))
        return 0 if artifact["complete"] else 1
    except (QualificationError, GoldSetContractError, MissingCredentialError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"state": "error", "error": str(exc)}, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
