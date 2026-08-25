# Freshness Assurance + Collection Gap Detection V1

## Scope and trust boundary

Freshness Assurance is a read-only backend projection over existing Source Health, exact per-Source cadence policy, discovery state, bounded collection-run summaries, and private draft/discovery metadata. It does not fetch Sources, change cadence, infer market activity, publish Evidence, make review decisions, run extraction, call a model, or perform historical reacquisition.

The contract is implemented by `app.services.freshness_assurance.build_runtime_freshness()`. `scripts/freshness_status.py` is its operator CLI. JSON output contains identifiers, operational states, timestamps, counts, reasons, and alert codes only—never article bodies, excerpts, credentials, or review history.

## Existing semantics audit

What already existed:

- `source_freshness.py` distinguished successful quiet checks from failures and recognized blocked access responses.
- `source_cadence.py` resolved the exact deterministic cadence, selected due/not-due Sources, respected Source Health, and calculated feed-window ceilings.
- per-Source discovery state retained `last_checked_at`, `last_success_at`, status, error, found/new/known counts, and historical-backlog count.
- collection run summaries retained per-Source outcome and new/duplicate counts; pipeline/scheduler records retained operation completion and outcome.
- Source Health, Monitor, Morning Brief, Review Operations, and `collection_status.py` already exposed pieces of this state.

What was inferred or incomplete:

- legacy Source Health used calendar-day cadence labels rather than the optimized second-level policy for overdue decisions;
- “latest item” mixed publication and capture visibility but did not establish a protected system-wide last-new-intelligence clock;
- no one contract separated last attempt, last success, and last genuinely new discovery;
- no system claim was gated by overdue/failing/blocked/never-run Sources;
- no berry, geography, explicitly linked actor, or normalized source-type freshness rollup existed;
- feed-window risk was available only through the one-off cadence audit, not as a recurring deterministic condition;
- no bounded yield-drift condition distinguished acquisition change from inferred competitive inactivity.

Today V1 landed while this mission was in progress. Its provisional pipeline-level freshness helper was replaced during reconciliation: Today now consumes this service and retains only presentation compatibility aliases. It no longer derives `current_through` from pipeline maximums or trusted-record capture dates.

## Three clocks

Every Source exposes three separate timestamps:

1. `last_collection_attempt`: the most recent attempt, successful or failed.
2. `last_successful_collection`: the most recent successful response/process anchor.
3. `last_new_intelligence`: the newest genuine discovered item's immutable `first_seen_at`.

A successful duplicate-only run advances the first two clocks but not the third. A pending review draft is sufficient to show acquisition occurred; publication/review state does not control freshness.

The system summary also exposes the newest Source attempt as top-level `last_collection_attempt`. All timestamps are normalized to UTC. Offset-aware inputs are converted; schema-compatible naive timestamps are interpreted as UTC rather than host-local time.

## Source state model

| State | Deterministic meaning |
|---|---|
| `CURRENT_ACTIVE` | Successful inside cadence; latest successful run produced at least one non-historical new item. |
| `CURRENT_QUIET` | Successful inside cadence; latest successful run produced zero new items. |
| `DUE` | One configured cadence interval elapsed, inside grace. |
| `OVERDUE` | Cadence plus one full cadence interval of grace elapsed without success. |
| `RETRYING` | One retained retryable failure after a prior success; existing bounded retry policy applies. |
| `FAILING` | Multiple consecutive retained failures, or a failure with no prior success. |
| `BLOCKED` | Existing Source Health access-block semantics; automatic polling remains paused. |
| `NEVER_RUN` | No retained attempt or run exists. |
| `INSUFFICIENT_HISTORY` | A state/attempt exists but bounded successful operation history cannot establish the full contract. |

The grace interval deliberately preserves the existing Source Health convention: a Source becomes due after one cadence, then operationally overdue after one additional missed cadence. It is exact to seconds. A six-hour Source is due after six hours and overdue after twelve; a weekly newsroom checked yesterday remains current even when its last new publication is old.

`due` and `overdue` are also explicit boolean fields. They remain visible when the primary state is `RETRYING`, `FAILING`, or `BLOCKED`, so a failed scheduled check cannot hide an already missed cadence. Aggregate overdue and failing counts may therefore overlap intentionally.

## System state and “current through”

`current_through` is the completion timestamp of the newest collection operation containing at least one successful Source. It is never render time, restart time, review time, reindex time, or the newest trusted record's capture date.

The application may display **INTELLIGENCE CURRENT THROUGH `<timestamp>`** only when:

