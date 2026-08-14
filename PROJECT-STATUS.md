# Project Status

*Maintained by Claude. Updated at the end of each work session that changes project state. Keep short — this is a status check, not a changelog (see `docs/reviews/CURRENT-STATE-AUDIT.md` and `docs/v2/` for detail).*

**Last updated:** 2026-08-14

---

**Current program:**
Intelligence OS V2

**Current stage:**
Phase 2A complete — the repository-contract and scope-semantics design portion of Phase 2 (`BL-036`, `BL-037`). `docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md` is now the authoritative contract-requirements document for Phase 2B's implementation, built from 23 real, code-verified access patterns across the whole application, not from planning-doc assumptions or the Phase 1.5 findings document alone. The Assessment/Recommendation/Signal analytical-scope gap Phase 1.5B identified is resolved at the decision and schema level (`08-DECISION-LOG.md` D-012) — repository/route implementation of that decision is Phase 2B's job, not done yet.

**Current branch:**
`v2/intelligence-os`

**Next phase:**
Phase 2B — Repository/query implementation (`docs/v2/07-IMPLEMENTATION-ROADMAP.md`, `docs/v2/10-BACKLOG.md` BL-030 – BL-035) — not started, pending owner authorization. Scoped precisely by Phase 2A's deliverable, not designed from scratch.

**Last completed:**
Phase 2A (2026-08-14): `docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md` — an inventory of 23 real data-access patterns (verified directly against `app/main.py`, expanding on the 9 the Phase 1.5 findings document named), each classified CORE PERSISTENCE / CORE QUERY / DOMAIN-PACK-DOMAIN-SERVICE / UI COMPOSITION; a three-layer repository/query/domain-service boundary design (not implemented); a specified-but-not-yet-written repository contract-test suite for Phase 2B to implement test-first; a proposed Phase 2B package structure (`app/repositories/`, `app/queries/`, `app/services/berries/`); a documented raw-record → query-result → domain-synthesis → presentation flow; explicit error/integrity semantics for missing/duplicate/dangling/malformed/ambiguous-scope cases; and a Phase 3 migration gate for the known seed/demo-data hygiene issue (no code change — see `09-RISK-REGISTER.md` R-12). Alongside it, `08-DECISION-LOG.md` D-012 resolves the analytical-scope gap: `domain_ids`/`market_ids`/`geography_ids` (optional, additive) added to `assessment.schema.json` and `recommendation.schema.json`; `domain_ids`/`geography_ids`/`berry_ids` (the last one newly formalized, not new) added to `signal.schema.json`. Zero existing records were rewritten; zero routes, templates, or `app/main.py` structure changed.

Previously: tablet navigation breakpoint fix (2026-08-14, `app/static/app.css` mobile-collapse threshold 800px → 834px) resolving the Phase 1.5 visual review's one MUST-FIX-BEFORE-PHASE-2 finding. Before that: Phase 1.5B (`BL-026` – `BL-029`, 2026-08-13) — Blueberry Landscape, enhanced Company/Variety synthesis views, `docs/v2/PHASE-1-5-PROTOTYPE-FINDINGS.md`, `docs/v2/PHASE-1-5-VISUAL-REVIEW.md`.

