# Review Outcome Instrumentation V1

## Outcome

Human review transitions now produce compact append-only records under
`inbox/review_events/`. The ledger is private mutable runtime state: it is
covered by the existing complete-runtime backup and Docker bind mount, and is
not read by the static builder. No Source, schedule, trust rule, or automatic
throttling policy changed.

There is deliberately no historical backfill. A current state can be known
without its transition time being known; those pre-ledger states are not
reported as events.

## Event contract

Each event records an opaque event ID, UTC time, private actor, workflow,
object ID/type, action, prior/new state, and previous event ID. When present on
the reviewed object or its registered Source, the envelope also records Source
ID/class, query family/identifier, discovery mechanism, berry/geography/entity
IDs, media type, relevance tier, discovered-item ID, pipeline run ID, and the
queue-entry time used for latency. It never copies a title, summary, body,
transcript, URL, password, session secret, or API key. Provenance is taken only
from stored fields; titles are never parsed to invent attribution.

Files use exclusive creation and deterministic retry identities. A repeated
form submission with the same transition is a no-op. A later real transition
back to the same action is distinct because its prior state and event-chain
predecessor differ. Event creation is compensated if the paired mutable-state
write or publish transaction fails.

## Instrumented workflows

| Workflow label | Real actions |
|---|---|
| `publication_review` | Publish, Reject |
| `atomic_evidence_review` | Approve/publish Atomic Evidence; distinct from publication outcomes |
| `publication_triage` | Dismiss, Restore; does not reject or delete a draft |
| `reading_queue` | Mark read, Keep, Dismiss, Promote |
| `claim_testing` | Pass, Fail, Defer, Reopen; Pass is not Publish or Fact creation |
| `signal_candidate_review` | Confirm, Edit, Defer, Dismiss, Dispute; remains untrusted |
| `signal_alert_review` | Confirm, Dismiss on proposed trusted Signal alerts |
| `recommendation_proposal_review` | Accept, Reject |

Monitoring pause/resume/snooze/stop is operational control, not a review
outcome, and is not in the ledger. Publication Save currently also edits draft
content and does not provide an unambiguous Keep-vs-edit intent; V1 therefore
does not fabricate a Keep outcome from that endpoint.

## Analytics and operator status

`scripts/review_capacity.py` reads the ledger and keeps its three categories
separate:

1. `OBSERVED`: recorded actions, grouped by workflow/action/Source/class/query,
   reviewed and unreviewed current objects, last decision, and median latency.
2. `DERIVED_OPERATIONAL_METRICS`: backlog, age, arrivals, source/query load,
   duplicate pressure, relevance, and queue growth.
3. `SIMULATED_POLICY_EFFECT`: what the conservative policy would delay or
   surface. It does not predict analyst decisions.

The fast `collection_status.py` output exposes total observed decisions, last
decision time, and counts by action without deep item orchestration. Rates stay
`null` until at least **30 publication Publish/Reject decisions across at least
two observed days**. Before that point, raw counts are useful for checking the
instrumentation, but Source yield is not actionable. Each Source/query cohort
also needs 30 decisions before its rate is shown. Automatic throttling remains
OFF.

## Remaining instrumentation limits

- Publication Save needs a separate explicit Keep control before keep-rate can
  be measured independently from editing.
- Dismiss/defer reason categories are not collected on every workflow.
- Events cannot reconstruct decisions made before deployment.
- A future concurrent multi-writer service would need stronger transactional
  storage than the current flat-file plus compensation model.

## Validation and production proof

Focused tests cover compactness, idempotency, workflow separation,
insufficient-sample semantics, no inferred history, and verified backup/restore
of a private event. The static builder has no review-event or inbox dependency.
Production proof captures pre/post runtime counts and hashes, rebuilds the
existing Docker deployment, confirms timer and automatic-throttling state,
exercises authenticated review, and verifies event survival.
