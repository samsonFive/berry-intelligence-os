# Berry OS repair checkpoint — 2026-09-11

Branch: `fix/astra-news-reader` in `C:/Users/Johnny/Downloads/sscanar/berry-intelligence-os-astra-repair`. No merge, production deployment, production writes, or model calls performed in this checkpoint. Previous checkpoints: bdb4c69 and 759ed42. Use `git log -3 --oneline` for the newest repair commit.

## Completed in this checkpoint

- Company coverage service: inclusive last 90 calendar days by publication date; separate undated/history; pending status and readable-text counts; duplicate IDs counted once; no stored evidence mutations.
- Cal Giant company page: current coverage, direct report handoff with company name and window, archive links, collapsed full history, clearer archive labels. Existing canonical identity/alias repair remains on the branch.
- Company reports: complete article inventory beyond the top-15 synthesis cap, opening excerpts where text exists, explicit blocked/missing text, separate pending/undated items, no pending inventory in trusted model grounding. Unrelated variety candidates no longer inflate company coverage.
- Reports/PDF: working-report review marker replaces false automatic analyst-review claim; readable company name and publication window in PDF scope.
- Company timelines suppress consent/access-page summaries without modifying original evidence. Evidence reader hides empty metadata; reader subject attribution no longer incorrectly describes published evidence as pending.
- Source references now link the official Cal Giant newsroom, retaining manual/reference status. Read-only `scripts/audit_company_coverage.py` reproduces local coverage counts.
- TD-113 and Coverage Matrix document the unresolved acquisition gap.

## Verification

- `fix-tests.txt`: 128 passed.
- `report-final-tests.txt`: 92 passed.
- `last-focused-tests.txt`: 112 passed, including package export round-trip, company reports, shared-reader integration, attribution, and UI shell tests.
- First full suite: **2634 passed / 5 failed**, in 714.89 seconds (`final-tests.txt`). Three obsolete heading assertions were updated; empty-report test was isolated from local runtime. Package export mismatch arose while the canonical company description changed during the run; unchanged-data export round-trip passed in the subsequent focused run.
- **Fresh full suite is still RUNNING at handoff.** Command: `../berry-intelligence-os/.venv/Scripts/python.exe -m pytest -q --tb=short --basetemp=.astra-tests-clean`; output: `artifacts/astra-repair/clean-full-tests.txt`; tool session 27040. Do not claim a green full suite until reading completion. Application/test/data files were frozen before this run. Its actively written log is intentionally not staged.
- `scripts/validate_records.py`: all validated records passed (`record-validation.txt`).
- `scripts/build_static.py`: 1630 pages, Pagefind built, no unpublished draft IDs or titles leaked (`static-build.txt`).
- Local report creation and PDF export returned 200 using an explicit no-model verification process. PDF text checked and first page rendered/visually inspected. `verify_local_report.py` reproduces this; it writes only this worktree's private inbox. Do not run it during full-suite tests.
- Actual browser checks: Cal Giant search returns canonical company; company → named 90-day report → scope preview works; report shows zero unrelated variety candidates; blocked source text becomes a notice; archive shared reader next-story URL changes and Escape clears story URL/restores focus after close animation. Desktop 1280 and mobile 390 viewport checks found no document overflow. Screenshots are in `screenshots/`; desktop captures are soft due to browser capture scaling, mobile capture is clearer. No screenshot content was inserted.

## Remaining issues / do not overclaim

**Freshness/acquisition is NOT fixed.** Local published data has 20 Cal Giant mentions, nine access-screen records, and zero current articles in June 14–September 11. User's production audit reports different counts; local and production were not reconciled. Official June–August coverage remains missing and direct acquisition returned HTTP 403. This checkpoint improves identity, scope, source-quality honesty and report completeness; it does not yet supply the missing recent intelligence.

Next priority: supported forward acquisition through the existing discovery/intake pipeline, followed by private publication review and evidence-backed company reporting. Do not fabricate source text or approve recovered/new sources automatically. The no-model local report intentionally exposes insufficient content; it is a verification artifact, not a stakeholder-ready Cal Giant analysis.

Existing reports re-resolve source packets against current data when reopened while edited prose is preserved. Consider this live-packet behavior when assessing report reproducibility; do not silently turn saved drafts into frozen evidence snapshots.

The local preview server was last started on port 8018, PID 25144; verify process command before stopping only that owned server. Two private verification reports were created in this worktree's ignored inbox. Latest: `/reports/rp-b47f7fc0948be290`.

## Resume economically

Give the next agent `NEXT-AGENT-PROMPT.md`. First read the completed clean-full-tests log, fix any remaining failures with targeted reruns, then commit final test evidence. Do not rerun the whole audit or full suite without a reason. No usage-reset credit was consumed; at handoff the five-hour account window was 93% used.
