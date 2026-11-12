# Berry OS — experience consolidation and interactive Landscape proposal

11 November 2026 — **Revision 3: accepted information architecture and strengthened experience acceptance.** Landscape · Briefing · Workspaces · Learn and investigation-centered consolidation are accepted design direction. This revision incorporates the [design review addendum](DESIGN_REVIEW_ADDENDUM.md), strengthens relationship visibility before interaction, and adds a visual/interaction checkpoint before cross-surface pattern rollout. Revision 2's state, evidence, persistence, API, implementation and ownership contracts remain in force, including React, controlled CopilotKit and AG Grid Community.

**Planning documents only: no application implementation, data generation, package installation, dependency-file change or runtime mutation.** Workstream instructions describe future authorized implementation; they do not start it.

Basis: completed design handoff and screenshots 01–12; current source checkout `C:/Users/Johnny/Downloads/sscanar/berry-news-recalibration-20261111`, branch `fix/berry-news-first-page-20261111`, clean HEAD `6734f676a8eff9a24caa8f407ecdd2c415b216e0`. The prior production screenshots remain historical observations; this mission did not reopen production. Existing capabilities below are code-confirmed unless attributed to those screenshots. All new composite interactions are proposed and runtime-untested.

## 1. Accepted direction: four primary destinations

Use the accepted **Landscape · Briefing · Workspaces · Learn** structure. Learn answers a distinct educational question, has real lesson/research/editing workflows, and the current product requirement explicitly preserves it at top level (`docs/v2/feature-requests/LEARNER-MODE.md`, September 30 addition). The flagship sprint requires no Learn rebuild or live research. This accepts the design direction, not implementation completion.

| Primary destination | Independent job | Boundary |
|---|---|---|
| Landscape | Understand actors, genetics, markets and connections within an investigation | Scope, selection, analytical views and inspectable evidence |
| Briefing | Discover and read what is changing, including followed developments and signals | Reading/following state; a story or alert does not approve a claim |
| Workspaces | Develop, organize, save and present analysis | Authored documents, saved investigations and explicit output types |
| Learn | Understand how and why crops, production systems and sensory science work | Educational knowledge, distinct from competitive Evidence/Signals |

Current live navigation: **News · Personal Digest · Map Explorer · Social Listening · Workspaces · Global Watchlist · Companies · Learn**, plus overlapping landscape/report tools in More. Proposed utilities: Search and More → Browse / Research tools / Review / Operations / Settings / Help. Preserve the separate public-static navigation and authentication gates. No new private surface becomes public through the shell change.

## 2. Disposition of existing experiences

Consolidation changes working surfaces and entry points; it does not merge stores or erase existing links.

| Current experience | User job | Proposed location / interaction | Unique capability to preserve | Dependency or risk |
|---|---|---|---|---|
| Landscape Explorer | Trace actors, markets and genetics through sources | **KEEP / promote** as Landscape anchor | Country matrix, portfolio connections, exact-edge evidence, source/date semantics | Requires common state and richer entity panels |
| Global Watchlist | Find organizations and sustain monitoring | **MERGE** roster/saved-scope entry into Landscape; **EMBED** tracking in company detail | Captured News, private corrections, groups, imported tier provenance | Monitoring intent and private classification must not become commercial facts |
| Configurable Landscapes | Compose a selection of existing intelligence | **MERGE** compatible section adapters and saved scopes into Landscape; output composition in Workspaces | Section selections and multi-berry company/variety scope | Existing downstream handoffs can drop countries/custom dates; preserve old semantics |
| Global Berry Landscape | Understand four-crop value chains and milestones | **EMBED** supported milestone/value-chain modules later; **RETAIN** advanced global/coverage browse | Public-source gate, typed footprint, source-checked supplements | Some supplements are not canonical Evidence; no untyped union or doubled counts |
| Company directory | Find/select actors | **RETAIN** Browse companies; default selection through Landscape search | Catalog filters, aliases, status and pagination | Full browse remains accessible; not a new primary destination |
| Company dossier | Investigate one actor | **OPEN** company panel; Expand opens full dossier with return context | Reviewed backbone, news, roles, people and profile distinctions | Existing profile links discard originating scope |
| Company portfolio | Inspect genetics access | **EMBED** populated portfolio in company panel; expanded matrix when needed | Breeder/owner/licensee/marketer/grower distinctions | Source-named variety is not an approved company role |
| Variety directory | Find/select cultivars | **RETAIN** Browse varieties; default searchable selector | Codes/aliases, status, deep search and coverage tooling | Catalog breadth is not depth of reviewed intelligence |
| Variety Competition | Compare portfolio/trait context | **MERGE** into Landscape portfolio/comparison renderer | Role, rights and sourced observation presenters | Mixed trial methods remain separate observations |
| Retail observations | Inspect sightings and listings | **EMBED** when populated; **OPEN** observation detail | Retailer/market/date/product context; unnamed-variety records | Retail market does not prove growing location |
| Standalone company comparison | Compare selected companies | **MERGE** into Landscape comparison; old URL remains an expanded entry | Existing five-company presenter, role matrix, invalid-ID handling | Preserve old five-company links |
| Watchlist comparison | Compare roster selections | **MERGE** entry action into same cohort | Scoped developments and tracking context | Old saved Watchlist filters exclude cohort |
| Variety comparison | Compare selected cultivars | **MERGE** into same investigation, separate variety cohort | Four-variety sourced dimensions and missing-value semantics | Never synthesize a common performance ranking |
| Map Explorer | Inspect geographic patterns | **EMBED** Geography view; **RETAIN** full map expansion | Separate news/company-location/variety-growing layers | Header must declare geographic basis |
| Geography profiles | Investigate a place | **OPEN** geography panel; Expand for complete profile | Organizations, observations, IP and evidence by basis | Company presence never propagates automatically to varieties |
| News | Discover developments | **MERGE** as Briefing default | Existing visual cards, media, grouping, dates and trust labels | Preserve source approval versus escalated claims |
| Personal Digest | Follow, save and finish reading | **MERGE** as Briefing Following / Saved / Reading views | Personal subscriptions and reading state | Reading/save state remains independent of trust |
| Source Reader | Inspect a source | **OPEN** one shared persistent Reader | Article/Brief, native media, excerpts and citations | Return must restore investigation, not default to Digest |
| Workspaces | Author and organize | **KEEP** primary | Nested cited blocks, versions, captures and linked landscapes | Existing private SQLite and conflict handling remain authoritative |
| Reports | Produce authored analytical output | **MERGE** into Workspaces report library/actions | Edited sections, citations, generated-draft provenance | No silent regeneration or automatic provider call |
| Brief Packs / readouts / war-room | Assemble and present a briefing | **MERGE** into Workspaces output library/presentation actions | Live composition versus dated export | A live pack is not a historical snapshot |
| Social Listening | Inspect social conversation | **MERGE** entry into Briefing Social; **RETAIN** advanced analytic expansion | Native media, perspective/role distinctions, sampling context | Social posts remain distinct from News and verified facts |
| Monitor | Notice tracked change | **EMBED** following/alerts in Briefing; configuration secondary | Watch/alert routing and collection status | Following is not evidence of activity or confidence |
| Intelligence registers / strategic questions / moves / whitespace | Inspect interpretation and lineage | **EMBED** relevant items; **RETAIN** advanced registers | Distinct statements, Signals, Assessments, Recommendations; coverage-first whitespace | No generic undifferentiated insight object |
| Competitive evaluation | Conduct governed capability assessment | **RETAIN** advanced Landscape research tool | Ordinal 1–5 rubric, scope compatibility, analyst decisions and frozen cited snapshots | Separate from live portfolio comparison and synthetic flavor 1–9 |
| Global Berry Strategy Review | Review a scoped interpretation | **RETAIN** advanced reviewed output, linked from Workspaces/Landscape | Basis snapshot/hash, staleness, approval and history | Cannot become a filters-only saved view |
| Learn | Build understanding | **KEEP** fourth primary; contextual Explain leads into lessons | Educational identity, visual lessons, explicit research/edit/version flow | No lesson research required for demo |
| Ask Berry OS / contextual research | Start optional bounded research | **RETAIN** explicit contextual action; **DEFER** demo orchestration | Provider scope, citations and live/unreviewed split | Hover, selection and navigation never start research |
| News packets | Capture/export a batch | **RETAIN** secondary Briefing capture/export | Capture diagnostics and packet JSON | Collection action is distinct from reading |
| Identity / source / claim / signal review; coverage; collection/settings | Curate and operate | **RETAIN** secondary Research / Review / Operations | Trust gates, private state and completeness diagnostics | Presentation cleanup must not remove these capabilities |

