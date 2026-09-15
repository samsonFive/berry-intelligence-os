# Trust Feedback Controls — Frontend Service Contract V1

Prototype-facing contract for `prototypes/trust-feedback-controls-v1/`.
Sol’s `feature/trust-feedback-domain-v1` is expected to satisfy an equivalent service later.

**Not a second canonical state store.** Events append to the existing analyst feedback / review-event stream. Projections for Today / trusted feed are derived.

**Prototype adapter:** in-browser mock only. No live mutation endpoint is called.

## Operations

| Operation | Purpose |
|---|---|
| `eligibility` | Pre-flight blockers before an up action |
| `promote` | Thumbs-up intent (relevant / retain_for_review / monitor) |
| `exclude` | Thumbs-down with optional reason |
| `defer` | Exclude immediately; reason deferred |
| `undo` | Compensating event restoring prior projection |
| `history` | Fetch last action / event trail for a record |

## Common request fields

```json
{
  "record_id": "canonical-object-id",
  "actor_id": "analyst-id",
  "actor_context": {
    "roles": ["analyst"],
    "session_id": "optional-opaque"
  },
  "idempotency_key": "client-generated-opaque",
  "expected_version": 3,
  "action": "promote|exclude|defer|undo",
  "intent": "relevant|retain_for_review|monitor|null",
  "reason": "duplicate|wrong_entity|outdated|weak_source|unreadable|irrelevant|other|null",
  "event_id": "required-for-undo",
  "prior_state_hint": "unreviewed|optional-client-hint"
}
```

## Common response fields

```json
{
  "ok": true,
  "result": {
    "record_id": "canonical-object-id",
    "event_id": "opaque-event-id",
    "prior_state": "unreviewed",
    "resulting_state": "promoted|relevant_pending_approval|excluded|unreviewed",
    "blockers": [
      {
        "code": "unreadable_content|incomplete_provenance|approval_required|...",
        "message": "Human-readable explanation"
      }
    ],
    "undo_available": true,
    "timestamp": "ISO-8601",
    "idempotent": false,
    "message": "Restrained confirmation copy",
    "kind": "promoted|pending|blocked|excluded|deferred|undo|idempotent"
  }
}
```

Error envelope:

```json
{
  "ok": false,
  "error": {
    "code": "not_found|version_conflict|undo_unavailable|unauthorized|validation",
    "message": "…",
    "current_version": 4
  }
}
```

## Eligibility

`POST /trust-feedback/v1/eligibility` (proposed)

Request: `{ "record_id", "actor_id" }`

Response.result:

| Field | Notes |
|---|---|
| `eligible` | false if any hard blocker |
| `blockers[]` | `unreadable_content`, `incomplete_provenance`, … |
| `approval_required` | true → up yields pending, not promoted |
| `already_promoted` | idempotent path |
| `content_honesty` | `readable\|unreadable\|historical_context\|unknown_date` |

Hard rule: unreadable / bot-wall / cookie / empty / navigation-shell → **not promotable**.

## Promote (thumbs up)

`POST /trust-feedback/v1/promote`

Does **not** mean published Evidence. Only existing publication review promotes drafts to trusted Evidence.

Resulting states demonstrated in this prototype:

| Scenario | resulting_state | kind |
|---|---|---|
| Eligible, no approval gate | `promoted` | `promoted` |
| Eligible, approval required | `relevant_pending_approval` | `pending` |
| Incomplete provenance | prior unchanged | `blocked` |
| Unreadable content | prior unchanged | `blocked` |
| Already promoted | `promoted` | `idempotent` |

## Exclude (thumbs down)

`POST /trust-feedback/v1/exclude`

Immediate exclusion from trusted-feed projection. **Does not delete provenance** or operational records. Item remains in audit / history filters.

## Defer

`POST /trust-feedback/v1/defer`

Same projection effect as exclude; `reason` null; UI may later attach reason without inventing a second store.

## Undo

`POST /trust-feedback/v1/undo`

Body includes `event_id` of the event to compensate. Appends a new event with `undoes_event_id`. Does not erase history.

## History

`GET /trust-feedback/v1/history?record_id=`

Returns append-only events for the record (and optionally actor-scoped projection metadata).

## Versioning & concurrency

- Clients send `expected_version`.
- Conflicts return `version_conflict` with `current_version`.
- Concurrent analysts append events; they do not overwrite each other.
- `idempotency_key` makes safe retries.

## Mapping to roadmap Trust Feedback State Model

Aligned with commit `f2021d4b1709629cb20bc81c609a9ea644142950`  
`artifacts/product-experience-roadmap-v1/TRUST-FEEDBACK-STATE-MODEL.md`:

- Up intents: `relevant` | `retain_for_review` | `monitor`
- Down reasons: `irrelevant`, `duplicate`, `wrong_entity`, `outdated`, `weak_source`, `unreadable`, …
- Undo = compensating event
- Thumbs-down preserves provenance
- Feedback never creates Fact / Signal / Assessment / Watch

## Prototype vs Sol

| Concern | This prototype | Sol domain |
|---|---|---|
| Persistence | In-memory mock | Event stream / existing review conventions |
| Transport | Local JS `mockService` | HTTP (or internal service) matching this contract |
| Fixtures | Synthetic only | Production objects when wired |
| Canonical store | None invented | Reuse analyst feedback events — no second trust repo |
