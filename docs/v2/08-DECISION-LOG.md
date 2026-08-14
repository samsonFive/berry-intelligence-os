# Intelligence OS — Decision Log (V2)

**Status:** Reviewed 2026-08-13. D-002 through D-009 are `ACCEPTED`. D-001 is `ACCEPTED` subject to the revised migration strategy recorded below. D-010 and D-011 are `ACCEPTED` (resolved this review). D-012 is `ACCEPTED` (2026-08-14, Phase 2A). No decision below authorizes starting implementation on its own — see `PROJECT-STATUS.md` and `07-IMPLEMENTATION-ROADMAP.md` Phase 0 for what's actually next.

Format follows the same shape as V1's existing ADRs (`docs/decisions/ADR-000{1-4}`) — Status / Decision / Rationale / Consequences — with an added **Alternatives considered** section, since these were proposed for the first time rather than recorded after the fact.

---

## D-001 — PostgreSQL as V2's operational store

**Status**: ACCEPTED (2026-08-13), subject to the revised migration strategy in this decision and in `02-TARGET-ARCHITECTURE.md`/`07-IMPLEMENTATION-ROADMAP.md` Phase 3

**Decision**: V2 uses PostgreSQL as the operational database behind the live application, replacing flat JSON files as the read/write path.

**Rationale**: `CURRENT-STATE-AUDIT.md` identified concrete, already-manifesting limits of flat-file storage at V1's modest scale — no referential-integrity checking, no concurrent-writer story, full-folder scans for every list/filter operation. Postgres is a mature, boring, well-understood answer to exactly those three problems. See `02-TARGET-ARCHITECTURE.md` Section 3 for the full rationale.

**Alternatives considered**: staying on flat files indefinitely (rejected — doesn't solve the observed problems); a document database (rejected — this domain model is genuinely relational, with foreign-key-like references everywhere; a document store would just reimplement joins badly); a graph database (rejected — `PRD.md`'s own V1 scope explicitly deferred this, and nothing in the current data volume or query pattern justifies it now).

**Reviewer modification (2026-08-13)**: the migration *strategy* originally proposed alongside this decision — an extended, continuously-running dual-write period — is **rejected in favor of a simpler, bounded approach**: freeze and archive a validated Intelligence Package from V1, load it into Postgres once, run deterministic parity checks and the full test suite against the Postgres repository, run V2 on Postgres in a staging/branch environment for a bounded acceptance period, then cut over. **No extended period with two simultaneous operational sources of truth.** The repository abstraction from Phase 2 remains mandatory — it's what makes this bounded approach possible at all, by letting the same application code run against either backend without knowing which one it's talking to. See `07-IMPLEMENTATION-ROADMAP.md` Phase 3 (revised) for the full seven-step sequence, and `06-MIGRATION-MAP.md` for the updated JSON-storage entry.

**Consequences**: requires the (now-simplified) Phase 3 migration work; introduces an operational dependency (a running Postgres instance) V1 never had; portability must be actively maintained (D-002) so this doesn't become vendor lock-in in practice. The simplified strategy trades "zero simultaneous-source-of-truth risk for an extended period" for "a bounded acceptance window where correctness must be established before cutover, not gradually proven while both stores stay live indefinitely" — a deliberate tradeoff, not a reduction in rigor (see R-01/R-11, `09-RISK-REGISTER.md`, revised).

---

## D-002 — JSON remains the interchange/export contract

**Status**: ACCEPTED (2026-08-13)

**Decision**: regardless of D-001, every core object's canonical shape remains the JSON Schema-defined shape, and every Postgres row must round-trip losslessly to that JSON shape. JSON is not replaced as the interchange format even though it's replaced as the operational store.

**Rationale**: Core Design Principle #8 ("JSON remains a first-class interchange/export format") and #9's portability requirement. This is also what makes `05-INTELLIGENCE-PACKAGE-SPEC.md` possible at all — an export format that's a lossy approximation of the database would undermine archival, migration, and downstream-agent use cases.