- a successful collection operation exists; and
- no scheduled Source is `OVERDUE`, `FAILING`, `BLOCKED`, `NEVER_RUN`, or `INSUFFICIENT_HISTORY`.

Otherwise `system_state` is `DEGRADED`, `can_claim_current` is false, and the product should display a compact message such as **COLLECTION PARTIALLY DEGRADED — 3 scheduled Sources overdue**. `current_through` remains available as operational context but must not be presented as an unqualified system-current claim.

`DUE` and one bounded `RETRYING` Source do not independently make the system stale; they are visible conditions inside the configured operating window.

## Last-new-intelligence protection

`last_new_intelligence` is the maximum `first_seen_at` among discovered items excluding `historical_backlog`. This is deliberately independent from publication date and review state.

The following cannot advance it:

- duplicate-only collection;
- Source Fidelity recovery or bounded historical reacquisition;
- review, publish, reject, dismiss, or defer actions;
- reindexing, rebuilding, deployment, or restart;
- an old article's reacquisition timestamp.

`last_new_rich_draft` is separate and uses only non-repair `FULL_ARTICLE` publication artifacts. It never substitutes for `last_new_intelligence`.

## Coverage and gap detection

The same state rows are aggregated without article-body inference:

- berry: explicit `berry_ids` for Blueberry, Strawberry, Raspberry, and Blackberry;
- geography: explicit Source `region_coverage` only;
- actor: explicit `linked_competitor_ids` only, with `direct_monitoring_gap` when a linked direct Source is unhealthy;
- source type: deterministic precedence into `company_newsroom`, `trade_publisher`, `association`, `registry_government`, `academic_research`, `spoken_video`, or `other`.

Coverage means collection coverage, not observed market activity or actor importance. V1 flags `COVERAGE_DEGRADED` only when all Sources in a segment are unhealthy or unhealthy Sources reach at least 25% with a minimum of two. Individual gaps remain visible even below that threshold.

Only 16 canonical discoverable Sources currently carry explicit actor links. V1 reports those honestly and does not infer actors from article bodies or rank importance.

## Feed-window and yield drift

`FEED_WINDOW_RISK` reuses the cadence mission's observed-new-item velocity, visible feed depth, and 2x safety factor. It is emitted when configured cadence exceeds the recalculated safe interval. The condition recommends cadence review; it never changes cadence automatically.

Yield drift is operational, not competitive interpretation:

- `NEW_ITEM_YIELD_DEGRADED`: at least three earlier productive successful runs followed by three successful zero-new runs. Requiring repeated prior productivity prevents a one-time bootstrap/backfill run followed by normal duplicate-only checks from creating alert noise.
- `RICH_BODY_YIELD_DEGRADED`: at least three earlier `FULL_ARTICLE` drafts followed by three explicit thin/failure outcomes.

The language is “acquisition yield changed,” never “the Company/market went quiet.” Historical repair artifacts are excluded.

## Alert conditions

- `SOURCE_OVERDUE`
- `MULTIPLE_CONSECUTIVE_FAILURES`
- `COVERAGE_DEGRADED`
- `FEED_WINDOW_RISK`
- `RICH_BODY_YIELD_DEGRADED`
- `NEW_ITEM_YIELD_DEGRADED`
- `NO_SUCCESSFUL_COLLECTION_RUN`

V1 records conditions in output only. It sends no notification and changes no operational state.

Each alert retains its established `code` and also exposes a stable `condition` name for downstream consumers. Compatibility mappings are `MULTIPLE_CONSECUTIVE_FAILURES` -> `SOURCE_FAILURE_STREAK`, `COVERAGE_DEGRADED` -> `COLLECTION_COVERAGE_DEGRADED`, and `NO_SUCCESSFUL_COLLECTION_RUN` -> `NO_SUCCESSFUL_COLLECTION`. Top-level `alert_conditions` contains the unique condition names.

## CLI and JSON

```bash
python scripts/freshness_status.py
python scripts/freshness_status.py --json
```

The CLI reads at most the newest 500 collection/scheduler summaries by default and performs one pass across private discovered-item and draft metadata. It makes no network call and writes nothing. The service accepts a deterministic `now` for tests and consumers.

## Today and Review Operations integration contract

Today should call `build_runtime_freshness()` and consume at minimum:

- `current_through`
- `last_successful_collection`
- `last_new_intelligence`
- `system_state`
- `can_claim_current`
- `overdue_count`
- `failing_count`
- `blocked_count`
- `due_count`
- `retrying_count`
- flat `*_source_count` aliases for discoverable, current, due, overdue, failing, blocked, current-quiet, and retrying Sources
- `counts.overdue`
- `counts.failing`
- `counts.blocked`

