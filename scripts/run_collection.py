"""Run one bounded, human-gated recurring collection cycle.

Normal runs perform discovery and may acquire/transcribe media before stopping
at human publication review. ``--dry-run`` is an offline local plan: it makes
no network calls and writes nothing. Real extraction is disabled unless it is
explicitly enabled, configured, and matched by an operator qualification file.
"""

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
from app.runtime_config import resolve_data_dir, resolve_inbox_dir
from app.services.ai_extraction import (
    PROMPT_VERSION,
    OpenAICompatibleExtractionConfig,
    OpenAICompatibleExtractionProvider,
)
from app.services.ai_gateway.untrusted_complete import maybe_untrusted_completer
from app.services.article_refresh import process_discovered_article
from app.services.collection_runner import (
    CollectionLockedError,
    CollectionRunner,
    OperationalStateStore,
    resolve_extraction_gate,
)
from app.services.media_discovery import DiscoveryError, discover_source
from app.services.media_orchestration import (
    MediaOrchestrationService,
    MediaTranscriptionAdapter,
    OrchestrationResult,
    ParentResolution,
)
from app.services.media_transcription import (
    AVAILABLE_WHISPER_MODELS,
    DEFAULT_WHISPER_MODEL,
    load_transcript_artifact,
    transcript_cache_matches_request,
)
from app.services.extraction_evaluation import public_configuration
from app.services.model_qualification import file_sha256, qualification_configuration_fingerprint
from app.services.transcript_evidence import TranscriptEvidenceExtractionService


def _environment_enabled(name: str) -> bool:
    return os.environ.get(name, "").strip().casefold() in {"1", "true", "yes", "on"}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--all", action="store_true", help="Run every Source with usable discovery configuration")
    scope.add_argument("--source", help="Run one configured Source by ID")
    parser.add_argument(
        "--dry-run",
        "--offline-plan",
        dest="dry_run",
        action="store_true",
        help="Offline, no-write plan using configured Sources and already-staged items; discovery is not called",
    )
    parser.add_argument("--skip-transcription", action="store_true", help="Reuse valid caches but do not acquire/transcribe missing media")
    parser.add_argument(
        "--allow-historical-backfill",
        action="store_true",
        help=(
            "Opt into a spoken-media source's full back-catalog on its first-ever discovery run "
            "(default: a bounded recent window only -- see app.services.media_discovery.classify_initial_backlog) "
            "and into drafting already-staged items flagged historical_backlog by a prior run."
        ),
    )
    parser.add_argument("--max-transcriptions", type=int, help="Maximum uncached transcription attempts in this run")
    parser.add_argument("--max-items", type=int, help="Maximum staged items processed in deterministic order")
    parser.add_argument("--model", choices=AVAILABLE_WHISPER_MODELS, default=DEFAULT_WHISPER_MODEL)
    parser.add_argument("--device", choices=("cpu", "cuda"))
    parser.add_argument("--language", help="Requested transcript language")
    parser.add_argument("--created-by", default="recurring-collection-runner")

    parser.add_argument("--enable-extraction", action="store_true", help="Opt into recurring model extraction; still requires exact qualification")
    parser.add_argument("--qualification-file", type=Path, help="Operator qualification JSON for exact provider/model/prompt version")
    parser.add_argument("--extract-base-url", help="OpenAI-compatible base URL (or BIOS_EXTRACT_BASE_URL)")
    parser.add_argument("--extract-model", help="Extraction model (or BIOS_EXTRACT_MODEL)")
    parser.add_argument("--extract-api-key-env", default="BIOS_EXTRACT_API_KEY")
    parser.add_argument("--extract-timeout", type=float)
    parser.add_argument("--extract-window-chars", type=int)
    parser.add_argument("--extract-overlap-segments", type=int)
    parser.add_argument("--extract-temperature", type=float)
    parser.add_argument("--extract-max-candidates", type=int)
    parser.add_argument("--extract-max-total-candidates", type=int)
    parser.add_argument("--extract-response-format", choices=("json_schema", "json_object"))

    parser.add_argument("--retry-limit", type=int, default=3)
    parser.add_argument("--retry-operator-items", action="store_true", help="Re-evaluate terminal/operator items after the underlying issue was corrected")
    parser.add_argument("--retry-backoff-seconds", type=int, default=1800)
    parser.add_argument("--lock-stale-seconds", type=int, default=21600)
    parser.add_argument("--json", action="store_true", help="Print the complete machine-readable run summary")
    parser.add_argument(
        "--data-dir", type=Path, default=None,
        help="Defaults to BIOS_RUNTIME_DIR/data (or BIOS_DATA_DIR) if set, else <repo>/data -- "
        "same resolution app/main.py uses, so a scheduled run against a deployed container's "
        "mounted runtime volume writes where the app actually reads from, not a container-local path.",
    )
    parser.add_argument("--schemas-dir", type=Path, default=SCHEMAS_DIR)
    parser.add_argument(
        "--inbox-dir", type=Path, default=None,
        help="Defaults to BIOS_RUNTIME_DIR/inbox (or BIOS_INBOX_DIR) if set, else <repo>/inbox.",
    )
    parser.add_argument("--operations-dir", type=Path, help="Defaults to <inbox>/operations")
    return parser


