# Production Collection Operations V1

Implementation basis: `v2/intelligence-os` at
`e1ae5d06dc87cfe9322604b342c8adb30c95536f` (2026-08-22). Implementation PR
#76 merged and was deployed as canonical
`9b57f10cf03861a5cb5f2525d196cc2fda351488`.

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

The pre-deploy publication-review backlog was 1,020. It had been 901 before the
latest two observed article cycles, and the latest article run created 119
drafts, matching that observed increase. The proof cycle's CPVO run then added
28 review drafts, bringing the backlog to 1,048. Collection is therefore
creating work faster than the observed review throughput. The six-hour article
cadence reduces pressure but does not auto-review or weaken the human trust
gate. Status reports current backlog, last-run created count, backlog-to-created
ratio (8.81 after deployment), and growth pressure.

## Production proof

Root SSH inspection and deployment on the IONOS VPS were completed on
2026-08-22. Before mutation, production was on `e1ae5d0`, the old timer was
enabled/active, the app was healthy, and `/dev/vda1` had 111 GiB free of 116
GiB. A fresh pre-deploy backup was created and independently verified:

- archive: `/var/backups/berry-intelligence-os/berry-runtime-20260822T111551Z.tar.gz`
- SHA-256: `0638e6033d032954fb9bba7be4990b18aeb00a2a9e11372ce7b4bcba56087abf`
- pre-deploy state: 6,885 inbox files, 2,624 data files, 1,020 review drafts

Canonical `9b57f10` was fast-forwarded, the existing Docker Compose application
was rebuilt, and the updated service/timer units were installed. The app is
healthy and remains bound to `127.0.0.1:8000` behind Caddy. Every one of the
6,885 pre-deploy inbox files passed a manifest-driven SHA-256 comparison
against the mounted post-rebuild runtime. All 2,623 unchanged trusted files
also passed; the one deliberately changed trusted file was
`configuration/collection_pipelines.json`, and its live hash exactly matched
canonical (`364d7807ab8aa665e6514261a4d555c58a88683000196e5d6b3d15e441d2653e`).

The timer is enabled and active. Its first persistent trigger ran at 11:18:05
UTC and completed exit 0 at 11:19:12 UTC; the next dispatcher edge was
11:30:07 UTC. That real scheduled cycle selected only due work:

- CPVO: `SUCCESS`, 136 queries, 28 relevant/review-ready drafts, 0 failures,
  55.337 seconds; next due 2026-08-29 11:19:01 UTC.
- Runtime backup: `SUCCESS`, 4 valid/retained archives, 0 removed, 10.6
  seconds; next due 2026-08-23 11:19:12 UTC. The new archive SHA-256 and
  sidecar both equal
  `ffc2bd55b5408e37f809fdd17e45e310813332a2fd478b58f83e7814c3e1dd7a`,
  and an independent verify passed.
- Article/news next due: 2026-08-22 14:29:45 UTC. Spoken next due:
  2026-08-23 08:29:45 UTC. Plant patent next due: 2026-08-26 14:36:01 UTC.

The default production `collection_status.py --json` completed in **2.99
seconds**, versus the former attached run exceeding 35 minutes. It reported
persisted detail mode, 1,048 publication-review drafts, one legacy article
Source failure, 103 retryable item failures, 102 operator interventions, a
healthy verified 69-second-old backup, 95.9% disk free, and no lock.

Lock contention was proven with a normal verified backup rotation holding the
shared lease. A concurrent mutable manual Source run exited 2 before discovery
with the holder run ID; an otherwise identical dry run exited 0; the holder
exited 0; no lock remained. HTTPS smoke passed: `/healthz` 200, `/login` 200,
unauthenticated `/work-queue` 302, login POST 303, and authenticated
`/work-queue` 200. The app remained healthy throughout.

Production collection is unattended and observable within its current
on-host recovery boundary. The active operational constraint is analyst review
capacity (TD-056); off-host backup replication remains resilience debt
(TD-051). Trade/weather need rolling-window configuration before they should
be made unattended (TD-055), not a blind timer.

Review Capacity + Collection Backpressure V1 subsequently added read-only
backlog economics, age/pressure warnings, and a deterministic critical-policy
simulation (`scripts/review_capacity.py`). Automatic throttling remains off:
production does not yet have enough recorded review events to calculate honest
analyst throughput or Source yield. See
`docs/v2/REVIEW-CAPACITY-COLLECTION-BACKPRESSURE-V1.md` and TD-064.

Review Outcome Instrumentation V1 adds the prospective evidence TD-064 was
missing. Real human transitions are appended under private
`inbox/review_events/`, which is already inside this runbook's complete-runtime
backup and persistent bind-mount scope. `collection_status.py` cheaply reports
the total, latest time, and action counts; it does not expose actor identity.
No current-state record was converted into a historical event, rates remain
insufficient until the documented sample threshold is met, and automatic
throttling remains off. See
`docs/v2/REVIEW-OUTCOME-INSTRUMENTATION-V1.md`.
