# Contract mapping

Maps `app.services.publication_review_query` (this mission) against the
three real, authoritative inputs and the one *inspected-only* reference.

## Authoritative inputs (all at frozen `cf6d193`)

| Source | What it defines | How this module uses it |
|---|---|---|
| `publication_review_domain.py` | Review states, commands, eligibility, digests, identity | Called directly for eligibility (`check_eligibility`), permitted next commands (`permitted_commands`), and state-name vocabulary (`REVIEW_STATES`, `SUPERSEDED_DUPLICATE`, etc.) — never reimplemented |
| `publication_review_repository.py` | `DraftState`, `DurableReviewRepository` | The only data source this module reads from — `get_draft_state`, `list_draft_states`, `pending_transactions`, `journal_phases_present` |
| `publication_review_command.py` | Command service, decision semantics | Not called for any decision method (`approve_publication`, etc.) — only its own encoding convention (`supersede_publication_duplicate`'s `reason_category = "survivor=<id>:<basis>"`) is decoded, since that string lives in the durable `decision_history` this module reads |

## Inspected-only reference (frozen, unmerged, never imported)

`feature/publication-review-readonly-ui-v1` at `d19ee0a3` —
`app/services/publication_review_readonly.py`'s `project_queue_item()`/
`project_detail()`. This file does **not** exist in this branch's working
tree (confirmed: `ls app/services/publication_review_readonly.py` fails
here) and is never imported by `publication_review_query.py`. It was read
via `git show d19ee0a:app/services/publication_review_readonly.py` only,
to design a compatible output shape.

### Field-by-field alignment

`publication_review_readonly.py`'s own functions read a generic "draft"
dict with a documented fallback chain per field (e.g. `queue_state` first,
else derived from `status`). `to_readonly_ui_compatible()` (this module)
produces a dict where the **first** name in each fallback chain is
already populated with real data, so that reference file's own functions
— if a future mission wires them to this module's output — would need no
change to consume it correctly:

| Grok's first-choice field | This module's real value | Alignment |
|---|---|---|
| `queue_state` | `domain`'s own review state string (`pending_review`/`approved`/.../`superseded_duplicate`) | **Exact** |
| `draft_id` | `DraftState.id` | **Exact** |
| `version` | `DraftState.version` | **Exact** |
| `headline` | `draft["title"]` | **Exact** (Grok's field name differs; alias provided) |
| `publication_date` | `draft["published_date"]` | **Exact** (alias provided) |
| `captured_at` | `DraftState`'s underlying `captured_date` | **Exact** (alias provided) |
| `entity_ids` (fallback) | `draft["entity_ids"]` | **Exact** |
| `duplicate_of` (fallback) | `eligibility.duplicate_of` | **Exact** |
| `provenance_warnings`/`blocking_warnings` | Synthesized `{code, message, level}` from `eligibility.warnings`/`.blockers` | **Compatible shape, generated message text** — this module's own canonical `warnings`/`blockers` fields are plain code lists; the wrapped-dict shape is produced only inside `to_readonly_ui_compatible()` |
| `source_completeness` (its `.class` read) | `{"class": content_class}` | **Compatible** — a minimal stand-in, not the full `source_completeness()` payload |
| `article`/`transcript` (used by Grok's own `classify_content`/`_extract_body`) | **Not reproduced** | **Documented gap** — see below |

### Documented gaps / contract differences from `d19ee0a`

1. **`superseded_duplicate` is unknown to Grok's `_review_state()`.** Its
   fallback mapping (`pending`/`draft`/`review_ready` → `pending_review`,
   `approved`/`published` → `approved`, etc.) has no case for
   `superseded_duplicate` — an unmapped status falls through to
   `return status or "pending_review"`, so a superseded draft would render
   with the raw string `"superseded_duplicate"` rather than a recognized
   state. Not fixed here (that file is frozen and unmerged); documented so
   a future wiring mission knows to add the case.
2. **Grok's `classify_content()`/`_extract_body()` read `article`/
   `transcript` directly off the draft dict.** This module deliberately
   does **not** include those keys in its queue/detail views (per this
   mission's own "does not expose full acquired article bodies" rule) —
   only `content_class`/`acquisition_classification` (already-computed
   classifications) and a bounded `excerpt`. A future wiring mission has
   two honest options: (a) extend Grok's UI to read `content_class`
   directly (it already prefers `source_completeness.class` first, which
   this module's `to_readonly_ui_compatible()` populates), or (b) decide,
   as a separate product/security decision, that the private operator
   detail view is allowed to see full text and add an explicitly-
   authorized hydration call. This module takes no position on that
   decision — it only refuses to leak the body by default.
3. **Grok's warnings/blockers carry human-readable `message` text this
   module does not canonically store.** `to_readonly_ui_compatible()`
   synthesizes a generic message from the code
   (`code.replace("_", " ").capitalize()`) — adequate for the fallback
   case, but a real UI would likely want curated copy per code. Not a
   blocking gap; noted for `INTEGRATION-NOTES.md`.
4. **No `duplicate.candidate_title`/`similarity` fields.** This module's
   `domain.check_eligibility()` returns only a duplicate *id*
   (`duplicate_of`), never a title or similarity score (per
   `article_dedup.find_duplicate_article()`'s own "no fuzzy identity"
   rule — there is no similarity score to report). Grok's `_duplicate()`
   fallback (`duplicate_of`/`probable_duplicate_of`) already tolerates a
   bare id with no title/similarity.

## Why this is not "a second competing review contract"

Every field this module ever returns is either (a) read directly off
`DraftState`, (b) computed by calling `publication_review_domain`'s own
functions, or (c) a pure, additive alias/wrapper for compatibility
(`to_readonly_ui_compatible()`), clearly separated from the canonical
shape. No new review-state vocabulary, no new eligibility rule, and no new
identity/duplicate rule was introduced.
