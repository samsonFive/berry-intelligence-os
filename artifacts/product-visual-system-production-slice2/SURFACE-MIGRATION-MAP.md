# SURFACE-MIGRATION-MAP — PVS Slice 2

| Surface | Before | After (Slice 2) |
| --- | --- | --- |
| Landscape shell | V2 warm styles in `v2.css` | + `pvs_tokens.css` + scoped `competitor_pvs.css`; `data-pvs-slice="2"` |
| Landscape filters/chips | Existing form | Same GET params; 44px targets; PVS chips |
| Company cards | Plain cards | Lettermarks (no hotlinked imagery); status badges with aria-labels |
| Tier bands | Sections only | Sticky local band navigation |
| Empty / no-results | `.competitor-empty` | PVS system-state styling |
| Detail drawer | Bootstrap offcanvas | Lettermark hero; maturity gap/complete colors via PVS |
| Company profile | Stakeholder chrome | PVS fonts/tokens; lettermark; profile concerns panel |
| Brand / breeding profiles | Generic entity heading + `_entity_body` | Same + PVS slice wrapper + concerns panel |
| Imagery | None / inconsistent | Controlled lettermark fallbacks only |

## Deferred (not Slice 2)

- Source Health / collection ops
- Review queues
- Trust-feedback mutations
- Today/reader (already Slice 1)
- Publication-review routes
- Full static redesign of non-competitor entity types
