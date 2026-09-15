# Accessibility Checklist — Trust Feedback Controls V1

Prototype verification checklist. Re-run against production wiring when Sol’s service lands.

## Keyboard

- [x] Up / Down / History activatable by keyboard (native `<button>`)
- [x] j / k move card focus; Enter opens reader
- [x] u / d / z shortcuts; disabled in text fields
- [x] Esc closes reason panel, then reader
- [x] Reason chips are focusable buttons in a radiogroup
- [x] Undo toast receives focus; focus restores to prior control after undo/timeout
- [x] No keyboard trap in reader (Esc + close control)
- [x] No horizontal scroll trap on narrow viewports

## Focus visibility

- [x] `:focus-visible` outline on links, buttons, chips, cards
- [x] Focused feed card uses inset accent (not color alone)
- [x] Toast Undo has high-contrast focus ring

## Screen reader / names

- [x] Trust controls grouped with `role="group"` + `aria-label` including headline context
- [x] Up / Down use `aria-pressed` for resulting state
- [x] Reason chips use `role="radio"` + `aria-checked`
- [x] Reader is `role="dialog"` with labelled title
- [x] Skip link to main feed
- [x] Status region `aria-live="polite"` for confirmations / blockers
- [x] Toast region also live for undo prompts

## Status & errors

- [x] Blocked promotion announced + visible text explanation (not color alone)
- [x] Pending approval uses badge text + message
- [x] Excluded cards keep text label “Excluded from trusted feed · retained for audit”
- [x] Version / service errors announced

## Touch / mobile

- [x] Controls meet ~44px min touch targets (`--touch`)
- [x] Reason chips wrap; no hover-only information
- [x] Drawer goes full-width on small screens
- [x] Filters and trust actions remain usable without hover

## Color independence

- [x] States use text labels + badges (shape/wording), not color alone
- [x] Icons accompanied by text (“Up”, “Down”)

## Residual / production follow-ups

- [ ] Wire real `aria-describedby` to server-provided blocker IDs
- [ ] Confirm SR verbosity with VoiceOver / NVDA on production templates
- [ ] Prefer reduced-motion if drawer transitions become longer
