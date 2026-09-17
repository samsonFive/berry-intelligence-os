# Accessibility checklist — Slice 1 (/today + reader)

## Verified in this slice
- [x] Skip link to What Changed
- [x] Visible `:focus-visible` on briefing controls (accent outline)
- [x] Reader `role="dialog"` + `aria-modal="true"` + labelled title
- [x] Close control has accessible name
- [x] Escape closes reader and restores focus
- [x] Tab cycles within reader while open (focus containment)
- [x] Live region announces open/close
- [x] Status badges use text + color (not color alone)
- [x] Trust state shown as labelled badge (display only)
- [x] Interactive targets use `min-height: 44px` on briefing actions / jump chips / selects
- [x] Mobile: single-column cards; full-width reader
- [x] `prefers-reduced-motion` disables skeleton animation and short transitions

## Residual / next slices
- [ ] Full VoiceOver/NVDA pass on production corpus
- [ ] Global AppShell token migration (out of scope)
- [ ] Trust thumbs mutation wiring (explicitly deferred)
