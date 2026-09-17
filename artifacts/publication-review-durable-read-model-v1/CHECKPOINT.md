# Publication Review Durable Read Model V1 — checkpoint (2026-09-16)

Branch: `feature/publication-review-durable-read-model-v1` in
`C:/Users/Johnny/Downloads/sscanar/berry-intelligence-os-publication-review-durable-read-model-v1`,
based exactly on `cf6d19319363dadd20d7182d5b8aaf3f97726d7b`
(`feature/publication-review-command-service-v1`, itself based on
`integration/competitor-intelligence-wave3`). No merge, push, deploy, PR,
or canonical/live data mutation performed. The frozen `cf6d193` branch was
not amended, rebased, or force-pushed.

## Mission

Build the backend read/query seam translating durable publication-review
state into queue, detail, status, decision-history, and correction-
history shapes for a future UI — read-only, no HTTP wiring, no decision
controls, no canonical mutation.

## What was built

1. **`app/services/publication_review_query.py`** — the read model:
   `list_queue()` (stable-ordered, filterable, paginated),
   `get_detail()` (full single-item view including decision/correction
   history, publication-binding verification, supersession metadata,
   promotion status, and a bounded excerpt), `status_summary()`,
   `decision_history_view()`/`correction_history_view()`,
   `promotion_status()` (honest staged-transaction visibility),
   `hydrated_excerpt()` (bounded, never the full body), and
   `to_readonly_ui_compatible()` (an additive alias layer for the
   inspected, unmerged `d19ee0a` UI reference's own field-name guesses).
2. **`tests/test_publication_review_query.py`** — 33 focused tests
   covering every required scenario (see `TEST-RESULTS.md`).
3. This artifact directory.

Nothing else was created or modified: no route, no template, no CSS, no
authentication code, no canonical/`inbox`/`data` mutation.

## Verification

- New focused tests: **33 passed**, 0 failed.
- Existing publication-review domain/repository/command/crash-recovery/
  migration/static-safety suites: **143 passed, 9 skipped** (intentional),
  0 failed — unaffected.
- Existing read-only UI tests (`d19ee0a`): **could not be run** — that
  branch is frozen, unmerged, and neither the module nor its test file
  exists in this working tree. Inspected via `git show` only.
- `scripts/validate_records.py`: all validated records passed.
- Static build / private-leakage checks (`tests/test_build_static.py`):
  **6 passed**, unaffected. This mission's own leakage proof lives
  directly in `tests/test_publication_review_query.py` (see
  `PRIVACY-AND-LEAKAGE-PROOF.md`).

## Contract differences from the inspected `d19ee0a` reference

See `CONTRACT-MAPPING.md` for the full field-by-field mapping. Headline
differences: `d19ee0a`'s own state-name mapping has no case for
`superseded_duplicate`; it reads `article`/`transcript` fields directly
for content classification and full-body extraction, which this module
deliberately never includes in its output (only classifications and a
bounded excerpt); and its warning/blocker shape carries human-readable
`message` text this module synthesizes generically rather than storing
canonically.

## Required statements

**DURABLE REVIEW STATE READABLE: YES**
**QUEUE AND DETAIL CONTRACT PRODUCED: YES**
**STAGED TRANSACTIONS EXPOSED AS COMMITTED: NO**
**FULL ARTICLE BODY LEAKAGE: 0**
**CANONICAL/LIVE DATA MUTATED: 0**
**FROZEN COMMAND BRANCH MODIFIED: NO**

## What is deliberately NOT done here

- No HTTP route, CLI, or UI wiring.
- No decision/command invocation of any kind from this module.
- No authentication/authorization design for the read side.
- No merge of, or commit onto, `feature/publication-review-readonly-ui-v1`
  (`d19ee0a`) or `feature/publication-review-command-service-v1` (`cf6d193`).
- No rehearsal/test fixture imported into production code — every test
  fixture in this mission lives in `tests/test_publication_review_query.py`
  itself, built via the real command service against `tmp_path` stores.
- No PR, merge, force-push, or deployment.

## Next concrete steps

See `INTEGRATION-NOTES.md`.
