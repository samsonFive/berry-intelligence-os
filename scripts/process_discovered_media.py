"""Advance one discovered-media item through safe orchestration steps."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.composition import get_repositories
from app.repositories.paths import DEFAULT_DATA_DIR, SCHEMAS_DIR
from app.services.ai_extraction import (
    ExtractionProviderError,
    OpenAICompatibleExtractionConfig,
    OpenAICompatibleExtractionProvider,
)
from app.services.article_refresh import process_discovered_article
from app.services.deterministic_tagging import matchers_from_entities
from app.services.relevance_screen import geography_corroboration_matchers
from app.services.media_orchestration import (
    JsonStagedTranscriptAdapter,
    MediaTranscriptionAdapter,
    MediaOrchestrationError,
    MediaOrchestrationService,
)
from app.services.media_transcription import AVAILABLE_WHISPER_MODELS, DEFAULT_WHISPER_MODEL
from app.services.transcript_evidence import StructuredCandidateProvider, TranscriptEvidenceExtractionService


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely process one staged discovered-media item")
    parser.add_argument("--item", required=True, help="Discovered-media item id")
    parser.add_argument("--dry-run", action="store_true", help="Report the next action without writing")
    parser.add_argument("--transcript", type=Path, help="Explicit normalized transcript JSON handoff")
    parser.add_argument("--model", choices=AVAILABLE_WHISPER_MODELS, default=DEFAULT_WHISPER_MODEL)
    parser.add_argument("--device", choices=("cpu", "cuda"), help="Local transcription device; auto-detected by default")
    parser.add_argument("--language", help="Force a transcription language code")
    parser.add_argument("--created-by", help="Transcript provenance label")
    parser.add_argument("--force", action="store_true", help="Bypass Claude's media/transcription caches")
    parser.add_argument("--candidates", type=Path, help="Structured output for the existing extraction service")
    parser.add_argument("--extractor-name", default="structured-file-provider")
    parser.add_argument("--extractor-method", choices=("human", "ai_assisted", "automated"), default="ai_assisted")
    parser.add_argument("--extract-provider", choices=("openai-compatible",), help="Real model extraction provider")
    parser.add_argument("--extract-base-url", help="OpenAI-compatible base URL (or BIOS_EXTRACT_BASE_URL)")
    parser.add_argument("--extract-model", help="Extraction model name (or BIOS_EXTRACT_MODEL)")
    parser.add_argument("--extract-api-key-env", default="BIOS_EXTRACT_API_KEY", help="Environment variable holding the optional API key")
    parser.add_argument("--extract-timeout", type=float, help="Model request timeout in seconds")
    parser.add_argument("--extract-window-chars", type=int, help="Approximate maximum characters per transcript window")
    parser.add_argument("--extract-overlap-segments", type=int, help="Segment overlap between transcript windows")
    parser.add_argument("--extract-temperature", type=float, help="Model sampling temperature")
    parser.add_argument("--extract-max-candidates", type=int, help="Maximum candidates per window")
    parser.add_argument("--extract-max-total-candidates", type=int, help="Maximum candidates retained per run")
    parser.add_argument("--extract-response-format", choices=("json_schema", "json_object"), help="Compatible endpoint output mode")
    parser.add_argument("--relevance-gate", action="store_true", help="Skip clearly irrelevant items before transcription")
    parser.add_argument("--enrich", action="store_true", help="Apply deterministic/AI publication-draft enrichment")
    parser.add_argument("--max-tier", type=int, default=3, help="Stop transcription after this tier (2 skips Whisper)")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--inbox-dir", type=Path, default=ROOT / "inbox")
    args = parser.parse_args()

    if args.dry_run and args.force:
        parser.error("--dry-run cannot be combined with --force")
    if args.candidates and args.extract_provider:
        parser.error("--candidates and --extract-provider are mutually exclusive")

    schema = json.loads((SCHEMAS_DIR / "evidence.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    repositories = get_repositories(args.data_dir, SCHEMAS_DIR)
    extraction_service = None
    try:
        if args.candidates:
            candidates = json.loads(args.candidates.read_text(encoding="utf-8"))
            if not isinstance(candidates, list):
                raise MediaOrchestrationError("candidate file must contain a JSON array")
            extraction_service = TranscriptEvidenceExtractionService(
                repositories=repositories,
                inbox_dir=args.inbox_dir,
                evidence_errors=lambda record: [error.message for error in validator.iter_errors(record)],
                provider=StructuredCandidateProvider(
                    candidates,
                    name=args.extractor_name,
                    method=args.extractor_method,
                ),
            )
        elif args.extract_provider == "openai-compatible":
            config = OpenAICompatibleExtractionConfig.from_environment(
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
            extraction_service = TranscriptEvidenceExtractionService(
                repositories=repositories,
                inbox_dir=args.inbox_dir,
                evidence_errors=lambda record: [error.message for error in validator.iter_errors(record)],
                provider=OpenAICompatibleExtractionProvider(config=config, repositories=repositories),
            )
        transcript_adapter = (
            JsonStagedTranscriptAdapter(args.inbox_dir, args.transcript)
            if args.transcript
            else MediaTranscriptionAdapter(
                args.inbox_dir,
                model=args.model,
                device=args.device,
                language=args.language,
                created_by=args.created_by,
                force=args.force,
                transcribe_missing=not args.dry_run,
                max_tier=args.max_tier,
            )
        )
        completer = None
        if args.enrich:
            from app.services.ai_gateway.untrusted_complete import maybe_untrusted_completer
            completer = maybe_untrusted_completer()
        service = MediaOrchestrationService(
            repositories=repositories,
            inbox_dir=args.inbox_dir,
            evidence_errors=lambda record: [error.message for error in validator.iter_errors(record)],
            transcript_adapter=transcript_adapter,
            extraction_service=extraction_service,
            complete_json=completer,
        )
        # Relevance Screen Boundary V1 (2026-08-23): a web_article item under
        # --relevance-gate goes through the same two-stage, body-aware
        # screen (app/services/relevance_screen.py + article_refresh.py's
        # process_discovered_article) scripts/run_collection.py and
        # scripts/ingest_articles.py already use, instead of
        # service.process()'s single-stage, metadata-only
        # app/services/relevance_screening.py gate, which never fetches a
        # real article body at all. Without --relevance-gate, behavior is
        # unchanged (direct service.process(), no screening) -- that flag's
        # whole purpose is to make screening optional.
        loaded_item = service.load_item(args.item)
        if args.relevance_gate and loaded_item.get("media_format") == "web_article":
            all_entities = repositories.entities.list()
            # Same pre-scoped-source signal scripts/run_collection.py's own
            # regulatory_source_ids uses -- a source explicitly tagged
            # government_regulatory (Federal Register, openFDA, UK FSA, a
            # CIK-scoped SEC EDGAR search) already names its own entity/
            # topic scope, so a docket-only or filing-only headline
            # deserves a real Stage B read rather than Stage A's generic-
            # web metadata gate. See article_refresh.process_discovered_
            # article's own always_body_check docstring.
            item_source = repositories.sources.get(loaded_item.get("source_id") or "")
            always_body_check = bool(
                item_source and "government_regulatory" in (item_source.get("entity_types") or [])
            )
            result, extra = process_discovered_article(
                loaded_item,
                orchestrator=service,
                inbox_dir=args.inbox_dir,
                completer=completer if args.enrich else None,
                berries=[r for r in all_entities if r.get("entity_type") == "berry"],
                geographies=[r for r in all_entities if r.get("entity_type") == "geography"],
                companies=[r for r in all_entities if r.get("entity_type") == "company"],
                dry_run=args.dry_run,
                always_body_check=always_body_check,
                geo_matchers=geography_corroboration_matchers(all_entities),
                company_matchers=matchers_from_entities(all_entities, "company"),
            )
        else:
            result = service.process(
                args.item,
                dry_run=args.dry_run,
                relevance_gate=args.relevance_gate,
                enrich=args.enrich,
            )
    except (OSError, ValueError, json.JSONDecodeError, ExtractionProviderError, MediaOrchestrationError) as exc:
        print(json.dumps({"item_id": args.item, "state": "error", "error": str(exc)}, indent=2))
        return 1

    print(json.dumps(result.as_dict(), indent=2))
    return 1 if result.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
