# Crash consistency and recovery

## Why exception-time rollback is not enough

`ReviewPublishService.publish()`'s existing JSON Unit of Work compensates
after a *caught* exception — it cannot run after the process itself dies
(host loss, OOM kill, power failure) between two writes. The contract's
own `FAILURE-AND-RECOVERY.md` calls this out explicitly, and this mission
implements the staged protocol it requires instead of relying on
compensation alone.

## The staged promotion protocol

`PublicationReviewCommandService._promote()`/`_finish_promotion()`
(`app/services/publication_review_command.py`) implement the contract's
seven numbered steps as eight concrete, ordered writes:

| # | Write | Where | Idempotent on retry? |
|---|---|---|---|
| 1 | Validate command, acquire per-draft lock | in-memory + `locks/<id>.lock` | n/a |
| 2 | `intent` journal phase | `journal/<draft>/<txn>/intent.json` | Yes — same content every time |
| 3 | `staged_publication` journal phase (the full trusted-record payload + its hash) | `journal/.../staged_publication.json` | Yes |
| 4 | `staged_decision` journal phase (binds draft id/version/digest/provenance to the publication hash) | `journal/.../staged_decision.json` | Yes |
| 5 | `staged_event` journal phase (the pending, not-yet-real audit event) | `journal/.../staged_event.json` | Yes |
| 6 | **The real visibility boundary**: one atomic write of the trusted publication to `data/evidence/<id>.json` | `atomic_write_json` (temp + `os.replace`) | Yes — skipped if the file already exists |
| 7 | The real, shared audit event | `append_review_event()` (its own exclusive-create + retry-detection) | Yes, by that function's own design |
| 8 | Draft compare-and-set to `approved` | `drafts/<id>.json` | Yes — skipped if already `approved` |
| 9 | `commit_marker` journal phase — the final, authoritative "this transaction is done and verified" signal | `journal/.../commit_marker.json` | Yes |

Step 6 is the one write external readers actually observe: before it,
`repositories.evidence.get(publication_id)` returns `None`; after it,
the complete record. Because `atomic_write_json` writes to a temp file
and renames, there is no window where a reader could see a half-written
file — it is always the prior complete state or the new complete state.

## Recovery: `reconcile_pending_transactions()`

Never runs automatically mid-request. An operator (or a startup hook, not
built in this mission) calls it explicitly. For every `(draft_id,
transaction_id)` whose journal has no `commit_marker` yet:

- If `staged_publication`, `staged_decision`, and `staged_event` are all
  present: **resume** — re-run `_finish_promotion()`. Every write in
  steps 6-9 is idempotent, so this converges to exactly the committed
  state whether it is running for the first time or the fifth.
- Otherwise (crashed before all three staged phases exist): **safely
  abandon** — nothing was ever made visible (step 6 never ran), so the
  draft stays at its prior version/state. A fresh command with a new
  idempotency key can be issued normally afterward.

Recovery never rolls back a published commit marker, and never fabricates
a decision from a staged-but-uncommitted event alone.

## What was actually tested (not just designed)

`tests/test_publication_review_crash_recovery.py` injects a real
hard-stop after every phase above by wrapping the real function so it
performs its actual write and then raises — the crash is not simulated by
skipping work, it happens exactly where a real process death would land:

1. Before intent — nothing written; retry behaves as a fresh command.
2. After intent, before `staged_publication` — abandoned; prior state visible.
3. After `staged_publication`, before `staged_decision` — abandoned.
4. After `staged_decision`, before `staged_event` — abandoned.
5. After `staged_event`, before the real evidence write — **resumed**;
   reader isolation holds throughout (no evidence file exists until
   recovery completes it).
6. Between the real evidence write and the real audit event — the sharpest
   case: the evidence file exists but nothing else does. Recovery resumes
   without creating a second evidence file.
7. Between the real audit event and the draft compare-and-set — the draft
   still reads `pending_review` even though the publication file exists
   (by design: the commit marker, not the evidence file alone, is
   authoritative for this repository's own reads). Recovery completes the
   compare-and-set; `append_review_event`'s own idempotent retry-detection
   guarantees no duplicate event.
8. Commit marker already published — reconciliation is a no-op;
   `pending_transactions()` no longer lists it.
9. A fresh command-service instance (simulating a new process) replaying
   the exact same idempotency key after full completion returns the
   identical result.
10. A duplicate appearing concurrently at the same publication id (written
    directly, simulating a race) is rejected with `identity_conflict`
    rather than overwritten.

Every one of these is a distinct, passing test — not a single "crash
somewhere" smoke test. See `TEST-RESULTS.md` for exact counts.

## Not applicable in this mission's scope

- **Attachment move failures**: publication drafts in this service carry
  no file attachments (unlike `ReviewPublishService.publish()`'s
  evidence-attachment handling) — there is nothing to restore.
- **Cross-host distributed locking**: the per-draft lock is single-machine,
  multi-process safe (exclusive file creation). The contract does not
  require a distributed lock, and none was introduced, per "avoid
  introducing an external infrastructure dependency."
