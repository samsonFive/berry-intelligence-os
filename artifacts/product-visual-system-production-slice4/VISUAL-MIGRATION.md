# VISUAL-MIGRATION — PVS Production Slice 4

## System applied

- Tokens: `app/static/pvs_tokens.css`
- Slice CSS: `app/static/monitor_pvs.css` under `.pvs-slice-4`
- Marker: `data-pvs-slice="4"` on `/queues/monitoring` and `/watches`
- Fonts: Fraunces + Source Sans 3 (same as prior slices)

## Presentation changes

| Concern | Treatment |
| --- | --- |
| Hierarchy | Display titles, muted copy, inventory vs action metrics |
| Alert bands | Left-border groups by kind; sticky jump nav including per-group counts |
| Watch cards | Compact surface cards; workflow badge; 44px actions |
| Watchlist | Filter chips + card grid; degraded/new badges |
| Empty states | Dashed `pvs-system-state` panels |
| Isolation | `queue.html` loads PVS head_extra **only** when `dimension == 'monitoring'` |

## Presentation adapters

None. Existing monitor/watchlist view models already expose groups, counts, workflow states, and filter flags.
