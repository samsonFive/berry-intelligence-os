# Collection Runtime + Data Integrity V1

Canonical audit basis: `v2/intelligence-os` at `c83b3ff` (2026-08-21).
This document describes paths the code actually reads and writes.

## Runtime state map

| State | Real path | Classification | Recovery / retention |
|---|---|---|---|
| Trusted records and acquisition config | repo `data/`; deployed `${BIOS_RUNTIME_DIR}/data` | GIT-TRACKED seed; VPS-PERSISTENT bind mount; SEEDED then additively SYNCED; mutable after publish | BACKED UP; published records are IRREPLACEABLE |
| Publication and Atomic Evidence drafts | `inbox/evidence/*.json` | GITIGNORED; WORKTREE-LOCAL without runtime env; VPS-PERSISTENT in Docker | BACKED UP; IRREPLACEABLE review/provenance |
| Discovered items and source health | `inbox/discovered_media/*.json`, `_state/*.json` | GITIGNORED; VPS-PERSISTENT when mounted | BACKED UP; items mostly RECREATABLE, first-seen/health history is not |
| Raw media and transcripts | `inbox/discovered_media/_media`, `_transcripts`, `_normalized_transcripts` | GITIGNORED; VPS-PERSISTENT | BACKED UP; raw media often RECREATABLE, transcript provenance retained |
| Collection attempts/retries/runs/lock | `inbox/operations/items`, `runs`, `collection.lock` | GITIGNORED; VPS-PERSISTENT except live lock | BACKED UP; run history retained, lock RECREATABLE |
| Patent/CPVO/trade/weather state | `inbox/operations/{patent_monitor,cpvo_registry,trade_intelligence,weather_intelligence}/state.json` | GITIGNORED; VPS-PERSISTENT | BACKED UP; seen indexes RECREATABLE, history retained |
| Cron logs | deployed `inbox/operations/cron-logs` | GITIGNORED; VPS-PERSISTENT | BACKED UP; old worktree-local default retired |
| Signal candidates and audit | `inbox/signal_candidates`, `inbox/signal_candidate_audit` | GITIGNORED; VPS-PERSISTENT | BACKED UP; decisions IRREPLACEABLE |
| Analyst queue | `inbox/analyst_queue_state.json` | GITIGNORED; VPS-PERSISTENT | BACKED UP; IRREPLACEABLE |
| Static site | `generated/` | GITIGNORED build artifact | RECREATABLE from trusted `data`; never contains inbox |
| Test runtime | `tests/fixtures/runtime` | GIT-TRACKED, explicitly fictional | SEEDED test-only; never production content |

`data/` and `inbox/` are the complete mutable backup scope. Secrets live in
`deploy/.env` or process environment and are deliberately outside it.

## Inbox durability and isolation

`inbox/` remains gitignored. Separate worktrees and cloud agents therefore
have separate local inboxes by design. Cursor saw zero of Claude's 18 UK
drafts because it read a different filesystem runtime; Git had no objects to
transfer. Production uses one operator-selected persistent runtime
(`BIOS_RUNTIME_DIR`, or explicit paths) shared only by authorized processes.
Developers retain isolated inboxes. Production counts are inspected with the
read-only status command against that runtime, not by copying drafts into Git.

## Docker persistence boundary

Compose bind-mounts host `demo-runtime/data` to `/app/runtime/data` and host
`demo-runtime/inbox` to `/app/runtime/inbox`. Every important mutable path is
below one of those mounts. Rebuild replaces `/app`, not `/app/runtime`. The
entrypoint seeds an empty data volume and additively syncs trusted data; it
never seeds or overwrites inbox. Container-local state outside `/app/runtime`
is ephemeral and collectors must not use it.

## Production VPS proof (2026-08-22)

The IONOS VPS was inspected and deployed, not inferred from Compose files.
Canonical `704c18e` was fast-forwarded and the existing Docker/Caddy stack was
rebuilt. The app remained loopback-only on host port 8000; public HTTPS stayed
behind Caddy. Docker still bind-mounted the same host paths:

- `/opt/berry-intelligence-os/demo-runtime/data` -> `/app/runtime/data`
- `/opt/berry-intelligence-os/demo-runtime/inbox` -> `/app/runtime/inbox`

The complete verified deployment backup is
`/var/backups/berry-intelligence-os/berry-runtime-20260822T051144Z.tar.gz`
(SHA-256 `669612e2387cecd55ac5784d0f7aab63cc1c859aeb41a5a2aa6437b143ee2793`,
8,804 archive entries: 2,624 `data/`, 6,179 `inbox/`, plus the manifest).
An isolated restore passed. The first archive attempt exposed and did not hide
a real defect: substring-based secret-name filtering omitted a legitimate
trusted Evidence filename containing the word `secret`. That archive is not
the accepted deployment backup. TD-047 and its regression test record the
fix; the accepted archive includes that Evidence, `collection_pipelines.json`,
and the analyst queue while still excluding `.env`/credential/token paths.

Persistence was measured before and after rebuild. The full 6,179-file inbox
was byte-for-byte identical (SHA-256 inventory
`2a0848e9b7885750e350418d703aef90848c192d303f1970d2d3c484e6ddb2a9`).
That includes 901 publication/Atomic Evidence drafts, 46 live Signal
candidates, collection/discovery state, 2,606 operations files, and the one
normalized transcript. The analyst queue file is present and backed up
(SHA-256 `119af74fcdf74580fd0bb1134c392882cfcfde01255ee08c5fc2d86e97d8ffda`).
Trusted runtime data gained only the additively synced canonical pipeline
registry; no existing trusted file was lost.