Important landscape differences: Watchlist combines organization discovery with captured News and private intent; configurable Landscape composes selected published records/sections; Global Berry Landscape adds public-source supplements and reviewed strategy snapshots; Explorer traverses typed relationships and their sources. Reuse each through an explicit adapter. Do not add their totals together or call every row trusted.

## 3. Composite Landscape

Use **Landscape Explorer's bundle, APIs and interaction semantics as the domain foundation**, rendered within the new persistent React application. Its cached bundle, typed edges, portfolio context and persistent evidence aside already exist (screenshots 08 and 12). Recompose those data into an intelligence report. The existing Explorer route remains a compatible legacy/expanded destination; do not embed its complete page inside the new shell.

Candidate presentation scope: **Blueberry · Chile / China / Peru**, with **Fall Creek and Costa**, from the earlier audited matrix. Recheck these current authorized records and sources when implementation is separately authorized; earlier screenshots are not proof of current production content. Do not fabricate or strengthen a connection to preserve the rehearsal. Driscoll's remains a useful outside-scope dossier example, not an actor silently inserted into the regional scope. Initial dates: all recorded developments, ordered by genuine publication date; no arbitrary recent window that hides the required source.

Exactly **three complementary modules** are visible initially:

1. **Scope readout — what this scope shows:** two or three short, cited findings naming actors, activities or relationships. Reuse deterministic Explorer findings; evidence counts, missing-field messages and unsupported strategic conclusions do not lead. These describe the applied scope; selecting a company or opening detail does not redefine them.
2. **Main analytical field — connected companies and genetics:** the visual center. Use compact aligned relationship bands exposing explicit company → program → variety connections, exact role/direction and concise geographic activity wherever supported. A direct company → variety edge does not require an invented intermediate program. A source-named cultivar remains separate from an approved role. The candidate Fall Creek validation/planned-entry versus Costa reported growing/licensing contrast should be understandable before clicking, if current records still support it. An intentional matrix is preferable if it explains the actual connections more clearly. A roster with news, a generic card wall, a KPI wall or decorative unnamed links fails the default experience.
3. **Relevant developments:** a bounded, subordinate set of existing visual News cards. Apply module scope, then use active Comparison cohort → otherwise explicit in-scope focus → otherwise applied scope. Name the active basis in the heading. Hover or relationship/source/descendant-detail inspection does not retarget the rail. No matches produces one honest state plus scoped Briefing access; never silently substitute an unfiltered feed. Co-mentions remain labeled.

The main analytical field changes renderer among Connections, Portfolio, Geography and Comparison. These are coordinated views over one scope and selection, not whole existing destinations placed in tabs. It has one expanded analytical task at a time. Sensory demo explicitly replaces that field when chosen, without appending another large section below it.