**Findings worth knowing about (documented, not silently resolved):**
- The Assessment/Recommendation domain-scope gap (Phase 1.5B's finding) is now a **resolved decision** (D-012), not just a named gap — but the *fields* existing is Phase 2A's contribution; the *code* that reads/writes/queries them (`scope_disagreements()`, scope-aware `list()` filters) is explicitly Phase 2B's job, not done yet. Legacy records (all 6 imported Signals, the one real Assessment, the one real Recommendation) correctly have no explicit scope declared — this is honest "not yet declared," not a bug, and is not backfilled in Phase 2A per its own instruction not to rewrite existing records.
- The seed/demo-data hygiene finding (5 entities + 3 evidence records, self-described as fictional, no structural flag) now has a named Phase 3 gate (`09-RISK-REGISTER.md` R-12: no Intelligence Package used as the Postgres seed may contain unmarked fictional/demo records) and three evaluated-but-not-chosen fix candidates (`PHASE-2-REPOSITORY-REQUIREMENTS.md` Part 6.4, `data_classification` field preferred). Still unresolved in code — Phase 2A's mandate was the repository contract, not this data-hygiene fix, and nothing in the repository design depends on it being fixed first.
- The repository/query/domain-service three-layer split (Part 3) is explicitly *not* "one repository per screen" — it's ~10 record repositories (one per existing schema), a handful of query services grouped by kind of cross-object question, and a domain-service layer whose entire contents came from code Phase 1.5B had already isolated into clearly-marked comment blocks (`# BERRIES DOMAIN PACK PROTOTYPE LOGIC`, `# BERRIES LANDSCAPE PROTOTYPE LOGIC`) specifically anticipating this extraction.
- The review/publish workflow (`POST /review/{id}/publish`) is the one write pattern in the whole application that creates multiple object types (Evidence + Facts + Relationships + sometimes new Entities) in one logical operation — the strongest real argument found for a unit-of-work concept in the eventual repository interface, surfaced only by inventorying actual write code, not by reasoning from the read-heavy Phase 1.5 prototypes alone.

**In progress:**
Nothing. Phase 2A is complete and fully verified.

**Next:**
Owner authorization to begin Phase 2B (repository/query implementation), scoped by `docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md` and `docs/v2/10-BACKLOG.md` BL-030 – BL-035.

**Next implementation action:**
Not started — pending owner authorization. Phase 2B: implement the record-repository/query-service/domain-service layers Phase 2A specified, in the proposed `app/repositories/`/`app/queries/`/`app/services/berries/` structure, then refactor routes onto them.

**Blocked by:**
None.

**Known-good V1 reference:**
Tag `v1-blueberry-reference` → commit `432a96bd4efce1991df83b60aa1587154ba19528`. Unaffected by Phase 1A/1B/1.5A/1.5B/2A (all work on `v2/intelligence-os`, `master` untouched).

**Architecture documents:**
Accepted (`docs/v2/00-README.md` through `10-BACKLOG.md`, 2026-08-13). `docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md` (2026-08-14) is now the authoritative Phase 2B implementation spec, superseding `07-IMPLEMENTATION-ROADMAP.md` Phase 2's original item-level descriptions where they conflict.

**Tests at baseline:**
205 passed, 0 failed (`pytest -q`) — 122 original + 11 Phase 1A schema tests + 21 Phase 1B Domain Pack tests + 26 Phase 1.5A referential-integrity tests + 20 Phase 1.5B synthesis-view tests + 5 Phase 2A scope-field schema tests. `scripts/validate_records.py` passes with zero schema errors — the three schema files touched this phase (`assessment.schema.json`, `recommendation.schema.json`, `signal.schema.json`) gained only optional fields, verified to introduce zero regressions against live data. No route, template, or `app/main.py` code changed; no PostgreSQL work; no AI integration; no Collector execution code; runtime application behavior is unchanged.

**Important decisions — status:**
(IDs match `docs/v2/08-DECISION-LOG.md`)
- D-001 through D-009 — **ACCEPTED**
- D-010 — Claim stays a `fact.classification` value — **ACCEPTED (Option A)**, implemented
- D-011 — Recommendation and Evidence Priority coexist permanently — **ACCEPTED**, implemented
- D-007 (declarative Domain Packs, narrowed Phase 1 scope) — **ACCEPTED**, implemented
- D-012 (explicit analytical scope, separate from provenance) — **ACCEPTED** (2026-08-14, Phase 2A), schema-level implemented (three schemas gained optional `domain_ids`/`market_ids`/`geography_ids`, Signal's `berry_ids` formalized); repository/query-level implementation is Phase 2B work

No decisions remain open. No PostgreSQL, AI integration, or Phase 2B implementation work has begun.
