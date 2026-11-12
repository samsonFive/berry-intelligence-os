# Berry OS — coordinated frontend agent workstreams

Revision 3, 11 November 2026. **Dispatch-ready planning only. No implementation agent is authorized to start from this document alone.** The user accepted the IA/consolidation direction and added visual/interaction acceptance; coding, installation, provider calls, data changes and deployment remain unauthorized in this task.

Read [the revised proposal](BERRY_OS_EXPERIENCE_CONSOLIDATION_PROPOSAL.md) and [shared contracts](FRONTEND_CONTRACTS.md) together. Source baseline: `berry-news-recalibration-20261111`, clean HEAD `6734f676a8eff9a24caa8f407ecdd2c415b216e0`. Verify actual canonical/deployed revisions and current repository instructions when implementation is authorized. Preserve the completed audit and its production/local-data distinction.

Also read [VISUAL_INTERACTION_ACCEPTANCE.md](VISUAL_INTERACTION_ACCEPTANCE.md). V1 is a new experience checkpoint alongside unchanged engineering gates G0/G1/G2. Existing state/evidence/persistence/API/ownership contracts remain intact. No broad re-audit is required; only recheck candidate scenario records when the future populated slice is built.

## Decisions shared by every workstream

- Accepted primary destinations: Landscape, Briefing, Workspaces, Learn.
- One React/TypeScript root with a persistent router/provider tree, served by FastAPI under proposed `/app/*`. FastAPI remains authoritative for auth, domain queries, stores and governed actions.
- Actual controlled CopilotKit integration and AG Grid Community adoption are in the flagship scope. No framework/SDK/provider calls or packages are installed by this planning task.
- Existing routes, static published output, canonical records, private stores, trust gates and authored editing workflows remain supported.
- One authoritative investigation contract; Copilot, grids and panels consume it. Ordinary navigation/hover/filtering does not call a model or start acquisition.
- All domain presentation remains source-backed; source approval, claim approval, unverified identity, inferred interpretation and synthetic demonstration stay distinct.
- Public demo scenario: Blueberry; Chile/China/Peru; Fall Creek/Costa. Other actors can be inspected outside scope without silently enlarging it.

- Candidate scenario records must be checked before future use; earlier screenshots are not current-production proof. The default must expose real role-bearing connections and meaningful activity differences before clicking. A roster/news arrangement or generic card wall fails acceptance.
- Developments use active Comparison cohort → otherwise explicit in-scope focus → otherwise applied scope, within existing module filters. Label the active basis; hover/detail inspection does not retarget it and empty results do not silently become general news.
- Complete and review one populated Landscape/Reader/comparison/sensory sequence at V1 before propagating its visual patterns into Briefing, Workspaces and Learn. Independent foundational engineering can continue.

## Coordination model

W0 is the integrating lead. W1–W8 are workstreams, not eight simultaneous agents. With the current four-slot team, run **at most three implementation agents plus the lead**. Combine sequential roles when fewer agents are available. Do not assign overlapping shared-file ownership to accelerate work.

Before each wave, the lead publishes: current contract revision, exact file owners, accepted API/component shapes, dependency versions, integration head and demonstrable acceptance target. Every handoff includes changed paths, exported interfaces, real-data screenshots, tests, remaining limitations and downstream consumers affected. Contract changes go through W0 and the owning agent; consumers do not patch a neighbor's module independently.

## Ownership matrix

All proposed paths are relative to the source repository. They identify future work; no application files listed here were created by the planning task.

