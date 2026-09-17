# Next-agent prompt

You are the implementation owner for the next bounded Berry Intelligence OS publication-review wave.

Start only from the exact verified remote head of `integration/publication-review-wave4` recorded in its final checkpoint. Create a new isolated worktree and a new branch. Do not amend, rebase, or add commits to the frozen Wave 4 branch.

Read first:

- `artifacts/publication-review-wave4/CHECKPOINT.md`
- `artifacts/publication-review-wave4/EXACT-COMMIT-MAP.md`
- `artifacts/publication-review-wave4/CONTRACT-IMPLEMENTATION-MAP.md`
- `artifacts/publication-review-wave4/COMBINED-CURRENT-STATE-MATRIX.md`
- `artifacts/publication-review-wave4/NEXT-WAVE-RECOMMENDATION.md`
- the final Publication Review Contract V1 artifacts

Wave 4 contains the durable command-service backend and a private read-only review UI. The UI decision controls are intentionally disabled and disconnected. There is no production HTTP, CLI or UI mutation adapter. Do not infer authorization to connect one from the presence of the backend.

Before implementation, confirm the next mission explicitly authorizes production decision wiring. If it does, keep the slice narrow:

1. Configure the durable review repository as shared operational state.
2. Add one authenticated adapter to the existing command service.
3. Require an authorized human actor, expected version, content digest, provenance digest and idempotency key.
4. Preserve immutable decision/publication binding, durable receipts, recoverable staging and complete-state visibility.
5. Keep claim/Evidence review separate. Do not create or update entities, facts, relationships, signals, assessments, recommendations or trusted Atomic Evidence.
6. Do not add auto-publication, bulk approval, legacy bypasses or direct draft-to-Evidence promotion.
7. Connect UI controls only when explicitly included in the mission and only after adapter tests pass.

Validate authorization, optimistic concurrency, provenance tampering, idempotent retry, process restart, crash injection at every write boundary, multi-worker behavior, prohibited side effects, static/private boundaries, Today/reader regressions and browser mutation traffic. Take before/after snapshots of canonical and trusted data. Compare the complete repository suite against the Wave 4 baseline by exact nonpassing node ID.

Keep the documented `source_body.access_limited` reporting discrepancy and the 21 inherited Wave 3 suite failures as separate work unless the mission expressly includes them.

Do not deploy, merge, publish, approve live records, import generated/live decisions, or force-push. Produce a clean checkpoint with exact commits, tests, browser evidence, mutation proof and a continuation prompt before using the full usage window.
