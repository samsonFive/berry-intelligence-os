# Shared investigation state — source evidence and recommended contract

Proposal only, 11 November 2026. Source inspected read-only in `berry-news-recalibration-20261111`, branch `fix/berry-news-first-page-20261111`, clean HEAD `6734f676a8eff9a24caa8f407ecdd2c415b216e0`. This is newer than the handoff. All feasibility below is code-confirmed or proposed, not newly runtime-tested.

**Revision 2 reading note:** existing-code findings below remain supporting evidence. The adopted React/CopilotKit/AG Grid architecture, route/provider ownership and current implementation contracts are defined in [FRONTEND_CONTRACTS.md](FRONTEND_CONTRACTS.md) and [the revised proposal](BERRY_OS_EXPERIENCE_CONSOLIDATION_PROPOSAL.md). Those replace the earlier frontend-deferral recommendation. Extending saved field allowlists alone is insufficient; preserve new fields through request parser, bundle, form, writer and restore.

## Existing contracts that consolidation must preserve

| Surface | Source contract | Consequence |
|---|---|---|
| Configurable Landscape | `app/services/landscape_workspace.py:18` FIELDS: berry, company, variety, countries, list, tier, favorites, window, start, end, section. Multi-ID values accepted. | Scope is selector-based. Its date range applies only to source rows; standing portfolios and analyses remain. Geography inventory uses active stored operating/growing/trial relationships, not arbitrary news mentions. |
| Landscape Explorer | `landscape_workspace.py:19` EXPLORER_FIELDS: berry, compare, pair, countries, q, predicate, evidence, status, window, time, start, end, focus, edge, view, theme, limit, favorites, tier, list. | Here `compare` means the second **berry**. `focus` can be company/program/variety; edge is relationship ID. Never repurpose `compare` as a company basket. |
| Explorer parser | `app/services/landscape_explorer.py:50` selection accepts one berry, all, or pair mode. Views portrait/changes/explain/relationships/compare. Time clock documented/published/event. | Documented means first captured, not development date. Arbitrary three-of-four berry subset is not currently a direct parser contract; all four and two-berry pairs are. |
| Explorer interactions | `app/static/landscape_explorer.js:29` setURL uses replaceState; initial focus/edge restored; no popstate handler. Apply scope reloads. | Reload/share works for existing selectors, but selection history is not a traversable Back/Forward sequence. |
| Explorer graph scope | `landscape_explorer.py:248` adds focus to graph seeds. Predicate filters edges after reachability. | Out-of-scope focus can enlarge bundle. Predicate=develops is an edge filter and can remove operating-location edges; it is not an authored company-role filter. |
| Global Watchlist | `landscape_workspace.py:21` WATCHLIST_FIELDS excludes focused company and comparison cohort. `global_watchlist_routes.py:65` reconstructs contextual return. `global_watchlist.js:10` holds checked IDs in DOM, cap four. | Existing saved Watchlist landscapes are filters only. Compare cohort becomes URL state after submit. Preserve old save meaning. |
| Standalone Compare | `company_workspace.py:28,79` cap five, canonical-ID resolution, dedup, invalid/overflow reporting. `variety_workspace.py:984,987` cap four. | Reuse these presenters for new integrated compare. Preserve old direct `?ids=` URLs/caps. |
| Global berry preference | `app/services/ui_context.py:108` query → bios_berry cookie → stored meta.ui. Blank query value falls through. | Explicit `all`/global sentinel must be authoritative in new context. Deliberate investigation scope must not be overwritten by a profile breadcrumb or preference cookie. |
| Saved Landscapes | `landscape_workspace.py:225` load_views validates outer version1, kind overview/explorer; save_view validates surface blank/watchlist, revision, and reconstructs allowlisted fields. | Reuse optimistic revision checks/history, but new state keys require explicit allowlisting. A new unsupported kind/surface breaks readers. |
| Reader | `app/static/v2.js:129,155,255` story URL, push on opening, replace on adjacent story, popstate, focus return. Full reader validates return_to. | Existing behavior is reusable but a new central coordinator must own history once; competing handlers must not issue duplicate history.back calls. |
| Map | `app/static/global-explorer.js:44` replaces URL after scoped fetch. Three layers news/companies/varieties. | Different geographic semantics and date controls; cannot share an unlabeled universal region interpretation. |
| Configurable Landscape handoffs | `app/landscape_routes.py:39` News only carries company when exactly one; Map drops source dates; BriefPack first four companies/varieties, one berry, no country/custom dates. | Current handoffs narrow scope. New output action must state/resolve supported scope, never silently trim. |

