# Shared company scope in Competitive Evaluation

Competitive Evaluation previously required a second manual selection even when
analysts already organized companies using shared favorites, assigned tiers and
custom lists. Its existing Filters panel now accepts those same marks. Individual
entity selections narrow the result further. The chosen cohort applies before
pagination to matrix/plot, people, overview, relationships, exposure, import index,
saved-comparison index and complete CSV/JSON exports.

A company excluded by the shared filters is named explicitly. An empty cohort
stays empty in records, assessments, jobs, relationships and archive handoffs;
it never becomes an all-company view. Canonical counterparties can remain visible
as attributed relationship context. Matching import batches keep their original
complete totals. The Saved index shows snapshots containing a matching company;
opening a snapshot restores its complete captured scope.

Saved comparisons keep resolved IDs, readable filter labels and their original
captured records. List membership/tier changes or an archived list do not change
the saved report or its JSON/record CSV. Existing snapshots without the new
optional presentation metadata remain readable and export unchanged. Live company
list choices never include account-specific Digest subscriptions or reading state.
There is no migration or change to ratings, source inspection, identity mapping,
analyst decisions or human review gates.

The existing coverage panel uses the server-resolved cohort rather than re-adding
excluded URL choices. It retains valid legacy IDs, frozen selections and the
explicit empty-cohort marker. Landscape and other non-Evaluation handoffs preserve
their existing behavior. The filters retain their original entity picker, column
controllers, keyboard paths and account layout settings. The popup now fits the
available viewport height, with Apply visible on desktop and phone. Save wording
and Help explain the workflow in plain language.

## Validation

- 73 related tests pass, including all eight views, combined/invalid/empty scopes,
  full exports, retained original citations, private/shared account boundaries,
  archived-list snapshots, historical snapshot compatibility and read-only
  saved-index behavior. Five cases execute the real coverage script; both changed
  browser controllers pass Node syntax checks. The Python runner records zero
  attempted external connections. Guide privacy checks are recorded separately.
- Native authenticated desktop/390px review uses the existing copied public seed
  and one synthetic account, never production. It applies list/tier/favorite
  filters, saves a scope, archives the synthetic list through Companies and
  reopens the unchanged captured scope. An excluded company hands off to an empty
  archive and an empty current comparison. The panel stays within both viewports.
- Initial encoding and controller naming errors were caught and fixed before
  pushing. Native review confirmed the final controller runs; original diagnostics
  remain in the ignored evidence. A slow Companies semantic lookup recovered
  through its visible Lists shortcut without restarting the active preview.

This follows the already-green #512 draft. Current-head CI, reconciliation with
the separately approved #508 then #507 releases, fresh guarded production-copy
preservation and exact release approval remain required. The prior draft heads
are unchanged and no production deployment is included. Cold catalog performance,
source depth and human-owned catalog/name/photo choices remain open.

Evidence: ignored `inbox/evaluation-shared-company-scope-20261104/`.
