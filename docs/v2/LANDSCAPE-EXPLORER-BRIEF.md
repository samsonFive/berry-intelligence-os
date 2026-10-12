# Berry Intelligence OS — Landscape Explorer

## Model and mission

Recommended implementation agent: GPT-6 Astra, Extra high reasoning, in Codex with repository access. This is a recommendation for engineering the feature, not a requirement to run Astra inside the product. Reuse the product's existing inference provider where appropriate.

Build an evidence-backed visual intelligence explorer in the existing Berry Intelligence OS repository: https://github.com/samsonFive/berry-intelligence-os.

This document is an executable engineering handoff and proposed PR scope. It is not an opened GitHub PR or a report of inspected repository state. Inspect current canonical code before choosing implementation details. Historical project descriptions and supplied interview materials are context, not authoritative current schemas or production data.

### User intent

The app is functional and visually appealing. Its next major capability should turn collected information into understandable industry landscapes, reveal relationships and change, and produce useful visual explanations. Blueberry is the first working test case. The other berries are part of this same mission, with a deliberate review and tuning checkpoint before completing them.

Success: an analyst selects Peru, Chile, and China, sees documented connections among blueberry companies, breeding programs, varieties, and markets, understands what changed, opens the evidence, and exports a readable landscape portrait.

## Execution contract — read first

1. Inspect AGENTS.md, current default branch, existing feature work, entity registry, variety records, evidence models, geographic filters, dossier routes, change engine, export tools, inference adapters, and actual hosting architecture. Record canonical SHA and relevant existing components. Do not assume remembered PR numbers or routes remain current.
2. Implement this in the existing app and its design system. Do not create a separate website or replace the news reader.
3. Build a berry-neutral engine with blueberry enabled first. Avoid blueberry-specific persistence or duplicated berry-specific UI.
4. Reach Milestone A: a complete, tested, previewable blueberry vertical slice. Open a draft PR if repository access permits. Commit and push the reviewable work where permitted.
5. STOP at Milestone A and provide the review packet below. Do not begin remaining-berry rollout, merge, or deploy. This stop is explicitly requested by the user. Blueberry completion does not complete the overall mission.
6. After explicit user feedback approving continuation, implement the revisions, then finish Milestone B on the same mission. Preserve the full scope and status in the repository so another session can resume.
7. Prefer one draft PR carried through both milestones. If repository conventions require several PRs, use linked PRs under one tracked mission and preserve the same review gate. Do not silently narrow scope.
8. Never claim tests passed, a preview works, a PR exists, or deployment succeeded without verification. If remote access is unavailable, produce the committed local implementation and exact PR title/body; report the access limitation.

Suggested branch: feature/landscape-explorer. Draft PR title at checkpoint: Landscape Explorer: blueberry review milestone. Final title: Landscape Explorer: evidence-backed berry landscapes, change views, and visual briefings.

## Product scope

### 1. Landscape: a readable industry portrait

Provide an entry from main navigation and contextual entry points from company/variety dossiers where those exist. Default to blueberry during Milestone A.

Use a structured, stable visual composition: selected countries or regions as lanes, company/program cards grouped sensibly, varieties shown on expansion, and labeled connections visible on selection. Include a small geography overview if supported by the existing map infrastructure. An exploratory network layout may be an alternate view; an unreadable all-node force graph cannot be the default.

Controls: berry, multiple countries, entity search, relationship type, evidence status, focus/reset, and date/change window. Persist shareable filter state in the URL; preserve selection when opening evidence. Show an explicit legend and current data scope. Dense results must use progressive disclosure with visible hidden-result counts.

Selecting a company, program, or variety highlights its documented neighborhood. Selecting a relationship opens its source-backed evidence panel. Keyboard users must be able to perform the same analysis through a synchronized relationship list/table. Support desktop, dark/light themes, and a usable mobile stacked view.

### 2. Follow the genetics

Enable tracing breeder/program → variety → licensed or documented commercial actors → countries, subject to available evidence. Preserve the distinction among breeder, owner, licensee, grower, marketer, and distributor. Use only supported typed relationships; ownership does not imply breeding, and marketing does not imply growing.

Cross-geography genetics is a first-class feature. A variety/program documented in several countries should show those links. A shared company name alone does not prove that the same genetics are present in both places. Never invent acreage, volume, market share, availability, or commercial adoption from article counts.

### 3. Change: what became visible and what actually changed

Offer a date window and highlight newly documented relationships, reported expansions, acquisitions, licensing announcements, and explicitly evidenced endings. Separate publication time, ingestion/first-seen time, and event time.