## Recommended state contract

Use one versioned explicit investigation envelope, projected to a shareable URL and validated against the existing backend. Revision 2 adopts a persistent React shell while retaining FastAPI, governed read models and stores. The React router becomes the sole client history writer.

- **Scope:** canonical berry IDs; country/region IDs; an explicit geography basis for the active module; optional authored `actor_roles`; company marks/list filters; source-review/status filters where applicable. `relationship_types` is an advanced connection-module filter, separate from actor roles.
- **Time:** separate developments publication range from standing context. An advanced Changes lens can select publication/event/first-captured clock. Do not apply news recency to portfolios, identity or current location records.
- **Selection:** one focus entity, independent typed comparison cohorts (`company_ids` max5, `variety_ids` max4). Pinning a subject does not focus it; focusing does not add/remove cohort. Keep selected IDs visible when outside applied scope, with an explicit status and remove/include action.
- **View:** one main lens (roles/portfolios/geography/relationships/compare), independent of scope. Keep legacy `view` values as adapter fallback rather than redefining existing route values.
- **Detail:** typed company/variety/geography/relationship/source/observation ID, section and parent-detail breadcrumb. Opening a source from a relationship preserves the relationship and investigation underneath. A direct canonical profile remains available as Expand.
- **Search:** explicit `q_scope` = current investigation or all catalog; roster/source queries retain distinct targets. Loaded-table search remains labeled loaded rows. All-catalog results do not silently alter applied scope.
- **Output:** saved investigation reference and revision, optional workspace/report destination. No canonical data or source bodies in URL state.

Use pushState for deliberate applied scope, lens, cohort and persistent detail transitions. Use replaceState for URL normalization and debounced search text. A single popstate coordinator rebuilds exactly the historical state, including reader/detail, without pushing again. Hover/focus previews create no history. Reload resolves canonical IDs and current records, retaining explicit invalid/out-of-scope diagnostics. New empty scope means explicit All, not inherited cookie.

The base investigation scope stays unchanged by focus. Related-company or cultivar panels may show an explicitly labeled connected subset. Out-of-scope direct entities open as outside-scope detail with a deliberate Include/expand-scope action; their mere selection must not enlarge main matrix/export scope.

For the presentation scope, use single berry or All plus countries, with existing berry-pair comparison retained as an advanced view. Arbitrary multi-berry subsets can follow once a tested adapter is in place. Expose only supported controls.

## Save meanings and backward compatibility

1. **Save investigation:** selectors, cohort, lens and optional open detail; resolves current data when reopened. This is a new explicit action. Keep the existing private `landscape_views.json` outer version1 and kind explorer, add a `ctx_v` marker and allowlisted state keys, and retain compatible current filters as fallback. New controls create a new investigation row when launched from a legacy Watchlist/overview view. They never overwrite those rows or reinterpret their meaning.
2. **Existing saved view:** continue its original surface/kind semantics. Translation into new Landscape is an explicit Open in Landscape action; old route and save endpoints remain functional. Preserve revisions and archive/history behavior.
3. **Workspace:** shared authored page with cited captures, source snapshots, versions and editable blocks. Reuse `workspace_landscapes` links and page version/conflict checks. A saved Landscape link is live; captured passages retain source versions. Saving does not approve claims.
4. **Brief Pack:** selection/composition IDs, always a live brief (`app/services/saved_brief_packs.py`). Do not relabel as snapshot.
5. **Report:** resolved scope plus generated and edited section text (`report_builder/reports_store.py`); preserve analyst edits. Topic reports also retain research_snapshot metadata. Do not replace report persistence during navigation consolidation.
6. **Dated export:** rendered content with date, scope, basis and source references. This captures presentation output; it does not imply a universal frozen backend snapshot.
7. **Advanced competitive evaluation:** `/competitive-evaluation?saved=...` has a genuinely different immutable cited comparison snapshot in private Store kind competitive_comparison (`workspace_landscapes.py:60`). Preserve separately from live Company Compare.

Compatibility tests must exercise old saved views and URLs; five-company and four-variety legacy comparisons; explicit All overriding cookie; canonical redirects/invalid IDs; back/forward/reload through nested source detail; out-of-scope pinned cohorts; save revision conflicts; exports reproducing scope without trim; and synthetic-demo exclusion from trusted sources/counts. This is proposed implementation work, not completed testing.
