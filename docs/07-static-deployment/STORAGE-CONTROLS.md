# Host storage controls

These host services bound nested backup history and logs and publish storage
health without changing application data, analyst decisions or source settings.
Installation and activation require the coordinated server release window.
Public source contains generic code and synthetic tests; recovery manifests,
plans, receipts, actual server bindings and delivery credentials stay private.

## Recovery and retention

The existing production backup runner retains fourteen daily archives in the
backup root. It does not inspect the separate directory created for each
release/rehearsal. The host retention service manages that nested history;
direct-root archives remain exclusively under the existing daily rotation.

Before each run, the service collects the accepted current and previous release
identities from the release ledger and its retained before-ledger snapshot.
It verifies both recovery archives against release receipts, member checksums
and gzip integrity, checks immutable images and the running app/copilot pair,
and protects the full dependency sets: accepted stages, configuration and
environment files, referenced archives, image identities and actual mounted
data/subtrees. The generic backup-root mount is not blanket protection for all
old archives. Missing, ambiguous, stale or changed recovery evidence stops
deletion. Recovery pins must use release child directories so daily root
rotation cannot delete them.

The nested pool retains the latest verified archive in seven daily, four weekly
and three monthly buckets. Current and previous recovery sets are additional
pins. Files younger than 72 hours, invalid archives, unknown formats/names,
filesystem indirection and unreferenced objects without a verified plan are
preserved. Host verification streams member checksums and limits manifest
metadata to 16 MiB and the TAR inventory to 100,001 members. Inventories beyond
those limits are held for review. Each invocation retires at most ten archives
and 5 GiB. It never
removes directories, Docker images, volumes or live runtime data. Small
configuration and audit receipts remain in their original locations.

All state-changing runs acquire the same three exclusive release locks used by
the deployment operators. A busy window is skipped without writing status into
the protected runtime. The dry-run plan pins the ledger, protection manifest,
policy, archive paths, identities and hashes. Explicit application of an
existing plan requires its SHA256. The timer instead generates and applies a
fresh plan under one lock context. Retirement intents and results are persisted;
an unmatched retirement intent is held for review before any later plan or
protection metadata can replace it, including after an error following unlink.

```sh
python3 -I -B /opt/berry-storage-controls/current/scripts/storage_retention.py \
  --policy /etc/berry-storage-controls/policy.json \
  --protection /var/lib/berry-storage-controls/recovery.json --refresh-protection
```

Review `retention-plan.json`, its SHA256, protected sets and proposed removals
before the first `--apply`. The service timer runs every six hours, with jitter,
to clear a bounded backlog while avoiding an unbounded cleanup sweep.

Off-host replication is separate. This implementation does not create an
external backup account or claim that local tiers provide disaster recovery.
Keep any already verified off-host recovery copies and their manifests.

## Disk and inode alerts

The host monitor samples every five minutes using available blocks rather than
reserved filesystem space. The combined example uses 20 GB warning, 12 GB
critical, a 10 GiB deployment reserve, and 5%/2% free inode thresholds. The
collector/monitor enforce an 8 GiB minimum; installation must preserve any
stricter reserve accepted by the current release owner and must account for
that owner's complete backup/startup budget. Monitoring thresholds do not
lower a release gate. The monitor emits new conditions,
escalation, recovery and six-hour reminders. Failed delivery remains pending and
retries with the same event identity. State-change history is bounded.

The policy is root-owned mode 0600. Private state is root-owned mode 0700/0600;
the safe status file is service-readable at
`inbox/operations/storage/status.json`, owner/group 1000, mode 0640, with a 2750
parent. It contains operational measurements only. It never contains endpoint
credentials, environment values, article bodies or report contents.

Journal alerts are enabled with external delivery disabled by default. An
operator can separately configure a private HTTPS webhook or verified-TLS SMTP
destination. Scheduled Codex follow-ups can also read the safe status and return
to an existing chat; such local checks depend on the computer and app remaining
online. They do not replace the independent host monitor.

## Log rotation

`deploy/logging/journald-berry-storage.conf` limits persistent journal storage to
512 MiB, retains at most fourteen days and reserves space for other services.
Validate the effective configuration before restarting journald and rotating
and vacuuming archived journals. Preserve release/incident receipts separately.

`deploy/logging/docker-compose.rotation.yml` sets `json-file` logs to 10 MB times
three files for app, copilot and Caddy. Existing containers adopt these settings
only when recreated. Review the exact logging-only configuration delta alongside
the complete live Compose chain, environment, resources and mounts; retain the
previous recovery configuration. Recreate app and copilot together because the
sidecar uses the app's network namespace. Coordinate Caddy's recreation as well.
Do not truncate Docker-owned files or restart the Docker daemon as a shortcut.

## Installation and verification

1. Reserve the server slot and capture the current accepted release/configuration
   and both recovery sets. Never install from stale release bindings.
2. Deploy an immutable, hash-verified host package at
   `/opt/berry-storage-controls/releases/<source-sha>` and switch the root-owned
   `current` link only while its timers/services are inactive. Include the three
   host modules, their CLI scripts and `runtime_backup.py` from the same tested
   source; no production records belong in the package.
3. Preserve prior host policy, units, journal configuration and timer states in
   a new private installation receipt. Create required directories before
   loading hardened units. Install the reviewed policy as mode 0600 and unit
   files as root-owned mode 0644. Precreate the private `docker-client`
   directory under the state directory with an empty mode-0600 `config.json`;
   the retention unit uses the local Unix socket and that isolated client
   configuration while access to home directories is disabled.
4. Verify the units and effective journal configuration. Run the actual recovery
   collector and retention dry run. Review the exact plan before retiring a
   bounded first batch. Check that both pinned archives and every referenced
   recovery dependency remain intact.
5. Enable the monitor and retention timers. Exercise alert escalation, duplicate
   suppression, recovery, failed delivery and busy-lock behavior using isolated
   synthetic state; never fill the production filesystem to test a threshold.
6. Activate Docker rotation through the separately reviewed paired cutover.
   Inspect each running container's logging driver/options afterward, verify
   app/copilot health, normal login, retained private reports and the scheduler,
   then record the final source/configuration and available disk space.

If a control fails, disable only the newly owned timers/units or restore their
recorded previous configuration. Never restore analyst databases or replace the
runtime as a response to a host-monitor problem. Preserve receipts and failed
retirement evidence for review.
