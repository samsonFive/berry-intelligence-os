# Trust Feedback State Model V1

This is a proposed model; this planning checkpoint adds no code or schema.

## Semantics

| Action | Meaning | Does not mean |
|---|---|---|
| Up — Relevant | Relevant to the analyst’s scope. | Trusted, true, published, or corroborated. |
| Up — Retain | Keep in the working set. | Promote to Evidence or Research Packet. |
| Up — Monitor | Keep available for future monitoring. | Create a Watch or confirm a Signal. |
| Down | Exclude from the analyst’s active feed with a reason. | Delete provenance or operational records. |
| Undo | Append a compensating event and restore the prior projection. | Erase audit history. |

Down reasons: `irrelevant`, `duplicate`, `wrong_entity`, `wrong_berry_or_region`, `weak_source`, `unreadable`, `outdated`, `misleading_extraction`, and `other`.

## Event contract

```json
{
  "event_type": "analyst_feedback",
  "event_id": "opaque-id",
  "object_type": "evidence|discovered_media|signal|assessment",
  "object_id": "canonical-id",
  "actor_id": "analyst-id",
  "action": "up|down|undo",
  "intent": "relevant|retain_for_review|monitor",
  "reason": "duplicate",
  "prior_state": "unreviewed",
  "resulting_state": "excluded",
  "created_at": "ISO-8601",
  "undoes_event_id": null
}
```

Reuse existing analyst queue/review-event conventions where safe. Do not create a second trust repository.

## Transitions and safety

| Prior state | Action | Result | Effect on trust data |
|---|---|---|---|
| unreviewed | up | retained with typed intent | none |
| unreviewed | down | excluded from personal projection | none |
| retained/excluded | undo | prior projection restored | append compensating event |
| any | repeat | idempotent current state | no duplicate effect |
| any | Promote/Reject/Source Fidelity | existing governed transition | existing permissions apply |

Every event requires actor, timestamp, object ID, prior/resulting state, action, and reason where applicable. Bulk actions show scope/count and never bulk-promote. Keyboard shortcuts are explicit and disabled in text fields. Static output must not expose analyst state. Concurrent analysts append events rather than overwrite each other.

Only existing publication review can promote a draft to trusted Evidence. Feedback never creates a Fact, confirms a Signal, creates an Assessment, or creates a Watch. Original records, acquisition outcomes, provenance, and feedback events remain authorized-audit searchable; exclusion changes only active Today/report projections. **Thumbs-down preserves provenance.**
