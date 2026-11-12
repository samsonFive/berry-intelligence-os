# Berry OS — shared frontend contracts

Revision 3, 11 November 2026. **Proposed technical contracts remain unchanged; experience acceptance is additive. No code or runtime configuration.** Read with [the proposal](BERRY_OS_EXPERIENCE_CONSOLIDATION_PROPOSAL.md), [agent workstreams](COORDINATED_AGENT_WORKSTREAMS.md) and [visual/interaction acceptance](VISUAL_INTERACTION_ACCEPTANCE.md). Existing backend evidence is in [STATE_CONTRACT_NOTES](STATE_CONTRACT_NOTES.md).

## 1. One application and explicit migration boundary

One React/TypeScript root is served by FastAPI under proposed `/app/*`; React Router owns client navigation, URL writes and Back/Forward. One instance each of the investigation provider, QueryClient, Copilot provider and panel host persists across implemented client routes. FastAPI and existing governed services/stores remain authoritative. Vite builds assets; no Next.js/backend migration requirement.

Initial native routes: Landscape, bounded Briefing reading, Workspaces saved-investigation/output entry and existing-Learn entry/consumption. Full legacy editors/tools retain normal routes and explicit return context until migrated with revision/draft parity. Do not embed them in iframes or inject full HTML pages into React and claim a persistent shell. The initial migrated extent must be visible in acceptance evidence.

Legacy global history/Reader/sheet scripts stay on legacy pages. New components use adapters, not parallel controller initialization. Public-static navigation/output remains separate. Any required Copilot runtime is behind a session-authorized same-origin gateway; credentials stay server-side.

## 2. State domains

| Domain | Authoritative owner | Persistence |
|---|---|---|
| Applied investigation | W1 context reducer + URL contract, validated by backend | URL; explicit private saved investigation selectors |
| Server query results | W3 services; one W1 QueryClient caches authorized results | Scope-aware memory cache; invalidate on identity/session change |
| Grid layout / pane sizes / density | User layout preference adapter | Existing private preferences with version/revision handling |
| Authored document drafts | Existing Workspace/report stores and revision contracts | Preserve content/citations/versions; separate from context selectors |
| Conversation | W6 session/selected supported thread interface | Session-only allowed for flagship; product copy states actual retention |
| Demo observations | Isolated demo loader | Dedicated synthetic namespace; no trusted records/search/counts |

Explicit URL scope wins over cookies/default preferences. Copilot state and AG Grid selected rows are projections of the investigation contract, not competing stores. No account details, secrets, source bodies or full documents in URL state.

## 3. Context envelope

Names below are proposed; freeze the exact API schema at G0 before implementation.

- `ctx_v`: 1.
- `berry`: one canonical berry, All, or the explicitly supported advanced pair mode. Do not promise arbitrary three-of-four filtering before an adapter exists.
- `countries`: canonical Geography IDs; `geo_basis` declares recorded company connections, source geography, variety-growing or rights lens as supported.
- `actor_roles`: authored actor-role filters. Advanced `relationship_types` applies only to the connection renderer.
- `news_from/news_to`: genuine source-publication interval for development modules, not standing portfolios or universal event time.
- `focus`: current focal actor/selection, independent of pinned cohorts.
- `cohort_companies`: up to five canonical IDs; `cohort_varieties`: up to four. Stable user order, deduplication and explicit invalid/overflow issues.
- `lens`: Connections / Portfolio / Geography / Comparison / Sensory demo; `comparison_kind`: company or variety.
- `detail_type/detail_id`: active persistent panel. Bounded `detail_path`: typed ancestor IDs for shared/reloaded breadcrumbs.
- `q/q_scope`: scope or catalog search. Loaded-grid text filtering has a separate name and scope.
- `saved_view_id/revision`: optional reference to a saved context; live context remains explicit.
- `investigationRevision`: session-local monotonically advancing action revision for stale-command/request rejection; not historical truth or permission.

Current Explorer `compare` means second berry. Legacy Watchlist `compare` means company cohort. Do not reuse either ambiguously. Old routes keep their contracts; adapters normalize supported parameters explicitly. Monitoring regions/groups, private tiers, source/tag filters and authored evaluations require their own applicability handling. No silent broadening or parameter loss.

