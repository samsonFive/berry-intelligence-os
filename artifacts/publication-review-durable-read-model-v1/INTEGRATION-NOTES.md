# Integration notes — recommended later wiring seam

This mission built no route, no template, and no auth. Here is exactly
where a future wiring mission should connect, and what it still needs to
decide.

## The seam itself

```python
from app.services.publication_review_query import list_queue, get_detail, status_summary
from app.services.publication_review_repository import DurableReviewRepository, resolve_review_state_dir

repository = DurableReviewRepository(resolve_review_state_dir())
page = list_queue(repository, state="pending_review", page_size=25)
detail = get_detail(repository, draft_id, evidence_reader=repositories.evidence)
```

A future `GET /api/publication-reviews` route (the exact path
`COMMAND-CONTRACTS.md`'s own "Proposed adapter surface" names) would call
`list_queue()`; `GET /api/publication-reviews/{draft_id}` would call
`get_detail()`. Both are already pagination/filter-ready — the route
layer's only job would be translating query-string parameters into this
module's `state`/`content_class`/`page_size`/`cursor` arguments and
serializing the result to JSON, which is already plain-dict-shaped.

## What a wiring mission still needs to decide (not decided here)

1. **Actor/session integration for the read side.** This module takes no
   actor at all — reads require no authorization in this mission's own
   design (`COMMAND-CONTRACTS.md`: "Inspection does not imply a human
   decision"). A future mission should confirm whether the *read* surface
   itself needs any authentication (e.g., "must be a signed-in operator,
   any permission level" vs. fully open) — this mission takes no position.
2. **Full-body hydration for an authorized reviewer.** `hydrated_excerpt()`
   deliberately returns only a bounded excerpt (see
   `PRIVACY-AND-LEAKAGE-PROOF.md`). If the eventual UI needs a reviewer to
   read the complete article/transcript to decide, that requires an
   explicitly separate, explicitly authorized accessor — `DraftState.draft`
   itself (read directly from the repository) already has the full text;
   this mission does not build a route for it, since that is a genuine
   authorization/product decision (matching the contract's own "a
   separately authorized content locator or hydrated body" language), not
   a read-model shape decision.
3. **Whether to wire `to_readonly_ui_compatible()` at all.** It exists as
   a convenience for anyone who wants to reuse `d19ee0a`'s own
   `project_queue_item()`/`project_detail()` logic once that branch is
   eventually merged. If a future mission instead builds a fresh
   presentation layer directly against this module's canonical shape
   (the `queue_item_view()`/`get_detail()` field names), the alias layer
   is simply unused — nothing depends on it.
4. **`superseded_duplicate` UI support.** `d19ee0a`'s own state mapping
   has no case for it (see `CONTRACT-MAPPING.md`, gap #1). A wiring
   mission touching that file will need to add one.
5. **Warning/blocker message copy.** `to_readonly_ui_compatible()`
   synthesizes generic messages from blocker/warning codes. A real UI
   would likely want curated, reviewer-facing copy per code — a small,
   separate content task, not a read-model concern.
6. **Reconciliation trigger.** This mission's read model can *observe* a
   pending transaction (`promotion_status()`) but does not trigger
   `PublicationReviewCommandService.reconcile_pending_transactions()`. A
   wiring mission should decide whether the read surface should show a
   "retry/reconcile" action (which would be a *command*, out of this
   mission's read-only scope) or whether reconciliation stays a separate
   operational action entirely.

## What does NOT need further decision

The queue/detail/status/history shapes, pagination, ordering, digest
exposure, and privacy boundaries are all real, tested, and ready to be
called by an HTTP route today — this mission's own scope explicitly
excludes writing that route, not designing its data contract.
