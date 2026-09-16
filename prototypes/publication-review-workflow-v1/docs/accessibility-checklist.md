# Accessibility Checklist — Publication Review Workflow V1

Verified against the fixture-driven prototype UI (keyboard + Playwright inspection).

## Structure & semantics

- [x] Landmark structure: skip link, `aside` rail, `main`, labeled sections
- [x] Heading hierarchy: page `h1`, panel `h2`, block `h3`
- [x] Dialog uses `role="dialog"`, `aria-modal="true"`, `aria-labelledby`
- [x] Queue uses `role="listbox"`; items expose `aria-current` when selected
- [x] Filter chips use `aria-pressed`
- [x] Decision buttons grouped with `role="group"` + accessible name
- [x] Status messages use `role="status"` / `aria-live="polite"` (receipt, toast, limited copy, `#live`)

## Keyboard

- [x] Skip link reaches `#main`
- [x] All interactive controls reachable by Tab
- [x] Visible focus ring (`:focus-visible` using PVS bronze outline)
- [x] Dialog focus moves to close control on open
- [x] Dialog Tab cycle is contained (first ↔ last)
- [x] Esc closes dialog and restores prior focus
- [x] Backdrop / Cancel also restore focus
- [x] Operator shortcuts j/k/a/r/x/c do not fire inside inputs/textarea/select

## Targets & layout

- [x] Primary controls meet 44×44px (`--pvs-touch`)
- [x] Desktop layout: rail + queue + workspace
- [x] Tablet (≤980px): stacked rail; single-column layout; shorter queue
- [x] Mobile (≤640px): tightened padding; definition list stacks

## Contrast & motion

- [x] Navy / bronze / warm-canvas PVS tokens (same as Today/reader Slice 1)
- [x] Status badges use semantic foreground + background pairs
- [x] `prefers-reduced-motion` collapses motion tokens / transitions

## Announcements

- [x] Filter change announced
- [x] Draft selection announced
- [x] Dialog open/close announced
- [x] Decision recorded / concurrent no-op / idempotent duplicate announced
- [x] Pending count updates with `aria-live`

## Known prototype limits

- Docs links in the rail open markdown files via static server (browser-native); not a production docs viewer.
- Color is not the sole signal (badges include text labels).