Keep a compact scope bar and one organized command area. Advanced filtering, layout and operations stay deliberate actions rather than multiple stacked toolbars. The exact relationship rendering and the five required review states are specified in [VISUAL_INTERACTION_ACCEPTANCE.md](VISUAL_INTERACTION_ACCEPTANCE.md).

| Module / user question | Supporting data | Existing reuse | Interaction |
|---|---|---|---|
| Readout: what is consequential here? | Typed location/relationship records and cited findings | `build_bundle()`, `add_portrait_context()` and Explorer takeaways | Hover/focus a statement for source context; click opens exact relationship/source |
| Connected field: who connects to which genetics, in what role? | Authored actor roles, programs, varieties and explicit edges | Explorer portfolio/neighborhood data; company backbone/portfolio presenters | Real role-bearing paths and activity differences visible before click; selection highlights and deepens them |
| Portfolio: what links these actors to cultivars? | Six commercial role buckets and cited cultivar records | `present_company_portfolio()`, `present_company_compare()` | Company cohort columns and real role-labeled entries; cultivar click opens detail |
| Geography: what kind of activity is recorded where? | Company locations, growing entries, source mentions, rights records | Explorer country matrix; Map Explorer SVG and region services | Choose a declared layer; cell/country opens geography or relationship detail |
| Comparison: how do selected companies/varieties differ? | Existing role, rights, trait and footprint presenters | Company Compare and Variety Compare | Replace main field; preserve both typed cohorts and current investigation |
| Developments: what changed for this selection? | Actual entity links, explicit berry/geography tags, published dates | `_news_cards.html`, current news services and shared Reader | Comparison cohort → otherwise in-scope focus → otherwise scope; explicit heading, no silent broadening |
| Sensory demonstration: how do synthetic specimens differ on the declared metric? | Separate future synthetic specimen fixture only | Existing trait/compare visual patterns plus a new isolated adapter | Labeled dot comparison, visible 1–9 axis, fictitious specimens, own cohort; extra dimensions/distributions require explicit schema support |

Definitions: **Shared context** is applied scope, focal entity and comparison cohorts. **View** is the current analytical representation. **Detail** is a company, variety, geography, relationship, observation or source in the contextual panel. **Output** is a saved investigation, authored document or dated export. Changing detail never silently changes the base scope or comparison cohort.

## 3a. Adopted frontend architecture

Build **one React + TypeScript application**, with Vite assets served by the existing FastAPI deployment. Proposed private entry routes are `/app/landscape`, `/app/briefing`, `/app/workspaces` and `/app/learn`. A single root, router, investigation provider, request cache, Copilot provider and panel manager stay mounted across implemented client surfaces. Next.js and a backend rewrite are not prerequisites.

| Decision | Planned implementation | Boundary |
|---|---|---|
| Shared shell | React/TypeScript, Vite build, one React Router instance | FastAPI serves authorized HTML/deep links and compiled assets; old Jinja/public-static routes remain |
| Application state | Validated context reducer/provider with URL serialization | Scope, focus, cohorts, lens and detail are authoritative here; no second Copilot/Grid business-state store |
| Server-data loading | One TanStack Query client over existing/new bounded read APIs | Scope-aware cache, cancellation, stale-response guards and logout invalidation; separate from authored drafts/layout preferences |
| CopilotKit | Actual SDK/runtime integration using controlled tools and a curated component catalog | Explicit commands operate over existing data; no live research required, model-supplied factual props or automatic trust actions |
| AG Grid | Community edition first; shared React adapter for expanded portfolio matrix, then advanced catalogs | Custom Berry theme, read-only canonical intelligence, semantic row/column IDs; simple tables and existing Workspace editors remain |
| Context previews | Floating UI interaction primitive | Enterable hover/focus previews, keyboard/touch persistent detail and predictable dismissal |
| Motion | Short CSS/Motion transitions in React; reduced-motion support | Orientation, panel/lens changes and selection feedback; no decorative motion or animation-dependent correctness |
| Legacy continuity | Existing pages remain functional and receive explicit return-context links | Unmigrated full editors are compatibility handoffs, not falsely advertised persistent React experiences |

The frontend platform owner is the only editor of new package manifests/lockfiles/build configuration, including agreed Copilot runtime dependencies. Versions are pinned together after the authenticated integration proof; feature agents do not install competing versions independently. A minimal Copilot runtime, if required by the selected supported SDK path, sits behind a same-origin authenticated gateway. It does not replace FastAPI's authorization, records or persistence. Do not assume that CopilotKit's Built-in Agent supports streaming shared state; Phase A can use read-only context and validated tool actions without relying on that feature.

The new root must not execute legacy global Reader/history/grid controllers. Reuse backend view models and capabilities through React adapters. One router writes history; one panel manager controls entity/source/copilot space and focus. Separate layout preferences, cached server results, investigation selection, authored-document drafts and conversation history. No private corpus or credentials enter compiled assets or URL parameters.

### Controlled CopilotKit behavior

Expose typed actions for set scope, open entity, add/remove/set comparison cohort, change lens, show exact relationship, show source, and explicit save/open investigation. Buttons, grid cells, map elements, narrative links and Copilot tools call the same dispatcher. Tool arguments contain canonical IDs/selectors; the authorized backend resolves factual values, status, source references and display models. Domain owners supply CompanySummary, PortfolioComparison, GeographyConnections, RelatedDevelopments, EvidenceDetail and SensoryDemo; the Copilot agent registers them instead of building a second UI family.

Every command carries an investigation revision. A model result arriving after a newer user action cannot overwrite that action; reject/reconcile the stale command. Normal selection, hover, navigation and filtering never make model/provider calls. Send minimum necessary authorized scope/IDs and bounded source context, excluding credentials, account details, private employer notes and entire Workspace bodies. Copilot conversation is a separate session artifact, not content in selector-only saved views. Provider errors leave direct investigation fully usable. Unrestricted generated HTML/JavaScript and experimental declarative surfaces are later extensions, not flagship dependencies.

