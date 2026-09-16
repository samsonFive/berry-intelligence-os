# Production Migration Map — Publication Review Workflow V1

Maps this disconnected prototype to likely production surfaces. **Do not treat this prototype as a production route.**

## Source of truth today

| Concern | Production reference (wave3 / review ops) | Prototype stand-in |
| --- | --- | --- |
| Pending queue | `pending_review` queries / review list templates | Fixture `drafts[]` + queue panel |
| Review workspace | `review.html` / draft detail | Workspace blocks in `app.js` |
| Decisions | Review operations (promote/reject/defer patterns) | In-memory events + receipts |
| Visual system | `app/static/pvs_tokens.css` (Slice 1) | Copied `tokens.css` |
| Evidence | Separate Evidence approval path | Explicitly **out of scope** — labeled not Evidence |

## Suggested migration steps (future work; not performed here)

1. **Keep prototype isolated** under `prototypes/publication-review-workflow-v1/` until UX sign-off.
2. **Align decision verbs** with production API contracts: map `approve_publication` → publication promotion endpoint (not Evidence).
3. **Port queue columns** (quality, date confidence, provenance warn, duplicate, entity match, attention rank) into the existing review list without inventing a second design language — reuse PVS badges.
4. **Workspace panels** should bind to draft DTOs already returned by review APIs (source URL, discovery/capture timestamps, acquisition outcome, provenance chain, history).
5. **Guardrails in API + UI**:
   - Reject/correction require reason codes (already partially present in ops).
   - No bulk approve endpoint or UI.
   - Optimistic concurrency via draft version / etag (prototype: `expected_version_conflict_if_acted`).
   - Idempotency keys on decision writes.
   - Receipts from server event log; no erase undo.
6. **Warn vs block**: surface `level: warn|block` from contract; only `block` disables approve.
7. **Do not** wire prototype JS into Flask routes; rewrite against production templates/components when migrating.
8. **Evidence** remains a separate operator path; copy must continue to say “publication approval.”

## Files that must stay untouched by this prototype track

- `app/**` production Python / templates / static (except future deliberate Slice work)
- Live databases / canonical imports
- Deployment manifests

## Exit criteria before production Slice

- [ ] Product sign-off on decision labels and receipt fields
- [ ] API contract for approve_publication vs Evidence documented
- [ ] A11y checklist re-run on production templates
- [ ] Fixture states covered by integration tests against real DTOs
- [ ] Feature flag / dark launch plan (no silent trusted publication)

## Explicit non-delivery

This branch ships **prototype + artifacts only**. No PR/merge/deploy is part of the mission.