If only first-seen time is available, label it “newly documented,” not “new market entry.” Absence of recent coverage is not withdrawal. Reported announcements are not completed transactions. Do not fabricate a historical timeline from current-only records; explain where historical coverage starts. Stable identifiers and layouts should allow comparison without arbitrary visual rearrangement.

### 4. Explain: visual briefings grounded in the selected landscape

At Milestone A support three bounded questions:

- What connects these selected markets?
- Where is this program or variety documented?
- What changed in this window?

Each produces a compact visual explanation and readable text organized around documented findings, changes, possible implications, and unknowns. Link every factual finding to evidence IDs and underlying sources. Label interpretations separately. Every diagram element and connecting claim must resolve to supported entities/relationships; the model cannot introduce new graph facts.

Implement a deterministic explanation baseline that works without an API key. Optional model-assisted phrasing must use the selected evidence bundle, structured output validation, bounded input/output, timeout handling, and cache keys tied to filters and evidence version. Validate that cited IDs exist and actually support the generated claim; merely checking ID existence is insufficient. If validation fails, fall back to the deterministic explanation. Treat source text as untrusted content, never tool instructions. Keep keys server-side; static hosting requires precomputed artifacts or the existing authenticated backend, not browser secrets.

Free-form chat, predictive recommendations, and autonomous research are outside this release. Do not build a decorative chatbot instead of the visual explorer.

### 5. Export and return to a landscape

At Milestone A export a standalone printable HTML briefing and a vector SVG landscape portrait. Include title, berry/country filters, selected focus, date window, generation time, data version, legend, findings, uncertainties, and numbered source notes with links. Export the selected scope, not just the cropped viewport. Make crowded landscapes fit readable pages/panels. Include a source/relationship CSV for verification.

Milestone B adds or integrates downloadable PDF using existing export infrastructure where available; browser print-to-PDF alone must be labeled as such. Support shareable in-app URLs. Persist saved landscapes only through an existing saved-view facility or a small user-scoped implementation consistent with the app; do not introduce cross-user visibility. Saved views must distinguish current refreshed data from a frozen exported snapshot.

## Shared data and evidence architecture

Reuse the existing database/read models where feasible. A graph database is not required. Choose an additive adapter and derived read model rather than a platform rewrite.

Conceptual entities: company, breeding program, variety, country/region, and relevant platform/IP family only where existing data supports those concepts. Each requires a stable ID, display label, aliases, entity type, applicable berry tags, and source provenance. Prefer canonical registry IDs. Ambiguous names remain unresolved rather than being silently merged; distinguish parent/subsidiary and rebrands.

Conceptual relationships require stable ID, subject ID, predicate, object ID, berry scope, geography scope where applicable, evidence references, provenance, reported/confirmed/contested status, first-seen date, and event/effective dates when known. Evidence requires source URL/title, publication date if known, article/document ID, supporting excerpt or locator, extraction origin/version, and existing review status. Use existing confidence conventions; do not invent precise numeric certainty scores.

Repeated syndicated stories must not inflate independent corroboration. Preserve contradictory sources and date-specific relationships. Historical or ended links should not be silently treated as active. Explain whether the dataset is approved-only or includes unreviewed reporting; default to existing trust policy.

If relationships are not yet durable, implement a bounded extraction/materialization job reusing existing ingestion, with schema validation, deduplication, incremental updates, and idempotent writes. Candidate relations inferred by a model remain candidates until the applicable trust policy permits display. Do not silently rewrite registry facts. Browsing the landscape must not trigger expensive whole-corpus extraction.

Maintain one selection/evidence bundle contract for landscape, change, explanation, and export so filters cannot drift between views. Return data coverage metadata and explicit partial-result/truncation flags. Version cached results and invalidate them when evidence changes. Keep authorization and entity visibility consistent across UI, read API, export, and saved views.

## Milestone A — blueberry review gate

Deliver all five blueberry product capabilities above, with generic underlying contracts. Use real existing blueberry data in the preview. Aim to demonstrate multiple companies/programs/varieties, at least two countries, and a sourced multi-country path when the actual corpus supports it. Do not fabricate completeness to meet a count. Synthetic fixtures belong in tests or an explicitly labeled rehearsal mode, never mixed into production evidence.

If the corpus cannot support Peru/Chile/China, show the truthful partial landscape and use a supported example for the main demonstration. Implement the necessary evidence pipeline within scope; do not substitute a static hardcoded diagram. State corpus limitations separately from software completion.

### Acceptance checklist

