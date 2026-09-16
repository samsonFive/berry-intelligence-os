# Publication promotion failure and recovery

## Rollback compensation is not crash consistency

The existing JSON Unit of Work and attachment/event cleanup compensate after a caught exception. They reduce ordinary partial failures, but they cannot run after process termination, host loss, or power failure. Therefore they do not prove atomic durability or reader isolation. V1 may reuse compensation as a cleanup mechanism, but production promotion is blocked until either one transactional durable store covers all trust-state writes or the staged protocol below is implemented.

## Concurrency controls

Every mutation uses a per-draft lock, compare-and-set `review_version`, reviewed digest, and idempotency receipt in shared durable storage. The service re-reads draft state, source/provenance, acquisition outcome, duplicate identity, and trusted-publication existence while holding the lock. A stale screen receives 409 with the current version and digest and makes no mutation. A filesystem lock in one checkout is insufficient across workers.

An idempotency receipt binds actor, command type, draft ID, and normalized payload hash to one result. Exact retry returns the recorded result. Reuse for different parameters returns `idempotency_conflict`.

## Durable review state

The authoritative production repository must be shared across checkouts and workers and survive restart. It stores the draft state/version, immutable provenance references and hashes, command receipt, decision, transaction journal/commit marker, and archive reference. A gitignored `inbox/` may implement local development and tests, but production cannot acknowledge a draft or decision that exists only there.

## Promotion journal and visibility commit

If one database/object-store transaction cannot cover the entire promotion, approval uses a private durable journal and staging namespace outside canonical/static inputs:

1. validate command and acquire lock;
2. durably write command intent/receipt with expected version, reviewed digest, provenance digest, actor, and target publication ID;
3. stage the trusted publication under the transaction ID; it is not queryable as trusted;
4. stage the immutable review decision binding draft/version/provenance to the publication hash;
5. append the audit event linked to that transaction; before commit it is an operational pending event, not a completed trust decision;
6. verify the staged publication, decision, event, and hashes, then atomically compare-and-set the draft version and publish one commit marker;
7. archive the source draft and related private attachments idempotently, mark cleanup complete, and release the lock.

The commit marker is the visibility boundary. Trusted repositories, extraction jobs, Today, reports, company coverage, and static builders recognize a publication only when the marker exists and every referenced record/hash verifies. They ignore staging namespaces and incomplete journals. The journal contains identifiers and hashes, not copied article bodies or secrets.

## Recovery cases

| Failure point | Observable state | Recovery |
|---|---|---|
| Before intent is durable | Prior complete state only | Retry normally. |
| After intent, before publication stage | Pending journal, prior complete state visible | Same-key retry or reconciler resumes after revalidation. |
| Publication staged, decision absent | Staged publication is invisible; prior complete state visible | Reconciler resumes or abandons the stage. |
| Decision staged, audit event absent | Publication and decision remain invisible; prior complete state visible | Reconciler appends the event or abandons all staged records. |
| Audit event appended, commit marker absent | Event is pending/operational only; trusted/static readers still see prior complete state | Reconciler verifies all bindings and commits or marks the transaction aborted. It never reports approval from the event alone. |
| Commit marker published | Publication, decision, and audit event become one new complete visible state | Recovery may only finish idempotent archival/cleanup; it must not roll back visible trust without a new audited decision. |
| Commit exists, draft archive incomplete | New complete state visible; private draft remains temporarily | Reconciler completes idempotent archive. |
| Attachment move fails | Journal records pending attachment operation | Restore or resume without exposing a partial static record. |
| Process crashes after completion | Receipt/event/publication identify completed result | Exact retry returns the same publication and completes cleanup. |
| Duplicate appears concurrently | Deterministic identity check fails under lock | One succeeds; the other receives identical-success or 409 conflict, never overwrite. |

At every row, a reader sees exactly one of two snapshots: the prior draft/nonpublication state, or the committed publication/decision/event state. No reader may infer trust from file existence, publication status, or an audit event without the verified commit marker.

## Audit rules

Completed revision and decision events are append-only. Corrections, withdrawal, supersession, and body upgrades append a new event/review cycle; they do not edit prior decisions. Failed or interrupted command attempts may be retained as operational journal/pending event entries but are not represented as completed human decisions unless referenced by a valid commit marker.

The event records actor ID, command and reason, before/after state, version, content digest, warning acknowledgments, idempotency key hash, publication/draft/source IDs, timestamp, and linked prior event where applicable. It excludes full bodies, transcripts, credentials, cookie walls, and access-denied payloads.

## Content upgrades

A later readable body or improved transcript creates a new content revision with old/new hashes and provenance. It invalidates any open review digest and requires human publication re-review before the upgraded content affects readable/current coverage or static excerpts. Previously approved metadata remains auditable.
