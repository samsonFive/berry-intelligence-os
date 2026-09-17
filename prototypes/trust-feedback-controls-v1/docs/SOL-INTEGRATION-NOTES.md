# Sol Integration Notes — Trust Feedback Domain V1

Sol is implementing `feature/trust-feedback-domain-v1` separately.

This prototype **does not require** Sol’s branch to exist and **does not invent** a competing persistence layer.

## What the frontend needs

Implement (or adapt) the operations in `FRONTEND-SERVICE-CONTRACT.md`:

1. `eligibility`
2. `promote`
3. `exclude`
4. `defer`
5. `undo`
6. `history`

Reuse analyst queue / review-event conventions where safe. Append-only events. No second trust repository.

## Required honesty rules (backend must enforce)

- Thumbs-down **never** deletes provenance or operational records.
- Unreadable / bot-wall / cookie / empty / navigation-shell content is **not promotable**.
- Historical context remains historical; unknown-date retains limitation.
- Thumbs up never auto-publishes Evidence / Fact / Signal / Assessment / Watch.
- Only existing publication review promotes drafts to trusted Evidence.
- Undo appends a compensating event; it does not erase history.
- Idempotent retries via `idempotency_key`.
- Optimistic concurrency via `expected_version`.

## Projection vs storage

| Layer | Responsibility |
|---|---|
| Event store (Sol) | Canonical append-only feedback events |
| Feed projection | Active Today / trusted feed membership |
| Audit / history UI | Always searchable authorized events + excluded items |
| This prototype mock | Ephemeral demo only |

## Suggested event shape (roadmap-aligned)

```json
{
  "event_type": "analyst_feedback",
  "event_id": "opaque-id",
  "object_type": "evidence|discovered_media|signal|assessment",
  "object_id": "canonical-id",
  "actor_id": "analyst-id",
  "action": "up|down|undo|promote|exclude|defer",
  "intent": "relevant|retain_for_review|monitor",
  "reason": "duplicate",
  "prior_state": "unreviewed",
  "resulting_state": "excluded",
  "created_at": "ISO-8601",
  "undoes_event_id": null
}
```

Naming: Sol may keep `up`/`down` in the domain event while the HTTP API uses `promote`/`exclude`. Map explicitly; do not fork semantics.

## UI handoff points (Daily Briefing Slice 1+)

Production surfaces to wire later (not modified by this prototype):

- `/today` briefing cards (`_briefing_card.html`)
- In-app reader (`?reader=`)
- Possibly `/news` archive cards

Trust controls must remain visually distinct from “Original source” / Landscape / Diagnostics.

## Out of scope for Sol (this slice)

- Bulk promote
- New Facts from feedback
- Deleting acquisition outcomes
- Static public pages reflecting personal analyst state

## Acceptance when wiring

1. Contract fields round-trip (record ID, actor, idempotency, version, action, reason, prior/resulting state, blockers, event ID, undo availability, timestamp).
2. Prototype scenarios still hold against live service with synthetic or staging records.
3. Production files for this prototype package remain isolated under `prototypes/trust-feedback-controls-v1/`.