| Stream | Exclusive files/areas | Must consume rather than independently edit |
|---|---|---|
| **W0 Integration/backend contract lead** | Shared FastAPI registration (`app/main.py`); central auth/gateway registration; existing `app/services/landscape_workspace.py` writer/schema changes; shared sheet-layout endpoint/schema changes; release integration | Frontend router/state from W1, grid migration mapping from W4, runtime implementation from W6 |
| **W1 Frontend platform/state** | Proposed `frontend/package.json`, lockfile, TypeScript/Vite/build config; all new frontend/runtime dependency manifest edits; `frontend/src/app/`, `state/`, `contracts/`, `api/client`; shell route/provider composition | Visual tokens/primitives W2; detail renderer/focus W5; domain models W3; Copilot implementation W6 |
| **W2 Visual system/interaction primitives** | `frontend/src/design/`, `components/ui/`, shared tokens/styles, preview primitive and motion specifications; necessary legacy theme bridge in Glasshouse/shared CSS | Global router/state W1, Reader domain behavior W5, domain components W4/W7 |
| **W3 Domain query/API adapters** | Proposed `app/investigation_routes.py`, `app/services/investigation_api.py` and bounded panel/comparison serializers; curated source/read-model adapters | Main registration/auth changes W0; existing canonical domain schemas/stores remain unchanged |
| **W4 Landscape/AG Grid** | `frontend/src/features/landscape/`, `features/grids/`; BerryDataGrid, domain cell renderers and layout migration mapping | State/URL W1, tokens W2, APIs W3, storage contract W0, entity/source panel W5 |
| **W5 Detail/Reader/Briefing** | `frontend/src/features/detail/`, `reader/`, `briefing/`; DetailHost behavior, source reading, focus restoration and panel stack | Router writes W1, shared primitives W2, source/body APIs W3, legacy Reader scripts remain outside the React root |
| **W6 CopilotKit** | `frontend/src/features/copilot/`; proposed `copilot-runtime/` runtime code excluding dependency manifests; tool/catalog registration and minimum-context serializer | Root mounting W1, domain components W4/W5/W7, action schema W1/W0, auth gateway W0 |
| **W7 Workspaces/Learn/demo/outputs** | `frontend/src/features/workspaces/`, `learn/`, `demo/`; isolated `app/demo_data/flavor/` and demo adapter; new composite export renderer/routes in isolated modules | Existing save writer/schema W0, existing Workspace editing/revisions, canonical data, domain/detail APIs W3/W5 |
| **W8 Integration QA** | New frontend integration/e2e suites, dedicated backend contract regression tests, screenshots and acceptance records | Production fixes assigned back to owners; no parallel edits of implementation files |

W1 is the **single dependency steward**. W6/W4/W2 submit package requirements to W1. W0 owns deployment integration when later authorized. No agent independently modifies package/lock/build/deployment configuration. Existing comparison presenter changes require W3 ownership and lead review; W4 consumes their models.

## W0 — integration and backend contract lead

**Outcome:** every workstream builds against one coherent, compatible application contract.

Responsibilities:

1. Confirm source/canonical/deployed revision, overlapping active work, route prefix, auth parity and baseline evidence. Preserve runtime mounts; code delivery does not replace persistent data/inbox.
2. Freeze versioned scope/selection/panel/action/result contracts and exact per-module filter applicability before parallel UI work.
3. Own existing shared save and sheet-layout storage changes. Preserve the full envelope through parser → bundle → route serialization → allowlist → restore. Preserve old view kinds/rows and optimistic revision checks.
4. Register W3/W7 route modules and W6's authenticated same-origin runtime gateway. Old paths and public-static output retain their original access and semantics.
5. Integrate branches in dependency order, route shared edits through owners, and verify release gates on the actual final head. No deployment is authorized by this planning document.

Acceptance: full new/legacy save round trips; old links/caps/store meanings unchanged; unauthorized shell/API/detail/export/agent requests denied consistently; source/canonical data files preserved; every shared file has one owner.

## W1 — persistent React shell and shared state

**Outcome:** Landscape, implemented Briefing, saved-investigation/lesson entry views share one mounted application frame.

Responsibilities:

- React/TypeScript with Vite assets and one React Router under proposed `/app/landscape`, `/app/briefing`, `/app/workspaces`, `/app/learn`. FastAPI serves deep-link HTML and build assets; no Next.js requirement.
- Keep navigation, scope, command entry, comparison tray, investigation provider, query client and Copilot provider mounted. Feature routes use an outlet, not another root.
- Own action reducer/dispatcher, investigation revision, URL normalization/serialization, one history writer, per-surface scroll/layout state, request cancellation and cache-key conventions.
- Explicit URL scope overrides cookie defaults. Focus and comparison cohort are independent. Preserve outside-scope/invalid selections for explicit resolution.
- Keep server cache, layout preferences, authored drafts and conversation state separate. Clear private cached results on session change/logout.
- Provide interfaces for W5 DetailHost and W6 Copilot without duplicating their behavior. Do not load legacy `v2.js`, `personal_digest.js`, `site_sheet.js` or legacy global history controllers inside the new root.
- Be the sole editor of dependency manifests, lockfiles, build config and version pinning, including any required runtime package manifest.

Acceptance: root/provider instance survives implemented cross-surface navigation; direct URLs/reload/Back/Forward restore normalized state; normal interaction remains functional without a model; stale requests cannot repaint a new selection; legacy handoffs are clearly bounded rather than represented as persistent shell transitions.

## W2 — Berry visual system and shared interaction primitives

**Outcome:** a distinctive, consistent agricultural intelligence application, including vendor components.

Responsibilities:

