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
| `ACTIVE` | 12 hours | Active short-window feeds whose measured safety ceiling is below one day |
| `NORMAL` | 24 hours | Active news/trade/alert feeds |
| `LOW_FREQUENCY` | 7 days | Quiet official newsrooms, registries, and spoken feeds |
| `QUIET` | 14 days | Available for sustained quiet evidence; not assigned from a short observation window |
| `HEALTH_DEGRADED` | bounded retry / operator | Existing Source Health `FAILING` retries at most daily; `BLOCKED` is not automatically polled |

The configuration maps the existing `realtime`, `daily`, `weekly`, `biweekly`, `monthly`, `quarterly`, `annual`, and discoverable `event_driven` values to real intervals. `daily` was already present on 29 Source records but was missing from Source Health's cadence-day map; that mismatch is corrected. Discoverable event-driven Sources receive a conservative weekly recurring check instead of being starved.

## High-confidence changes

Only four Source recommendations change; 69 remain unchanged.

| Source | Current | Recommended | Evidence |
|---|---:|---:|---|
| Global caneberry search | daily | 6 hours | 63 new items after the initial run across five repeat scans; 100-item visible window; dedicated Raspberry/Blackberry guardrail |
| HortiDaily | weekly | 12 hours | 84 new items after the initial run across 25 repeat scans; visible window 28; measured half-window ceiling 69,385 seconds |
| Blue Book Services | weekly | 12 hours | 26 new items after the initial run across 25 repeat scans; visible window 10; measured half-window ceiling 83,025 seconds despite weak body acquisition |
| Fruitnet Produce Plus | daily | 6 hours | Four new items after the initial run across five repeat scans; current visible window only two; measured half-window ceiling 31,510 seconds |

Driscoll's and berry trade-remedy searches remain `HIGH_FREQUENCY` because their existing `realtime` intent is appropriate for time-sensitive company/regulatory discovery. Global caneberry joins that class because both observed velocity and strategic Raspberry/Blackberry coverage justify it. Language never enters the cadence rule.

Quiet official newsrooms, registries, podcasts, and video feeds retain weekly cadence. The 20 new direct/sitemap Sources retain the daily/weekly settings established by their bounded onboarding proof; one initial capped scan is insufficient evidence to tune them further. The three sitemaps therefore remain weekly and are explicitly reported as having insufficient repeat velocity for a feed-window calculation rather than being treated like RSS.

## Feed-window and yield protection

The audit excludes each Source's initial run from velocity, then computes a maximum safe interval only when repeat-run elapsed time, genuinely new items, and a visible window all exist. The safety factor collects before half the expected visible window turns over. Feed capacity alone never becomes an activity estimate.

The four changed Sources remain inside their measured safe intervals. The dedicated caneberry search is tightened, not deprioritized. Canonical scheduled coverage remains Blueberry 62, Strawberry 44, Raspberry 42, and Blackberry 42 Sources; the scheduler never uses berry volume to reduce cadence.

Rich-body outcomes are reported per Source from stored private Publication Review drafts as `FULL_ARTICLE`, `THIN_DESCRIPTION`, or `UNKNOWN_NOT_RECORDED`. The unknown class is preserved for older drafts created before completeness instrumentation; it is not relabeled as success or failure. Relevant-draft counts describe drafts produced by deterministic relevance screening, not human review yield.

## Request economics

On the canonical 73-Source surface, the prior group schedule implied about 257 network requests/day (256 Source collection attempts plus the second Redagricola playlist request). The feed-window-safe schedule is about 52.86 requests/day, an estimated 79.4% reduction. This is a cadence-model estimate, not metered publisher traffic; retryable failures can add bounded retries and blocked Sources add none until operator resolution.

The reduction predominantly removes duplicate-only scans from weekly/daily Sources that were being polled every six hours. Daily active feeds, all three high-frequency searches, the 10-item Blue Book window, and the newly onboarded direct rich publishers remain protected. Therefore the prior 20-40 rich publication candidates per 30 days expectation should remain approximately intact. That is a preservation estimate grounded in retained cadence and feed-window coverage, not a prediction of analyst decisions.

## Operator contract

`scripts/run_collection.py --pipeline-scope ...` now persists the complete due/not-due decision set with exact next-due timestamps in each run summary. Explicit `--source` remains an operator override and does not consult cadence. If the additive policy file is unexpectedly absent, the runner fails safe to the legacy all-source group behavior rather than starving discovery.

`scripts/collection_status.py` reuses Source Health and shows due, not due, blocked, and next expected collection time. `scripts/collection_cadence_audit.py` is a read-only, offline every-Source report covering type, berries, geography, adapter, current and recommended cadence, run history, observed activity/week and /30 days, new/duplicate yield, duplicate-only rate, relevant drafts, rich-body class, failures, Source Health, due state, feed-window ceiling, and reason. It reads retained state only and performs no publisher fetch.

TD-076 remains the only relevant ownership limitation: three existing runtime Source records have no three-way baseline and are not overwritten. The cadence policy is explicitly authoritative operational scheduler configuration, alongside the pipeline registry, so startup safely applies later policy corrections without changing runtime-owned Source records or trusted data.

## Production proof

PR #149 merged the implementation as `7fe31dc`; PR #150 corrected the three feed-window ceilings found by the first live audit and merged as `c165f58`; PR #151 made the cadence policy authoritative operational configuration and merged as implementation canonical `0da18d3`. All four required GitHub checks passed on each final head. The production host and container both reported `0da18d3c90a2c26201f262b37163059fe3cc0036` after an app-only rebuild.

Before the final mutation, `berry-runtime-20260824T152247Z.tar.gz` was created and independently verified at `/var/backups/berry-intelligence-os/` with SHA-256 `f7b819d258036d590337ac4a8bb2d2472eb3b6521af79e82e0518c348512924b`. Startup synchronized the mounted cadence policy through the authoritative contract: repository seed and runtime both hashed to `bcf40476e42156a81fc6215a92b1c886324c95ef96bb4b08a3b5226d3c5675b8`.

The canonical-data audit against production history reported 73 discoverable Sources, 50 with repeat-run evidence, 20 one-run-only, three without retained history, four changed, and 69 unchanged. Estimated attempts fell from 257.0 to 52.86 per day (79.4%), with 82.18 duplicate-only Source scans/day estimated avoided. No recommended interval exceeded its measured feed-window ceiling. Coverage remained Blueberry 62, Strawberry 44, Raspberry 42, and Blackberry 42.

The no-write dispatcher proof evaluated 58 article/news candidates, selected exactly four due, skipped 54 not due, and paused the existing blocked Growing Produce Source through Source Health. It evaluated 12 spoken-media Sources and selected none because all were not due. Both runs reported extraction disabled, unconfigured, unqualified, and unrunnable. Restoring the existing timer triggered the same registry dispatcher rather than an all-Source sweep.

Mounted state survived the rebuild: data remained 2,657 files, inbox 10,020 files, and Evidence 1,660 files before the scheduler smoke. The Evidence tree hash remained `c1087486b2a9cfa4adcd5b1efb4ec64ad54bf18c53facfc0e28e9c9f0b9f918b`; the private review-event ledger retained 11 files, no qualification marker existed, and the public `/healthz` returned 200. The timer was restored enabled and active. TD-076 remains visible rather than bypassed: production runtime exercises 70 discoverable Sources until the three protected divergent Source records receive an explicit ownership resolution, while the deterministic policy and audit cover all 73 canonical Sources.
