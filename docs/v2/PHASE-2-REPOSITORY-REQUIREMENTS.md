# Intelligence OS V2 — Phase 2A: Repository Contract & Scope Semantics

**Status:** Written 2026-08-14, against commit `9fc9daa` on `v2/intelligence-os` (Phase 1.5 complete and visually accepted; the pre-Phase-2 tablet-navigation MUST-FIX resolved). **This document is a design/contracts deliverable.** It defines what Phase 2B implements; it does not implement a repository layer, does not touch PostgreSQL, and does not migrate any route. Every access pattern below was verified directly against `app/main.py` as it exists today — not inferred from planning docs, and not designed from a generic CRUD template.

**Relationship to other documents:** this is the authoritative source for Phase 2B's implementation scope. `docs/v2/07-IMPLEMENTATION-ROADMAP.md`'s Phase 2 section, `docs/v2/10-BACKLOG.md`'s Phase 2 items, and `docs/v2/PHASE-1-5-PROTOTYPE-FINDINGS.md`'s Section 8 ("Phase 2 implications") are all inputs to this document, not restated in full here — read them first if the *why* behind a requirement isn't obvious from this document alone.

---

## Part 1 — Inventory of actual access patterns

Every pattern below was located by reading `app/main.py`'s actual route handlers and helper functions (not by re-deriving from `docs/v2/PHASE-1-5-PROTOTYPE-FINDINGS.md`'s 9-item list, which is folded in here as a subset, verified, and expanded to 23 patterns). Line-number references are to `app/main.py` at commit `9fc9daa`; they will drift as the file changes and are given for traceability at the time of writing, not as a permanent index.

### 1.1 Read patterns

