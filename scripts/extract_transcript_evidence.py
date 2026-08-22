"""Validate structured transcript-extractor output into review proposals.

This offline runner deliberately requires already-structured candidate output.
A future model adapter can call TranscriptEvidenceExtractionService directly;
this command proves the stable transcript/proposal boundary without credentials.
"""

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
from app.services.transcript_evidence import (
    StructuredCandidateProvider,
    TranscriptArtifact,
    TranscriptContractError,
    TranscriptEvidenceExtractionService,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Create untrusted atomic Evidence proposals from a transcript")
    parser.add_argument("--transcript", type=Path, required=True)
    parser.add_argument("--parent-evidence", required=True)
    parser.add_argument("--candidates", type=Path, required=True, help="Structured output from an extractor provider")
    parser.add_argument("--extractor-name", default="structured-file-provider")
    parser.add_argument("--extractor-method", choices=("human", "ai_assisted", "automated"), default="ai_assisted")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--inbox-dir", type=Path, default=ROOT / "inbox")
    args = parser.parse_args()

    try:
        transcript_payload = json.loads(args.transcript.read_text(encoding="utf-8"))
        embedded_parent = transcript_payload.get("parent_evidence_id")
        if embedded_parent and embedded_parent != args.parent_evidence:
            raise TranscriptContractError("--parent-evidence conflicts with transcript parent_evidence_id")
        transcript_payload["parent_evidence_id"] = args.parent_evidence
        transcript = TranscriptArtifact.from_dict(transcript_payload)
        candidates = json.loads(args.candidates.read_text(encoding="utf-8"))
        if not isinstance(candidates, list):
            raise TranscriptContractError("candidate file must contain a JSON array")
        schema = json.loads((SCHEMAS_DIR / "evidence.schema.json").read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        service = TranscriptEvidenceExtractionService(
            repositories=get_repositories(args.data_dir, SCHEMAS_DIR),
            inbox_dir=args.inbox_dir,
            evidence_errors=lambda record: [error.message for error in validator.iter_errors(record)],
            provider=StructuredCandidateProvider(
                candidates,
                name=args.extractor_name,
                method=args.extractor_method,
            ),
        )
        result = service.run(transcript)
    except (OSError, json.JSONDecodeError, TranscriptContractError) as exc:
        print(f"Extraction failed: {exc}")
        return 1

    print(f"Candidates found: {result.candidates_found}")
    print(f"Accepted into inbox: {len(result.accepted)}")
    print(f"Duplicates: {len(result.duplicates)}")
    print(f"Invalid outputs: {len(result.invalid)}")
    for error in result.invalid:
        print(f"- {error}")
    return 1 if result.invalid else 0


if __name__ == "__main__":
    raise SystemExit(main())
