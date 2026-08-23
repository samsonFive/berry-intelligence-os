# Canonical Data Promotion / Runtime Sync V1

Git canonical data and mutable production data have overlapping, but not
identical, ownership. A deploy must neither freeze canonical repairs forever
nor treat Git as permission to erase live operator work. This contract uses an
explicit three-way comparison for existing trusted JSON records.

## Ownership

| Class | Examples | Deployment policy |
|---|---|---|
| Additive configuration | `configuration/sources.json` | Add canonical source IDs missing at runtime; preserve every existing runtime ID. |
| Authoritative operational configuration | `configuration/collection_pipelines.json` | Replace from canonical at startup. This is pipeline policy, not a trusted intelligence record. |
| Promotable trusted records | JSON under `assessments`, `entities`, `evidence`, `facts`, `recommendations`, `relationships`, `signals`, and `strategic-questions` | Add when new. Update an existing record only through explicit, backup-gated promotion when the three-way comparison proves it safe. |
| Other seed/reference files | imports, Markdown, Python helpers, CSV, other configuration | Add when missing; never overwrite an existing runtime file. |
| Runtime-published records | trusted records present only in runtime | Runtime-owned. Reported as runtime-only and never overwritten or copied back automatically. |
| Runtime operational state | collection runs, scheduler state, locks, review events, analyst queue state | Runtime-owned and outside canonical promotion. |
| Untrusted artifacts | all of `inbox/` | Never read as canonical input or overwritten by this sync. Promotion audit reports are the sole writes under `inbox/operations/promotions/`. |

## Baseline and states

`data/.canonical-promotion-manifest.json` records the last accepted canonical
raw and semantic SHA-256, the exact runtime raw SHA-256 at promotion, the
canonical commit, and timestamp for each promotable path. Startup establishes
or advances a baseline only when canonical and runtime are semantically equal.
It never updates a differing existing trusted record.

For structured JSON, semantic SHA-256 is computed from strict parsed JSON
(duplicate keys rejected), sorted object keys, compact separators, UTF-8, and
no non-finite numbers. Object key order, indentation, and CRLF/LF therefore do
not create false divergence. Values, types, array order, and every other
meaningful JSON distinction remain significant. Raw hashes are retained for
backup identity and audit.

The deterministic states are:

- `NEW`: canonical exists and runtime does not.
- `UNCHANGED`: canonical and runtime semantic hashes match.
- `SAFE_CANONICAL_UPDATE`: runtime still matches the last-promoted semantic
  hash and canonical has changed.
- `RUNTIME_DIVERGED`: runtime changed while canonical stayed at the baseline,
  or an existing non-promotable seed/reference file differs.
- `CONFLICT`: canonical and runtime both changed from the baseline, or an
  existing differing promotable record has no baseline.

Only `SAFE_CANONICAL_UPDATE` is eligible for explicit mutation. Divergence and
conflict reports include path/record ID plus canonical, last-promoted, and
runtime hashes. Reconciliation remains a deliberate operator action.

## Commands

Dry-run is the default and performs no writes:

```bash
python -m scripts.sync_trusted_data \
  --seed data \
  --runtime demo-runtime/data \
  --canonical-sha "$(git rev-parse HEAD)"
```

Container startup uses `--startup-sync`. It preserves the established
new-file and new-source behavior, refreshes the authoritative pipeline
registry, and records only equal-content baselines. It does not apply safe
updates; an explicit operator step is required.

Existing trusted records may be promoted only after creating and verifying a
backup of the exact current runtime:

```bash
python scripts/runtime_backup.py create \
  --runtime-dir demo-runtime \
  --output-dir /var/backups/berry-intelligence-os
python scripts/runtime_backup.py verify /var/backups/berry-intelligence-os/berry-runtime-TIMESTAMP.tar.gz
python -m scripts.sync_trusted_data \
  --seed data \
  --runtime demo-runtime/data \
  --canonical-sha "$(git rev-parse HEAD)" \
  --apply-safe-updates \
  --verified-backup /var/backups/berry-intelligence-os/berry-runtime-TIMESTAMP.tar.gz
```

The promotion fails closed when the archive is invalid, omits `data/`, omits
any target, or contains target bytes different from the live runtime at apply
time. A verified old backup is therefore insufficient after any intervening
runtime edit.

## Atomicity, recovery, and audit

All eligible files are validated and staged before mutation. Each destination
is atomically replaced, with previous bytes held in a transaction rollback
directory. A caught failure rolls back replaced records and the baseline
manifest. An interrupted process leaves
`.canonical-promotion-transaction.json`, staging/rollback material, and the
verified external backup; another apply refuses to start until an operator
reconciles or restores that transaction. This is bounded file-level
transactionality, not a database transaction.

A successful explicit apply persists a JSON audit report under
`inbox/operations/promotions/`. It contains canonical SHA, timestamp, backup
identity, state counts, paths/IDs, and raw/semantic/baseline hashes, but no
record bodies or secrets.

## Historical backfill proof

The Evidence Berry Tagging Backfill V1 implementation commit (`a48cd73`) was
reconstructed from Git. Its parent supplied the last-promoted runtime and
baseline; the implementation commit supplied the new canonical seed. The new
planner classified 1,266 Evidence records as follows:

- 275 `SAFE_CANONICAL_UPDATE`
- 991 `UNCHANGED`
- 0 `RUNTIME_DIVERGED`
- 0 `CONFLICT`
- 0 `NEW`

Thus the bounded 275-record metadata repair would be deployable with one
verified-backup-gated command and no manual per-file copying.

## Production runbook

Before deployment, record runtime counts and representative hashes, create and
verify the standard `data/` + `inbox/` backup, and retain its archive SHA-256.
Deploy with `BIOS_CANONICAL_SHA` set to the exact canonical commit. After
startup, run the dry-run against `/app/seed/data` and `/app/runtime/data` from
the application container. Review every divergence/conflict before any
explicit apply. Then verify mounted counts/hashes, `/healthz`, authenticated
application access, the fast operator status command, and the actual systemd
timer. Never infer scheduler health from repository configuration alone.

New canonical records remain automatic at startup. Existing trusted canonical
updates are never automatic. No source is added, no pipeline cadence changes,
and trust review semantics remain unchanged by this mechanism.

## Production proof — 2026-08-23 UTC

PR #92 was rebased onto Commercial Positions V2 canonical `2d0baa9`, preserving
its `AGENTS.md`, project status, runtime, static build, and TD-074/TD-075
changes. Post-rebase focused validation passed 22 tests, record validation,
and the 1,527-page static build/leakage check. PR #92 merged as `878dd8e` and
that exact commit was deployed.

Before mutation, the established containerized backup command created and
verified `/var/backups/berry-intelligence-os/berry-runtime-20260823T001440Z.tar.gz`:

- archive SHA-256: `c0c83ed418a5d132a848e035fd8c99312e4bb91d788bc822b03ddacecee9b2ff`
- scope: `data`, `inbox`
- 10,849 manifest files; 51,387,732 manifest bytes
- created `2026-08-23T00:14:40+00:00`

Startup copied zero files, updated zero authoritative config files, added zero
Source IDs, and created
`demo-runtime/data/.canonical-promotion-manifest.json`. The manifest records
canonical `878dd8e9cec0cc30eb6f6fe4173c5547b3269dec`, contains 1,856 equal
promotable baselines, and had SHA-256
`dbae1bd1c9195e5118a0e39e6701a043b47e0f77ca897315bf951823ea74e66f`.

The post-startup production dry-run classified:

- 2,543 `UNCHANGED`
- 0 `NEW`
- 0 `SAFE_CANONICAL_UPDATE`
- 57 `CONFLICT`
- 18 `RUNTIME_DIVERGED`
- 4 runtime-only paths
- no incomplete transaction

The 57 conflicts are legacy promotable trusted records whose canonical and
runtime semantic hashes differ but which predate the baseline manifest. They
were correctly denied an assumed ancestry and were not overwritten. The 18
runtime divergences are all non-promotable historical import/reference files
(Markdown, CSV, or Python) protected by additive-only policy. The runtime-only
paths are the two seed markers plus one Assessment and one Evidence record;
both records remain runtime-owned. This honest bootstrap state is TD-076, not
a reason to weaken the conflict rule.

Pre/post deterministic SHA-256 manifests were identical for every existing
file:

- data excluding the newly created promotion manifest:
  `d42ab67119757435ce6c8a52ca9702992d58db46a0e89e6a10654185cbc29521`
- inbox:
  `858380e8b8d0cc205422379f2f28195b68a7cd4ad968929d974891f6e60a0665`

Data count changed only from 2,624 to 2,625 for the manifest; inbox stayed
8,226. `sources.json` and `collection_pipelines.json` retained their exact
pre-deploy hashes. The review-event ledger remained honestly empty (zero
events; none fabricated). The app was Docker `healthy`; internal and public
`/healthz` both returned 200. `bios-collection.timer` remained enabled and
active while its service was correctly inactive between runs. Fast operator
status completed in 3.39 seconds, reported the backup healthy, no active lock,
and automatic throttling disabled.

Semantic normalization is materially load-bearing in production: 2,191 JSON
pairs had different raw hashes but equal semantic hashes and were classified
`UNCHANGED`, not conflict. This includes line-ending/serialization differences
without normalizing values or array order.

Production-binary proofs used isolated `/tmp` runtimes and did not touch the
mounted data:

- new-record startup: `NEW=1`, `files_added=1`, byte-identical copy, baseline
  created, no Sources added;
- safe update: baseline v1, canonical v2, `SAFE_CANONICAL_UPDATE=1`, a newly
  created verified backup, `updated_count=1`, audit report persisted, no
  transaction left behind;
- invalid backup against the real mounted planner: apply failed before
  transaction creation, and the production manifest hash was identical before
  and after.

Historical reconstruction remains the proof for Claude's berry-tagging
migration: the parent of `a48cd73` supplied runtime/baseline content and
`a48cd73` supplied new canonical content. All 275 changed Evidence records were
`SAFE_CANONICAL_UPDATE`, 991 were unchanged, and zero diverged/conflicted.
With this mechanism present before that deployment, one verified-backup-gated
apply would have promoted all 275 atomically without manual per-file copying.