| # | Screen / workflow | Objects accessed | Current implementation | Filters | Sort | Traversal | Core / Domain | Result shape |
|---|---|---|---|---|---|---|---|---|
| R1 | Newsfeed (`/`) | Evidence | `filter_evidence()` (L463) over `published_evidence()` | text (q), berry, source_type, priority:level, competitor (entity_id), geography, region | `published_evidence()` sorts by `published_date`/`captured_date` desc | none | **CORE QUERY** (filter mechanism) + **DOMAIN-PACK** (which filter *dimensions* exist — berry/competitor/geography are Berries-specific per `04-DOMAIN-PACK-SPEC.md` Section 7) | list of raw Evidence dicts |
| R2 | Evidence detail (`/evidence/{id}`) | Evidence, Facts, Relationships, Entities | direct lookup + `facts_for_evidence()`, `relationships_for_evidence()`, entity_id resolution against `entity_index()` | none (single record) | n/a | Evidence → Facts (reverse ref via `evidence_ids`), Evidence → Relationships (reverse ref), Evidence → Entities (forward ref via `entity_ids`) | **CORE QUERY** | one Evidence dict + 3 related lists |
| R3 | Entity list (`/entities/{type}`) | Entities of one type | `filter_entities()` (L550) | text (q), berry, region, company (relationship-derived) | name asc | Entity → Entity via `related_entity_ids()` (for the `company` filter) | **CORE QUERY** (mechanism) + **DOMAIN-PACK** (berry/region/company as filter dimensions) | list of raw Entity dicts |
| R4 | Entity detail — generic (`/entities/{type}/{id}`) | Entity, Evidence, Facts, Relationships, Signals, Assessments, Recommendations, Strategic Questions | direct lookup + `facts_for_entity()`, `relationships_for_entity()`, `entity_activity()` (merged timeline), `entity_synthesis_context()` (Phase 1.5B: `signals_for_entity()`, `assessments_for_entity()`, `recommendations_for_entity()`, `strategic_questions_for_entity()`, `grouped_relationships_for_entity()`) | none (single record) | `entity_activity()` sorts its merged feed by date desc | Entity → Evidence (reverse), Entity → Facts (reverse), Entity → Relationships (both directions, resolved to the *other* entity), Entity → Signal/Assessment/Recommendation (reverse via `entity_ids`), Entity → Strategic Question (union via linked Evidence/Signal/Assessment/Recommendation) | **CORE QUERY** — every function listed is entity-type-agnostic | one Entity dict + ~7 related lists, one merged/sorted timeline |
| R5 | Entity detail — variety-specific addendum | Entity.attributes, Patent entities | `variety_trait_profile()`, `variety_patent_link()`, breeding-program lookup via `attributes.breeding_program_id` | none | none | Variety.attributes.traits[].trait → Trait entity name (lookup); Variety.attributes.patent_number → Patent entity (fuzzy match) | **DOMAIN-PACK / DOMAIN SERVICE** — reads Berries-specific `attributes` conventions no other entity type uses | trait-profile rows, one Patent dict or None, one breeding-program dict or None |
| R6 | Work Queue (`/work-queue`) | Evidence, Drafts, Entities, Signals | `published_evidence()[:5]`, `list_drafts()`, `unresolved_entities()`, high-priority filter (any dimension = high), `all_signals()[:5]`, `queue_counts()` | implicit: `status=unverified` for entities, `priority.*.level=high` for evidence | most-recent-first (evidence/signals), by construction (drafts) | none | **UI COMPOSITION** — assembles 6 unrelated small lists for one dashboard, no synthesis logic of its own | 6 independent lists + 1 count dict |
| R7 | Priority queue (`/queues/{dimension}`) | Evidence | `queue_items(dimension)` — filters `published_evidence()` where `priority[dimension].level != 'none'`, optional region filter | dimension (path param), region (query param) | two-stage: date desc within level, then level rank (high→low) | none | **CORE QUERY** (mechanism) + **DOMAIN-PACK** (the 4 priority dimensions themselves are a Berries-authored triage taxonomy, not a core concept — see `03-DOMAIN-MODEL.md`'s Evidence Priority discussion) | list of raw Evidence dicts |
| R8 | Strategic Question list/detail | Strategic Questions, Evidence | `load_strategic_questions()`, `evidence_for_strategic_question(sq_id)` | none | none | Strategic Question → Evidence (reverse ref via `strategic_question_ids`) | **CORE QUERY** | list/one dict + reverse-linked Evidence list |
| R9 | Signal list/detail (`/signals`, `/signals/{id}`) | Signals, Evidence, Facts, Entities, Strategic Questions | `all_signals()`, `signal_by_id()`, plus the same reverse/forward lookups as R2/R4 applied to a Signal | none on list; none on detail (single record) | `all_signals()` sorts by `last_updated` desc | Signal → Evidence/Facts/Entities/Strategic Questions (all forward refs) | **CORE QUERY** | list or one Signal dict + linked lists |
| R10 | Assessment list/detail | Assessments, Facts, Evidence, Entities, Strategic Questions, Facts-as-counterevidence | `all_assessments()`, `assessment_by_id()` | none | `created_at` desc | Assessment → Facts/Evidence/Entities/Strategic Questions/Counterevidence (all forward refs) | **CORE QUERY** | list or one dict + linked lists |
| R11 | Recommendation list/detail | Recommendations, Assessments, Signals, Facts, Evidence, Entities, Strategic Questions | `all_recommendations()`, `recommendation_by_id()` | none | `created_at` desc | Recommendation → Assessment/Signal (forward), then transitively to Facts/Evidence (the lineage chain) | **CORE QUERY** | list or one dict + linked lists across two hops |
| R12 | Sources (`/sources`) | Sources (configuration, not a core intelligence object) | `filter_sources()`, `load_sources()` | entity_type, berry, region, priority, view (gaps/due), group_by | grouped, not flat-sorted | none | **DOMAIN-PACK** — the whole Source-registry concept and its filter taxonomy is Berries-specific collector configuration (`04-DOMAIN-PACK-SPEC.md` Section 5) | grouped dict of lists |
| R13 | Review Queue (`/review`) | Drafts (inbox), unvalidated auto-captured Evidence | `list_drafts()`, `unvalidated_auto_captured_evidence()` | implicit: `auto_captured=true, validated=false` | drafts by `captured_date` desc; unvalidated by source monitoring-priority then date | none | **CORE QUERY** — a "what needs a human decision" queue, not domain-specific in mechanism (though the source-priority sort input is Domain-Pack config) | 2 lists |
| R14 | Duplicate detection (used during Intake/Review) | Evidence, Drafts | `find_possible_duplicates(title)` — fuzzy substring match over `all_evidence() + list_drafts()` | title similarity (substring both directions) | none | none | **CORE QUERY** — generic near-duplicate title matching, not domain-specific | list of candidate dicts |
| R15 | Search — live app (header dropdown, `/api/search`) | Evidence, Entities | `text_matches()` (substring + typo-tolerant fuzzy fallback), `filter_evidence(q=...)`, entity name/alias/description scan | free-text query | none server-side | none | **CORE QUERY** — the fuzzy-match mechanism itself is domain-agnostic | `{"evidence": [...], "entities": [...]}` |
| R16 | Search — static build (Pagefind + `search-core.js`) | Evidence (as `type:evidence`), Entities (as `type:entity`) | Pagefind's own index, ranked by `mergedSearch()`: entity matches first, then evidence by date desc, deduped | free-text query, `type` facet | entity-first, then date desc | none | **CORE QUERY** (ranking logic) — `mergedSearch()`'s "entities outrank incidental mentions" rule is a reusable design reference per `06-MIGRATION-MAP.md`, not Berries-specific | ranked, deduped result list |
| R17 | Blueberry Landscape (`/landscapes/berries/blueberry`) | Signals, Assessments, Recommendations, Strategic Questions, Entities (companies, varieties, geographies), Evidence, Facts, Relationships | `landscape_context()` — the single largest aggregation in the app; see Section 1.2 below | `berry_id` (currently hard-coded to `berry-blueberry` at the route) | multiple, section-specific (alphabetical for rollups, date-desc for movement) | extensive — see 1.2 | **mixed, itemized in 1.2** | one large composed context dict, ~9 top-level sections |
| R18 | Static build (`scripts/build_static.py`) | everything above | calls the *exact same* helper functions as the live routes, in a loop, once per record | none (renders every record) | same as live routes | same as live routes | same classification as the live pattern it mirrors | N rendered HTML files |

### 1.2 Landscape (R17) broken into its constituent sub-patterns

The Landscape is not one query — `landscape_context()` composes at least 8 independently-classifiable sub-patterns, matched to the exact function that implements each (all in `app/main.py`, all added in Phase 1.5B):

| Sub-pattern | Function | Traversal | Classification |
|---|---|---|---|
| Records within analytical scope (Signals) | `landscape_intelligence_objects()`, Signal branch | direct: `berry_id in Signal.berry_ids` | **CORE QUERY**, blocked on Part 2 below — Signal has a real scope field to query |
| Records within analytical scope (Assessment/Recommendation) | `landscape_intelligence_objects()`, Assessment/Recommendation branch | **indirect**: berry-scoped entity id set ∩ `entity_ids` | **CORE QUERY today, but a workaround** — see Part 2; this is the exact gap D-012 resolves |
| Entities within scope | `landscape_entities()` | direct: `berry_id in Entity.berry_ids`, minus seed-fixture exclusion | **CORE QUERY** + **DEFER** (the exclusion list itself, see Part 6) |
| Competitive field rollup (company × variety/patent/brand/geography counts) | `landscape_competitive_field()` | Company → Relationship → {Variety, Patent, Brand, Geography}, grouped and counted per company | **DOMAIN-PACK / DOMAIN SERVICE** — this is exactly `04-DOMAIN-PACK-SPEC.md` Section 6's "Blueberry Landscape" report template, described in the spec, implemented for the first time here |
| Variety rollup | `landscape_variety_rollup()` | Variety.attributes → breeding program entity, trait count, evidence count, Signal/Assessment touches | **DOMAIN-PACK / DOMAIN SERVICE** |
| Geographic footprint | `landscape_geographic_footprint()` | Geography → region (name-lookup table `REGION_LOOKUP`), Relationship (`operates_in`) → region, Evidence → region (via `evidence_regions()`) | **DOMAIN-PACK / DOMAIN SERVICE** (the region-bucketing *table* is Berries-authored; the bucket-then-aggregate *mechanism* is closer to CORE — flagged as a hybrid in Part 3) |
| Recent meaningful movement | `landscape_recent_movement()` | Evidence filtered to `id ∈ ⋃(Signal/Assessment/Recommendation.evidence_ids)`, sorted by date desc, capped | **CORE QUERY** — "evidence something else already cited" is a generic relevance pattern, not Berries-specific |
| Evidence coverage & limitations | `landscape_evidence_coverage()` | Evidence source-type distribution, Fact confidence/dispute counts scoped to berry-entity set, Relationship dispute counts, unresolved Strategic Question count, thin-coverage Variety list | **CORE QUERY** (the aggregate mechanism) + **DOMAIN-PACK** (`PRIMARY_SOURCE_TYPES`, which source types count as "primary/registry-grade," is a Berries-specific epistemic judgment) |

### 1.3 Write patterns

| # | Screen / workflow | Objects written | Current implementation | Complexity | Core / Domain |
|---|---|---|---|---|---|
| W1 | Evidence validate (`POST /evidence/{id}/validate`) | Evidence (state transition) | direct field mutation + `save_evidence()` | single-record update | **CORE PERSISTENCE** |
| W2 | Evidence purge (`POST /evidence/{id}/purge`) | Evidence (delete), Source (tally bump), blocked-domains list | `path.unlink()` + conditional `bump_source_tally()` + conditional `add_blocked_domain()` | single-record delete with 2 conditional side effects | **CORE PERSISTENCE** (delete) + **DOMAIN-PACK** (the blocked-domain/source-tally side effects are Berries collector-config concepts) |
| W3 | Signal / Assessment / Recommendation create (`POST /signals`, `/assessments`, `/recommendations`) | one new record each | build dict → `get_validator(schema).iter_errors()` → `save_X()` | single-record create, schema-validated at write time | **CORE PERSISTENCE** |
| W4 | Source create/toggle/delete/check-now/mark-checked | Source (in a flat `sources.json` list, not one-file-per-record like everything else) | `save_sources()` rewrites the *entire* source list every time | single-record logical change, whole-collection physical write | **DOMAIN-PACK** — Sources are Berries collector configuration, and this write pattern (rewrite-whole-collection vs. one-file-per-record) is itself a real inconsistency worth normalizing behind the repository interface, not exposing to Phase 2B route code |
| W5 | Intake draft create (`POST /intake`) | one new Evidence draft (in `inbox/`, not `data/`) | `save_draft()` + optional `save_attachment()` | single-record create in a separate storage location | **CORE PERSISTENCE** — but the *location* split (`inbox/` vs. `data/evidence/`) is exactly what `06-MIGRATION-MAP.md`'s Intake entry already flags for unification behind `review_state: draft` |
| W6 | Review/publish (`POST /review/{id}/publish`) | **one Evidence, up to `NUM_FACT_ROWS` Facts, up to `NUM_RELATIONSHIP_ROWS` Relationships, and zero-or-more new Entities** (via `unique_entity_id()` when a typed company/variety/geography name doesn't match an existing entity), plus draft deletion and attachment migration | the single most complex write in the app — multiple object types created in one logical operation, some of them (Entities) created *implicitly* as a side effect of typed free text, not explicitly requested | **the only genuinely multi-object transactional write pattern in the entire application** | **CORE PERSISTENCE**, but see Part 3 — this is the strongest argument in the whole codebase for a **unit-of-work** concept in the repository interface, not five independent single-record saves that could partially fail |

### 1.4 What this inventory changes about the Phase 1.5 findings' 9-item list

`docs/v2/PHASE-1-5-PROTOTYPE-FINDINGS.md` Section 2 named 9 missing query capabilities from the Landscape/Company/Variety prototypes alone. Verified against the full application (not just Phase 1.5B's own code), all 9 hold up, plus 14 more patterns exist that Phase 1.5B's findings document had no reason to surface (search, review/publish, sources, work-queue, priority queues) because that document was scoped to the three synthesis screens. The two most consequential additions this broader inventory found:

1. **W6 (review/publish)** is the only pattern in the entire application that needs multi-object transactional semantics. Every other write is a single record. A repository interface designed only from the Landscape/Company/Variety read patterns would never have surfaced this — it's a write-side requirement, and Phase 1.5's findings document only looked at reads.
2. **W4 (sources)** writes its entire collection on every change, unlike every other object type's one-file-per-record convention. This is real, existing inconsistency the repository interface needs to normalize (present a uniform `create`/`update`/`delete` contract to callers) rather than leak into Phase 2B route code as "sources are special."

---

## Part 2 — Scope semantics

### 2.1 The problem, restated precisely

`assessment.schema.json` and `recommendation.schema.json` have no field expressing "what analytical context (market, domain, geography) does this apply to." `signal.schema.json` does have `berry_ids`, inherited from the original V1 Signal shape. The Landscape (`landscape_intelligence_objects()`, Section 1.2 above) works around the gap for Assessment/Recommendation by intersecting their `entity_ids` against the set of entities already known to belong to a berry — a real, working approximation, but one that is silently wrong the moment an Assessment names an entity that itself touches more than one market (e.g., a company active in both blueberry and raspberry), or the moment a genuinely cross-market or global Assessment exists with no entity to anchor the intersection at all.

### 2.2 Resolution

Following this task's architectural rule (Workspace scope is singular; analytical scope is explicit, multi-valued, and separate from provenance):

**Workspace scope.** Every persisted core intelligence record (Entity, Evidence, Fact, Relationship, Signal, Assessment, Recommendation, Strategic Question) belongs to exactly one Workspace. This is already `03-DOMAIN-MODEL.md`'s stated design (D-008, `08-DECISION-LOG.md`) — a `workspace_id` field, real from Phase 3 onward, not enforced pre-Postgres since V2 today runs as a single implicit Workspace. Nothing in this task changes that; it's restated here only because analytical scope (below) must not be confused with it. Workspace answers "whose data is this, administratively." Analytical scope answers "what does this data claim to be *about*."

**Analytical scope — explicit fields, proposed.** Add three optional array fields to `assessment.schema.json`, `recommendation.schema.json`, and (for consistency, see 2.5) `signal.schema.json`:

```json
"domain_ids": {
  "type": "array",
  "items": {"type": "string"},
  "$comment": "Which Domain(s) this record analytically applies to (e.g. a Domain Pack activation id). Explicit, not derived -- see docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md Part 2. Absent or empty means scope is not yet explicitly declared, not 'applies everywhere'."
},
"market_ids": {
  "type": "array",
  "items": {"type": "string"},
  "$comment": "Which market/category id(s) within a domain this applies to -- for Berries, this is the existing berry_ids concept, generalized to a name that isn't berry-specific at the core-schema level. A Berries Domain Pack maps its own berry_ids values into this field 1:1."
},
"geography_ids": {
  "type": "array",
  "items": {"type": "string"},
  "$comment": "Which geography entities this record's analysis is scoped to, when narrower than the full domain/market -- e.g. an Assessment specifically about southern Africa licensing dynamics. Optional; absent means no explicit geographic narrowing was declared."
}
```

All three are **optional arrays**, never required, never singular. A record with zero values in all three is explicitly "scope not yet declared" — not a validation error, and not silently treated as "applies to everything." A record with multiple values in `market_ids` is a genuinely cross-market Assessment (e.g., "financial capital entering *berry genetics* broadly" naming both `berry-blueberry` and `berry-raspberry`), representable without duplicating the record — directly satisfying this task's "a global or cross-market Assessment must be representable without duplication" instruction.

**Why three separate fields, not one `scope_ids` bag.** Domain, market, and geography are different *kinds* of scope that a query needs to filter on independently (the Landscape page's own five sections filter by market and by geography as separate, not-always-aligned dimensions — see the Geographic footprint sub-pattern in 1.2, which is explicitly not the same partition as the market/berry one). Collapsing them into one untyped array would force every consumer to re-derive which id belongs to which axis by checking id-prefix conventions — exactly the "free strings, unenforceable" problem the blueberry import package's own P-9 proposal already flagged for entity roles (`04-DOMAIN-PACK-SPEC.md` Section 3).

### 2.3 Provenance is separate from scope — the two mechanisms and how they relate

- **Explicit scope** (`domain_ids`/`market_ids`/`geography_ids`, above) is the *authoritative* answer to "what analytical context does this record apply to." It is set by whoever authors the record (human today; `ai_proposed: true` content later, same as every other field).
- **Derived scope** (walking `entity_ids` → each entity's own `berry_ids`/domain membership, exactly what `landscape_intelligence_objects()` does today) remains available and useful, but demoted to what this task specifies: a **validation hint**, a **convenience** (e.g., pre-filling a create form's scope fields from the entities the author already picked), and an **enrichment mechanism** (e.g., a UI badge reading "derived scope: blueberry, raspberry" next to the explicit one, for an author who forgot to set it). It is never the sole mechanism a query relies on once explicit scope exists.

**Scope disagreement detection.** When a record has explicit scope *and* resolvable entity references, a repository/query-layer function compares the two: `derived_market_ids = ⋃(entity.market_ids for entity in resolve(record.entity_ids))`. If `derived_market_ids` is not a subset of `record.market_ids` (i.e., the entities touch a market the explicit scope doesn't declare), that is a **detectable, reportable inconsistency** — surfaced as a data-quality finding (e.g., in a future review-queue-style "scope mismatch" list), never silently auto-corrected and never treated as a validation failure that blocks publishing. The direction of the check matters: derived scope *narrower than or equal to* declared scope is fine (an author is allowed to declare broader intent than the specific entities cited so far demonstrate); derived scope *wider than* declared scope is the interesting case worth flagging.

### 2.4 Legacy record behavior

The one real Assessment and one real Recommendation from Phase 1.5A, and all six imported Signals, currently have no `domain_ids`/`market_ids` values (Signals already have `berry_ids`, which maps directly). Because the new fields are optional:

- They continue to validate against the updated schemas with zero changes (verified in Part "implementation" below via `scripts/validate_records.py` against live data).
- They are **not** silently treated as "scope: everything" — a query that filters strictly by explicit `market_ids` would find zero of them, which is the *correct*, honest behavior for a record making no explicit claim, not a bug to route around.
- The Landscape's existing derived-scope workaround (`landscape_intelligence_objects()`) remains exactly as-is for these legacy records and for any future record that also doesn't set explicit scope — derived scope is always a valid fallback when explicit scope is absent, per 2.3. Nothing about this record's *data* needs to change in this task; only the *schema* gains the option.
- A future, separately-scoped task (Phase 2B or later, not this one) can choose to backfill explicit `market_ids: ["berry-blueberry"]` onto the existing Signal/Assessment/Recommendation records, since their true scope is in fact known and singular today — but that is a data-authoring decision, not a schema requirement, and is explicitly **not done in this task** per the "do not rewrite all existing records" instruction.

### 2.5 Should Signal gain the same fields, for consistency?

**Yes, add `domain_ids` and `geography_ids` to `signal.schema.json`; keep `berry_ids` as Signal's existing market-scope field rather than renaming it.** Reasoning:

- Signal already has `berry_ids` (required-in-practice, though not schema-required — all 6 live Signals set it) serving exactly the role `market_ids` plays for Assessment/Recommendation. Renaming a field with 6 live, valid, working records for naming consistency alone is exactly the kind of churn this task's "additive, optional, backward-compatible" instruction exists to prevent — the value is in having *a* market-scope field, not in every object calling it the identical name at the JSON level. `market_ids` (Assessment/Recommendation) and `berry_ids` (Signal) are documented as the same *concept*, deliberately not unified into one literal field name.
- Signal currently has **no** `domain_ids` or `geography_ids` field at all — that gap is real and should close the same way Assessment/Recommendation's does, for the same reason (Section 2.1's problem applies to Signal too, just less visibly today since every live Signal happens to be single-market).
- This keeps the three object types symmetric in *capability* (all three can express domain, market/berry, and geography scope explicitly) without forcing a cosmetic rename that touches zero new capability.

### 2.6 D-012

A new decision log entry is required (this is a genuine architectural resolution, not an implementation detail) — see `docs/v2/08-DECISION-LOG.md` D-012, added by this task.

---

## Part 3 — Repository and query boundary design

### 3.1 The shape of the boundary

Not "one repository class per object type" and not "one giant repository god-object." Three layers, matching the three genuinely different *kinds* of operation Part 1's inventory surfaced:

1. **Record repositories** — one per core persisted object type (Entity, Evidence, Fact, Relationship, Signal, Assessment, Recommendation, StrategicQuestion, Source, Draft). Each exposes exactly the CORE PERSISTENCE operations (Section 3.2) and the single-hop CORE QUERY operations that are genuinely about *that* object type alone (get-by-id, list-with-filter). This is the layer that has a JSON-file implementation today and a PostgreSQL implementation later — the actual swap seam.
2. **Query services** — cross-object, multi-hop read operations (reverse references, timelines, coverage aggregates). These call *into* multiple record repositories, never touch storage directly, and are where every CORE QUERY pattern in Part 1 that spans more than one object type lives (`entity_activity()`, `strategic_questions_for_entity()`, `grouped_relationships_for_entity()`, the lineage-traversal need in R11). A query service has exactly one implementation regardless of which record-repository backend is active underneath it — it's written entirely in terms of the record-repository interface, so it does not need its own JSON-vs-Postgres variant.
3. **Domain services** — every DOMAIN-PACK / DOMAIN SERVICE pattern from Part 1 (the Landscape's competitive-field/variety/geographic rollups, `variety_trait_profile()`, source filtering). These call query services and record repositories, and are where Berries-specific business logic lives, isolated from both storage and from the generic query layer. A second Domain Pack gets its own domain-service implementations without touching layers 1 or 2 at all — this is the concrete mechanism that makes Phase 7's "zero core code changes for a second domain" acceptance criterion achievable.

This is **not** "dozens of tiny repositories" — it's 10 record repositories (one per object type already in `schemas/`), a small number of query services (grouped by *kind* of cross-object question, not one per screen), and domain services that already have a natural home (`app/main.py`'s own `# BERRIES DOMAIN PACK PROTOTYPE LOGIC` and `# BERRIES LANDSCAPE PROTOTYPE LOGIC` comment blocks, added in Phase 1.5B specifically to mark this exact boundary ahead of time).

### 3.2 Core persistence operations (per record repository)

Verified against Part 1's write inventory (W1-W6) and every `save_X`/lookup function in `app/main.py` — not a generic assumption:

| Operation | Verified need | Notes |
|---|---|---|
| `get(id) -> Record \| None` | every detail route (R2, R4, R9, R10, R11) | never raises for "not found" — the caller decides 404 vs. something else (see Part 5) |
| `list(filter=...) -> list[Record]` | every list route (R1, R3, R9, R10, R11, R12) | `filter` is the record repository's own single-object-type filter (text/status/type); cross-object filters belong to query/domain services, not here |
| `create(record) -> Record` | W3, W5, W6 | validates against the object's JSON Schema before persisting (today: `get_validator(schema).iter_errors()`, called inline in every create route — this belongs in the repository, not repeated per route) |
| `update(id, record) -> Record` | W1 (Evidence validate) | today implemented as "load, mutate, `save_X()` the whole record" — the interface should expose this as an explicit `update`, not force every caller to re-implement read-modify-write |
| `delete(id) -> None` | W2 (Evidence purge) | the *only* real delete in the app; must not raise if the record doesn't exist in a way that breaks the idempotent-retry case, but must be distinguishable from "delete of something that never existed" for audit purposes (see Part 5) |

**Not proposed:** a generic `upsert`. Every real `create` call site in Part 1 generates a fresh id (`new_signal_id()`, `new_assessment_id()`, etc.) and never overwrites an existing record; every real `update` call site (only W1) already knows the id and is mutating a known record. Collapsing these into one `upsert` would hide a real distinction (schema validation happens differently for a brand-new record with generated fields vs. a targeted field mutation) that the current code already keeps separate, correctly.

### 3.3 Core query operations (query-service layer)

Derived directly from Part 1's multi-hop patterns, named for what they actually do rather than borrowed from a generic ORM vocabulary:

| Operation | Verified need (Part 1 ref) | Why it's a query service, not a record repository method |
|---|---|---|
| `objects_referencing(entity_id, types=[...]) -> dict[str, list]` | R4's Signal/Assessment/Recommendation/Fact/Relationship lookups, all currently five separate full-scan functions | spans multiple record repositories; a single record repository has no way to know about the other nine object types |
| `relationships_for_entity(entity_id, resolve_other_side=True) -> list[EdgeView]` | R4's `grouped_relationships_for_entity()` | joins Relationship repository + Entity repository; the *direction-and-predicate-honest* rendering (Section 1.2's finding) belongs here, once, rather than being re-implemented per screen |
| `entity_timeline(entity_id) -> list[TimelineItem]` | R4's `entity_activity()` | merges Evidence + Fact + Relationship by date; already exists as one function today, just not yet behind an interface boundary |
| `strategic_questions_for(evidence=..., signals=..., assessments=..., recommendations=...) -> list[StrategicQuestion]` | R4, R8 | reverse-reference union across 4 object types |
| `evidence_for_strategic_question(sq_id) -> list[Evidence]` | R8 | simple reverse reference, but spans repositories (Evidence, filtered by a field that names a different object type) |
| `lineage(recommendation_id) -> LineageChain` | R11's two-hop Recommendation → Assessment/Signal → Facts → Evidence walk | **new, not yet a named function today** — R11's route currently does this inline, ad hoc, once; Part 1.4 flags this as worth promoting to a real operation, since "prove the lineage chain" is the entire point of the Recommendation object (Core Design Principle #3) and deserves one canonical implementation, not one per screen that needs it |
| `duplicates_of(title) -> list[Evidence \| Draft]` | R14 | fuzzy-match across two record repositories (Evidence, Draft) |
| `search(query, types=[...]) -> RankedResults` | R15, R16 | today split between a live Python implementation and a static Pagefind implementation with *shared ranking logic* (`search-core.js`) but *no shared query-service abstraction* — Phase 2B should give both the same query-service interface even though their underlying index differs (this is explicitly named in `06-MIGRATION-MAP.md` as a Phase 3 Postgres-full-text-search REPLACE; Phase 2B's job is only to make sure today's two implementations sit behind one interface shape, not to unify their engines yet) |

### 3.4 Domain-Pack / domain-service operations

Every one of these reads Berries-specific conventions (predicate meaning, `attributes` sub-shapes, region tables, source-type epistemics) that a second Domain Pack would not share verbatim. Listed with the exact `app/main.py` function it generalizes:

| Operation | Generalizes | What a second Domain Pack would supply instead |
|---|---|---|
| `competitive_field(scope)` | `landscape_competitive_field()` | its own definition of what "portfolio" relationships mean for its own predicates (e.g., a SaaS-CI pack's `integrates_with`/`competes_with` instead of `develops`/`owns`/`licenses`) |
| `entity_rollup(entity_type, scope)` | `landscape_variety_rollup()` | its own per-type rollup columns |
| `geographic_footprint(scope)` | `landscape_geographic_footprint()` | its own region taxonomy (the bucket-then-aggregate *mechanism* stays generic; the region-name lookup table does not) |
| `trait_profile(entity)` | `variety_trait_profile()` | its own attribute-claim convention, or none at all if the domain has no trait concept |
| `patent_link(entity)` | `variety_patent_link()` | its own identifier-matching convention, or none |
| `evidence_coverage(scope)` | `landscape_evidence_coverage()` | its own `PRIMARY_SOURCE_TYPES`-equivalent judgment of what counts as authoritative |
| `filter_sources(...)` | `filter_sources()` | its own source-filter dimensions |

### 3.5 UI composition (not a repository or query-service concern at all)

R6 (Work Queue) is the one pattern that is neither a query nor a domain rollup — it's literally "call five unrelated things and put them on one page." This stays exactly where it is today: a route handler composing calls to record repositories and query services, with no new abstraction needed. Naming it explicitly here is itself the useful output — it prevents Phase 2B from over-engineering a "dashboard service" for something that's genuinely just view composition.

---

## Part 4 — Separating repository, query, synthesis, and presentation

### 4.1 The four stages, and where each one lives today vs. where it should live

```
persisted JSON dict                 (record repository's native shape)
        |
        v
query result (typed, cross-object)   (query service's native shape)
        |
        v
domain synthesis (rollup, scoped)    (domain service's native shape)
        |
        v
presentation / view model            (route handler's job, consumed by templates)
```

**Where this boundary already, accidentally, exists today:** `/api/feed`, `/api/entities/{type}/{id}`, and `/api/search` (Part 1's R15/`app/main.py` L3389-3427) already return raw persisted dicts as JSON with zero presentation logic mixed in — proof that stage 1 (or, for `/api/search`, stage 2) outputs are already API-shaped, not HTML-shaped, in the one place the app currently has an API. Phase 2B's job is to make this the *designed* boundary everywhere, not a happy accident in three routes.

**Where the boundary is currently blurred:** `landscape_context()` returns a dict whose keys are named for what the *template* needs (`header_stats`, `competitive_field` rows carrying pre-formatted display fields) rather than a clean domain-synthesis result a Report generator or the future API could reuse as-is without re-deriving the same rollup. This is expected and acceptable for a Phase 1.5B prototype (whose explicit job was UX validation, not architecture) — but Phase 2B should not copy this pattern forward. The recommended fix is not "rewrite `landscape_context()` now" (out of scope, would be a route/behavior change) but: **when Phase 2B implements the domain-service layer, `competitive_field()`/`entity_rollup()`/etc. return the synthesis result (companies with their counts, as data), and a separate, thin presentation-adapter function in the route/template layer adds display-only fields (formatted dates, badge labels)** — exactly the same separation `us_date`/`as_bullets` (the existing Jinja filters) already model for individual fields, just applied at the object level too.

### 4.2 Why this matters beyond Phase 2

This is the direct mechanism for `01-PRODUCT-VISION.md`'s stated goal that "future API, reports, HTML, and downstream exports... reuse the same intelligence layer." A Report (Phase 6) generating a "Blueberry Landscape" PDF and the live `/landscapes/berries/blueberry` HTML page should call the *identical* `competitive_field()` domain-service function and diverge only at the presentation-adapter stage (HTML template vs. PDF template) — not maintain two independent rollup implementations that could silently drift apart in what they count as a company's "portfolio."

---

## Part 5 — Error and integrity semantics

None of these are hypothetical — each is either an already-observed real case in this codebase or a direct consequence of a real write pattern from Part 1.

| Condition | Current behavior (verified) | Proposed repository/query-service behavior |
|---|---|---|
| Missing ID (`get()` on a nonexistent record) | Route-level: raises `HTTPException(404)` inline, ad hoc, in every detail route | Repository `get()` returns `None`; **raising an HTTP-flavored exception is a route-layer decision, not a repository one** — the repository must stay usable from a future API, CLI, or Report generator that wants different not-found handling than a 404 page |
| Duplicate ID on create | Not currently checked — `save_X()` silently overwrites any existing file at that path | **Repository `create()` must raise on an existing id** (a real integrity gap today: two identically-timed writes with a colliding generated id would silently clobber, and nothing detects it) — this is the one place this document proposes real *new* behavior, not just formalizing existing behavior, precisely because generated ids (`new_signal_id()` etc.) already collision-avoid via timestamp+random suffix but nothing structurally *guarantees* it |
| Dangling reference (an `evidence_ids`/`entity_ids`/etc. value that doesn't resolve) | Two different behaviors exist today depending on path: `scripts/validate_records.py` never checks this at all (schema-shape only); `tests/test_intelligence_lineage.py` (Phase 1.5A) checks it only in tests, not at runtime; live create routes (Signal/Assessment/Recommendation) *do* reject unknown referenced ids at write time (`unknown_evidence`/`unknown_facts`/etc. checks) | **Write-time validation (reject unknown references at create) is correct and should move into the repository/query layer unchanged.** Read-time dangling references (a reference that resolved when written but the target was later deleted — currently only possible via Evidence purge, W2) should **not** crash a page; the existing pattern of "resolve against `entity_index()`, silently skip ids that aren't found" (used throughout `entity_detail()` today) is the right behavior for reads and should be formalized as the query-service contract, not treated as a bug — but it must be paired with the referential-integrity test suite (already established practice, `tests/test_intelligence_lineage.py`) staying mandatory in CI, since silent-skip-on-read means orphans are invisible unless something else is watching for them |
| Malformed record (fails its own JSON Schema) | `get_validator(schema).iter_errors()` at write time (routes); `scripts/validate_records.py` at any time for the whole tree | **Unchanged — this is already correct and load-bearing.** The repository `create`/`update` operations must call schema validation before persisting, exactly as every route does today; this is not new design, it's preserving existing correct behavior through the interface change |
| Unsupported entity type | Not currently rejected anywhere — `entity.schema.json` accepts any string for `entity_type` (`03-DOMAIN-MODEL.md`'s own documented gap: "V1 hard-codes these; V2 makes them declarative") | Out of scope for Phase 2A/2B to fix (it's a Domain Pack enforcement question, tracked separately) — but the repository layer should **not** make this worse by adding a new hard-coded entity-type list of its own; it should accept whatever `entity_type` string is given, consistent with today, and defer enforcement to Domain Pack validation (`04-DOMAIN-PACK-SPEC.md`) whenever that's implemented |
| Unsupported relationship predicate | Same situation as entity type — `relationship.schema.json` doesn't constrain `predicate` to the Domain Pack's declared list at write time today | Same conclusion: not a Phase 2A/2B fix; repository layer should not silently invent new enforcement here either |
| Ambiguous scope (Part 2's disagreement case) | Does not exist as a concept today | **Detect, report, never silently resolve** — exactly as specified in Part 2.3. This is a new capability, not a behavior-preservation requirement, and should be implemented as an explicit query-service function (`scope_disagreements(record) -> list[Mismatch]`) callers can opt into, not a validation gate that blocks writes |
| Partial data (a record missing optional fields the UI wants) | Handled today, extensively and correctly, via `or []`/`or {}`/empty-state template branches (`{% else %}<p class="empty-state">...` throughout every template touched in Phase 1.5B) | **Formalize, don't change.** The repository/query layer should return `None`/`[]` for absent optional data, never fabricate a placeholder value — this is the same "honest about what it doesn't know" discipline the Phase 1.5 Landscape work already established as a hard requirement and should propagate to the repository contract explicitly, not be left as "something templates happen to handle well" |
| Draft/unpublished filtering | Currently two different mechanisms for "not ready to show": `published_evidence()` filters `status == "published"`; `inbox/` is a physically separate directory from `data/` for drafts | **Repository layer should expose one filter concept** (a `status`/`review_state` filter parameter on `list()`), not require callers to know that Evidence's "unpublished" state lives in a different *location* than its published state. This directly serves `06-MIGRATION-MAP.md`'s already-planned Evidence review-state unification (`draft → in_review → published`) — Phase 2B's repository interface is the natural place to *present* that unified concept even before Phase 3's schema migration makes it real underneath, by having the JSON-backed implementation quietly check both `inbox/` and `data/evidence/` behind one `list(status=...)` call |

---

## Part 6 — Seed/demo-data treatment

**No migration or removal of demo data happens in this task or in Phase 2B.** This section documents the existing mechanism as technical debt and proposes (without implementing) the eventual fix, per this task's explicit instructions.

### 6.1 Current mechanism (as of `9fc9daa`)

Two hard-coded id sets in `app/main.py` (`SEED_FIXTURE_ENTITY_IDS`, `SEED_FIXTURE_EVIDENCE_IDS`, introduced in Phase 1.5B), used only by the Landscape's aggregation functions (`landscape_evidence()`, `landscape_entities()`). Every other route in the application — entity pages, evidence pages, search, the API — shows the 8 fictional V1 seed/demo records exactly as if they were real intelligence, since only the Landscape knows to exclude them.

### 6.2 Why this is real technical debt, restated for the repository design specifically

A repository/query layer built on top of today's storage, without addressing this, would face a choice: (a) bake the same hard-coded exclusion list into the record-repository layer itself (spreading Berries-specific, prototype-era knowledge into what's supposed to be the generic persistence seam), or (b) leave it as a Landscape-only domain-service concern (correct layering, but means every *other* future domain-service or query-service function that shouldn't surface fictional data has to independently remember to exclude it too, with no structural guarantee). Neither is acceptable as a permanent state — hence the Phase 3 gate below.

### 6.3 Phase 3 migration gate (explicit, added by this task)

**No Intelligence Package used as the PostgreSQL seed (Phase 3, Step 1: "freeze and archive") may contain unmarked fictional/demo records.** This is now a named, checkable precondition on Phase 3's own first step — see `docs/v2/09-RISK-REGISTER.md` R-12 (added by this task) and the Phase 3 update to `docs/v2/10-BACKLOG.md`.

### 6.4 Proposed (not implemented) eventual mechanisms, evaluated

| Option | Evaluation |
|---|---|
| `data_classification: production \| demo \| seed` field on every record | **Preferred candidate.** Least invasive of the three: additive/optional field (same pattern as Part 2's scope fields), works uniformly across every object type with one convention, queryable by any future repository/query/domain layer without special-casing, and self-documenting (a record's own file states its status, rather than an external list that can drift out of sync with the data as new fixtures are ever added). Backward-compatible: absent means "production" by default for every existing real record (safe default — the alternative, absent-means-demo, would silently hide real data), and the 8 known fixtures get the one-time addition of `data_classification: "demo"` as part of whatever task eventually implements this. |
| Separate directories (e.g. `data/_fixtures/` outside `data/`) | Viable, but weaker: requires every path-globbing call site (`load_json_files()` and its many callers) to know to skip a second directory tree, and doesn't generalize as cleanly if a future need arises for *partially* fictional content (e.g., a real entity with one fictional attribute for demo purposes) — a field-level classification handles that; a directory-level one cannot. |
| Package-level exclusion (an exclude-list maintained in the Intelligence Package exporter only) | Weakest: reintroduces exactly today's problem (an external list that has to be kept in sync with the data, rather than the data self-describing) at a different layer, and does nothing for any consumer that isn't the exporter (a repository query, a report, an API call would still see fictional data as real). |

**Recommendation, not a decision made in this task:** `data_classification` as an additive optional field is the structurally cleanest fix and should be proposed as a schema addition alongside Part 2's scope fields whenever this gate is actually implemented (Phase 2B or Phase 3, not decided here) — but implementing it now was judged out of scope for Phase 2A, since Phase 2A's mandate is the repository *contract*, and this is a *data-hygiene* fix that doesn't block any repository-interface design decision in this document (every repository/query operation above works identically whether or not fictional records are marked — marking them only changes what a *domain service* chooses to filter, per Section 6.2's option (b), which remains valid and sufficient through Phase 2B).

---

## Part 7 — Proposed Phase 2B code organization

### 7.1 Current structure (verified, not assumed)

```
app/
  main.py            3,428 lines: routes, all helper functions (persistence, query,
                      domain-service, and route-composition logic all interleaved,
                      distinguished today only by comment blocks, not module boundaries)
  templates/*.html    Jinja2 templates, unchanged by this task
  static/*.{css,js}   unchanged by this task
```

Two comment blocks already exist inside `app/main.py`, added deliberately in Phase 1.5B to mark exactly the seam this document formalizes: `# BERRIES DOMAIN PACK PROTOTYPE LOGIC` (variety trait/patent functions) and `# BERRIES LANDSCAPE PROTOTYPE LOGIC` (all `landscape_*` functions). These are not incidental — they are the intended extraction points.

### 7.2 Proposed structure for Phase 2B

```
app/
  main.py             routes only, post-refactor -- imports from the packages below,
                       contains no persistence/query/domain-service logic itself
  repositories/
    base.py           the shared Record Repository protocol (get/list/create/update/delete,
                       Section 3.2), plus the shared error types (Section 5)
    json_backend.py    today's load_json_files()/save_X() functions, adapted to implement
                       the protocol -- the FIRST implementation, not a new one
    entities.py, evidence.py, facts.py, relationships.py, signals.py,
    assessments.py, recommendations.py, strategic_questions.py,
    sources.py, drafts.py
                       one thin module per object type, each just wiring the shared
                       protocol to that object's schema/folder -- not 10 independent
                       designs
  queries/
    entity_graph.py    objects_referencing(), relationships_for_entity(), entity_timeline(),
                       lineage() -- Section 3.3
    strategic_questions.py, search.py, duplicates.py
  services/
    berries/           every DOMAIN-PACK / DOMAIN SERVICE function from Section 3.4,
                       moved here verbatim from its current app/main.py location --
                       this directory's existence and its Berries-only content is itself
                       the concrete Phase 7 test ("does a second domain need only a
                       services/<other-domain>/ sibling, zero core changes?")
  templates/, static/  unchanged
```

**What Phase 2B must NOT do, per this task's own scope guard:** refactor `app/main.py` beyond what's needed to move code into the structure above; touch route URLs, request/response shapes, or template contexts (behavior-preserving refactor only, verified the same way `06-MIGRATION-MAP.md` already specifies: the existing test suite passes with fixture changes allowed but assertion changes not); introduce PostgreSQL; begin Phase 3.

### 7.3 Tiny import-neutral preparation considered for this task, and rejected

This task's own instructions permit "a tiny import-neutral preparation... if absolutely necessary." None was found to be necessary: `app/main.py`'s existing Phase 1.5B comment-block boundaries already mark the extraction points precisely enough for Phase 2B to act on directly, and any actual file-split would itself be exactly the kind of change this task defers ("do not refactor `app/main.py` in this task"). No changes were made to `app/main.py`'s structure in this task.

---

## Part 8 — Repository contract-test strategy

### 8.1 Why these are specified, not written, in this task

Per this task's own instruction: contract tests are created now only if they can be written **against current behavior**, without beginning route migration. No repository interface exists yet in `app/main.py` — Part 3-7 above are a design for Phase 2B to build, not code that exists today. Writing a "contract test suite" against an interface that doesn't exist would mean either (a) writing it against the *planned* interface, which is speculative test-writing for code that doesn't exist (indistinguishable from beginning Phase 2B's implementation, which this task explicitly excludes), or (b) writing it against today's loose functions under a new pytest module without actually introducing the `repositories`/`queries` boundary, which would produce tests Phase 2B would likely restructure anyway rather than reuse. Both are worse than specifying the suite precisely here and having Phase 2B write it alongside the interface it's testing, test-first.

### 8.2 The specification, precise enough for Phase 2B to implement directly

A `RepositoryContractSuite` (or equivalent), parameterized over backend implementation (JSON today, PostgreSQL from Phase 3), asserting the following for **every** record repository from Section 3.2:

1. **Same entity lookup**: `get(existing_id)` returns a record with every field the schema declares present in the source data; `get(nonexistent_id)` returns `None` on both backends, never raises, never returns a partial/empty record.
2. **Same filters**: for a fixed, versioned test dataset (the existing `data/` tree at a pinned commit is sufficient — no new fixture data needs inventing), every `list(filter=...)` call used by a real route in Part 1 (R1, R3, R7, R9-R12) returns the identical *set* of ids on both backends. Order is checked separately (below) since "same set, different order" and "different set" are different failure classes worth distinguishing in a failing test's message.
3. **Same reverse references**: every query-service operation in Section 3.3 (`objects_referencing`, `relationships_for_entity`, `evidence_for_strategic_question`) returns the identical result for a fixed set of real entity/record ids already present in `data/` (e.g., `company-costa-group-holdings`, which Part 1.4 and the Phase 1.5 visual review already established as a rich, well-linked test subject touched by Signal + Assessment + Recommendation).
4. **Same ordering**: every `list()`/query-service call with a documented sort (Part 1's "Sort" column) produces the identical *sequence*, not just the identical set, on both backends — this specifically catches a real, easy-to-introduce Postgres-migration bug class (a `list()` that's correct in content but relies on JSON-file directory-listing order rather than an explicit `ORDER BY`, which SQL will not reproduce by accident).
5. **Same published/draft (review-state) behavior**: `list(status="published")` and any future unified draft/in-review/published filter (Part 5's "Draft/unpublished filtering" row) return identical results whether the JSON backend's draft data lives in `inbox/` or the future Postgres backend's lives in a `review_state` column — this is the concrete test that Part 5's "repository layer should expose one filter concept" requirement was actually satisfied, not just designed.
6. **Same landscape/domain-service inputs**: every domain-service function (Section 3.4) run against the identical record-repository backend produces identical output — since domain services are specified (Section 3.1) to contain no storage-specific logic at all, this test's real purpose is to catch a violation of that boundary (a domain service that accidentally imports a JSON-specific helper directly instead of going through the repository interface), not to test storage parity a second time.
7. **Same lineage traversal**: `lineage(recommendation_id)` for `recommendation-treat-costa-driscolls-as-structurally-linked` (Phase 1.5A's real, existing Recommendation) returns the identical `Recommendation → Assessment → Facts → Evidence` chain on both backends, including counterevidence.
8. **Same error semantics**: every condition in Part 5's table produces the same *class* of outcome (raises vs. returns `None`/`[]` vs. returns a reportable-but-non-blocking result) on both backends — the exact exception type may differ (a Postgres backend may raise a driver-specific integrity error where the JSON backend raises a Python `FileExistsError`-equivalent for the duplicate-id case), but the contract test asserts the *repository-level* exception type from Section 5's design, requiring each backend to translate its native errors into that shared vocabulary rather than leaking backend-specific exceptions to callers.

### 8.3 What Phase 2B delivers against this spec

Phase 2B's own acceptance criteria (already stated in `07-IMPLEMENTATION-ROADMAP.md` Phase 2, unrevised by this task except where noted in the roadmap update below) should include: the contract suite above exists and passes against the JSON backend (the only backend that exists through Phase 2B); a second, even trivial in-memory backend implementation (already planned in `07-IMPLEMENTATION-ROADMAP.md`) also passes it, proving the seam is real; Phase 3 then adds a PostgreSQL backend and re-runs the identical, unmodified suite.

---

## Summary — acceptance criteria cross-check

1. Every real Phase 1.5 retrieval pattern is documented — **23 patterns** (R1-R18, W1-W6), verified against `app/main.py`, not the findings doc alone. ✅
2. Each pattern is classified Core vs. Domain-specific — every row in Parts 1.1/1.2/1.3 carries an explicit classification, several as documented hybrids rather than forced into one bucket. ✅
3. Explicit analytical scope semantics are resolved — Part 2, D-012. ✅
4. Legacy/backward-compatible scope behavior is defined — Part 2.4. ✅
5. Repository/query boundaries are specified — Part 3. ✅
6. Presentation logic is explicitly excluded from repositories — Part 4. ✅
7. Shared backend contract-test requirements are defined — Part 8 (specified precisely; not implemented, per this task's own conditional instruction). ✅
8. Phase 2B has bounded implementation tasks — Part 7.2's structure plus the contract suite in Part 8.2 are concrete enough to scope real backlog items from (see `10-BACKLOG.md` update). ✅
9. No PostgreSQL implementation has begun — confirmed; this document contains no PostgreSQL code, connection logic, or schema DDL. ✅
10. Runtime application behavior is unchanged — confirmed; the only non-documentation change in this task is two additive, optional JSON Schema fields (Part 2), verified not to alter validation results for any existing live record. ✅

---

## Part 9 — Phase 2B.1 implementation findings (added 2026-08-14)

**Status:** appended after Phase 2B.1 (`app/repositories/`, `app/repositories/json/`, the contract-test suite) was actually built and proven — see `PROJECT-STATUS.md` for that task's own summary and commit. This section records what implementation confirmed or refined; it does **not** redesign anything Parts 1-8 above already specified. Every architectural decision in this document held up unchanged through implementation — the additions below are learnings *within* that design, not corrections to it.

### 9.1 Pattern-by-pattern disposition, as actually built

**Satisfied directly by a record repository (Part 3.2), confirmed working:**
R2 (Evidence single-record lookup), R9/R10/R11 (Signal/Assessment/Recommendation get/list), R12 (Sources — see 9.2), R1's base layer (`EvidenceRepository.list(status="published")`, matching `published_evidence()` exactly), W1 (Evidence validate = `update()`), W2's core deletion (Evidence purge = `delete()` — the source-tally/blocked-domain side effects remain domain-service concerns layered above it, not part of the delete itself), W3 (Signal/Assessment/Recommendation create), W4 (every Source mutation — create/toggle/delete/check-now/mark-checked — maps cleanly onto `JsonSourceRepository`'s create/update/delete, confirming Part 3's proposed hidden-collection-rewrite design works exactly as specified), and W6's *first* step in isolation (creating the Evidence record itself is a plain `create()` call; only the *coordination* across Fact/Relationship/Entity needs the Unit of Work).

**Confirmed as Phase 2B.2 query-service work, not repository work (Part 3.3):** R4's reverse Signal/Assessment/Recommendation/Fact/Relationship lookups, R6 (Work Queue's cross-list composition), R7's priority-level filter (a repository can hand back all Evidence, but "priority.reading.level == 'high'" is a nested-field, multi-dimension filter Part 3.2 already scoped out of the repository layer — implementation confirms a plain `list(**filters)` doing top-level exact-match, as built, correctly does *not* reach into this), R8 (Strategic-Question reverse reference), R14 (duplicate-title detection across two record families), R15/R16 (search). None of these needed a repository capability beyond `get`/`list` to be buildable in Phase 2B.2 — confirmed by writing the record-repository layer far enough to see that no query-service function in Part 3.3's table is missing a repository primitive it would need.

**Confirmed as Berries domain-service work (Part 3.4):** R5, R17's every sub-pattern (competitive field, variety/geographic rollups, evidence coverage). Untouched by this task, as scoped.

**Confirmed as Phase 2B.3 transactional-write work, now with a concrete seam to build against:** W6 (review/publish). `app/repositories/unit_of_work.py`'s `JsonUnitOfWork` is built, tested in isolation (`tests/repositories/test_unit_of_work.py`, 6 tests), and *not* wired into `app/main.py` — Phase 2B.3 migrates review/publish onto `uow.evidence.create(...)`/`uow.facts.create(...)`/etc. against an interface that already exists, rather than inventing one under the pressure of an in-flight route migration.

### 9.2 What building it actually taught (refinements, not redesigns)

1. **Entities' nested-folder layout cleanly separates into a read concern and a write concern.** Reading needs no entity-type awareness at all — `Path.rglob("*.json")` over `data/entities/` finds every entity regardless of subfolder, for free, exactly matching `all_entities()`'s existing traversal. Only *placing a new record* needs to know which subfolder (`entity_folder()`'s mapping), so `EntityRepository` overrides exactly one method (`_new_record_path()`) and inherits `get`/`list`/`update`/`delete` unchanged from the shared JSON base — `update()`/`delete()` locate a record's *existing* file wherever it already is and rewrite it there, never relocating it. This is a confirmation of Part 3.2's design, not a new requirement, but Phase 2A's own inventory didn't need to work out *how* a single base class would reconcile a flat contract with a nested backend — now proven, and the pattern (one small `_new_record_path()` override, not a parallel implementation) is the template for the one other object type that might ever need it.
2. **Duplicate-id rejection (Part 5's flagged new behavior) costs a full scan of the relevant folder on every `create()` call.** At current data volume (162 entities, 1,263 evidence, all well under a second even unindexed) this is invisible, and the existing `load_json_files()`-style mtime-signature cache means it's not literally re-reading from disk on repeated calls within one cache-valid window. Worth naming explicitly for Phase 3: a PostgreSQL backend gets this for free from a primary-key constraint; a future JSON-backend performance concern only if record volume grows by an order of magnitude before Phase 3 lands, which `docs/v2/09-RISK-REGISTER.md` has no reason to track as a new risk today (not observed, not likely before Phase 3's own timeline).
3. **Strategic Questions have zero write usage in the live application, not just light usage.** Phase 2A's Part 1.1 (R8) named the read pattern; implementation is what confirmed, by re-reading every route again while building `StrategicQuestionRepository`, that literally no route creates, edits, or removes one — all 9 live records exist only because the Berries Domain Pack seeded them once (Phase 1B). `StrategicQuestionRepository` still inherits `create`/`update`/`delete` from the shared base (uniform mechanics, per Part 3.2's own reasoning), but its class docstring states this more starkly than Part 1's table did, for a Phase 2B.2 author's benefit.
4. **Sources have no JSON Schema at all** (`schemas/` contains no `source.schema.json`) — Part 1.1 already classified Sources as DOMAIN-PACK; implementation is what concretely confirmed that `JsonSourceRepository.create()`/`update()` therefore cannot perform schema validation the way every other repository in this package does, as a structural fact rather than an inferred one. Documented in the class itself; no schema was retroactively invented to close this gap, since inventing one was never this task's scope.

None of these four findings change Parts 1-8's architecture, the proposed Phase 2B.2/2B.3 scope, or D-012. They are the kind of detail a design pass reasonably cannot see until the code exists, recorded here so Phase 2B.2 doesn't have to rediscover them.

---

## Part 10 — Phase 2B.2 implementation findings (added 2026-08-14)

**Status:** appended after Phase 2B.2 (`app/queries/`, `app/services/berries/`, `app/composition.py`, and the read-path migration of `app/main.py`) was built and proven — see `PROJECT-STATUS.md` for that task's summary and commit. Read this alongside Part 9; together they are the as-built record of everything Parts 1-8 proposed. No route was rewritten from scratch — every migrated function keeps its exact `app/main.py` name and signature, its internals now delegating to a query service, a Berries domain service, or a record repository (`app/composition.get_repositories()`/`get_query_services()`/`get_domain_services()`, cached per `(data_dir, schemas_dir)` so `tests/test_build_static.py`'s `DATA_DIR` monkeypatching stays correctly isolated).

### 10.1 Final R1-R18 mapping

Collapsed into 7 query services (not 18, not 1), per Part 3.3's own proposal: `ReferenceQueryService`, `EntityIntelligenceQueryService`, `LineageQueryService`, `TimelineQueryService`, `ScopeQueryService`, `CoverageQueryService`, `SearchQueryService` (all in `app/queries/`), plus two Berries domain services (`BerriesLandscapeService`, `BerriesVarietyService` in `app/services/berries/`).

| Pattern | Repository ops used | Query-service method | Domain-service participation | Current `app/main.py` caller |
|---|---|---|---|---|
| R1 Newsfeed | `evidence.list()` | — (`filter_evidence()`/`text_matches()` stay pure, unchanged) | none | `home()`, `all_evidence()`/`published_evidence()` |
| R2 Evidence detail | `evidence.list()`, `facts.list()`, `relationships.list()` | `ReferenceQueryService.facts_for_evidence()`, `.relationships_for_evidence()` | none | `evidence_detail()` |
| R3 Entity list | `entities.list()` | — (`filter_entities()` stays pure) | `entity_regions()` (moved to `app/services/berries/geography.py`) | `entity_list()` |
| R4 Entity detail (generic) | `evidence.list()`, `facts.list()`, `relationships.list()`, `signals.list()`, `assessments.list()`, `recommendations.list()`, `strategic_questions.list()` | `EntityIntelligenceQueryService` (`facts_for_entity`, `signals_for_entity`, `assessments_for_entity`, `recommendations_for_entity`, `strategic_questions_for_entity`, `evidence_for_entity`), `TimelineQueryService.entity_activity()` | `entity_regions()` (geography) | `entity_detail()` |
| R5 Entity detail — variety addendum | `entities.list()` | — | `BerriesVarietyService` (`variety_trait_profile`, `variety_patent_link`) | `entity_synthesis_context()` |
| R6 Work Queue | `evidence.list()`, `signals.list()`, `entities.list()` | none (stays UI composition, per Part 3.5) | none | `work_queue()` |
| R7 Priority queue | `evidence.list()` | — (`queue_items()` stays pure, unchanged) | none | `queue_view()` |
| R8 Strategic Question list/detail | `strategic_questions.list()`, `evidence.list()` | `ReferenceQueryService.evidence_for_strategic_question()` | none | `strategic_question_detail()` |
| R9 Signal list/detail | `signals.list()`, `evidence.list()`, `facts.list()`, `entities.list()`, `strategic_questions.list()` | `LineageQueryService` (`resolve_linked_evidence/facts/entities/strategic_questions`) | none | `signal_detail()` |
| R10 Assessment list/detail | same as R9 + `assessments.list()` | `LineageQueryService` (same methods; counterevidence resolved via `resolve_linked_facts()`, preserving the existing fact-only behavior) | none | `assessment_detail()` |
| R11 Recommendation list/detail | `recommendations.list()`, `assessments.list()`, `signals.list()`, `facts.list()`, `evidence.list()`, `entities.list()`, `strategic_questions.list()` | `LineageQueryService` (adds `resolve_linked_assessments/signals`) — this is the genuine multi-hop reuse case (3 real call sites: R9/R10/R11 share the same resolver methods) | none | `recommendation_detail()` |
| R12 Sources | `sources.list()`, `entities.list()` | none (`filter_sources()`/`group_sources()` stay pure) | domain-pack, unmigrated (Sources predate a `SourcesQueryService`; not needed — see 10.3) | `sources_page_context()` |
| R13 Review Queue | `evidence.list()` (unvalidated), Drafts (unmigrated — see 10.3) | none | none | `review_queue()` |
| R14 Duplicate detection | `evidence.list()` (via migrated `all_evidence()`) + Drafts (unmigrated) | none (see 10.3 — kept split, not forced into one service) | none | `find_possible_duplicates()` |
| R15 Search — live app | `evidence.list(status="published")`, `entities.list()` | `SearchQueryService` (thin pass-through; ranking/typo logic stays in `text_matches()`/`filter_evidence()`, unchanged per Part 7's explicit "do not build a new search engine") | none | `api_search()`, `home()` |
| R16 Search — static build | n/a (Pagefind indexes the already-built static HTML) | not touched — out of scope, unchanged | none | `scripts/build_static.py` |
| R17 Blueberry Landscape | `evidence.list()`, `entities.list()`, `relationships.list()`, `signals.list()`, `assessments.list()`, `recommendations.list()`, `facts.list()`, `strategic_questions.list()` | `ScopeQueryService.records_by_entity_intersection()` (replaces the inline Assessment/Recommendation derivation), `CoverageQueryService` (evidence/fact/relationship/SQ breakdowns) | `BerriesLandscapeService` (every `landscape_*` sub-pattern from Part 1.2's table, moved verbatim) | `landscape_context()` (thin wrapper: calls `get_domain_services(DATA_DIR).landscape.landscape_context()`, adds `berry_label`) |
| R18 Static build | same repository ops as the live routes it mirrors | same query services as the live routes it mirrors | same domain services | `scripts/build_static.py` (imports `entity_activity`, `entity_regions`, `landscape_context`, etc. from `app.main`, unchanged) |

### 10.2 Boundary-discipline decisions made during implementation

- **`ScopeQueryService`** implements D-012's explicit-scope/derived-scope distinction generically (`explicit_scope()` unifies Signal's `berry_ids` and Assessment/Recommendation's `market_ids` under one accessor; `records_by_entity_intersection()` is the legacy/default derived rule every pre-D-012 caller already used; `scope_disagreements()` flags a record whose explicit scope and entity-derived scope point in different directions, per D-012's "must be surfaced, never silently resolved" requirement). Not yet wired into any live route filter — Landscape's Assessment/Recommendation branch uses the derived-intersection method only, preserving its exact current behavior; a route that filters by explicit scope is future Phase 2B.3+ work, not invented here.
- **`LineageQueryService`** was scoped down from an earlier "one `recommendation_lineage()` method" design once the actual `recommendation_detail()` route was re-read in full: a Recommendation stores its own `assessment_ids`/`signal_ids`/`fact_ids`/`evidence_ids` directly (no multi-hop *traversal* is actually needed — Signal/Assessment/Recommendation detail routes are structurally identical single-hop id-resolution, not a chain to be walked). The service instead provides one resolver method per target type, reused identically across all three routes — genuine reuse (3 real call sites), not a synthesis method invented for migration convenience.
- **`find_possible_duplicates()`** (R14) still queries Evidence (now repository-backed, via the migrated `all_evidence()`) and Drafts (`list_drafts()`, unmigrated) directly in `app/main.py`, rather than being wrapped in a query-service method — Drafts have no repository (Phase 2B.1 built 9 named repositories, Draft was explicitly not one of them), so a `duplicates_of()` query service would need to either reach into `INBOX_DIR` directly (violating the query-service layer's own "never touch storage directly" rule) or accept a pre-loaded Draft list as a parameter, which is exactly what today's plain function already does. Documented as a deliberate partial/mixed migration, not an oversight.
- **Geography** (`REGIONS`, `REGION_LOOKUP`, `geography_region()`, `evidence_regions()`, `entity_regions()`, plus `berry_label()`) moved to `app/services/berries/geography.py` rather than a Core query service, per Part 3.4's own note that the region-*table* is Berries-authored even though the bucket-then-aggregate *mechanism* is Core-shaped — consistent with the "hybrid, flagged" classification Part 1.2 already gave it.

### 10.3 Deliberately not migrated in Phase 2B.2 — and why that's correct, not incomplete

- **Sources (R12)** stay on `load_sources()`/`filter_sources()`/`group_sources()`, all pure or repository-backed already (`load_sources()` now delegates to `JsonSourceRepository.list()`); no dedicated `SourcesQueryService` was built because nothing about Source filtering spans object types the way R4/R11 do — it would be a query service with no cross-object question to answer, exactly the "don't add a service merely to have one" discipline this task's brief warns against.
- **Drafts (R6, R13, R14)** stay entirely on `list_drafts()`/`get_draft()`, unmigrated, because Phase 2B.1 did not build a `DraftRepository` (drafts live in `inbox/`, not `data/`, and are explicitly out of the 9-repository scope that phase defined). This is the one category of "direct filesystem access remaining in a read path" this task's acceptance criteria asks to be explicitly justified — justified here: migrating Drafts onto a repository is Phase 2B.3-or-later scope (`06-MIGRATION-MAP.md` already flags the `inbox/` vs. `data/evidence/` split for eventual unification behind `review_state: draft`), not something to improvise as a side effect of a read-path task.

### 10.4 Part 11 — Write call-site audit (W1-W6), unchanged this task

No write route or workflow was migrated. Re-verified against the current `app/main.py` (not assumed from Phase 2A's Part 1.3, which was written before Phase 2B.1's repository layer existed):

| # | Workflow | Objects written | Verified this task |
|---|---|---|---|
| W1 | Evidence validate (`POST /evidence/{id}/validate`) | Evidence (update) | unchanged; still direct field mutation + `save_evidence()` |
| W2 | Evidence purge (`POST /evidence/{id}/purge`) | Evidence (delete) + Source (tally) + blocklist | unchanged; still `path.unlink()` + conditional side effects |
| W3 | Signal / Assessment / Recommendation create | one new record each | unchanged; still `get_validator(...).iter_errors()` → `save_X()` |
| W4 | Source create/toggle/delete/check-now/mark-checked | Source (whole-collection rewrite) | unchanged; still `save_sources()` |
| W5 | Intake draft create (`POST /intake`) | one new Evidence draft, in `inbox/` | unchanged; still `save_draft()` + optional `save_attachment()` |
| W6 | Review/publish (`POST /review/{id}/publish`) | **one Evidence, up to `NUM_FACT_ROWS` Facts, up to `NUM_RELATIONSHIP_ROWS` Relationships, and every Entity named in the form — both newly-created *and pre-existing, matched-by-name* ones** | re-read in full this task — see below; refines Part 9's characterization |

**W6's exact mutation sequence, as verified by re-reading `review_publish()` (`app/main.py`) line by line this task:**

1. For every typed company/variety/retailer/geography **name**, match against `entity_index()` by `(name.lower(), entity_type)`. A match reuses the existing entity's id; no match generates a new id (`unique_entity_id()`) and stages a brand-new entity dict.
2. Build `fact_ids`/`relationship_ids` for the new Facts/Relationships this publish creates (ids derived from the draft id, always fresh).
3. Build the new Evidence record (id = the draft id, always fresh).
4. Schema-validate the Evidence record; abort with no writes if invalid.
5. **For every entity named in the form — `for entity_id in set(entity_ids)` — regardless of whether it was matched or newly created:** append this Evidence's id to `entity["evidence_ids"]`, append the new fact ids to `entity["fact_ids"]`, append any relationship ids touching it to `entity["relationship_ids"]`, then `save_entity(entity)`.
6. `save_fact()` for each new Fact.
7. `save_relationship()` for each new Relationship.
8. `save_evidence()` for the new Evidence record (after resolving attachment moves).
9. `delete_draft()` — removes the source draft file from `inbox/`, a different storage location entirely.

**The refinement this re-read surfaces:** Part 9 (`app/repositories/unit_of_work.py`'s own docstring, written during Phase 2B.1) states "Phase 2B.1's only real multi-repository write pattern (review/publish) is exclusively a sequence of `create()` calls." Step 5 above is **not** exclusively create — when an entity name matches an *existing* entity (the common case for any evidence about a company/variety/geography the system already knows, which is most evidence after the first mention), `save_entity()` performs a genuine **update** of a previously-published record's `evidence_ids`/`fact_ids`/`relationship_ids` arrays, in the same logical operation as the Fact/Relationship/Evidence creates.

**Why this matters for Phase 2B.3, and why it is not fixed here:** `JsonUnitOfWork` (unchanged this task, per this task's explicit instruction not to modify it without a correctness bug affecting *current, used* behavior — the Unit of Work is not wired into any route yet, so nothing live is affected) only compensates `create()` calls on rollback; it explicitly does not compensate `update()`. If Phase 2B.3 migrates `review_publish()` onto the Unit of Work by wrapping *every* entity save in `uow.entities.create(...)`, it will incorrectly raise `DuplicateRecord` for every matched-existing-entity case (the common case). The correct migration distinguishes the two cases explicitly — `uow.entities.create(entity)` for newly-created entities (compensable as today's seam already handles), `uow.entities.update(entity_id, entity)` for matched-existing entities (not compensable by the current seam; a mid-operation failure after an existing entity's linkage arrays are updated, but before the Fact/Relationship/Evidence it now references are actually created, would leave that entity referencing records that don't exist). This is a real, previously-undocumented gap between the current `JsonUnitOfWork` and W6's actual behavior — surfaced here, per this task's Part 11 instruction, as the explicit "required Phase 2B.3 change" rather than silently worked around: Phase 2B.3 must either (a) snapshot each matched entity's prior linkage-array state so `update()` calls can be compensated too, or (b) accept and document that only the create-heavy path (new entities, Facts, Relationships, Evidence) gets rollback protection, and a failure after an existing-entity update is a narrower, explicitly-accepted residual risk. Neither option is chosen here — that choice belongs to Phase 2B.3.

No PostgreSQL work began. No write route was touched. `JsonUnitOfWork` is unmodified.

---

## Part 11 — Phase 2B.3 implementation findings (added 2026-08-14)

BL-033 is complete. Every persisted Core-object write in `app/main.py` now crosses the repository boundary. Evidence validate/purge use repository update/delete; Signal, Assessment, Recommendation, auto-captured Evidence, Entity, Fact, and Relationship saves delegate to their repositories; Source's legacy whole-list callers are bridged through `JsonSourceRepository` CRUD. Strategic Questions have no live write route. Landscape and search were already migrated in Phase 2B.2.

Review/publish now constructs one `JsonUnitOfWork` over Entity, Fact, Relationship, and Evidence repositories. New Entities and all new Facts/Relationships/Evidence use `create()`. Matched existing Entities use `update()`. The JSON UoW now snapshots each updated record's prior value and restores it in reverse operation order if a later write fails, resolving Part 10.4's documented gap rather than accepting dangling linkage arrays. Inbox draft deletion is the final operation inside the UoW: success commits the structured records with the draft gone; deletion failure compensates the structured records and leaves the draft safely retryable.

Direct filesystem writes remain only for storage surfaces that have no Phase 2 repository: inbox drafts, draft/published attachments, and the blocked-domain configuration list. They are deliberately not converted into improvised repositories in BL-033. Attachment movement still precedes the JSON UoW and therefore retains the flat-file backend's documented best-effort (not fully atomic) character; PostgreSQL work remains untouched.

Acceptance verification added explicit failure injection for every publish boundary: after new-Entity creation, after existing-Entity update, after Fact creation, after Relationship creation, and after Evidence creation via draft-deletion failure. It also proves the final case rolls all structured records back, leaves the draft present, and permits one clean retry without duplicate records or linkage ids.
