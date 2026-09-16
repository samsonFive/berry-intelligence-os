# Publication review command contracts

These contracts define application-service behavior. HTML forms, JSON routes, and future operator tools are adapters to the same commands and may not weaken their checks.

## Common command envelope

Every state-changing command carries:

- `draft_id`
- `actor_id`: immutable identity from the authenticated session, never free text
- `idempotency_key`: caller-generated, nonblank, at most 200 characters
- `expected_version`: the review version displayed to the operator
- `reviewed_content_digest`: required for decisions; identifies the material actually inspected
- `source_surface`: bounded enum such as `review_web` or `review_cli`
- `comment`: optional except where a command explicitly requires it

The service derives timestamps, command IDs, permissions, current state, and repository locations. Callers cannot supply or override them.

## Common result

Successful commands return `command_id`, prior and resulting states, resulting version, event ID, publication ID when applicable, warnings, and `idempotent_replay`. Responses contain no private body unless the caller separately requests and is authorized for review detail.

Common errors are:

| Status | Code | Meaning |
|---|---|---|
| 400 | `invalid_command` | Malformed envelope or unsupported reason code. |
| 401/403 | `unauthenticated` / `forbidden` | No authenticated actor or missing permission. |
| 404 | `draft_not_found` | Safe ID resolved to no review draft. |
| 409 | `stale_review` | Version or digest no longer matches. |
| 409 | `invalid_transition` | Command is not permitted from current state. |
| 409 | `idempotency_conflict` | Key was used with a different normalized command. |
| 409 | `identity_conflict` | Trusted record with conflicting deterministic identity exists. |
| 422 | `ineligible_for_approval` | Current blockers prevent approval. |
| 503 | `promotion_incomplete` | Durable recovery is required; safe retry uses the same key. |

## Commands

### Inspect

`get_publication_review(draft_id)` is read-only. It returns state/version/digest, provenance, content-class and acquisition summaries, duplicate candidates, blockers, warnings, permitted commands, and a separately authorized content locator or hydrated body. Inspection does not imply a human decision.

### Save content revision

`revise_publication_draft(envelope, patch)` accepts only an allowlist of draft fields. It validates Source and entity references, increments the version, recalculates the digest, and appends a revision event. It cannot set approval fields or create canonical records.

### Approve

`approve_publication(envelope, approval_basis, warning_acknowledgments)` rechecks eligibility, identity, duplicates, version, digest, and permission under a per-draft lock. It creates exactly one trusted publication compatibility record with empty `fact_ids`, creates no graph records, archives the reviewed draft privately, and records intent and completion. `approval_basis` is one of `full_article`, `partial_article`, `full_transcript`, `structured_registry`, or, if product policy accepts it, `limited_content`.

### Reject

`reject_publication(envelope, reason_code, comment)` requires a typed reason and explanatory comment. It preserves the rejected draft privately and appends the terminal decision. It creates no trusted record.

### Defer

`defer_publication(envelope, reason_code, review_after)` records a typed operational reason and optional review-after date. It is not rejection, dismissal, or trust.

### Request or submit correction

`request_publication_correction(envelope, blocker_codes, comment)` moves the review to `correction_required`. `submit_publication_correction(envelope, patch, comment)` applies an allowlisted revision, increments version/digest, re-evaluates eligibility, and returns to `pending_review` when structurally valid. Submission does not approve.

### Return deferred item

`return_publication_to_review(envelope, comment)` moves a deferred item to `pending_review` and appends the reason. It does not erase the deferral.

### Declare duplicate

`supersede_publication_duplicate(envelope, survivor_id, identity_basis, comment)` requires a resolvable survivor and exact supported identity basis. Fuzzy similarity alone is insufficient. It preserves lineage and creates no duplicate publication.

## Proposed adapter surface

- `GET /api/publication-reviews/{draft_id}`
- `POST /api/publication-reviews/{draft_id}/revisions`
- `POST /api/publication-reviews/{draft_id}/approve`
- `POST /api/publication-reviews/{draft_id}/reject`
- `POST /api/publication-reviews/{draft_id}/defer`
- `POST /api/publication-reviews/{draft_id}/request-correction`
- `POST /api/publication-reviews/{draft_id}/submit-correction`
- `POST /api/publication-reviews/{draft_id}/return-to-review`
- `POST /api/publication-reviews/{draft_id}/supersede-duplicate`

Existing HTML routes should call these commands rather than `ReviewPublishService.publish()` directly. V1 defines no collection endpoint that accepts multiple approval decisions. A session may navigate many drafts, but every approval remains a separate request and authorization event.

## Repository boundary and test seams

The command service depends on narrow ports for draft load/compare-and-set/archive, trusted-publication identity lookup/create, Source/entity read resolution, acquisition/transcript outcome reads, event append, idempotency receipt read/write, lock acquisition, and journal recovery. Repositories return typed not-found/conflict results and do not make trust decisions.

Tests inject temporary implementations of each port plus a clock and command-ID generator. Failure injection is required at every journal phase. Route tests verify actor binding and response mapping; domain tests require no filesystem or application data.