Focusing an outside-scope entity does not add it to the base graph seed set. Show its detail as Outside scope; Include/expand is explicit. A changed scope retains pinned IDs with explicit issues rather than deleting them.

## 4. Shared actions

Every action has a typed payload, origin (`direct`, `grid`, `copilot`, `restore`) and expected investigation revision where asynchronous. Read/query/navigation events do not grant write/trust permission.

| Action | Payload | Effect |
|---|---|---|
| Apply scope | Supported IDs/basis/actor roles/news dates | Updates normalized scope and its applicable modules; preserves cohort issues |
| Focus entity | Type/canonical ID | Highlights actual connections, opens entity detail and re-evaluates related developments under the declared precedence |
| Pin/unpin/set cohort | Company or variety IDs | Changes comparison membership independently of focus |
| Change lens | Approved enum/comparison kind | Changes main analytical renderer, preserving context |
| Open detail/source | Typed canonical ID and optional ancestor path | Replaces/pushes contextual panel content |
| Close/return/expand | Valid known panel path or allowlisted same-origin return URL | Restores parent detail/view, trigger and scroll |
| Save/open investigation | Valid context/title/reference/revision | Existing explicit private save semantics; no automatic conversation save |

Deliberate actions request router push navigation. Typing/normalization uses replace. Back/Forward/reload must reconstruct the same scope/cohort/lens/detail. Feature modules do not call raw browser history. A late query/model result cannot replace newer direct user action; abort/reject or present an explicit suggestion to reapply.

## 5. Read-model/API boundary

Proposed versioned adapters may expose landscape, comparison, entity detail, relationship, developments and source detail under `/api/investigations/v1/*`; W0 registers them, W3 implements them. Save/export use existing stores/services through validated wrappers. Final URLs are agreed at G0.

Each response carries request ID, expected investigation revision/scope key, actual applied module scope, display data, source references, omitted/unsupported scope keys and record trust/identity state. Domain kinds distinguish canonical records, retained sources and synthetic demo; canonical catalog data is not automatically trusted intelligence. Preserve per-record claim/source status and original units/conditions/date basis.

Thin curated serializers reuse existing domain presenters; do not ship raw entity attributes/private workspace bodies as a generic panel API. Large source bodies hydrate only for selected detail. Backend data remains factual authority; no values/relationships/rankings are accepted merely because a model included them in component props.

Country rules: HQ, operating/R&D/planned activity, cultivar growing, retail market, rights territory, source mention and monitoring scope remain distinct. Berry/actor/time controls apply only where supported. Every module has one concise scope subtitle. All-profile expansion is labeled beyond scope. Missing is null/unknown; observed zero retains its true units/context.

## 6. Controlled Copilot catalog

Catalog components are domain-owned: CompanySummary, PortfolioComparison, GeographyConnections, RelatedDevelopments, EvidenceDetail and SensoryDemo. Copilot registers and selects them; it does not create factual payloads or an alternate design language.

Tools carry IDs/selectors and call the shared actions/query service. Render backend results with the same components as direct interaction. Scope/context serialization includes only the minimum needed authorized public-source context; no unrelated private content. Model calls require explicit commands; hover, maps, sorting and navigation remain deterministic.

The supported runtime/provider combination must be proven with an approved real turn at G1. CopilotKit Built-in Agent streaming shared state is not assumed; controlled tool calls plus read-only context can satisfy the flagship. Experimental declarative surfaces and unrestricted generated HTML/JavaScript are not a release dependency.

Copilot failure, cancellation, stale revision and unsupported query have bounded UI states. Keep direct controls available. No publish/approve/canonical-edit tools. Save is explicit and uses the normal writer; chat transcript remains separate. Generated prose, if included, is labeled AI synthesis and its references validated.

## 7. Grid adapter

AG Grid Community backs demanding read-only analytical views. `getRowId` uses canonical records/composite canonical keys; `colId` uses stable semantic identifiers. Cell action → shared focus/detail; explicit pin/check → shared cohort. Do not collapse these behaviors into row selection.

Separate business scope/cohort from AG Grid filter/sort/layout state. Mark loaded-row filtering clearly. Semantic tables remain for small comparisons; the current Workspace authored-grid controller remains until a separate revision-preserving migration.