- [ ] Open blueberry Landscape Explorer through app navigation.
- [ ] Select multiple countries; see exact local relationships and explicitly labeled shared genetics links.
- [ ] Focus a variety/program; follow a documented path and open supporting evidence for every edge.
- [ ] A shared company mention without genetics evidence cannot produce a genetics link.
- [ ] Filter, focus, reset, and URL reload preserve coherent selection and view state.
- [ ] Date window distinguishes actual events from newly documented evidence.
- [ ] Contradictory/unreviewed/ended relationships use the correct labels and visibility policy.
- [ ] Each preset explanation uses only the selected evidence and distinguishes interpretations and unknowns.
- [ ] No inference provider/key: all essential exploration and deterministic explanations still work.
- [ ] Printable HTML, SVG, and CSV match the selected data and retain evidence/source links.
- [ ] Empty, sparse, ambiguous, loading, failed, and truncated states are understandable.
- [ ] Keyboard/list alternative, mobile, both themes, and existing reader/dossiers work.

### Review packet — required before stopping

Provide draft PR URL or exact local PR body, branch/base/HEAD SHAs, preview URL or exact startup instructions, desktop/mobile screenshots, and one exported blueberry briefing. Include a five-minute walkthrough with explicit data-backed examples, checks run and outcomes, supported relationship/data counts, real-data limitations, and known issues. Ask for feedback on readability, trust, analyst usefulness, and export quality.

Commit a mission status/resume document naming completed work, the exact review gate, remaining Milestone B scope, and relevant implementation decisions. Finish the checkpoint report with: “Blueberry milestone is ready for review. Remaining berries and cross-berry completion are pending your feedback; the full mission remains open.” Await feedback before proceeding.

## Milestone B — finish the same mission after feedback

1. Apply agreed blueberry revisions first, updating shared components.
2. Enable strawberry, raspberry, and blackberry using the same engine. Inspect other berry categories already supported by the app and document inclusion decisions; do not invent categories.
3. Preserve berry-specific relationship meanings and traits. Do not impose blueberry assumptions on strawberry licensing or raspberry commercialization. Use existing trait/sensory records if available; unsupported trait comparison remains an explicit gap.
4. Add an All berries scope and side-by-side comparison of two selected berry landscapes, with common actors highlighted and berry-specific relations kept distinct. Avoid implying varieties are shared across species. Do not rank markets by volume or influence unless appropriate sourced metrics exist.
5. Complete saved views, PDF export/integration, cache/update behavior, and final UX refinements.
6. Run final coverage and regression checks. Report each berry's data sufficiency separately; thin coverage is visible, not replaced with imaginary connections.
7. Update the PR description to describe the final implementation. Make it ready for review with remaining limitations. Do not merge or deploy without subsequent authorization.

## Verification and performance

Use meaningful fixtures/tests for alias ambiguity, country filtering, cross-geography genetics, mention-only false links, syndicated duplicate evidence, contradictory claims, event versus first-seen time, source removal/cache invalidation, partial coverage, export parity, and invalid model output. Verify authorization boundaries where the app has multiple users. Run required repo checks and a real UI walkthrough of core flows; do not rely solely on unit tests or screenshots.

Suggested initial performance budget: a bounded portrait of 100 visible entities/200 relations becomes interactive within two seconds after data arrives; selection/highlighting within 200 ms on a representative laptop. Measure and report test environment, payload sizes, and actual results. Aggregate larger graphs, expose counts, and permit expansion without silently losing evidence. Inspect production constraints before committing to these budgets.

Do not add a graph database, broad infrastructure migration, new production hosting, paid provider requirement, unrestricted web crawler, or generalized ontology editor for this release. Prefer minimal compatible dependencies, additive migrations, feature gating, and a documented rollback that disables the explorer without breaking existing features.

## PR description template

Problem: collected news and entity records are difficult to synthesize into a sourced view of industry structure and change.

Behavior: Landscape Explorer connects documented companies, programs, varieties, and geographies; supports focused genetics tracing and time-aware change views; and exports explanations with evidence and uncertainty visible.

Include final implemented scope, data/read-model changes, screenshots and preview instructions, representative evidence-backed walkthrough, checks and measured performance, migrations/configuration, inference fallback behavior, limitations, and rollback. At Milestone A explicitly label this a blueberry review checkpoint with Milestone B outstanding. Never claim this is already deployed.

## First action for the implementation agent

Inspect the repository and current infrastructure, report the components you will reuse and genuine gaps, then proceed to implement Milestone A. Resolve routine choices autonomously. Ask only about a material unresolved decision that cannot be answered from code or this brief. Deliver working reviewable code before pausing at the required blueberry gate.
