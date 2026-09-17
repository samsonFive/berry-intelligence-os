# Next-agent prompt

Validate and integrate Trust Feedback Domain V1 from `feature/trust-feedback-domain-v1`. Read `AGENTS.md` and this artifact directory first. Do not infer feedback for legacy records and do not bulk-migrate application data.

Confirm that `app/services/trust_feedback.py` continues to use `inbox/analyst_queue_state.json` plus the existing `review_events` ledger. Verify promotion can only cross into trusted data through the injected existing approval handler. Preserve the distinction between endorsements, approved Sources, trusted intelligence, current news, and Research Packet inclusion.

For a future UI/route slice, derive actor identity and permissions from the authenticated server session, never from client fields. Wire the deterministic projection into one consumer at a time with private-state and static-leakage tests. Thumbs-down must remain a query-time exclusion with immediate Undo; it must never delete provenance. Do not let feedback confirm Signals, create Facts/Assessments/Watches, or bypass publication review.

Run focused tests and record/static validation. Do not run collection, publish, approve, merge, or deploy without separate authorization.
