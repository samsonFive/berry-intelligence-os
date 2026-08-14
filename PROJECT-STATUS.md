# Project Status

*Maintained by Claude. Updated at the end of each work session that changes project state. Keep short — this is a status check, not a changelog (see `docs/reviews/CURRENT-STATE-AUDIT.md` and `docs/v2/` for detail).*

**Last updated:** 2026-08-14

---

**Current program:**
Intelligence OS V2

**Current stage:**
Phase 1B complete — Berries Domain Pack foundation added (BL-018 – BL-023). Phase 1 is now fully complete.

**Current branch:**
`v2/intelligence-os`

**Next phase:**
Phase 1.5 — Intelligence UX Prototype (not started)

**Last completed:**
`BL-018` – `BL-023` (Phase 1B). New: `schemas/domain-pack.schema.json` (generic manifest schema, no berry-specific content) and `domain-packs/berries/` — the first real declarative Domain Pack: `manifest.json`, `entity-types.json` (9 types), `relationship-predicates.json` (16: the 10 V1 predicates + 6 accepted extensions), `taxonomies/entity-role-vocabulary.json` (65 roles) and `taxonomies/trait-vocabulary.json` (10 traits), `strategic-question-templates.json` (9 templates), `collector-templates.json` (all 120 sources, 0 excluded). 21 new tests added (`tests/test_domain_pack.py`) implementing the task's 10 deterministic validation checks. This task creates and validates Domain Pack artifacts only — `app/main.py` still reads from its own hard-coded constants; nothing was migrated to read from the pack.

**Findings worth knowing about (documented, not silently resolved):**
- `entity-role-vocabulary.json`: live entity roles turned out far broader (65 distinct strings, spanning every entity type) than the blueberry import package's own P-9 proposal (16 roles, written with company-type entities specifically in mind). Both are included, tagged by source; 10 likely-overlapping role clusters (e.g. the `genetics_*` family) are documented as open questions, not merged.
- `trait-vocabulary.json`: `eating-quality`'s own description already restates what `soluble-solids` and `titratable-acidity` measure more precisely — flagged as one unresolved overlap, kept as three separate entries (matching live data).
- `entity-types.json`: corrected two illustrative-but-unverified assumptions from `docs/v2/04-DOMAIN-PACK-SPEC.md`'s own worked example (company/geography/patent "traits" that don't exist as real trait entities in live data) — the earlier planning doc's example was aspirational, not verified against data at the time it was written.

**In progress:**
Nothing. Phase 1B is complete and fully verified.

**Next:**
Owner authorization to begin Phase 1.5 (`docs/v2/07-IMPLEMENTATION-ROADMAP.md`).

**Next implementation action:**
Phase 1.5 — import the 6 staged blueberry Signals, author one Assessment and one Recommendation, prototype landscape/company/variety views, all against the current JSON-backed repository (no PostgreSQL). **Not started — pending owner authorization.**

**Blocked by:**
None.

**Known-good V1 reference:**
Tag `v1-blueberry-reference` → commit `432a96bd4efce1991df83b60aa1587154ba19528`. Unaffected by Phase 1A/1B (all work on `v2/intelligence-os`, `master` untouched).

**Architecture documents:**
Accepted (`docs/v2/00-README.md` through `10-BACKLOG.md`, 2026-08-13).

**Tests at baseline:**
154 passed, 0 failed (`pytest -q`) — 122 original + 11 Phase 1A schema tests + 21 Phase 1B Domain Pack tests. `scripts/validate_records.py` passes with zero schema errors. No production data was rewritten; no routes, templates, or UI behavior changed; no PostgreSQL work; no Collector execution code.

**Important decisions — status:**
(IDs match `docs/v2/08-DECISION-LOG.md`)
- D-001 through D-009 — **ACCEPTED**
- D-010 — Claim stays a `fact.classification` value — **ACCEPTED (Option A)**, implemented
- D-011 — Recommendation and Evidence Priority coexist permanently — **ACCEPTED**, implemented
- D-007 (declarative Domain Packs, narrowed Phase 1 scope) — **ACCEPTED**, implemented: `domain-packs/berries/` covers exactly the six required surfaces; report templates/filters/visualization config remain unimplemented, as specified

No decisions remain open. No Phase 1.5, PostgreSQL, Collector execution, or UI/route/template work has begun.
