# Project Status

*Maintained by Claude. Updated at the end of each work session that changes project state. Keep short — this is a status check, not a changelog (see `docs/reviews/CURRENT-STATE-AUDIT.md` and `docs/v2/` for detail).*

**Last updated:** 2026-08-13

---

**Current phase:**
Pre-Phase 0 — V2 planning complete, awaiting owner review (see `docs/v2/07-IMPLEMENTATION-ROADMAP.md`)

**Current branch:**
`master`

**Current milestone:**
Architecture review

**Last completed:**
V2 planning document set drafted and pushed (`docs/v2/00-README.md` through `10-BACKLOG.md`)

**In progress:**
Owner review of `docs/v2/` — nothing implementation-facing is in progress

**Next:**
Accept/revise the proposed decisions in `docs/v2/08-DECISION-LOG.md`; once accepted, first concrete action is `BL-001` (Phase 0): tag the current commit as the V1 reference baseline

**Blocked by:**
None — planning work is complete and awaiting review, not stuck on anything

**Current known-good tag:**
None yet. Recommended tag name `v1-blueberry-reference`, not yet created — this is `BL-001` in `docs/v2/10-BACKLOG.md`, the first step of Phase 0, deliberately not done until the plan itself is accepted

**Tests at baseline:**
122 passed, 0 failed (`pytest -q`, verified at commit `787bb9e`); `scripts/validate_records.py` passes with zero schema errors

**Important decisions pending:**
(IDs match `docs/v2/08-DECISION-LOG.md`)
- D-010 — Claim: separate schema, or remain a `fact.classification` value?
- D-011 — Does `Recommendation` replace `evidence.priority`, or coexist with it?
- D-001 through D-009 — proposed (PostgreSQL, JSON interchange contract, FastAPI retained, frontend retained initially, AI provider abstraction, collector abstraction, Domain Packs, Organization/Workspace/Domain scoping, no big-bang rewrite) — not individually blocking, but none are accepted yet
