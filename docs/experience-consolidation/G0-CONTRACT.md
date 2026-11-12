# Experience consolidation — G0 contract, 11 November 2026

Implementation branch: `feature/experience-consolidation-20261111`.
The user's evening correction preserves the existing Workspaces editor and grid
as the primary Workspaces destination. The new investigation save/PDF tools are
additive utilities at `/app/workspaces`, reached through “Save / export.” They
do not replace the authored workspace, its controller or its saved grid layouts.
Canonical baseline: `3f159639a85db0dea7e93b2d5c0387efa4eb468f` (#550).
Integrated canonical: `46ba7f02` (#564), preserving Strategy inputs, global News
expansion, translation/noise fixes, #560/#561 document/language recovery and the
reviewed initial Brand media cohort, #563 official listings and #564 information-first
Workspace reading views. Canonical acquisition/data/coverage changes
are inherited unchanged; this candidate's own changes remain the experience.
The user's current mission starts implementation. Earlier planning-only text in
the supplied archive describes that document's prior scope. Deployment and live
provider acceptance remain separate, concrete release steps.

## Ownership and gates

The lead owns shared FastAPI registration, saved-view writer changes, integration,
release records and the authenticated runtime gateway. W1 owns `frontend/package*`,
lockfiles, build/TypeScript config, `src/app`, `src/state`, `src/contracts` and
`src/api`. W2 owns `src/design` and `src/components/ui`. W3 owns
`app/investigation_routes.py`, `app/services/investigation_api.py` and its tests.
Subsequent feature slices receive explicit owners. At most three implementation
agents plus the lead run concurrently; consumers do not edit another owner's files.

G0 freezes the following contract. G1 requires actual Community grid, shared
detail and a real approved Copilot SDK/provider tool turn. V1 requires a populated
five-state screenshot/continuous-interaction packet before cross-surface design
rollout. Until reviewed, Briefing/Workspaces/Learn routes may expose deliberate
legacy entry boundaries. G2 includes save/reopen, export, auth, compatibility,
required final-head CI and separately authorized production acceptance. A blocked
provider or missing visual review is recorded honestly, never replaced with a mock.

## Version 1 investigation

The same explicit string fields travel through URL, API and saved selectors:

| Field | Meaning |
| --- | --- |
| `ctx_v` | `1` |
| `berry` | `all`, `berry-blueberry`, `berry-strawberry`, `berry-raspberry`, `berry-blackberry` |
| `countries` | Comma-separated canonical geography IDs; empty means All |
| `geo_basis` | `company_connections`, `source_geography`, `variety_growing`, `rights` |
| `actor_roles` | Comma-separated authored actor roles |
| `relationship_types` | Comma-separated connection predicates |
| `news_from`, `news_to` | ISO publication dates or empty; only developments |
| `company_set` | `all` (default for older URLs/saves) or `watched`; resolves the existing uncapped company universe or shared workspace Watch membership, independently of focus and comparison pins |
| `focus` | Canonical company or variety ID, or empty; entity type resolved separately |
| `cohort_companies` | Stable-order canonical IDs, cap 5, preserve overflow diagnostics |
| `cohort_varieties` | Stable-order canonical IDs, cap 4, preserve overflow diagnostics |
| `lens` | `connections`, `portfolio`, `geography`, `comparison`, `news`, `sensory` |
| `comparison_kind` | `company` or `variety` |
| `detail_path` | Up to 8 `type:ID` references, separated by `~`; source refs may carry `@brief`, bare means Article; current is last |
| `demo_specimens` | Separate `demo-specimen-*` cohort, comma-separated; empty means the complete isolated fixture |
| `q`, `q_scope` | Search text and `scope` or `catalog` |
| `saved_view_id`, `saved_revision` | Optional live investigation reference |

Detail types: company, variety, geography, relationship, source, observation.
Source sections are encoded on each ancestor reference, so nested return and
reload retain Article/Brief independently of canonical entity/real cohorts.
`@article` normalizes to a bare source reference. Unknown syntactically valid
demo IDs remain selectors with isolated-demo diagnostics; they never resolve as
real cultivars. The demo UI keeps at least one specimen selected.
Canonical identifiers contain letters, numbers, `_`, `-`, and `.`; no source
bodies, credentials or private authored text belongs in these fields. Input size
and invalid values produce explicit issues. `investigationRevision` is a local
monotonic action revision sent as `revision` with API calls. Router navigation is
the sole history writer. Deliberate actions push; normalization/search replace;
hover/focus previews do neither. Pop/reload reconstructs state without pushing.
Late queries/tools cannot apply to a newer revision.

The November 11 evening design revision adds monitored companies and the News
view at the user's request. Watch membership is an interest selector, not proof
of an active collection pipeline. It reuses the existing shared Watch store;
there is no parallel monitoring store and no production auto-seeding. Ten real
companies are modeled in the isolated review runtime. The roster and News feed
are paginated without a total-company cap. Comparison retains its independent
five-company/four-cultivar bounds. A saved `watched` selector resolves current
shared membership when reopened rather than copying or freezing its members.
Standing findings and relationships retain their applied scope independently;
the roster explicitly labels companies outside that scope.

Initial presentation URL explicitly chooses blueberry and Chile/China/Peru. A
new URL with explicit empty scope means All, independent of cookies. Focus and
cohort membership are independent; out-of-scope entities never seed the graph.
Preserve invalid/outside-scope selections for visible remove/include resolution.

## Read APIs

Private, authoring-only, same-origin `/api/investigations/v1` endpoints use
existing session protection. Responses carry `Cache-Control: private, no-store`.
Every response envelope has `api_v: 1`, `request_id`, integer `revision`, `scope_key`,
`applied_scope` (per-module applicability), `issues` and `data`. Invalid requests
return bounded 4xx diagnostics, not silent broadening.

* `GET /monitoring?limit=10&offset=0`: a page of the selected company universe,
  full matching count, next-page position, recorded scope and monitoring state.
* `GET /news?limit=36&offset=0`: retained source cards for the company universe,
  berry/source-geography/publication scope, full matching count and pagination.
  Focus and comparison pins do not retarget this feed. An empty watched set
  produces an empty feed. All-company mode also includes scoped industry news.
  The shared cards and Reader retain publication/capture, source review,
  unreviewed mentions and source-independence disclosures. Neither endpoint
  starts collection, classification or model work.

* `GET /landscape`: normalized context and curated existing Explorer projection:
  `selection`, `nodes`, `edges`, `sources` (metadata only), `market_rows`,
  `portfolios`, `findings`, `scope_notes`, `options`, `developments`.
  Existing model keys inside nodes/edges/portfolio rows are preserved; an adapter
  documents any renamed field. `options` lists available canonical berries,
  countries and company/variety selectors. Do not return raw Entity attributes.
* `GET /comparison`: `comparison_kind` and cohort from context; `data` is the
  existing company/variety compare presenter plus explicit scope applicability.
* `GET /detail?type=...&id=...`: bounded curated selected entity/relationship/source
  model, including `type`, `id`, `title`, `kind_label`, `status`, `summary`,
  `sections`, `sources`, `expand_href`, `outside_scope`. Source detail alone may
  carry `article_text`, `article_blocks`, `document_blocks`, `card`, `media` and
  `body_availability`, using the existing Reader presenter without acquisition.
* `GET /developments`: existing News semantics and visuals, module scope first,
  then valid active comparison cohort, otherwise in-scope focus, otherwise scope.
  `data` includes `cards`, `basis`, `heading`, `briefing_href`, `matching_count`.
  Co-mentions stay labeled. No match never falls back to an unfiltered feed.

Catalog options add `match_basis` (`exact_name`, `exact_alias`, `substring`, or
`unfiltered`) and a bounded `matched_label` from an authored name/alias only.
Exact matches precede substring matches before API/tool result caps; relative
order inside each group stays stable. Multiple exact matches remain ambiguous.
The tool discloses exact/available/returned counts and truncation. These fields
describe name matching, never identity approval or confidence. No automatic
entity selection or canonical change occurs.

Development cards for an explicit focus/comparison subject also carry additive
`scope_match`: `kind` is `primary` or `related_context`, with `primary_id`,
`primary_label`, `subject_ids`, `subject_labels`, and `subject_matches` rows
(`id`, `label`, `basis`). A basis is `recorded_link` or `unreviewed_mention`;
the top-level basis prefers a recorded eligibility link when several subjects
match. Existing `company_mentions` continues to mean an additional unreviewed
alias-recalled link. Stored related context is not relabeled as unreviewed.
Primary attribution reuses the existing metadata-only deterministic matcher;
these labels do not approve an identity, commercial relationship or claim.

Use one request corpus. Exclude seed fixtures and preserve social output
eligibility as existing Explorer does. Pass `focus=''` to `build_bundle`; pass
explicit countries, including empty for All. Reuse existing source, identity,
portfolio, geographic and trust presenters. News time never filters standing
portfolios. Country bases remain distinct. Selected-only body hydration is required.

## Shared frontend interfaces

`useInvestigation()` exposes `{ context, revision, dispatch }`; context fields use
the exact snake_case names above. `dispatch` accepts `{type, ...payload, origin?,
expectedRevision?}`. Actions: `applyScope` (`scope` partial context), `focusEntity`
(`entity: {type,id}`), `togglePin` (`entity`), `setCohort` (`kind, ids`), `setLens`
(`lens, comparison_kind?`), `openDetail` (`detail: {type,id}`), `closeDetail`,
`replaceContext` (`context`, used for saved reopen). Stale expectedRevision is
rejected. `openDetail` preserves ancestors and does not retarget developments.
The root exports `useInvestigation` from `src/state/InvestigationProvider.tsx` and
context/types/URL helpers from `src/contracts/investigation.ts`.

`src/api/client.ts` exposes `getInvestigation<T>(endpoint, context, revision,
signal?)` and the response envelope type. Query keys include normalized context
and applicable subject. Clear private query caches on logout/session transition.
One provider tree persists across routes, with one detail allocation. Copilot
uses shared actions and never renders a second analysis.

Additive actions: `setDetailSection({section:'article'|'brief'})` changes only the
active source reference; `setDemoCohort({ids})` changes only the synthetic cohort.
Both use the same revision/history owner. Canonical module cache projections
clear `demo_specimens`, and ordinary exports exclude it. An explicitly selected
annex resolves only that fixture's chosen specimens. Existing ctx_v=1 rows and
bare detail paths remain valid; outer store version and kinds are unchanged.

Native Learn consumption may use `/app/learn/{concept|lesson}/{canonical-id}`;
the ID is bounded and investigation selectors remain in the query. These routes
share the root/provider tree and safe login/legacy-return validation. Educational
knowledge remains distinct from competitive Evidence; research/edit/version
workflows expand through their existing governed routes.

W2 exports `Button`, `Badge`, `EntityButton`, `SourceLink`, `Preview`, `EmptyState`
and scoped design CSS; consumers may use semantic HTML with these tokens.
Warm ivory, botanical text, selective forest/sage, editorial serif headings,
readable compact UI. Real role/activity/status distinctions remain visible.
Enterable Floating UI preview has keyboard/touch detail equivalents and Escape;
motion respects reduced motion. Domain owners compose their own feature content.

## Save, export and runtime

New saved investigations retain outer version 1 and `kind=explorer`, adding
`ctx_v` plus the allowlisted fields above, normal revision conflicts and history.
Legacy rows retain their original open/save semantics. Converted legacy contexts
save as a new row. These saved investigations reopen live selectors in Landscape.
Authored Workspaces keep their existing saved-Landscape generation links. Native
`ctx_v=1` investigations are excluded from that legacy generator until an explicit
adapter supports all their selectors; direct links fail clearly instead of
silently broadening company cohorts or monitored News. Authored content is unchanged.

Composite export uses validated domain data, explicit scope/content preview,
generated-at time and cited source appendix, including data beyond viewport.
Synthetic demo is isolated from ordinary search/counts/exports; an optional
explicitly labeled annex uses fictitious specimens and synthetic overall liking
on a visible 1–9 scale. No real cultivar receives a synthetic score.

Copilot runs only on an explicit command with a configured server-side provider;
the real turn sends bounded IDs/scope/public-source context. No provider fallback,
canonical editing, trust approval, implicit research or workspace-body export.
The storage constraint was cleared and locked builds have passed. G1 and V1 are
now accepted on the current emitted client and authenticated real APIs: the
explicitly approved real comparison produced exact normalized direct-control
equivalence, and the populated continuous packet passed all 16 checks. Earlier
failures and diagnostic limits remain recorded in `IMPLEMENTATION-STATUS.md`.
Offline fixtures do not substitute for that provider proof. Native bounded
Briefing/Workspaces/Learn rollout is now open; G2 and production acceptance remain
separate release requirements.
