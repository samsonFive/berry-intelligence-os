# Unified information catalog

The live application has one information inventory. Review status and confidence
describe an item; they do not decide whether it can appear in search, News,
research or a report. A user can use a web source without first promoting it
through publication and claim queues.

`app/services/information_catalog.py` is the common adapter. It combines existing
Evidence records, intake metadata (including atomic proposals) and retained web
results by exact record ID. Canonical Evidence wins over an older intake/cache
copy. Rejected and archived decisions suppress stale copies. Independent sources
are never merged by similar wording. The request corpus loads this inventory
once per request. Inventory reads do not change any stored record or decision.

Each row exposes `information.review_status`, `information.confidence`,
`information.confidence_label`, `information.verification_status`,
`information.caveats` and `information.publication_status`. Confidence reuses the
existing `information_confidence` field, with compatibility for stored confidence
metadata. Missing confidence remains unknown; publication or review never creates
a numerical score. Verification and material source limitations remain available
in the item details and citation metadata. Facts, source claims and analyst
interpretations retain their types and links.

News and map views use one default inventory. Old `trusted` / `unreviewed`
bookmarks resolve to that inventory. Statements default to all statements, with
review available as an optional filter. Search ranks equivalent text matches
without a review-state bonus. Company and other report scopes include unreviewed
sources alongside reviewed records, and synthesis receives the per-source flags.
Source wording must remain attributed, including in generated prose.

Existing review/edit endpoints and their audit history still work. Completing a
review refines a record; it is no longer a prerequisite for using it. The separate
Pending Review navigation entry and repeated trust badges are removed from the
general feed. Confidence and review are available in collapsed item details.

The implementation now includes physical consolidation. After an explicit,
verified migration, `data/information/records/<id>.json` is the authoritative
source store for acquisition, source review, search, News and reports.
`data/information/assets/` holds migrated attachments. Intake and retained-web
adapters use the same record IDs and directory; retained daily/packet envelopes
store ID references instead of duplicate source bodies. Updating source review
changes the same record. It does not move or copy the record between states.

`app/services/information_storage.py` resolves the active store. A data marker
and inbox binding record the exact absolute runtime paths, including non-sibling
data and inbox roots. A missing, mismatched or interrupted activation blocks
startup and writes. Startup never migrates or silently falls back to legacy
folders after activation. Unmigrated installations retain legacy behavior until
an operator performs the maintenance cutover. Facts, Entities, Signals and other
typed knowledge records keep their existing schemas and repositories.

`scripts/migrate_information_storage.py` provides a read-only plan, verified raw
backup, exclusive maintenance lock, resumable cutover and guarded rollback. Exact
IDs preserve source identity; incompatible same-ID records or attachment
collisions stop migration. Previous raw variants and record versions are audit
history, not another live dataset. See the
[storage migration runbook](../07-static-deployment/UNIFIED-INFORMATION-STORAGE-MIGRATION.md)
for operational steps and rollback limits.

Publication/export authorization remains separate from review and confidence.
Each active source record has an independent `publication_scope` of `public` or
`private`. Migration preserves previously published canonical sources as public;
intake, retained-cache sources and internal canonical records remain private.
New acquisition defaults to private, and reviewing a private source preserves its
scope. Cache metadata cannot grant review or publication. Existing confidence
is reused; this change adds no scoring model.

Static builds and public search use a read-only public projection. It also hides
derived records that depend on private sources and removes private backlinks
from otherwise public records. Private intake, model output, user annotations,
retained caches and audit backups are not published by this change. Review is
never inferred merely because a record appears in a search result or report.

The implementation is prepared in the isolated
`feature/unified-information-20261113` checkout. This document records prepared
behavior, not a completed production migration or deployment. Runtime migration
and release require their own verification receipts.

## Local validation

Physical migration and public-scope checks passed 23 focused tests, including
backup coverage, collision handling, interrupted cutover/resume, rollback,
activation guards, cache-reference hydration, stale acquisition protection and
private dependency projection. These are local fixture checks; they do not prove
that a live runtime has been migrated.

Container startup and compose checks passed 12 tests. The entrypoint passed a
Bash syntax check; partial activation blocks startup, active restarts do not
recreate legacy evidence directories, and private runtime/backup paths are
excluded from Git.

Earlier logical-catalog validation:

A consolidated changed-path run passed 133 tests, including catalog membership,
readonly scope, source readers, metadata preservation through optional review,
topic-body retrieval and static privacy. Separate focused runs passed 241
search/investigation/landscape/export tests, 147 report/research tests and 69 topic
retrieval tests. UI checks passed 46 Python tests and 173 frontend tests;
TypeScript checking and the production frontend build passed. Record validation
passed. The static build wrote 2,429 pages and verified that unpublished draft
IDs/titles were absent.

Final catalog, exclusion and same-source preview checks passed 16 tests. The
additional company/News/packet/map adapter checks passed 30 tests.

A full-suite collection enumerated 7,995 tests during development. Execution
was stopped during the
unchanged export tests because those tests took several minutes each on this
Windows workspace. A full-suite pass is not claimed; the required repository CI
checks remain a prerequisite for merge or release.
