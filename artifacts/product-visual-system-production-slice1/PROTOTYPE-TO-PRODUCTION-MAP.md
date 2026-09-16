# Prototype → production map — Slice 1

Visual reference: `prototype/product-visual-system-v1` @ `1c6b299`.

| Prototype artifact | Production action |
|---|---|
| `tokens/tokens.css` / `tokens.json` | **Adapted** into `app/static/pvs_tokens.css` (minimum shared set + `--brief-*` aliases) |
| Style-guide shell / rail demo | **Not copied** — production keeps V2 AppShell; only briefing canvas/type treatment on `/today` |
| Feed / competitor card demos | **Adapted** feed-card hierarchy into `daily_briefing.css` + existing `_briefing_card.html` |
| Filters / chips | **Adapted** jump chips + sticky filter bar / 44px selects |
| Reader drawer demo | **Adapted** into production reader layer styles + JS focus trap |
| Trust controls (thumbs) | **Not connected** — display-only trust badge for existing `review_trust_state` |
| Source Health / queues / tables catalog | **Deferred** |
| Imagery policy demos | **Adapted lightly** — identity fallback monogram; no hotlinks; no generated article photos |
| Component catalog / migration map docs | **Referenced** via this artifact set; not merged wholesale |

## Copied vs adapted

- **Copied:** 0 prototype HTML/JS files into production templates.
- **Adapted:** token values, typography pairing, badge/status language, drawer elevation, touch targets, reduced-motion hooks.
- **Preserved:** data contracts, honesty rules, reader query URLs, Pagefind, static export, trust backend boundaries.
