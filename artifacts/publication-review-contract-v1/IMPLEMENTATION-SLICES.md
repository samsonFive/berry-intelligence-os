# Publication Review Contract V1 implementation slices

Implement these slices in order. Each slice must preserve existing trusted data and run focused tests before the next begins.

## Slice 1: Pure domain contract

Add typed states, commands, eligibility results, blocker/warning codes, content-digest rules, deterministic identity rules, and transition tests. No routes or repository writes. Test every content-matrix row and invalid transition.

## Slice 2: Review repository and recovery primitives

Add a publication-review repository adapter over current inbox files, version compare-and-set, per-draft locking, idempotency receipts, durable private promotion journal, archive semantics, and recovery tests with injected failures. Keep all runtime records gitignored and outside static inputs.

## Slice 3: Boundary-safe command service

Implement revise, approve, reject, defer, correction, return, and duplicate commands. Approval writes only the strict trusted-publication compatibility profile with empty `fact_ids` and no graph side effects. Reuse existing duplicate normalization and JSON atomic-write helpers where their behavior matches this contract.

## Slice 4: Compatibility adapters

Route existing HTML actions and any review CLI through the command service. Replace free-text actor authority with authenticated identity. Keep legacy read projections while mapping canonical states explicitly. Prevent `ReviewPublishService.publish()` from being a production bypass.

## Slice 5: Trust and static projections

Make Today, reports, company coverage, static build, and qualified Atomic extraction consume the strict trust/content projection. Add leak tests for drafts, journals, events, private bodies, limited-content records, and Atomic proposals.

## Slice 6: Operator UI

Build the queue/detail/actions from `UI-DATA-CONTRACT.md`. Keep one-item commands, explicit warning acknowledgments, stale-review reloads, and separated operational counters. This is a separate implementation checkpoint.

## Slice 7: Corrections and withdrawal

Only after product authorization, add post-approval corrections/withdrawal with a new review cycle, append-only events, downstream invalidation, and static behavior. Do not fold this into initial promotion implementation.

## Integration constraints

- Do not migrate or rewrite historical trusted records as part of V1.
- Do not create a parallel canonical publication store.
- Do not import live/generated review records in tests.
- Use temporary fixtures and verify no production dependency on them.
- Preserve acquisition-outcome, transcript, duplicate, Source Health, and Atomic-review behavior.
- Run record validation and the focused publication/review/acquisition/transcript/static suites after each relevant slice.
