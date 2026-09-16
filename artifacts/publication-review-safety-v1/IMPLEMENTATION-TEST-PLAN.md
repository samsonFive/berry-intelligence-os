# Implementation test plan

Implement future protections in this order:

1. Add a publication draft version and actor policy. Use a deterministic
   restored podcast draft fixture, submit missing/bot/AI actors and stale
   versions, and assert 4xx plus unchanged `data/`, draft, and event trees.
2. Add a table-driven state machine test for pending, in-review, rejected,
   superseded, published, and already-published states. Every invalid edge must
   have zero writes.
3. Add fault-injection tests around each publish write boundary. Assert the
   rollback invariant for Evidence, Facts, entities, attachments, draft, and
   review event; retry must be safe.
4. Add duplicate policy fixtures: identical deterministic identity, conflicting
   identity, duplicate URL/different id, and content hash/different URL. Encode
   the chosen policy before implementation.
5. Add source/transcript version binding tests. Metadata-only save followed by
   body upgrade and transcript replacement must require re-review.
6. Add provenance tamper/corruption fixtures. The loader and review queue must
   surface a blocked item with diagnostics and never silently skip it into a
   publishable state.
7. Add job-admission and static-build consistency tests. Pending publications
   cannot feed Evidence generation; a partial trusted JSON input fails the
   build without public output.
8. Run every future test under a mutation-detecting harness using temporary
   data/inbox roots. The committed `data/` tree and operator inbox must remain
   byte-identical.

Required test evidence for each implementation PR: command, exact fixture,
expected state transitions, test count, duration, and before/after tree digest.
