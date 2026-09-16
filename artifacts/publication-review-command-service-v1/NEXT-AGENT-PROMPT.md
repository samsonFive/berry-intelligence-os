# Continue Berry Intelligence OS work — compatibility adapter and trust projection

Work in a fresh isolated worktree from wherever
`feature/publication-review-command-service-v1` or its integrated
successor lands. Read `CHECKPOINT.md`, `IMPLEMENTED-CONTRACT-MAP.md`,
`STATE-STORAGE.md`, `COMMAND-API.md`, `AUTHORIZATION.md`, and
`CRASH-RECOVERY.md` first, plus `design/publication-review-contract-v1`'s
own `IMPLEMENTATION-SLICES.md` for Slices 4-7.

## Settled facts — do not re-derive

1. Slices 1-3 (pure domain, durable repository, boundary-safe command
   service) are implemented and tested (149 new focused tests across the
   contract's own required categories). Do not rebuild them from scratch
   — extend `app/services/publication_review_domain.py`/
   `_repository.py`/`_command.py` additively.
2. `ReviewPublishService.publish()` still exists, unchanged, and is still
   what `/review/{id}/publish` calls. This mission proved (via a direct
   monkeypatch test, not just an absence-of-import check) that the new
   command service never reaches it. The old route is still a
   trust-crossing bypass relative to the contract until Slice 4 happens.
3. The durable review-state store lives at `review_state/` (local dev,
   gitignored) or `$BIOS_RUNTIME_DIR/review_state` (persistent-mount
   deployments) — a new, parallel directory, never `inbox/` or `data/`.
4. A real, pre-existing gap in `app.services.source_body.classify_source_body()`
   (`access_limited` state keys off the wrong field name for real
   acquisition output) was found and documented but not fixed — see
   `CHECKPOINT.md`. Fixing it would be a legitimate, separate,
   narrowly-scoped change; do not fold it into an unrelated mission.
5. No live inbox draft has ever been imported through
   `publication_review_migration.import_inbox_draft()` — it has only run
   against hand-built test fixtures.

## Open items for a future mission (per the contract's own slice order)

1. **Slice 4 — compatibility adapters.** Route `/review/{id}/publish`,
   `/reject`, `/save`, and any review CLI through
   `PublicationReviewCommandService` instead of
   `ReviewPublishService.publish()`. This requires: (a) a real
   `ActorDirectory` implementation backed by the existing session/login
   mechanism (`app/runtime_config.py`'s `BIOS_REVIEW_USERNAME`/
   `BIOS_SESSION_SECRET`), since today's route only checks a nonblank
   form field; (b) a decision on how the HTML form supplies
   `expected_version`/`reviewed_content_digest`/`idempotency_key` (a
   hidden field re-rendered on every page load is the natural choice);
   (c) explicitly deciding what happens to `ReviewPublishService.publish()`
   itself once nothing calls it for publication approval anymore (it is
   still used for `approve_claim`/`reject_claim`, which are a separate,
   already-correctly-separated trust decision this mission did not touch).
2. **Slice 5 — trust and static projections.** This mission's own
   static-safety tests prove no leak exists *today*, but Today/reports/
   company coverage were not updated to consume a `limited_content`-aware
   projection (the contract's own requirement that limited-content
   publications be excluded from readable/current-coverage counts). Add
   that once real limited-content approvals exist in production.
3. **An explicit reconciler entry point.** `reconcile_pending_transactions()`
   exists and is tested but nothing calls it automatically (deliberately,
   per this mission's own scope — "never automatically mid-request"). A
   future mission should decide whether it runs at application startup,
   via a scheduled job, or via an explicit operator action, and wire that
   decision in.
4. **Fix or formally accept `classify_source_body()`'s `failure_category`/
   `acquisition_failure_category` key mismatch** (see `CHECKPOINT.md`) —
   a small, real, separately-scoped correctness fix.
5. **Slice 7 — post-approval correction/withdrawal** — only after the
   product decisions `DECISION-LOG.md` itself lists as still required
   (roles, public-projection behavior, downstream invalidation) are made.

## Runtime / housekeeping

Use `../berry-intelligence-os/.venv/Scripts/python.exe`. Git needs
`-c safe.directory=<worktree path>` per command. Every new test in this
mission uses `tmp_path`-rooted stores exclusively — follow that pattern
for any addition; never point a new test at the real `data/`/`inbox/`.
