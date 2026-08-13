# Intelligence OS — Backlog (V2)

**Status:** Planning draft, not accepted. Every item is `Not started`. This translates `07-IMPLEMENTATION-ROADMAP.md`'s phase-level goals into bounded, individually-completable work items — none of them "giant undifferentiated tasks," per the roadmap's own constraint.

**Size key**: S = a few hours to ~1 day of focused work. M = a few days. L = a week or more, or high uncertainty — an `L` item is itself a signal it may need splitting further once scoped in detail.

---

## Phase 0 — Freeze / reference baseline

| ID | Title | Purpose | Dependencies | Acceptance criteria | Status | Size |
|---|---|---|---|---|---|---|
| BL-001 | Tag V1 reference baseline | Guarantee a recoverable, known-good V1 state before any V2 work begins | None | Named git tag pushed; tests/validation/static build all pass against it in isolation | Not started | S |
| BL-002 | Document V1 baseline's CI independence | Confirm V2 branch work can't accidentally affect V1's live deployment | BL-001 | V1's `deploy-pages.yml` continues to succeed from the tag with zero changes required | Not started | S |

## Phase 1 — V2 domain definitions and abstractions

| ID | Title | Purpose | Dependencies | Acceptance criteria | Status | Size |
|---|---|---|---|---|---|---|
| BL-010 | Write `assessment.schema.json` | New core object per `03-DOMAIN-MODEL.md` | BL-001 | Schema validates a hand-written example Assessment record; requires ≥1 `fact_ids` | Not started | S |
| BL-011 | Write `recommendation.schema.json` | New core object per `03-DOMAIN-MODEL.md` | BL-001, D-011 decision | Schema validates a hand-written example; requires ≥1 `assessment_or_signal_ids` | Not started | S |
| BL-012 | Extend `evidence.schema.json` | Unified review-state enum, `source_tier`, `event_date`, `information_confidence` — all optional/additive | BL-001 | Full V1 evidence dataset (1,263 records) validates unchanged against extended schema | Not started | M |
| BL-013 | Extend `relationship.schema.json` | Add `confidence` field (P-3, blueberry import proposal) | BL-001 | Full V1 relationship dataset (204 records) validates unchanged | Not started | S |
| BL-014 | Extend `signal.schema.json` | Enforce `minItems: 2` on `evidence_ids`; richer status enum | BL-001 | The 6 staged blueberry signals validate against the new schema | Not started | S |
| BL-015 | Tighten `strategic-question.schema.json` status enum | `active/answered/retired` per P-6 | BL-001 | Full V1 strategic-question dataset (9 records) validates unchanged | Not started | S |
| BL-016 | Resolve D-010 (Claim schema) | Unblock Phase 1 schema work | BL-001 | Recorded decision in `08-DECISION-LOG.md`, either confirming (a) or scoping (b) | Not started | S |
| BL-017 | Resolve D-011 (Recommendation vs. `evidence.priority`) | Unblock Phase 4 planning | BL-001 | Recorded decision in `08-DECISION-LOG.md` | Not started | S |
| BL-018 | Write `domain-pack.schema.json` | Validates the manifest shape from `04-DOMAIN-PACK-SPEC.md` | BL-010 – BL-015 | A hand-written minimal manifest validates; a manifest missing a required section fails validation | Not started | M |
| BL-019 | Extract Berries entity types into Domain Pack `entity-types.json` | Replace hard-coded `SOURCE_ENTITY_TYPES`/implicit types with declared config | BL-018 | File lists all 9 live entity types (`CURRENT-STATE-AUDIT.md` Section 6), each entity in live data resolves to a declared type | Not started | S |
| BL-020 | Extract Berries relationship predicates into Domain Pack `relationship-predicates.json` | Include V1's 10 plus the 6 from P-2 | BL-018 | File lists 16 predicates; every live relationship (204 records) resolves to a declared predicate | Not started | S |
| BL-021 | Build Berries taxonomy files (roles, trait vocabulary) | Per P-9 and `04-DOMAIN-PACK-SPEC.md` Section 3 | BL-018 | Entity-role vocabulary file matches the 16 roles the blueberry import package already proposed | Not started | M |
| BL-022 | Migrate 9 live strategic questions into `strategic-question-templates.json` | Per `04-DOMAIN-PACK-SPEC.md` Section 4 | BL-018 | All 9 questions present, content unchanged | Not started | S |
| BL-023 | Build Berries `collector-templates.json` from the 120-source registry | Per `04-DOMAIN-PACK-SPEC.md` Section 5 | BL-018 | All 120 sources represented with their type/priority/berry/region metadata intact | Not started | M |

