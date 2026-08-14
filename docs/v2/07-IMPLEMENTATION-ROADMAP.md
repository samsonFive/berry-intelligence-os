# Intelligence OS — Implementation Roadmap (V2)

**Status:** Reviewed and accepted with revisions, 2026-08-13 (see `08-DECISION-LOG.md`). **Implementation still has not begun** — this planning-review pass updated the plan itself; the first concrete implementation action is Phase 0 / `BL-001`, which remains not started (see `PROJECT-STATUS.md`).

## How phases work

Each phase has a stated goal, a bounded scope (what's in, explicitly what's out), and acceptance criteria specific enough to check off, not "done when it feels done." Phases are sequential in dependency, not necessarily in calendar time — a phase can start being scoped/designed before the prior one's implementation fully lands, but its *work* depends on the prior phase's acceptance criteria being met. Detailed work items for each phase are broken out in `10-BACKLOG.md`; this document stays at phase-goal granularity.

---

## Phase 0 — Freeze / reference baseline

**Goal**: guarantee the current, working Berry Intelligence OS remains recoverable and usable throughout everything that follows (Core Design Principle #10).

**Scope**:
- Tag the current commit (the latest planning-review commit, post-acceptance) as the V1 reference baseline — recommended name `v1-blueberry-reference`, matching `PROJECT-STATUS.md`.
- Confirm the tagged baseline's own CI (tests, schema validation, static build) passes in isolation, independent of any V2 work-in-progress branch.
- Establish that V1 keeps deploying (GitHub Pages) unaffected by V2 development — V2 work happens on a separate branch/path, never by modifying the V1 deployment pipeline in place until a deliberate cutover decision is made (which is itself out of scope for Phase 0).

**Explicitly out of scope**: any schema change, any code change to `app/main.py`, any data change.

**Acceptance criteria**:
- A named, pushed git tag exists pointing at the frozen V1 commit.
- Running the full V1 test suite and `scripts/validate_records.py` against that tag, on a clean checkout, passes exactly as it did at audit time (122/122 tests, zero schema errors).
- V1's GitHub Pages deployment continues to succeed from the tagged baseline with no changes required.

---

## Phase 1 — V2 domain definitions and abstractions

**Goal**: get the target domain model (`03-DOMAIN-MODEL.md`) and Domain Pack spec (`04-DOMAIN-PACK-SPEC.md`) from planning documents into real, versioned schema artifacts — before any storage migration, so Phase 3 migrates data *into* a settled target shape rather than a moving one.

**Scope**:
- Write the new/extended JSON schemas: `assessment.schema.json`, `recommendation.schema.json` (new); extend `evidence.schema.json` (unified review-state, `source_tier`, `event_date`), `relationship.schema.json` (`confidence`), `signal.schema.json` (richer status enum, enforced `minItems: 2`), `strategic-question.schema.json` (tightened status enum). Per D-010 (ACCEPTED, Option A): **no separate `claim.schema.json`** — Claim stays `fact.classification == "claim"`.
- Write `domain-pack.schema.json` (validates the manifest shape from `04-DOMAIN-PACK-SPEC.md`), covering all eight contribution surfaces the spec defines — but see the next bullet for what Phase 1 actually *implements*.
- Build the Berries Domain Pack itself as the first real artifact against that schema — this is where V1's hard-coded entity types, relationship predicates, and constants (`BERRIES`, `SOURCE_ENTITY_TYPES`, `PRIORITY_DIMENSIONS`) get extracted into declarative Domain Pack content. **Scope narrowed on review (D-007 consequence)**: Phase 1 implements only the surfaces concretely required by the Berries reference build — manifest, entity types, relationship predicates, taxonomies, strategic-question templates, collector templates. Report templates, visualization configuration, and advanced filter configuration remain specified but unimplemented until Phase 1.5 or Phase 4 demonstrates a concrete need — avoid speculative abstraction ahead of proven use.

**Explicitly out of scope**: any database work, any change to the live running application, any AI/collector code, Domain Pack report templates / visualization config / advanced filters (deferred per above).

**Acceptance criteria**:
- Every new/extended schema validates against `scripts/validate_records.py`'s existing validator with zero code changes to the validator itself beyond adding the new schema files.
- The full V1 dataset (162 entities, 1,263 evidence, etc.) validates cleanly against the *extended* schemas with all new fields optional (no existing record becomes invalid) — a direct, checkable parity test.
- The Berries Domain Pack manifest validates against `domain-pack.schema.json`, implementing exactly the six narrowed-scope surfaces above, and contains every entity type, predicate, and taxonomy value currently in live use (verifiable by diffing against `CURRENT-STATE-AUDIT.md` Section 6's counts).

---

## Phase 1.5 — Intelligence UX prototype

**Added on review, 2026-08-13.** Inserted between Phase 1 and Phase 2 for a specific reason: before committing further engineering to a storage migration, validate that the Assessment/Signal/Recommendation semantics Phase 1 just formalized actually work when a real person uses them against real data — and let that real usage tell Phase 2 what the repository interface actually needs to support, rather than guessing.

**Goal**: validate the product's intelligence/synthesis experience against the existing JSON backend, before committing to the storage migration. **Explicitly not** a productionization effort — Phase 4 remains where the intelligence layer is completed and productionized, after the Postgres migration. This phase is a prototype pass whose main output is *findings*, not finished features.

**Scope**:
- Import and review the six existing proposed blueberry Signals (`data/imports/blueberry-public-pilot-2026-08-03/signals/`) using the Phase 1 refined signal schema, against the **current JSON-backed repository** — no Postgres.
- Create at least one real, human-authored Assessment (Phase 1 schema), against real Berries data.
- Create at least one real, human-authored Recommendation (Phase 1 schema), correctly tracing `Recommendation → Assessment/Signal → Facts → Evidence → Source`.
- Prototype a Blueberry/Berries Landscape view — a rollup, not a single-record page.
- Prototype a richer Company intelligence/portfolio view — going beyond what V1's current entity page shows (`CURRENT-STATE-AUDIT.md` Section 8, Workflow B: V1 has no dedicated "portfolio" rollup for a company's varieties/patents/relationships).
- Prototype a richer Variety intelligence view — same idea, for varieties, including a first real attempt at surfacing trait provenance (`CURRENT-STATE-AUDIT.md` Section 5's identified gap: trait-to-variety linkage isn't currently a structured, queryable relationship).
- Document findings, explicitly aimed at feeding Phase 2's repository-interface design: what rollup queries did these prototypes actually need? What Domain Pack configuration (beyond Phase 1's narrowed scope) turned out to be genuinely necessary, not speculative? What data-model gaps appeared once real intelligence was presented to a real user?

