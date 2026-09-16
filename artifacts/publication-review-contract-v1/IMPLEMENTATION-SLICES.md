# Publication Review Contract V1 implementation slices

Implement these slices in order. Each slice must preserve existing trusted data and run focused tests before the next begins.

## Slice 1: Pure domain contract

Add typed states, commands, eligibility results, blocker/warning codes, content-digest rules, deterministic identity rules, and transition tests. No routes or repository writes. Test every content-matrix row and invalid transition.

## Slice 2: Review repository and recovery primitives

Define the authoritative shared durable production repository and keep the current inbox implementation only as a local/test adapter. Add version compare-and-set, cross-worker locking or equivalent serialization, immutable provenance bindings, idempotency receipts, private staged writes, one visibility commit marker, archive semantics, reconciliation, and fault-injection tests. Runtime state remains outside Git and static inputs, but it must survive restart and a new checkout.

## Slice 3: Boundary-safe command service

Implement revise, approve, reject, defer, correction, return, and duplicate commands. Approval stages only the strict trusted-publication compatibility profile with empty `fact_ids` and no graph side effects, binds it to the reviewed provenance/decision/event, and exposes it only through a completed commit marker. Reuse existing duplicate normalization and JSON atomic-write helpers only where their behavior matches this contract; exception-time compensation alone is insufficient.

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

## Blocking acceptance tests

All seven groups must pass before a production promotion route can be enabled:

1. **Durable review state:** create/acknowledge a draft, restart the service and open a clean checkout/second worker, then retrieve the same state/version/provenance. Deleting a local inbox projection must not delete authoritative work. Reproduce the candidate-pack reporting discrepancy shape and assert `review_ready` cannot be reported until durable persistence succeeds.
2. **Authorized human actor:** missing, free-text-only, AI, bot, service, expired, and unauthorized identities receive 401/403 with byte-identical durable/canonical/event trees. An authorized human actor succeeds only through an explicit command.
3. **Optimistic concurrency:** two reviewers act from the same version and digest; exactly one transition wins. Wrong version, stale body/transcript hash, and stale screen return 409 with no trust mutation.
4. **Immutable binding:** mutate source URL, acquisition outcome, body/transcript, content hash, entity links, or provenance after inspection; approval must fail until a new digest is inspected. A committed decision must verify the draft/version/provenance/publication hashes end to end.
5. **Idempotent retry:** duplicate click, retry after response loss, and restart/replay with the same key return one result, publication, decision, event, and marker. Reusing the key for another payload conflicts.
6. **Atomic or recoverably staged writes:** inject ordinary exceptions and hard-stop crashes before/after publication stage, decision stage, event append, marker publication, and archive. Before the marker, recovery preserves the prior complete view; after it, recovery preserves the new complete view and only finishes cleanup.
7. **Reader isolation:** run dynamic trusted queries, Atomic job admission, Today/report/company coverage, and a static build at every injected phase. They must see the prior complete state or new complete state only. A missing/mismatched referenced record fails closed and does not replace prior static output.

Every acceptance run uses temporary stores, captures before/after tree digests, and proves canonical/live data and the operator inbox are unchanged. Preserve explicit tests that acquisition/AI cannot auto-publish and publication approval cannot approve Atomic Evidence or create Facts.
