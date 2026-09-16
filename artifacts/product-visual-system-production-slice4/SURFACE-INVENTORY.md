# SURFACE-INVENTORY — PVS Production Slice 4

Inventory against Slice 3 tip `dd72be7` before presentation edits.

## Routes in scope

| Method | Path | Purpose | Mutates? |
| --- | --- | --- | --- |
| GET | `/queues/monitoring` | Monitor Alerts + Watches inventory | No |
| POST | `/queues/monitoring/{id}` | Pause / snooze / stop / resume watch workflow | Yes (analyst queue state) |
| POST | `/signals/{id}/alert-decision` | Confirm / Dismiss proposed signal alert | Yes (signal alert workflow) |
| GET | `/watches` | Personal watchlist (+ type/new/sort filters) | No |
| POST | `/watches/toggle` | Add / remove watch | Yes |
| GET | `/watches/open` | Open watch + optional mark-seen | Yes (seen stamp only via open) |

## Templates

- `queue.html` (monitoring branch only; other dimensions unchanged)
- `_monitor_workspace.html`
- `_watch_card.html`
- `watchlist.html`

## Alert groups (`present_monitor_alerts`)

| Key | Meaning |
| --- | --- |
| `signals` | Proposed trusted Signal records |
| `candidates` | Signal candidates on watches |
| `watch_activity` | New activity on inventory watches |
| `sources` | Failing/blocked collection sources |

## Watch states

- Monitoring inventory cards: `active` / `snoozed` / other → Pause/Resume/Remove forms
- Watchlist empty: no watches vs filter miss
- Watchlist badges: NEW INTELLIGENCE, NEW ASSESSMENT, MONITORING DEGRADED, never_seen / quiet

## Out of scope

Watchtower (`/watchtower`), Today/reader, Source Health/Collection Ops, publication review, reading/testing/commercial queues (CSS gated off).