## Phase 2 — Repository/storage abstraction

| ID | Title | Purpose | Dependencies | Acceptance criteria | Status | Size |
|---|---|---|---|---|---|---|
| BL-030 | Define repository interfaces per core object type | The seam Phase 3 swaps behind | Phase 1 complete | Interface covers list/filter/get/create/update for every core type; documented | Not started | M |
| BL-031 | Implement JSON-file repository against the new interface | Prove the interface without changing behavior | BL-030 | Existing `load_json_files()` logic reachable only through the interface | Not started | M |
| BL-032 | Refactor evidence/entity routes onto the repository interface | Remove direct file I/O from route handlers | BL-031 | No route performs direct file I/O (verified by code search); all 122 tests pass unmodified in assertion | Not started | L |
| BL-033 | Refactor remaining routes (facts, relationships, sources, review, signals, strategic questions) onto the interface | Complete the abstraction | BL-032 | Same acceptance bar as BL-032, applied repo-wide | Not started | L |
| BL-034 | Build a second (in-memory) repository implementation for test speed | Prove the seam is real, not a renamed function call | BL-030 | Test suite can run against either implementation without route code changes | Not started | S |

## Phase 3 — PostgreSQL parity migration

| ID | Title | Purpose | Dependencies | Acceptance criteria | Status | Size |
|---|---|---|---|---|---|---|
| BL-040 | Generate Postgres schema from Phase 1 JSON schemas | Ground truth stays the JSON schema, not a hand-written DDL | Phase 1, Phase 2 complete | Every field/enum/required-optional distinction preserved; reviewed against schemas by hand | Not started | M |
| BL-041 | Implement Postgres-backed repository | Second real implementation of Phase 2's interface | BL-040, BL-030 | Passes the same test suite BL-034's in-memory implementation passes | Not started | L |
| BL-042 | One-time full dataset load into Postgres | Seed V2's operational store from V1's dataset | BL-041 | All 1,882 live records present, verified by automated count-and-content check | Not started | M |
| BL-043 | Build the continuous parity-check job | The core mitigation for R-01/R-11 | BL-042 | Job runs on a schedule, diffs every Postgres row against source JSON, alerts loudly on any discrepancy | Not started | L |
| BL-044 | Implement `Evidence` review-state migration mapping | Per the exact mapping in `06-MIGRATION-MAP.md` | BL-042 | Every evidence record's new `review_state` matches the documented mapping rule for its V1 `status`/`validated`/`auto_captured` combination | Not started | M |
| BL-045 | Dual-write period: application writes both JSON and Postgres | The actual bridge — no big-bang cutover | BL-041, BL-043 | Zero parity discrepancies over the defined observation window | Not started | L |
| BL-046 | Cut application reads over to Postgres; disable JSON writes | Completes the migration | BL-045 clean for observation window | App fully functional read/write against Postgres only; JSON files archived, not deleted | Not started | M |
| BL-047 | Pre-migration full Intelligence Package archival export | Independent backstop against R-01, separate from the parity job itself | BL-042 (can run before BL-045) | A complete, validated Intelligence Package of the pre-migration JSON state exists in cold storage | Not started | S |

## Phase 4 — Intelligence/synthesis layer

