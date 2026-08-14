# Project Status

*Maintained by Claude. Updated at the end of each work session that changes project state. Keep short — this is a status check, not a changelog (see `docs/reviews/CURRENT-STATE-AUDIT.md` and `docs/v2/` for detail).*

**Last updated:** 2026-08-14

---

**Current program:**
Intelligence OS V2

**Current stage:**
Phase 2B.3 complete — all persisted Core-object writes now use repositories, and review/publish uses `JsonUnitOfWork` with create and existing-Entity update compensation.

**Current branch:**
`v2/intelligence-os`

**Next phase:**
Owner decision on the next authorized phase. BL-034, BL-035, PostgreSQL, and all later phases remain not started.

**Last completed:**
Phase 2B.3 (2026-08-14): BL-033 completed. Evidence validate/purge and every persisted Core-object create/update/delete path now cross repository interfaces. Review/publish uses one UoW across Entity, Fact, Relationship, and Evidence writes; matched existing Entities are restored from prior-value snapshots if a later write fails. Inbox drafts, attachments, and blocked-domain configuration remain documented filesystem exceptions because Phase 2 defines no repositories for them. 354 tests, record validation, and the 1,463-page static build pass.

Previously: Phase 2B.1 (2026-08-14) — the record-repository layer at `app/repositories/`. Before that: Phase 2A (2026-08-14) — `docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md`, D-012 (analytical scope). Before that: tablet navigation breakpoint fix; Phase 1.5B (`BL-026` – `BL-029`).

**Findings worth knowing about (documented, not silently resolved):**
- **Review/publish's existing-Entity update gap is resolved.** Phase 2B.3 chose Part 10.4's snapshot-and-restore option: `JsonUnitOfWork` captures prior record values for updates and restores them during reverse-order rollback. The draft is deleted only after a successful UoW exit. Attachment moves remain outside the UoW and retain the JSON backend's documented best-effort limitation.
- **One direct filesystem read remains in an application read path, and it's justified, not an oversight:** `list_drafts()` (Review Queue, duplicate detection) still reads `inbox/evidence/` directly via `load_json_files()`, because Phase 2B.1 explicitly did not build a `DraftRepository` (only 9 named object types were in scope). `docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md` Part 10.3 documents this as deliberate, not deferred-and-forgotten.
- A single, low-materiality ordering nuance: `EvidenceRepository.list()` (built in Phase 2B.1) sorts by published/captured date descending, matching `published_evidence()`'s existing sort exactly — but `all_evidence()` (unsorted, raw file-path order, before this task) now inherits that same sort too. Verified against every `all_evidence()` call site in `app/main.py`: none depend on its order except `published_evidence()` itself (which already re-sorted identically) — the one exception is `find_possible_duplicates()`'s reviewer-facing duplicate-warning list, whose display order was never a specified or tested contract. Flagged here per this task's transparency requirement, not silently absorbed.

**In progress:**
Nothing. Phase 2B.3 is complete and fully verified.

**Next:**
Owner authorization for the next bounded phase.

**Next implementation action:**
Not started — BL-034, BL-035, PostgreSQL, and later work were explicitly outside Phase 2B.3.

**Blocked by:**
None.

**Known-good V1 reference:**
Tag `v1-blueberry-reference` → commit `432a96bd4efce1991df83b60aa1587154ba19528`. Unaffected by Phase 1A/1B/1.5A/1.5B/2A/2B.1/2B.2 (all work on `v2/intelligence-os`, `master` untouched).

**Architecture documents:**
Accepted (`docs/v2/00-README.md` through `10-BACKLOG.md`, 2026-08-13). `docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md` (2026-08-14, Part 9 addendum added 2026-08-14, Part 10 addendum added 2026-08-14) is the authoritative Phase 2B implementation spec.

**Tests at baseline:**
354 passed, 0 failed (`pytest -q`). `scripts/validate_records.py` passes with zero schema errors. `scripts/build_static.py` succeeds (1,463 pages). BL-034, BL-035, PostgreSQL, templates, and data records were untouched.

**Important decisions — status:**
(IDs match `docs/v2/08-DECISION-LOG.md`)
- D-001 through D-009 — **ACCEPTED**
- D-010 — Claim stays a `fact.classification` value — **ACCEPTED (Option A)**, implemented
- D-011 — Recommendation and Evidence Priority coexist permanently — **ACCEPTED**, implemented
- D-007 (declarative Domain Packs, narrowed Phase 1 scope) — **ACCEPTED**, implemented
- D-012 (explicit analytical scope, separate from provenance) — **ACCEPTED**, schema-level implemented (Phase 2A); query-level `ScopeQueryService.explicit_scope()`/`records_by_entity_intersection()`/`scope_disagreements()` implemented and tested (Phase 2B.2), but not yet wired into any live route filter — Landscape's Assessment/Recommendation branch still uses the legacy derived-intersection rule only, preserving its exact existing behavior

No decisions remain open. No PostgreSQL, AI integration, or write-migration work has begun.
