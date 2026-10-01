# Mission 4 — Map Explorer and shared region annotations

October 1, 2026. Implemented review checkpoint on `feature/map-explorer-workspace`, stacked on `feature/news-reader-consolidation`. Not merged or deployed. This checkpoint covers the usable map/table/editor and initial public context; it does not claim the complete geography acquisition program is finished.

## Analyst jobs

**Scope → locate → inspect → read or edit → return.** `/explorer` and its existing country/berry bookmarks remain available in the approved bright Glasshouse shell. The functional vendored map retains country selection, keyboard/touch list fallback, pan and zoom. It can collapse; Focus table brings the region heading and rows into view without changing geographic scope. The shared right overlay Reader opens News cards with Article/Brief, image previews when available and the existing personal icon actions.

News coverage, Company operating regions and Variety growing regions are separate layers. News shares the exact metadata selection service used by News home: publication order, berry/country intersections, search, company, existing watchlist, assigned tier and date/timezone scope. News → Map → News preserves these values. Source reviewed and reviewed Fact support are both required for Trusted news and source-inventory snapshots. GET does not collect, capture a body, approve information or mark reading complete. List paths do not read the full capture store.

Region layers use country and berry selections and existing company/list/tier assignments. Variety company scope requires actual stored ownership, development, license, growing, trial, marketing or distribution roles; photo seed associations are not substituted for roles. Region status/activity and an explicit Observed by date operate separately from News dates and review. Undated entries remain unknown when an observation cutoff is used. Table A–Z, search and Company/Country sorting narrow table rows only; the map retains the full geographic scope.

The full-width table displays one location per row, source links, locality notes, activity, status, effective/observation date or Unknown, basis and profile/editor actions. Existing `operates_in` remains Operations (unspecified). Explicit substituted-predicate limitations are flagged on the row, with original notes retained. Country shading represents recorded entries, not area, certainty, market share or an exact farm point. No company office, patent territory, commercial observation or article mention becomes a variety growing location.

Six existing Geography records lacked ISO selector attributes: Canada, Colombia, Germany, Portugal, Zambia and Zimbabwe. Explicit country-code metadata was added so their stored records and relationships can be selected and counted on the map. No geographic containment, Fact or relationship was inferred. Some vendored boundary features still lack usable ISO metadata (including France/Norway and the nonstandard Taiwan code); those remain visibly unavailable until a reviewed selector-catalog correction. Political/disputed features are not silently mapped to another country.

## Shared profile editing and history

`/profiles/{entity_id}/regions` is the same editor reached from the map and Company/Variety profiles, including the current company dossier. It reads canonical geographic edges plus authoring-only annotations in ignored `inbox/profile_region_annotations.json`. Geography, optional locality, activity, location status, source/observation dates, supporting news source or active reviewed statement, source URL and notes are editable. A selected statement can supply its real supporting source; the annotation itself is still unreviewed. Company and variety activity vocabularies are distinct.

Writes use the existing serialized/atomic private-state mechanism. An expected revision prevents an old form from silently overwriting a newer edit. Add/edit/removal retain before/after snapshots, timestamp and reviewer; removal is a tombstone over the local view, preserving the underlying canonical edge. Corrupt history fails instead of being silently replaced by an empty store. Source choices must be linked to the profile or its stored relationship/statement; malformed/private/credentialed URLs, unsupported activities and invalid dates are rejected. The local authoring and same-origin safeguards apply. No AI collector writes this file, no canonical domain schema is changed, and no user entry is auto-promoted.

Read-only runtimes omit private annotations and editing; static profiles omit editor links. Private notes/history do not enter public static output or Market Snapshots. This is shared local analyst working state, not per-account storage or a multi-worker transaction system.

## Market statistics

The bottom panel contains six manually checked 2025 U.S. production/harvested-area figures across cultivated blueberries, raspberries and strawberries. Source: USDA NASS, *Noncitrus Fruits and Nuts 2025 Summary*, released May 1, 2026, pages 75 and 77, checked October 1. [Original report](https://esmis.nal.usda.gov/sites/default/release-files/795891/ncit0526.pdf). Values retain source rounding and units (million lb, million cwt and acres); strawberry cwt is explained, not silently converted. Fresh/processed utilization and cultivated/wild distinctions remain explicit. These public reference values are not canonical reviewed Facts.

Trade context projects the latest recorded period of each existing reviewed `trade_observation`; it creates no parallel Trade schema, acquires nothing on page load and sums nothing. Reporter/partner, flow, HS/revision, fresh/frozen coverage, mixed-code caveat, units/currency, valuation basis, release/estimate status, publication/access date, record/source links and `does_not_prove` remain available. Null quantity/value is Unknown; a recorded zero remains zero. Mixed HS codes never appear as a pure blueberry/raspberry total.

Country and berry scope apply to statistics; News dates/review/company/list/tier scope do not. Selected country/crop gaps are explicit, and multiple countries remain separate. Initial national coverage is deliberately partial. Wider FAOSTAT/national-provider collection, annual MIDAGRI Trade ingestion through the existing Trade architecture, explicit Perplexity research, refresh/revision jobs and reviewed statistics/regions in snapshots remain follow-up work. The validated snapshot PDF remains a trusted source inventory; private annotations and unreviewed reference context are not added to it.

## Verification

- Focused region, News, Digest and existing Explorer checks: 60 passed before final documentation. Tests cover pure GET, trust separation, source validation, concurrent saves, stale revisions, removal/history, role-based scope, annual/date separation, mixed Trade semantics and private snapshot boundaries.
- Browser review: A–Z/search/sort; keyboard Peru selection and live country/table refresh; all six corrected country mappings; statement-linked trial save → map → reopen → removal with retained history; shared Reader Article/Brief and focus return; no horizontal page overflow at desktop and 390px mobile. The temporary trial was removed from the isolated review view.
- Desktop Focus table shows nine complete region rows in the standard viewport, with approximately 45px rows. Narrow screens scroll inside the table, not the whole page. [Review image](../../artifacts/design-sprint/map-region-table-live.png).
- Records validation and static public-safety build passed (1,755 generated pages; no unpublished draft ids/titles). Full-suite and exact-head CI results are recorded in the draft PR; do not infer a merge/deployment from this checkpoint.

## Remaining accepted missions

Companies: shared favorites, Tier 1/2/3/Untiered editing, custom-list membership/subscriptions across all views; alphabetical directory; editable identity/logo/site/social/LinkedIn; People within a profile tab. Prototype marks must not be silently imported or assigned to unknown identities. Existing tier/list filtering here does not claim favorites migration is finished.

Varieties/Map depth: candidate identity confirmation, the 32 unclear photo cells, source-assisted growing-region suggestions and human reconciliation, subnational boundaries, broad public statistics acquisition and reviewed snapshot integration. Existing footprint/commercial-observation and Trade/Weather/CPVO backends remain unchanged.

Consolidated Reports & Briefings / Meeting Prep, configurable Landscape, detailed visual Learn with explicit deep-research jobs, remaining audited workspace homes, legacy compatibility and the visual workflow guide remain in the agreed mission sequence. The guide must distinguish implemented local behavior from proposals and production deployment.
