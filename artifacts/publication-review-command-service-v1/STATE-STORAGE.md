# Durable review state storage

## Why not `inbox/`

The candidate pack's own finding (`research/publication-review-candidate-pack-v1`,
`INVENTORY.md`) is the concrete proof: a fresh, isolated git worktree has
**zero** review backlog, because `inbox/` is gitignored and worktree-local.
A production deployment with multiple workers/checkouts behind
`BIOS_RUNTIME_DIR` (see `app/runtime_config.py`) already avoids the
*local-dev* version of this problem for `data/`/`inbox/` themselves, but
the contract's own requirement goes further: durable draft state needs
real compare-and-set concurrency, immutable provenance binding,
idempotency receipts, and a recoverably-staged commit protocol — none of
which the existing `inbox/evidence/<id>.json` convention provides (it is
a plain, unversioned, unlocked JSON file).

## Storage backend: filesystem, no external infrastructure

Per the contract's own instruction ("avoid introducing an external
infrastructure dependency unless the contract explicitly requires one" —
it does not), `DurableReviewRepository`
(`app/services/publication_review_repository.py`) is a plain-filesystem
store using the exact same one-file-per-record, atomic-rename-on-write
discipline every other repository in this codebase already uses. No
database, queue, or object store was introduced.

## Directory resolution

`resolve_review_state_dir()` mirrors `app.runtime_config.resolve_data_dir`/
`resolve_inbox_dir` exactly:

1. `BIOS_REVIEW_STATE_DIR` (explicit override) wins outright.
2. Otherwise `BIOS_RUNTIME_DIR/review_state` when a persistent runtime
   mount is configured (the same variable that already relocates `data/`
   and `inbox/` for a remote/production deployment) — this is what makes
   the store survive a fresh checkout in that deployment shape.
3. Otherwise a repo-relative, **gitignored** `review_state/` directory for
   local development — added to `.gitignore` alongside `inbox/`, kept
   deliberately distinct from it per the contract's own "keep inbox/ as a
   local/test adapter only" instruction.

## Layout

```
<review_state_root>/
  drafts/<draft_id>.json                     current DraftState snapshot
  drafts_archive/<draft_id>/<version>.json    append-only prior versions
  locks/<draft_id>.lock                       per-draft exclusive lock
  idempotency/<actor_id_hash_dir>/<key_hash>.json   idempotency receipts
  journal/<draft_id>/<transaction_id>/*.json  staged promotion protocol
```

Every write goes through `atomic_write_json` (`app.services.draft_delivery`,
reused verbatim): a temp file in the same directory, then `os.replace()`
— an atomic rename on the underlying filesystem. A reader never observes
a torn/partial file; it observes either the previous complete file or the
new complete file.

## `DraftState` fields (every field `IMPLEMENTATION SCOPE` item 1 names)

| Field | Meaning |
|---|---|
| `id` | Durable draft identity |
| `version` | Monotonic version, incremented on every state-changing write (both content revisions and decisions) |
| `state` | One of the six canonical review states |
| `draft` | The actual review-relevant content payload |
| `content_digest` | `compute_review_content_digest()` — the normalized-content digest |
| `provenance_digest` | `compute_provenance_digest()` — a separate digest over acquisition/source provenance fields only |
| `content_class` | Last computed `source_completeness()` class |
| `acquisition_classification` | Last computed `classify_source_body()` body state |
| `created_at`/`updated_at` | ISO-8601 timestamps |
| `decision_history` | Append-only list of every command applied, in order |
| `publication_binding` | `{publication_id, committed_at, transaction_id}` once approved, else `None` |
| `recovery_state` | Reserved for future explicit in-progress markers (the journal itself is the authoritative recovery signal today — see `CRASH-RECOVERY.md`) |

## Concurrency

- **Compare-and-set**: `compare_and_set(draft_id, expected_version, mutate)`
  re-reads the current `DraftState`, rejects with `StaleVersion` (no write)
  if `expected_version` does not match, archives the prior version, then
  atomically writes the new one.
- **Per-draft locking**: `lock_draft(draft_id)` is an exclusive
  `O_CREAT|O_EXCL` file lock — the same primitive
  `review_events.append_review_event`'s own exclusive-create already
  relies on for collision safety. Single-machine, multi-process safe; a
  lock older than `LOCK_STALE_SECONDS` (120s default) is presumed
  abandoned by a crashed process and may be reclaimed. This is not a
  distributed lock across separate hosts — the contract does not require
  one, and none was introduced.
- **Idempotency receipts**: keyed by `(actor_id, idempotency_key)`,
  storing a hash of the full normalized command payload plus the recorded
  result. An exact retry returns the stored result; a different payload
  under the same key raises `IdempotencyConflict`.

## Proof this actually survives restart / a new checkout

`tests/test_publication_review_repository.py::test_state_survives_a_fresh_repository_instance_pointed_at_the_same_root`
constructs a *second*, independent `DurableReviewRepository` Python object
pointed at the same root directory (no shared in-process state) and
confirms it sees the first instance's committed work — the same property
a new worker process or a redeployed checkout would need.
`test_deleting_a_local_inbox_projection_does_not_delete_durable_work`
proves the two stores are genuinely independent.
