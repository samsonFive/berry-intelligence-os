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
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--inbox-dir", type=Path, default=ROOT / "inbox")
    args = parser.parse_args()

    if args.dry_run and args.force:
        parser.error("--dry-run cannot be combined with --force")

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
            )
        )
        service = MediaOrchestrationService(
            repositories=repositories,
            inbox_dir=args.inbox_dir,
            evidence_errors=lambda record: [error.message for error in validator.iter_errors(record)],
            transcript_adapter=transcript_adapter,
            extraction_service=extraction_service,
        )
        result = service.process(args.item, dry_run=args.dry_run)
    except (OSError, json.JSONDecodeError, MediaOrchestrationError) as exc:
        print(json.dumps({"item_id": args.item, "state": "error", "error": str(exc)}, indent=2))
        return 1

    print(json.dumps(result.as_dict(), indent=2))
    return 1 if result.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
