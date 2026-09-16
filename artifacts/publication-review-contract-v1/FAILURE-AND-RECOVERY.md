# Publication promotion failure and recovery

## Concurrency controls

Every mutation uses a per-draft lock, compare-and-set `review_version`, reviewed digest, and idempotency receipt. The service re-reads draft state, source/provenance, acquisition outcome, duplicate identity, and trusted-publication existence while holding the lock. A stale screen receives 409 with the current version and digest and makes no mutation.

An idempotency receipt binds actor, command type, draft ID, and normalized payload hash to one result. Exact retry returns the recorded result. Reuse for different parameters returns `idempotency_conflict`.

## Promotion journal

Because JSON files and attachment moves are not one database transaction, approval uses a private durable journal outside the canonical/static tree:

1. validate command and acquire lock;
2. write command intent with input digest and target publication ID;
3. create or verify the trusted publication atomically;
4. append the completed publication decision event;
5. archive the source draft and related private attachments;
6. mark the journal complete and release the lock.

The public/static projection recognizes a publication only after a completed decision exists. The journal contains identifiers and hashes, not copied article bodies or secrets.

## Recovery cases

| Failure point | Observable state | Recovery |
|---|---|---|
| Before intent is durable | No mutation | Retry normally. |
| After intent, before publication create | Pending journal, no trusted publication | Same-key retry or reconciler resumes after revalidation. |
| Publication exists, completion event missing | Trusted file is quarantined from projection by incomplete journal | Reconciler verifies exact content/hash and appends completion, or compensates the uncommitted create. |
| Completion exists, draft archive incomplete | Trusted publication remains authoritative; private draft remains | Reconciler completes idempotent archive. |
| Attachment move fails | Journal records pending attachment operation | Restore or resume without exposing a partial static record. |
| Process crashes after completion | Receipt/event/publication identify completed result | Exact retry returns the same publication and completes cleanup. |
| Duplicate appears concurrently | Deterministic identity check fails under lock | One succeeds; the other receives identical-success or 409 conflict, never overwrite. |

## Audit rules

Completed revision and decision events are append-only. Corrections, withdrawal, supersession, and body upgrades append a new event/review cycle; they do not edit prior decisions. Failed command attempts may be retained as operational journal entries but are not represented as completed human decisions.

The event records actor ID, command and reason, before/after state, version, content digest, warning acknowledgments, idempotency key hash, publication/draft/source IDs, timestamp, and linked prior event where applicable. It excludes full bodies, transcripts, credentials, cookie walls, and access-denied payloads.

## Content upgrades

A later readable body or improved transcript creates a new content revision with old/new hashes and provenance. It invalidates any open review digest and requires human publication re-review before the upgraded content affects readable/current coverage or static excerpts. Previously approved metadata remains auditable.
