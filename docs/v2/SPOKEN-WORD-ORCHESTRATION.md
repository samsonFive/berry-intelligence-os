# Spoken-Word Orchestration Bridge

The bridge coordinates existing stages without owning discovery,
transcription, extraction, or review:

```text
discovered_media_item
  -> untrusted publication_artifact draft
  -> human publication review
  -> parent Evidence resolution
  -> normalized TranscriptArtifact binding
  -> existing atomic Evidence extractor
  -> untrusted atomic_evidence proposals
  -> human atomic Evidence review
```

## Derived operator state

`MediaOrchestrationService` derives state from the discovered item, trusted
Evidence repository, Evidence inbox, and normalized transcript adapter. It
does not persist a separate workflow record.

- `discovered`: no publication representation exists.
- `awaiting_publication_review`: a deterministic publication draft exists.
- `publication_rejected`: the prior draft remains rejected for audit.
- `publication_approved`: the trusted parent exists but the transcript is
  missing or malformed.
- `ready_for_extraction`: the trusted parent and valid transcript both exist.
- `extraction_complete`: the existing extractor ran; its outputs remain inbox
  proposals.

Multiple possible publication representations produce an `ambiguous` parent
resolution and block automatic progress.

## Transcript handoff contract

Transcription/acquisition code implements:

```python
class StagedTranscriptAdapter(Protocol):
    def load(self, discovered_item: dict[str, Any]) -> dict[str, Any] | None: ...
```

The returned object has the existing `TranscriptArtifact` fields:

- `transcript_id`
- `language`
- `provenance` (`method`, `created_by`, `created_at`)
- ordered `segments` with text and timestamps
- optional `parent_evidence_id`
- optional `discovered_item_id` for a defensive association check

The parent may be absent before publication approval. Once a trusted
`publication_artifact` resolves, `bind_transcript()` copies the payload,
sets the parent metadata, and validates it with `TranscriptArtifact.from_dict`.
It does not mutate transcript text or retranscribe; consequently the existing
segment-content SHA-256 remains stable.

The included filesystem adapter reads either an explicitly supplied path or:

```text
inbox/discovered_media/_normalized_transcripts/<discovered-item-id>.json
```

It intentionally does not treat acquisition's raw transcript staging files as
normalized `TranscriptArtifact` input.

## Operator command

Inspect or prepare the safe next step:

```bash
python scripts/process_discovered_media.py --item <id> --dry-run
python scripts/process_discovered_media.py --item <id>
```

When a normalized transcript and structured extractor output are available:

```bash
python scripts/process_discovered_media.py \
  --item <id> \
  --transcript normalized-transcript.json \
  --candidates extractor-output.json
```

Without `--candidates`, an eligible item stops at `ready_for_extraction`.
This keeps provider selection explicit. Neither command publishes Evidence,
approves proposals, or creates Facts, Assessments, or Recommendations.
