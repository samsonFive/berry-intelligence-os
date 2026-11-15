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

The legacy `data/evidence`, `inbox/evidence`, and retained-web files remain storage
adapters behind the shared catalog. This is a non-destructive logical unification,
not a bulk file migration: ingestion, review history, attachments and existing IDs
keep working without copying or overwriting production runtime data. A later
physical storage consolidation must migrate every writer and attachment reference
together. There is no second persisted master catalog to become stale.

Publication/export authorization remains separate from review and confidence.
Static builds and public search continue to read their explicitly exportable
snapshot; private intake, model output, user annotations and retained caches are
not published by this change. Review is never inferred merely because a record
appears in a search result or report.

The implementation is prepared in the isolated
`feature/unified-information-20261113` checkout. Production runtime files have not
been migrated and this change has not been deployed.

## Local validation

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