**Explicitly out of scope**: PostgreSQL in any form — these prototypes run against the current JSON-backed repository/`load_json_files()` path, deliberately, so this phase tests the *domain model and UX*, not the *storage layer*. Polished, production-quality UI — these are prototypes, allowed to be rough, since their job is to generate findings, not ship.

**Acceptance criteria**:
- All 6 staged Signals are visible in the running app, using real data, under the Phase 1 refined schema.
- At least one Assessment and one Recommendation exist, human-authored, reviewed, and correctly exposing their full lineage chain.
- At least one usable landscape view exists that synthesizes multiple records into a single view (the concrete test of "synthesis, not just listing").
- A written findings document exists and is referenced directly by Phase 2's repository-interface design work — not filed away unread.

---

## Phase 2 — Repository/storage abstraction

**Goal**: introduce a storage-interface boundary in the application code *before* changing what's behind it, so Phase 3's actual cutover is a swap behind an already-tested seam, not a simultaneous "change the interface and the implementation" risk. Informed directly by Phase 1.5's findings on what rollup queries the real prototypes actually needed. **Split into two sub-phases on review (2026-08-14)**: 2A designs the contract from real, observed application query needs; 2B implements it. This split exists because a repository interface designed from planning-doc assumptions rather than the actual Phase 1.5 access patterns risks exactly the "generic CRUD abstraction that doesn't fit the real query shapes" failure mode — 2A's whole job is to prevent that by inventorying real code first.

