# Collection Operations Status

`collection_status.py` is a read-only operator view of the recurring collection pipeline. It answers what the system is waiting on and recommends one safe next action. It never performs that action.

## Commands

```bash
python scripts/collection_status.py
python scripts/collection_status.py --json
python scripts/collection_status.py --source <source-id>
```

The default report shows all discoverable Sources. `--source` limits readiness, item detail, and the per-Source report to one configured Source. `--json` emits the stable machine-readable representation.

To evaluate extraction-enabled readiness, pass the same external configuration used by the runner:

```bash
python scripts/collection_status.py \
  --enable-extraction \
  --extract-base-url <openai-compatible-base-url> \
  --extract-model <model> \
  --qualification-file <qualification-marker.json>
```

The API key, if required, remains in the environment variable named by `--extract-api-key-env`. Status does not contact the endpoint. A marker is accepted only when the existing qualification validator confirms its provider, model, prompt, generation settings, benchmark identity, and evaluation-artifact integrity.

## What the report means

The read model combines configured Sources, staged discoveries, runner operation and lock state, publication review, trusted publication artifacts, cached transcript readiness, extraction completion, model qualification, and Atomic Evidence review.

Each discovered item receives exactly one operational category:

- `ready_to_advance`: the next bounded collection run can safely advance it.
- `human_publication_review_required`: the publication trust gate is waiting on a reviewer.
- `extraction_ready`: trusted parent and transcript are ready for a currently qualified extractor.
- `extraction_blocked`: extraction is disabled, incomplete, or not exactly qualified.
- `human_atomic_evidence_review_required`: untrusted proposals await item-by-item review.
- `retryable_failure`: bounded runner retry remains available.
- `operator_intervention_required`: malformed state, ambiguity, exhaustion, or another manual correction blocks progress.
- `completed_no_action`: a legitimate terminal state, including rejection or recorded zero-candidate extraction.

Recommended-action precedence is deterministic:

1. resolve operator-action failure;
2. review Atomic Evidence;
3. review publication;
4. qualify extraction model;
5. run collection;
6. no action.

An active runner lock suppresses a new run recommendation. Status reports stale locks but never steals or recovers them.

## Pilot readiness

The report deliberately separates:

- **Collection-only pilot** — checks discoverable scope, lock safety, and readable discovery state. It does not require a semantic model.
- **Extraction-enabled pilot** — additionally requires complete provider/model configuration and an exact, integrity-valid qualification marker.

Extraction readiness never weakens either human trust boundary. A ready extractor can create only untrusted Atomic Evidence proposals.

## Operator cycle

1. Check `collection_status.py`.
2. Dry-run `run_collection.py`.
3. Run a bounded collection.
4. Review publication drafts at `/review`.
5. Use `qualify_extraction_model.py` when semantic extraction is desired; qualification remains an explicit human decision.
6. Run a bounded extraction-enabled collection.
7. Review Atomic Evidence at `/review`.
8. Repeat.

`run_collection.py` advances workflow. `/review` makes human trust decisions. `qualify_extraction_model.py` validates and explicitly qualifies an extraction configuration. `collection_status.py` only observes their persisted state.

## Safety and degraded state

The command does not discover, download, transcribe, invoke a model, mutate retries, create or recover locks, or write review/trusted data. Runtime JSON is read directly only where no repository abstraction exists. A malformed runtime record is isolated, shown as operator intervention, and does not hide unaffected Sources or items.

This is local operational infrastructure. Runtime, qualification, and unpublished review state are not connected to static generation.
