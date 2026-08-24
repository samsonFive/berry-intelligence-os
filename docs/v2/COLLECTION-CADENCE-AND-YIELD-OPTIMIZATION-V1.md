# Collection Cadence + Yield Optimization V1

**Measured:** 2026-08-24

**Scope:** deterministic recurring Source selection, operational yield audit, and Source Health visibility

**Trust boundary:** unchanged. This work performs no publication, review decision, extraction, model call, qualification, Atomic proposal, or historical reacquisition.

## Result

The production dispatcher used to treat the pipeline cadence as the Source cadence: every article/news Source was polled every six hours and every spoken-media Source daily, even though all Source records already carried individual cadence intent. The timer and pipeline registry remain the one scheduler; a due pipeline now selects only Sources whose own deterministic cadence is due.

The canonical surface is 73 discoverable Sources. Retained production operations cover 70 because TD-076's additive-only Source ownership contract correctly preserves three older runtime records that lack their newer canonical discovery blocks (Produce Report, Fresh Plaza, Fresh Fruit Portal). Of the 70 production-observed Sources, 50 have at least two recorded runs and support evidence-based velocity/duplicate decisions; the 20 forward-expansion Sources have one initial run and are kept at their already-reviewed configured cadence. No one-run backlog is presented as publication frequency.

Across the 50 repeat-observed Sources, retained summaries contain 761 Source-run observations after grouping, with 581 repeat runs producing zero new items. That 76.3% is a discovery duplicate-only rate, not review yield and not an analyst keep/dismiss prediction.

## Cadence model

| Class | Interval | Use |
|---|---:|---|
| `HIGH_FREQUENCY` | 6 hours | High-velocity or time-sensitive bounded discovery |
| `NORMAL` | 24 hours | Active news/trade/alert feeds |
| `LOW_FREQUENCY` | 7 days | Quiet official newsrooms, registries, and spoken feeds |
| `QUIET` | 14 days | Available for sustained quiet evidence; not assigned from a short observation window |
| `HEALTH_DEGRADED` | bounded retry / operator | Existing Source Health `FAILING` retries at most daily; `BLOCKED` is not automatically polled |

The configuration maps the existing `realtime`, `daily`, `weekly`, `biweekly`, `monthly`, `quarterly`, `annual`, and discoverable `event_driven` values to real intervals. `daily` was already present on 29 Source records but was missing from Source Health's cadence-day map; that mismatch is corrected. Discoverable event-driven Sources receive a conservative weekly recurring check instead of being starved.

## High-confidence changes

Only three Source recommendations change; 70 remain unchanged.

| Source | Current | Recommended | Evidence |
|---|---:|---:|---|
| Global caneberry search | daily | 6 hours | 63 new items after the initial run across five repeat scans; 100-item visible window; dedicated Raspberry/Blackberry guardrail |
| HortiDaily | weekly | daily | 84 new items after the initial run across 25 repeat scans; latest visible window 28 |
| Blue Book Services | weekly | daily | 26 new items after the initial run across 25 repeat scans; visible window 10; discovery-window protection despite weak body acquisition |

Driscoll's and berry trade-remedy searches remain `HIGH_FREQUENCY` because their existing `realtime` intent is appropriate for time-sensitive company/regulatory discovery. Global caneberry joins that class because both observed velocity and strategic Raspberry/Blackberry coverage justify it. Language never enters the cadence rule.

Quiet official newsrooms, registries, podcasts, and video feeds retain weekly cadence. The 20 new direct/sitemap Sources retain the daily/weekly settings established by their bounded onboarding proof; one initial capped scan is insufficient evidence to tune them further. The three sitemaps therefore remain weekly and are explicitly reported as having insufficient repeat velocity for a feed-window calculation rather than being treated like RSS.

## Feed-window and yield protection

The audit excludes each Source's initial run from velocity, then computes a maximum safe interval only when repeat-run elapsed time, genuinely new items, and a visible window all exist. The safety factor collects before half the expected visible window turns over. Feed capacity alone never becomes an activity estimate.

The three changed Sources remain inside their measured safe intervals. The dedicated caneberry search is tightened, not deprioritized. Canonical scheduled coverage remains Blueberry 62, Strawberry 44, Raspberry 42, and Blackberry 42 Sources; the scheduler never uses berry volume to reduce cadence.

Rich-body outcomes are reported per Source from stored private Publication Review drafts as `FULL_ARTICLE`, `THIN_DESCRIPTION`, or `UNKNOWN_NOT_RECORDED`. The unknown class is preserved for older drafts created before completeness instrumentation; it is not relabeled as success or failure. Relevant-draft counts describe drafts produced by deterministic relevance screening, not human review yield.

## Request economics

On the canonical 73-Source surface, the prior group schedule implied about 257 network requests/day (256 Source collection attempts plus the second Redagricola playlist request). The recommended schedule is about 47.86 requests/day, an estimated 81.4% reduction. This is a cadence-model estimate, not metered publisher traffic; retryable failures can add bounded retries and blocked Sources add none until operator resolution.

The reduction predominantly removes duplicate-only scans from weekly/daily Sources that were being polled every six hours. Daily active feeds, all three high-frequency searches, the 10-item Blue Book window, and the newly onboarded direct rich publishers remain protected. Therefore the prior 20-40 rich publication candidates per 30 days expectation should remain approximately intact. That is a preservation estimate grounded in retained cadence and feed-window coverage, not a prediction of analyst decisions.

## Operator contract

`scripts/run_collection.py --pipeline-scope ...` now persists the complete due/not-due decision set with exact next-due timestamps in each run summary. Explicit `--source` remains an operator override and does not consult cadence. If the additive policy file is unexpectedly absent, the runner fails safe to the legacy all-source group behavior rather than starving discovery.

`scripts/collection_status.py` reuses Source Health and shows due, not due, blocked, and next expected collection time. `scripts/collection_cadence_audit.py` is a read-only, offline every-Source report covering type, berries, geography, adapter, current and recommended cadence, run history, observed activity/week and /30 days, new/duplicate yield, duplicate-only rate, relevant drafts, rich-body class, failures, Source Health, due state, feed-window ceiling, and reason. It reads retained state only and performs no publisher fetch.

TD-076 remains the only relevant ownership limitation: three existing runtime Source records have no three-way baseline and are not overwritten. The cadence policy itself is a new additive configuration file, so it deploys safely without changing those runtime-owned Source records.