- Specify warm neutral reading surfaces, selective botanical accents, editorial and UI typography, tabular numerals, spacing, borders, icons, focus/selection, density and image treatment. Do not retain uniform green panels as the design identity.
- Build common scope controls, entity identity rows, relationship/status labels, findings, citations, buttons/menus, panel frames, command entry and populated/empty/loading/error states.
- Define responsive resizable main/detail panes; preserve readable report widths and useful analytical density. No dashboard-layout builder.
- Implement enterable hover/focus previews using Floating UI; keyboard/touch persistent equivalents, Escape and focus-return behavior. Do not rely on a separate information icon for every field.
- Define restrained CSS/Motion transitions, stable loading layout and reduced-motion policy. Proposed 150–220ms transitions describe orientation, never correctness or a compulsory delay.
- Publish tokens consumed by AG Grid, Copilot output, domain modules, Reader, Workspaces and Learn. Own any legacy CSS/theme bridge without replacing governed editors.

Acceptance: first review initial Landscape, company selected, comparison, evidence and sensory states in the V1 continuous packet, including narrow-screen detail. Propagate accepted patterns to Briefing/Workspace/Learn afterward. No stock-theme clash; readable hierarchy/focus, no hover-only information, no repeated empty sections and fewer exposed toolbars. W2 recommends visual pass/rework; W0 records the gate.

## W3 — curated domain APIs and panel read models

**Outcome:** React receives existing intelligence with precise scope and provenance, without duplicating trust/domain logic.

Responsibilities:

- Reuse Explorer `build_bundle`/portrait context, company backbone/portfolio, company/variety compare, variety intelligence, geography and existing source/news services.
- Return bounded, allowlisted read models for landscape, comparison, entity, exact relationship, developments and source detail. The raw Entity API is not the intended panel model.
- Load the shared corpus once per bounded request/context where possible; do not add full rescans for every card/variety. Fetch large source bodies only for selected detail.
- Carry canonical IDs, original role/direction/status, individual claim/source state, dates/clock, citations, scope applicability and real missing-value semantics. No normalized superiority score.
- Keep focus outside the base-scope graph expansion. Distinguish actor role from edge predicate; monitoring region from commercial country; company location from cultivar growing; source approval from claim approval.
- Supply bounded metadata/list/detail models for native Briefing, saved investigation and existing lesson entry where needed by W5/W7. Legacy authored stores remain authoritative.

Acceptance: same underlying records/citations as existing presenters for the audited cohort; null/unknown preserved; no private raw-attribute dump; no rights-to-growing inference; correctly labeled out-of-scope detail and source discoveries; scope/date tests and bounded performance measurements.

## W4 — Landscape composition and AG Grid

**Outcome:** substantive interactive intelligence at rest, with a professional analytical grid where useful.

Responsibilities:

- Compose initial scope readout, main analytical field and subordinate relevant developments. Show supported company/program/variety relationships, direction/role and activity contrasts before interaction. Never invent intermediate nodes, strengthen source-named roles or replace a roster with generic cards. Scope findings remain about the applied scope when focus/detail changes.
- Implement linked highlighting and Connections/Portfolio/Geography/Comparison renderers over W1 actions/W3 models. Keep existing useful map behavior through a scoped React adapter.
- Build one read-only BerryDataGrid with AG Grid Community; pilot the expanded company-by-variety matrix, then reuse in advanced catalog browsing. Small comparison tables can stay semantic HTML.
- Use canonical row IDs and stable semantic column IDs. Explicit pin/check actions change the shared cohort; row/cell actions open focus/detail. AG Grid selection never becomes a second business store.
- Map existing generated column/view IDs to semantic layouts; serialize only supported preferences or propose the versioned extension to W0. Preserve old rows/conflicts and provide an explicit fallback where mapping is impossible.
- Keep loaded-row filtering distinct from server/full-catalog search. Exports use domain data, not virtualized viewport rows.
- Consume W2 theme tokens; do not independently change global colors/typography. Do not promise Enterprise grouping/pivot/range/Excel behavior in the Community implementation.

Acceptance: before-click relationships and contrasts are readable at V1; AG Grid is a purposeful analytical view. Preserve actual portfolio records/role/status, keyboard/panel actions, cohort/state, layout conflicts, unknowns and full intended export. No double initialization of legacy tables. A roster with adjacent news is insufficient.

## W5 — unified detail, Reader and Briefing

**Outcome:** the same company/variety/relationship/source experience opens from all native surfaces.

Responsibilities:

