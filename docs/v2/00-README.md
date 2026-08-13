# Intelligence OS V2 — Planning Document Set

**Status: planning draft. Nothing in `docs/v2/` is accepted. No implementation begins until this set is reviewed and approved.**

This directory is the architecture planning pass for the controlled transition from Berry Intelligence OS V1 into a generalized Intelligence OS, per the product direction: an independently hosted platform that can monitor arbitrary industries/markets/geographies, with Berry Intelligence becoming the first Domain Pack and reference implementation rather than the platform's architectural identity.

**No production code, data, or existing documentation was changed to produce this set.** The V1 application remains the working reference implementation and stays fully usable and recoverable throughout (Core Design Principle #10) — see `07-IMPLEMENTATION-ROADMAP.md` Phase 0.

## What was read to produce this

`docs/reviews/CURRENT-STATE-AUDIT.md`, `README.md`, `WELCOME.md`, `docs/00-product-vision/VISION.md`, `docs/01-prd/PRD.md`, `docs/03-information-architecture/DOMAIN-MODEL.md`, `docs/04-technical-architecture/ARCHITECTURE.md`, `docs/05-development-roadmap/BUILD-GUIDE.md`, all four ADRs (`docs/decisions/`), all six current JSON schemas (`schemas/`), the current routes/templates/scripts (`app/main.py`, `app/templates/`, `scripts/`), and the blueberry import package's documentation (`data/imports/blueberry-public-pilot-2026-08-03/`, particularly `manifest.json`, `README.md`, and `proposed-schema-enhancements.md`, which independently proposed several of the same gaps this planning pass also identifies — a useful cross-check, not a coincidence, since both efforts were grounded in the same live data).

## How to read this document set

Read in numeric order for a first pass — each document builds on the ones before it:

| # | Document | Answers |
|---|---|---|
| 01 | [`PRODUCT-VISION.md`](01-PRODUCT-VISION.md) | What is Intelligence OS, who is it for, and how does it relate to Berry Intelligence OS (a Domain Pack) versus the platform itself? |
| 02 | [`TARGET-ARCHITECTURE.md`](02-TARGET-ARCHITECTURE.md) | What does the platform look like technically — web app, API, storage, search, jobs, collectors, AI, deployment — split into NOW (V1 today) / V2 (this plan's scope) / LATER (deliberately deferred)? |
| 03 | [`DOMAIN-MODEL.md`](03-DOMAIN-MODEL.md) | What are the actual objects (Organization through Export Package) — their purpose, scope, relationships, provenance requirements, and review state? |
| 04 | [`DOMAIN-PACK-SPEC.md`](04-DOMAIN-PACK-SPEC.md) | How does a domain (Berries, or anything else) plug into the platform without touching core code? |
| 05 | [`INTELLIGENCE-PACKAGE-SPEC.md`](05-INTELLIGENCE-PACKAGE-SPEC.md) | What's the portable export/import file format for archival, downstream agents, and migration? |
| 06 | [`MIGRATION-MAP.md`](06-MIGRATION-MAP.md) | What happens to every significant piece of the current repository — kept, adapted, replaced (with a bridge), built new, or deferred? |
| 07 | [`IMPLEMENTATION-ROADMAP.md`](07-IMPLEMENTATION-ROADMAP.md) | What are the phases, in what order, with what acceptance criteria? |
| 08 | [`DECISION-LOG.md`](08-DECISION-LOG.md) | What architecture decisions is this plan proposing, and which two are genuinely still open? |
| 09 | [`RISK-REGISTER.md`](09-RISK-REGISTER.md) | What can go wrong, and what's the specific, structural (not just procedural) mitigation for each? |
| 10 | [`BACKLOG.md`](10-BACKLOG.md) | What are the actual bounded work items, phase by phase? |

## The single most important idea in this set

Everything here is organized around one distinction, stated fully in `01-PRODUCT-VISION.md` Section 5: **Intelligence OS (core) owns what's true for any domain — evidence, facts, claims, relationships, assessments, signals, recommendations, the review workflow, storage, search, AI abstraction, collectors, reports, exports. A Domain Pack owns everything that's only true because you're watching *this* market — which entity types exist, which relationship predicates matter, which taxonomies, templates, and starter sources apply.** Berries becomes the proof that this split is real: Phase 7 of the roadmap validates it by building a second Domain Pack — recommended to be a genuinely unrelated industry, not just another berry, specifically because that's the harder and more honest test.

## What this plan does NOT do

- It does not modify `app/main.py`, any schema, any template, or any data file.
- It does not commit the platform to PostgreSQL, a specific AI provider, or any specific SaaS feature as a *fait accompli* — every architectural choice in `02-TARGET-ARCHITECTURE.md` and every decision in `08-DECISION-LOG.md` is marked `PROPOSED`, not accepted, per the task's explicit instruction.
- It does not propose a big-bang rewrite anywhere — `06-MIGRATION-MAP.md` gives every `REPLACE` item a coexistence bridge, and `08-DECISION-LOG.md` D-009 records this as a deliberate, named decision, not an implicit assumption.
- It does not scope Phase 8 (SaaS-readiness) in detail — that phase's first work item is a justification decision, made later, against real need.

## Recommended next step

Per the task's own closing instruction, implementation does not begin until this set is reviewed and accepted. The concrete first action **after acceptance** is Phase 0 (`07-IMPLEMENTATION-ROADMAP.md`): tag the current V1 commit as the reference baseline (`BL-001`, `10-BACKLOG.md`) — a trivial, reversible, zero-risk action that unblocks every subsequent phase without touching anything currently running.
