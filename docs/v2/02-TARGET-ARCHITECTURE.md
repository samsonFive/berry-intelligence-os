# Intelligence OS — Target Architecture (V2)

**Status:** Reviewed and accepted with revisions, 2026-08-13. See `08-DECISION-LOG.md` for every decision implied here — D-001 through D-009 are `ACCEPTED` (D-001 subject to the revised, non-dual-write migration strategy reflected in Section 3 below).

## How to read this document

Every subsystem below is broken into three columns:

- **NOW** — what exists today, in the V1 reference baseline (verified in `CURRENT-STATE-AUDIT.md`), which remains running and usable throughout migration (Core Design Principle #10).
- **V2** — what this planning pass proposes building. This is the actual scope of the work covered by `07-IMPLEMENTATION-ROADMAP.md`.
- **LATER** — named explicitly so it's clear what was *considered and deliberately deferred*, not overlooked. Nothing in this column is scoped, estimated, or committed to.

Nothing is added to the V2 column because it's fashionable. Where a subsystem's NOW state is already adequate for a single-operator, single-or-few-domain deployment, V2 leaves it alone and says so.

---

## 1. Web application

| NOW | V2 | LATER |
|---|---|---|
| FastAPI + Jinja2, server-rendered, single `app/main.py` (2,512 lines), 18 templates, no JS framework, no build step | **Adapt, don't rewrite.** Split `app/main.py` into routers by concern (entities, evidence, review, sources, reports) as domain-agnostic core code; move Berry-specific route behavior (entity-type-specific rendering quirks, if any survive) behind the Domain Pack interface (`04-DOMAIN-PACK-SPEC.md`). Templates stay server-rendered Jinja2 — no justification exists yet to introduce a client-side framework for what is fundamentally a read-and-review-heavy analyst tool. | A richer client-side app (React/Vue/etc.) if the product ever needs highly interactive, stateful views (live-updating dashboards, drag-and-drop report building) that server rendering genuinely can't do well. Not justified by anything in scope today. |

**Rationale for not rewriting the frontend now:** `CURRENT-STATE-AUDIT.md` rates the current template/CSS system as consistent and functional (Section 9); the actual V1 gaps are missing *views* (rollups, dashboards — Section 4/14 of the audit), not a broken rendering approach. Fix the missing views with more server-rendered templates before concluding the rendering approach itself is the problem.

## 2. API

| NOW | V2 | LATER |
|---|---|---|
| Three thin JSON endpoints exist (`/api/feed`, `/api/entities/{type}/{id}`, `/api/search`) — not a designed API surface, more a by-product of the server-rendered app needing some JSON for its own search UI | **New, but additive.** A real, versioned, read-first API (`/api/v2/...`) covering entities, evidence, facts, claims, relationships, assessments, signals, recommendations, strategic questions, and export-package generation — the same objects the domain model defines (`03-DOMAIN-MODEL.md`). Write endpoints (create/review/approve) come after read endpoints are stable, since read is what downstream/API consumers (Core Design Principle #11) need first. | GraphQL, webhooks/event streaming, real-time subscriptions — none justified without a concrete consumer asking for them. |

## 3. PostgreSQL

| NOW | V2 | LATER |
|---|---|---|
| No database. Flat JSON files, one per record, read fresh (with an in-process mtime-based cache) on every request. | **New, operational store — with JSON remaining the interchange contract (Decision D-001, D-002, both ACCEPTED).** PostgreSQL becomes where the app reads/writes at runtime; every table maps closely to a domain-model object; every row remains exportable back to the same JSON shape the Intelligence Package spec defines, so "the data" is never something only readable through a live database connection. **Migration approach (revised on review, `07-IMPLEMENTATION-ROADMAP.md` Phase 3): freeze and archive a validated Intelligence Package from V1 → load it into Postgres once → deterministic JSON↔Postgres↔JSON parity checks → full test suite against the Postgres repository → a bounded staging/branch acceptance period → cut over.** Not a big-bang cutover, but explicitly **not** an extended, indefinitely-running dual-write period either — the repository abstraction from Phase 2 is what makes this bounded sequence possible, since the same application code runs against either backend without an ongoing simultaneous-writes requirement. | Managed multi-region replication, read replicas, sharding — none justified at current or near-term data volumes (V1's entire dataset is under 2,000 records across all types). |

**Why Postgres and not "stay on flat files forever" or "jump straight to a fancier store":** flat files have already shown real limits at V1's modest scale — no referential-integrity checking (`CURRENT-STATE-AUDIT.md` Section 10), no concurrent-writer story, and every list/filter/sort operation is a full-folder scan. Postgres is a boring, well-understood answer to exactly those three problems, with mature tooling for the exact kind of structured, relational, provenance-chained data this domain model is (Section 3, `03-DOMAIN-MODEL.md`). It is not chosen because it's trendy — the opposite: it's the least novel technology that solves the actual observed problems.

## 4. Object/document storage

| NOW | V2 | LATER |
|---|---|---|
| Attachments (uploaded reports, images) stored directly on the local filesystem under `data/attachments/{evidence_id}/`, served via a route that path-validates against directory traversal | **Adapt.** Abstract behind a storage interface (local filesystem for single-operator/dev use, S3-compatible object storage as the pluggable alternative) so a hosted deployment isn't forced onto local disk, but a local-first single-operator deployment still needs nothing beyond a folder. Portability requirement (Core Design Principle #9) applies here too — no lock-in to one object-storage vendor's SDK. | CDN-fronted asset delivery, image transformation/thumbnailing pipelines — not justified without evidence attachments becoming a much larger part of the product. |

## 5. Search

| NOW | V2 | LATER |
|---|---|---|
| **Two independent implementations that must be kept in sync by hand** (`CURRENT-STATE-AUDIT.md` Section 2/10): a Python substring/typo-tolerant scan for the live app, and Pagefind (client-side WASM, build-time indexed) for the static deployment. | **Replace the live-app search with Postgres full-text search** (`tsvector`/`tsquery`, or `pg_trgm` for fuzzy/typo tolerance), operating over the same tables the rest of the app now reads from — one implementation instead of two, and no separate index-build step for the authoring app. **Keep Pagefind for the static/read-only publication path** (Section 6 below) — it's the right tool for a database-less static site and nothing in V2 changes that deployment target's constraints. | A dedicated search service (Elasticsearch/OpenSearch/Postgres-external) if relevance requirements (semantic search, large-scale ranking) outgrow what Postgres full-text search and the domain-model-aware ranking logic already built this V1 session (entity-first, date-sorted merge — `ARCHITECTURE.md`, "Search result prioritization") can do. Not justified today. |

## 6. Background jobs

| NOW | V2 | LATER |
|---|---|---|
| None as a general mechanism. Source polling runs as a single `asyncio` background task inside the FastAPI process lifespan, gated behind an env var, with no retry/backoff framework beyond what was hand-built into `resolve_real_summaries.py` (a standalone script, not integrated into the app process at all) | **New: a real job framework** (a lightweight queue — e.g. a Postgres-backed job table with a worker loop, not a new infrastructure dependency like Redis/Celery unless the volume genuinely demands it) covering: source collection runs, AI structuring jobs, report generation, and export-package generation. Every job type gets the same crash-recovery discipline this session's own `resolve_real_summaries.py` proved out by hand (retry-then-skip on transient failure, domain-aware circuit breaking, two-layered process-crash recovery) — generalized into the framework instead of re-invented per script. | A dedicated message broker (Redis/RabbitMQ/SQS) and a distributed worker fleet — not justified until job volume or latency requirements outgrow what a Postgres-backed queue and a handful of worker processes can do. |

## 7. Collector framework

| NOW | V2 | LATER |
|---|---|---|
| Two hard-coded collector *behaviors* inside `app/main.py`'s `check_source()`: RSS/Atom feed polling (via `feedparser`), and Google News keyword search (screen-scraped via a headless Playwright browser, since Google's redirect is client-side JS — `ARCHITECTURE.md`). Neither is pluggable; adding a third kind of source means editing core application code. | **New: a Collector interface** — a small, well-defined contract (`collect(source_config) -> list[RawCapture]`) that RSS, keyword-search, and future collector types all implement identically, registered by a Domain Pack or by platform config, not hard-coded into the app. The existing RSS and keyword-search behaviors become the first two reference collector implementations, not special-cased core logic. Collector output still lands as `Evidence` (unstructured/raw) — collectors gather, they do not structure (Core Design Principle #1, "collect once, structure once"). | A marketplace/plugin-distribution mechanism for third-party collectors, collector sandboxing/resource limits for untrusted collector code — not justified until collectors are written by anyone other than the platform's own operators. |

## 8. AI provider abstraction

| NOW | V2 | LATER |
|---|---|---|
| **None exists.** No AI/LLM integration anywhere in the current codebase (`CURRENT-STATE-AUDIT.md` Section 13, confirmed by direct search) — Milestone 6 was never started. | **New: a provider-neutral AI interface** (Core Design Principle #5) — a small contract (`propose_structure(evidence) -> ProposedFacts/Claims/Relationships`, `propose_assessment(...)`, `summarize(...)`) implemented against whichever provider(s) an operator configures, with no application code anywhere calling a specific vendor's SDK directly. Every AI output lands as a *proposal* attached to the relevant object with a clear "AI-proposed, pending review" state (Core Design Principle #4) — never auto-published. This is the mechanism that closes `CURRENT-STATE-AUDIT.md`'s largest-ranked gap (Section 14, #1 and #2: no synthesis layer, priority queues that don't scale with auto-captured volume). | Fine-tuning custom models, running local/self-hosted inference — not justified before the provider-neutral abstraction itself is proven against at least one hosted provider. |

## 9. Report generation

| NOW | V2 | LATER |
|---|---|---|
| None. "Intelligence product" (landscape view, competitor profile, weekly digest) is named in `DOMAIN-MODEL.md` from the start but was never built — the closest V1 equivalent is a filtered list page, not an assembled report. | **New: a report-generation layer** producing the `Report` domain object (`03-DOMAIN-MODEL.md`) from a template (Domain-Pack-contributed, `04-DOMAIN-PACK-SPEC.md`) plus a query against the current data — landscape views, comparison views, and digests, each traceable back to the evidence/facts/assessments it drew from (never freestanding prose, per the lineage requirement in `DOMAIN-MODEL.md` and Core Design Principle #3). | Fully custom drag-and-drop report building, scheduled/emailed report delivery — not justified until template-based reports are proven useful. |

## 10. Export layer

| NOW | V2 | LATER |
|---|---|---|
| One narrow export exists: `scripts/export_for_review.py` produces an `.xlsx` of the unvalidated review backlog, for offline bulk triage — not a general data export, command-line only, not reachable from any route. | **New: the Intelligence Package export** (`05-INTELLIGENCE-PACKAGE-SPEC.md`) — JSON/JSONL/CSV, generated from the same objects the API serves, downloadable via the API and/or a UI action, versioned and manifest-described so a downstream consumer can validate what they received. | Streaming/incremental export for very large datasets, export-format plugins for arbitrary third-party schemas — not justified at current data volumes or against a named consumer's format requirement. |

## 11. Authentication

| NOW | V2 | LATER |
|---|---|---|
| **None.** `AUTHORING_MODE` is a single global on/off env-var switch, not authentication — no login, no session, no per-user identity anywhere in the code (`CURRENT-STATE-AUDIT.md` Section 4, confirmed by direct search). | **New, minimal: single-operator or small-team authentication** — enough to know *who* approved a fact or ran an import (the `reviewer` field already exists on facts/signals and deserves to be a real user reference, not a free-text string), and to gate write access. A standard, well-understood approach (e.g. session-based auth against the Postgres `User` table) — not a build-your-own-crypto exercise. **Hard rule, added on review, not conditional on any phase: no writable Intelligence OS instance may be exposed to the public internet without authentication in front of it — ever.** If V2 stays local/private through Phases 1-4 (as expected — see `07-IMPLEMENTATION-ROADMAP.md`), authentication does not block those phases' work. It becomes a hard gate the moment any writable instance is reachable from the public internet, independent of which phase that happens in. | Full multi-tenant SSO/OAuth-provider support, fine-grained per-object permissions, org-level billing/seat management — explicitly `LATER`, gated on Phase 8 (SaaS-readiness) actually being justified. |

## 12. Organization / workspace / domain boundaries

| NOW | V2 | LATER |
|---|---|---|
| None. V1 is implicitly single-operator, single-domain (blueberry only), with no concept of a boundary between one dataset and another. | **New, schema-present but lightly enforced**: `Organization → Workspace → Domain` as real objects in the domain model and the Postgres schema from the start (so later migration doesn't require a structural rewrite), with every core object (`Entity`, `Evidence`, `Fact`, ...) scoped to a `Workspace`. **V2 itself may run with exactly one Organization and one Workspace** — the schema exists to prevent a costly later migration, not because multi-tenant isolation is being built out now. | Real multi-tenant isolation (row-level security, per-tenant resource quotas, tenant-specific billing) — explicitly deferred to Phase 8, "if still justified." |

## 13. Deployment

| NOW | V2 | LATER |
|---|---|---|
| Two paths: local `uvicorn` for authoring (writable, single-operator), and a static build (`scripts/build_static.py`) deployed read-only to GitHub Pages via a CI workflow that now runs `pytest` before every build (this session's own fix). | **Adapt, keep both.** The static/read-only publication path is preserved unchanged — it's cheap, proven, and serves a real need (a shareable, zero-infrastructure, always-rebuildable public view). Add a **new, independently hosted deployment path** (Core Design Principle: "independently hosted intelligence platform") for the live, writable, Postgres-backed app — containerized, deployable to any standard host, no proprietary-platform lock-in (continuing ADR-0001's local-first/portable spirit into a hosted context). | Kubernetes/complex orchestration, multi-region deployment, blue-green/canary release automation — not justified for a single-operator-to-small-team product with V1's current data volume. A single container plus a managed Postgres instance is enough until there's a concrete reason to outgrow it. |

---

## Cross-cutting: what does NOT change

- **Local-first remains possible.** Nothing above removes the ability to run the whole system on a single machine with no external dependencies beyond Postgres itself (which can run locally too) — "independently hosted" (the product direction's own words) means *not dependent on one SaaS vendor*, not *impossible to self-host*.
- **JSON stays first-class** (Core Design Principle #8) at every layer above, even where Postgres is the operational store — every table's data must round-trip to the same JSON shape the schemas already define, extended per `03-DOMAIN-MODEL.md`/`05-INTELLIGENCE-PACKAGE-SPEC.md`.
- **The V1 application keeps running throughout** (Core Design Principle #10) — nothing above is a "stop V1, start V2" cutover. See `06-MIGRATION-MAP.md` and Phase 3 of `07-IMPLEMENTATION-ROADMAP.md` for how the Postgres migration specifically avoids a big-bang cutover.