| ID | Title | Purpose | Dependencies | Acceptance criteria | Status | Size |
|---|---|---|---|---|---|---|
| BL-050 | Build Assessment create/review/approve UI | Extends the review-queue pattern to a new object type | Phase 3 complete, BL-010 | An analyst can create, review, and publish an Assessment through the UI | Not started | M |
| BL-051 | Build Recommendation create/review/approve UI | Same pattern for Recommendation | Phase 3 complete, BL-011, BL-017 | An analyst can create, review, and publish a Recommendation through the UI | Not started | M |
| BL-052 | Migrate 124 records' `priority` values into initial Recommendations | Per D-011's resolution | BL-051 | Every priority level currently set (`CURRENT-STATE-AUDIT.md` Section 4: reading/testing/commercial/monitoring counts) has a corresponding Recommendation record | Not started | M |
| BL-053 | Import the 6 staged blueberry Signals | Closes a gap open since 2026-08-04 | BL-014, Phase 3 complete | All 6 visible and correctly linked in the running app | Not started | S |
| BL-054 | Build "Berries Landscape" Intelligence Product / view | Proves the rollup/synthesis concept end-to-end | BL-050 – BL-053 | View shows information (a real geography-grouped rollup) not visible on any single existing page | Not started | L |
| BL-055 | Fix `/work-queue` vs. `/review` count discrepancy | Named directly in `CURRENT-STATE-AUDIT.md` as a live, current bug | Phase 3 complete | Both pages agree on backlog size, sourced from the same query | Not started | S |
| BL-056 | Add visual distinction for `disputed` status (facts and relationships) | Named directly in `CURRENT-STATE-AUDIT.md` Section 7/9 as a rendering gap | Phase 3 complete | A disputed fact/relationship is visually distinguishable from an active one without reading small print | Not started | S |

## Phase 5 — AI and collector framework

| ID | Title | Purpose | Dependencies | Acceptance criteria | Status | Size |
|---|---|---|---|---|---|---|
| BL-060 | Define AI provider interface | Core Design Principle #5 | Phase 4 complete | Interface covers propose-structure, propose-assessment, summarize at minimum | Not started | M |
| BL-061 | Implement first AI provider integration behind the interface | Prove the abstraction against a real provider | BL-060 | A real structuring proposal (Fact/Claim/Relationship) can be generated and lands in the review queue as `ai_proposed: true` | Not started | M |
| BL-062 | Implement `AI Job` object with cost/timing tracking | Direct mitigation for R-04 | BL-060, Phase 3's Postgres | Every AI Job records provider, cost, timing, outcome, and reviewer decision once reviewed | Not started | M |
| BL-063 | Define Collector interface | Core Design Principle #6 | Phase 4 complete | Interface covers `collect(source_config) -> list[RawCapture]` at minimum | Not started | S |
| BL-064 | Re-implement RSS collection behind the Collector interface | Re-home proven V1 logic, don't rewrite it | BL-063 | Identical output to V1's `check_source()` RSS behavior against the same feeds | Not started | M |
| BL-065 | Re-implement keyword-search collection behind the Collector interface | Same, for the Google-News-based path | BL-063 | Identical output to V1's `check_source()` keyword-search behavior | Not started | M |
| BL-066 | Implement `Collection Job` as a stored, auditable object | Replaces fire-and-forget background task | BL-064, BL-065 | Every collection run is visible, auditable, with status/error/count recorded | Not started | M |
| BL-067 | Generalize `resolve_real_summaries.py`'s crash/retry discipline into shared job-framework error handling | Reuse proven engineering rather than re-inventing it per job type | BL-062, BL-066 | Both AI Jobs and Collection Jobs share the same retry/circuit-breaker/crash-recovery code path | Not started | L |
| BL-068 | Second-provider swap test | Proves D-005/R-05's zero-lock-in claim | BL-061 | Configuring a second AI provider requires zero application code changes | Not started | S |

## Phase 6 — Reports, exports, and API

