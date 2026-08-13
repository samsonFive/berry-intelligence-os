# Intelligence OS — Risk Register (V2)

**Status:** Planning draft, not accepted. Likelihood/impact ratings are this planning pass's own judgment, grounded in `CURRENT-STATE-AUDIT.md` where a risk is already partially observable in V1, and should be revisited once real V2 implementation experience exists.

Rating scale: **Likelihood** and **Impact** each Low/Medium/High. **Priority** is not a mechanical product of the two — it also weighs how hard the risk is to detect after the fact, since a low-likelihood, hard-to-detect risk (e.g., silent provenance loss) can outrank a higher-likelihood, easy-to-catch one.

---

## R-01 — Migration data loss

**Likelihood**: Low (with mitigation) / Medium (without) · **Impact**: High · **Priority**: Highest

**Description**: the Phase 3 Postgres migration, or any later schema evolution, silently drops or corrupts records from the 1,882-record V1 dataset — the single explicit product-direction requirement most directly threatened ("the existing blueberry dataset must be preserved").

**Mitigation**: the dual-write/parity-verification design in Phase 3 (`07-IMPLEMENTATION-ROADMAP.md`) is built specifically against this risk — automated, continuous, byte-level parity checking before any JSON-file write path is retired, plus a full Intelligence Package archival export taken before migration begins as an independent, out-of-band backstop. See D-009 (`08-DECISION-LOG.md`) — this is the primary reason a big-bang cutover is disallowed.

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

**Likelihood**: Medium (this is the specific, named risk of choosing a dual-write transition strategy at all) · **Impact**: Medium-High (a silent drift could look like R-01, migration data loss, if not caught) · **Priority**: High

**Description**: during Phase 3's dual-write period, the two stores (JSON files, Postgres) drift out of sync — a write succeeds on one side and fails or is delayed on the other, or a schema-evolution change is applied to one store's writer but not the other's, and nobody notices until the parity check catches it (or worse, doesn't).

**Mitigation**: this is precisely why Phase 3's acceptance criteria require the parity job to run *continuously* and report *zero discrepancies over a defined observation window* before cutover, not a one-time check at the start — the risk isn't "the migration is wrong on day one," it's "the two stores silently diverge over the following weeks." The parity job itself should alert loudly (not just log) on any discrepancy, treated as a Phase-3-blocking incident, not a background cleanup item.

**Owner/phase**: Phase 3, for the entire duration of the dual-write period.

---

## Summary — highest-priority risks

Ranked by this register's own priority assessment (not likelihood alone): **R-01 (migration data loss)**, **R-08 (report hallucination)**, and **R-09 (loss of provenance)** share the top priority tier — each directly threatens either an explicit product-direction requirement (preserving the dataset) or the platform's core identity claim (trustworthy, evidence-traceable intelligence). All three have structural, not just procedural, mitigations specified above and built into the roadmap's acceptance criteria, rather than left as "be careful" guidance.