Disk pressure was a development-host-only finding. Production `/dev/vda1` was
116 GiB total, 4.6 GiB used, 111 GiB available (4% used); the runtime was 60
MiB. Docker held 1.735 GiB of reclaimable build cache, journals 98.8 MiB, and
logs 125 MiB. Nothing was deleted.

The original production proof found a four-hour article/spoken timer whose
useful partial runs appeared wholly failed. Production Collection Operations
V1 replaces that arrangement with one 15-minute registry dispatcher. The
registry separately schedules article/news every six hours, spoken discovery
daily, plant patent and CPVO weekly, and runtime backup daily. Trade and
weather remain manual because their current configurations are fixed
historical pilots. See `PRODUCTION-COLLECTION-OPERATIONS-V1.md` for measured
post-deploy scheduler proof and the cadence rationale.

The deployed UID/GID 1000 app user created and removed a probe in the
persistent lock directory; the effective lock path is
`/app/runtime/inbox/operations/collection.lock`. Docker health was `healthy`.
HTTPS smoke results: `/healthz` 200, `/login` 200, unauthenticated
`/work-queue` 302 to login, login POST 303, authenticated `/work-queue` 200.

Production-scale `collection_status.py --json` originally exceeded an attached
35-minute ceiling. The cause was item-by-item orchestration and repeated broad
Evidence/draft scans inside a status request, not output size. The default now
reads persisted run/pipeline state, current draft counts, backup health, disk,
and lock state; `--audit-items` explicitly requests the former deep audit. See
TD-054 and `PRODUCTION-COLLECTION-OPERATIONS-V1.md` for before/after proof.

## Backup and restore

```bash
python scripts/runtime_backup.py create --runtime-dir demo-runtime --output-dir /var/backups/berry-intelligence-os
python scripts/runtime_backup.py rotate --runtime-dir demo-runtime --output-dir /var/backups/berry-intelligence-os --keep 14
python scripts/runtime_backup.py verify /var/backups/berry-intelligence-os/berry-runtime-YYYYMMDDTHHMMSSZ.tar.gz
python scripts/runtime_backup.py restore BACKUP.tar.gz --target-runtime-dir /tmp/berry-runtime-restore-proof
python scripts/collection_status.py --data-dir /tmp/berry-runtime-restore-proof/data --inbox-dir /tmp/berry-runtime-restore-proof/inbox --json
```

Restore requires an empty target, validates paths/checksums, and reapplies
file modes. Archives contain only `data/` and `inbox/`, exclude `.env` and
credential names and symlinks, and are never copied to static output.

## Recurring collection audit

| Pipeline | Actual runner | Scheduling now | Timeout / retry / isolation |
|---|---|---|---|
| Article/news | `run_collection.py --pipeline-scope article-news` | every 6 hours through registry dispatcher | adapter timeouts; item backoff; per-source/item isolation; shared lock |
| Spoken media | `run_collection.py --pipeline-scope spoken-media` | daily through registry dispatcher; no implicit Whisper | adapter timeouts; per-feed/item isolation; shared lock |
| Plant patent | `monitor_plant_patents.py` | weekly through registry dispatcher | 30s provider timeout; per-query isolation; shared lock |
| CPVO | `monitor_cpvo_registry.py` | weekly through registry dispatcher | 15s timeout; per-query isolation; shared lock |
| Trade | `monitor_trade_intelligence.py` | manual pilot | 20s timeout and request delay; per-period/lane isolation; shared lock |
| Weather | `monitor_weather_intelligence.py` | manual pilot | 30s timeout; per-region isolation; shared lock |
| Runtime backup | `runtime_backup.py rotate` | daily through registry dispatcher; retain 14 verified archives | new archive verified before bounded pruning; shared lock |

The machine-readable contract is `data/configuration/collection_pipelines.json`.
`collection_status.py` adds last attempt/useful success/full success, outcome,
next due, failures, items/drafts, review backlog, backup health, runtime
persistence, disk free space, and lock state. A scheduler script is not proof
a production timer is installed.

All writers use `inbox/operations/collection.lock`. A second systemd/manual/
smoke/worker invocation fails before mutation. Dry runs remain lock-free and
write-free. Source, feed, item, query, lane, and region failures are isolated.

## Idempotency and deterministic dedup

Patent, CPVO, trade, and weather state carries an acquisition signature from
pipeline version and meaningful configuration. A change invalidates only the
derived seen index; run history and review drafts remain. Draft paths remain a
final exact-id duplicate guard.

Article dedup uses normalized canonical URL; exact title + source + date; or
exact title + date + explicit origin publisher name/host (Google News versus
publisher RSS). Legacy trusted source documents without `evidence_role` are
included. Similar titles alone never merge.

## Retention

- **ACTIVE:** open drafts/candidates, live retry state, review transcripts,
  current analyst queue state.
- **ARCHIVED:** rejected/dismissed drafts, retired candidates and audit,
  completed runs, superseded acquisition signatures. Archive means hidden
  from active queues, not deleted.
- **REGENERABLE:** static output, downloadable media, seen indexes and locks.
  Regeneration never erases provenance or decisions.

Verified on-host backups use bounded retain-14 rotation. No draft, provenance,
or trusted-data age deletion is implemented. Storage growth and off-host
backup replication remain operator policy.
