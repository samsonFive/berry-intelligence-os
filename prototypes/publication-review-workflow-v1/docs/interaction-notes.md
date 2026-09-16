# Interaction Notes — Publication Review Workflow V1

## Operator flow

1. Open queue; pending-review count is visible.
2. Optionally filter by readable / transcript / limited / problem.
3. Select a draft (click or `j`/`k`). Queue sorts pending first, then needs-attention rank.
4. Inspect workspace: source metadata, body/transcript or limited explanation, entities, duplicates, warnings, provenance, history.
5. Choose a decision. Approval always opens a confirmation dialog.
6. On success, read the receipt (actor, time, draft, resulting publication id label). No erase/undo control is offered.

## Decision semantics

| Action | Label in UI | Effect in prototype memory |
| --- | --- | --- |
| Approve | **Approve publication** | `approved` + prototype `proto-pub-*` id (label only) |
| Reject | Reject | `rejected` — reason required |
| Defer | Defer | `deferred` — remains as draft file conceptually |
| Request correction | Request correction | `correction_requested` — reason required |

**Approve publication ≠ Evidence approval.** Copy in workspace and dialog states this explicitly.

## Guardrails

| Guardrail | Behavior |
| --- | --- |
| No bulk approval | No multi-select; no “approve all”; callout + `no-bulk` copy |
| Explicit confirmation | Approve requires Confirm approve publication |
| Reasons | Reject and request correction require a reason select |
| Warn vs block | `warn` items show “(warning — not an automatic blocker)”; `block` shows “(contractual blocker)” and disables approve |
| Stale / concurrent | Fixture `already_handled_by_another_reviewer` or non-pending → toast, idempotent no-op |
| Duplicate click | Idempotency key `action:draft_id:version` returns prior receipt |
| Success receipt | Actor, timestamp, draft id, resulting publication id (or none) |
| No false undo | Receipt states corrective events only; no Undo button |

## Keyboard

| Key | Action |
| --- | --- |
| `j` / `k` | Next / previous visible draft |
| `a` | Open approve-publication dialog (if pending) |
| `r` | Open reject dialog |
| `x` | Open defer dialog |
| `c` | Open request-correction dialog |
| `Esc` | Close dialog + restore focus |
| `Tab` (in dialog) | Focus trap |

## Filters

- **All pending** — shows all drafts (handled items remain visible but dimmed for demos of concurrent state).
- Content-quality filters match `content_quality`.
- **Problem states** — `content_quality === problem` OR any `blocking_warnings`.

## Terminology alignment

Uses existing product language where present: pending review, defer, reject, provenance, acquisition outcome, publication date confidence. New explicit phrase: **Approve publication** (not Promote-to-Evidence / Evidence approval).
