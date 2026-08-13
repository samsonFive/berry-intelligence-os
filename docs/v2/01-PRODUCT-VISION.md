# Intelligence OS — Product Vision (V2)

**Status:** Planning draft. Nothing in this document has been approved for implementation.
**Relationship to V1 docs:** this supersedes none of `WELCOME.md`, `docs/00-product-vision/VISION.md`, or `docs/01-prd/PRD.md` for the Berry Domain Pack itself — those remain accurate descriptions of the berry product. This document describes what the *platform underneath* Berry Intelligence OS becomes.

---

## 1. Product mission

Berry Intelligence OS's own mission statement already generalizes almost without editing:

> Enable analysts to transform public information, observations, reports, and organizational knowledge into trusted, explainable intelligence about a market.

V1 hard-coded "the global berry marketplace" into that sentence. **Intelligence OS's mission is the same sentence with the berry-specific noun phrase replaced by a variable**: trusted, explainable, evidence-traceable intelligence about *whatever market, industry, or geography a Domain Pack defines* — collected once, structured once, and reusable across every downstream view, report, and consuming system that needs it.

Everything else V1 got right should survive this generalization unchanged:

- Evidence before conclusions (ADR-0002).
- Facts are separate from interpretation; interpretation is separate from recommendation (`WELCOME.md` principles 2-3, `DOMAIN-MODEL.md`'s lineage chain).
- Every published conclusion is traceable to evidence.
- AI proposes; a human approves (`WELCOME.md` principle 5, carried forward as Core Design Principle #4 for V2).
- JSON is authoritative, or in V2's case, remains the interchange and export contract even where PostgreSQL becomes the operational store (Core Design Principle #8/#9).

## 2. Product boundaries

**Intelligence OS is:**
- A platform for structuring public-domain and organizationally-submitted information into evidence-linked entities, facts, claims, relationships, assessments, signals, and recommendations, for one or more domains at once.
- The home for cross-domain infrastructure: collection, storage, review, AI-assisted structuring, search, reporting, and export.
- Explicitly agnostic about which market it's watching — that's the Domain Pack's job (Section 4 below, and `04-DOMAIN-PACK-SPEC.md`).

**Intelligence OS is not:**
- A general-purpose CRM, document management system, or BI/dashboarding tool. It structures *evidence about a market*, not arbitrary business records.
- A scraping-as-a-service or data-broker product. Collectors gather what the operator configures them to gather, for the operator's own analytical use — not for resale of raw collected content (see Risk Register, copyright/licensing).
- An autonomous publisher. Per Core Design Principle #4, AI-proposed structure always has a human review gate before anything is trusted; this is a product boundary, not just an engineering choice, and it does not relax as the platform scales toward SaaS.
- Designed around any one organization's confidential downstream data (Core Design Principle #12). The platform's own operational data — what it collects, structures, and stores — must remain something the operator would be comfortable existing independently of any single company's internal systems, even when a specific deployment happens to be used inside one.

## 3. Target users

Largely unchanged from `PRD.md` Section 3, generalized:

| User | V1 (berry-specific) | V2 (general) |
|---|---|---|
| Intelligence analyst / system owner | Captures, reviews, structures, publishes for blueberry | Same role, any domain; now potentially across multiple domains/workspaces in one deployment |
| Product/business leader | Understands berry category position | Understands their domain's landscape — the "north star" outcome (Section 4) is unchanged in kind, only in subject |
| Cross-functional teams | Product, breeding, commercial, regional teams for berries | Whatever teams a given Domain Pack's audience implies — the platform doesn't know or care who they are |
| Future contributor | Submits berry evidence through hosted intake | Same, generalized; still gated by human review before anything is trusted (unchanged from V1's deferred-but-designed-for hosted submission path, ADR-0003) |
| **New in V2**: Downstream system / AI agent | Did not exist in V1 | Consumes exported Intelligence Packages (`05-INTELLIGENCE-PACKAGE-SPEC.md`) or the API — a first-class consumer, not an afterthought, but one that *reads* the platform's output rather than shaping the platform's architecture (Core Design Principle #11) |
| **New in V2**: Organization/workspace administrator | Did not exist — V1 has no auth | Manages who has access to which workspace/domain, once multi-tenancy exists (`LATER`, not `NOW` — see `02-TARGET-ARCHITECTURE.md`) |

## 4. Key use cases

Carried forward, generalized from `PRD.md` Section 10 ("V1 success criteria") and `VISION.md`'s north-star:

1. An analyst captures a piece of public information (article, report, filing, observation) without editing JSON directly, and it becomes linked entities, facts, and relationships.
2. A decision-maker opens an entity page (a company, a product line, a region — whatever the domain models) and understands its position, its evidence trail, and *why* the platform believes what it believes, not just what happened.
3. A decision-maker gets a synthesized view across many entities — a landscape, a comparison, a "what changed this period" digest — not just a list of individual records. **This is explicitly a V1 gap** (`CURRENT-STATE-AUDIT.md` Section 14, gap #1) that V2's intelligence/synthesis layer (`02-TARGET-ARCHITECTURE.md` Phase 4) exists to close.
4. An operator points the platform at a new domain (a new industry, not just a new berry) by writing a Domain Pack, without touching core application code (Core Design Principle #7).
5. A downstream system — another AI agent, a Copilot-style assistant, an internal tool — ingests a portable, provenance-preserving export of the platform's structured intelligence, without needing to understand the platform's internal storage model.
6. An operator can always answer "why does the platform believe this" by walking the lineage chain `Recommendation → Assessment/Signal → Facts → Evidence → Source` — a chain `DOMAIN-MODEL.md` specified from day one but V1 never fully built (`CURRENT-STATE-AUDIT.md` Section 5; two of its five links, Assessment and Recommendation, have no schema in V1 at all).

## 5. Intelligence OS versus Domain Pack — the distinction that matters most

This is the single most important conceptual shift from V1 to V2, so it's worth stating precisely.

**Intelligence OS (the platform / "core")** owns:
- The record types that are true for *any* domain: Evidence, Source, Fact, Claim, Relationship, Assessment, Signal, Recommendation, Strategic Question, Entity (as a generic typed container), Collector, Collection Job, AI Job, Intelligence Product, Report, Export Package, and (new) Organization, User, Workspace, Domain.
- The workflows that are true for any domain: capture → review → structure → publish → assess → report → export.
- The infrastructure: storage, search, background jobs, the AI provider abstraction, the collector framework, the export layer, authentication, and deployment.
- The invariants: provenance, review state, AI-proposes/human-approves, JSON as interchange contract.

**A Domain Pack** owns everything that only makes sense because you're watching *this specific kind of market*:
- Which entity *types* exist within the generic `Entity` container (for Berries: company, variety, breeding_program, brand, geography, retailer, trait, berry — `04-DOMAIN-PACK-SPEC.md` details how these are declared, not hard-coded).
- Which relationship *predicates* are meaningful (for Berries: owns, develops, licenses, operates_in, and the additional ones the blueberry import package's own `proposed-schema-enhancements.md` (P-2) identified as missing — `exhibits_claimed_trait`, `protects`, `markets`, `offers`, `administers_license_for`, `subsidiary_of`).
- Domain-specific taxonomies, trait vocabularies, strategic-question templates, collector templates (which sources/keywords/RSS feeds matter for *this* domain), report templates, filter sets, and visualization configuration.

Berry Intelligence becomes **the first Domain Pack and reference implementation** — proof that the split is real, not just aspirational — never the platform's architectural identity. A second Domain Pack (Phase 7 of the roadmap) is the actual test of whether this boundary was drawn correctly: if adding one requires touching core code, the boundary is wrong.

## 6. Downstream integration philosophy

Core Design Principle #11: corporate or downstream systems consume exports/API output; they do not dictate the core architecture. Concretely:

- The platform's primary interfaces to the outside world are the **Intelligence Package export** (`05-INTELLIGENCE-PACKAGE-SPEC.md` — files, portable, archivable, diffable) and a **clean read API** (`02-TARGET-ARCHITECTURE.md`). Both exist to be consumed, not to be told what shape to take by whoever is consuming them.
- No specific downstream system (a particular company's internal tool, a particular AI vendor's ingestion format) gets bespoke treatment in core code. If a downstream integration needs something the general export/API doesn't provide, that's a signal to strengthen the general contract, not to special-case the consumer.
- This is also why Core Design Principle #12 matters operationally, not just as an ethical stance: designing the platform's *own* data model around one company's confidential internal categories would violate the vendor-neutral principle (`ADR-0004`) that already governs how V1 treats market entities, and would make Domain Packs non-portable across operators.

## 7. A possible SaaS future, without letting it dominate V2

The platform "potentially evolves into a SaaS product" is real, and V2's architecture should not foreclose it — multi-tenancy, org/workspace boundaries, and authentication are all named explicitly in `02-TARGET-ARCHITECTURE.md`. But per this plan's own instruction not to add fashionable infrastructure prematurely:

- **V2 builds for a single operator running one or more domains**, with the org/workspace/user schema present from the start (so migrating data later doesn't require a schema rewrite) but **not** built out with real multi-tenant isolation, billing, or self-service onboarding until a second real deployment or paying user actually exists.
- SaaS-readiness is explicitly its own late-phase concern (Phase 8, `07-IMPLEMENTATION-ROADMAP.md`), gated on "if still justified" — i.e., a decision point, not a default.
- Nothing about the domain model, the collector framework, or the AI abstraction is SaaS-specific — they're correct for a single careful operator first, and multi-tenant only adds isolation and access control on top, not a redesign.

## 8. What does NOT change from V1's stated principles

Restated deliberately, because they're easy to erode under "generalize everything" pressure:

- Evidence remains the root object (ADR-0002) — nothing is asserted without a source.
- JSON remains authoritative for interchange and export even if PostgreSQL becomes the operational store (Core Design Principle #8/#9; `08-DECISION-LOG.md` D-001, D-002).
- The system stays portable and not vendor-locked, in the AI provider it uses (Core Design Principle #5) and in its storage layer (Core Design Principle #9's "portability must remain a design requirement").
- Market/domain entities are treated neutrally — no operator's employer or interest group gets architectural privilege (ADR-0004, carried into every Domain Pack).
- AI proposes, humans approve — this does not relax as the system scales toward more automation; more automation means more *proposals* moving faster through review, not fewer humans in the loop.
