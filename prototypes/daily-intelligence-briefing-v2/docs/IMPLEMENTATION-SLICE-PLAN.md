# Daily Intelligence Briefing V2 — Implementation slice plan

Cherry-pickable after Competitor Landscape integration. Keep each slice independently reviewable.

## Slice 0 — Contract + fixtures (this prototype)

- View-model contract
- Fixture taxonomy for honesty states
- Standalone HTML for stakeholder review

## Slice 1 — Read model only

- Build `DailyBriefingV2` presenter over existing trusted evidence / review / source-health / landscape adapters
- No new persistent store
- Enforce honesty filters in presenter tests

## Slice 2 — Route + shell (isolated)

- Add a preview/staff route only after product approval
- Reuse V2 shell patterns; do not alter Morning Brief until cutover decision
- Wire reader offcanvas patterns already approved in V2

## Slice 3 — Attention unification

- Map review-ready, body unavailable, bot wall, consent, missing entity link, manual acquisition, aging classification into one attention enum
- Deep-link to existing queues / Source Health rather than duplicating workflows

## Slice 4 — Landscape handoff

- Generate landscape query strings from briefing context
- Preserve return path `from=briefing-v2`

## Slice 5 — Cutover decision

- Decide whether Morning Brief becomes this briefing or remains adjacent
- Only then touch production navigation

## Explicit non-goals for early slices

- No acquisition logic changes
- No Source Health behavior changes
- No canonical competitor identity edits
- No genetics relationship invention
- No live inbox mutation
