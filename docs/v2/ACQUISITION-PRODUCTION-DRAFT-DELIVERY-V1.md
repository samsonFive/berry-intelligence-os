# Acquisition → Production Draft Delivery V1

Proven contract. **Operational collection is supposed to run on production.**
systemd `bios-collection.timer` → `scripts/collection_cron.sh` → Docker
`python scripts/run_due_pipelines.py` with `BIOS_RUNTIME_DIR=/app/runtime`.
That writes the authoritative analyst inbox: VPS `demo-runtime/inbox`
(`inbox/evidence/*.json`), which FastAPI `list_drafts()` / `/review/{id}`
reads.

The acquisition clone is a **local operator sandbox**. Its gitignored
`inbox/` is not production review. Local collection results are **not**
expected to appear on `/review` unless production collection processed the
same item, or an operator explicitly delivers them.

`scripts/deliver_drafts.py` is **not** a second scheduled collector. It is
an identity-gated, dry-run-default, additive promotion tool for exceptional
off-runtime drafts. It must not auto-run. It must not replace
`demo-runtime/inbox`.

Code deploy, `sync_trusted_data.py`, and Git never copy untrusted drafts.

## Why a draft can exist locally and 404 in production

Collection writes drafts into whichever inbox that process resolved
(`BIOS_RUNTIME_DIR/inbox` or repo `inbox/`). A successful local
`process_discovered_media` run is expected to create
`inbox/evidence/<id>.json` on that machine only. Production collection
(`bios-collection.timer` → `scripts/run_due_pipelines.py` inside Compose)
writes the VPS inbox. If production never processed that discovered item,
`GET /review/<id>` is 404 even though a local clone has the file.

A 404 on `/review/{id}` can also mean the record is already **trusted**
under `data/evidence/` (published). Delivery must `SKIP_ALREADY_TRUSTED`
and must not recreate a pending draft. Restoring a missing `article` body
onto a trusted record is a separate publish/fidelity mission, not draft
delivery.

## Operator delivery

```bash
python scripts/deliver_drafts.py \
  --source-inbox /path/to/source/inbox \
  --destination-inbox /opt/berry-intelligence-os/demo-runtime/inbox \
  --destination-data /opt/berry-intelligence-os/demo-runtime/data \
  --source-identity acquisition-local \
  --destination-identity production-vps \
  --expected-destination-identity production-vps
```

Default is dry-run (zero writes). Apply:

```bash
BIOS_DRAFT_DELIVERY_ALLOWED_DESTINATIONS=production-vps \
python scripts/deliver_drafts.py \
  --source-inbox /path/to/source/inbox \
  --destination-inbox /opt/berry-intelligence-os/demo-runtime/inbox \
  --destination-data /opt/berry-intelligence-os/demo-runtime/data \
  --source-identity acquisition-local \
  --destination-identity production-vps \
  --expected-destination-identity production-vps \
  --ids ev-media-c8cdb7133db1cae0bf66 \
  --apply
```

Backup production runtime before apply (`scripts/runtime_backup.py create`).

## Outcomes

| Outcome | Meaning |
|---|---|
| `NEW_DRAFT` | Destination missing this id; apply copies the JSON and missing referenced transcript files |
| `ALREADY_PRESENT_IDENTICAL` | Destination file exists; bytes or payload hash match |
| `CONFLICT_DIFFERENT_CONTENT` | Destination file exists with different content; production wins; no write |
| `SKIP_ALREADY_TRUSTED` | Same id or `source_url` exists under destination `data/evidence` |
| `SKIP_TEST_ARTIFACT` | Test/fixture id or submitter |
| `SKIP_NOT_OPERATIONAL` | Source record is already published |

Identity mismatch or a production destination without
`BIOS_DRAFT_DELIVERY_ALLOWED_DESTINATIONS` fails closed.

Audit files: `inbox/operations/draft-deliveries/` (ids, hashes, outcomes).
No article body, summary, transcript text, or secrets.

Static output never reads this path. Delivery does not change trust, publish,
reject, or `/pending` ranking.
