# Continuation prompt — produce Daily Intelligence Briefing V2 after Landscape integration

Use only after Competitor Landscape V1 is integrated and product asks for production implementation.

## Context

- Stakeholder prototype lives on branch `prototype/daily-intelligence-briefing-v2`
- Path: `prototypes/daily-intelligence-briefing-v2/`
- Base of prototype work: `d44e3e3d753e4f796151e75c6747214b92c8232e`
- Do not treat prototype fixture claims as canonical facts

## Read first

1. `prototypes/daily-intelligence-briefing-v2/docs/VIEW-MODEL-CONTRACT.md`
2. `docs/UX-DECISION-LOG.md`
3. `docs/IMPLEMENTATION-SLICE-PLAN.md`
4. `docs/ACCESSIBILITY-CHECKLIST.md`
5. `docs/CHECKPOINT.md`
6. Current Morning Brief / Live Intelligence / review queues / Source Health / Competitor Landscape production code

## Implement in slices

Follow `IMPLEMENTATION-SLICE-PLAN.md`:

1. Read-model presenter + honesty filters + tests
2. Isolated preview route (no nav cutover yet)
3. Attention unification deep-links
4. Landscape query handoff
5. Explicit cutover decision for Morning Brief

## Hard constraints

- No inventing summaries for unreadable / consent / bot-wall bodies
- Capture date must never replace publication date
- Unknown publication dates never lead the briefing
- Observed fact ≠ analyst interpretation
- No acquisition logic changes unless a true blocker is found and recorded
- No Source Health behavior changes in the same slice as briefing UI
- No canonical competitor identity edits
- No genetics relationship invention
- No live inbox mutation from the briefing surface

## Done when

- Presenter tests prove honesty gates
- Preview route matches prototype information architecture
- Landscape handoff preserves berry/region/tier/focus
- Accessibility checklist still passes
- PRODUCTION ROUTES beyond the approved preview remain untouched until cutover decision
