# Production Continuation Prompt — After Trust Feedback Controls Prototype

Copy/paste for the next production agent.

---

You are continuing Berry Intelligence OS product work after two frozen branches:

1. **Daily Intelligence Briefing V2 Slice 1** — `feature/daily-intelligence-briefing-v2-slice1` @ `d6941bc2b2de7ffdd5fc76767f9180c4938aaf25`
2. **Trust Feedback Controls V1 prototype** — `prototype/trust-feedback-controls-v1` (standalone under `prototypes/trust-feedback-controls-v1/`)

Sol owns backend domain work on `feature/trust-feedback-domain-v1`.

## Do

- Keep Daily Briefing Slice 1 production behavior intact unless a dedicated production slice says otherwise.
- When wiring trust controls into `/today` + in-app reader, implement against `docs/FRONTEND-SERVICE-CONTRACT.md` from the trust prototype.
- Enforce: thumbs-down preserves provenance; unreadable content not promotable; no auto-publish on thumbs up.
- Use Sol’s service when available; do not invent a second trust store.
- Add focused tests + browser checks for feed card + reader + undo + blocked promotion.

## Do not

- Force-push, merge, or deploy unless explicitly requested.
- Call live mutation endpoints from prototypes.
- Treat prototype in-memory state as canonical.
- Bulk-promote.
- Delete acquisition / provenance on exclude.

## Suggested next production slice

“Trust Feedback Controls — Production Slice 1”: mount controls on briefing cards + reader, feature-flagged, backed by Sol’s domain API (or a staging double matching the contract), with accessibility parity to the prototype checklist.
