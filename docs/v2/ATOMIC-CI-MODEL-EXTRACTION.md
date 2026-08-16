# Atomic CI Model Extraction

`atomic-ci-v1` is the provider-neutral, long-transcript extraction contract.
It extends the existing `ExtractionProvider`; it does not create a second
extraction framework.

## Boundary

```text
TranscriptArtifact
  -> deterministic overlapping windows
  -> OpenAI-compatible chat-completions endpoint
  -> defensive candidate validation and cross-window dedupe
  -> TranscriptEvidenceExtractionService
  -> inbox/evidence/ (draft, in_review)
  -> human review
```

The model cannot write files or choose IDs, timestamps, provenance, or review
state. It returns only an atomic statement, exact global transcript segment
indexes, and optional IDs selected from an allowlist. The service derives
timestamps from the transcript, validates repository links, generates stable
proposal IDs, and owns inbox idempotency. It never creates trusted Evidence,
Facts, Relationships, Assessments, or Recommendations.

## Windowing and dedupe

Windows contain whole transcript segments and are bounded approximately by
characters (`12,000` by default). Each window repeats the preceding eight
segments by default, preserving context at boundaries without embeddings or
provider-specific logic. Segment indexes remain global.

Candidates are rejected unless their indexes are ordered, unique, contiguous,
and present in the submitted window. Identical normalized statements are
deduplicated only when their cited segment spans overlap. The existing stable
proposal identity remains the final idempotency backstop.

## Prompt contract

`atomic-ci-v1` means:

- extract discrete supportable statements, not an episode summary;
- preserve attribution and qualifiers such as `may`, `expects`, and
  `approximately`;
- record what the source says without asserting objective truth;
- use no outside knowledge and skip corrupted or uncertain passages;
- allow zero candidates;
- use only supplied repository IDs;
- never return timestamps or trusted-domain fields.

The version, provider implementation, model, transcript hash, transcript ID,
and final segment span are recorded on every proposal. Full prompts and secrets
are not stored.

## Configuration

No endpoint, model, or credential is committed. Configure through command-line
arguments or environment variables:

| Setting | CLI | Environment | Default |
|---|---|---|---|
| Base URL | `--extract-base-url` | `BIOS_EXTRACT_BASE_URL` | required |
| Model | `--extract-model` | `BIOS_EXTRACT_MODEL` | required |
| API key variable | `--extract-api-key-env` | value read from named variable | `BIOS_EXTRACT_API_KEY` |
| Timeout | `--extract-timeout` | `BIOS_EXTRACT_TIMEOUT_SECONDS` | 120 seconds |
| Window size | `--extract-window-chars` | `BIOS_EXTRACT_WINDOW_CHARS` | 12,000 characters |
| Overlap | `--extract-overlap-segments` | `BIOS_EXTRACT_OVERLAP_SEGMENTS` | 8 segments |
| Temperature | `--extract-temperature` | `BIOS_EXTRACT_TEMPERATURE` | 0 |
| Candidates/window | `--extract-max-candidates` | `BIOS_EXTRACT_MAX_CANDIDATES` | 12 |
| Candidates/run | `--extract-max-total-candidates` | `BIOS_EXTRACT_MAX_TOTAL_CANDIDATES` | 100 |
| Output mode | `--extract-response-format` | `BIOS_EXTRACT_RESPONSE_FORMAT` | `json_schema` |

The base URL should normally include the compatible API prefix (for example,
`http://127.0.0.1:1234/v1`). The provider appends `/chat/completions` unless the
full endpoint is supplied. `json_object` is available for compatible local
runtimes that do not implement strict JSON Schema response format.

## Operator command

```bash
python scripts/process_discovered_media.py \
  --item <discovered-item-id> \
  --extract-provider openai-compatible \
  --extract-base-url <compatible-base-url> \
  --extract-model <model-name>
```

Existing transcript caches are resolved before extraction. Parent binding and
extraction do not set transcription `--force`; therefore this command does not
invalidate a valid cached transcript.

## Failure and metrics

Invalid JSON, unsafe extra fields, missing/wrong types, invented IDs,
out-of-window segments, truncation, timeout, and HTTP failure are explicit.
One failed window is reported while successful windows may still produce review
drafts. If every window fails, the operator command fails without proposals.

Each completed run reports segments, windows, model calls, candidates before
validation, rejected candidates, overlap duplicates, final candidates, elapsed
time, provider/model, errors, and token usage when the endpoint supplies it.

Repeatable model probing, synthetic benchmarking, deterministic real-transcript
sampling, preview-only diagnostics, and the manual quality rubric are described
in `docs/v2/ATOMIC-CI-EVALUATION.md`.
