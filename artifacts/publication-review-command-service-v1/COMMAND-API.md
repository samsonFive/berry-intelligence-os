# Command surface

`app.services.publication_review_command.PublicationReviewCommandService`
is the only production-facing surface (no HTTP route is wired to it in
this mission — see `NON-GOALS`). Every state-changing method takes a
`domain.CommandEnvelope` and returns a `domain.CommandResult`, or raises
`domain.CommandError` with a typed `.code`.

## Common envelope (`domain.CommandEnvelope`)

| Field | Meaning |
|---|---|
| `draft_id` | Target draft |
| `actor_id` | Immutable identity string, resolved server-side via `ActorDirectory` — never trusted as-is |
| `idempotency_key` | Caller-generated, required |
| `expected_version` | The version the caller last observed |
| `reviewed_content_digest` | The digest of the content the caller actually inspected |
| `source_surface` | Bounded label (defaults to `review_command_service`) |
| `comment` | Optional except where a command requires it |

The service derives everything else (timestamps, command ids, actor
permissions, current state) — callers cannot override them.

## Read operations

| Method | Behavior |
|---|---|
| `get_publication_review(draft_id)` | Full state + eligibility + permitted next commands. Read-only; never implies a decision. |
| `list_publication_reviews(state=None)` | Queue/list with a stable state filter. |
| `status_summary()` | `{total, by_state: {...}}` counts. |
| `decision_history(draft_id)` | The append-only decision list. |

## Commands

| Method | From state(s) | To state | Notes |
|---|---|---|---|
| `revise_publication_draft(envelope, patch)` | `pending_review` | (unchanged) | Content revision, not a trust decision. Allowlisted fields only (`ALLOWED_REVISION_FIELDS`). Bumps version + both digests. |
| `approve_publication(envelope, approval_basis, warning_acknowledgments=())` | `pending_review` | `approved` | The only command that promotes a trusted publication. See below. |
| `reject_publication(envelope, reason_code, comment)` | `pending_review`, `deferred`, `correction_required` | `rejected` | `reason_code` from a closed set; `comment` required. |
| `defer_publication(envelope, reason_code, review_after=None)` | `pending_review` | `deferred` | `reason_code` from a closed set. |
| `request_publication_correction(envelope, blocker_codes, comment)` | `pending_review` | `correction_required` | At least one known blocker code; `comment` required. |
| `submit_publication_correction(envelope, patch, comment)` | `correction_required` | `pending_review` | Re-evaluates eligibility; does not itself approve. |
| `return_publication_to_review(envelope, comment)` | `deferred` | `pending_review` | |
| `supersede_publication_duplicate(envelope, survivor_id, identity_basis, comment)` | `pending_review` | `superseded_duplicate` | `identity_basis` is `canonical_url` or `title_source_date` — no fuzzy basis accepted. |

Every command not listed for a given state raises `invalid_transition`;
every terminal state (`approved`/`rejected`/`superseded_duplicate`)
rejects a *new* decision command with `already_decided` — an identical
retry of the *same* command with the *same* idempotency key still
succeeds as an idempotent replay.

## Approval in detail

`approve_publication` is the only method that can create a trusted
publication. Its sequence:

1. Authorize the actor (human + `publication_review` permission).
2. Idempotency check (replay short-circuits everything below).
3. Acquire the per-draft lock.
4. Re-load the draft; check version, content digest, and provenance
   digest; check the transition is valid from the current state.
5. Recompute eligibility **inside the lock**, including a duplicate check
   against both trusted publications and other pending drafts.
6. Reject if not `approvable`, if `approval_basis` is not one of the
   content's own `permitted_approval_bases`, or if any mandatory warning
   is unacknowledged.
7. Reject with `identity_conflict` if a trusted record already exists at
   the target publication id.
8. Run the staged promotion protocol (`CRASH-RECOVERY.md`).
9. Persist the idempotency receipt; return the result.

`approval_basis` is one of `full_article`, `partial_article`,
`full_transcript`, `structured_registry`, `limited_content` — exactly the
contract's own five bases. `limited_content` is only ever permitted for
`description_only`/thin-metadata content, and the resulting trusted
record carries `limited_content: true` plus `publication_content_basis`
so a future reporting layer can exclude it from readable/current-coverage
counts (per the contract's own explicit requirement) without a schema
migration.

## Errors

Every error is a `domain.CommandError` with one of `COMMAND-CONTRACTS.md`'s
own codes: `invalid_command`, `unauthenticated`, `forbidden`,
`draft_not_found`, `stale_review`, `invalid_transition`,
`idempotency_conflict` (raised as `IdempotencyConflict`, a
`ReviewRepositoryError` subclass, from the repository layer),
`identity_conflict`, `ineligible_for_approval`, `already_decided`,
`promotion_incomplete`.
