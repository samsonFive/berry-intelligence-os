# Global Watchlist dashboard and PDF export

Open `/global-watchlist` in the existing private application. The top navigation and retained sidebar now point to Global Watchlist; `/competitors` bookmarks redirect with their query parameters. Executive Landscape, Map Explorer, Geography, Variety and capability-research views remain connected supporting surfaces.

## Resulting behavior

The local checked corpus projects 166 organizations, including the complete original 33-entry roster. Select a berry-specific tier, a saved workspace group, geography, market or canonical entity; combine filters and search aliases. Followed/grouped entities and imported tier members precede the remaining alphabetic inventory. Unknown classification, confidence and evidence are explicit. The bounded, keyboard-scrollable table keeps the relevant news and group controls reachable.

Select up to four organizations to compare, inspect scoped existing capability judgments, then open a company without discarding the comparison URL. Profile sections connect canonical varieties/brands, genetics, people, jobs, IP, awards, locations, source relationships, observations and retained research where captured. Genetic potential and commercial adoption are separate evidence sections. There is no new numerical threat or competitiveness score.

Monitoring groups are explicitly shared within the protected workspace, with creator/actor attribution. Create, rename, delete and add/remove members use transactional, versioned SQLite objects/history. Filters never change membership. Following reuses the existing durable Watch store and My Watches navigation, including canonical program/brand routes.

Observations, sourced claims, hypotheses and anecdotes remain unreviewed workspace capture; they cannot self-promote to verified Facts. Association corrections use canonical source/entity IDs and versioned inclusion/exclusion decisions. Private profiles/readers and alias recall consume the same overlay on each request; reprocessing a stable source ID cannot erase it. Public output does not include private correction decisions, notes or groups.

`Export PDF` downloads a paginated A4 report of the same company/comparison/filter projection, including source provenance, scope, publication versus capture dates, evidence gaps, research review states, private-note attribution and complete scoped source register. ReportLab is an existing runtime dependency; pypdf is added only to development requirements for PDF content tests. No internal or demo sensory values are included.

## Tier import and missing input

Source: `data/imports/competitor-registry-2026-09-15/snapshot.json` and `reconciliation-matrix.json`, a retained transcription of the operator's original internal spreadsheet screenshot. Report: `tier-import-report.json`. The checked import has 33 mapped rows, 132 distinct per-berry assignments, zero unmatched canonical IDs and zero conflicting cells. Importing identical input repeats the same object/version, rather than duplicating assignments. Regional scopes, effective dates and source-defined definitions are preserved when supplied; ambiguous scope rollups remain unassigned.

The retained source is **unreviewed_import**, with a transcription caveat. The original workbook/independently verified screenshot transcription and formal tier definitions are not supplied by this snapshot. This release preserves its labels and assignments without upgrading their authority or inventing a scoring methodology.

The older September 19 build-package workbook was also checked. Its `Entities.monitoring_tier` and `Method` describe collection cadence (monthly, quarterly and semiannual), a separate taxonomy that is not substituted for the regional, berry-specific competitor assignments.

```powershell
python -m scripts.import_global_watchlist_tiers --apply --report tier-report.json
# Optional subsequent source, with exact canonical IDs or unambiguous exact aliases:
python -m scripts.import_global_watchlist_tiers --source tier-snapshot.json --apply --report tier-report.json
```

Both commands use the application's configured runtime paths. Omitting `--apply` validates without writing runtime assignments. The import never creates entities or claims. Source conflicts and unmatched/ambiguous aliases remain reported for repair.

## Review and validation

- `IMPLEMENTATION.md`: actual reuse map and additive storage contract.
- `screenshots/`: desktop watchlist, rows, comparison and profiles; 390px mobile overview/profile details.
- `visual-results.json`: comparison selection and horizontal-overflow/JavaScript checks.
- `python -m scripts.verify_global_watchlist_browser`: reproducible authenticated localhost visual check; uses an isolated `tmp/` runtime, ephemeral in-memory credentials, Chrome (`CHROME_PATH` override), and shuts its server down. No production deployment or collection.
- `pytest tests/test_global_watchlist.py`: persistence, optimistic concurrency, tier scopes/idempotency, exact-ID links, correction replay and public isolation, notes, PDF content, authorization and same-origin mutation checks.
- Existing comparison, registry, profile, Watch, source-recall and authentication suites provide regression coverage. Legacy navigation tests now assert the consolidated destination.
- Canonical record validation and the complete static build passed locally. The static build generated 2,415 pages and verified no unpublished draft IDs/titles leaked.
- Final counts and the full-suite/navigation rerun breakdown are recorded in `VALIDATION.md`.

## Runtime and release limits

- Private research returns in another checkout's `inbox/` are not automatically copied into this worktree. Configure the normal existing `BIOS_RUNTIME_DIR`/`BIOS_INBOX_DIR` when reviewing against an established runtime; missing research stays explicitly empty. Runtime contents are never committed.
- The release adds no social/API subscriptions, collectors, live source connections, automatic source promotion, new capability formula or IP/legal-status inference. Existing stored scopes and trust gates remain controlling.
- Districts, jobs, awards, relationship dates, comparability context and current capability evidence are available only where real records provide them. Missing evidence is never represented as zero performance. Canonical dossiers and research views remain the full-detail workflows.
- Corrections apply to source associations in the protected shared corpus. They do not rewrite already-reviewed Fact statements, relationship assertions or assessment judgments; those retain their existing explicit review workflows.
- No production deployment or canonical-branch merge is included. Exact-head repository CI remains the release/merge gate.


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


## Four seeded custom Watchlist landscapes

The original Global Watchlist release is live at https://intel.johnnyaceii.com/global-watchlist (canonical `ae22ea07`, tested `ce2b3bc1`). Its HTTPS browser verification covered 244 organizations, the shared sheet/Reader, alphabet navigation, a ten-page Planasa PDF and mobile overflow, with zero JavaScript errors. The release preserved 4,551 substantive data files, saved private state and the account/workspace databases. The deployment manifest changes deliberately with the revision; it is not an intelligence record. Release metadata and rollback remain recorded on the host.

The requested follow-up adds Global Blueberry Landscape, Global Blackberry Landscape, Global Strawberry Landscape and Global Raspberry Landscape as starter saved scopes. Each selects one berry and leaves geography unrestricted. They recompute against current captured records, not frozen organization lists. Scoped PDFs name the selected saved landscape. Monitoring groups, follows, canonical intelligence and tier review states are unchanged.

The existing private `landscape_views.json` store holds the selections and history. A backward-compatible `surface: watchlist` marker routes these views to Global Watchlist; their existing overview kind remains readable by prior app images. Normal authoring startup seeds only absent defaults. Repeated startup preserves edits, custom names, archives and existing views. Users can save, update, copy, archive and restore scopes with revision checks and existing same-origin protection. Existing Workspaces links resolve these same current scopes.

Validation: 77 related Watchlist, Landscape, Workspaces and Reader-return checks pass. Browser verification exercised all four global scopes and their PDF buttons, custom-copy persistence, archive/restore and phone layout with zero JavaScript errors. Screenshots and `default-landscapes-visual-results.json` use the committed local snapshot (166 organizations); the live corpus is larger. Fresh exact-head hosted CI and coordinated release checks remain required for the seeded-landscapes follow-up; it is not yet deployed.