- Own persistent DetailHost, entity/relationship/observation/source renderers, bounded breadcrumb path, pin/expand/close and focus/scroll restoration. Integrate with W1 router through actions; do not add a history controller.
- Reuse source Article/Brief/media/citation capabilities via W3. Preserve source body limitations, source/claim distinction and original-publisher links.
- Implement Briefing's native read surface and its bounded following/saved/reading entry using existing visual News cards, personal-state APIs and signals. Keep social-specific trust and sampling semantics.

- Before V1, finish the shared detail/Reader and Landscape development-card behavior. Roll those patterns into native Briefing only after experience acceptance; foundational API/auth work can continue independently.
- Coordinate copilot/detail/source panel space; a source can replace panel content while preserving its predecessor. Full canonical pages retain real hrefs/return context.
- Preserve populated content and collapse secondary provenance into usable previews/detail. Material disputed/planned/unverified status remains visible; coverage diagnostics stay intentional.

Acceptance: company → variety → relationship → source → close restores exact context and focus; same component behavior from Landscape/grid/Briefing/Workspace references; Article/Brief/media work; keyboard/touch/narrow-screen operation; no body hydration in unselected cards; no accidental reading/trust mutation from opening detail.

## W6 — controlled CopilotKit integration

**Outcome:** real SDK/runtime interaction over the same investigation and domain components used by direct controls.

Responsibilities:

- Register one curated catalog: CompanySummary, PortfolioComparison, GeographyConnections, RelatedDevelopments, EvidenceDetail, SensoryDemo. Domain owners implement the components; W6 registers tools/renderers.
- Tools carry canonical IDs/selectors and an investigation revision. The backend resolves facts, observations, statuses and citations. Do not let the model invent factual component props.
- Reuse W1 actions for scope, entity opening, typed cohorts, view changes, exact relationship/source and explicit save/open investigation. Reject/reconcile stale model actions after newer user interaction.
- Mount the SDK provider once through W1's composition point. Implement the selected supported runtime/backend adapter behind W0's same-origin auth gateway. Verify supported APIs before pinning; do not assume Built-in Agent streaming shared state.
- Restrict context to necessary authorized scope/IDs and bounded public-source context. Exclude credentials, private employer notes, full Workspace bodies and unrelated personal fields. Ordinary navigation/hover does not invoke a provider.
- Preserve usable direct UI on provider failure/cancel. Separate session conversation from saved investigation selectors. No publication/claim-approval/canonical-edit tools and no required live research.

- Apply components to the existing analytical field/coordinated detail area. Chat may acknowledge/explain actions; it must not duplicate a comparison or assemble a parallel investigation beside the report. V1 verifies direct and Copilot actions lead to the same readable state.

Acceptance: a real approved SDK/provider command “Compare Fall Creek and Costa in China” matches equivalent direct controls in normalized state, URL and displayed records; unknown IDs/unsupported rankings handled honestly; stale response cannot undo user action; no unwanted private context; saved investigation reload works without chat transcript; failure leaves direct flow intact. A fixture-only demonstration is insufficient proof of actual integration.

## W7 — Workspaces/Learn continuity, demo and outputs

**Outcome:** investigations can be retained/presented, with a truthful cross-surface migration boundary.

Responsibilities:

- Build native Workspaces entry for saved investigations and existing authored outputs; reopen context without rebuilding selection. Build native existing-Learn entry/detail consumption sufficient for contextual Explain. Do not rebuild lesson research or authored editors in the flagship.
- Respect existing document drafts, citations, source capture hashes, revision/conflict behavior and generated-content provenance. Full legacy editing remains an explicit expanded compatibility handoff until equivalent adapters are delivered.
- Wire Save investigation to W0's existing saved-Explorer extension; preserve old filters-only saves, live Brief Packs, authored documents and frozen review snapshots as distinct output types.
- Implement an isolated future flavor fixture/loader with fictitious specimen IDs, 1–9, most scores 4–7, when coding/data generation is later authorized. Keep it out of canonical repositories/search/counts. Use one prominent synthetic label per self-contained panel/export; no implication of real commercial-variety measurement.

- Supply that isolated sensory state early for V1, scheduled in an available slot after a bounded W4–W6 handoff. Start with a labeled dot comparison and visible 1–9 axis; extra dimensions/distributions require deliberately defined metric/replicate semantics. Full Workspace/Learn pattern rollout and output work follow V1. No data is generated by this plan update.
- Render one composite cited PDF from validated domain models/context, with content preview, generation timestamp and source appendix. Explicit labeled demo annex only; no silent viewport truncation or changed export audience.

Acceptance: saved context round-trip including nested source ancestry/cohorts; legacy saves unchanged; native shell entries preserve investigation; old editors keep draft/revision behavior; demo exclusion and labeled-annex tests; PDF visual verification and complete intended content/citations.