It may also show `last_new_rich_draft` and compact berry coverage. It must not recompute freshness from pipeline maximum success, page render time, trusted `captured_date`, or publication/review state.

Review Operations can consume the same top-level fields and alert counts. Neither surface should parse CLI text; both use the Python service/JSON shape.

## Current production proof

PR #157 merged the implementation as `4f05bde1fd4f68cb553feb782636769ab8209704` after all four required checks passed. The first production audit exposed alert noise from treating one bootstrap/productive run as an established productivity baseline. A body-free replay over the same bounded production history showed that requiring three prior productive successful runs reduced `NEW_ITEM_YIELD_DEGRADED` from 30 Sources to five, each with 3-8 prior productive runs. PR #158 added that regression-tested correction and merged as final implementation canonical `0b9de659fb0d73c12dd6b9dfb5509d669d9c2d7a`; all four fresh checks passed again.

The final pre-mutation backup is `/var/backups/berry-intelligence-os/berry-runtime-20260824T171932Z.tar.gz`, independently verified across 12,715 manifest entries with SHA-256 `54d9305866e5d4fa462b89b229302bc2849e5f3d14cd0a8fdd0d5f11acc454f8`. The earlier implementation backup (`berry-runtime-20260824T170218Z.tar.gz`, 12,713 entries, SHA-256 `4682e3cd405942dce897873e1c4f8fee1d5289b3ab076e105b2d99036060ea0f`) was also independently verified. Both app-only rebuilds preserved the mounted runtime. Final counts match the second pre-deploy gate: 2,657 data files, 10,057 inbox files, 1,663 Evidence files, and 11 review-event files. Evidence tree SHA-256 `1734646bbf8382fe9bc2415f6a422dfd291019a6b730b7e6a719177750ff1d07` and review-event tree SHA-256 `152e45863113d8f8c722e57b0327355e65be407edfafb2dad6029f8684d25861` remained byte-identical. A verified restore comparison proved the only data-tree change during implementation startup was the expected `.canonical-promotion-manifest.json`; every other trusted data file was byte-identical.

The read-only production audit at 2026-08-24 17:20 UTC reports `DEGRADED`, with `can_claim_current=false`, because `source-20260819-growing-produce-berries` is explicitly `BLOCKED` after 26 retained failures and has no successful collection anchor. It is not overdue under cadence semantics. `current_through` and last successful collection operation are `2026-08-24T15:35:51+00:00`; last genuinely new intelligence is `2026-08-24T15:29:05+00:00`; last scheduler run is `2026-08-24T17:15:31+00:00`; last new rich draft is `2026-08-24T00:00:00+00:00`. No collection was forced to make the result green.

Runtime Source counts are 69 current of 70 discoverable: 34 `CURRENT_ACTIVE`, 35 `CURRENT_QUIET`, zero due, zero overdue, zero retrying, zero failing-primary, one blocked, zero never-run, and zero insufficient-history. TD-076 remains the reason production exposes 70 rather than the canonical 73 discoverable Sources. Berry current/scheduled counts are Blackberry 38/39, Blueberry 58/59, Raspberry 38/39, and Strawberry 40/41; the one shared blocked Source appears in each berry but no berry crosses the deterministic coverage-degradation threshold. Africa, Asia-Pacific, Europe, and South America have no unhealthy Source; Global and North America each include the same blocked Source. There are no explicit actor gaps and no feed-window risks. The corrected meaningful yield-drift conditions are Blue Book Services, HortiDaily, Mexico berry news search, Morocco berry news search, and UK berry growers news search. These are warnings only and do not change cadence.

Internal and public `/healthz` returned 200, `/login` returned 200, the container reports exact canonical `0b9de659`, and Docker is healthy. `bios-collection.timer` is enabled/active, its service is idle, and the collection lock is absent. The JSON CLI completed in 0.923 seconds; a measured same-process service call took 0.915 seconds cold and 0.0616 seconds warm with identical output; established `collection_status.py` completed in 4.17 seconds. Automatic throttling remains off. Today now consumes this one authoritative service; no Source, cadence, review/trust, extraction, model, or historical-reacquisition behavior changed.

Validation: 88 final focused/overlap tests passed locally; record validation, Python compilation, and `git diff --check` passed. The 1,598-page static build passed with the private-draft leakage check. The broad local Windows suite was interrupted by its 20-minute limit at 86% with two pre-existing one-second warm-route timing assertions; both passed isolated reruns. GitHub's complete Python, repository-integrity, static-public-safety, and change-scope checks passed on both PRs.
