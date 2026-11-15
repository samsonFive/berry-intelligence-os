# Unified information storage maintenance runbook

This procedure consolidates source/evidence records into one physical runtime
store. It does not publish private information, change confidence scores or
convert source claims into Facts. The feature includes the tooling below; no
production migration or deployment is recorded by this runbook.

## Storage and privacy

The active layout is:

```text
/app/runtime/data/information/
  store.json                  # active marker with exact runtime bindings
  records/<id>.json           # one authoritative source record per ID
  assets/<id>/<filename>      # migrated attachments
  history/<id>/<hash>.json    # original variants and subsequent versions
/app/runtime/inbox/.information-store.json
```

The inbox still contains discovery receipts, normalized media, review events,
reading state and cache envelopes. Those operational files are not alternate
source stores. Daily and packet cache envelopes retain `records_ids` and, when
present, `rotating_records_ids`; readers hydrate current source metadata from the
shared store. Existing source-artifact and discovered-media paths remain intact.
Typed Facts, Entities, Relationships and other knowledge repositories are not
moved into the source store.

Each source has independent review/confidence metadata and `publication_scope`.
Previously published canonical sources remain public unless already explicitly
private. Internal canonical records, intake and retained cache records remain
private. A cache's published/reviewed labels cannot qualify it as reviewed.
Optional review preserves a private source's scope. Static/public projections
exclude private sources and private-dependent knowledge; review is not permission
to export.

## Prepare the release and a rehearsal

1. Require successful current-head repository CI, record validation and static
   public-safety checks. Record the exact candidate image ID and existing release
   image ID. Keep the original image and runtime backup for rollback.
2. Inventory every web process, acquisition CLI, scheduled collector and other
   writer sharing the runtime. Stop them for the final snapshot and cutover.
   `--quiesced` is an operator assertion, not a command that stops these writers.
3. Take a verified full snapshot of both runtime roots and the independent
   backup mount using the existing runtime backup procedure. Migration's own raw
   backup supplements this full snapshot; it is not a replacement.
4. Rehearse the exact candidate image against a copied runtime. Follow the
   [bounded VPS rehearsal rules](BOUNDED-VPS-REHEARSALS.md) when using that host.
   Mount the copy at the same **container** paths used by production, not at a
   different path inside the container. Activation markers intentionally bind
   absolute paths, so copying an active store to another runtime path does not
   automatically rebind it. Never use symlinks to alias legacy folders.

Use a private backup directory outside both runtime roots, for example
`/app/backups/information-migration-backups`. It contains full private source
bodies and original review metadata. Keep it out of Git, Docker build context,
static output and public release artifacts. Do not print the private plan or
copy it into a PR. The safe plan summary contains counts, hashes and conflicts.

## Plan and apply

The commands below are schematic. An existing deployment can have multiple
compose overrides, environment files and additional mounts, including a paired
copilot. Use the **complete effective compose argument list and environment from
the release handoff**, preserving every runtime/backup/auxiliary mount and the
copilot baseline. Never operate on an existing runtime using only the repository
base compose file: that can select a different image, runtime or service setup.
Do not print rendered compose configuration containing credentials.

Construct one Bash array from that reviewed handoff, replacing these placeholder
paths with the complete ordered argument list. Include every `--env-file` and
`-f` override used by the actual release; the placeholder override below is not a
new deployment file:

```bash
COMPOSE=(docker compose
  --env-file /absolute/path/to/deploy/.env
  -f /absolute/path/to/deploy/docker-compose.yml
  -f /absolute/path/to/each-remaining-reviewed-override.yml
)
```

Select the pinned candidate image in that complete configuration before running
the commands. Confirm the app service's mounted roots are the intended runtime
and its backup mount is independent. The examples bypass the normal entrypoint
so an interrupted migration can be resumed. They do not start the web server or
call acquisition providers.

The read-only plan is:

```bash
"${COMPOSE[@]}" run --rm --no-deps --entrypoint python app \
  -m scripts.migrate_information_storage plan \
  --data-dir /app/runtime/data --inbox-dir /app/runtime/inbox
```

