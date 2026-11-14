# Berry Intelligence — current mission status

## Company news review preset — implementation pending release

Report Builder now has a company-list review implementation with fixed
publication dates, platform-first research, bounded web gap filling,
per-company outcomes, resumable checkpoints and matching saved-row PDF/Excel
exports. The native company report reader replaces the long embedded-document
experience when structured report data is available. Existing report artifacts
and human trust decisions remain separate.

This is implementation status, not a claim that the new workflow is live or
that collection coverage is repaired. Source-backed live acceptance, release
checks and event-level coverage diagnosis remain pending. See
`docs/v2/COMPANY-NEWS-REVIEW-PRESET.md` and TD-REPORT-NEWS-001.

## Strawberry company report availability and capability audit — November 13

The strawberry company review is live in **Reports & Briefings → Reports →
Research reports**, with an in-app reader and PDF/Excel downloads.
[Open the report](https://intel.johnnyaceii.com/reports/library/strawberry-company-news-20261113).
The private catalog and optional XLSX support are delivered through
[PR #576](https://github.com/samsonFive/berry-intelligence-os/pull/576).
The report files and source notes remain outside this public repository.
Automatic company-news generation and source/claim approval remain separate work.

Local validation: 102 focused tests passed with two Windows symlink skips.
Desktop and phone browser checks confirmed all 27 company headings, 83 source
links, no page errors or phone overflow, and byte-identical private PDF/XLSX
downloads. All five code CI checks passed. Live HTTPS checks using normal
sign-in confirmed the report reader, original PDF/Excel bytes, login protection
and continued availability of the existing Regina report. Operational release
and preservation records remain private.

The audit identifies reusable saved cohorts, exact-date news packets, Research
Desk, report drafts/source snapshots and PDF export. It records the remaining
company-news generator work as TD-REPORT-NEWS-001. See
`docs/audits/STRAWBERRY-COMPANY-REPORT-CAPABILITY-2026-11-13.md`.

## Curated variety reports — November 13

Published through [PR #574](https://github.com/samsonFive/berry-intelligence-os/pull/574), canonical merge `6f74665b`: the descriptive Regina profile is the reference for a reusable variety-report standard. **Reports & Briefings → Reports → Research reports** now provides an in-app reader and direct PDF download alongside working drafts. The four-page report retains its image, 16 source links, and clickable video. See [the report](https://intel.johnnyaceii.com/reports/library/regina-blackberry), [PDF download](https://intel.johnnyaceii.com/reports/library/regina-blackberry/download.pdf), and `reports/README.md`.

All five release checks passed. Local desktop/mobile layout checks and live HTTPS sign-in, reader, and byte-identical PDF-download checks passed; anonymous access remains protected. The healthy release retains 30,261 runtime files, 906 existing static assets, all 32 environment values, mounts, settings, and copilot image, with the collection timer restored and a fresh verified backup. The live image and release pointer match. Supporting preservation details and exact receipts are recorded in [the release note](docs/v2/REGINA-REPORT-LIBRARY-2026-11-13.md).

## Global Watchlist reconciliation — November 4

Global Watchlist #505 is now merged at `ae22ea07` and its healthy runtime uses image `20c8a5a0`. At the last observation the release owner was still reconciling its version receipt; this integration does not modify that record. The draft preserves the dashboard, shared table controls, scoped Reader links and source corrections. Both response imports are retained where the catalog redirect safeguards meet the new preference endpoints.

The preceding #506 head `53bfc5f5` passed all four checks (6,717 tests), 610 affected checks and native desktop/phone review. The newly reconciled head requires its own checks and current-live preservation. Earlier workflow timings and data counts below remain dated prior-head evidence. The user approved removal of only the earlier redundant #506 test copy; its 25,271 files were rechecked against retained base/delta recovery archives before cleanup. Archives, receipts, images and live data remain.

**Earlier preparation snapshot (retained with its original scope):**

Updated November 4, 2026. The healthy interactive app now runs source-intelligence
#501 at `d785c182`, with equal recorded/running image `ed6d0f4c`, retaining
editable catalog #492. The completed private review of the preceding #492 base
verified all five accounts including Chris.H, 1,259 profiles, 11,830 existing
protected JSON records, four databases and 1,115 research files. These are dated
isolated-review counts, not a new census of #501's changing runtime.

Combined draft [#506](https://github.com/samsonFive/berry-intelligence-os/pull/506)
retains platform #500, source #498, harvest/Learn #504, checklist #503 and now the
live #501 changes. The preceding exact head `e0d898c7` passed all four checks
(6,686 tests), 455 affected checks and desktop/390px review. Its 47 private
route/PDF checks passed, preserving existing data and adding only six source
and README files. Twenty-four complete-response comparisons matched across
eight fresh processes; 25,271 isolated runtime files stayed unchanged. The tested
workflows improved about 47–49%, but first catalog visits still took 5.8–6.4s.
Those results remain evidence for that head, not acceptance of this revision.

Next: validate the current #506 combination, repeat current-live preservation,
then request exact-head release approval. Nothing is merged or deployed by this
integration. Existing archives, original test copies, settings, data mounts,
operator edits and human decisions remain. No further cleanup or provider call
is authorized. Old component approvals do not cover this combined release.

The dense News/Reader, consolidated navigation, collaborative Workspaces,
private Digest/layouts, Companies, four-crop Landscape/reporting, 27 visual Learn
lessons and visual Help explainer remain delivered. The
[31-requirement checklist](docs/v2/REDESIGN-REQUIREMENTS-CHECKLIST.md) retains every
accepted requirement and the remaining work. Broader source/profile depth,
cold-load speed, independent expected-name/photo answers, held Map figures and
Learn quality remain open. Source occurrences are not approved identities.

Earlier status text is preserved in
[history](PROJECT-STATUS-HISTORY.md#november-4-2026---status-before-live501-reconciliation).
