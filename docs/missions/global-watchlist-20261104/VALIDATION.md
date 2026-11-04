# Validation results

Local environment: Windows, Python 3.13.7. The repository's hosted Python 3.12 checks on [draft PR #505](https://github.com/samsonFive/berry-intelligence-os/pull/505) remain required before merge.

## Automated checks

- Complete repository run: **6,619 passed, 10 skipped, 1 failed** in 2,507 seconds. The sole failure was the old primary-navigation expectation in `test_snapshot_workspace_navigation.py`, which still required Landscape Explorer in the primary menu.
- That expectation now requires Global Watchlist in the shared primary navigation and separately verifies that Landscape Explorer remains available in the supporting menu. Both authoring and readonly modes passed in the final **36-test** dashboard/navigation regression run. No application change was needed to resolve this failure.
- Together, the full run and the successful rerun validate **6,620 distinct passing cases, with 10 skipped**. The full run was not repeated after the assertion-only correction. The final PDF direction/AI-status changes also passed all 10 dashboard tests and the browser download check.
- Earlier combined coverage: 225 passing registry/profile/comparison/Watch/authentication/alias-recall/correction tests.
- After reconciling the current canonical catalog-authoring release into the feature branch, all 50 focused dashboard, navigation, registry-integration and catalog-authoring checks passed. The PR runs a new complete check set on the updated head.
- `scripts/validate_records.py`: all canonical records passed.
- Static snapshot: 2,415 HTML pages generated; draft leakage check returned `[]`; protected Global Watchlist was not generated into the public output. Pagefind indexed 2,414 eligible pages successfully. Its final subprocess was rerun outside the Windows sandbox after an output-write permission denial; no build-code workaround was introduced.

Raw local test logs are kept under ignored `tmp/`, including `gw-committed-full-suite.log` and `gw-final-navigation-check.log`.

## Real-record acceptance flow

An isolated runtime exercised real canonical Planasa and Fall Creek records through the application endpoints. All seven checks passed: combined tier/berry/region filtering; saved membership across filter changes and reloads; comparison-to-profile context; durable following; attributed unreviewed hypotheses; persistent association correction with alias-recall suppression; group rename/member removal/deletion. No canonical records were edited by this check.

The September 15 tier source was applied twice: identical structured report, identical serialized report hash, same object ID and **version 1**. Results: 33 source rows, 132 retained berry cells (including explicit unassigned values), zero unmatched canonical IDs and zero conflicting cells. The source remains an unreviewed transcription.

## Visual and export checks

Authenticated Chrome checked 1440x1000 desktop and 390x844 mobile views. Two-company selection opened two comparison profiles, the PDF download completed, JavaScript error list was empty, and mobile page/profile widths were both 390px without page overflow. Screenshots are retained beside this report.

The final five-page Planasa/blueberry PDF was rasterized and every page inspected. Its source register, page headers/footers, table, source links and section transitions are legible without overlap or clipping. Company assessments preserve AI PROPOSED versus REVIEWED status; ownership/licensing relationships name both endpoints in their stored direction. Publication and capture dates remain separate, undated catalog pages remain distinct developments, and demo/private draft fixtures are excluded.

The user explicitly authorized publishing the feature branch and opening draft PR #505. No production deployment or canonical-branch merge was performed.


## November 4 design review follow-up

The watchlist now uses the existing Glasshouse news shell and `_news_cards.html`: publisher visuals or labeled illustrations, review labels, save/feedback controls, company context and the shared slide-over Reader. Grouped sources retain publication/capture dates and independence disclosures. No news model, collection or trust policy changed.

The existing variety column engine is now shared through `glasshouse_base.html`, with compact Workspaces-style grid cells, sticky headers, frozen identity, resize/reorder/hide controls, keyboard resizing and column movement, account-persisted layouts, loaded-row search/sort, text wrapping, keyboard cell navigation and visible-row CSV export. The governed Workspaces and competitive-grid controllers remain responsible for their richer editing workflows. The shared endpoint is an alias over the existing private analyst preference store, including optimistic revisions, actor isolation, same-origin writes and no-store responses. CSV escapes formula-leading cells. Loaded-row controls apply to the rendered sheet; the PDF retains the complete URL-filtered scope.

Alphabetical organization navigation now filters the same server projection used by the news and PDF while preserving berry/region/group filters. Companies, Varieties and Watchlist reuse one alphabet macro. News remains chronological. The site design contract is recorded in `AGENTS.md`.

Validation: 93 related watchlist, company directory, news, shell, variety preparation and Workspaces tests passed. An earlier 36-test run covered watchlist/PDF, preference validation, variety routes/sheets and public static safety. The final route/no-store rerun passed 16 tests. Authenticated Chrome checks exercised 166 organizations, resize/reorder/hide, account layout restoration, wrap, search, alphabetical scope, shared Reader, company/variety compatibility and 390px page overflow, with zero JavaScript errors. Updated screenshots are in `screenshots/design-*.png`.

The authenticated local review preview is running at `http://127.0.0.1:18766/global-watchlist` in the dedicated review Chrome window. It uses isolated review state and disables collectors. Previous-head CI passed; fresh CI is required for this follow-up head. Merge and deployment remain held for review.


## Approved release verification

The user approved deployment on November 4 after reviewing the feature and PDF export. All four hosted checks passed on `bd96a7bc` (6,634 tests passed, 11 skipped). An isolated candidate on the configured host passed against its richer published corpus (244 organizations; 30 scoped news cards; a nine-page Planasa export), with authentication, alphabetical scope, private preference revisions/CSRF, News, Workspaces, Companies and Varieties checked. The host runtime/configuration backup was created and verified before any switch.

Visual inspection of all nine production-corpus PDF pages caught people/hiring records separating from their citations across a page break. The release follow-up wraps those blocks together where they fit. A 20-record regression reproduced the defect before the fix and passes after it; all 12 watchlist tests pass. This formatting-only fix requires fresh exact-head CI and a regenerated candidate before merge/deployment. Approval continues to cover the requested release; no trust promotion or new source acquisition is involved.


Canonical reconciliation: `d785c182` (source-intelligence PR #501) landed during release gating. The watchlist branch incorporates that canonical release and resolves the shared news-card conflict by retaining media labels/scoped full Reader links plus grouped-source disclosures. All 75 focused Watchlist, News, Reader-return and Workspaces tests pass. The on-host candidate must use the current source-intelligence image as its base, followed by fresh exact-head CI.