Copilot operates the existing investigation canvas/detail allocation. A comparison command changes the shared cohort/lens and renders the same domain comparison; chat may acknowledge/explain the action but does not duplicate the full comparison as a parallel report. Do not make a permanent chat feed compete with company/source drawers. Actual SDK integration and visual/interaction quality have separate acceptance gates.

### AG Grid adoption and preserved behavior

Retain the Smartsheet-like interaction contract—readable full text, frozen identity, resizing/reordering, selection, useful cell actions and saved layouts—while replacing the demanding read-only grid implementation. Begin with the expanded company-by-variety portfolio matrix. Row/cell activation opens detail; explicit checkbox/pin actions modify the cohort. Grid filters over loaded rows are labeled separately from whole-catalog/server scope. Virtualized screen rows are never the export data source.

Current layouts use generated `c{index}-{hash(title)}` IDs and view keys derived from pathname/header titles. Their storage accepts widths/order/hidden/string filters/revision; raw AG Grid GridState does not fit. Introduce stable semantic `colId`/canonical row IDs, an explicit legacy mapping and a narrow serialization adapter or additive versioned extension. Preserve old rows and conflict handling; unmapped preferences get an explicit fallback. The grid owner writes mapping code; the integration lead owns shared storage/API changes. Grouping, pivoting, range operations, styled Excel export and enhanced spreadsheet clipboard behavior require an explicit Enterprise feature/license decision; they are not Phase A promises.

