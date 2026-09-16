# Accessibility Checklist — Product Visual System V1

Prototype verification. Re-run when tokens land in production.

## Keyboard & focus
- [x] Skip link to main
- [x] Visible `:focus-visible` accent outline on buttons, chips, links, icon buttons
- [x] Drawer moves focus in and restores on close
- [x] Escape closes drawer
- [x] Undo toast focuses Undo control
- [x] No keyboard trap in drawer
- [x] Viewport / filter chips are button toggles with `aria-pressed`

## Structure & names
- [x] One `h1` in the style guide; sections use `h2`/`h3`
- [x] Nav uses `aria-current="page"`
- [x] Drawer `role="dialog"` + `aria-modal` + labelled title
- [x] Trust / filter groups labelled
- [x] Tables have caption + `scope`

## Status & color
- [x] Badges include text labels (not color alone)
- [x] Dot + text on status badges
- [x] Alerts and toasts use `aria-live`
- [x] Empty/blocked/error states explain in text

## Touch & responsive
- [x] Min ~44px targets on interactive controls
- [x] Mobile: single column cards; full-bleed drawer
- [x] No hover-only information
- [x] No horizontal scroll trap in main content (tables wrapped)

## Motion
- [x] Short transitions on drawer/backdrop only
- [ ] Production follow-up: respect `prefers-reduced-motion`

## Residual production follow-ups
- [ ] VoiceOver/NVDA pass on `/today` after token adoption
- [ ] Ensure reader and trust controls share focus management utilities
- [ ] Confirm contrast of muted text on canvas (≥ 4.5:1 for body)
