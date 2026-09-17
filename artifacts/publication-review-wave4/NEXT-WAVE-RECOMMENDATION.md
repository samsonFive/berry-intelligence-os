# Next-wave recommendation

Keep Wave 4 frozen and use its verified remote head as the exact base for a separately authorized production-wiring wave.

The next wave should connect one narrowly scoped authenticated adapter to the existing command service only after the durable review repository is configured as shared operational state. The adapter must require an authorized human actor, expected version, content digest, provenance digest and idempotency key. It must return the existing durable receipt and preserve recoverable staging. Legacy publication paths must not bypass these checks.

The UI should remain read-only until that adapter passes end-to-end authorization, concurrency, retry, crash-injection, complete-state isolation and prohibited-side-effect tests. When UI wiring is explicitly authorized, begin with a single-item decision flow. Preserve the separate claim/Evidence gate and prohibit entity, fact, relationship, signal, assessment, recommendation and trusted Atomic Evidence creation.

Required acceptance evidence for that wave:

1. A shared durable store survives restart and multiple workers.
2. Unauthorized, missing, AI, bot and service actors are rejected.
3. Stale version/content/provenance decisions are rejected without partial writes.
4. Repeated submissions return the same durable receipt.
5. Every injected stop between writes recovers to the prior or new complete state.
6. Static and public readers never observe the review queue or a partial promotion.
7. Browser traffic proves the UI calls only the intended authenticated adapter.
8. Protected canonical and trusted-data mutation snapshots remain zero except for the explicitly authorized publication records.

Track two separate cleanup items outside that production-wiring slice: reconcile the documented `source_body.access_limited` reporting discrepancy, and repair the 21 inherited Wave 3 full-suite failures/errors. Neither should be folded into the mutation wiring merely to broaden the branch.