References checked 11 November 2026: [Vite backend integration](https://vite.dev/guide/backend-integration), [React Router](https://reactrouter.com/start/declarative/installation), [TanStack Query caching](https://github.com/TanStack/query/blob/main/docs/framework/react/guides/caching.md), [CopilotKit controlled tool rendering](https://docs.copilotkit.ai/generative-ui/tool-rendering), [state-rendering support boundary](https://docs.copilotkit.ai/generative-ui/state-rendering), [AG Grid editions](https://www.ag-grid.com/javascript-data-grid/community-vs-enterprise/), [AG Grid theming](https://www.ag-grid.com/javascript-data-grid/theming/), [Floating UI hover](https://floating-ui.com/docs/usehover), [Motion layout](https://motion.dev/docs/react-layout-animations). These support the approach; Berry OS integration remains untested.

## 4. One continuous investigation

1. Open Landscape; apply Blueberry and Chile/China/Peru with the country basis visibly identified as recorded company connections. This updates the readout, actor field and scope-relevant developments together.
2. Select Fall Creek. Its populated summary opens in the right panel. Highlight connected programs/varieties and typed country activity; retain other actors for comparison.
3. Select a linked cultivar from its portfolio. Replace the detail panel with that variety, retaining Fall Creek as investigation focus and a clear Company → Variety breadcrumb. Growing locations remain distinct from the company's locations.
4. Open Fall Creek's Chile relationship, then its supporting source. Panel breadcrumbs preserve the company/relationship path. Close returns to the prior detail and triggering control.
5. Add Fall Creek and Costa with explicit **Add to comparison** controls. A persistent cohort tray shows both. Selecting an actor to read never automatically pins or removes it.
6. Choose Compare companies. The main field becomes the existing role/portfolio comparison; geography highlights the selected countries while the panel can still inspect a cultivar or connection.
7. Open the relevant BluGenix development. Reader reuses Article/Brief, source/trust labels and canonical company/variety links. Opening evidence does not reset the comparison.
8. Close Reader or choose its visible return breadcrumb. Restore the same lens, scope, cohort, panel predecessor, scroll and focus. No Browser Back dependency.
9. Save investigation, then open it from Workspaces. Reload reconstructs selectors/cohorts/view against current authorized records. Export produces a dated, cited PDF with an explicit contents preview. Synthetic material is included only by selecting a labeled demo annex.

Required integration: introduce the persistent React root and shared components; adapt existing entity links while retaining real hrefs; add allowlisted panel read models; replace ephemeral checkbox state with typed cohorts; isolate base scope from focal-entity expansion; route the React Reader through the shared history contract; preserve context on Expand/Return links; add versioned save fields and composite PDF. Do not use iframes or copy complete pages into panels. Direct controls and Copilot commands must produce the same normalized investigation.

## 5. Shared state, scope and saving

### Proposed contract

Use **`ctx_v=1`** in the new `/app/landscape` route, with explicit adapters for supported existing Explorer/Watchlist/comparison links. The original routes and unconverted parameters retain their current semantics. The URL is authoritative for applied state; explicit URL scope wins over berry cookies/stored defaults. Local preferences may retain layout, never replace a deliberate scope.

| State | Contract |
|---|---|
| Scope | Single berry, All, or existing advanced berry-pair mode; canonical country IDs plus a named geography basis; authored `actor_roles`; optional news-publication interval |
| Selections | `focus` is the focal actor. Separate `cohort_companies` (max 5) and `cohort_varieties` (max 4), canonical/deduplicated IDs in stable chosen order |
| View | `lens=connections|portfolio|geography|comparison|sensory_demo`; comparison subtype company/variety |
| Detail | Typed `detail_type` + `detail_id`; an optional bounded `detail_path` contains only typed ancestor IDs, so reload/shared URLs restore panel breadcrumbs. Existing `edge` and Reader `story` supported through adapters; trigger/scroll tracked by the same coordinator |
| Search | `q` plus `q_scope=in_scope|catalog`; selector searches canonical names/aliases/codes. Loaded-table text filtering is a separate labeled local control |
| Output reference | Saved-view ID/revision as reference; URL state remains explicit. Reopening a live saved investigation re-queries current data |

Do not reuse **`compare`** for companies: current Explorer uses it for the second berry. Do not treat relationship `predicate` as an actor-role filter: current edge filtering can remove `operates_in` when selecting `develops`. Old Watchlist monitoring-region/group/tier/source/tag selectors also require explicit per-module adapters; do not translate monitoring region into a commercial country filter. Keep unmapped specialist selectors and their original route accessible, show their applicability, and do not claim an equivalent converted scope until that adapter is implemented. Phase A uses the supported explicit demo scope; old URLs keep their existing renderer/semantics.

Integrated company comparison adopts the existing **five-company** presenter; variety stays **four**. Existing Watchlist comparison keeps its legacy four-company limit. Old standalone `?ids=` links remain functional. When imported/linked state exceeds a supported cap, preserve the IDs and report overflow with explicit split/open actions; never silently trim a cohort. Deleted/unresolvable IDs stay visible as selection issues with removal actions.

A scope change retains pinned out-of-scope subjects with an Outside scope label and explicit include/remove actions. Focusing an outside-scope search result opens its detail without enlarging the base actor universe. This requires a wrapper because current Explorer adds focus to graph seeds. Expanded profile detail can show all captured information, explicitly labeled beyond the current scope.

### Filter applicability

| Module | Berry / actor role | Country meaning | Date meaning | Selection behavior |
|---|---|---|---|---|
| Connected field/readout | Limits eligible actors/edges by explicit supported scope | Declared company-connection basis, activity labels retained | Standing relationships remain; advanced chronology has its own clock | Focus highlights; does not redefine universe |
| Portfolio | Berry filters varieties; company role limits actor discovery | Country selected the actors; it does **not** establish where their varieties grow | News dates do not remove portfolio links | Focus/cohort chooses companies; all real relationship roles remain distinguishable |
| Geography | Applies only supported entity/berry filters | Explicit layer: source mentions, company locations, variety growing, rights; HQ and monitoring scope separate | Observation/as-of date only where available; distinct from news publication | Cell opens exact basis/source; no inherited cultivar footprint |
| Comparison | Typed cohort retained; berry narrows relevant portfolio observations | Highlight/annotate matching geography; clearly label all-profile context | Only recent-development subsection follows news dates | No hidden pruning or common superiority score |
| Developments | Explicit berry/entity tags; actor-role selection resolves eligible IDs | Source geography is a mention unless stronger basis is recorded | `news_from/news_to` means source publication; capture shown separately | Focus/cohort-linked records first; co-mentions labeled; no invented links |
| Sensory demo | Only a demo fixture's own declared berry can apply | Country/actor filters inactive and visibly not applied | No real-world measurement date implied | Uses demo specimen cohort, independent of real company/variety cohorts |

At each module, one compact scope subtitle states applicability. Rename the common date control **Development dates**, not a universal Time filter. Current Explorer “documented” time means first captured; preserve Published / Effective / First captured as advanced explicit clocks. Unsupported filters remain visible as not applied or are disabled for that lens; never silently pretend they affected every module. Pure scope readout findings keep their standing-relationship basis; only development-derived findings follow the publication interval.

### History, direct links and saves

The new React Router is the single history writer. Shared actions request push navigation for deliberate scope/lens/cohort/detail transitions and replacement for typing/normalization; feature modules do not call raw history independently. Back/Forward and reload reconstruct state without duplicate loads. Legacy Explorer uses replace-only and legacy Reader owns story history, so neither global controller is mounted inside the new React root. The React Reader adapter joins the shared router/panel contract. Close restores parent detail, analytical view and focus; request revision/abort guards reject stale responses.

Anchor links continue to support direct pages/new tabs. Expand appends an allowlisted same-origin `return_to` for the full investigation URL; Return to investigation is explicit. An independent entity URL opens its normal dossier without fabricating an origin. Sharing a URL grants no access; existing authorization still applies.

| Save/output type | Exact meaning |
|---|---|
| Existing saved Watchlist/configurable view | Existing filters/composition semantics retained; old rows not rewritten |
| **New Save investigation** | Applied scope, typed cohorts, focus, lens and useful panel detail, stored as IDs/selectors; reopens current data, not a frozen conclusion |
| Workspace / authored report | Versioned user-edited content and citations; captures can retain source snapshots/hashes; never silently regenerated |
| Brief Pack | Existing live selection/composition semantics retained |
| Dated PDF/export | Frozen rendered output with generated-at time, scope, selected entities, trust/date labels and source appendix |
| Competitive evaluation / Strategy Review snapshot | Existing immutable/reviewed basis, versions and approval semantics retained |

Minimal persistence change: preserve and validate the full versioned envelope through **request parser/wrapper → bundle/context filters → save-route form serialization → `save_view` allowlist → restore**. Extending `EXPLORER_FIELDS` alone is insufficient: current `build_bundle.selection()` reconstructs known keys and would drop the new fields before the final allowlist. Extend the existing supported `kind=explorer` path with `ctx_v` and context keys while retaining outer store/version and revision checks. Translating an old Watchlist/overview uses **Save investigation as new**, leaving the original intact. No unsupported store kind, broad migration or source-body persistence in saved selectors. Test full new-envelope and legacy round trips, including both load and re-save.

## 6. Progressive detail and visual direction

| Element | At rest | Hover / keyboard focus | Click / tap | Expand |
|---|---|---|---|---|
| Company | Name, real role(s), relevant genetics/activity and material state | Short sourced description; relevant dated development; source basis | Populated company panel with portfolio and related developments | Full dossier/portfolio, carrying return context |
| Variety | Canonical/commercial name, berry, explicit company role and available useful observation | Original observation scale, source and trial context | Variety panel with populated traits, roles, rights and location evidence | Full profile/trait comparison |
| Geography | Place + activity type: office, operating, R&D, planned, growing, rights | Which relationship or observation supports the label and its date | Place/relationship panel | Complete map/geography profile |
| Relationship | Role, direction and materially important status (including disputed/planned) | Supporting source/excerpt, date, confidence and caveat | Persistent exact-edge evidence | Full source/lineage or advanced relationship table |
| Sensory demo | Panel-level synthetic label, fictitious specimen names, 1–9 display | Demo attribute explanation and exact synthetic value | Persistent specimen explanation/comparison | Labeled demo-only comparison/export annex |

Hover/focus previews are small, enterable surfaces with a short dismissal grace period; they remain open while the pointer or focus is inside. Escape closes; focus returns to the trigger. The same name/cell opens persistent detail on click/tap; keyboard Enter/Space works. No hover-only content or separate information icon on every field. Deep navigation and actions belong in the persistent panel.

Hover/focus does not change scope, comparison membership or history. Company, variety, relationship, source and Copilot output use one coordinated area; at narrower widths use an intentional focused detail state with an explicit return. Repeated evidence inspection preserves parent detail, scroll and focus rather than reconstructing the comparison.

Suppress empty sections in presentation mode; use one intentional no-results state only when an entire selected module has no content. In comparisons use an em dash with an accessible Unknown / no recorded observation explanation, never numeric zero. A real observed zero retains units/context. Research coverage mode exposes missing fields, unverified candidates, source-body gaps, identity work and collection diagnostics. Do not hide material status: breeder versus owner, source-named versus approved role, planned versus operating, disputed versus settled, and synthetic versus measured remain intelligible at rest.

Create a deliberate Berry design system, using the current light/botanical direction as a starting point rather than preserving the uniform green wash. Use warm neutral reading surfaces, selective sage/forest accents, stronger editorial headings, readable UI typography, tabular analytical numerals, consistent spacing/borders/icons and unmistakable selection/focus states. Favor meaningful company/fruit imagery with existing reuse permission. Avoid repeated stock cards, decorative heroes and invented cultivar photography. AG Grid, Copilot output, Reader, Workspace and Learn components all consume these tokens; their stock themes do not become the product identity.

Define reusable entity identity rows, relationship labels, scope controls, findings, citations, populated summaries, table tools, command entry and empty/loading/error states. Resizable main/detail panes and per-surface scroll/draft retention support different tasks. A complete dashboard builder is outside the presentation scope. Contextual detail, Copilot and source reading share coordinated space rather than stacking competing drawers. Tables preserve readable full text, gridlines, frozen identity and useful controls in analytical views.

Loading is local to the changing module; preserve layout and the last useful content only with an accurate Updating state and applied-scope label. Never display stale records under a newer entity title. Cache authorized read models by applicable scope, cancel superseded work and preload bounded metadata on deliberate intent. Brief 150–220ms panel/lens transitions are a design target, not measured performance; honor reduced motion and keep correctness independent of animation. Existing server-rendered transitions may receive progressive enhancement later. No ordinary hover/navigation starts AI or collection.

### Sensory presentation acceptance

Begin the isolated demo with a labeled dot comparison of fictitious specimens, a visible 1–9 axis and one deliberately named synthetic metric. Additional dimensions require deliberate fixture semantics; sweetness intensity, acidity intensity and liking are different measurements. Distribution views require explicit synthetic observations/replicates rather than an invented distribution from a single value. Use one prominent label per self-contained panel and standalone output, with fuller context in preview/detail. All existing demo isolation and export contracts remain unchanged.

### V1 — visual and interaction checkpoint

Add [V1 experience acceptance](VISUAL_INTERACTION_ACCEPTANCE.md) after the first populated Landscape composition and early sensory state, alongside the unchanged G0/G1/G2 engineering gates. **Do not propagate these patterns across Briefing, Workspaces and Learn until V1 passes.** Independent foundational engineering can continue.

Review five states: initial Landscape, company selected, comparison, evidence and synthetic sensory. Require five populated desktop screenshots, a short continuous interaction recording, a narrower-layout review and keyboard/touch-equivalent detail/return behavior. Compare direct controls with a Copilot command operating the same investigation. Attractive isolated components and SDK/test success do not establish experience quality.

Recheck only current authorized scenario records when implementation is later authorized; the earlier audit is a reference, not current-production proof. W2 recommends visual acceptance, W8 records continuous evidence, and W0 tracks pass/rework and prevents premature pattern rollout. Defects return to existing owners. **Current status: planned, not run.** No implementation or provider call is authorized by this checkpoint specification.

## 7. Before/after wireframes and update map

Current screenshots: **01–02** roster/selection; **03** separate comparison; **04–05** company/portfolio detail; **06–07** directory/profile; **08** matrix; **09** geography; **10/12** source/evidence; **11** authoring.

### Initial desktop — proposed

```text
berry intelligence     LANDSCAPE   Briefing   Workspaces   Learn     Search  More
Blueberry ▾  Chile · China · Peru ▾  [Company connections]  Development dates ▾
Find a company, variety or program…    Views ▾    Save investigation   Export

WHAT THIS SCOPE SHOWS
Two or three cited findings; named actors and activity, rather than KPI tiles.

MAIN ANALYTICAL FIELD                        RELEVANT DEVELOPMENTS
Actor → recorded role → genetics             Bounded visual News cards
Fall Creek → Breeder → Cargo / Blue Ribbon   Active basis named in heading
  Chile: validation | China: planned entry   Cohort when comparing;
Costa — recorded program connection          otherwise in-scope focus;
  Costa Variety Improvement Program          otherwise applied scope
  China: growing/licensing reported
Source-named BluGenix cultivars remain a separate, labeled association.
These candidate record examples require a current authorized check before use.

Connections / Portfolio / Geography / Compare / Sensory demo
The chosen renderer replaces this main field; full tables expand when needed.
```

### Company selection — proposed

```text
Same scope + Connections view + saved comparison tray
CONNECTED FIELD (other actors remain)     COMPANY PANEL: Fall Creek
Selected company's paths highlighted      Populated summary + explicit roles
Related developments update               Programs / linked varieties / activity
                                         Add to comparison · Expand profile
```

### Comparison — proposed

```text
Cohort: [Fall Creek ×] [Costa ×] [+ Add company]       Companies / Varieties
MAIN FIELD: role/portfolio comparison        DETAIL PANEL (optional)
Actual named genetics and roles              Selected variety/relationship
Geography/activity differences               preserved independently of cohort
Source-linked real observations
RELEVANT DEVELOPMENTS: selected companies; visible publication window
```

### Evidence — proposed

```text
Comparison, scope and cohort stay in place   SOURCE READER
                                            Costa → China connection → Source
                                            Article / Brief
                                            Supporting statement + source text
                                            Method/confidence detail on demand
                                            Close → prior detail, scroll, focus
```

```text
APPLIED SCOPE ───> readout + eligible actors + eligible developments
FOCUS ──────────> path highlighting + entity panel
COHORT ─────────> comparison + saved/output selection
DEVELOPMENTS ───> active Comparison cohort; else in-scope focus; else scope
LENS ───────────> main analytical renderer only
DETAIL ─────────> persistent panel only (source is a detail subtype)
SAVE ───────────> selector snapshot in existing private saved-view store
AUTHOR/EXPORT ──> explicit document or dated artifact
```

## 8. Presentation sprint and coordinated workstreams

### A — required flagship release

Deliver a complete populated investigation using the candidate Blueberry / Chile-China-Peru / Fall Creek-Costa scope after checking its current authorized records. Validate Landscape at V1 first, then extend its accepted patterns across the bounded native Briefing reading, Workspaces saved-investigation/output entry and existing-Learn access. Actual controlled CopilotKit and AG Grid Community integration remain required. Full legacy editors remain explicit compatibility destinations until parity.

Required outcomes:

1. One authenticated persistent React/TypeScript root, router, investigation provider, query client, Copilot provider and panel system; implemented client navigation preserves context and per-surface scroll.
2. The three-module Landscape report with meaningful role-bearing relationships and activity differences visible before interaction; linked selection, purposeful analytical views, five-company/four-variety cohorts and curated detail.
3. AG Grid Community powering the expanded portfolio matrix under the Berry theme, with stable IDs, correct business selection and tested saved-layout mapping. Keep small semantic tables and current Workspace editing workflows.
4. An approved real CopilotKit tool turn over existing intelligence, producing the same normalized state/view/components as equivalent direct controls. Source values/citations resolve through the backend. No new research orchestration requirement.
5. Shared visual News cards and React Reader behavior preserving Article/Brief, source/claim labels, panel ancestry and close/return focus; provider-independent direct interaction remains complete.
6. An early isolated synthetic sensory state for V1, using future fictitious specimens, 1–9 scores mostly 4–7 and a readable labeled dot comparison. Generate data only during later authorized implementation; preserve panel/output labeling, metric semantics and all canonical/search/count/export exclusions.
7. Save investigation, native Workspaces reopening/reload, and one verified composite cited PDF with content preview. Explicit demo annex only. Preserve original save types and intended content beyond virtualized rows.
8. Strong agricultural/editorial visual polish, usable previews, responsive resizable panes, stable loading, restrained motion, reduced-motion support and keyboard/touch parity.

Reduce optional lenses, cohort breadth, export formats and hover embellishment if capacity is short. Do not cut state/save correctness, source return, actual SDK proof, access/trust boundaries or demo isolation. This is a bounded frontend migration using existing governed backend capabilities; it is not a backend or data-model rewrite.

### B — immediately afterward

Complete Briefing Following/Saved/Reading/Social/Signals consolidation; migrate compatible configurable/global-landscape modules; broaden countries/berries, advanced catalogs, map/retail views and mapped layout preferences; bring Workspace authoring and Learn editing into the persistent client only after draft/version/conflict parity. Consolidate report discovery while preserving live Brief Packs and frozen/approved review snapshots.

Legacy full-editor transitions remain clearly identified compatibility handoffs until their adapters exist. Adding four navigation labels does not establish four fully migrated experiences.

### C — longer term

Retire duplicate controllers after measured compatibility proof; improve structured role/date/trait coverage and real sensory intelligence; adopt Enterprise grid features only for an explicit need/license decision; evaluate open-ended/declarative generated UI after controlled component/state behavior is stable. CopilotKit itself is already in Phase A.

### Coordinated agent workstreams

[COORDINATED_AGENT_WORKSTREAMS.md](COORDINATED_AGENT_WORKSTREAMS.md) contains dispatch-ready scopes, exclusive paths, dependencies and acceptance checks. [FRONTEND_CONTRACTS.md](FRONTEND_CONTRACTS.md) freezes the shared interaction model. Proposed files identify future work, not application code created in this task.

| Stream | Deliverable | Exclusive shared ownership / boundary |
|---|---|---|
| **W0 Integration lead** | Backend compatibility/auth/save contracts and integration/release | Existing main route registration, shared saved-view/schema and sheet-layout API changes; approves cross-stream contracts |
| **W1 Platform/state** | Persistent React shell, router/providers, URL/action/cache model | New frontend app/state/contracts/API client; sole dependency/lock/build steward, including agreed runtime manifests |
| **W2 Visual system** | Berry tokens, typography, primitives, previews, motion and responsive panes | Shared design/UI/CSS and intentional legacy theme bridge; vendor components consume its tokens |
| **W3 Domain APIs** | Bounded landscape/entity/relationship/development/source/comparison read models | New route/serializer modules reusing existing presenters; no raw private entity dump or domain-schema rewrite |
| **W4 Landscape + AG Grid** | Three-module report, linked views and professional portfolio matrix | Feature rendering, BerryDataGrid/cells and legacy-to-semantic layout mapping; no independent state/theme |
| **W5 Detail/Reader/Briefing** | One detail/reading experience and native bounded Briefing | Panel ancestry/focus/close/expand, entity/source renderers and shared visual News; router remains W1's |
| **W6 CopilotKit** | Real controlled SDK/runtime integration | Typed tools/catalog registration, minimal context and stale-command/failure handling; domain owners supply actual components |
| **W7 Persistence/outputs/demo** | Native saved-investigation/Learn entry, isolated demo and composite PDF | New feature/demo/export modules; central save writer stays W0's; authored stores/editor semantics preserved |
| **W8 QA** | Cross-surface functional/visual/accessibility proof | Dedicated tests/screenshots/acceptance records; defects return to implementation owners |

Shared shell/styles, selection state, Reader behavior, main registration, save contracts, dependencies and grid layout adapters each have one named owner. Feature agents never patch shared files independently. Workstreams can be combined sequentially for a smaller team; they are not all concurrent agents. With the current four-slot team, run at most **three implementation agents plus W0**.

### Dependency waves and gates

```text
G0: W0 freezes scope/state/API/component/save/layout contracts (unchanged)
    |
    +-- W1 platform/state -- W2 visual system -- W3 domain APIs
    |
G1: authenticated real-data proof
    Actual AG Grid + shared panel + supported Copilot tool/runtime turn
    Dependency versions/topology pinned by W1; no mock-only completion claim
    |
    +-- W4 populated Landscape -- W5 detail/Reader -- W6 same-investigation Copilot
    +-- W7 early isolated sensory state, scheduled in an available agent slot
    |
V1: visual + continuous-interaction acceptance of five populated states
    Screenshots + short recording + narrower layout + keyboard/touch review
    Pass before copying patterns into other surfaces; owner fixes if rework
    |
    +-- W5 Briefing rollout -- W7 Workspaces/Learn/outputs -- W1 hardening
    +-- W8 cross-surface QA, within the same concurrency limit
    |
G2: integrated presentation candidate, owner fixes, full acceptance proof
```

At each handoff, provide contract revision, changed paths, interfaces, evidence and limitations. W0 resolves shared changes. G1 proves technical adoption; V1 separately proves a coherent populated investigation. A failed V1 holds cross-surface pattern propagation and returns defects to existing owners; independent unaffected engineering continues. G2 still governs complete state/save/auth/export and release evidence.

### Release acceptance

Execute scope → company → variety → geographic relationship → second company → AG Grid comparison → relevant development → evidence → restored investigation → save → native Workspaces reopen → reload → PDF. Run an equivalent Copilot command and verify the same normalized context, record IDs, view and citations. Ordinary interaction must work when the provider fails.

Verify additionally:

- One mounted shell/router/provider tree across implemented native routes; accurately identified legacy handoffs.
- Deep-link/reload/Back/Forward behavior and restored scroll/focus/panel ancestry; no stale agent/request overwrite.
- Explicit module filter applicability, unknown versus zero, exact role/status and geography meanings.
- AG Grid row identity, layout mapping/revision conflicts, loaded-row scope and export completeness; legacy grids unchanged.
- Source approval versus claim confidence; no agent tools for publication/canonical editing or hidden provider calls on hover/navigation.
- Minimum agent context and consistent auth on shell/API/detail/export/runtime paths; separate public-static output.
- New and old save/load/re-save meanings; authored drafts/versions and frozen snapshots preserved.
- Synthetic exclusion from trusted records/search/counts/ordinary export, with a clearly labeled opt-in annex.
- Reviewed desktop/narrow-screen states, keyboard/touch interaction, enterable previews, reduced motion and useful loading/error states.
- Appropriate record/static-public integrity and final-head CI checks when implementation occurs, plus authorized production smoke proof because local and production corpora differ.

Targets such as immediate local feedback (<100 ms) and panel motion around 150–220 ms are proposed UX targets, not measurements of the current app. Establish a realistic warm-data query budget against actual data at G1.

## 9. Decisions, dependencies and planning status

The four primary destinations and investigation-centered consolidation are accepted. Proceed with one persistent React shell, controlled CopilotKit in the flagship, AG Grid Community for demanding analytical tables, a shared Berry design system and panel/state contracts, and a separate fictitious sensory demo. Recheck the candidate public regional scenario when building the populated slice. Keep FastAPI, governed domain queries, auth and existing stores. V1 is planned, not run: validate the continuous Landscape investigation before propagating its patterns to other surfaces.

Scheduling needs the presentation deadline and available implementation capacity. A real supported Copilot runtime/provider path and approved configured model must be verified at G1; if unavailable, report that exact dependency and continue deterministic shell/grid/detail work without claiming Copilot completion. Never request credential values in the handoff or silently substitute a research provider. Enterprise grid licensing is unnecessary for the selected Community slice; reevaluate only if advanced paid features are deliberately added. Engineering must verify deployed revision and production data before release.

This update changes planning documents only. No application files, dependencies, source data, authentication or deployment configuration were changed; no implementation agents, provider calls or research jobs were started. Runtime feasibility and cross-surface parity remain to be proven during later authorized implementation.

Supporting material: [visual/interaction acceptance](VISUAL_INTERACTION_ACCEPTANCE.md), [design review addendum](DESIGN_REVIEW_ADDENDUM.md), [coordinated workstreams](COORDINATED_AGENT_WORKSTREAMS.md), [frontend contracts](FRONTEND_CONTRACTS.md), [original state/save inspection](STATE_CONTRACT_NOTES.md), [completed audit](../berry-os-design-handoff/BERRY_OS_DESIGN_HANDOFF.md), [actual screenshot contact sheet](../berry-os-design-handoff/SCREENSHOT_CONTACT_SHEET.jpg).
