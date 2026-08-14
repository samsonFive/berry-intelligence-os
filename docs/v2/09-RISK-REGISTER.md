# Intelligence OS — Risk Register (V2)

**Status:** Reviewed and accepted with revisions, 2026-08-13 — R-01's mitigation and R-11's likelihood/priority were updated to reflect the simplified Phase 3 migration strategy (see the note at the end of this document). Likelihood/impact ratings are this planning pass's own judgment, grounded in `CURRENT-STATE-AUDIT.md` where a risk is already partially observable in V1, and should be revisited once real V2 implementation experience exists.

Rating scale: **Likelihood** and **Impact** each Low/Medium/High. **Priority** is not a mechanical product of the two — it also weighs how hard the risk is to detect after the fact, since a low-likelihood, hard-to-detect risk (e.g., silent provenance loss) can outrank a higher-likelihood, easy-to-catch one.

---

## R-01 — Migration data loss

**Likelihood**: Low (with mitigation) / Medium (without) · **Impact**: High · **Priority**: Highest

**Description**: the Phase 3 Postgres migration, or any later schema evolution, silently drops or corrupts records from the 1,882-record V1 dataset — the single explicit product-direction requirement most directly threatened ("the existing blueberry dataset must be preserved").

**Mitigation**: the revised, bounded seven-step migration in Phase 3 (`07-IMPLEMENTATION-ROADMAP.md`, `08-DECISION-LOG.md` D-001) is built specifically against this risk — freeze and archive a validated Intelligence Package first (an independent, out-of-band backstop that exists *before* any Postgres load happens), then deterministic JSON→Postgres→JSON round-trip parity checks against that frozen archive, then the full test suite against the Postgres repository, then a bounded staging acceptance period, then cutover — with the V1 git tag and the archived package preserved indefinitely afterward, not just until confidence is high. See D-009 (`08-DECISION-LOG.md`) — this is the primary reason a big-bang cutover is disallowed. Deliberately **not** an extended dual-write period (rejected on review — see D-001's reviewer modification): the mitigation here is a verified, deterministic, bounded sequence, not an open-ended parallel-run.

**Owner/phase**: Phase 3.

---

## R-02 — Over-generalization

**Likelihood**: Medium · **Impact**: Medium · **Priority**: High

**Description**: the platform is generalized further than any real second domain actually needs, producing abstractions that are speculative rather than proven — e.g., a Domain Pack contribution surface with fields no real pack ever uses, or a Collector interface shaped around imagined future collector types instead of the two that already exist.

**Mitigation**: Phase 7's second-domain validation is the direct, structural defense — every abstraction in `04-DOMAIN-PACK-SPEC.md` is checked against a deliberately unrelated second industry *in this planning pass itself* (Section-by-section "second-domain check"), and again for real in Phase 7. Anything that doesn't earn its place against a real second use case is a candidate for simplification, not permanent scope.

**Owner/phase**: ongoing design discipline through Phase 1/4/5, validated at Phase 7.

---

## R-03 — Premature SaaS complexity

**Likelihood**: Medium (if not actively guarded against) · **Impact**: Medium · **Priority**: Medium

**Description**: multi-tenancy, billing, SSO, or other SaaS-specific infrastructure gets built before there's a real second operator or paying customer to justify it, consuming engineering effort that doesn't serve the platform's actual current use.

**Mitigation**: Phase 8 is explicitly gated on "if still justified," with its own acceptance criteria left undefined until a named reason and requester exist (`07-IMPLEMENTATION-ROADMAP.md`). D-008 (`08-DECISION-LOG.md`) draws the specific line: Organization/Workspace/Domain *schema* exists early (cheap, prevents a future rewrite), but *enforcement* (real isolation, billing) waits for Phase 8.

**Owner/phase**: guarded by the Phase 8 gate; violated if any earlier phase's scope creeps into SaaS-specific work without going through that gate.

---

## R-04 — AI cost explosion

**Likelihood**: Medium · **Impact**: Medium-High (financial, and could force a rushed, poorly-reviewed automation posture that violates Core Design Principle #4) · **Priority**: High

**Description**: once AI-assisted structuring/assessment/report-drafting exists (Phase 5-6), usage — especially automated, collector-triggered AI Jobs — grows faster than cost visibility or budget controls, either creating a large unexpected bill or creating pressure to skip human review to "keep up," which would be a direct principle violation, not just a cost problem.

**Mitigation**: `AI Job` (`03-DOMAIN-MODEL.md`) is specified to record cost (token count or equivalent) on every run from the start, not added later — cost visibility is a Phase 5 acceptance requirement, not a follow-up. The provider-neutral abstraction (D-005) also makes it possible to route work to a cheaper provider/model per job type without an application rewrite. No auto-scaling of AI usage without a human-set ceiling should be implemented without an explicit budget/rate-limit decision, which this document flags but does not resolve.

**Owner/phase**: Phase 5.

---

## R-05 — Provider lock-in

**Likelihood**: Low (with mitigation) / High (without) · **Impact**: Medium · **Priority**: Medium

**Description**: AI provider-specific behavior (a particular model's prompt quirks, a particular vendor's function-calling format) leaks into core application logic, making a future provider switch expensive despite the abstraction existing on paper.

**Mitigation**: D-005's provider-neutral interface, with the Phase 5 acceptance criterion that a provider swap requires zero application code changes — a real test, not just an architectural intention. Prompt templates and provider-specific tuning live behind the interface, not scattered through route/business logic.

**Owner/phase**: Phase 5, re-verified whenever a second provider is actually integrated.

---

## R-06 — Source copyright / licensing

**Likelihood**: Medium · **Impact**: Medium-High (legal/reputational) · **Priority**: High

**Description**: Collectors (especially screen-scraping-based ones, per V1's own precedent of resolving Google News redirects via headless browser) gather copyrighted publisher content in a way that exceeds fair use or a publisher's terms of service, particularly if collected content is re-published, re-distributed, or included verbatim in exports/reports rather than summarized with attribution.

**Mitigation**: V1's own operating discipline is already a partial answer and should be carried forward explicitly: this session's own work refused to attempt bypassing CAPTCHA/bot-detection specifically because doing so crosses from "collecting information a user could see" into "circumventing a site's own access controls" (`ARCHITECTURE.md`'s summary-resolution section documents this refusal directly). V2 should formalize this as policy, not just inherited caution: Collectors respect robots.txt and bot-detection by design (never engineered around); stored Evidence should prefer summary/excerpt + source link over full-text reproduction where a source's terms are unclear; and the Intelligence Package export (`05-INTELLIGENCE-PACKAGE-SPEC.md`) should carry enough source attribution that a downstream consumer can independently assess their own reuse rights rather than inheriting an ambiguous status silently.

**Owner/phase**: Phase 5 (Collector framework design), and an explicit legal/policy review before any hosted, multi-user deployment (Phase 8 gate).

---

## R-07 — Duplicate entity resolution

**Likelihood**: High (this is already a known, named V1 concern) · **Impact**: Medium · **Priority**: Medium-High

**Description**: as more Collectors and AI-assisted structuring run, the same real-world entity gets created multiple times under slightly different names/aliases (V1's own `review.html` duplicate-title warning and `Entity.aliases` field are the existing, partial mitigations) — at V2's larger intended scale (more domains, more automated collection), this problem compounds faster than V1's manual-review-time duplicate check can catch.

**Mitigation**: entity-matching/dedup logic remains explicitly a **human-in-the-loop** decision (Core Design Principle #4) even when AI proposes a likely match — an `AI Job` can *suggest* "this looks like an existing entity," never silently merge. Phase 4/5 should extend V1's existing duplicate-detection pattern (currently title-string-matching only, per `CURRENT-STATE-AUDIT.md`) using the richer signal AI-assisted proposals can offer, but the merge/reject decision stays a reviewed action, logged the same way any other review decision is.

**Owner/phase**: Phase 4 (initial extension of existing duplicate detection), Phase 5 (AI-assisted matching suggestions).

---

## R-08 — Report hallucination

**Likelihood**: Medium-High (inherent to any LLM-assisted report drafting) · **Impact**: High (directly undermines the platform's core "trustworthy evidence system" identity) · **Priority**: Highest

**Description**: an AI-drafted Report or Assessment states something not actually supported by the evidence/facts it claims to synthesize — the single failure mode most damaging to the platform's stated identity, since it would make the lineage-traceability guarantee (Core Design Principle #3) false in exactly the place a consumer is most likely to trust it (a polished, finished-looking report).

**Mitigation**: structural, not just a review-culture request — `Report` (`03-DOMAIN-MODEL.md`) is specified so every claim/number in it must trace through the lineage chain to supporting Evidence, and Reports carry the same `draft → reviewed → published` gate as any other AI-assistable object (Core Design Principle #4). A Report generation implementation should be built to *only* assemble from already-structured, already-linked Assessments/Signals/Facts/Recommendations — never free-generate prose not grounded in a specific object's citation, which is what makes hallucination checkable at all (a claim with no cited source is a detectable defect, not just a bad experience).

**Owner/phase**: Phase 6 (Report generation design), enforced by the review gate at every phase where AI touches published content.

---

## R-09 — Loss of provenance

**Likelihood**: Medium (schema evolution and migration both create opportunities for this) · **Impact**: High · **Priority**: Highest

**Description**: a record's link back to its supporting evidence/facts breaks or goes unenforced somewhere in the pipeline — during migration (a foreign key that should exist doesn't), during AI-assisted structuring (a proposal that drops its source reference), or during export (a flattened CSV row that loses the chain a JSON export would have kept). Already a *partially observed* V1 issue: `CURRENT-STATE-AUDIT.md` found no referential-integrity checking anywhere in V1 today — a dangling reference currently fails silently, not loudly.

**Mitigation**: this is the direct rationale for `source-lineage.json`'s `orphan_check` in `05-INTELLIGENCE-PACKAGE-SPEC.md` — provenance completeness becomes a machine-checkable export property, not an assumption. Phase 3's Postgres migration should add real foreign-key constraints (something flat JSON files structurally cannot enforce), closing V1's specific, already-identified gap. Every new core object (Assessment, Recommendation) is specified in `03-DOMAIN-MODEL.md` with a *required*, non-empty evidence/fact reference — provenance is a schema-level requirement, not a UI convention.

**Owner/phase**: Phase 1 (schema requirements), Phase 3 (foreign-key enforcement), Phase 6 (export-time `orphan_check`).

---

## R-10 — Authentication / security

**Likelihood**: Medium · **Impact**: High (once the app is independently hosted rather than run locally, this becomes a real attack surface for the first time) · **Priority**: High

**Description**: V1 has zero authentication (`CURRENT-STATE-AUDIT.md` Section 4) — safe only because it's a local-only, single-operator tool. The moment V2 is "independently hosted" (the product direction's own words), this changes completely: unauthenticated write access to a hosted intelligence store is a real security exposure, not a theoretical one.

**Mitigation**: minimal authentication is scoped explicitly into Phase 6 (`07-IMPLEMENTATION-ROADMAP.md`), not deferred to Phase 8 — write access must be gated before any hosted deployment goes live, independent of whether full multi-tenant permissions (Phase 8) exist yet. Use standard, well-understood authentication (not custom crypto) per `02-TARGET-ARCHITECTURE.md` Section 11. No hosted deployment should be considered complete without this, regardless of how far other phases have progressed.

**Owner/phase**: Phase 6 (minimum viable), Phase 8 (full model, if justified).

---

## R-11 — Flat-file / Postgres parity drift during transition

**Likelihood**: Low-Medium (substantially reduced by the revised, bounded migration strategy — see below) · **Impact**: Medium-High (an undetected discrepancy could look like R-01, migration data loss, if not caught) · **Priority**: Medium (downgraded on review from High, reflecting the reduced exposure window)

**Description**: **revised in scope on review, 2026-08-13** — the original framing of this risk assumed an extended dual-write period where two actively-written stores could silently diverge over time. That strategy was rejected (`08-DECISION-LOG.md` D-001's reviewer modification): Phase 3 now freezes the JSON source, loads it into Postgres once, and never writes to JSON again. The residual risk this leaves is narrower but real: **(a)** the one-time load (step 2) silently drops or transforms something during the JSON→Postgres translation, and **(b)** during the bounded staging/branch acceptance period (step 5), the application writes new data directly to Postgres — data that has no JSON-side equivalent by design (the archive is a frozen point-in-time snapshot, not meant to stay in sync) — which matters only if the migration needs to be abandoned mid-staging and rolled back, at which point those Postgres-only writes would need an explicit reconciliation plan, not an assumption they'll just carry over.

**Mitigation**: **(a)** is exactly what the deterministic JSON→Postgres→JSON round-trip parity check (step 3) exists to catch — run against the frozen archive, not a moving target, so "zero discrepancies" is a clean, one-time, fully reproducible bar rather than an ongoing monitoring problem. **(b)** is addressed by treating the staging period as genuinely provisional: any real analytical work done during it (a new Fact, a new Assessment) should be treated as at-risk until cutover is final, and a rollback decision during staging should be made early rather than late, before provisional Postgres-only work accumulates enough volume to make reconciliation itself risky.

**Owner/phase**: Phase 3 — step 3 (parity check) and step 5 (staging period), specifically.

---

## R-12 — Seed/demo-data contamination in the PostgreSQL seed

**Likelihood**: Medium (without an explicit gate) / Low (with it) · **Impact**: Medium-High (fictional data indistinguishable from real intelligence in the permanent operational store is a trust-identity problem, not just clutter) · **Priority**: High

**Description**: **added 2026-08-14, Phase 2A** (`docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md` Part 6). The live dataset contains 5 entities and 3 evidence records explicitly self-described in their own `description` field as fictional V1 seed/demo data (`company-example-genetics`, `company-example-nursery`, `retailer-example-market`, `variety-example-blue`, `variety-example-red`, `ev-sample-patent-published`, `ev-sample-retail-placement`, `ev-sample-variety-launch`), stored in the same `data/entities/`/`data/evidence/` folders as real intelligence with no structural field distinguishing them (found during Phase 1.5B, `docs/v2/PHASE-1-5-PROTOTYPE-FINDINGS.md` Section 5). Today, only the Blueberry Landscape's aggregation functions know to exclude them (a hard-coded id list, `app/main.py`); every other route, and any future repository/query/export code that doesn't independently know about that same list, would present them as real.

**Mitigation**: an explicit Phase 3 migration gate, not a Phase 2 requirement — **no Intelligence Package used as the PostgreSQL seed (Phase 3 Step 1, "freeze and archive") may contain unmarked fictional/demo records.** Three candidate mechanisms are evaluated (not chosen) in `docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md` Part 6.4: an additive `data_classification: production | demo | seed` field (the preferred candidate — least invasive, self-describing, works uniformly across every object type), separate directories, or package-level exclusion. Whichever is chosen, it must exist and be applied *before* Phase 3 Step 1 freezes the archive that becomes Postgres's permanent seed data — after that point, fictional records loaded as real become exactly the kind of irreversible, hard-to-detect mistake R-01's "zero data loss, bounded, sequential" migration philosophy exists to prevent (the inverse failure mode: not losing real data, but permanently gaining fake data indistinguishable from it).

**Owner/phase**: identified Phase 2A; must be resolved no later than Phase 3 Step 1. May be resolved during Phase 2B if convenient, but is not a Phase 2B acceptance requirement.

---

## Summary — highest-priority risks

Ranked by this register's own priority assessment (not likelihood alone): **R-01 (migration data loss)**, **R-08 (report hallucination)**, and **R-09 (loss of provenance)** share the top priority tier — each directly threatens either an explicit product-direction requirement (preserving the dataset) or the platform's core identity claim (trustworthy, evidence-traceable intelligence). All three have structural, not just procedural, mitigations specified above and built into the roadmap's acceptance criteria, rather than left as "be careful" guidance.

**Revised on review, 2026-08-13**: R-01's mitigation and R-11's likelihood/priority were both updated to reflect the simplified, bounded Phase 3 migration strategy adopted this review (freeze/archive/load/parity-check/test/stage/cutover, replacing the originally-proposed extended dual-write period — see `08-DECISION-LOG.md` D-001). R-01 remains top-priority; R-11 is downgraded from High to Medium priority, since removing the extended-dual-write design removes the specific failure mode ("two actively-written stores silently diverging over weeks") that risk was originally scoped around.
