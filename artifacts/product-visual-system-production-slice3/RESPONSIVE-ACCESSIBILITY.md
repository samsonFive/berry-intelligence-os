# RESPONSIVE-ACCESSIBILITY — PVS Production Slice 3

## Responsive

| Viewport | Evidence |
| --- | --- |
| Desktop ~1440×900 | `01_desktop_source_health.png`, `03_desktop_collection_ops.png`, banner variants |
| Mobile ~390×844 | `07_mobile_source_health.png`, `08_mobile_collection_ops.png` |

CSS breakpoints in `ops_pvs.css`:

- `max-width: 980px` — sticky nav flush; filter fields full width
- `max-width: 640px` — 2-col metrics; stacked definition lists; full-width action buttons

## Accessibility

- Skip links on both surfaces
- `:focus-visible` uses `--pvs-focus` / `--pvs-focus-offset`
- Filter/form controls retain explicit `<label for=…>`
- Status banners use `role="status"` / `role="alert"` as appropriate
- Disabled Run now keeps native `disabled` + reduced opacity cursor
- Touch targets ≥ `--pvs-touch` (44px) on primary controls
- `prefers-reduced-motion` disables transitions/scroll-behavior under `.pvs-slice-3`
- Contrast: navy/bronze on warm canvas with OK/warn/danger token pairs from Slice 1

## Iconography

No remote `<img>` dependencies added. Status communicated via CSS badges, borders, and existing text labels.
