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
from app.repositories.paths import SCHEMAS_DIR
from app.runtime_config import env_path, resolve_data_dir, resolve_inbox_dir
from app.services.runtime_backup import backup_health
from app.services.ai_extraction import EXTRACTION_VERSION, PROMPT_VERSION, OpenAICompatibleExtractionConfig, OpenAICompatibleExtractionProvider
from app.services.collection_runner import OperationalStateStore, resolve_extraction_gate
from app.services.collection_status import CollectionStatusService
from app.services.extraction_evaluation import public_configuration
from app.services.model_qualification import file_sha256, qualification_configuration_fingerprint
from app.services.pipeline_health import build_pipeline_health
from app.services.analyst_queue import load_state as load_analyst_queue_state
from app.services.review_capacity import build_review_capacity_report, load_json_objects
from app.services.review_events import load_review_events
from app.services.source_cadence import load_cadence_policy


def _enabled(name: str) -> bool:
    return os.environ.get(name, "").strip().casefold() in {"1", "true", "yes", "on"}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print the stable machine-readable report")
    parser.add_argument(
        "--audit-items",
        action="store_true",
        help="Explicit deep per-item audit; default operator status reads persisted run/review state",
    )
    parser.add_argument("--source", help="Limit item/source detail and readiness to one configured Source")
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--schemas-dir", type=Path, default=SCHEMAS_DIR)
    parser.add_argument("--inbox-dir", type=Path, default=None)
    parser.add_argument("--operations-dir", type=Path, help="Defaults to <inbox>/operations")
    parser.add_argument("--backup-dir", type=Path, default=None, help="Verified runtime backup directory (or BIOS_BACKUP_DIR)")
    parser.add_argument("--retry-limit", type=int, default=3)
    parser.add_argument("--lock-stale-seconds", type=int, default=21600)

    parser.add_argument("--enable-extraction", action="store_true", help="Evaluate readiness with recurring extraction enabled")
    parser.add_argument("--qualification-file", type=Path)
    parser.add_argument("--qualification-gold-set-file", type=Path)
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
    gold_set_path = args.qualification_gold_set_file
    if gold_set_path is None:
        configured_gold_set = os.environ.get("BIOS_COLLECTION_QUALIFICATION_GOLD_SET_FILE")
        gold_set_path = Path(configured_gold_set) if configured_gold_set else ROOT / "benchmarks" / "atomic-evidence-gold-set-v1.json"
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
    gold_set_sha = file_sha256(gold_set_path) if gold_set_path.exists() else None
    gate = resolve_extraction_gate(
        enabled=enabled,
        provider="openai-compatible",
        model=model,
        base_url=base_url,
        prompt_version=PROMPT_VERSION,
        qualification_path=qualification_path,
        configuration_fingerprint=fingerprint,
        benchmark_sha256=benchmark_sha,
        gold_set_sha256=gold_set_sha,
        extraction_version=EXTRACTION_VERSION,
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
        gold_set_sha256=gold_set_sha,
        extraction_version=EXTRACTION_VERSION,
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
        f"Source cadence: due={report.get('source_schedule', {}).get('due', 0)}, "
        f"not_due={report.get('source_schedule', {}).get('not_due', 0)}, "
        f"blocked={report.get('source_schedule', {}).get('blocked', 0)}",
        f"Runner lock: {report['lock']['state']}",
        f"Persistent runtime configured: {report.get('runtime', {}).get('persistent_runtime_configured', False)}",
        f"Storage free: {report.get('runtime', {}).get('free_percent', 0)}%",
        f"Backup health: {report.get('backup', {}).get('state', 'UNCONFIGURED')}",
        "",
        "Work:",
        f"  ready to advance: {counts['ready_to_advance']}",
        f"  discovered: {counts.get('discovered', 0)}",
        f"  relevant: {counts.get('relevant', 0)}",
        f"  skipped irrelevant: {counts.get('skipped_irrelevant', 0)}",
        f"  transcript ready: {counts.get('transcript_ready', 0)}",
        f"  enrichment ready: {counts.get('enrichment_ready', 0)}",
        f"  publication review: {counts['human_publication_review_required']}",
        f"  review pressure: {report.get('review_capacity', {}).get('backlog_level', 'unknown')}",
        f"  median / oldest queue age: {report.get('review_capacity', {}).get('median_queue_age_days', 'n/a')} / {report.get('review_capacity', {}).get('oldest_queue_age_days', 'n/a')} days",
        f"  simulated deferral if critical: {report.get('review_capacity', {}).get('simulated_would_defer', 'n/a')} (automatic throttling OFF)",
        f"  backlog / drafts created last run: {report.get('review_backlog', {}).get('backlog_to_last_run_created_ratio') or 'n/a'}",
        f"  trusted publications: {counts.get('trusted_publication', 0)}",
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
                f"{source['retryable_failures'] + source['operator_intervention']}, "
                f"due={source.get('schedule', {}).get('due')}, "
                f"next_due={source.get('schedule', {}).get('next_due') or 'operator/manual'} "
                f"-> {source['recommended_next_action']}"
            )
    if report.get("pipelines"):
        lines.extend(["", "Pipelines:"])
        for pipeline in report["pipelines"]:
            mode = "scheduled" if pipeline["scheduled"] else "manual"
            failure = "failing" if pipeline["failure_state"] else "ok"
            lines.append(
                f"  {pipeline['pipeline']}: {mode}, enabled={pipeline['enabled']}, "
                f"outcome={pipeline.get('outcome') or 'never'}, "
                f"last_attempt={pipeline['last_attempt'] or 'never'}, "
                f"last_success={pipeline['last_success'] or 'never'}, "
                f"next_due={pipeline['next_due'] or 'manual'}, "
                f"duration={pipeline.get('duration_seconds') if pipeline.get('duration_seconds') is not None else 'n/a'}s, "
                f"failures={pipeline.get('failure_count', 0)}, "
                f"drafts={pipeline.get('drafts_created', 0)}, {failure}"
            )
    if report["problems"]:
        lines.extend(["", "Operator problems:"])
        lines.extend(f"  - {problem['identity']}: {problem['message']}" for problem in report["problems"])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    args.data_dir = args.data_dir or resolve_data_dir(ROOT)
    args.inbox_dir = args.inbox_dir or resolve_inbox_dir(ROOT)
    if args.retry_limit < 0 or args.lock_stale_seconds < 0:
        parser.error("retry and lock-stale values must be non-negative")
    try:
        repositories = get_repositories(args.data_dir, args.schemas_dir)
        schema = json.loads((args.schemas_dir / "evidence.schema.json").read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        gate, blockers = _extraction_state(args)
        cadence_policy_path = args.data_dir / "configuration" / "source_collection_cadence.json"
        cadence_policy = load_cadence_policy(cadence_policy_path) if cadence_policy_path.is_file() else {}
        service = CollectionStatusService(
            repositories=repositories,
            inbox_dir=args.inbox_dir,
            operations=OperationalStateStore(args.operations_dir or args.inbox_dir / "operations"),
            evidence_errors=lambda record: [error.message for error in validator.iter_errors(record)],
            extraction_gate=gate,
            extraction_blockers=blockers,
            retry_limit=args.retry_limit,
            lock_stale_after=timedelta(seconds=args.lock_stale_seconds),
            cadence_policy=cadence_policy,
        )
        report = service.build(
            source_id=args.source,
            persisted_only=not args.audit_items and args.source is None,
        ).as_dict()
        pipeline_config = args.data_dir / "configuration" / "collection_pipelines.json"
        if not pipeline_config.is_file():
            pipeline_config = ROOT / "data" / "configuration" / "collection_pipelines.json"
        report.update(build_pipeline_health(
            data_dir=args.data_dir,
            inbox_dir=args.inbox_dir,
            config_path=pipeline_config,
        ))
        capacity = build_review_capacity_report(
            drafts=load_json_objects(args.inbox_dir / "evidence"),
            sources=repositories.sources.list(),
            entities=repositories.entities.list(),
            trusted=repositories.evidence.list(),
            run_records=[
                *load_json_objects(args.inbox_dir / "operations" / "runs"),
                *load_json_objects(args.inbox_dir / "operations" / "pipelines", recursive=True),
            ],
            analyst_state=load_analyst_queue_state(args.inbox_dir),
            review_events=load_review_events(args.inbox_dir),
        )
        derived = capacity["derived_operational_metrics"]
        simulation = capacity["simulated_policy_effect"]
        report["review_capacity"] = {
            "backlog_level": derived["backlog_level"],
            "thresholds": capacity["policy"]["thresholds"],
            "median_queue_age_days": derived["median_queue_age_days"],
            "oldest_queue_age_days": (derived["oldest_open_item"] or {}).get("queue_age_days"),
            "new_since_last_run": derived["new_since_last_run"],
            "net_backlog_growth": derived["arrival"]["net_backlog_growth_from_first_snapshot"],
            "simulated_would_defer": simulation["would_defer"],
            "automatic_throttling_enabled": False,
            "rates_measurable": capacity["observed_review_events"]["rates_measurable"],
            "total_observed_review_decisions": capacity["observed_review_events"]["total_observed_decisions"],
            "last_review_decision_at": capacity["observed_review_events"]["last_decision_at"],
            "review_decisions_by_action": capacity["observed_review_events"]["counts_by_action"],
            "warning": (
                None if derived["backlog_level"] == "normal"
                else f"{derived['backlog_level']} review pressure; simulation only, no automatic deferral"
            ),
        }
        backup_dir = args.backup_dir or env_path("BIOS_BACKUP_DIR")
        report["backup"] = backup_health(backup_dir) if backup_dir else {
            "state": "UNCONFIGURED",
            "archives": 0,
            "verified": False,
        }
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"state": "error", "error": str(exc)}, indent=2))
        return 2
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) if args.json else _human(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