## W8 — independent integration, visual and accessibility QA

**Outcome:** one coherent application experience is demonstrated rather than inferred from isolated components.

Responsibilities:

- Run direct and copilot-driven versions of the complete investigation. Verify state, filters, sources, auth, legacy links, saves, reload, history and export.
- Verify one provider/router/cache/panel tree across native surfaces, and accurately labeled compatibility handoffs to unmigrated full editors.
- Audit AG Grid layouts/selection, source/trust distinctions, unknown versus zero, synthetic separation, stale-response handling and model failure.
- Capture agreed desktop/narrow-screen states; test keyboard-only/touch-equivalent detail, enterable previews, focus restoration, reduced motion and useful error/loading states.

- Produce the V1 packet: five populated states plus a short continuous interaction recording, current scenario IDs/bases, narrow/keyboard/touch checks and direct-versus-Copilot comparison. Isolated component screenshots or engineering tests cannot substitute for the continuous investigation. Record planned/pass/rework honestly and return defects to existing owners.
- Measure perceived responsiveness with actual data. Proposed targets are immediate local feedback (<100 ms), restrained panel motion (~150–220 ms) and a measured warm-query budget agreed at G1. These are acceptance targets, not existing measurements.
- Check records/static-public integrity and the repository's applicable final-head CI gates when implementation later occurs. Assign failures back to code owners.

Acceptance: all release criteria below have reproducible evidence, remaining limitations are explicit, and no component-only test is presented as whole-app or production proof.

## Dependency waves and integration gates

| Stage | Workstreams / concurrency | Gate |
|---|---|---|
| **G0: contract freeze** | W0 coordinates W1/W2/W3 planning and exact interfaces | State/API/component catalog, panel behavior, layout migration shape, packages/edition and legacy boundaries agreed |
| **Foundation wave** | W1 platform, W2 visual primitives, W3 read models | Authenticated deep link/reload and real-data typed query in one persistent shell |
| **G1: adoption proof** | W4 grid, W5 detail, W6 Copilot in bounded slices | Actual Community grid + shared panel + approved real Copilot tool turn use the same state; versions/topology pinned by W1 |
| **Composition wave** | W4 populated Landscape/grid, W5 detail/Reader, W6 same-investigation Copilot; W7 early demo in an available slot | Relationship-visible-at-rest Landscape → company → variety → compare → source plus isolated sensory state |
| **V1: visual and interaction checkpoint** | W2/W8 review continuous evidence; W0 records pass/rework | Five populated states, desktop screenshots, short continuous recording, narrow/keyboard/touch review; pass before cross-surface pattern rollout |
| **Output/parity wave, after V1** | W5 Briefing rollout; W7 Workspaces/Learn/saves/outputs; W1 hardening and W8 QA scheduled within existing limit | Accepted patterns extend across native entries; saved reopen/PDF/demo and four-surface continuity verified |
| **G2: presentation release candidate** | W0 integrates owner fixes, W8 verifies | Complete acceptance run, visual review, auth/legacy/static checks and actual production smoke after authorized release |

G1 proves chosen adoption rather than postponing it. If provider credentials/integration are unavailable, continue deterministic shell/grid/detail work and report the specific missing dependency. Do not label Copilot complete until its real integration works. Do not replace a failed proof with a mock chat or silently change provider.

V1 proves experience quality separately. A failed V1 holds cross-surface pattern propagation and sends design/behavior fixes to W2/W4/W5/W6/W7 under existing ownership; unaffected foundational engineering can continue. Do not start four implementation agents to add early demo/QA work. Passing V1 does not replace G2 or authorize deployment. Current V1 status is planned/not run.

## Flagship cut and follow-up

**Required flagship:** persistent React shell and native entry routes; complete Landscape; working Copilot command; AG Grid portfolio matrix; shared detail/Reader; bounded Briefing reading; Workspaces saved-investigation reopening; contextual existing-Learn access; isolated sensory demo; dated PDF; coherent visual/motion/accessibility behavior.

**Immediately afterward:** full Briefing view consolidation, broader catalog/map/retail adapters, deeper Workspace/Learn client authoring parity, expanded berry/region combinations, output-library consolidation and layout migration coverage.

**Longer term:** retired duplicate controllers after compatibility proof, richer measured sensory/domain coverage, optional Enterprise features with an explicit need/license decision, and open-ended/declarative generated UI where justified.

Calendar dates require the presentation deadline and available implementation capacity. Reduce breadth/export formats before cutting shared-state correctness, source return, keyboard/touch behavior or demo isolation. No coding, dependency installation, credential setup or deployment is started by this document.