def _validate_nonnegative(parser: argparse.ArgumentParser, name: str, value: int | None) -> None:
    if value is not None and value < 0:
        parser.error(f"{name} must be non-negative")


def _human_summary(payload: dict) -> str:
    counts = payload["counts"]
    gate = payload["extraction_gate"]
    lines = [
        f"Run: {payload['run_id']}",
        f"Sources checked: {counts['sources_checked']}",
        f"Sources succeeded: {counts['sources_succeeded']}",
        f"Sources failed: {counts['sources_failed']}",
        "",
        f"New media items: {counts['items_new']}",
        f"Items processed: {counts['items_processed']}",
        f"Transcripts ready: {counts['transcripts_ready']}",
        f"Transcriptions attempted: {counts['transcriptions_attempted']}",
        f"Publication drafts created: {counts['publication_drafts_created']}",
        f"Awaiting publication review: {counts['awaiting_publication_review']}",
        "",
        f"Ready for extraction: {counts['ready_for_extraction']}",
        f"Extraction gate: {gate['reason']}",
        f"Extraction skipped: {counts['extraction_skipped']}",
        f"Atomic reviews waiting: {counts['atomic_reviews_waiting']}",
        f"Atomic proposals created: {counts['proposals_generated']}",
        "",
        f"Retryable failures: {counts['retryable_failures']}",
        f"Operator-action items: {counts['operator_action_items']}",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.data_dir is None:
        args.data_dir = resolve_data_dir(ROOT)
    if args.inbox_dir is None:
        args.inbox_dir = resolve_inbox_dir(ROOT)
    for name, value in (
        ("--max-transcriptions", args.max_transcriptions),
        ("--max-items", args.max_items),
        ("--retry-limit", args.retry_limit),
        ("--retry-backoff-seconds", args.retry_backoff_seconds),
        ("--lock-stale-seconds", args.lock_stale_seconds),
    ):
        _validate_nonnegative(parser, name, value)

    operations_dir = args.operations_dir or args.inbox_dir / "operations"
    extract_base_url = args.extract_base_url or os.environ.get("BIOS_EXTRACT_BASE_URL")
    extract_model = args.extract_model or os.environ.get("BIOS_EXTRACT_MODEL")
    extraction_enabled = args.enable_extraction or _environment_enabled("BIOS_COLLECTION_ENABLE_EXTRACTION")
    qualification_path = args.qualification_file
    if qualification_path is None:
        configured_path = os.environ.get("BIOS_COLLECTION_QUALIFICATION_FILE")
        qualification_path = Path(configured_path) if configured_path else None
    extraction_config = None
    configuration_fingerprint = None
    if extract_base_url and extract_model:
        extraction_config = OpenAICompatibleExtractionConfig.from_environment(
            api_key_env=args.extract_api_key_env,
            base_url=extract_base_url,
            model=extract_model,
            timeout_seconds=args.extract_timeout,
            window_chars=args.extract_window_chars,
            overlap_segments=args.extract_overlap_segments,
            temperature=args.extract_temperature,
            max_candidates_per_window=args.extract_max_candidates,
            max_total_candidates=args.extract_max_total_candidates,
            response_format=args.extract_response_format,
        )
        temporary_provider = OpenAICompatibleExtractionProvider(
            config=extraction_config,
            repositories=None,
        )
        configuration_fingerprint = qualification_configuration_fingerprint(
            provider="openai-compatible",
            model=extract_model,
            base_url=extract_base_url,
            prompt_version=PROMPT_VERSION,
            generation=public_configuration(temporary_provider),
        )
    # resolve_extraction_gate() returns immediately when extraction is
    # disabled, before it ever looks at benchmark_sha256 -- so the
    # benchmark file only needs to exist (and only needs hashing) when
    # extraction is actually being requested. A deployed container image
    # that never opted into local extraction (this project's default; the
    # recurring scheduler always runs with extraction off) has no reason
    # to require benchmarks/atomic-ci-v1.json to be present at all.
    benchmark_sha256 = file_sha256(ROOT / "benchmarks" / "atomic-ci-v1.json") if extraction_enabled else None
    gate = resolve_extraction_gate(
        enabled=extraction_enabled,
        provider="openai-compatible",
        model=extract_model,
        base_url=extract_base_url,
        prompt_version=PROMPT_VERSION,
        qualification_path=qualification_path,
        configuration_fingerprint=configuration_fingerprint,
        benchmark_sha256=benchmark_sha256,
    )

    schema = json.loads((args.schemas_dir / "evidence.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    evidence_errors = lambda record: [error.message for error in validator.iter_errors(record)]
    repositories = get_repositories(args.data_dir, args.schemas_dir)
    extraction_service = None
    if gate.runnable:
        assert extraction_config is not None
        extraction_service = TranscriptEvidenceExtractionService(
            repositories=repositories,
            inbox_dir=args.inbox_dir,
            evidence_errors=evidence_errors,
            provider=OpenAICompatibleExtractionProvider(config=extraction_config, repositories=repositories),
        )

    def discover(source_id: str):
        return discover_source(
            source_id,
            inbox_dir=args.inbox_dir,
            data_dir=args.data_dir,
            schemas_dir=args.schemas_dir,
            allow_historical_backfill=args.allow_historical_backfill,
        )

    def transcript_ready(item: dict) -> bool:
        payload = load_transcript_artifact(args.inbox_dir, item["id"])
        return bool(
            payload
            and transcript_cache_matches_request(
                args.inbox_dir,
                payload,
                item,
                model=args.model,
                language=args.language,
            )
        )

    # web_article items have no transcript to acquire -- they need real HTML
    # acquisition and body-aware relevance screening instead. Computed once
    # per run, not per item, since entity lists and the AI completer are the
    # same for every article this run considers.
    all_entities = repositories.entities.list()
    article_berries = [record for record in all_entities if record.get("entity_type") == "berry"]
    article_geographies = [record for record in all_entities if record.get("entity_type") == "geography"]
    article_companies = [record for record in all_entities if record.get("entity_type") == "company"]
    article_completer = maybe_untrusted_completer()

    # Sources explicitly registered as government_regulatory are pre-scoped
    # by their own search query (e.g. a Federal Register search built from
    # "strawberries antidumping") -- a docket-only headline from one of them
    # should always get a real Stage B body read rather than being dropped
    # by Stage A's generic-web metadata gate. See article_refresh.py's
    # always_body_check docstring for why this is scoped to the source, not
    # a global relevance-screen change.
    regulatory_source_ids = {
        s["id"] for s in repositories.sources.list() if "government_regulatory" in (s.get("entity_types") or [])
    }

    def orchestrate(item_id: str, allow_transcription: bool, run_extraction: bool, dry_run: bool):
        adapter = MediaTranscriptionAdapter(
            args.inbox_dir,
            model=args.model,
            device=args.device,
            language=args.language,
            created_by=args.created_by,
            transcribe_missing=allow_transcription,
        )
        service = MediaOrchestrationService(
            repositories=repositories,
            inbox_dir=args.inbox_dir,
            evidence_errors=evidence_errors,
            transcript_adapter=adapter,
            extraction_service=extraction_service if run_extraction else None,
        )
        item = service.load_item(item_id)
        if item.get("historical_backlog") and not args.allow_historical_backfill:
            # Staged (never dropped -- see media_discovery.classify_initial_backlog),
            # but excluded from the recurring pass's normal drafting so a
            # spoken-media source's bounded-but-still-real back-catalog
            # doesn't dominate the Scanner review queue. Re-run with
            # --allow-historical-backfill for intentional backfill.
            return OrchestrationResult(
                item_id=item_id,
                state="historical_backlog_suppressed",
                parent_resolution=ParentResolution(
                    status="skipped",
                    message="Historical backlog item; rerun with --allow-historical-backfill to draft it.",
                ),
                transcript_status="deferred",
                next_action="No action; outside the source's bounded initial-discovery window.",
            )
        if item.get("media_format") == "web_article":
            # Real acquisition + two-stage body-aware relevance screening +
            # enrichment, the same pipeline scripts/ingest_articles.py uses
            # standalone -- reachable through the normal recurring runner
            # now instead of only a special-purpose pilot CLI.
            result, extra = process_discovered_article(
                item,
                orchestrator=service,
                inbox_dir=args.inbox_dir,
                completer=article_completer,
                berries=article_berries,
                geographies=article_geographies,
                companies=article_companies,
                dry_run=dry_run,
                always_body_check=item.get("source_id") in regulatory_source_ids,
            )
            result.relevance_tier = extra.get("relevance_tier")
            return result
        return service.process(item_id, dry_run=dry_run)

    runner = CollectionRunner(
        repositories=repositories,
        inbox_dir=args.inbox_dir,
        operations=OperationalStateStore(operations_dir),
        discover=discover,
        orchestrate=orchestrate,
        transcript_cache_ready=transcript_ready,
        extraction_gate=gate,
        retry_limit=args.retry_limit,
        retry_backoff=timedelta(seconds=args.retry_backoff_seconds),
        lock_stale_after=timedelta(seconds=args.lock_stale_seconds),
    )
    try:
        summary = runner.run(
            source_id=args.source,
            dry_run=args.dry_run,
            skip_transcription=args.skip_transcription,
            max_transcriptions=args.max_transcriptions,
            max_items=args.max_items,
            retry_operator_items=args.retry_operator_items,
        )
    except (CollectionLockedError, DiscoveryError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"state": "error", "error": str(exc)}, indent=2))
        return 2
    payload = summary.as_dict()
    print(json.dumps(payload, indent=2, ensure_ascii=False) if args.json else _human_summary(payload))
    return 1 if payload["counts"]["sources_failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
