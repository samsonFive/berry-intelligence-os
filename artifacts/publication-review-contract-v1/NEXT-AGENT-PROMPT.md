# Next implementation prompt

Implement Publication Review Contract V1 slices 1 and 2 only.

Start from the exact published HEAD of `design/publication-review-contract-v1` and create a new isolated branch/worktree. Read `AGENTS.md` and every file in `artifacts/publication-review-contract-v1/` before editing.

Scope:

1. Add the pure publication-review domain model: canonical review states, typed commands/results, eligibility/blocker/warning vocabulary, transition rules, deterministic publication identity, and canonical review-content digest.
2. Add private repository/recovery primitives over the existing inbox architecture: version compare-and-set, per-draft locking, idempotency receipts, private durable promotion journal, and private draft archive behavior.
3. Add focused tests for every transition, eligibility content class, stale version/digest, idempotent replay/conflict, concurrent decisions, duplicate identities, and injected failure/recovery phase.

Do not implement routes, UI, CLI integration, production promotion commands, trusted publication writes, static behavior changes, or data migrations. Do not call or alter `ReviewPublishService.publish()` in this slice. Do not create/update Entity, Fact, Relationship, Evidence, Source, Signal, Assessment, acquisition, transcript, inbox, or live/generated application records.

Use temporary test roots only. Keep journals, receipts, locks, archives, and tests body-safe and outside static inputs. Preserve all existing acquisition, transcript, duplicate, Source Health, Atomic Evidence, and record-validation behavior.

Validation:

- run the new focused domain/repository/recovery tests;
- run the existing publication review, duplicate, source-fidelity, transcript-readiness, review-event, acquisition-outcome, Atomic Evidence, static-leak, and record-validation checks listed in `focused-validation.txt` and `record-validation.txt`;
- do not run collection or mutate application data.

Deliver a bounded commit, clean worktree, exact test counts, files changed, and a continuation prompt for slice 3. Push only the new branch non-destructively. Do not create a PR, merge, deploy, publish, approve, or run a canary.
