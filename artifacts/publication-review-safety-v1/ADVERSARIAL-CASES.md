# Adversarial cases

These cases are implementation-ready test specifications, not claims that the
current system already handles every case.

1. **Double-click / timeout retry:** two identical publish requests for one deterministic draft id; inject a response timeout after commit; expect one trusted publication and one append-only publish event, with the retry classified as already published.
2. **Concurrent reviewers / stale browser:** two requests use the same draft version, one publishes and one rejects; expect one accepted transition, the loser gets a conflict/stale response, and no contradictory event.
3. **Crash points:** inject failures before/after entity update, Fact create, Evidence create, event append, attachment move, and draft delete; expect either complete publication or an intact retryable draft, never both draft and trusted record without an explicit idempotent result.
4. **Actor policy:** missing reviewer, bot actor, AI actor, and valid human actor; expect the first three blocked before any write and only the last admitted.
5. **Provenance:** missing source URL/identity/captured date, corrupted JSON, altered transcript hash, changed locator, and tampered discovery provenance; expect an actionable block and no trusted output.
6. **Duplicate identity:** same deterministic id with identical identity, same id with conflicting title/source/date, same source URL under another id, and same content under different URLs; expect respectively idempotent success, 409/no overwrite, policy-defined dedupe, and policy-defined distinctness.
7. **Supersession/body changes:** supersede a draft, save metadata then upgrade body, replace transcript after extraction; expect re-review/version conflict rather than silently approving stale material.
8. **Two trust stages:** publish a publication artifact without Facts, then attempt trusted-feed use and claim approval; expect approved source plus pending claim before the second human decision, then one approved Fact only after claim review.
9. **Audit/database split:** make review-event append fail after structured writes and make Evidence write fail after event append; expect compensation or an explicit durable repair state, never silent disagreement.
10. **Static partial read:** expose a truncated or concurrently replaced trusted JSON file to static build; expect build failure and no partially published HTML artifact.

Each future test should use `tmp_path`, deterministic fixtures, injected fault
points, and before/after digests for any trusted/runtime tree in scope.
