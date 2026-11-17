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
The accepted ledger must pin an immutable `berry.recovery-proof.v1` document by
its absolute private path and SHA256. That proof authenticates genuine PRE/POST
captures, the exact release plan and previous ledger, and the final completed
producer verification. Full private app/copilot inspection snapshots bind
Config, HostConfig (including logging), mounts and the paired namespace.
Ordered Compose files, environment files and transitive recovery dependencies
must match their accepted content hashes and modes. A stage pathname or a hash
computed only when consuming an old baseline does not establish acceptance.

The proof also retains the physical store/migration markers, exact raw migration
backup subtree and the guarded rollback recipe/modules. Seal it before writing
the new accepted ledger; write the old/new-ledger promotion receipt afterward.
Use the completed producer's final verification rather than an earlier progress
event. Unknown or incomplete producer/schema/state evidence holds deletion.

The proof declares `operation_kind` as `unified-migration`,
`recovery-adoption` or `configuration-only`. Archive pins state their capture phase, physical store
schema and recovery role. A legacy archive captured before migration requires
an authenticated observed transformation and a supported, image-bound replay
protocol. It is not a snapshot of the activated unified store. Replay must
verify restored source bytes before restoring their original nanosecond file
times, generate a fresh migration plan at the restored paths, and use a new
empty backup base without reusing a saved resume identity. Preserve reading and
review decisions and verify the resulting store. Missing protocol or execution
evidence holds automatic retirement; this service never performs a restore.

Replay v1 keeps its original default-plan contract. The separate v2 contract
supports a fresh streamed ASCII plan prepared by the authenticated native
helper. It restores metadata from the source inventory and timestamp sidecar,
verifies every source before changing file times, releases inventory buffers,
then prepares one plan exclusively in a new empty backup directory. Apply uses
only that returned plan identity; it never replans or rewrites the aggregate
plan. Raw-file and canonical JSON hashes remain separate. A deterministic
migration identity may repeat when the restored sources and visible paths match;
the new directory and preparation evidence establish freshness.

V2 requires both a functional image-bound fixture and representative resource
evidence for metadata allocation and native prepare/apply. Source/API fixtures
alone leave adoption on hold. The functional execution retains its actual
container inspection and raw result, bound to the image, executable and read-only
inputs; changing a receipt's execution label is insufficient. Observed kernel
limits, swap, peak usage, OOM
counters and initial/terminal container identity must be retained; declared
limits or guessed missing counters are insufficient. A separately owned
qualification can supply missing observations without rewriting old producer
proofs or claiming another rollback exercise. Keep its small receipts outside
the temporary workspace. Qualification requires actual capacity admission and
preserves the native helper's reserve; it does not authorize another full
runtime copy or automatic cleanup.

The explicit recovery-adoption profile admits a supported native migration
history through a metadata-only acceptance. It preserves the original accepted
ledger, HOLD wrapper, receipts and native artifacts, including genuinely absent
native kind fields. A versioned descriptor authenticates that original history
and maps the exact final off-host archive hash/size to its verified nested local
copy. It never substitutes a rehearsal archive or labels the historical HOLD
ready. The new ledger changes only the backup locator, recovery pointer and
metadata receipt; runtime stage, images, source, configuration, current container
identities and logical previous release remain unchanged. Unknown producer
profiles and unsupported extensions remain held for review.

Both distinct recovery archives, full native content/store/rollback provenance
and the supported image-bound replay evidence are still required. Reuse an
already verified compatible previous archive in place. A local copy or a source
fixture alone does not establish adoption. Small private operator files can
bootstrap metadata verification without installing active services or creating
another full runtime copy.

The extended snapshot and the timestamp/logo supplement have separate explicit
native profiles. Supplement evidence is joined to the accepted source, native
completion, audit and copy-preservation receipts. Helper constants are read as
bounded literal data; the collector never executes producer files. Known file
entries in the producer's path list are classified explicitly. Historical
archive pairs do not become permanent inherited body-verification requirements.
An optional native candidate image-manifest reference is retained and checked
against its image admission and source, including safe exact inventory paths.

A configuration-only logging cutover authenticates its own fresh app/copilot
and Caddy snapshots and current state. It preserves images, environment,
resources, mounts and store markers while changing the declared log settings
and required container identities/namespace metadata. Its failure recovery
restores configuration against current data. Required inherited migration
material is a flat, explicit pin set; older full-archive generations are not
recursively inherited. Caddy identity/configuration participates in subsequent
live checks when the operation changed Caddy.

Logging-only comparison preserves the complete configuration and effective mount
rows. Bind ordering is compared using full strings, including duplicate entries
and options. A sidecar hostname derived from the app is accepted only when both
old and new network namespaces prove the corresponding app identity. Custom
hostnames, environment provenance labels and all other configuration remain
checked. Compose render, recreation and rollback must explicitly retain the
original ordered, protected environment-file inputs.

The service verifies both recovery archives against release receipts, member checksums
and gzip integrity, checks immutable images and the running app/copilot pair,
and protects the full dependency sets: accepted stages, configuration and
environment files, referenced archives, image identities and actual mounted
data/subtrees. The generic backup-root mount is not blanket protection for all
old archives. Missing, ambiguous, stale or changed recovery evidence stops
deletion. Recovery pins must use release child directories so daily root
rotation cannot delete them. Both pinned archives must be present locally for
this policy. Retain verified off-host copies as well; an off-host transfer
receipt alone cannot satisfy the host's recurring archive verification.

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
monitor policy enforces an 8 GiB minimum; installation must preserve any
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

The scheduled chat check runs once daily at 09:00 America/Los_Angeles. The
release owner also runs the reviewed read-only check after each production
deployment or terminal failed cutover/recovery, records its sanitized result
with the private closeout and delivers actionable changes to the existing
authorized alerts chat. An access or integrity failure is monitoring unavailable.
The private handoff supplies the exact pinned command and destination. No
deployment polling watcher is needed.

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
   If a supported native history needs recovery adoption, complete that explicit
   metadata acceptance first. Retire only proved unused owned rehearsal copies
   while retaining their evidence before staging a missing local archive.
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

Reserve each phase against freshly measured available blocks on every relevant
filesystem. Existing local recovery archives are already included in that free
space and need not be duplicated. Keep the actual raw rollback and new-store
working sets; rehearsal surplus does not fund a second simultaneous archive.
After genuine adoption, an inactive installation and reviewed archive-only
first apply may reclaim verified eligible history before the logging snapshot.
Credit only measured reclamation. Logging admission uses its actual post-migration
full-source/header/metadata bound plus startup reserve, not an earlier compressed
backup estimate. Missing capacity keeps the next phase on HOLD.

If a control fails, disable only the newly owned timers/units or restore their
recorded previous configuration. Never restore analyst databases or replace the
runtime as a response to a host-monitor problem. Preserve receipts and failed
retirement evidence for review.
