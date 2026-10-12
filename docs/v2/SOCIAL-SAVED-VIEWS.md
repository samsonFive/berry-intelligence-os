# Saved Social Listening views — October 7, 2026

Saved views reopen applied filters without repeated setup. The compact disclosure supports naming a view, reopening it, updating the same name with its current revision, and removing it. Matching posts link back to saved views in the existing reader. All berries remains the default for new views; corporate and consumer views can be saved separately.

## Private state and scope

The implementation extends the existing private `watchlist_state.json` with `social_profiles`, using the shared serialized writer and atomic replacement. Existing `watches` and unrelated state keys are preserved. No canonical registry, SQL or trusted-record migration is required. Data stays in the configured inbox and never enters static public output.

Each entry stores validated applied filters, a stable name-derived ID, revision, update time, optional scope reviewer and review time. Saving captures berry, platform, provenance mode, language, purchase market, company/variety, perspective, role, dates, text query and selected workspace view. It does not capture a transient drilldown ID subset or a source-query execution plan. Mode isolation, English-readable visibility and matching reader links use the existing shared aggregate contract. A view is a live selection of retained records, not a frozen result snapshot.

A company/variety selection must reference an existing canonical entity and retains a disabled target using the existing `WatchProfile` suggestion contract. Explicitly naming a scope reviewer records scope review only. It neither qualifies extraction/source rights nor promotes observations into Evidence, Facts, Signals or Assessments. Changing a saved scope without a reviewer clears its prior scope-review label.

## Operating controls and rollback

Collection remains disabled (`monitoring=false`, all target `enabled=false`). Save/remove routes use existing private authoring, authentication and same-origin checks. Unknown fields/scopes, invalid dates, stale revisions, duplicate names without the current revision and more than 50 views are rejected. Unreadable/invalid saved profiles fail closed and preserve the existing file. Saving performs no source request, paid operation or external transmission.

Back up the private watchlist file before operational changes. Rollback code may leave the additive `social_profiles` key in place; existing watch operations preserve it. Restore the whole file only from an operator-selected backup that includes subsequent watch changes, or remove only the additive key under the same serialized writer. Never replace unrelated watches with an older profile-only snapshot. Removing a view leaves observations/media and existing watches intact.

## Validation and remaining work

The initial focused social/watchlist suite passed 144 tests with one existing dependency warning. After reader-link changes, the profile/routes/watchlist suite passed 61 tests; the final changed profile/routes checks passed 32 tests. Coverage includes restart, reciprocal preservation of existing watches and saved views, stale revisions, invalid scopes, corruption preservation, same-origin/authentication, and positive/negative reader matching. Browser verification saved an unreviewed **Blueberry posts** view in the isolated trial runtime, reloaded it with the same 41-post selection, and displayed its matching link in the reader. Private screenshots remain outside Git.

This completes saved filtering and initial durable registry-linked scope, not unattended monitoring. Editable handles/exclusions/cadence/budget plans, source rights/deletion refresh, real recovery drills and qualified downstream assembly/retraction remain open. No new collection, purchase, merge or deployment occurred. Required checks must pass on the final PR HEAD; prior-head checks are historical evidence only.
