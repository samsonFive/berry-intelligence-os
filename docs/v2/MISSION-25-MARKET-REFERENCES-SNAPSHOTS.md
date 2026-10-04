# Mission 25 — Market figures that survive snapshot export

Map statistics previously contained six manually checked US figures and were excluded from Market Snapshots. Snapshots now have an optional Market statistics section, with individual figure selection. Countries, berry scope, reporting periods, source units and qualifications stay attached in both composition and PDF. This is public reference context, separate from reviewed statements. Private region notes and human trust decisions remain outside the export.

## Official reference capture

A bounded request reused the existing Eurostat collector: annual strawberries (`S0000`), Germany/Spain/Netherlands/Portugal, three recognized production/area/yield indicators and a recent window beginning in 2023. The original public response is retained at `data/imports/map-market-references-2026-10-03/eurostat-strawberries.json`; it contains 24 populated cells and original provisional flags. Its dataset update is September 28, 2026; capture was October 3 UTC. Dataset update is not relabeled as article publication date.

The latest populated period is 2025 in all four countries. There are eight area/production figures: Germany 10.14 thousand hectares and 128.41 thousand tonnes; Spain 7.04 and 332.05; Netherlands 1.34 and 91.14; Portugal 0.39 and 10.83. These values reproduce the original agency cells without conversion. Yield and the empty 2026 cells remain absent. No yield is calculated from area and production. The initial eight cells have no supplied estimate/provisional flag; this does not imply that they are final. Original flags on earlier observations are retained in the capture. Confidential cells cannot become public references.

[Original dataset](https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/apro_cpsh1?format=JSON&lang=en&crops=S0000&geo=ES&time=2025), [agency methodology](https://ec.europa.eu/eurostat/cache/metadata/en/apro_cp_esms.htm), [official API guidance](https://ec.europa.eu/eurostat/web/user-guides/data-browser/api-data-access/api-getting-started).

Harvested production is distinct from the USDA utilized production references. Source-defined area, cultivated/wild and fresh/processed coverage remain separate. Eurostat's 2025 reporting-framework change is explained in plain language; no cross-country, cross-unit or cross-category sums are presented. Existing USDA values and Trade/Market Reality/Variety schemas are unchanged.

## Refresh and export boundaries

`scripts/capture_map_statistics.py` makes one bounded official request and writes a new ignored capture with the original payload, request scope, capture time and derived groups. It never replaces public references or existing captures, edits canonical intelligence, starts a paid provider or schedules itself. Empty, ambiguous, out-of-scope, invalid numeric or invalid-position responses fail without replacing earlier data. An operator reviews a capture before public reference changes. This is a manual refresh path, not a delivered in-app refresh/reconciliation queue or globally complete dataset.

Figure selection uses stable source/category/period/measure identities, independent of value or display position. Selecting an unavailable or out-of-scope figure returns 422 instead of silently substituting new numbers. Explicitly empty selections export no reference figures. Disabling the section excludes its figures and citations. Publication/news/date/list filters never masquerade as annual statistical periods. Existing reviewed/escalated news eligibility is retained.

PDF tables separate country/crop/period, measure, value and unit/status. Qualifications, source check/update basis and a readable source appendix remain. Statistics-only snapshots omit irrelevant zero-news inventory tables. Source IDs are not dumped into prose; original code locators remain in source notes. Screen values lead, while definitions and raw timestamps are closed by default. Export has a clear primary action. Report edits elsewhere retain their existing rendering/persistence semantics.

## Verification

Focused service, Map, Explorer, existing Market Reality, report/PDF and full static/private-sentinel checks passed before the final source-reproducibility assertion: 130 passed, one existing reportlab warning, 13.33 seconds. Final follow-up results are recorded in the PR/checklist. Canonical validation passed. The production build produced 1,755 pages, Pagefind and no unpublished IDs/titles. No live provider calls enter required CI.

The manual refresh was executed successfully against the real agency endpoint and kept a separate four-country capture in `inbox/market_statistics_captures`. The public response used for reference values is reproducible from the committed source capture. Browser composition excluded Spain area and both Portugal figures while retaining Spain production; the URL and downloaded PDF retained that exact selection and one source. The actual downloaded one-page PDF was rendered and inspected. A two-country review sample was separately generated and inspected on all its pages.

Desktop and 390px phone checks retained the selection; phone page width was 375px without horizontal overflow. The country/period, measure and prominent number remain distinct. Enter expanded definitions; the viewport override was reset. Screenshots: `market-statistics-selection.png`, `market-statistics-mobile.png`. Browser export completion was unusually delayed; the verified file is retained, but no immediate-download performance claim is made.

## Remaining accepted requirements

Broader FAOSTAT/national production/area/yield coverage, supported national trade feeds, app-assisted refresh and source/revision reconciliation remain. Reference geography is country-level, not exact farm coordinates. User-reviewed location proposals, subnational boundaries and region/Trade choices in snapshots remain. Wider filtered-news snapshot handoffs, body/media availability, protected AI company/contact proposals, per-account/inter-process runtime safety, older-PR parity and canonical release integration remain on the durable checklist. No merge or deployment is authorized by this draft checkpoint.


Final focused acceptance after source reproducibility and appendix pagination: **131 passed / one existing warning in 35.58 seconds**. Record validation passed. Both final sample PDF pages and the actual single-figure browser export were rendered and inspected. The source appendix now stays with its first source. Draft-head required CI remains the release gate.


The live/public visual Guide now describes the optional individual-figure capability. Draft #298 is pushed and attached; required exact-head checks are tracked in GitHub. Canonical was freshly fetched and remains `916b8f09f9ce2a1847335d7990ea80ff921f1cec`; the expansion guide has no diff. No merge or deployment.


Market-code head `b8a29039ea35a9623c9c5c964a307cf5410498f2` passed all four required checks, run `37212137821`: **3,666 passed / 11 skipped / two warnings in 244.73 seconds**. The subsequent Guide wording follow-up passed 18 focused Guide/static tests; its pushed head requires fresh checks. This is not canonical release sign-off.
