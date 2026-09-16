# Publication Review Command Service V1 — checkpoint (2026-09-16)

Branch: `feature/publication-review-command-service-v1` in
`C:/Users/Johnny/Downloads/sscanar/berry-intelligence-os-publication-review-command-service-v1`,
based on `c95c05e51b8247a0b22f417a877088c8d7f20e6b`
(`integration/competitor-intelligence-wave3`). No merge, push, deploy, PR,
or canonical/live data mutation performed.

## Mission

Implement the smallest production-safe backend capable of maintaining a
durable publication-review queue and executing explicit single-item human
review decisions, per `design/publication-review-contract-v1`
(`4c126a6e15d448c4be2f0dae73ddce879fbc0346`). No UI, no live promotion, no
trusted Atomic Evidence.

## What was built

Slices 1-3 of the contract's own `IMPLEMENTATION-SLICES.md`, plus the
specific static-safety proofs and migration adapter this mission's own
scope names:

1. **`app/services/publication_review_domain.py`** — pure domain: six
   canonical review states, eight commands, an exhaustive transition
   table, the full eligibility content matrix (readable/partial/
   transcript/structured-registry/thin-metadata/navigation-shell/
   retryable/unsupported/malformed/duplicate), deterministic publication
   identity, and two independent digests (content, provenance).
2. **`app/services/publication_review_repository.py`** — a durable,
   filesystem-backed review-state store (`review_state/`, resolved the
   same `BIOS_RUNTIME_DIR` way `data/`/`inbox/` already are), with
   compare-and-set versioning, per-draft exclusive locking with
   stale-lock reclaim, idempotency receipts, and a staged promotion
   journal. No external infrastructure dependency introduced.
3. **`app/services/publication_review_command.py`** — the boundary-safe
   command service: structured human-actor authorization, all eight
   contract commands, the staged promotion protocol for approval, and
   crash-recoverable reconciliation. Never calls
   `ReviewPublishService.publish()`.
4. **`app/services/publication_review_migration.py`** — one explicit,
   single-item development-inbox import adapter (never a directory scan,
   never called against live data in this mission).
5. Six new focused test files (see `TEST-RESULTS.md` for exact counts).

## Verification

- New focused tests: **143 passed, 9 skipped** (intentional — a
  parametrized exhaustive cross-product test skips pairs already covered
  by the explicit valid-transition list).
- Existing publication/review/duplicate/source-fidelity/transcript-
  readiness/review-event/Atomic-Evidence/trust-feedback/acquisition/
  transcript suites: **291 passed, 0 failed** (unaffected by this
  mission's additions).
- `scripts/validate_records.py`: all validated records passed.
- `scripts/wave2_contract_gate.py --mode quick`: see `TEST-RESULTS.md` for
  the exact count/duration recorded from this run.
- Static build + public-safety: a real `scripts/build_static.py` run
  (the same mechanism `tests/test_build_static.py` uses) proves an
  approved publication renders correctly while the durable review-state
  store, an unrelated pending draft, and the full acquired article body
  text never appear anywhere in output.

## A real, pre-existing gap found and documented, not fixed

`app.services.source_body.classify_source_body()`'s `access_limited`
state only checks `discovery_provenance.failure_category`; real
acquisition output stores `acquisition_failure_category` instead
(confirmed: `source_completeness()` itself checks both keys). This makes
`access_limited` effectively unreachable for real drafts. Not fixed —
`source_body.py` is outside this mission's scope, and altering
classification code as an incidental side effect of building this service
would itself violate the "do not alter extraction code" discipline this
mission chain has followed since `readable-acquisition-canary-v1`. Worked
around in `publication_review_domain.check_eligibility()` by reading
`source_completeness()`'s own already-correct `retryable` field directly,
with the discrepancy documented in a code comment at the point of use and
in `IMPLEMENTED-CONTRACT-MAP.md`.

## Required statements

**DURABLE REVIEW STATE IMPLEMENTED: YES**
**AUTHORIZED HUMAN REQUIRED: YES**
**OPTIMISTIC CONCURRENCY ENFORCED: YES**
**IDEMPOTENT COMMANDS ENFORCED: YES**
**CRASH RECOVERY TESTED: YES**
**ENTITIES/FACTS/RELATIONSHIPS CREATED BY APPROVAL: 0**
**TRUSTED ATOMIC EVIDENCE CREATED BY APPROVAL: 0**
**LIVE/CANONICAL RECORDS MUTATED: 0**

## What is deliberately NOT done here

- No HTTP route, CLI, or UI was built or modified — no production
  mutation route is exposed to users.
- No compatibility-adapter wiring (`ReviewPublishService.publish()` still
  exists unchanged and unremoved; the contract's Slice 4 recommends
  eventually routing existing HTML actions through this new service, but
  that is out of this mission's own scope).
- No post-approval correction/withdrawal command (Slice 7) — not
  authorized by this mission's brief.
- No live inbox draft was imported; the migration adapter was only
  exercised against hand-built test fixtures.
- No canonical entity/relationship/Fact/Signal/Assessment/Recommendation/
  Atomic Evidence record was created, modified, or deleted, by this
  service or by any test.
- No PR, merge, force-push, or deployment.

## Next concrete steps

See `NEXT-AGENT-PROMPT.md`.
