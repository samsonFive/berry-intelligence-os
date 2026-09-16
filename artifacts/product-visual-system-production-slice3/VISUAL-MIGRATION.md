# VISUAL-MIGRATION — PVS Production Slice 3

## System applied

- Tokens: `app/static/pvs_tokens.css` (unchanged)
- Slice CSS: `app/static/ops_pvs.css` (new), scoped under `.pvs-slice-3`
- Templates: `sources.html`, `collection_ops.html`
- Fonts: Fraunces + Source Sans 3 (same Google Fonts pattern as Slice 1/2)
- Marker: `data-pvs-slice="3"`

## Presentation changes

| Concern | Treatment |
| --- | --- |
| Hierarchy | Display title, muted eyebrow, status strips |
| Health bands | Colored sticky jump nav + left-border section bands |
| Healthy / warn / blocked | `pvs-badge-ok` / `pvs-badge-warn` / `pvs-badge-danger` |
| Tables / cards | Compact health rows + ops metric grid |
| Local nav | Sticky `ops-band-nav` on both surfaces |
| Empty / banners | Dashed empty panels; success/warn/error system states |
| Responsive | 980 / 640 breakpoints; 44px touch targets |
| A11y | Skip links, `:focus-visible`, labeled filters, disabled opacity |

## Not changed

- Route handlers in `app/main.py`
- `group_source_health` / freshness classification
- Collection runner / lock semantics
- Form destinations, methods, field names, enablement conditions
- Remote imagery (none added; lettermarks/icons unused where not needed)

## Presentation adapters

None. Existing view models already expose health keys, lock state, `just_ran` banners, counts, and degraded source rows.
