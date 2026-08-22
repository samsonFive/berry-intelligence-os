# Intelligence OS — Domain Model (V2)

**Status:** Reviewed and accepted, 2026-08-13, including resolution of the two open decisions (D-010, D-011 — see `08-DECISION-LOG.md`) this document originally flagged as unresolved.

This extends, and in two places (Assessment, Recommendation) finally *implements*, the domain model V1's own `docs/03-information-architecture/DOMAIN-MODEL.md` specified from the project's first commit but never fully built. That document's lineage requirement is the organizing idea for everything below:

> Recommendation → Assessment/Signal → Facts → Evidence → Source. Every published object must expose this chain.

V1 built `Facts → Evidence → Source`. `Assessment` and `Signal` existed as names (`Signal` got a schema; `Assessment` never did) and `Recommendation` never existed as an object at all — its role was informally filled by the four `priority` dimensions bolted directly onto `Evidence` (`CURRENT-STATE-AUDIT.md` Section 5/14). V2 completes the chain.

## Summary table

| Object | Core or Domain-specific | New in V2? |
|---|---|---|
| Organization | Core | New |
| User | Core | New |
| Workspace | Core | New |
| Domain | Core (the *concept* is core; a *specific* Domain's contents are Domain-Pack-defined) | New |
| Entity | Core (generic container) | Adapted (V1 has this) |
| Entity Type | Domain-specific (declared by a Domain Pack) | Adapted (V1 hard-codes these; V2 makes them declarative) |
| Evidence | Core | Adapted (V1 has this, well-developed) |
| Source | Core | Adapted (V1 has an informal version; formalized as its own object here) |
| Fact | Core | Adapted (V1 has this, well-developed) |
| Claim | Core | Adapted (in V1 today, `claim` is a value of `fact.classification`; see below for whether V2 keeps it that way) |
| Relationship | Core (predicates are Domain-specific) | Adapted (V1 has this) |
| Assessment | Core | **New** (named in V1's original domain model, never implemented) |
| Signal | Core | Adapted (V1 has a schema; 0 live records — `CURRENT-STATE-AUDIT.md` Section 6) |
| Recommendation | Core | **New** (named in V1's original domain model, never implemented; V1's `priority` dimensions are the closest analog and are folded into this object per the decision below) |
| Strategic Question | Core | Adapted (V1 has this) |
| Collector | Core | New (V1's collection logic is hard-coded, not an object — `02-TARGET-ARCHITECTURE.md` Section 7) |
| Collection Job | Core | New |
| AI Job | Core | New |
| Intelligence Product | Core | New name for a concept `DOMAIN-MODEL.md` named but V1 never built as a distinct object (closest V1 analog: a filtered list page, not a stored, assembled object) |
| Report | Core | New |
| Export Package | Core | New (formalizes `05-INTELLIGENCE-PACKAGE-SPEC.md` as a first-class object, not just a file format) |

---

## Organization

- **Purpose**: the top-level tenant boundary. Everything else in the system belongs to exactly one Organization.
- **Ownership/scope**: root of the ownership tree; owns Workspaces.
- **Important relationships**: has many Workspaces; has many Users (via membership, with a role).
- **Provenance requirements**: none (an Organization is administrative metadata, not evidence-derived).
- **Review state**: n/a.
- **Core or domain-specific**: Core.
- **V1 equivalent**: none — V1 has exactly one implicit organization (the operator running the local app).

## User

- **Purpose**: a real person who can authenticate, author, review, and approve.
- **Ownership/scope**: belongs to one or more Organizations (with a role per membership).
- **Important relationships**: is the `reviewer` on Facts, Signals, Recommendations; is the actor on Collection Jobs and AI Job approvals; belongs to Workspaces via Organization membership (or, if finer-grained access is needed later, directly).
- **Provenance requirements**: none directly, but every provenance-bearing object's `reviewer`/`approved_by` field should reference a real User once this exists, replacing V1's free-text `reviewer` string (verified in V1: `fact.reviewer` is an unstructured string like `"research-agent/blueberry-public-pilot-2026-08-03"` — see `06-MIGRATION-MAP.md` for how that free text becomes a proper reference).
- **Review state**: n/a.
- **Core or domain-specific**: Core.
- **V1 equivalent**: none — no authentication exists in V1.

## Workspace

- **Purpose**: a working context within an Organization — the unit most users actually operate inside day to day. Where a Domain gets activated for real use.
- **Ownership/scope**: belongs to one Organization; scopes nearly every other core object (Entity, Evidence, Fact, Claim, Relationship, Assessment, Signal, Recommendation, Strategic Question, Intelligence Product, Report, Export Package all belong to exactly one Workspace).
- **Important relationships**: has one or more active Domains; has member Users.
- **Provenance requirements**: none directly.
- **Review state**: n/a.
- **Core or domain-specific**: Core.
- **V1 equivalent**: none — V1's single dataset is the implicit, only workspace.

## Domain

- **Purpose**: the activation of a Domain Pack (`04-DOMAIN-PACK-SPEC.md`) within a Workspace — "we are now watching the [X] market using the [X] Domain Pack's entity types, predicates, taxonomies, and templates."
- **Ownership/scope**: belongs to a Workspace (a Workspace could in principle activate more than one Domain, though V2's first real deployment activates exactly one — Berries).
- **Important relationships**: references a Domain Pack (by id/version); every Entity Type, Relationship predicate, Strategic Question template, Collector template, and Report template available in a Workspace traces back to its active Domain(s).
- **Provenance requirements**: none directly — the Domain Pack itself is versioned, so a Domain's behavior at any point in time is reproducible.
- **Review state**: n/a.
- **Core or domain-specific**: the *concept* is core infrastructure; the *content* of any given Domain is entirely Domain-Pack-defined (Section below, and `04-DOMAIN-PACK-SPEC.md`).
- **V1 equivalent**: none as an explicit object — V1 *is* the Berry domain, inseparably.

## Entity

- **Purpose**: a stable, named thing the domain cares about — unchanged in spirit from V1's `entity.schema.json` (`"A stable object such as a company, variety, source, berry, brand, breeding program, geography, retailer, trait, person, patent, or product"`, `DOMAIN-MODEL.md`).
- **Ownership/scope**: belongs to a Workspace; has an Entity Type declared by that Workspace's active Domain.
- **Important relationships**: linked from Evidence, Facts, Relationships (as subject or object), Signals, Recommendations, Strategic Questions; has back-references to all of these (V1 pattern, kept — but see provenance requirement below for the integrity gap this creates).
- **Provenance requirements**: none for the Entity record itself (an entity's *existence* isn't "evidence," though every *claim about* an entity must trace to evidence) — but V2 should close the referential-integrity gap `CURRENT-STATE-AUDIT.md` flagged (Section 10): back-references must be verifiably real, not just conventionally maintained, once a real database with foreign keys exists (Phase 3).
- **Review state**: `active`, `inactive`, `historical`, `unverified` — kept unchanged from V1's schema (`entity.schema.json`), a genuinely well-realized part of the model (`CURRENT-STATE-AUDIT.md` Section 7 calls out `unverified` rendering as a positive example).
- **Core or domain-specific**: the container is Core; its `entity_type` value and the meaning of that type is Domain-specific.
- **V1 equivalent**: `schemas/entity.schema.json`, unchanged in shape.

## Entity Type

- **Purpose**: the domain-specific vocabulary of *what kinds* of Entity exist — company, variety, geography, trait, etc. for Berries; something entirely different for another domain.
- **Ownership/scope**: declared by a Domain Pack (Section 4, `04-DOMAIN-PACK-SPEC.md`), activated into a Workspace via its Domain.
- **Important relationships**: every Entity has exactly one Entity Type; Entity Types can declare which Relationship predicates and Traits/Attributes are meaningful for them.
- **Provenance requirements**: none — this is schema/configuration, not evidence-derived data.
- **Review state**: n/a (versioned as part of the Domain Pack, not individually reviewed).
- **Core or domain-specific**: **Domain-specific by definition** — this is exactly the boundary Section 5 of `01-PRODUCT-VISION.md` draws. The mechanism for declaring an Entity Type is core; the actual list of types (company/variety/... vs. whatever a different industry needs) is not.
- **V1 equivalent**: hard-coded implicitly — V1 has no `entity_type` registry; any string is accepted by the schema, and the *actual* 9 types in use (`CURRENT-STATE-AUDIT.md` Section 6) exist only because that's what the Berry data happens to contain plus a few hard-coded constants in `app/main.py` (`SOURCE_ENTITY_TYPES`, `BERRIES`).

## Evidence

- **Purpose**: unchanged from V1 — the root object (ADR-0002). Every article, note, report, observation, or submission enters as Evidence, preserving what was received and where it came from.
- **Ownership/scope**: belongs to a Workspace.
- **Important relationships**: references a Source; links to Entities, Facts, Claims (see below), Relationships, Strategic Questions it supports; is the base of the lineage chain everything else stands on.
- **Provenance requirements**: itself the unit of provenance — must preserve original source/submission, capture date, source type, submitter, review state, and original attachment/URL where available (`PRD.md` Section 9, kept unchanged).
- **Review state**: V1 conflates two genuinely different concepts here (`CURRENT-STATE-AUDIT.md` Section 5/6) — `status` (draft/in_review/published) and `validated` (a boolean meaningful only for auto-captured records). **V2 proposes unifying these into one review-state enum** applicable to every Evidence record regardless of how it arrived: `draft → in_review → published`, with `published` requiring the same human-review gate whether the evidence came from manual intake, an import package, or a Collector. See `06-MIGRATION-MAP.md` for how the 1,263 existing records map onto this.
- **Core or domain-specific**: Core.
- **V1 equivalent**: `schemas/evidence.schema.json`, largely preserved; adds the `event_date`/`source_tier`/`information_confidence` fields the blueberry import package's own `proposed-schema-enhancements.md` (P-4) already identified as missing.

## Source

- **Purpose**: formalized as its own object in V2. In V1, "source" is really three different, loosely-connected things: `evidence.source_name`/`source_url` (free text per record), the monitored-source registry (`data/configuration/sources.json`, used only by Collectors), and `source_type` (a string on Evidence). V2 makes Source a real, referenceable object.
- **Ownership/scope**: belongs to a Workspace; a Source can be either a monitored/collected source (has a Collector configuration) or a one-off manually-cited source (an analyst typed in a URL during intake) — both are the same object type, differing only in whether a Collector is attached.
- **Important relationships**: referenced by Evidence (many Evidence records can share one Source, e.g. the same publication cited repeatedly); a monitored Source is targeted by zero or more Collection Jobs.
- **Provenance requirements**: a Source's own reliability tier (V1's `tier-1`/`tier-2`/`tier-3`, currently just a string inside `evidence.tags` — `CURRENT-STATE-AUDIT.md` Section 7) becomes a first-class field on Source itself, inherited by default onto Evidence collected from it, per the blueberry import package's own proposal (P-4, `source_tier` enum).
- **Review state**: `active`/`paused`/`retired` for monitored sources (mirrors V1's source `enabled` toggle, `/sources` page).
- **Core or domain-specific**: Core object; *which* sources matter is Domain-specific (a Domain Pack ships a starter source list — `04-DOMAIN-PACK-SPEC.md`).
- **V1 equivalent**: `data/configuration/sources.json` (registry) plus free-text fields on `evidence.schema.json` — unified here.

## Fact

- **Purpose**: unchanged from V1 — a concise statement supported by evidence.
- **Ownership/scope**: belongs to a Workspace.
- **Important relationships**: requires ≥1 Evidence; may link Entities; may be superseded by another Fact (`supersedes` field, kept from V1).
- **Provenance requirements**: `evidence_ids` (≥1), `confidence`, `reviewer`, `created_at`, `status` — all kept unchanged from V1's `fact.schema.json`, which the audit confirms is one of the strongest-realized parts of the current model.
- **Review state**: `active`, `disputed`, `superseded`, `withdrawn` — kept unchanged. **V2 requirement, not present in V1**: `disputed` status must carry real visual/API weight, not the plain-text-only rendering `CURRENT-STATE-AUDIT.md` Section 7 found (a UI requirement, tracked in `10-BACKLOG.md`, not a schema change).
- **Core or domain-specific**: Core.
- **V1 equivalent**: `schemas/fact.schema.json`, kept.

## Claim

- **Purpose**: an assertion that has not been independently verified — distinct from a Fact by exactly that property (`PRD.md` Section 9: "Competitor claims must be labeled as claims unless independently verified").
- **Ownership/scope**: as Fact.
- **Important relationships**: as Fact.
- **Provenance requirements**: as Fact.
- **Review state**: as Fact.
- **Core or domain-specific**: Core.
- **Decision (`08-DECISION-LOG.md` D-010, ACCEPTED 2026-08-13)**: Claim remains a subtype/classification of Fact, not a separate schema — `fact.classification = "fact" | "claim"`, sharing every other field with Fact. This is simple, already validated at scale (132 fact / 54 claim records, `CURRENT-STATE-AUDIT.md` Section 6), and the classification enum is the *entire* mechanism that makes the FACT/CLAIM distinction real rather than just a naming convention. **No separate Claim persistence schema is introduced in V2** unless a future concrete workflow (a distinct required-field set, a distinct verification lifecycle that promotes a Claim into a Fact) demonstrates the need — at which point that becomes a new, separately-numbered decision, not a reopening of D-010.

## Relationship

- **Purpose**: unchanged — an explicit, evidenced connection between two Entities.
- **Ownership/scope**: belongs to a Workspace; subject/object are Entities within that Workspace.
- **Important relationships**: `subject_id` → Entity, `object_id` → Entity, requires ≥1 Evidence.
- **Provenance requirements**: `evidence_ids` (≥1) — kept. **New in V2, per the blueberry import package's own proposal (P-3)**: a real `confidence` field (low/medium/high), closing the gap `CURRENT-STATE-AUDIT.md` Section 5/7 found (V1 has no such field; where confidence is expressed today it's free text buried in `notes`).
- **Review state**: `active`, `historical`, `disputed` — kept. Same disputed-visibility requirement as Fact (currently unrendered at all for relationships per the audit).
- **Core or domain-specific**: the object type is Core; the `predicate` vocabulary is Domain-specific (`04-DOMAIN-PACK-SPEC.md`) — V1 hard-codes a 10-value enum in `relationship.schema.json`; V2 makes the predicate list something a Domain Pack contributes, with the blueberry import package's own proposed additions (`exhibits_claimed_trait`, `protects`, `markets`, `offers`, `administers_license_for`, `subsidiary_of` — P-2) as the Berries pack's starting extension.
- **V1 equivalent**: `schemas/relationship.schema.json`, extended.

## Assessment

- **Purpose**: **new in V2, though not a new idea** — V1's own `DOMAIN-MODEL.md` defines it as "an analyst interpretation of one or more facts." This is the first link V1's lineage chain never got a schema for.
- **Ownership/scope**: belongs to a Workspace.
- **Important relationships**: requires ≥1 Fact (an Assessment interprets facts, it doesn't stand alone — this is what keeps it distinct from a Claim, which interprets nothing, and a Signal, which requires a *pattern* across multiple evidence, not one analyst's read of existing facts); may reference Entities and Strategic Questions it bears on.
- **Provenance requirements**: `fact_ids` (≥1), `confidence`, `reviewer`, `created_at` — mirroring Fact's provenance discipline exactly, since an Assessment is exactly as untrustworthy as its unexplained-reasoning cousin (a bare opinion) unless it's this well-anchored.
- **Review state**: proposed by a human or by AI (per Core Design Principle #4, AI-proposed Assessments carry an explicit `ai_proposed: true` / `reviewed_by` pair before counting as published) → `active` / `superseded` / `withdrawn`.
- **Core or domain-specific**: Core.
- **V1 equivalent**: none. The blueberry import package's own `proposed-schema-enhancements.md` (P-8) explicitly flagged this as "the domain model declares [it]... and that chain is currently unbuildable," recommending exactly this deferral-with-a-deliberate-decision, which V2 is now making: build it, don't retire it.

## Signal

- **Purpose**: unchanged — a monitored pattern supported by multiple evidence or fact records (distinguishing it from Assessment, which can rest on a single fact's interpretation).
- **Ownership/scope**: belongs to a Workspace.
- **Important relationships**: requires ≥2 Evidence (V1's schema doesn't currently enforce this `minItems`, though the blueberry import package's *own proposed* signal schema did, P-7 — V2 should enforce it, since a "signal" built on one data point is really just a Claim); may reference Facts, Entities, Strategic Questions.
- **Provenance requirements**: `evidence_ids` (≥2, enforced), `direction`, `strength`, `confidence`, `first_seen`, `last_updated`, `reviewer` — kept from V1's schema.
- **Review state**: V1's enum today is unclear in practice (0 live records to observe) — V2 adopts the richer state machine the blueberry import package's own proposal specified: `proposed → monitoring → confirmed / refuted → retired`, since "proposed but never confirmed or refuted" is a real, distinct state worth tracking (the 6 unapplied signals from that package are all sitting in exactly this state today, unable to progress because the field to track it doesn't cleanly exist yet).
- **Core or domain-specific**: Core.
- **V1 equivalent**: `schemas/signal.schema.json`, refined; **the 6 unapplied signals in `data/imports/blueberry-public-pilot-2026-08-03/signals/` are a direct, ready-made migration target** — see `06-MIGRATION-MAP.md`.

## Recommendation

- **Purpose**: **new in V2, though — like Assessment — not a new idea.** V1's `DOMAIN-MODEL.md` defines it, in spirit, as "a proposed action." This is the *other* missing link in the lineage chain. **Resolved this review (`08-DECISION-LOG.md` D-011, ACCEPTED)**: Recommendation is a **decision/action** object, answering *"what action or decision is proposed based on accumulated intelligence?"* — a genuinely different question from the one Evidence Priority answers (see below), not a grander version of it.
- **Ownership/scope**: belongs to a Workspace.
- **Important relationships**: requires ≥1 Assessment or Signal (never bare evidence — a Recommendation is downstream of interpretation, per the lineage chain, not a shortcut around it); may reference Entities and Strategic Questions.
- **Provenance requirements**: `assessment_or_signal_ids` (≥1), `action_type`, `rationale`, `reviewer`, `created_at`.
- **Review state**: same AI-proposes/human-approves discipline as Assessment.
- **Core or domain-specific**: the object is Core; the *vocabulary* of `action_type` values is Domain-specific (`04-DOMAIN-PACK-SPEC.md`) — a genuinely different, decision-oriented vocabulary from Evidence Priority's triage dimensions (e.g., candidates for a Berries Domain Pack starter vocabulary: `pursue_licensing_discussion`, `escalate_to_commercial_review`, `monitor_for_confirmation`, `no_action_warranted` — illustrative, not finalized; an actual vocabulary is Phase 1.5/Phase 4 work, informed by the first real Recommendations written in Phase 1.5).
- **Relationship to Evidence Priority — permanent, not a migration-period default (`08-DECISION-LOG.md` D-011, ACCEPTED 2026-08-13)**: Evidence Priority (the four dimensions on `Evidence` — `reading`/`testing`/`commercial_position`/`monitoring`) and Recommendation **coexist permanently**, because they answer different questions at different points in the lineage chain. Evidence Priority is **triage**, attached directly to one Evidence record: *"how urgently, or in what way, should an analyst pay attention to this specific item?"* Recommendation is **decision/action**, downstream of Assessment/Signal/Facts: *"what should we actually do, based on accumulated intelligence?"* A single high-priority evidence item does not imply any Recommendation exists yet — real analytical work (an Assessment or Signal) sits between the two. Because of this, **existing `evidence.priority` values are never mechanically converted into Recommendation records** — see `10-BACKLOG.md`'s BL-052 (a bounded review task, not a conversion sweep) and `06-MIGRATION-MAP.md`'s entry for `evidence.priority`.
- **V1 equivalent**: none as an object. `evidence.priority.{reading,testing,commercial_position,monitoring}` is a related-but-distinct, permanently-retained concept (see above), not a migration source for Recommendation records.

## Strategic Question

- **Purpose**: unchanged — an enduring question that organizes evidence and analysis around a decision need.
- **Ownership/scope**: belongs to a Workspace.
- **Important relationships**: links Evidence (both directions, closing the one-directional gap `CURRENT-STATE-AUDIT.md` Section 7 found in V1's rendering); may link Facts, Assessments, Signals, Recommendations that bear on it.
- **Provenance requirements**: none for the question itself; its *value* comes entirely from what it links.
- **Review state**: `active`, `answered`, `retired` (adopting the blueberry import package's own proposed enum, P-6, which is richer than V1's implemented one).
- **Core or domain-specific**: the object is Core; a *starter set* of questions is Domain-Pack-contributed (`04-DOMAIN-PACK-SPEC.md`, "strategic-question templates").
- **V1 equivalent**: `schemas/strategic-question.schema.json`, kept, enum tightened.

## Collector

- **Purpose**: a configured, pluggable definition of *how* to gather raw material from one kind of source (`02-TARGET-ARCHITECTURE.md` Section 7) — RSS polling, keyword search, and whatever a future Domain Pack or platform update adds.
- **Ownership/scope**: a Collector *type* (the code implementing the interface) is Core or Domain-Pack-contributed; a Collector *configuration* (this specific RSS feed, this specific keyword set) belongs to a Workspace and targets a Source.
- **Important relationships**: attached to a Source; run by Collection Jobs.
- **Provenance requirements**: none directly — a Collector produces raw material that becomes Evidence, which then carries its own provenance.
- **Review state**: `enabled`/`disabled` (mirrors V1's per-source toggle).
- **Core or domain-specific**: the interface/framework is Core; specific collector *implementations* may be Core (RSS, keyword-search, both already proven in V1) or Domain-Pack-contributed (a domain-specific API integration, for example).
- **V1 equivalent**: hard-coded behavior inside `check_source()` in `app/main.py` — not an object at all today.

## Collection Job

- **Purpose**: one execution of a Collector against a Source — "check this feed now," recorded as a first-class, auditable event rather than a fire-and-forget background task.
- **Ownership/scope**: belongs to a Workspace; references a Collector and a Source.
- **Important relationships**: produces zero or more Evidence records (as `draft`, entering the review pipeline exactly like manually-submitted evidence).
- **Provenance requirements**: start/end time, status, error detail if failed, count of items produced — an operational audit trail, not evidence-provenance in the Fact/Assessment sense.
- **Review state**: `queued → running → succeeded / failed / partial`.
- **Core or domain-specific**: Core.
- **V1 equivalent**: none as a stored object — V1's `check_source()` runs and logs to stdout/console only; nothing persists that a given poll happened, beyond its side effects (new Evidence files, updated source tallies).

## AI Job

- **Purpose**: one execution of an AI provider call proposing structure (facts/claims/relationships from evidence), an assessment, a signal candidate, or a recommendation — recorded the same way a Collection Job is, for the same auditability reason, and critically so the human-approval gate (Core Design Principle #4) has something concrete to review against.
- **Ownership/scope**: belongs to a Workspace; references the AI provider used (Section 8, `02-TARGET-ARCHITECTURE.md`) and the object(s) it proposed structure for.
- **Important relationships**: produces proposed Facts/Claims/Relationships/Assessments/Signals/Recommendations, each tagged `ai_proposed: true` until a human reviews them.
- **Provenance requirements**: provider used, prompt/input reference, timestamp, cost (token count or equivalent, for the AI-cost-explosion risk tracked in `09-RISK-REGISTER.md`), reviewer and decision once reviewed.
- **Review state**: `proposed → approved / rejected / partially_approved`.
- **Core or domain-specific**: Core.
- **V1 equivalent**: none — no AI integration exists in V1.

## Intelligence Product

- **Purpose**: kept from `DOMAIN-MODEL.md`'s original definition — "an assembled view such as a berry landscape, competitor profile, variety profile, weekly digest, testing queue, patent landscape, or onboarding workspace." In V2 this becomes the general *category* that both a live in-app view and a generated Report can be an instance of.
- **Ownership/scope**: belongs to a Workspace.
- **Important relationships**: assembled from Entities, Evidence, Facts, Assessments, Signals, Recommendations per a query/template; may be the direct source of a Report or an Export Package.
- **Provenance requirements**: must expose the lineage of everything it assembles (same requirement as any published object).
- **Review state**: n/a for a live/dynamic Intelligence Product (it's always current); a *snapshotted* one (frozen for a Report) inherits the review state of its source query's inputs.
- **Core or domain-specific**: the mechanism is Core; specific product *templates* (which views exist, what they show) are Domain-Pack-contributed (`04-DOMAIN-PACK-SPEC.md`).
- **V1 equivalent**: none as a distinct object — the closest things are filtered list pages (a company list, a priority queue), which are views, not stored/assembled/reusable objects.

## Report

- **Purpose**: a generated, shareable document built from one or more Intelligence Products — the customer-facing deliverable named explicitly in the V2 product direction ("generate customized intelligence reports").
- **Ownership/scope**: belongs to a Workspace.
- **Important relationships**: built from Intelligence Product(s); every claim/number in it traces back through the lineage chain to the Evidence that supports it (Core Design Principle #3 — no report content is allowed to be freestanding prose disconnected from evidence).
- **Provenance requirements**: generation timestamp, the query/template + parameters used to build it, and the full lineage of everything it cites.
- **Review state**: `draft → reviewed → published` — reports, like everything else AI might help draft, are proposals until a human signs off (Core Design Principle #4), especially given the report-hallucination risk (`09-RISK-REGISTER.md`).
- **Core or domain-specific**: the mechanism is Core; report *templates* are Domain-Pack-contributed.
- **V1 equivalent**: none.

## Export Package

- **Purpose**: formalizes `05-INTELLIGENCE-PACKAGE-SPEC.md`'s file format as a first-class, storable, auditable object — "we generated this specific export, at this time, with this content, for this purpose" — rather than just an ad hoc file someone ran a script to produce.
- **Ownership/scope**: belongs to a Workspace.
- **Important relationships**: references every Entity/Evidence/Fact/Claim/Relationship/Assessment/Signal/Recommendation/Report it contains, at the version/state they were in at export time.
- **Provenance requirements**: manifest (per `05-INTELLIGENCE-PACKAGE-SPEC.md`), generation timestamp, requested-by (User or API client), format (JSON/JSONL/CSV), scope (what filter/query produced it).
- **Review state**: n/a (an export is a point-in-time artifact, not something that itself gets reviewed — though its *contents* only include already-reviewed/published objects by default, with an explicit, logged override required to include unreviewed content).
- **Core or domain-specific**: Core.
- **V1 equivalent**: `scripts/export_for_review.py`'s `.xlsx` output is a narrow, single-purpose precedent (bulk review, not general export) — not the same object, but proof the underlying "serialize a filtered slice of the dataset to a portable file" mechanism already works at V1's scale.
