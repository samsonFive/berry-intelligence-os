# Project Status

*Maintained by Claude. Updated at the end of each work session that changes project state. Keep short — this is a status check, not a changelog (see `docs/reviews/CURRENT-STATE-AUDIT.md` and `docs/v2/` for detail).*

**Last updated:** 2026-08-14

---

**Current program:**
Intelligence OS V2

**Current stage:**
Phase 1.5 complete — both the intelligence-object activation (1.5A: BL-024/BL-025) and the synthesis-experience prototype (1.5B: BL-026 – BL-029). Signal, Assessment, and Recommendation are real objects; a Blueberry Landscape view, an enhanced Company portfolio view, and an enhanced Variety intelligence view all synthesize them against real data. **Phase 1.5 is now fully complete.** The Phase 1.5 visual acceptance review's one MUST-FIX-BEFORE-PHASE-2 finding (tablet-width sidebar collapse) has been resolved (2026-08-14) — **Phase 2 is now unblocked.**

**Current branch:**
`v2/intelligence-os`

**Next phase:**
Phase 2 — Repository/storage abstraction (`docs/v2/07-IMPLEMENTATION-ROADMAP.md`) — not started, pending owner authorization. No longer blocked on any Phase 1.5 finding.

**Last completed:**
Tablet navigation breakpoint fix (2026-08-14). `app/static/app.css`'s mobile sidebar-collapse rule moved from `@media(max-width:800px)` to `@media(max-width:834px)` — a single-value change, resolving `docs/v2/PHASE-1-5-VISUAL-REVIEW.md`'s only MUST-FIX-BEFORE-PHASE-2 finding (the sidebar previously stayed visible at real tablet-portrait widths of 768-834px, cramping content). No navigation redesign, no information-architecture change, no page-content change. Verified with Playwright at 768/820/834/1024/1440px: sidebar hides with zero page overflow at all three tablet widths, and 1024/1440px are bit-for-bit unchanged (both were already above both the old and new threshold). `pytest -q` (200/200 passed) and `scripts/build_static.py` (1,463 pages) both re-run clean against the change.

