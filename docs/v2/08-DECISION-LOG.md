# Intelligence OS — Decision Log (V2)

**Status:** Every decision below is `PROPOSED`. None are `ACCEPTED`. This log exists so decisions are visible and debatable before implementation begins, not to record decisions already made — matching the task's explicit instruction: "Mark these PROPOSED, not accepted."

Format follows the same shape as V1's existing ADRs (`docs/decisions/ADR-000{1-4}`) — Status / Decision / Rationale / Consequences — with an added **Alternatives considered** section, since these are being proposed for the first time rather than recorded after the fact.

---

## D-001 — PostgreSQL as V2's operational store

**Status**: PROPOSED

**Decision**: V2 uses PostgreSQL as the operational database behind the live application, replacing flat JSON files as the read/write path.

**Rationale**: `CURRENT-STATE-AUDIT.md` identified concrete, already-manifesting limits of flat-file storage at V1's modest scale — no referential-integrity checking, no concurrent-writer story, full-folder scans for every list/filter operation. Postgres is a mature, boring, well-understood answer to exactly those three problems. See `02-TARGET-ARCHITECTURE.md` Section 3 for the full rationale.

**Alternatives considered**: staying on flat files indefinitely (rejected — doesn't solve the observed problems); a document database (rejected — this domain model is genuinely relational, with foreign-key-like references everywhere; a document store would just reimplement joins badly); a graph database (rejected — `PRD.md`'s own V1 scope explicitly deferred this, and nothing in the current data volume or query pattern justifies it now).

**Consequences**: requires the Phase 3 parity-migration work (`07-IMPLEMENTATION-ROADMAP.md`); introduces an operational dependency (a running Postgres instance) V1 never had; portability must be actively maintained (D-002) so this doesn't become vendor lock-in in practice.

---

## D-002 — JSON remains the interchange/export contract

**Status**: PROPOSED

**Decision**: regardless of D-001, every core object's canonical shape remains the JSON Schema-defined shape, and every Postgres row must round-trip losslessly to that JSON shape. JSON is not replaced as the interchange format even though it's replaced as the operational store.

**Rationale**: Core Design Principle #8 ("JSON remains a first-class interchange/export format") and #9's portability requirement. This is also what makes `05-INTELLIGENCE-PACKAGE-SPEC.md` possible at all — an export format that's a lossy approximation of the database would undermine archival, migration, and downstream-agent use cases.