### Phase 2A — Repository contract & scope semantics

**Status**: Complete (2026-08-14). See `docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md` for the full deliverable.

**Scope**: inventory every real data-access pattern in the current application (23 identified, verified against `app/main.py`, not just Phase 1.5's own findings document); classify each Core vs. Domain-Pack-specific; resolve the Assessment/Recommendation/Signal analytical-scope gap Phase 1.5B's findings surfaced (`08-DECISION-LOG.md` D-012 — explicit, optional, additive `domain_ids`/`market_ids`/`geography_ids` fields, separate from provenance); design the repository/query/domain-service boundary (not implement it); specify the shared backend contract-test suite Phase 2B must satisfy; propose Phase 2B's code organization.

**Explicitly out of scope, and not done**: any repository/query code; any change to `app/main.py`'s structure; PostgreSQL; route migration. The only production-code change in Phase 2A is the three additive, optional JSON Schema fields D-012 specifies (verified via `scripts/validate_records.py` to introduce zero validation regressions against live data).

**Acceptance criteria**: all met — see `docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md`'s own closing cross-check against these criteria.

### Phase 2B — Repository/query implementation

**Status**: Not started. Scoped by Phase 2A's deliverable, not by this section's own (now superseded) description below.

**Scope** (per `docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md` Parts 3 and 7): implement the record-repository / query-service / domain-service layers specified in Phase 2A, in the `app/repositories/`, `app/queries/`, `app/services/berries/` structure Phase 2A proposed; refactor `app/main.py` to call the new layers instead of `load_json_files()`/direct file I/O; implement the repository contract-test suite Phase 2A specified (Part 8) against the JSON backend, then a second, trivial (e.g. in-memory) backend, proving the seam is real; implement the `scope_disagreements()` detection function D-012 specifies but Phase 2A did not build; build the minimal Intelligence Package exporter against the new repository interface (unchanged from this section's original scope — see below).
- **Carried forward from this section's original, pre-split scope**: build a **minimal Intelligence Package exporter** against the repository interface — not the full report/API/export UI (that remains Phase 6), just enough to export the current dataset to the `05-INTELLIGENCE-PACKAGE-SPEC.md` format and validate it can be re-imported without information loss. This exists early for two reasons at once: it's the concrete migration-safety mechanism Phase 3's "freeze and archive" step needs, and it's the earliest possible proof that the long-term downstream-system export contract actually works, not just a paper spec.

**Explicitly out of scope**: PostgreSQL itself (that's Phase 3) — this phase's success is proven by the *same JSON-file backend* working correctly through the new interface. The full report/API/export UI (Phase 6). Fixing the seed/demo-data structural gap (`docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md` Part 6, `09-RISK-REGISTER.md` R-12) — tracked as a Phase 3 gate, not a Phase 2B requirement, though Phase 2B may implement it if convenient.

**Acceptance criteria**:
- All existing tests (205 as of Phase 2A, plus whatever Phase 2B itself adds) pass against the refactored code with zero test-assertion changes (fixture/setup changes are acceptable if they reflect the new interface, but what a test *checks* should not need to change, since behavior hasn't changed).
- No route handler in the application performs direct file I/O anymore — every data access goes through a repository interface, verifiable by code search.
- A second, trivial repository implementation (even an in-memory one, for test speed) can be swapped in without touching route code, proving the seam is real and not just a renamed function call.
- The repository contract-test suite (`docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md` Part 8.2) exists and passes against both backends.
- The minimal Intelligence Package exporter produces a valid package from the live dataset, and that package re-imports without information loss (checkable via `source-lineage.json`'s `orphan_check`, per `05-INTELLIGENCE-PACKAGE-SPEC.md`).

---

## Phase 3 — PostgreSQL parity migration

**Goal**: make PostgreSQL the operational store, with zero data loss (the single most important acceptance bar in this entire roadmap, given the Risk Register's top-ranked risk) — via a **bounded, sequential** migration, not an extended period with two live, simultaneously-written sources of truth. **Revised on review, 2026-08-13** — see D-001's reviewer modification, `08-DECISION-LOG.md`.

**Scope** (the seven-step sequence, replacing the originally-proposed dual-write approach):
1. **Freeze and archive** a complete, validated Intelligence Package from the current JSON-backed system, using the minimal exporter built in Phase 2.
2. **Load** that package into PostgreSQL — a one-time, auditable load, not an ongoing sync.
3. **Implement deterministic JSON → PostgreSQL → canonical JSON round-trip parity checks** — run them, not as a continuously-live background job monitoring two simultaneous writers, but as a repeatable, deterministic verification step against the frozen, loaded dataset.
4. **Run the complete application test suite** (all 122 tests plus whatever Phase 1.5/1/2 added) against the Postgres-backed repository implementation.
5. **Run V2 on a branch/staging environment** using PostgreSQL, for a **bounded acceptance period** — real usage, real verification, explicitly time-boxed rather than open-ended.
6. **Cut V2 over** to PostgreSQL once parity and tests remain clean through that acceptance period.
7. **Preserve the V1 tag and the archived JSON package indefinitely** — not deleted, not merely "kept until confidence is high." They remain the permanent, independently-verifiable record of the pre-migration state, referenced by `PROJECT-STATUS.md`'s "known-good V1 reference" going forward.
- Within this sequence: migrate `Evidence`'s dual review-state concept (`status`/`validated`) to the unified enum, per the exact mapping specified in `06-MIGRATION-MAP.md`, as part of step 2's load.

**Explicitly out of scope**: search replacement (Postgres full-text search lands here as a byproduct of Postgres existing, but tuning/ranking parity with the current app is Phase 3's stretch goal, not a hard gate — the hard gate is data correctness, not search quality). An extended, indefinitely-running dual-write period — explicitly rejected by this revision.

**Acceptance criteria**:
- 100% of the 1,882 live V1 records (entities + evidence + facts + relationships + strategic questions + signals, per `CURRENT-STATE-AUDIT.md` Section 6/11), plus whatever Phase 1.5 added (Signals, Assessment, Recommendation), exist in Postgres with zero data loss, verified by an automated count-and-content check, not a spot check.
- The deterministic round-trip parity check (step 3) reports zero discrepancies against the frozen archive.
- Every existing test passes against the Postgres-backed repository (step 4).
- The staging acceptance period (step 5) runs clean for its full defined duration before cutover — any discrepancy found during it resets the clock, it does not get waived.
- The V1 git tag and the archived Intelligence Package both still exist and are documented as permanent, post-cutover (step 7) — this is a standing acceptance criterion, not a one-time check.

---

## Phase 4 — Intelligence/synthesis layer (productionization)

**Goal**: close `CURRENT-STATE-AUDIT.md`'s highest-ranked gap for real — **productionize and complete**, on PostgreSQL, what Phase 1.5 already proved out as prototypes against JSON. This phase is not "build Assessment/Recommendation/landscape views for the first time" — that already happened in Phase 1.5, deliberately early, specifically so this phase builds on validated findings instead of guesses.

**Scope**:
- Rebuild the Assessment and Recommendation create/review/approve UI properly on the Postgres-backed repository, informed directly by Phase 1.5's findings document (not re-designed from scratch).
- **Revised on review (D-011, `08-DECISION-LOG.md`)**: BL-052 is a **bounded review task**, not a mechanical migration — examine the 124 curated `evidence.priority`-tagged records and create a Recommendation *only* where an actual, action-oriented recommendation is genuinely supported by the accumulated intelligence (an Assessment or Signal exists or can be written to justify it). `evidence.priority` itself is not touched, retired, or converted — it remains a permanent, distinct triage signal (D-011).
- Productionize the landscape/company/variety views Phase 1.5 prototyped, addressing whatever data-model or UX gaps that phase's findings document surfaced.
- Ensure the 6 Signals, and the Assessment/Recommendation examples created in Phase 1.5, survive the Phase 3 migration intact and are the seed content this phase builds on (not re-created).

**Explicitly out of scope**: AI-generated Assessments/Recommendations (that's Phase 5) — this phase completes the *human-authored* path first, so Phase 5's AI proposals have a solid, already-productionized target to write into. Prototyping from scratch — that was Phase 1.5's job; re-doing it here would mean Phase 1.5 didn't do its job.

**Acceptance criteria**:
- The Assessment/Recommendation UI is fully productionized on Postgres, handling more than the single hand-authored example each from Phase 1.5.
- BL-052's bounded review is complete and documented: how many of the 124 priority-tagged records were reviewed, how many genuinely warranted a Recommendation, and why the rest didn't — not a raw conversion count.
- The landscape/company/variety views are productionized, demonstrably addressing the specific gaps Phase 1.5's findings document identified.
- Everything Phase 1.5 created (6 Signals, the prototype Assessment(s)/Recommendation(s)) is present and correct in the Postgres-backed system, unchanged in substance.

---

## Phase 5 — AI and collector framework

**Goal**: build the provider-neutral AI abstraction and the pluggable Collector interface (`02-TARGET-ARCHITECTURE.md` Sections 7-8), with the human-approval gate (Core Design Principle #4) enforced structurally, not by convention.

**Scope**:
- Implement the AI provider interface and at least one real provider integration behind it.
- Implement `AI Job` as a stored, auditable object (Phase 1 schema) — every AI-proposed Fact/Claim/Relationship/Assessment/Recommendation/Signal is tagged `ai_proposed: true` and enters the existing review queue exactly like human-submitted content, never auto-publishing.
- Re-home the existing RSS and keyword-search collection *behaviors* behind the new `Collector` interface (a re-homing of proven V1 logic, per `06-MIGRATION-MAP.md`, not new collection logic).
- Implement `Collection Job` as a stored, auditable object, replacing the current fire-and-forget `check_source()` background task.
- Generalize `resolve_real_summaries.py`'s crash-recovery/circuit-breaker discipline into the shared job-framework error handling (`02-TARGET-ARCHITECTURE.md` Section 6).

**Explicitly out of scope**: a Collector plugin marketplace, custom per-Domain-Pack collector code (both `LATER`, `02-TARGET-ARCHITECTURE.md` Section 7).

**Acceptance criteria**:
- At least one AI-proposed Fact and one AI-proposed Assessment exist in the review queue, correctly flagged, and can be approved or rejected by a human reviewer through the UI — proving the propose/approve loop, not just the API call to a provider.
- RSS and keyword-search collection continue to work with identical output to the V1 behavior they replace, verified against a fixed set of known sources.
- Every Collection Job and AI Job run is visible, auditable, and correctly records cost/timing/outcome.
- AI provider swap (configuring a second provider) requires zero application code changes — a config-only change, proving the abstraction is real.

---

## Phase 6 — Reports, exports, and API

**Goal**: build the customer-facing output layer — the clean API, the Report generation mechanism, and the Intelligence Package export/import path — that lets downstream systems and human consumers get value out of everything Phases 1-5 built.

**Scope**:
- Implement the versioned read API (`02-TARGET-ARCHITECTURE.md` Section 2) covering every core object type.
- Implement Report generation from the Berries Domain Pack's report templates (`04-DOMAIN-PACK-SPEC.md` Section 6), each report's content traceable through its lineage per Core Design Principle #3.
- Implement full Intelligence Package export (JSON/JSONL/CSV, `05-INTELLIGENCE-PACKAGE-SPEC.md`) and the symmetric import path, generalizing `import_package.py`'s three-gate discipline.
- Implement minimal authentication (`02-TARGET-ARCHITECTURE.md` Section 11) — enough to know who's making API calls and who's approving reviewable content, not a full permissions system. **Hard rule, not phase-conditional**: no writable Intelligence OS instance may be exposed to the public internet without authentication in front of it. If V2 stays local/private through Phases 1-4, this doesn't block that work — it becomes non-negotiable the moment any writable instance is reachable from the public internet, regardless of phase.

**Explicitly out of scope**: write-API endpoints beyond what review/approval already needs; GraphQL/webhooks/streaming (all `LATER`).

**Acceptance criteria**:
- A full Intelligence Package export of the entire current dataset round-trips: export it, import it into a fresh Workspace, and the result is content-identical to the source (the `orphan_check` in `source-lineage.json` is empty both directions).
- At least one Report template generates a real, correct, fully-lineage-traceable report against live data.
- The API serves every core object type with working filtering, and requires authentication for anything beyond published, read-only content.
- A documented, working example exists of an external client (even a simple script) consuming the API or an exported package — the actual test of "downstream systems can consume this" (Core Design Principle #11).

---

## Phase 7 — Second-domain / second-berry validation

**Goal**: the real test of whether the Domain Pack boundary (`04-DOMAIN-PACK-SPEC.md`) was drawn correctly — prove it with a second Domain Pack, not just an unexercised specification.

**Scope**:
- Build a second Domain Pack. **Two candidates, both legitimate**: a second berry (raspberry/strawberry/blackberry — the multi-berry foundation `PRD.md` always specified, "V1 begins operationally with blueberry while preserving a multi-berry foundation") or a genuinely unrelated industry (proving generality beyond "another fruit," per this planning pass's own second-domain checks in `04-DOMAIN-PACK-SPEC.md`). Recommend attempting the **unrelated-industry case** if only one is resourced, since it's the harder and more informative test — a second berry could pass by accident even with an imperfect Core/Domain-specific boundary, since berries share so much structure with each other.
- Populate the new Domain Pack with a small but real dataset (order of magnitude: tens of entities, not thousands — enough to prove the mechanism, not a full research pass).
- Run the same collection → review → structure → publish → assess → report → export lifecycle against it, with zero core application code changes required.

**Explicitly out of scope**: production-scale data volume for the second domain — this phase proves the *mechanism*, not a fully-populated second product.

**Acceptance criteria**:
- The second Domain Pack is built and activated using only the declarative contribution surfaces in `04-DOMAIN-PACK-SPEC.md` — any point where core code needed to change to support it is a finding against the spec, to be fixed before calling this phase complete, not shipped as a known gap.
- At least one full lifecycle pass (collect → structure → review → publish → report → export) succeeds for the second domain.
- The Berries Domain Pack continues to work unaffected throughout — proving multi-domain coexistence in one deployment, not just sequential replacement.

---

## Phase 8 — SaaS-readiness work, if still justified

**Goal**: explicitly a decision gate, not a default next step. Only scoped in detail if, by the time Phases 1-7 are complete, there is a concrete reason (a second real operator, a paying customer, a specific hosting requirement) to build it.

**Scope (if justified)**:
- Real multi-tenant isolation (row-level security or equivalent) across Organizations/Workspaces.
- Full authentication (SSO/OAuth), per-object permissions, org-level billing/seat management.
- Deployment automation appropriate to multiple concurrent tenants.

**Explicitly out of scope unless justified**: everything above. This phase is intentionally underspecified in this document — writing a detailed plan for infrastructure that may never be needed would itself violate the instruction not to add infrastructure merely because it is fashionable.

**Acceptance criteria**: not defined here. The first acceptance criterion for Phase 8 is the justification decision itself — a named reason, a named requester, and a scoped set of requirements, written *at that time* against real needs, not spun up speculatively now.
