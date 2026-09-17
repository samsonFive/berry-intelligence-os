# Query model

`app.services.publication_review_query` — every function is pure with
respect to the durable repository: none of them ever calls
`compare_and_set`, `create_draft_state`, `write_journal_phase`,
`lock_draft`, or any other mutating method. Every function takes a
`DurableReviewRepository` instance (or a single `DraftState`) and returns
plain dicts/dataclasses.

## Functions

| Function | Returns | Purpose |
|---|---|---|
| `list_queue(repository, *, state=None, content_class=None, page_size=50, cursor=None)` | `QueuePage` | Stable-ordered, filterable, paginated queue |
| `get_detail(repository, draft_id, *, evidence_reader=None)` | `dict \| None` | Full single-item detail view |
| `status_summary(repository)` | `dict` | Total + per-state counts + count of drafts with a pending transaction |
| `decision_history_view(draft_state)` | `list[dict]` | Full, redacted, chronological decision history |
| `correction_history_view(draft_state)` | `list[dict]` | Just the `request_publication_correction`/`submit_publication_correction` steps |
| `promotion_status(repository, draft_id)` | `dict` | Whether an approval transaction is mid-flight/resumable — never "approved" |
| `hydrated_excerpt(draft_state)` | `dict` | A bounded (≤500 char) excerpt, never the full body |
| `queue_item_view(draft_state, *, repository)` | `dict` | The body-free per-item shape `list_queue()` and `get_detail()` both build on |
| `to_readonly_ui_compatible(view)` | `dict` | Additive alias layer for `d19ee0a`'s inspected field-name guesses (see `CONTRACT-MAPPING.md`) |

## Queue: ordering, filtering, pagination

**Ordering** is `(updated_at, id)` descending — most-recently-updated
first, `id` as a deterministic tiebreaker so two records sharing a
timestamp never reorder between reads (`test_repeated_queue_reads_are_identical`).
This module deliberately does not implement an "attention rank" or any
other presentation-layer scoring — that is exactly the kind of UI-owned
concern `publication_review_readonly.py` already has its own opinion
about (`_attention_rank`); this read model stays neutral so any UI can
apply its own ranking on top of a stable base order.

**Filtering**: `state` (exact match against one of the six canonical
review states) and `content_class` (exact match against
`source_completeness()`'s own class vocabulary) — both narrow the
underlying `DurableReviewRepository.list_draft_states()` call directly,
no client-side-only filtering hack.

**Pagination**: an opaque cursor, `"<updated_at>\x1f<id>"` — a real
position in the stable sort order, not an offset count. Resuming from a
prior page's `next_cursor` always continues exactly where it left off
even if records were added or removed in between
(`test_pagination_cursor_resumes_deterministically`).

## Detail view: what it adds beyond the queue row

- `source_url`, `source_type`, `media_format`, `summary`, `why_it_matters`,
  `entity_ids`/`berry_ids`/`geography_ids` — the review-relevant metadata
  fields (never the full body).
- `content_digest`/`provenance_digest` (aliased also as
  `review_content_digest` for the digest name the contract's own envelope
  uses) — read straight off `DraftState`.
- `decision_history` / `correction_history` — see below.
- `publication_binding` — the raw `{publication_id, committed_at,
  transaction_id}` `DraftState` already stores once approved, plus
  `publication_verified` (`True`/`False`/`None` — see
  `STATE-VISIBILITY.md`).
- `supersession` — parsed `{survivor_id, identity_basis}` when the state
  is `superseded_duplicate`, else `None`.
- `promotion_status` — see `STATE-VISIBILITY.md`.
- `excerpt` — see `PRIVACY-AND-LEAKAGE-PROOF.md`.
- `is_legacy_import` — a best-effort signal (see docstring in the module)
  that this record originated from `publication_review_migration.import_inbox_draft()`
  and has never had a real decision applied.

## Decision history and correction history

`decision_history_view()` returns every entry in `DraftState.decision_history`
in the order they were recorded (the list is itself append-only by
construction — every command in `publication_review_command.py` appends
exactly once, never rewrites a prior entry), each passed through
`_serialize_decision_event()`'s field whitelist (see
`PRIVACY-AND-LEAKAGE-PROOF.md`). `correction_history_view()` is the same
list filtered to `request_publication_correction`/
`submit_publication_correction` only — a genuinely distinct, named shape
per this mission's own requirement, not merely "the general history, read
carefully."

## Status summary

`{total, by_state: {<each of the six states>: count}, drafts_with_pending_transaction}`
— the last field surfaces, at the aggregate level, how many drafts have
real, durable, uncommitted promotion work outstanding, without claiming
any of them are approved.
