# Competitive evaluation sheet workspace

The competitive evaluation now opens as a compact sheet workspace. The large always-open entity picker and tall evidence cells previously pushed the comparison below the fold. A compact toolbar, numbered rows, frozen entity and evidence columns, and a side panel keep the comparison visible while preserving the original scoped records and review controls.

The visual reference is Smartsheet's table workflow: toolbar filters, dense rows, selectable columns and row details. Reference: [working with data in Smartsheet table view](https://help.smartsheet.com/articles/2483462-work-your-data-table-view). This implementation uses the existing OS shell and ordinary HTML/CSS/JavaScript; it adds no Smartsheet dependency or account connection.

The workspace provides:

- Existing comparison views in a dark left navigation rail, becoming a horizontally scrollable navigation strip on mobile.
- A collapsed filter popover containing the existing searchable, additive multi-entity picker, role, berry and destination controls. Selected entities remain visible above the sheet.
- Server-side sheet search, assessment-state filtering and sorting by entity, capability, rating or assessment date. These operate over all matching scoped cells before pagination and export. Unknown/N/A values follow numeric values in either numeric sort direction; neither becomes zero.
- Numbered rows with separate berry, programme, period, destination and origin columns. Entity and evidence actions remain frozen during horizontal scrolling. Column visibility and row height are presentation controls for the current page.
- A row-details side panel, opened by Inspect, double-click or Enter on a focused row. Arrow keys move between rows. Escape/Close restores focus. The panel exposes complete scope, original observations, source inspection status, anchor/confidence checks, existing guarded correction forms and revision history. Unsaved form text survives closing and reopening the row.
- The existing Reader opens outside the modal panel. Source capture and review continue through the original paths. Saved comparisons remain immutable and expose no assessment decision form.
- CSV export retains the complete filtered result, rather than just the visible page. Source citations, rubric versions and scope fields remain in the existing exports.

No original source, rating, mapping disposition, saved comparison, entity identity or trusted publication was changed by this UI work. The separate browser rehearsal uses an isolated copy with paid keys and polling disabled. Its earlier test override remains intact. No new backend store, overall score, inline raw-source editing, automatic approval or bulk rating action was added.

Validation includes actual route rendering for all eight views, pre-pagination search/filter/sort, invalid filter rejection, complete exports, immutable snapshot rendering and the existing assessment/override/import checks. The initial focused run passes 52 tests; the final rebased run passes 73 tests, including the newly canonical patent-sheet and snapshot navigation checks. Desktop and 412px browser checks cover multi-entity selection across searches, configurable columns/density, complete scope in the side panel, unsaved text preservation, Escape focus, original-source Reader content and older read-only saved comparisons. At 412px the document width is 397px; horizontal scrolling stays inside the grid. Final rebased tests and all four required current-head checks are recorded on [draft PR #445](https://github.com/samsonFive/berry-intelligence-os/pull/445).

The local preview uses `competitive-sheet-preview/inbox` on loopback port 8772. Earlier research counts and original-source limits remain documented in the [November 2 source-review receipt](COMPETITIVE-EVALUATION-SOURCE-REVIEW-2026-11-02.md). This is a review build; no merge or production deployment.