Review record/variant/asset coverage, public/private counts and every conflict.
Same-ID incompatible source identities, mismatched IDs/filenames and attachment
collisions with different bytes stop migration. Do not resolve these by dropping
a record or fuzzy-merging sources. Record any deliberate correction and rerun the
read-only plan. A plan against changing runtime files is provisional; generate
and verify the final plan after all writers are stopped.

Keep the web service stopped during migration:

```bash
"${COMPOSE[@]}" stop app
# Stop separately scheduled writers and any other process using these mounts.

"${COMPOSE[@]}" run --rm --no-deps --entrypoint python app \
  -m scripts.migrate_information_storage apply \
  --data-dir /app/runtime/data --inbox-dir /app/runtime/inbox \
  --backup-dir /app/backups/information-migration-backups --quiesced
```

Apply acquires the source-store and collector leases, backs up original bytes
with checksums, stages the complete records/assets/history store and verifies its
coverage. It binds the inbox and installs a maintenance guard before cutover.
After activating the shared store, it retires the backed-up legacy source JSON
and attachment payloads and rewrites retained envelopes to references. It removes
the maintenance guard only after completion. Existing review events and reading
state remain in place. No dual writes or competing live index are created.

Save the migration ID, exact per-run backup path, source fingerprint, counts and
completion result in the private release receipt. The private backup includes
`PLAN.private.json`, `MANIFEST.json` and original `sources/data` / `sources/inbox`
payloads. A successful process exit alone does not prove the application and
public export are correct.

## Verify before reopening writes

With acquisition still stopped, validate records and exercise the candidate
application against the migrated runtime. Confirm both data-only and inbox-only
adapters resolve the same store; review a source in place; inspect source-body
retrieval, attachments, retained News, search and report citations. Compare record
IDs, counts, hashes, review events, reading state and attachment coverage with the
private receipt. Verify a static/public build contains no private IDs, titles,
source bodies or private-derived records. Keep generated public output separate
from runtime and backup directories.

The container entrypoint performs additive canonical seed sync, then validates
both activation bindings before starting the application. In active mode it uses
only `data/information/records`; it does not recreate `inbox/evidence`. A missing
binding, stale absolute path, nonempty incomplete store or maintenance guard
blocks startup. Startup never performs migration or repairs markers. Start the
candidate service only after the checks succeed, then verify health, login and
the authenticated application before reenabling writers.

## Resume or roll back

If interrupted, leave all writers stopped. Do not delete markers, the transition
guard, a staged store or backup files to make startup work. Resume with the same
candidate image, exact runtime paths and backup parent:

```bash
"${COMPOSE[@]}" run --rm --no-deps --entrypoint python app \
  -m scripts.migrate_information_storage apply \
  --data-dir /app/runtime/data --inbox-dir /app/runtime/inbox \
  --backup-dir /app/backups/information-migration-backups \
  --resume information-REPLACE_WITH_RECORDED_ID --quiesced
```

Resume verifies the saved plan and raw backup before continuing. OS-owned leases
are released after a process crash; recovery only accepts this migration's stale
collector lease. A different active owner remains a blocking condition.

To restore legacy storage before reopening writes, use the **exact per-run**
backup directory, not its parent:

```bash
"${COMPOSE[@]}" run --rm --no-deps --entrypoint python app \
  -m scripts.migrate_information_storage rollback \
  --data-dir /app/runtime/data --inbox-dir /app/runtime/inbox \
  --backup-dir /app/backups/information-migration-backups/information-REPLACE_WITH_RECORDED_ID \
  --quiesced
```

Rollback verifies and restores original raw source/cache/attachment files and
clears activation bindings. It retains the staged/active store as a private
rollback archive. It leaves independent review/reading decisions in place and
refuses to discard new, changed or deleted source records/assets after cutover.
If writers have already resumed, preserve their newer work and reconcile it
before rollback; do not force an older snapshot over it. An image rollback alone
is insufficient because an old image expects the legacy storage layout. Restore
the prior image only after verified storage rollback, then repeat health, login,
record coverage and privacy checks.
