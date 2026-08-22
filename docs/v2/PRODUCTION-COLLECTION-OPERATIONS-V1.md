# Production Collection Operations V1

Implementation basis: `v2/intelligence-os` at
`e1ae5d06dc87cfe9322604b342c8adb30c95536f` (2026-08-22). Production proof is
recorded after deployment rather than inferred from repository configuration.

## Operator contract

`python scripts/collection_status.py` is the single fast operator view. By
default it reads the latest persisted collection and pipeline run records,
current review-draft counts, backup metadata, filesystem capacity, and the
shared lock. It does not replay item orchestration. `--audit-items` retains the
old deep, per-item diagnostic when an operator explicitly needs it.

The status command answers whether collection is running, what ran recently,
individual failures, next due times, review backlog, backup health, disk
health, and whether a lock is present or stale. JSON is available with
`--json`.

## TD-054 root cause and correction

The old status path called `MediaOrchestrationService.process(dry_run=True)`
for every discovered item. Each call repeatedly loaded/scanned trusted
Evidence and publication drafts, ran duplicate resolution, and for
unrepresented items built and validated a prospective draft. At production
scale (2,874 discovered items, 2,624 trusted files, and 1,020 drafts) that was
broad, effectively quadratic recomputation. It also read every historical run
JSON merely to select the latest. Output size was not the cause.

The default now reads persisted summaries and only the lexicographically
latest broad-run file. The expensive audit remains explicit. Correctness is
not weakened: operational status reports persisted operational facts, while
item-level recomputation is named and separately invoked.

## Cadences and scheduler

One registry-driven dispatcher, `scripts/run_due_pipelines.py`, evaluates all
pipelines. One systemd timer wakes it every 15 minutes; the registry, not a
collection of timers, owns cadence. Child collectors run sequentially and
continue to acquire the existing shared mutation lock.

| Pipeline | Cadence | Automated | Evidence |
|---|---:|---|---|
| Article/news | 6 hours | yes | News changes within hours, but the live backlog grew materially under the former four-hour cadence. |
| Spoken media discovery | daily | yes | Feeds change more slowly; the run never enables Whisper implicitly. |
| Plant patent | weekly | yes | Bounded public registry queries; daily polling is not justified by publication frequency. |
| CPVO | weekly | yes | Bounded public denomination/alias queries; daily polling adds cost without useful freshness. |
| Trade | manual | no | Current pilot is a fixed 2025-01 through 2026-06 window with 72 static Comtrade requests; scheduling would repeat history and amplify undocumented 429s. |
| Weather | manual | no | Current pilot is a fixed historical comparison through 2026-06, not a rolling current window. |
| Runtime backup | daily | yes | A verified recovery point is created before bounded rotation; 14 valid archives are retained. |

Every dispatcher run persists start/completion time, duration, outcome, exit
code, failure count/sample, counts, and drafts created beneath
`inbox/operations/pipelines/<pipeline>/runs/`. Pipeline status reports last
attempt, last useful success, last full success, next due, outcome, failures,
and drafts.

## Failure and locking semantics

Outcomes are `SUCCESS`, `PARTIAL`, and `FAILED`. For the source-isolated
article/news and spoken runners, some successful Sources plus some failed
Sources is `PARTIAL`: individual failures remain visible and the cycle counts
as useful work, but not as a full success. Zero successful Sources, a malformed
summary, or a failed non-source pipeline is `FAILED`. The dispatcher exits
nonzero only for `FAILED`, so systemd reflects operational utility without
hiding degraded Sources.

All mutable collectors use `inbox/operations/collection.lock`. A concurrent
manual or timer-launched writer fails before mutation. Dry-run/read-only work
does not acquire the mutation lock and remains nonblocking.

## Backups, retention, and storage

Daily rotation writes outside the app runtime, verifies the new archive and
its manifest before pruning, emits a SHA-256 sidecar, verifies existing
archives, preserves invalid archives for investigation, and removes only old
valid archives beyond the retain-14 policy. Retention cannot be configured
below two. Trusted `data/` and gitignored `inbox/` remain the complete backup
scope. Off-host replication remains debt; no cloud backup system was added.

Disk status retains the existing conservative warning below 10% free or 5 GiB
available. Production had 111 GiB available of 116 GiB (4% used), so no
cleanup or premature compaction was justified.

## Failure and backlog review

The 2026-08-22 08:02 UTC production run checked 44 Sources: 43 succeeded and
one publisher returned HTTP 403 (`source-20260819-growing-produce-berries`),
classified as expected publisher-blocked access rather than an adapter defect.
Persisted item failure state contained 205 entries. Current-run operator work
was dominated by 64 ambiguous multiple-publication representations; the rest
was predominantly expected bot/paywall access, plus isolated 403/404 access.
The 103 retryable failures were dominated by UK FSA 403/410 stale-or-blocked
alert URLs, with three openFDA response-body extraction failures. These remain
visible operational issues; this mission does not add or content-patch Sources.

The current publication-review backlog was 1,020. It had been 901 before the
latest two observed cycles, and the latest run created 119 drafts, matching the
observed increase. Collection is therefore creating work faster than the
observed review throughput. The six-hour article cadence reduces pressure but
does not auto-review or weaken the human trust gate. Status reports current
backlog, last-run created count, backlog-to-created ratio, and growth pressure.

## Production proof

Live measurements, scheduler installation, lock contention, backup rotation,
mounted-state hashes, application smoke, and deployed Git identity are added
here in the deployment commit/follow-up once measured. Repository readiness is
not represented as VPS proof.
