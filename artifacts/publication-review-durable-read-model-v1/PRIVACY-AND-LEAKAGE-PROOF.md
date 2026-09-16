# Privacy and leakage proof

## Full acquired article body — never exposed

Neither `queue_item_view()` nor `get_detail()` includes the draft's
`article`/`transcript` fields at all — only already-computed
classifications (`content_class`, `acquisition_classification`) and,
in `get_detail()` only, a bounded `excerpt` from `hydrated_excerpt()`.

`hydrated_excerpt()` truncates to `EXCERPT_MAX_CHARS = 500` characters and
sets `truncated: True` whenever the real body/transcript text exceeds
that bound — which every realistic acquired article does. This matches
the contract's own recommended default ("public metadata plus an
approved excerpt/link; full body redistribution requires a separate
legal/product decision") and this mission's literal "does not expose full
acquired article bodies" requirement, applied to every view this module
produces, not only a public/static one.

### Direct, executed proof (not an absence-of-field inference)

- `test_queue_item_never_contains_article_paragraphs_or_transcript_segments`:
  serializes a real queue row to JSON and asserts the literal body text
  (`"word word word"`, from a 300-word real fixture) does not appear
  anywhere in it, and that `"article"`/`"paragraphs"` are not even keys.
- `test_detail_view_never_contains_the_full_article_text`: same check
  against the full detail view (which does include the bounded excerpt) —
  the *complete* 300-word body string still never appears, and the
  excerpt is confirmed `truncated: True` and no longer than
  `EXCERPT_MAX_CHARS`.
- `test_hydrated_excerpt_is_bounded_and_never_the_full_body`: the excerpt
  function itself, called directly, returns exactly `EXCERPT_MAX_CHARS`
  characters for a body longer than that bound.
- `test_short_body_excerpt_is_not_marked_truncated`: a body shorter than
  the bound is returned whole and correctly marked `truncated: False` —
  proving the truncation logic is real, not a hardcoded flag.
- `test_readonly_ui_compatible_projection_also_never_leaks_full_body`:
  the additive compatibility-alias layer (`to_readonly_ui_compatible()`)
  is checked independently, since it copies most fields from the
  canonical view — confirming the alias step itself introduces no new
  leak.

## Actor / decision-event redaction

`_serialize_decision_event()` whitelists exactly eight fields (`command`,
`actor_id`, `occurred_at`, `reason_category`, `comment`, `resulting_state`,
`resulting_version`, `event_id`). The real, stored decision-history entry
(written by `publication_review_command.py`) additionally carries
`idempotency_key` — proven excluded by
`test_raw_repository_event_has_more_fields_than_the_serialized_view`,
which compares the raw stored dict's key set against the serialized
view's key set and asserts the former is a strict superset.
`test_decision_event_serialization_only_exposes_the_whitelisted_fields`
asserts the exact key set on a real, produced event.

## Unrelated private records

This module never reads any repository other than the one
`DurableReviewRepository` instance it is given, and never reads `inbox/`
directly. `get_detail()`'s optional `evidence_reader` parameter is used
**only** to call `.get(publication_id)` for the one specific id a draft's
own `publication_binding` names — it is never used to list or scan the
trusted evidence store, so no unrelated trusted record is ever touched or
exposed through this module.

## Zero mutation, proven by tree snapshot

`test_reads_never_mutate_the_durable_repository_or_data_dir` seeds two
drafts, approves one (a real, full command-service transaction), takes a
byte-for-byte snapshot of every file under the durable `review_state/`
root, the `data/` directory, and the `inbox/` directory, then calls every
read function this module exposes (`list_queue`, `get_detail` twice,
`status_summary`, `promotion_status`, `hydrated_excerpt`), and asserts the
snapshot is identical afterward. This is a direct proof, not an inference
from "the functions don't call `.create`/`.update`" — every byte of every
file is compared.
