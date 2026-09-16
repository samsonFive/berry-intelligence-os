# RESPONSIVE-ACCESSIBILITY — PVS Production Slice 4

## Responsive

| Viewport | Evidence |
| --- | --- |
| Desktop 1440×900 | `01`–`05` screenshots |
| Mobile 390×844 | `06_mobile_monitoring.png`, `07_mobile_watchlist.png` |

Breakpoints in `monitor_pvs.css`: 980px (sticky flush), 640px (stacked actions / single-column cards).

## Accessibility

- Skip links on both surfaces
- `:focus-visible` via PVS tokens
- Filter labels retained; watchlist filter chips keep active state
- Touch targets ≥ 44px on primary buttons/chips
- `role="status"` on empty states
- `prefers-reduced-motion` disables transitions under `.pvs-slice-4`

## Imagery

No remote image dependencies added.