**Alternatives considered**: a Postgres-native export format (rejected — ties every consumer to Postgres-specific tooling, violating portability); Protocol Buffers/Avro for interchange (rejected — no concrete consumer need justifies the added complexity over plain JSON, and JSON's human-readability was itself a stated V1 principle worth keeping, ADR-0001).

**Consequences**: every schema change must be made compatibly (additive, versioned) so old exports remain importable; the Postgres schema must be generated from (or kept in lockstep with) the JSON schemas, not designed independently.

---

## D-003 — FastAPI retained as the web/API framework

**Status**: PROPOSED

**Decision**: V2 continues to use FastAPI for both the web application and the new API layer.

**Rationale**: nothing in `CURRENT-STATE-AUDIT.md` identifies FastAPI itself as a limitation — the identified problems (monolithic `app/main.py`, no API design) are organizational, not framework-level. FastAPI's native OpenAPI generation is a direct asset for the new API layer (`02-TARGET-ARCHITECTURE.md` Section 2).

**Alternatives considered**: a framework switch (Django, Flask, a Node-based stack) — rejected outright; no problem identified in the audit points at the framework, and a framework switch would be exactly the kind of "add complexity because it's fashionable" the task explicitly warns against.

**Consequences**: none beyond the organizational refactor (`app/main.py` splitting) already planned independent of this decision.

---

## D-004 — Server-rendered frontend retained, initially

**Status**: PROPOSED

**Decision**: V2 continues with server-rendered Jinja2 templates, no client-side framework, at least through Phase 6 of the roadmap.

**Rationale**: `CURRENT-STATE-AUDIT.md` Section 9 rates the current template/CSS system as consistent and functional; the actual V1 gaps are missing *views* (rollups, dashboards), not a broken rendering approach. See `02-TARGET-ARCHITECTURE.md` Section 1.

**Alternatives considered**: adopting a client-side framework now, ahead of any concrete need — rejected as premature; nothing in the current or near-term roadmap requires client-side interactivity a server-rendered page can't provide.

**Consequences**: revisit if Phase 4's synthesis/landscape views turn out to need genuinely interactive, client-heavy UI (e.g., an interactive comparison matrix) that server rendering can't reasonably deliver — flagged as a possible future decision point, not decided now.

---

## D-005 — Provider-neutral AI abstraction

**Status**: PROPOSED

**Decision**: all AI/LLM usage goes through a provider-neutral interface (`02-TARGET-ARCHITECTURE.md` Section 8); no application code calls a specific vendor's SDK directly.

**Rationale**: Core Design Principle #5, explicit in the product direction. Also a direct mitigation for the provider-lock-in risk (`09-RISK-REGISTER.md`).

**Alternatives considered**: integrating directly against one provider first "to move faster," abstracting later — rejected; retrofitting an abstraction after direct integration is real, recurring pain, and the interface itself (Section 8) is not large enough to justify skipping it even for a first pass.

**Consequences**: every AI feature (structuring proposals, assessments, report drafting) is built against the interface from day one, which may mean slightly more upfront design work per feature in exchange for zero lock-in risk later.

---

## D-006 — Collector abstraction

**Status**: PROPOSED

**Decision**: source collection (RSS, keyword search, and future collection methods) goes through a pluggable `Collector` interface; the app never hard-codes a specific collection method's logic into core route/business-logic code again.

**Rationale**: `02-TARGET-ARCHITECTURE.md` Section 7; Core Design Principle #6 ("Collectors must be modular"). Directly motivated by `CURRENT-STATE-AUDIT.md`'s finding that V1's two collection behaviors are hard-coded inside `check_source()`, making a third collection method require core code changes.

**Alternatives considered**: keeping collection logic inline and just organizing it better (rejected — doesn't solve the actual problem, which is architectural coupling, not code tidiness); a full plugin-marketplace/sandboxed-execution model (rejected as premature — `LATER`, `02-TARGET-ARCHITECTURE.md` Section 7).

**Consequences**: RSS and keyword-search collection must be re-implemented behind the new interface (a re-homing of proven logic, not new logic — `06-MIGRATION-MAP.md`), a real but bounded migration cost.

---

## D-007 — Domain Packs as the mechanism for domain-specific concepts

**Status**: PROPOSED

**Decision**: entity types, relationship predicates, taxonomies, strategic-question templates, collector templates, report templates, filters, and visualization configuration are all Domain Pack-contributed, declarative artifacts (`04-DOMAIN-PACK-SPEC.md`) — not hard-coded into core application code, and not executable plugin code in V2 (see that document's "Why declarative, not executable" section).

**Rationale**: Core Design Principle #7, and the entire premise of "Berry Intelligence becomes the first Domain Pack... not the architectural identity of the platform" (product direction).

**Alternatives considered**: a code-plugin model (rejected for V2 as unjustified complexity/security-surface given nothing in current scope needs custom Domain Pack *logic*, only configuration — flagged as a possible `LATER` extension); keeping domain concepts hard-coded and just parameterizing them more (rejected — doesn't achieve the actual goal of a second Domain Pack requiring zero core code changes, which Phase 7 explicitly tests for).

**Consequences**: V1's hard-coded constants (`BERRIES`, `SOURCE_ENTITY_TYPES`, the 10-value relationship predicate enum, `PRIORITY_DIMENSIONS`) must all be extracted into the Berries Domain Pack (Phase 1) before Phase 7 can validate the boundary was drawn correctly.

---

## D-008 — Organization / Workspace / Domain scoping present from the start, not deferred

**Status**: PROPOSED

**Decision**: the `Organization → Workspace → Domain` hierarchy (`03-DOMAIN-MODEL.md`) exists as real schema/database structure from Phase 3 onward, even though V2 itself runs as a single Organization with a single Workspace. Real multi-tenant *isolation* (row-level security, per-tenant access control) is explicitly deferred to Phase 8.

**Rationale**: retrofitting a tenancy boundary into a schema that was never designed with one is expensive and risky once real data depends on the old shape; adding the *structure* now, without the *enforcement* machinery, costs little and prevents that future rewrite.

**Alternatives considered**: deferring the schema entirely until multi-tenancy is actually needed (rejected — this is precisely the kind of decision that's cheap now and expensive later, distinct from "add infrastructure because it's fashionable," since it's schema shape, not running infrastructure); building full multi-tenant isolation now (rejected — explicitly premature per the task's own instruction and Core Design Principle against over-generalization, `09-RISK-REGISTER.md`).

**Consequences**: every core object carries a `workspace_id` from Phase 3 onward, a small but permanent addition to every table/schema.

---

## D-009 — No big-bang rewrite; every replacement has a migration bridge

**Status**: PROPOSED

**Decision**: no component in `06-MIGRATION-MAP.md` marked `REPLACE` is cut over without a verified coexistence/bridge period first (dual-write for storage, side-by-side operation for search, re-homing proven logic for collectors and imports). The V1 application remains usable throughout (Core Design Principle #10).

**Rationale**: explicit task instruction ("No big-bang rewrite is allowed"); also the only responsible way to satisfy "the existing blueberry dataset must be preserved" against the top-ranked risk in `09-RISK-REGISTER.md` (migration data loss).

**Alternatives considered**: a scheduled cutover/migration window (rejected — unnecessary given the dataset's modest size makes a parity-verified dual-write period entirely practical, and it removes an entire category of risk for comparatively little extra engineering effort).

**Consequences**: Phase 3 in particular takes longer than a naive "just point the app at Postgres" cutover would — a deliberate, accepted tradeoff.

---

## D-010 — Claim: separate schema, or remain a Fact subtype?

**Status**: PROPOSED — genuinely unresolved, needs owner input (see `03-DOMAIN-MODEL.md`, Claim section)

**Decision**: not made in this planning pass. Two live options: **(a)** keep V1's approach — Claim is `fact.classification == "claim"`, sharing every field with Fact; or **(b)** split Claim into its own schema if a concrete future need (different required fields, a distinct verification workflow that promotes a Claim into a Fact) makes them diverge.

**Rationale for flagging rather than deciding**: V1's current approach is simple, already validated at scale (132 fact / 54 claim records), and the classification enum is the entire mechanism making the FACT/CLAIM distinction real. There's no evidence yet that (b) is needed — but the two options have different migration costs later, so it's worth a deliberate owner decision now rather than defaulting silently.

**Consequences of leaving unresolved**: Phase 1's schema work must pick one to proceed (this document recommends defaulting to (a), the lower-cost/already-proven option, unless the decision owner has a specific reason to choose (b) before Phase 1 begins).

---

## D-011 — Does `Recommendation` replace `evidence.priority`, or coexist with it?

**Status**: PROPOSED — genuinely unresolved, needs owner input (see `03-DOMAIN-MODEL.md`, Recommendation section)

**Decision**: not made in this planning pass. This document's default assumption for Phase 4 planning purposes is **coexistence during migration** — `Recommendation` is additive, `evidence.priority` isn't removed until `Recommendation` is proven out (Phase 4's acceptance criteria) — but this is a starting assumption, not a final decision.

**Rationale for flagging rather than deciding**: `evidence.priority`'s four dimensions (reading/testing/commercial_position/monitoring) are a real, working, if limited, recommendation mechanism today, used by 124 live records and rendered throughout the current UI (priority queues, evidence cards). Retiring it outright before `Recommendation` is proven risks a regression; keeping both forever risks exactly the two-competing-vocabularies confusion `CURRENT-STATE-AUDIT.md` found between `status` and `validated`.

**Consequences of leaving unresolved**: Phase 4 proceeds on the coexistence assumption; a decision to formally retire `evidence.priority` (or to keep it permanently as a lighter-weight triage signal distinct from the heavier Assessment/Signal-anchored `Recommendation`) should be made once Phase 4's acceptance criteria are met and there's real usage data to decide from.