**Alternatives considered**: a Postgres-native export format (rejected — ties every consumer to Postgres-specific tooling, violating portability); Protocol Buffers/Avro for interchange (rejected — no concrete consumer need justifies the added complexity over plain JSON, and JSON's human-readability was itself a stated V1 principle worth keeping, ADR-0001).

**Consequences**: every schema change must be made compatibly (additive, versioned) so old exports remain importable; the Postgres schema must be generated from (or kept in lockstep with) the JSON schemas, not designed independently. **This decision is now load-bearing for the revised D-001 migration strategy** — the JSON↔Postgres round-trip parity check (Phase 3) and the early minimal Intelligence Package exporter (Phase 2, new — see below) both depend on this contract being real, not aspirational.

---

## D-003 — FastAPI retained as the web/API framework

**Status**: ACCEPTED (2026-08-13)

**Decision**: V2 continues to use FastAPI for both the web application and the new API layer.

**Rationale**: nothing in `CURRENT-STATE-AUDIT.md` identifies FastAPI itself as a limitation — the identified problems (monolithic `app/main.py`, no API design) are organizational, not framework-level. FastAPI's native OpenAPI generation is a direct asset for the new API layer (`02-TARGET-ARCHITECTURE.md` Section 2).

**Alternatives considered**: a framework switch (Django, Flask, a Node-based stack) — rejected outright; no problem identified in the audit points at the framework, and a framework switch would be exactly the kind of "add complexity because it's fashionable" the task explicitly warns against.

**Consequences**: none beyond the organizational refactor (`app/main.py` splitting) already planned independent of this decision.

---

## D-004 — Server-rendered frontend retained, initially

**Status**: ACCEPTED (2026-08-13)

**Decision**: V2 continues with server-rendered Jinja2 templates, no client-side framework, at least through Phase 6 of the roadmap.

**Rationale**: `CURRENT-STATE-AUDIT.md` Section 9 rates the current template/CSS system as consistent and functional; the actual V1 gaps are missing *views* (rollups, dashboards), not a broken rendering approach. See `02-TARGET-ARCHITECTURE.md` Section 1.

**Alternatives considered**: adopting a client-side framework now, ahead of any concrete need — rejected as premature; nothing in the current or near-term roadmap requires client-side interactivity a server-rendered page can't provide.

**Consequences**: the new Phase 1.5 (Intelligence UX Prototype, inserted this review — see `07-IMPLEMENTATION-ROADMAP.md`) is the concrete, early test of this decision: if the landscape/company/variety prototype views turn out to need genuinely interactive, client-heavy UI that server rendering can't reasonably deliver, that's a finding Phase 1.5 surfaces *before* Phase 2/3 commit further engineering on top of the server-rendered assumption — not a late discovery.

---

## D-005 — Provider-neutral AI abstraction

**Status**: ACCEPTED (2026-08-13)

**Decision**: all AI/LLM usage goes through a provider-neutral interface (`02-TARGET-ARCHITECTURE.md` Section 8); no application code calls a specific vendor's SDK directly.

**Rationale**: Core Design Principle #5, explicit in the product direction. Also a direct mitigation for the provider-lock-in risk (`09-RISK-REGISTER.md`).

**Alternatives considered**: integrating directly against one provider first "to move faster," abstracting later — rejected; retrofitting an abstraction after direct integration is real, recurring pain, and the interface itself (Section 8) is not large enough to justify skipping it even for a first pass.

**Consequences**: every AI feature (structuring proposals, assessments, report drafting) is built against the interface from day one, which may mean slightly more upfront design work per feature in exchange for zero lock-in risk later. Phase 1.5's human-authored Assessment/Recommendation prototypes deliberately precede any AI-assisted version of the same objects (Phase 5), so this abstraction is designed against real, already-proven object semantics rather than guessed ones.

---

## D-006 — Collector abstraction

**Status**: ACCEPTED (2026-08-13)

**Decision**: source collection (RSS, keyword search, and future collection methods) goes through a pluggable `Collector` interface; the app never hard-codes a specific collection method's logic into core route/business-logic code again.

**Rationale**: `02-TARGET-ARCHITECTURE.md` Section 7; Core Design Principle #6 ("Collectors must be modular"). Directly motivated by `CURRENT-STATE-AUDIT.md`'s finding that V1's two collection behaviors are hard-coded inside `check_source()`, making a third collection method require core code changes.

**Alternatives considered**: keeping collection logic inline and just organizing it better (rejected — doesn't solve the actual problem, which is architectural coupling, not code tidiness); a full plugin-marketplace/sandboxed-execution model (rejected as premature — `LATER`, `02-TARGET-ARCHITECTURE.md` Section 7).

**Consequences**: RSS and keyword-search collection must be re-implemented behind the new interface (a re-homing of proven logic, not new logic — `06-MIGRATION-MAP.md`), a real but bounded migration cost.

---

## D-007 — Domain Packs as the mechanism for domain-specific concepts

**Status**: ACCEPTED (2026-08-13), scope for Phase 1 narrowed — see Consequences

**Decision**: entity types, relationship predicates, taxonomies, strategic-question templates, collector templates, report templates, filters, and visualization configuration are all Domain Pack-contributed, declarative artifacts (`04-DOMAIN-PACK-SPEC.md`) — not hard-coded into core application code, and not executable plugin code in V2 (see that document's "Why declarative, not executable" section).

**Rationale**: Core Design Principle #7, and the entire premise of "Berry Intelligence becomes the first Domain Pack... not the architectural identity of the platform" (product direction).

**Alternatives considered**: a code-plugin model (rejected for V2 as unjustified complexity/security-surface given nothing in current scope needs custom Domain Pack *logic*, only configuration — flagged as a possible `LATER` extension); keeping domain concepts hard-coded and just parameterizing them more (rejected — doesn't achieve the actual goal of a second Domain Pack requiring zero core code changes, which Phase 7 explicitly tests for).

**Consequences**: V1's hard-coded constants (`BERRIES`, `SOURCE_ENTITY_TYPES`, the 10-value relationship predicate enum, `PRIORITY_DIMENSIONS`) must all be extracted into the Berries Domain Pack (Phase 1) before Phase 7 can validate the boundary was drawn correctly. **Reviewer modification (2026-08-13)**: Phase 1 itself only *implements* the surfaces concretely required by the Berries reference build — manifest, entity types, relationship predicates, taxonomies, strategic-question templates, collector templates. Report templates, visualization configuration, and advanced filter configuration remain *specified* in `04-DOMAIN-PACK-SPEC.md` (the full contract still stands) but become implementation work only once Phase 1.5 or Phase 4 demonstrates a concrete need — avoiding speculative abstraction ahead of a proven use.

---

## D-008 — Organization / Workspace / Domain scoping present from the start, not deferred

**Status**: ACCEPTED (2026-08-13)

**Decision**: the `Organization → Workspace → Domain` hierarchy (`03-DOMAIN-MODEL.md`) exists as real schema/database structure from Phase 3 onward, even though V2 itself runs as a single Organization with a single Workspace. Real multi-tenant *isolation* (row-level security, per-tenant access control) is explicitly deferred to Phase 8.

**Rationale**: retrofitting a tenancy boundary into a schema that was never designed with one is expensive and risky once real data depends on the old shape; adding the *structure* now, without the *enforcement* machinery, costs little and prevents that future rewrite.

**Alternatives considered**: deferring the schema entirely until multi-tenancy is actually needed (rejected — this is precisely the kind of decision that's cheap now and expensive later, distinct from "add infrastructure because it's fashionable," since it's schema shape, not running infrastructure); building full multi-tenant isolation now (rejected — explicitly premature per the task's own instruction and Core Design Principle against over-generalization, `09-RISK-REGISTER.md`).

**Consequences**: every core object carries a `workspace_id` from Phase 3 onward, a small but permanent addition to every table/schema.

---

## D-009 — No big-bang rewrite; every replacement has a migration bridge

**Status**: ACCEPTED (2026-08-13)

**Decision**: no component in `06-MIGRATION-MAP.md` marked `REPLACE` is cut over without a verified bridge first (re-homing proven logic for collectors and imports; side-by-side operation for search; for storage specifically, the revised bounded freeze/archive/parity-check/staging/cutover sequence in D-001, not an extended dual-write). The V1 application remains usable throughout (Core Design Principle #10).

**Rationale**: explicit task instruction ("No big-bang rewrite is allowed"); also the only responsible way to satisfy "the existing blueberry dataset must be preserved" against the top-ranked risk in `09-RISK-REGISTER.md` (migration data loss).

**Alternatives considered**: an unbridged, scheduled cutover window (rejected — no bridge at all is the actual big-bang pattern this decision exists to prevent); an *extended*, indefinitely-running dual-write period (considered and rejected on review — see D-001's reviewer modification — in favor of a bounded, verified sequence that still avoids a big-bang cutover without maintaining two simultaneous operational sources of truth indefinitely).

**Consequences**: Phase 3 still takes longer than a naive "just point the app at Postgres" cutover would, but is now bounded (a defined acceptance period, not an open-ended parallel-run) rather than open-ended — a deliberate, accepted, and now-tightened tradeoff.

---

## D-010 — Claim: separate schema, or remain a Fact subtype?

**Status**: ACCEPTED (2026-08-13) — **Option A**

**Decision**: Claim remains a subtype/classification of Fact. `fact.classification = "fact" | "claim"`, sharing every field with Fact. **No separate Claim persistence schema is introduced in V2** unless a future concrete workflow demonstrates that Claims require materially different fields or a materially different lifecycle from Facts.

**Rationale**: V1's current approach is simple, already validated at scale (132 fact / 54 claim records), and the classification enum is the entire mechanism making the FACT/CLAIM distinction real — splitting the schema would add structure without a demonstrated need. See `03-DOMAIN-MODEL.md`'s Claim section (updated this review) for the full reasoning this decision closes out.

**Alternatives considered**: splitting Claim into its own schema now, anticipating future divergence (rejected — no concrete workflow has yet shown Facts and Claims need different required fields or a different review lifecycle; introducing the split speculatively would be exactly the over-generalization risk `09-RISK-REGISTER.md` (R-02) warns against).

**Consequences**: every place this document set previously described Claim as "TBD"/"unresolved" is updated to reflect Option A directly (`03-DOMAIN-MODEL.md`, `07-IMPLEMENTATION-ROADMAP.md` Phase 1, `10-BACKLOG.md`). If a future phase (most likely Phase 1.5 or Phase 4, once real Claims are reviewed in volume) surfaces a concrete need for divergent fields or lifecycle, that becomes a new, separately-numbered decision — not a reopening of this one.

---

## D-011 — Recommendation and Evidence Priority: relationship and semantics

**Status**: ACCEPTED (2026-08-13)

**Decision**: **Evidence Priority and Recommendation coexist permanently — this is not a migration-period compromise, it's the target state — because they answer different questions:**

- **Evidence Priority** (the existing four dimensions: `reading`, `testing`, `commercial_position`, `monitoring`) is a **triage** signal, attached directly to one Evidence record. It answers: *"How urgently, or in what way, should an analyst pay attention to this specific evidence item?"*
- **Recommendation** is a **decision/action** object (`03-DOMAIN-MODEL.md`). It answers: *"What action or decision is proposed based on accumulated intelligence?"* A Recommendation normally traces through `Recommendation → Assessment and/or Signal → Facts → Evidence → Source` — it is downstream of interpretation, never a shortcut around it.

Because the two objects answer genuinely different questions at genuinely different points in the lineage chain (Evidence Priority sits *on* Evidence itself; Recommendation sits *downstream* of Assessment/Signal/Facts), **existing `evidence.priority` values are not mechanically converted into Recommendation records.** A high reading-priority evidence item does not automatically imply any proposed action exists yet — that requires actual analytical work (an Assessment or Signal) in between. `10-BACKLOG.md`'s BL-052 is replaced accordingly (see below).

**Rationale**: this is a resolution, not a compromise between the two options this log previously floated ("replace" vs. "coexist as a migration-period default") — reviewer input clarified that the two objects were never actually competing for the same role, which is why forcing a mechanical conversion would have been a category error, not just unnecessary work.

**Alternatives considered**: mechanically converting every `evidence.priority` value with a non-`none` level into a Recommendation (rejected — would flood the Recommendation object with entries that aren't actually action/decision proposals, undermining exactly the lineage-integrity discipline `Recommendation`'s schema is designed to enforce, Core Design Principle #3); retiring `evidence.priority` in favor of Recommendation-only (rejected — Evidence Priority is a real, working, lighter-weight triage mechanism serving a genuinely different purpose, used by 124 live records today, and there's no reason a fast triage signal should require the full Assessment/Signal-anchored chain).

**Consequences**: `10-BACKLOG.md`'s BL-052 changes from "migrate every priority value into a Recommendation" to a **bounded review task**: examine the existing curated (124-record) priority-tagged evidence and create Recommendation records *only* where an actual, action-oriented recommendation is genuinely supported by the accumulated intelligence — not a 1:1 mechanical sweep. `03-DOMAIN-MODEL.md`'s Recommendation section is updated to state this permanent-coexistence relationship directly rather than flagging it as an open question.

---

## D-012 — Explicit analytical scope for Assessment, Recommendation, and Signal

**Status**: ACCEPTED (2026-08-14, Phase 2A)

**Decision**: **Explicit analytical scope and evidence provenance are separate concepts.** `assessment.schema.json` and `recommendation.schema.json` gain three new **optional, additive** fields — `domain_ids`, `market_ids`, `geography_ids` (all arrays of strings, all defaulting to absent/empty, none required) — expressing what analytical context a record explicitly claims to apply to. `signal.schema.json` gains `domain_ids` and `geography_ids` for the same reason, while keeping its existing `berry_ids` field as Signal's own market-scope field rather than renaming it to `market_ids` for cosmetic consistency. A record may declare zero, one, or many values in each field — a genuinely cross-market or global record (e.g., an Assessment about capital flows across the whole berry-genetics category, not one berry) is representable without duplicating the record. Workspace scope (D-008: every persisted core object belongs to exactly one Workspace) is unaffected and unchanged by this decision — Workspace answers "whose data is this, administratively"; the fields added here answer "what is this data *about*, analytically," a different and multi-valued question.

Derived scope — walking `entity_ids` outward to the entities' own market/domain membership, which is what `landscape_intelligence_objects()` (Phase 1.5B, `app/main.py`) does today for Assessment/Recommendation in the absence of any explicit field — remains available and useful **but is demoted to a validation hint, a convenience (e.g. pre-filling a create form), and an enrichment mechanism.** It is never the sole or authoritative source of scope once an explicit value exists. When explicit scope and derived scope disagree — specifically, when the entities a record cites belong to a market/domain the record's own explicit `market_ids`/`domain_ids` doesn't list — that is a detectable, reportable data-quality finding, surfaced for human review, never silently auto-corrected and never used to block publishing.

**Rationale**: `docs/v2/PHASE-1-5-PROTOTYPE-FINDINGS.md` (Phase 1.5B) identified this as the one concrete schema gap the synthesis prototype surfaced — the Landscape's transitive entity-intersection workaround produces correct results today only because this deployment has exactly one populated berry and only one real Assessment/Recommendation exist; it would silently mis-scope the moment either condition changes (a multi-market entity, a genuinely cross-market record with no anchoring entity at all). `docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md` Part 2 works through the full design; this entry records the decision itself.

**Alternatives considered**: leaving scope permanently derived-only (rejected — this is the status quo the finding already showed to be unsafe at scale, and it structurally cannot represent a record with no anchoring entity, e.g. a purely macro-level Assessment); one untyped `scope_ids` array instead of three typed fields (rejected — domain, market, and geography are independently filterable dimensions in real query patterns already observed, e.g. the Landscape's Geographic footprint section filters on a dimension that doesn't align 1:1 with its market/berry partition; one bag would force every consumer to re-derive which id belongs to which axis via naming convention, the exact "free strings, unenforceable" problem `04-DOMAIN-PACK-SPEC.md` Section 3 already flagged for entity roles); renaming Signal's `berry_ids` to `market_ids` for naming symmetry (rejected — six live, valid, working Signal records already use `berry_ids`; renaming a working field for cosmetic consistency alone is exactly the churn D-002's "additive, compatible schema evolution" principle exists to prevent, and the *concept* is what needs to be symmetric across the three object types, not the literal JSON key); making the new fields required (rejected — would immediately invalidate every existing live Signal/Assessment/Recommendation record, violating this decision's own backward-compatibility premise and D-002).

**Consequences**: `schemas/assessment.schema.json`, `schemas/recommendation.schema.json`, and `schemas/signal.schema.json` gain the fields described above (implemented in Phase 2A alongside this decision, verified via `scripts/validate_records.py` to introduce zero validation regressions against live data — no existing record is rewritten). No repository, query, or route code changes in Phase 2A; Phase 2B's query-service layer (`docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md` Part 3.3) is expected to implement the `scope_disagreements()` detection function and the scope-aware `list()` filters this decision specifies, but does not do so yet. Legacy records (all six imported Signals, the one Assessment, the one Recommendation) are unaffected in substance — they simply have no explicit `domain_ids`/`market_ids`/`geography_ids` values yet, which is a true, honest statement of "scope not yet explicitly declared," not silently read as "applies everywhere." Backfilling explicit scope onto those specific existing records is a future data-authoring decision, not required by this decision and not performed in Phase 2A.
