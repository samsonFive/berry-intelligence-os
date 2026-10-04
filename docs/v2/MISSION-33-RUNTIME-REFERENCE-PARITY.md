# Mission 33 — Persistent runtime reference parity

Release review found that Map statistics and its new review page read `data/configuration/market_statistics_reference.json` relative to the repository. Docker packages seed data under `/app/seed/data` and serves persistent records from the configured runtime. Those repository-only reads would fail in the deployed layout even though desktop tests passed.

Both views now use the existing runtime data-directory rules: explicit `BIOS_DATA_DIR` first, otherwise `BIOS_RUNTIME_DIR/data`, otherwise the local repository data directory. The shared loader reads existing configuration without copying seeds or writing records. Startup's existing additive sync already supplies missing configuration while retaining operator changes; its behavior is untouched.

An absent reference file means unknown coverage, with no fabricated figures or fallback into unrelated repository data. A malformed reference file fails closed with a readable recovery message. Invalid source links, numeric values and unit labels are rejected rather than displayed as valid references. Capture/apply routes check that configuration before reserving a new job or saving a reference selection. Original file bytes, private history and canonical records remain untouched.

## Verification

Initial runtime/Map/snapshot/static acceptance: 99 passed / one existing ReportLab warning in 14.53 seconds. Final malformed-cell/public-safety acceptance: **107 passed / one existing warning in 13.75 seconds**. Tests use a separate persistent directory with an illustrative override, verify identical Map/snapshot values, check data-directory precedence, preserve exact operator bytes and prove missing/corrupt data neither falls back nor creates new review state. No live provider or production mutation occurs.

This is deployment-layout logic, with no new interface layout. Mission 32's real source/browser acceptance remains separate. An actual container build/deployment and combined authenticated acceptance are not claimed. Exact pushed-head CI remains required; the canonical expansion guide must stay unchanged.

## Remaining release acceptance

A read-only inventory found 34 templates extending the older shell; code references alone do not prove that each is an active separate section. Actual browser review confirms that the Source authenticity queue still shows the older sidebar, older menu groupings and technical copy. Classify retained specialist routes separately from explicit legacy compatibility routes before replacing their chrome or recommending section retirement. Preserve Source authenticity, publication and individual-statement decisions as distinct workflows, with all original text/actions/history retained.

Wider market population, older-PR/retained-workflow parity, final visual Guide walkthrough and combined release/backup/rollback review remain. No merge or deployment before final human approval.