Previously: `BL-026` – `BL-029` (Phase 1.5B, 2026-08-13). Built `GET /landscapes/berries/blueberry` (`app/templates/landscape.html`), synthesizing Signals, Assessments, Recommendations, Strategic Questions, a company competitive-field rollup, a variety rollup, a geographic-footprint table, "recent meaningful movement" evidence, and an evidence-coverage/limitations summary from real data — with no composite "competitive strength" or "top variety" score anywhere (every count is a labeled coverage indicator). Enhanced the existing generic `entity.html`/`entity_detail()` (not a forked Company/Variety template) with: an "Intelligence touching this record" section (Signals/Assessments/Recommendations linked to any entity), a "Portfolio & network" section (every entity's relationships rendered as direction-honest, evidence-linked edges — `grouped_relationships_for_entity()`, entity-type-agnostic), a "Strategic questions this bears on" section, and — for varieties specifically — a "Trait profile" table resolving the real, previously-unrendered `attributes.traits[]` data with an honest OWNER/MARKETER CLAIM vs. independently-sourced-measurement vs. UNRESOLVED distinction, plus a "Breeding program & IP" section linking to the real breeding-program entity and best-effort-matching the variety's patent number against live patent entities (never guessing when no match exists). Added `tests/test_synthesis_views.py` (20 tests) covering the aggregation functions and the rendered routes. Wrote `docs/v2/PHASE-1-5-PROTOTYPE-FINDINGS.md`, the required Phase 1.5 findings document. Then, `docs/v2/PHASE-1-5-VISUAL-REVIEW.md` (24 screenshots + written review), which surfaced the tablet-breakpoint finding this session resolved.

**Findings worth knowing about (documented, not silently resolved — full detail in `docs/v2/PHASE-1-5-PROTOTYPE-FINDINGS.md` and `docs/v2/PHASE-1-5-VISUAL-REVIEW.md`):**
- Zero schema changes were needed to build any of the three synthesis views — a strong signal the Phase 1 domain model is sound.
- One concrete schema gap found: Assessment and Recommendation have no domain/berry-scope field of their own (unlike Entity/Evidence/Signal), so the Landscape had to derive berry-relevance transitively via `entity_ids` intersection — a working approximation, not a design recommendation. Recommended timing: resolve **during Phase 2**.
- One real data-hygiene finding: 5 entities + 3 evidence records in the live dataset are explicitly self-described as fictional V1 seed/demo data ("Fictional ... used as seed data" in their own description field) but live in the same folders as real data with no structural flag distinguishing them. Hard-coded-excluded from the Landscape (`SEED_FIXTURE_ENTITY_IDS`/`SEED_FIXTURE_EVIDENCE_IDS`, `app/main.py`) rather than silently included as if real. Recommended timing: resolve **no later than Phase 3 Step 1** (the archival step).
- 9 concrete missing repository-query capabilities and a 9-item Phase 2 repository-interface requirements list, both derived from what this prototype actually needed (not guessed in advance).
- Every berry-specific assumption introduced is classified CORE / DOMAIN PACK / DEFER in the findings doc — e.g. the entity-relationship rendering is fully generic (CORE), the competitive-field/variety-rollup logic is Domain-Pack-report-template-shaped (DOMAIN PACK), and the seed-fixture exclusion list is neither (DEFER — a data-hygiene problem, not a domain boundary one).
- The visual acceptance review's one MUST-FIX-BEFORE-PHASE-2 finding (tablet sidebar-collapse breakpoint) is now **resolved** (this session). Its remaining PHASE-4/LATER-classified suggestions (wide-table scroll affordance, badge-stacking row heights, a raw-id duplication on the Variety page, minor wording) are unresolved and not blocking.

**In progress:**
Nothing. Phase 1.5, its visual review, and the one MUST-FIX finding from that review are all complete and verified.

**Next:**
Owner authorization to begin Phase 2 (repository/storage abstraction), informed directly by `docs/v2/PHASE-1-5-PROTOTYPE-FINDINGS.md`'s Section 8. No outstanding blocker.

**Next implementation action:**
Not started — pending owner authorization. Phase 2: define repository interfaces per core object type, covering the query patterns Phase 1.5B's findings identified, and address the Assessment/Recommendation domain-scope gap as part of that design.

**Blocked by:**
None.

**Known-good V1 reference:**
Tag `v1-blueberry-reference` → commit `432a96bd4efce1991df83b60aa1587154ba19528`. Unaffected by Phase 1A/1B/1.5A/1.5B (all work on `v2/intelligence-os`, `master` untouched).

**Architecture documents:**
Accepted (`docs/v2/00-README.md` through `10-BACKLOG.md`, 2026-08-13).

**Tests at baseline:**
200 passed, 0 failed (`pytest -q`) — 122 original + 11 Phase 1A schema tests + 21 Phase 1B Domain Pack tests + 26 Phase 1.5A referential-integrity tests + 20 Phase 1.5B synthesis-view tests. Count unchanged by the tablet-breakpoint fix (CSS-only, no test files added or modified). `scripts/validate_records.py` passes with zero schema errors (no schema files were touched this phase). `scripts/build_static.py` succeeds (1,463 pages). No pre-existing production data was rewritten; only additive routes/templates were added (existing Signal/entity templates were extended, not replaced); no PostgreSQL work; no AI integration; no Collector execution code.

**Important decisions — status:**
(IDs match `docs/v2/08-DECISION-LOG.md`)
- D-001 through D-009 — **ACCEPTED**
- D-010 — Claim stays a `fact.classification` value — **ACCEPTED (Option A)**, implemented
- D-011 — Recommendation and Evidence Priority coexist permanently — **ACCEPTED**, implemented (Phase 1.5B's synthesis views do not touch or read from `evidence.priority`'s queues)
- D-007 (declarative Domain Packs, narrowed Phase 1 scope) — **ACCEPTED**, implemented: `domain-packs/berries/` covers exactly the six required surfaces; report templates/filters/visualization config remain unimplemented, as specified — Phase 1.5B's Landscape logic is exactly the kind of "report template" content `04-DOMAIN-PACK-SPEC.md` Section 6 anticipated, flagged as a DOMAIN PACK candidate in the findings doc rather than built as one prematurely

No decisions remain open. No PostgreSQL, AI integration, or Phase 2 work has begun.
