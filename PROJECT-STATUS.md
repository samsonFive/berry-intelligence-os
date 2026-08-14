# Project Status

*Maintained by Claude. Updated at the end of each work session that changes project state. Keep short — this is a status check, not a changelog (see `docs/reviews/CURRENT-STATE-AUDIT.md` and `docs/v2/` for detail).*

**Last updated:** 2026-08-13

---

**Current program:**
Intelligence OS V2

**Current stage:**
Phase 1.5A complete — the intelligence-object portion of Phase 1.5 (BL-024, BL-025 only). Signal, Assessment, and Recommendation are now real, reviewable, JSON-backed objects in the running app. The Landscape/Company/Variety prototypes and findings doc (BL-026 – BL-029) are deliberately **not** part of this task and remain not started.

**Current branch:**
`v2/intelligence-os`

**Next phase:**
Rest of Phase 1.5 (BL-026 – BL-029: Landscape/Company/Variety prototypes, findings doc) — not started, pending owner authorization.

**Last completed:**
`BL-024`, `BL-025` (Phase 1.5A, 2026-08-13). Imported the 6 staged blueberry Signals into `data/signals/` (status/reviewer/dates preserved exactly, no upgrades; stale `not_importable_reason` dropped; all evidence/entity/strategic-question references confirmed resolving against live data before import). Built list/detail/create routes and templates for both Assessment and Recommendation (`app/main.py`, `app/templates/assessment_*.html`, `app/templates/recommendation_*.html`), reusing the existing Signal create-form pattern; human-authored only, no AI-assisted generation. Created one real Assessment (`assessment-financial-capital-entering-berry-genetics-ownership`, medium confidence, grounded in 4 real Facts about Hortifrut/Costa/Planasa ownership changes, with 1 counterevidence fact) and one real Recommendation (`recommendation-treat-costa-driscolls-as-structurally-linked`, `escalate_to_commercial_review`, medium priority) with full traced lineage back to Evidence, verified live in the running app. Added nav entries for Signals/Assessments/Recommendations and trust-distinguishing badges (fact/claim/assessment/signal/recommendation/counterevidence) across every template that renders these types. Added `tests/test_intelligence_lineage.py` (26 tests) closing the referential-integrity gap `scripts/validate_records.py` doesn't cover — every cross-object reference (evidence_ids, fact_ids, entity_ids, strategic_question_ids, assessment_ids, signal_ids, counterevidence_ids) is now checked against live data, failing loudly on orphans.

**Findings worth knowing about (documented, not silently resolved):**
- No compatibility surprises this time (contrast with Phase 1A's Signal-schema finding): the six staged signals' evidence/entity/strategic-question ids were explicitly verified to resolve against current live data before import, not assumed from schema validity alone. Assessment/Recommendation routes were entirely new, so there were no prior live-app constants to reconcile against.
- The staged signals carry package-specific fields (`observation`, `why_it_might_matter`, `what_would_confirm_it`, `what_would_falsify_it`, `proposed_by`, `proposed_at`) that the pre-existing Signal templates never rendered (they only knew about `description`/`first_seen`/`last_updated`, fields the staged signals don't populate). Extended `signal_list.html`/`signal_detail.html` to fall back to and render these package fields when present, so the six imported signals are actually readable, not just technically present.

**In progress:**
Nothing. Phase 1.5A is complete and fully verified.

**Next:**
Owner authorization to begin the rest of Phase 1.5 (BL-026 – BL-029) or Phase 2, per `docs/v2/07-IMPLEMENTATION-ROADMAP.md`.

**Next implementation action:**
Not started — pending owner authorization. Candidates: BL-026 (Blueberry Landscape view), BL-027 (Company portfolio view), BL-028 (Variety intelligence view), BL-029 (Phase 1.5 findings doc), or Phase 2 (repository/storage abstraction).

**Blocked by:**
None.

**Known-good V1 reference:**
Tag `v1-blueberry-reference` → commit `432a96bd4efce1991df83b60aa1587154ba19528`. Unaffected by Phase 1A/1B/1.5A (all work on `v2/intelligence-os`, `master` untouched).

**Architecture documents:**
Accepted (`docs/v2/00-README.md` through `10-BACKLOG.md`, 2026-08-13).

**Tests at baseline:**
180 passed, 0 failed (`pytest -q`) — 122 original + 11 Phase 1A schema tests + 21 Phase 1B Domain Pack tests + 26 Phase 1.5A referential-integrity tests. `scripts/validate_records.py` passes with zero schema errors. `scripts/build_static.py` succeeds (1,462 pages). No pre-existing production data was rewritten; only additive routes/templates were added (Signal templates were extended, not replaced); no PostgreSQL work; no AI integration; no Collector execution code.

**Important decisions — status:**
(IDs match `docs/v2/08-DECISION-LOG.md`)
- D-001 through D-009 — **ACCEPTED**
- D-010 — Claim stays a `fact.classification` value — **ACCEPTED (Option A)**, implemented
- D-011 — Recommendation and Evidence Priority coexist permanently — **ACCEPTED**, implemented (Phase 1.5A's Recommendation workflow does not touch or read from `evidence.priority`'s queues)
- D-007 (declarative Domain Packs, narrowed Phase 1 scope) — **ACCEPTED**, implemented: `domain-packs/berries/` covers exactly the six required surfaces; report templates/filters/visualization config remain unimplemented, as specified

No decisions remain open. No PostgreSQL, AI integration, or Landscape/Company/Variety synthesis redesign work has begun.
