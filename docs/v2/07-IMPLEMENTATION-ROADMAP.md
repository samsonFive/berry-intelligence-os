# Intelligence OS — Implementation Roadmap (V2)

**Status:** Planning draft, not accepted. No implementation begins until this document (and the rest of the `docs/v2/` set) is reviewed and accepted.

## How phases work

Each phase has a stated goal, a bounded scope (what's in, explicitly what's out), and acceptance criteria specific enough to check off, not "done when it feels done." Phases are sequential in dependency, not necessarily in calendar time — a phase can start being scoped/designed before the prior one's implementation fully lands, but its *work* depends on the prior phase's acceptance criteria being met. Detailed work items for each phase are broken out in `10-BACKLOG.md`; this document stays at phase-goal granularity.

---

## Phase 0 — Freeze / reference baseline

**Goal**: guarantee the current, working Berry Intelligence OS remains recoverable and usable throughout everything that follows (Core Design Principle #10).

**Scope**:
- Tag the current commit (`b7013a1` plus this planning pass's own doc commits) as the V1 reference baseline (e.g. `v1-baseline`).
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
- Write the new/extended JSON schemas: `assessment.schema.json`, `recommendation.schema.json` (new); extend `evidence.schema.json` (unified review-state, `source_tier`, `event_date`), `relationship.schema.json` (`confidence`), `signal.schema.json` (richer status enum, enforced `minItems: 2`), `strategic-question.schema.json` (tightened status enum).
- Write `domain-pack.schema.json` (validates the manifest shape from `04-DOMAIN-PACK-SPEC.md`).
- Build the Berries Domain Pack itself as the first real artifact against that schema — this is where V1's hard-coded entity types, relationship predicates, and constants (`BERRIES`, `SOURCE_ENTITY_TYPES`, `PRIORITY_DIMENSIONS`) get extracted into declarative Domain Pack content.
- Resolve the two open domain-model decisions this plan explicitly flagged rather than silently defaulted: Claim-as-Fact-subtype vs. separate schema (D-010), and whether `evidence.priority` is retired or coexists with `Recommendation` (D-011) — see `08-DECISION-LOG.md`.

**Explicitly out of scope**: any database work, any change to the live running application, any AI/collector code.

**Acceptance criteria**:
- Every new/extended schema validates against `scripts/validate_records.py`'s existing validator with zero code changes to the validator itself beyond adding the new schema files.
- The full V1 dataset (162 entities, 1,263 evidence, etc.) validates cleanly against the *extended* schemas with all new fields optional (no existing record becomes invalid) — a direct, checkable parity test.
- The Berries Domain Pack manifest validates against `domain-pack.schema.json` and contains every entity type, predicate, and taxonomy value currently in live use (verifiable by diffing against `CURRENT-STATE-AUDIT.md` Section 6's counts).
- D-010 and D-011 have recorded decisions (not necessarily "build the maximal version" — a decision to keep V1's simpler shape is an acceptable outcome, as long as it's deliberate).

---

## Phase 2 — Repository/storage abstraction

**Goal**: introduce a storage-interface boundary in the application code *before* changing what's behind it, so Phase 3's actual cutover is a swap behind an already-tested seam, not a simultaneous "change the interface and the implementation" risk.

**Scope**:
- Define a repository interface per core object type (`EntityRepository`, `EvidenceRepository`, etc.) with the operations the app actually needs (list/filter/get/create/update) — modeled on, but not identical to, `load_json_files()`'s existing call sites, which is itself unchanged as the interface's first, only implementation.
- Refactor `app/main.py` (or its post-split successors, if that reorganization from `06-MIGRATION-MAP.md` happens here rather than later — a sequencing choice for whoever scopes Phase 2 in detail) to call the interface, not `load_json_files()`/direct file I/O, directly.
- No behavior change is permitted in this phase — it is a refactor, verified by the existing test suite passing unmodified in assertion.

**Explicitly out of scope**: PostgreSQL itself (that's Phase 3) — this phase's success is proven by the *same JSON-file backend* working correctly through the new interface.

**Acceptance criteria**:
- All 122 existing tests pass against the refactored code with zero test-assertion changes (fixture/setup changes are acceptable if they reflect the new interface, but what a test *checks* should not need to change, since behavior hasn't changed).
- No route handler in the application performs direct file I/O anymore — every data access goes through a repository interface, verifiable by code search.
- A second, trivial repository implementation (even an in-memory one, for test speed) can be swapped in without touching route code, proving the seam is real and not just a renamed function call.

---

## Phase 3 — PostgreSQL parity migration

**Goal**: make PostgreSQL the operational store, with a verified, automated parity guarantee against the JSON-file source of truth throughout the transition, and zero data loss (the single most important acceptance bar in this entire roadmap, given the Risk Register's top-ranked risk).

**Scope**:
- Stand up the Postgres schema, generated from the Phase 1 JSON schemas (every field, every enum, every required/optional distinction preserved).
- Implement a Postgres-backed repository (Phase 2's interface, second implementation) and a one-time, auditable load of the full V1 dataset into it.
- Run a **dual-write period**: the application writes to both JSON files and Postgres; an automated parity job continuously exports every Postgres row and diffs it against the corresponding JSON file, byte-for-byte on the fields both sides know about.
- Migrate `Evidence`'s dual review-state concept (`status`/`validated`) to the unified enum, per the exact mapping specified in `06-MIGRATION-MAP.md`.
- Cut the application over to reading from Postgres only once the parity job has run clean for a defined, deliberately conservative window; JSON-file *writing* stops at that point, but the files themselves are archived, not deleted (they remain a permanent, replayable Intelligence Package — `05-INTELLIGENCE-PACKAGE-SPEC.md` — of the exact pre-migration state).

**Explicitly out of scope**: search replacement (Postgres full-text search lands here as a byproduct of Postgres existing, but tuning/ranking parity with the current app is Phase 3's stretch goal, not a hard gate — the hard gate is data correctness, not search quality).

**Acceptance criteria**:
- 100% of the 1,882 live V1 records (entities + evidence + facts + relationships + strategic questions + signals, per `CURRENT-STATE-AUDIT.md` Section 6/11) exist in Postgres with zero data loss, verified by an automated count-and-content check, not a spot check.
- The parity job reports zero discrepancies across a defined observation window before cutover.
- Every one of the 122 existing tests passes against the Postgres-backed repository.
- A full-fidelity Intelligence Package export of the pre-migration JSON state exists and is archived before JSON-file writing is disabled.
- The application remains usable (readable and writable) throughout — no scheduled downtime window is required by this migration's design.

---

## Phase 4 — Intelligence/synthesis layer

**Goal**: close `CURRENT-STATE-AUDIT.md`'s highest-ranked gap — build the Assessment and Recommendation objects and the rollup/landscape views that make the platform answer "why" and "what should I pay attention to," not just list records.

**Scope**:
- Implement `Assessment` and `Recommendation` as real, reviewable objects (Phase 1 schemas), with UI to create, review, and approve them (extending the existing review-queue pattern this session already built for Evidence).
- Migrate the 124 manually-curated evidence records' existing `priority` values into the first real `Recommendation` records, per whatever D-011 decided in Phase 1.
- Import the 6 unapplied blueberry Signals as the first real `Signal` rows under the refined schema — a concrete, immediately-available validation case for this phase's work, not hypothetical data.
- Build at least one real `Intelligence Product`/landscape view (a "Berries Landscape" grouped by geography, per the Berries Domain Pack's report template) proving the rollup concept works end-to-end, from raw evidence through to a synthesized view a product leader can actually use — the specific capability `VISION.md`'s north-star promised and V1 never delivered.

**Explicitly out of scope**: AI-generated Assessments/Recommendations (that's Phase 5) — this phase proves the *objects and views* work with human-authored content first, so Phase 5's AI proposals have a solid, already-validated target to write into.

**Acceptance criteria**:
- At least one real Assessment and one real Recommendation exist, fully reviewed/published, each correctly exposing its lineage chain back to Evidence.
- All 6 blueberry Signals are imported and visible in the app (closing a gap open since 2026-08-04).
- The "Berries Landscape" view (or equivalent) is reachable in the running app and demonstrably shows information not visible on any single existing entity/evidence page — the actual test of whether synthesis, not just listing, was achieved.

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
- Implement minimal authentication (`02-TARGET-ARCHITECTURE.md` Section 11) — enough to know who's making API calls and who's approving reviewable content, not a full permissions system.

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
