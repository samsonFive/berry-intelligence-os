# Mission 8 — Customizable Landscape

Implemented on `feature/customizable-landscape`, stacked on Mission 7 / draft #280. This is a product/UI selection layer over the existing cached berry Landscape, plus private saved selections. It does not rebuild the underlying intelligence, alter canonical records, or replace human review. No merge or deployment.

## Purpose and behavior

`/landscapes` now answers “What is our captured competitive picture for these subjects and places?” Choose multiple berries, companies, varieties, countries/regions, personal company lists/favorites/tiers and the sections to include. Compact company/variety tables, dated sources and analysis cards use the shared bright Glasshouse shell. Sources open the existing overlay Reader. Company locations and variety growing/trial locations use active stored relationships; article mentions and unreviewed Map annotations cannot establish geographic coverage.

The date choices are All dated sources, Past 7 days, Past 30 days, Year to date and Custom range. Sources sort by publication date, newest first. Unknown dates are disclosed separately, and future dates are excluded. Standing portfolios, signals and assessments retain their separate time basis. Counts represent captured coverage, never acreage, market share or actual market activity. Licensee, owner, breeder and other active roles remain distinct. Photo associations awaiting identity/role review do not become confirmed portfolio relationships.

Private saved views persist only named selectors in `inbox/landscape_views.json`. Reopening resolves current data. Updates retain history and require a matching revision; stale edits cannot overwrite a newer view. Archive is reversible. Corrupt stores/rows and missing selected identities fail visibly instead of being overwritten or silently broadened. Published-only browsing never reads private views or personal marks and cannot save them. Standard local authoring/origin/login protections apply.

## Scope handoffs and preservation

News/Map receive their supported scopes; multiple explicit companies and variety selection remain in Landscape because those destinations support different filters. The limitation is stated at the handoff. Report builder receives named scope IDs, an explicit Landscape origin and visible, editable scope notes. Multi-berry, requested sections and custom date limitations are shown for confirmation rather than pretending the report generator supports them exactly. No-match personal scopes do not offer an unscoped report. Brief composition takes up to four selected companies/varieties from included sections; its country/date limitations remain explicit.

Existing cross-berry overview (`?view=legacy`), tracked-company briefs (`?view=feed`), per-berry briefings, registry coverage and concentration tools remain available. The static/public per-berry template and its live/public invariant remain unchanged. No collector, AI provider or trust action runs on browsing. Cold Landscape aggregation still has existing latency debt; no unrelated domain backend or protected expansion guide changed.

Report-image follow-up also separates reading from editing: report text is visible by default with a prominent takeaway; each section's edit textarea is collapsed. Native Save still submits every section, retaining generated prose, literal analyst wording and deliberately empty edits. Export formatting is unchanged from the revised, five-page Mission 7 PDF.

## Verification

- 113 focused Landscape, synthesis, reporting and company checks passed. After store-validation and report-reading changes, 45 Landscape/reporting checks and 78 report-builder/gap-research checks passed (one known reportlab warning per run). Exact-head CI follows on the draft PR.
- Record validation and the static public-safety build passed (1,755 pages; no unpublished draft leakage). New JavaScript syntax check passed.
- Isolated browser: select two companies/two berries, save, reset, reopen, change source dates, update the saved view, select only Companies and Latest sources, open a source Reader, close and retain scope, and page through sources without losing saved-view identity. An access-screen summary is disclosed rather than presented as article content; the stored source is untouched.
- Browser report handoff exposes the correct origin, both requested berries and section notes. The report opens as readable prose with separate editing controls.
- A 390px browser check found no page overflow; the compact inventory table scrolls inside its own region. The temporary viewport was reset. Review screenshot: [Landscape](../../artifacts/design-sprint/landscape-workspace-live.png).

## Remaining release work

Required CI must pass on the pushed head. Combined release review must recheck retained specialist handoffs, private account isolation and multi-worker saved-state behavior. Geography annotations remain unreviewed; later source-assisted suggestions cannot bypass their human gate. Learn, Monitor/Operations, live-data readiness and final workflow explainer continue under the ongoing requirements checklist. A locally verified mission is not a deployed release.
