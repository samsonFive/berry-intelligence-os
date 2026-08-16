# Recurring Collection Runner

`scripts/run_collection.py` performs one bounded pass over configured media
Sources. It is scheduler-friendly, but it is not a daemon or an approval
system.

## Trust boundaries

The runner may automate:

1. configured Source discovery and dedupe;
2. caption, transcript, and media acquisition;
3. local Whisper fallback and cache reuse;
4. creation of an untrusted `publication_artifact` draft;
5. resume after human publication review;
6. qualified model extraction into untrusted atomic Evidence proposals.

It cannot approve publication drafts or atomic Evidence. It never creates
Facts, Relationships, Assessments, or Recommendations.

## Commands

Run all eligible configured Sources:

```bash
python scripts/run_collection.py --all
```

Troubleshoot one Source and cap local work:

```bash
python scripts/run_collection.py \
  --source <source-id> \
  --max-items 20 \
  --max-transcriptions 2
```

Plan locally without network activity or writes:

```bash
python scripts/run_collection.py --all --dry-run --json
```

`--dry-run` and its alias `--offline-plan` inspect configured Sources,
already-staged items, caches, drafts, reviews, and extraction readiness. They
do not call discovery because the existing discovery service both fetches and
stages its results.

Defer CPU transcription while still reusing valid caches:

```bash
python scripts/run_collection.py --all --skip-transcription
```

Operational run and item records are written under `inbox/operations/` by
default. This directory is covered by the repository's existing `inbox/`
ignore rule and is outside trusted `data/`.

## Extraction gate

Recurring extraction is disabled by default. Enabling it requires all three:

1. `--enable-extraction` or `BIOS_COLLECTION_ENABLE_EXTRACTION=true`;
2. an OpenAI-compatible endpoint and model through the existing extraction
   options/environment variables;
3. an operator qualification file matching the exact provider, model, and
   prompt version.

Example qualification marker:

```json
{
  "provider": "openai-compatible",
  "model": "operator-selected-model",
  "prompt_version": "atomic-ci-v1",
  "operator_qualified": true,
  "qualified_by": "operator-identity",
  "qualified_at": "2026-08-16"
}
```

The marker contains no credentials and does not represent automated model
approval. It records an explicit human operational decision made after using
the independent extraction evaluation harness.

```bash
python scripts/run_collection.py \
  --all \
  --enable-extraction \
  --qualification-file inbox/operations/model-qualification.json \
  --extract-base-url <compatible-endpoint> \
  --extract-model <qualified-model>
```

Even with every gate open, output stops in `inbox/evidence/` for individual
human review in the Atomic Evidence Review Workbench.

## Retry and overlap behavior

- Retryable item failures use bounded, persisted backoff.
- Operator/terminal failures do not rerun by default. After correcting the
  underlying state, use `--retry-operator-items` to re-evaluate them.
- One local lock prevents overlapping non-dry runs. Old locks are recovered
  after the configured stale interval.
- Domain state remains authoritative: staged items, transcript caches,
  Evidence drafts, trusted publication artifacts, and atomic review records.
  Operational JSON stores only attempts, failures, retry timing, completed
  zero-result extractions, and run summaries.

## External scheduling

An external scheduler may invoke the same one-shot command. Use its exit code
and `--json` output or read `inbox/operations/runs/*.json`. Scheduling does not
change either human approval boundary. OS-specific cron or Task Scheduler
configuration is intentionally outside the core service.
