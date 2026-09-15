# Trust Feedback Domain V1 contract

## Purpose

Trust feedback is private analyst working state over an existing record. It uses `inbox/analyst_queue_state.json` for the latest projection and the existing append-only `inbox/review_events/trust_feedback/` ledger for history. It never deletes or rewrites Evidence, discoveries, Sources, or acquisition outcomes.

## Actions and transitions

| Action | Required input | Result | Trusted-data effect |
|---|---|---|---|
| `promote` with `relevant`, `retain_for_review`, or `monitor` | actor, object, idempotency key, expected version, surface | `retained` | None |
| `promote` with `governed_promotion` | same inputs, readable content, provenance, promotion authority | `approved_source`, `trusted_intelligence`, or honest `pending_promotion` with blockers | Only the injected existing approval handler may write trusted data |
| `exclude` | same inputs; optional controlled reason | `excluded` | Query-time removal from the actor's trusted projection; source record is preserved |
| `defer` | same inputs | `deferred` | None |
| `undo` | same inputs plus the original event ID | the original event's prior state | Appends a compensating event; never deletes history |

Undo is allowed only for the original actor's latest unsuperseded working-state event. A promotion that reached `approved_source` or `trusted_intelligence` must use the governed publication reversal workflow.

## Concurrency and idempotency

Each actor/object projection has a monotonically increasing `version`. If `expected_version` does not equal the current version, the action fails before a write. An `idempotency_key` replay with identical action inputs returns the original event without a duplicate write. Reuse of the same key with different inputs fails.

## Eligibility

`check_eligibility()` returns structured blockers and limitations. Promotion is blocked when the body is unusable, an acquisition outcome is a cookie wall, bot wall, empty/navigation shell, unsupported/error state, or manual-only result, or required source/capture provenance is missing. A partial body is eligible with a limitation.

Known historical publication dates produce `historical_context_only`; unknown dates produce `publication_date_unknown`. Both can enter governed review, but neither is eligible for current news.

## Query projection

`feedback_projection()` exposes:

- `eligible_for_trusted_feed`
- `excluded_from_trusted_feed`
- `pending_promotion`
- `approved`
- `trusted`
- `deferred`
- `last_feedback_action`
- `exclusion_reason`
- `undo_available`
- `current_news_eligible`
- content/date limitations and review blockers

Today, reports, company coverage, and Research Packets can call this projection before selection. V1 intentionally does not wire those consumers.

The executable event contract is `schemas/trust-feedback-event.schema.json`.
