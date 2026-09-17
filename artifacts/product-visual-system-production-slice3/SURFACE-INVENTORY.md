# SURFACE-INVENTORY — PVS Production Slice 3

Inventory taken against frozen Slice 2 HEAD `0ec6904` before presentation edits.

## Routes

| Method | Path | Purpose | Mutates? |
| --- | --- | --- | --- |
| GET | `/sources` | Source Health registry + filters + buckets | No |
| POST | `/sources` | Add source (authoring mode) | Yes (config) |
| POST | `/sources/{id}/toggle` | Pause / Resume | Yes |
| POST | `/sources/{id}/check-now` | Manual fetch | Yes (fetch) |
| POST | `/sources/{id}/mark-checked` | Manual check stamp for reference | Yes |
| POST | `/sources/{id}/delete` | Delete (exists; not in template UI) | Yes |
| POST | `/sources/blocked-domains/{domain}/remove` | Unblock domain | Yes |
| GET | `/collection-ops` | Collection Operations status | No |
| POST | `/collection-ops/run` | Bounded manual collection trigger | Yes (run) |

Query banners on Collection Ops: `?ran=completed|refused|error` (+ optional `reason`).

## Templates

- `app/templates/sources.html`
- `app/templates/collection_ops.html`
- Shared: `base.html`, `_workspace_help.html`, `_v2_sidebar.html` (nav only; not redesigned)

## Source Health states (HEALTH_BUCKETS)

| Key | Label | Meaning |
| --- | --- | --- |
| `failing` | Failing | Last collection attempt failed |
| `blocked` | Blocked | Access-control / bot-wall |
| `stale` | Stale | No recent successful collection |
| `due` | Due for a check | Cadence elapsed |
| `quiet` | Healthy but quiet | Checked OK; no new items |
| `current` | Healthy | Checked OK with activity |
| `manual` | Not configured for discovery | No discovery adapter |

Empty per-bucket: “No sources in this state.”
Global empty: “No sources yet…”
Authoring disabled: edits disabled banner.
Polling off: warning banner.
Static build: read-only registry note.
Error: `banner-error` when `error` set.

## Collection Operations states

| Surface | States |
| --- | --- |
| `just_ran` banners | `completed` / `refused` / `error` |
| Lock | `none` / `active` / `stale` / unreadable |
| Last run | present counts grid vs empty |
| History | table vs empty |
| Extraction | ENABLED / DISABLED badge |
| Degraded sources | list vs “No Source is currently failing or blocked.” |
| Run now | form POST `/collection-ops/run`; button disabled when lock active & not stale |

## Forms / actions preserved

Identical action URLs and methods to pre-migration templates (verified against `0ec6904`).

## Out of scope (untouched)

Today / reader, publication review, competitor landscape/profiles, story threads, command-service code, health calculation, scheduling, mutation endpoint handlers.
