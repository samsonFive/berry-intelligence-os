# Mounted Community grid layout checks

11 November 2026, actual `index-TMvSoonX.js` bundle. Status: all five integration
groups passed; root accepted the mounted grid evidence with the G1/V1 checkpoint.
The private QA account stores display preferences only. No canonical record,
investigation selector, cohort or focus was changed by a layout operation.

The populated current-corpus run exercised actual account GET/POST endpoints:

- Initial restore made no POST; cultivar identity was first and both identity/pin
  columns were in AG Grid 36's pinned-left cells.
- Actual mouse resize and company-column drag, Community visibility checkboxes,
  column text filtering, loaded-row quick filtering and sorting received server
  acknowledgements before navigation. The final combined display snapshot was
  confirmed at account revision 14.
- Lens return and reload restored width/order/hide/filter/sort/quick preferences,
  with no restoration POST and the same complete investigation selectors.
- A deliberately injected **layout POST only** 409 preserved the local display.
  Further edits produced no write. Explicit Reload saved layout restored the
  saved baseline, then a new real edit/save succeeded. No domain API was mocked.
- At 390px, identity/pin remained visible and frozen left. Keyboard Columns
  activation and Escape restored summary focus; fixed-column checkboxes stayed
  disabled. No provider turn or uncaught page error occurred.

Evidence: `artifacts/experience-consolidation/v1/grid-rehearsal-1794436607587/`
contains `grid-acceptance.json`, saved/conflict/narrow PNGs and continuous
`page@ff0c981f200f3edde65140feda7fb9e2.webm`. The preceding two failures were harness
corrections: an old AG Grid pinned-header DOM selector, and raw URL comparison
against omitted versus explicit default selectors. Neither required an app edit.

Account response-header timings were recorded with endpoint/status/duration only.
The run's successful layout POSTs were 28–74ms; initial layout GET was 569ms and
later GETs included 19–601ms. These are local warm-server observations. Fourteen
targeted codec/adapter/grid-state tests and TypeScript had passed before build;
larger catalog/legacy/session/cap cases remain covered by those targeted tests,
not falsely claimed as additional mounted scenarios.
