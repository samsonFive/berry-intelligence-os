# Validation results

Local environment: Windows, Python 3.13.7. The repository's hosted Python 3.12 checks remain required before merge; publishing the branch is awaiting explicit user approval after automatic approval review blocked the upload.

## Automated checks

- Complete repository run: **6,619 passed, 10 skipped, 1 failed** in 2,507 seconds. The sole failure was the old primary-navigation expectation in `test_snapshot_workspace_navigation.py`, which still required Landscape Explorer in the primary menu.
- That expectation now requires Global Watchlist in the shared primary navigation and separately verifies that Landscape Explorer remains available in the supporting menu. Both authoring and readonly modes passed in the final **36-test** dashboard/navigation regression run. No application change was needed to resolve this failure.
- Together, the full run and the successful rerun validate **6,620 distinct passing cases, with 10 skipped**. The full run was not repeated after the assertion-only correction. The final PDF direction/AI-status changes also passed all 10 dashboard tests and the browser download check.
- Earlier combined coverage: 225 passing registry/profile/comparison/Watch/authentication/alias-recall/correction tests.
- `scripts/validate_records.py`: all canonical records passed.
- Static snapshot: 2,415 HTML pages generated; draft leakage check returned `[]`; protected Global Watchlist was not generated into the public output. Pagefind indexed 2,414 eligible pages successfully. Its final subprocess was rerun outside the Windows sandbox after an output-write permission denial; no build-code workaround was introduced.

Raw local test logs are kept under ignored `tmp/`, including `gw-committed-full-suite.log` and `gw-final-navigation-check.log`.

## Real-record acceptance flow

An isolated runtime exercised real canonical Planasa and Fall Creek records through the application endpoints. All seven checks passed: combined tier/berry/region filtering; saved membership across filter changes and reloads; comparison-to-profile context; durable following; attributed unreviewed hypotheses; persistent association correction with alias-recall suppression; group rename/member removal/deletion. No canonical records were edited by this check.

The September 15 tier source was applied twice: identical structured report, identical serialized report hash, same object ID and **version 1**. Results: 33 source rows, 132 retained berry cells (including explicit unassigned values), zero unmatched canonical IDs and zero conflicting cells. The source remains an unreviewed transcription.

## Visual and export checks

Authenticated Chrome checked 1440x1000 desktop and 390x844 mobile views. Two-company selection opened two comparison profiles, the PDF download completed, JavaScript error list was empty, and mobile page/profile widths were both 390px without page overflow. Screenshots are retained beside this report.

The final five-page Planasa/blueberry PDF was rasterized and every page inspected. Its source register, page headers/footers, table, source links and section transitions are legible without overlap or clipping. Company assessments preserve AI PROPOSED versus REVIEWED status; ownership/licensing relationships name both endpoints in their stored direction. Publication and capture dates remain separate, undated catalog pages remain distinct developments, and demo/private draft fixtures are excluded.

No production deployment, canonical merge, remote branch push or pull request creation was performed.
