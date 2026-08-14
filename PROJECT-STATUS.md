# Project Status

*Maintained by Claude. Updated at the end of each work session that changes project state. Keep short — this is a status check, not a changelog (see `docs/reviews/CURRENT-STATE-AUDIT.md` and `docs/v2/` for detail).*

**Last updated:** 2026-08-14

---

**Current program:**
Intelligence OS V2

**Current stage:**
Phase 2B.2 complete — Core query services and Berries domain services now exist (`app/queries/`, `app/services/berries/`), a single composition boundary wires them to the record-repository layer (`app/composition.py`), and `app/main.py`'s read paths are migrated onto that stack with no externally observable behavior change. Write paths (review/publish and every other mutation) are untouched, per this slice's explicit scope.

**Current branch:**
`v2/intelligence-os`

**Next phase:**
Phase 2B.3 — Write-path migration and transactional workflow (`docs/v2/10-BACKLOG.md` BL-033), migrating review/publish onto `JsonUnitOfWork` — not started, pending owner authorization. Read `docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md` Part 10.4 first: it documents a real gap between review/publish's actual write sequence and what `JsonUnitOfWork` currently compensates.

**Last completed:**
Phase 2B.2 (2026-08-14): 7 Core query services (`app/queries/`: `ReferenceQueryService`, `EntityIntelligenceQueryService`, `LineageQueryService`, `TimelineQueryService`, `ScopeQueryService`, `CoverageQueryService`, `SearchQueryService`) and 2 Berries domain services (`app/services/berries/`: `BerriesLandscapeService`, `BerriesVarietyService`, plus `geography.py`'s region-bucketing/`berry_label()`), composed through `app/composition.py` (`get_repositories()`/`get_query_services()`/`get_domain_services()`, cached per `(data_dir, schemas_dir)` so test `DATA_DIR` monkeypatching stays correctly isolated). `app/main.py`'s storage-touching loaders (`all_evidence`, `all_entities`, `all_facts`, `all_relationships`, `all_signals`, `all_assessments`, `all_recommendations`, `load_strategic_questions`, `load_sources`) now delegate to repositories; `signal_detail`/`assessment_detail`/`recommendation_detail` use `LineageQueryService` to resolve their linked-record fields; `landscape_context()` delegates to `BerriesLandscapeService`; every migrated function keeps its exact original name and signature (verified against every `main.X` reference in `tests/*.py` and `scripts/build_static.py`). 20 new query-service tests (`tests/queries/`) against temporary repository fixtures. `docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md` Part 10 records the final R1-R18 mapping and Part 11's write-call-site audit (W1-W6, unchanged this task) — including a genuine finding: review/publish's entity-save step is not exclusively `create()` calls as `JsonUnitOfWork`'s own docstring states; publishing evidence naming an already-known entity performs an uncompensated `update()` in the same operation, a real gap Phase 2B.3 must resolve, not fixed here.

Previously: Phase 2B.1 (2026-08-14) — the record-repository layer at `app/repositories/`. Before that: Phase 2A (2026-08-14) — `docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md`, D-012 (analytical scope). Before that: tablet navigation breakpoint fix; Phase 1.5B (`BL-026` – `BL-029`).

**Findings worth knowing about (documented, not silently resolved):**
- **Review/publish's actual write sequence is not create-only.** `app/repositories/unit_of_work.py`'s docstring (written during Phase 2B.1, before this re-read) states review/publish is "exclusively a sequence of `create()` calls." Re-reading the route in full this task found that's not accurate: when a typed company/variety/geography name matches an already-existing entity (the common case for ongoing coverage of a known company), `save_entity()` performs a genuine update of that entity's `evidence_ids`/`fact_ids`/`relationship_ids` — in the same logical publish operation as the Fact/Relationship/Evidence creates. `JsonUnitOfWork` does not compensate `update()` calls on rollback. See `docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md` Part 10.4 for the full mutation-sequence trace and what Phase 2B.3 must decide. `JsonUnitOfWork` itself is unmodified this task — it is not wired into any route yet, so nothing live is affected today.
- **One direct filesystem read remains in an application read path, and it's justified, not an oversight:** `list_drafts()` (Review Queue, duplicate detection) still reads `inbox/evidence/` directly via `load_json_files()`, because Phase 2B.1 explicitly did not build a `DraftRepository` (only 9 named object types were in scope). `docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md` Part 10.3 documents this as deliberate, not deferred-and-forgotten.
- A single, low-materiality ordering nuance: `EvidenceRepository.list()` (built in Phase 2B.1) sorts by published/captured date descending, matching `published_evidence()`'s existing sort exactly — but `all_evidence()` (unsorted, raw file-path order, before this task) now inherits that same sort too. Verified against every `all_evidence()` call site in `app/main.py`: none depend on its order except `published_evidence()` itself (which already re-sorted identically) — the one exception is `find_possible_duplicates()`'s reviewer-facing duplicate-warning list, whose display order was never a specified or tested contract. Flagged here per this task's transparency requirement, not silently absorbed.

**In progress:**
Nothing. Phase 2B.2 is complete and fully verified.

**Next:**
Owner authorization to begin Phase 2B.3 (write-path migration), scoped by `docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md` Part 10.4 and `docs/v2/10-BACKLOG.md` BL-033.

**Next implementation action:**
Not started — pending owner authorization. Phase 2B.3: migrate review/publish (`docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md` W6) onto `JsonUnitOfWork`, resolving the entity-update compensation gap Part 10.4 documents; migrate remaining write routes (facts, relationships, sources, signals, assessments, recommendations).

**Blocked by:**
None.

**Known-good V1 reference:**
Tag `v1-blueberry-reference` → commit `432a96bd4efce1991df83b60aa1587154ba19528`. Unaffected by Phase 1A/1B/1.5A/1.5B/2A/2B.1/2B.2 (all work on `v2/intelligence-os`, `master` untouched).

**Architecture documents:**
Accepted (`docs/v2/00-README.md` through `10-BACKLOG.md`, 2026-08-13). `docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md` (2026-08-14, Part 9 addendum added 2026-08-14, Part 10 addendum added 2026-08-14) is the authoritative Phase 2B implementation spec.

**Tests at baseline:**
353 passed, 0 failed (`pytest -q`) — 333 as of Phase 2B.1 + 20 new query-service tests (`tests/queries/test_query_services.py`, against temporary repository fixtures). `scripts/validate_records.py` passes with zero schema errors. `scripts/build_static.py` succeeds (1,463 pages, unchanged from Phase 2B.1). No write route, template content, or PostgreSQL work touched; no write migration occurred. Runtime read-path behavior is unchanged (verified by the full pre-existing test suite passing without modification, plus manual code-search confirming no route/helper does direct JSON-folder scanning for reads except the justified `list_drafts()` exception).

**Important decisions — status:**
(IDs match `docs/v2/08-DECISION-LOG.md`)
- D-001 through D-009 — **ACCEPTED**
- D-010 — Claim stays a `fact.classification` value — **ACCEPTED (Option A)**, implemented
- D-011 — Recommendation and Evidence Priority coexist permanently — **ACCEPTED**, implemented
- D-007 (declarative Domain Packs, narrowed Phase 1 scope) — **ACCEPTED**, implemented
- D-012 (explicit analytical scope, separate from provenance) — **ACCEPTED**, schema-level implemented (Phase 2A); query-level `ScopeQueryService.explicit_scope()`/`records_by_entity_intersection()`/`scope_disagreements()` implemented and tested (Phase 2B.2), but not yet wired into any live route filter — Landscape's Assessment/Recommendation branch still uses the legacy derived-intersection rule only, preserving its exact existing behavior

No decisions remain open. No PostgreSQL, AI integration, or write-migration work has begun.
