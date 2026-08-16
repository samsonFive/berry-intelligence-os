"""Report what recurring collection is waiting on and the next safe action."""

from __future__ import annotations

import argparse
from datetime import timedelta
import json
import os
from pathlib import Path
import sys

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.composition import get_repositories
from app.repositories.paths import DEFAULT_DATA_DIR, SCHEMAS_DIR
from app.services.ai_extraction import PROMPT_VERSION, OpenAICompatibleExtractionConfig, OpenAICompatibleExtractionProvider
from app.services.collection_runner import OperationalStateStore, resolve_extraction_gate
from app.services.collection_status import CollectionStatusService
from app.services.extraction_evaluation import public_configuration
from app.services.model_qualification import file_sha256, qualification_configuration_fingerprint


def _enabled(name: str) -> bool:
    return os.environ.get(name, "").strip().casefold() in {"1", "true", "yes", "on"}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print the stable machine-readable report")
    parser.add_argument("--source", help="Limit item/source detail and readiness to one configured Source")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--schemas-dir", type=Path, default=SCHEMAS_DIR)
    parser.add_argument("--inbox-dir", type=Path, default=ROOT / "inbox")
    parser.add_argument("--operations-dir", type=Path, help="Defaults to <inbox>/operations")
    parser.add_argument("--retry-limit", type=int, default=3)
    parser.add_argument("--lock-stale-seconds", type=int, default=21600)

    parser.add_argument("--enable-extraction", action="store_true", help="Evaluate readiness with recurring extraction enabled")
    parser.add_argument("--qualification-file", type=Path)
    parser.add_argument("--extract-base-url")
    parser.add_argument("--extract-model")
    parser.add_argument("--extract-api-key-env", default="BIOS_EXTRACT_API_KEY")
    parser.add_argument("--extract-timeout", type=float)
    parser.add_argument("--extract-window-chars", type=int)
    parser.add_argument("--extract-overlap-segments", type=int)
    parser.add_argument("--extract-temperature", type=float)
    parser.add_argument("--extract-max-candidates", type=int)
    parser.add_argument("--extract-max-total-candidates", type=int)
    parser.add_argument("--extract-response-format", choices=("json_schema", "json_object"))
    return parser


def _extraction_state(args: argparse.Namespace) -> tuple[object, list[str]]:
    base_url = args.extract_base_url or os.environ.get("BIOS_EXTRACT_BASE_URL")
    model = args.extract_model or os.environ.get("BIOS_EXTRACT_MODEL")
    enabled = args.enable_extraction or _enabled("BIOS_COLLECTION_ENABLE_EXTRACTION")
    qualification_path = args.qualification_file
    if qualification_path is None and os.environ.get("BIOS_COLLECTION_QUALIFICATION_FILE"):
        qualification_path = Path(os.environ["BIOS_COLLECTION_QUALIFICATION_FILE"])
    fingerprint = None
    if base_url and model:
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
        provider = OpenAICompatibleExtractionProvider(config=config, repositories=None)
        fingerprint = qualification_configuration_fingerprint(
            provider="openai-compatible",
            model=model,
            base_url=base_url,
            prompt_version=PROMPT_VERSION,
            generation=public_configuration(provider),
        )
    benchmark_sha = file_sha256(ROOT / "benchmarks" / "atomic-ci-v1.json")
    gate = resolve_extraction_gate(
        enabled=enabled,
        provider="openai-compatible",
        model=model,
        base_url=base_url,
        prompt_version=PROMPT_VERSION,
        qualification_path=qualification_path,
        configuration_fingerprint=fingerprint,
        benchmark_sha256=benchmark_sha,
    )
    diagnostic = resolve_extraction_gate(
        enabled=True,
        provider="openai-compatible",
        model=model,
        base_url=base_url,
        prompt_version=PROMPT_VERSION,
        qualification_path=qualification_path,
        configuration_fingerprint=fingerprint,
        benchmark_sha256=benchmark_sha,
    )
    blockers: list[str] = []
    if not enabled:
        blockers.append("extraction is disabled")
    if not base_url or not model:
        blockers.append("extraction provider/model configuration is incomplete")
    elif qualification_path is None:
        blockers.append("no qualification marker is configured")
    elif not diagnostic.runnable:
        blockers.append(diagnostic.reason)
    return gate, blockers


def _human(report: dict) -> str:
    counts = report["counts"]
    readiness = report["pilot_readiness"]
    lines = [
        "COLLECTION OPERATIONS STATUS",
        f"Next action: {report['recommended_next_action']}",
        "",
        f"Sources configured: {report['sources_configured']}",
        f"Sources discoverable: {report['sources_discoverable']}",
        f"Runner lock: {report['lock']['state']}",
        "",
        "Work:",
        f"  ready to advance: {counts['ready_to_advance']}",
        f"  publication review: {counts['human_publication_review_required']}",
        f"  extraction ready: {counts['extraction_ready']}",
        f"  extraction blocked: {counts['extraction_blocked']}",
        f"  atomic review: {counts['human_atomic_evidence_review_required']} items / {counts['pending_atomic_proposals']} proposals",
        f"  retryable failure: {counts['retryable_failure']}",
        f"  operator intervention: {counts['operator_intervention_required']}",
        f"  completed/no action: {counts['completed_no_action']}",
        "",
        f"Collection-only pilot: {readiness['collection_only']['state']}",
    ]
    lines.extend(f"  - {reason}" for reason in readiness["collection_only"]["blockers"])
    lines.append(f"Extraction-enabled pilot: {readiness['extraction_enabled']['state']}")
    lines.extend(f"  - {reason}" for reason in readiness["extraction_enabled"]["blockers"])
    if report["sources"]:
        lines.extend(["", "Per Source:"])
        for source in report["sources"]:
            lines.append(
                f"  {source['name']} [{source['adapter'] or 'not discoverable'}]: "
                f"items={source['discovered_items']}, publication_review={source['pending_publication_review']}, "
                f"atomic_review={source['pending_atomic_review']}, failures="
                f"{source['retryable_failures'] + source['operator_intervention']} -> {source['recommended_next_action']}"
            )
    if report["problems"]:
        lines.extend(["", "Operator problems:"])
        lines.extend(f"  - {problem['identity']}: {problem['message']}" for problem in report["problems"])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.retry_limit < 0 or args.lock_stale_seconds < 0:
        parser.error("retry and lock-stale values must be non-negative")
    try:
        repositories = get_repositories(args.data_dir, args.schemas_dir)
        schema = json.loads((args.schemas_dir / "evidence.schema.json").read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        gate, blockers = _extraction_state(args)
        service = CollectionStatusService(
            repositories=repositories,
            inbox_dir=args.inbox_dir,
            operations=OperationalStateStore(args.operations_dir or args.inbox_dir / "operations"),
            evidence_errors=lambda record: [error.message for error in validator.iter_errors(record)],
            extraction_gate=gate,
            extraction_blockers=blockers,
            retry_limit=args.retry_limit,
            lock_stale_after=timedelta(seconds=args.lock_stale_seconds),
        )
        report = service.build(source_id=args.source).as_dict()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"state": "error", "error": str(exc)}, indent=2))
        return 2
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) if args.json else _human(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