Existing layouts use index/title-hashed IDs and pathname/header-based view keys; existing endpoint accepts widths/order/hidden/string filters/revision. W4 defines migration/serialization and unsupported fallback; W0 owns additive endpoint/schema changes. Do not save raw GridState into the existing record or overwrite old preference rows without mapping. Preserve optimistic conflict handling.

Community scope: standard sorting/filtering, resize/reorder/pin, custom cells, virtualization and keyboard interaction. Enterprise grouping/pivot/range/advanced clipboard/styled Excel is a separate explicit feature/license decision. Export domain models and source citations, not virtualized DOM or only visible rows.

## 8. Visual and interaction contract

W2 owns the tokens and common primitives, including typography, warm reading surfaces, selective botanical accents, spacing, borders, focus/selection, density, status/role chips, citations and loading/error states. AG Grid/Copilot consume these tokens. New CSS is scoped to the React app; a deliberate bridge styles retained legacy pages without breaking editors.

Preview → persistent detail → expanded investigation is the consistent pattern. Previews are enterable by pointer/focus, have dismissal grace, Escape and touch/keyboard equivalents. Only one coordinated detail/source/copilot panel allocation exists. Material breeder/owner, planned/operating, source-named/approved, disputed/settled and synthetic/measured distinctions remain visible at rest.

Panel/lens motion is brief and respects reduced motion. Preserve layout while updating; accurate updating/applied-scope labels prevent stale data from masquerading as current. Provisional targets: local selection feedback under 100 ms, panel transitions 150–220 ms; measure data-request performance against an agreed real-data budget at G1. No animation is required for correctness.

Suppress unnecessary empty sections; research/coverage mode exposes diagnostics intentionally. A whole empty module gets one useful no-results/expand action. Table unknowns use em dash plus accessible explanation, not zero.

### Revision 3 presentation acceptance, without schema changes

- The initial analytical field exposes explicit role-bearing relationships and meaningful geographic activity before interaction. Scope readout findings remain about applied scope, independent of focus/detail changes. A roster/news layout, generic card wall or unnamed diagram links do not satisfy this.
- Developments apply existing module filters, then use active Comparison cohort → otherwise explicit in-scope focus → otherwise applied scope. Heading states the basis. Hover, relationship/source/descendant detail do not retarget it. Outside-scope inspection does not broaden the base rail. Empty results do not silently fall back to general news. This adds no state key or store.
- Preview does not mutate scope/cohort/history or start research. Entity/source/Copilot output shares coordinated space; a Copilot comparison changes the same main view rather than generating a duplicate report in chat. This changes no tool/action contract.
- The synthetic view begins with a labeled dot comparison and visible 1–9 axis for one deliberately named synthetic metric. Additional dimensions and distribution views require declared semantics/observations; liking, sweetness and acidity intensity are distinct. Existing fixture isolation/save/export contracts are unchanged.
- V1 in [VISUAL_INTERACTION_ACCEPTANCE.md](VISUAL_INTERACTION_ACCEPTANCE.md) is planned/not run. Review five populated states and a short continuous recording, including narrow/keyboard/touch behavior, before propagating the design across other surfaces. G0/G1/G2 and ownership remain intact; SDK/test success does not establish visual acceptance.

## 9. Saving, authored content and export

New investigation saves selectors/IDs/lens/detail path only and reopens live data. Preserve existing supported `kind=explorer`, outer version and revisions while carrying the new fields through every parser/bundle/form/allowlist/restore stage. Save converted legacy selections as new rows. Prove new and old load/re-save round trips.

Authored Workspaces/reports retain their content, citations, source snapshots and versions. Brief Packs stay live composition. Capability and Strategy Review snapshots retain frozen/approved basis/history. No silent regeneration or automatic trust change.

Composite PDF uses validated domain output and explicit content preview. Include intended selected data beyond viewport and preserve citations/trust/date semantics. Synthetic data is an explicit separately labeled annex, excluded from ordinary exports. Demo specimens use a separate namespace, 1–9 scores mostly 4–7 when later authorized to generate; no measured commercial-variety implication.

## 10. Contract-change rule

W0 approves cross-workstream schema/ownership changes; the existing owner edits its implementation. Consumers add an adapter against an agreed version rather than inventing a second state/provider/Reader/theme. Each change includes compatibility notes, affected modules, round-trip/migration tests and acceptance evidence. Dependency versions/manifests/build changes are applied only by W1.
