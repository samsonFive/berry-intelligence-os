# Publication review state machine

## Existing vocabulary

| Layer | Values |
|---|---|
| Evidence schema `status` | `draft`, `in_review`, `published`, `archived`, `rejected` |
| Evidence schema `review_state` | `draft`, `in_review`, `published`, `rejected` |
| Review workbench projection | `pending`, `approved`, `rejected` |
| Pending triage overlay | open or `dismissed`; dismissal does not change publication review state |

V1 does not reinterpret historical records. The service introduces a versioned publication-review projection while continuing to serialize compatible schema fields.

## Proposed canonical review states

- `pending_review`: complete enough to inspect; no decision.
- `correction_required`: blocked until specified fields/content are corrected.
- `deferred`: intentionally postponed, with reason and optional review-after date.
- `approved`: terminal decision; exactly one trusted publication exists.
- `rejected`: terminal decision; draft retained privately.
- `superseded_duplicate`: terminal decision; points to the surviving trusted publication or draft.

`pending_review`, `correction_required`, and `deferred` are revisitable. `approved`, `rejected`, and `superseded_duplicate` are terminal for that review cycle.

## Permitted transitions

| From | Command | To | Required detail |
|---|---|---|---|
| `pending_review` | approve | `approved` | Actor, approval basis, version, digest, idempotency key, warning acknowledgments. |
| `pending_review` | reject | `rejected` | Reason category and explanatory comment. |
| `pending_review` | defer | `deferred` | Typed reason; optional review-after date. |
| `pending_review` | request correction | `correction_required` | One or more blocker codes and explanatory comment. |
| `pending_review` | declare duplicate | `superseded_duplicate` | Survivor ID and deterministic identity evidence. |
| `deferred` | return to review | `pending_review` | Version match; reason/comment recording why it is ready. |
| `deferred` | reject | `rejected` | Normal rejection requirements. |
| `correction_required` | submit correction | `pending_review` | Corrected fields, new version/digest, actor and comment; eligibility re-evaluated. |
| `correction_required` | reject | `rejected` | Normal rejection requirements. |

Saving editorial changes while `pending_review` is a content revision, not a trust decision. It increments `review_version`, changes the digest, and appends a revision event.

Every transition is persisted in the shared durable review repository. A local inbox projection may mirror it but cannot be the sole state. For approval, the state changes to `approved` for trusted readers only when one commit marker immutably binds the prior draft ID/version/digest and provenance hashes to the actor, decision, audit event, and resulting publication hash.

## Invalid transitions

- Approval from any state other than `pending_review`: 409 `invalid_transition`.
- Any command with stale version or digest: 409 `stale_review` with current version/digest, no mutation.
- Approval of a blocked or ambiguous draft: 422 `ineligible_for_approval` with blocker codes.
- Any second terminal decision with a new idempotency key: 409 `already_decided`.
- Exact replay of the original terminal command: success response with `idempotent_replay=true`.
- Reusing an idempotency key for different action/payload: 409 `idempotency_conflict`.

## After approval

Approval is not reversed by editing or deleting the original decision. A correction, withdrawal or readable-body upgrade creates a new review cycle and append-only event linked to the prior publication/version. V1 should initially expose no reversal command until its authorization and static/reporting semantics are implemented. The existing publication remains auditable.
