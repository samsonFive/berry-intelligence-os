# ACCESSIBILITY-CHECKLIST — Publication Review read-only UI v1

## Structure

- [x] Skip link to `#pr-workspace`
- [x] Page `h1`, panel `h2`, block `h3` hierarchy
- [x] Queue `role="listbox"` / items `role="option"` with `aria-selected`
- [x] Filter chips expose `aria-current`
- [x] Decision group `role="group"` with disabled controls + `aria-disabled`
- [x] Status banners / limited copy use `role="status"` or `role="alert"`
- [x] Live region `#pr-live` for selection announcements
- [x] Private panels marked `data-pagefind-ignore`

## Keyboard

- [x] Tab reaches filters, queue items, and disabled decision controls
- [x] Visible `:focus-visible` ring (PVS bronze)
- [x] `j` / `k` move selection via detail URL navigation
- [x] No decision dialogs in Slice 1 (no focus trap required for mutations)

## Targets & motion

- [x] Filter chips and decision buttons use min 44px (`--pvs-touch`)
- [x] Desktop two-column; tablet/mobile stacked (`max-width: 980` / `640`)
- [x] `prefers-reduced-motion` disables transitions

## Semantics: warn vs block

- [x] Warnings labeled “(warning — not an automatic blocker)”
- [x] Blockers labeled “(contractual blocker)” with danger styling
- [x] Duplicate card states warn-only explicitly

## Slice limits

- Decision buttons remain present but disabled; click handler only announces disconnection (no POST).
