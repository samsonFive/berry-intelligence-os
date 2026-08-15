# Transcript → Atomic Evidence Proposal Layer

**Date:** 2026-08-15

## Architectural approach

The extractor reuses the ordinary Evidence inbox and human review workflow. It does not add a spoken-word queue or trusted-data write path.

```text
Structured TranscriptArtifact
  → ExtractionProvider Protocol
  → untrusted structured candidates
  → deterministic service validation and identity
  → inbox/evidence draft proposals
  → existing edit / approve / reject review
  → published atomic Evidence only after approval
```

The repository has no implemented AI abstraction today. `ExtractionProvider` is therefore the smallest new interface: a provider receives an `ExtractionRequest` containing the transcript, parent publication artifact, and explicit extraction rules, then returns candidate dictionaries. Tests and the CLI use an offline structured-candidate provider; a future model adapter implements the same interface without changing validation or review.

## Transcript input contract

The JSON contract is acquisition- and vendor-neutral:

```json
{
  "transcript_id": "transcript-stable-id",
  "parent_evidence_id": "ev-publication-artifact",
  "language": "en",
  "provenance": {
    "method": "publisher_provided | human_provided | auto_generated",
    "created_by": "publisher, operator, or transcription system label",
    "created_at": "YYYY-MM-DD"
  },
  "segments": [
    {
      "text": "Transcript text",
      "start_seconds": 750,
      "end_seconds": 790,
      "speaker_label": "Speaker A"
    }
  ]
}
```

The future acquisition/transcription layer only needs to serialize this contract. It does not need to know inbox paths or Evidence proposal details.

## Candidate contract and trust boundary

A provider proposes:

- `normalized_statement`
- one or more contiguous `segment_indexes`
- supported `entity_ids`, `geography_ids`, and `berry_ids`

The service derives timestamps, speaker label, and the exact supporting excerpt from those segments rather than trusting a provider to invent locators. It adds parent/source lineage, separate transcript and extraction provenance, a canonical transcript-content SHA-256, draft/in-review state, and review-form suggestions. It never writes to `data/evidence/`.

## Validation and dedupe

Before inbox persistence, the service requires:

- an existing `publication_artifact` parent;
- a valid, ordered transcript with bounded timestamps;
- a non-empty candidate statement;
- valid contiguous segment references;
- resolvable and correctly typed entity/geography/berry IDs;
- valid extraction and transcript provenance;
- conformance to `evidence.schema.json`.

Invalid candidates are reported and not silently repaired. Proposal IDs are a SHA-256-derived key over parent Evidence ID, derived timestamp span, and normalized statement. The same unchanged transcript/candidate output therefore resolves to the same inbox ID; an existing pending, rejected, or already-approved record counts as a duplicate rather than being recreated. Text is normalized only for whitespace and identity—qualifiers and wording are otherwise preserved.

## CLI boundary

```bash
python scripts/extract_transcript_evidence.py \
  --transcript transcript.json \
  --parent-evidence ev-publication-artifact \
  --candidates structured-candidates.json
```

The candidate-file adapter is an offline provider boundary, not a CI heuristic. No live model, credentials, discovery, downloading, or transcription is included.