| ID | Title | Purpose | Dependencies | Acceptance criteria | Status | Size |
|---|---|---|---|---|---|---|
| BL-070 | Design and implement versioned read API (`/api/v2/...`) | Core Design Principle #11 | Phase 3 complete | Every core object type has a working, filterable read endpoint | Not started | L |
| BL-071 | Implement minimal authentication | Direct mitigation for R-10, required before any hosted deployment | Phase 3 complete | Write access requires authentication; `reviewer`/`approved_by` fields reference real Users | Not started | M |
| BL-072 | Build Report generation from Domain Pack templates | Closes the "customized intelligence reports" product-direction requirement | Phase 4 complete (Assessment/Recommendation exist to cite) | At least one report template generates a correct, fully lineage-traceable report against live data | Not started | L |
| BL-073 | Implement Intelligence Package export (JSON) | Core of `05-INTELLIGENCE-PACKAGE-SPEC.md` | BL-070 | Full-dataset export produces a valid manifest + all record types + `source-lineage.json` with empty `orphan_check` | Not started | M |
| BL-074 | Implement Intelligence Package export (JSONL, CSV) | Format completeness per the spec | BL-073 | Same content as JSON export, correctly reshaped, documented flattening notes for CSV | Not started | M |
| BL-075 | Implement Intelligence Package import (three-gate: dry-run/apply/approve) | Generalizes `import_package.py`'s proven pattern | BL-073 | A package exported by BL-073 can be re-imported into a fresh Workspace and round-trips content-identically | Not started | L |
| BL-076 | Round-trip validation test: full dataset export → import → compare | The actual proof this all works | BL-075 | Zero content differences between source and round-tripped Workspace | Not started | M |
| BL-077 | Document and publish a working external-client example against the API | Proves "downstream systems can consume this" | BL-070, BL-071 | A runnable example script (even minimal) successfully reads structured intelligence via the API | Not started | S |

## Phase 7 — Second-domain validation

| ID | Title | Purpose | Dependencies | Acceptance criteria | Status | Size |
|---|---|---|---|---|---|---|
| BL-080 | Choose and scope the second Domain Pack | Decision point: unrelated industry (recommended) vs. second berry | Phase 6 complete | A named domain, a named small dataset target, a named owner | Not started | S |
| BL-081 | Build the second Domain Pack manifest and all contribution-surface files | Per `04-DOMAIN-PACK-SPEC.md` | BL-080 | Validates against `domain-pack.schema.json`; uses only declarative contribution surfaces, zero core code changes | Not started | L |
| BL-082 | Populate a small real dataset for the second domain | Enough to prove the mechanism | BL-081 | Tens of entities, real evidence, at least a few facts/relationships, sourced from real public information | Not started | M |
| BL-083 | Run a full lifecycle pass for the second domain | Collect → structure → review → publish → report → export | BL-082, BL-072, BL-075 | One complete pass succeeds end-to-end | Not started | M |
| BL-084 | Regression-check the Berries Domain Pack throughout | Prove multi-domain coexistence, not sequential replacement | BL-081 – BL-083 | Berries continues to function unaffected at every step | Not started | S |
| BL-085 | Record findings against `04-DOMAIN-PACK-SPEC.md` | Any point where core code needed to change is a spec defect to fix | BL-083 | Written findings document; any core-code touch is either fixed (spec updated, code reverted to declarative) or explicitly, deliberately accepted as a spec gap | Not started | M |

## Phase 8 — SaaS-readiness (if justified)

| ID | Title | Purpose | Dependencies | Acceptance criteria | Status | Size |
|---|---|---|---|---|---|---|
| BL-090 | Justification decision: is Phase 8 needed now? | The actual first "acceptance criterion" for this phase, per `07-IMPLEMENTATION-ROADMAP.md` | Phase 7 complete | A named reason, a named requester, and a scoped requirements document — or an explicit decision to not proceed yet | Not started | S |

*(Further Phase 8 items are deliberately not broken out here — writing detailed backlog items for infrastructure that may never be justified would itself violate the "don't add infrastructure merely because it's fashionable" instruction. BL-090's outcome determines whether this section grows.)*
