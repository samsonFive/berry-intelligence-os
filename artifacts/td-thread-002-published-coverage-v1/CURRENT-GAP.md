# Current gap (as found on exact base)

Exact base: `c0de14c88960c22fee97a51fef0c71ffe386bcf9`.

## Live `/threads` universe

`story_thread_reader()` and `_intelligence_page_context()` built the candidate set from:

1. `list_pending_drafts()` (all non-rejected inbox drafts);
2. at most the currently viewed record, when that record was published or missing from pending.

`story_thread_reader()` then ran one-hop `expand_with_related()` against **all** published Evidence. That can attach a stored same-event link or an exact-title reprint to the **seed**, but it cannot assemble a trusted-only cluster unless the viewed record is already a hub for every member. `_intelligence_page_context()` did not expand at all, so `/intelligence/{id}` never advertised a trusted-only thread.

## What this is not

This is a **candidate-universe** gap, recorded as TD-THREAD-002. It is not permission to:

- merge on co-mention;
- loosen title similarity / Jaccard;
- widen date windows;
- infer same-event membership from berry type or region;
- turn a thread into a trust object.

Global Search still uses `_cheap_pending_threads()` (exact URL / exact normalized title of pending drafts only) and must not call `group_story_threads()` on the published feed. That search cost bound is separate and remains in force.
