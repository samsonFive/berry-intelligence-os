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
