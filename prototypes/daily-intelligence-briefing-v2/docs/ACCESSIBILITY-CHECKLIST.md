# Daily Intelligence Briefing V2 — Accessibility checklist

## Keyboard

- [x] Skip link to main briefing
- [x] Section jump links operable by keyboard
- [x] Card open controls are buttons (not click-only divs)
- [x] Reader closes with Escape
- [x] Focus moves into reader on open and returns to trigger on close
- [x] Visible focus styles on links/buttons

## Structure / semantics

- [x] One `h1`, section `h2`, card `h3`
- [x] Reader is `role="dialog"` + `aria-modal="true"`
- [x] Live region announces open/close
- [x] Status badges include text labels (color is not the only cue)
- [x] Observed fact vs analyst interpretation are separate labeled blocks

## Content honesty / comprehension

- [x] Publication date and capture date shown separately
- [x] Unknown-date appendix clearly labeled
- [x] Unreadable states explain operator next step without fake summaries

## Mobile / overflow

- [x] Sticky nav wraps rather than forcing horizontal page scroll
- [x] Drawer becomes full-width on small screens
- [x] Stats/pulse collapse to single column

## Contrast / density

- [x] Text and badges use dark text on light surfaces
- [x] Compact density hides detail but keeps headlines/actions available

## Manual verification targets

- Desktop briefing scan
- Mobile briefing scan
- Reader keyboard open/close
- Landscape handoff link
- Bot-wall and unknown-date states
