# Migration Map — Product Visual System V1

**Do not implement this migration in the prototype branch.** Recommendation only.

## Goal

Replace inconsistent interface languages gradually by adopting shared tokens and component patterns from this prototype — without a rewrite.

## Current tension (honest)

| Language | Traits | Where seen |
|---|---|---|
| V2 AppShell | Inter, cool gray canvas, purple brand | `app/static/v2.css` |
| Stakeholder / Briefing | Warm canvas, editorial serif, navy | `stakeholder.css`, `daily_briefing.css`, prototypes |
| Trust Controls prototype | Warm canvas, Fraunces + Source Sans 3, bronze accent | `prototypes/trust-feedback-controls-v1` |

**Target direction:** Briefing / Landscape / Trust editorial language (this system).

## Staged order

### 1. Daily Briefing and reader
- Adopt tokens for canvas, type, cards, filters, badges, reader drawer.
- Highest visibility; already closest to target.

### 2. Competitor Landscape
- Align competitor cards, filters, handoffs from Briefing.
- Preserve successful interaction patterns; restyle only.

### 3. Company / Entity profiles
- Profile summary + identity slots + status badges.
- Keep dossier depth; unify chrome.

### 4. Source Health and operational pages
- Replace tile-dashboard feel with health rows + restrained status.
- Keep diagnostics power; reduce visual noise.

### 5. Review queues
- Queue panel + table + trust/publication actions.
- Depends on Trust Feedback domain wiring.

### 6. Remaining static / report pages
- Last; lowest interaction frequency.
- Prefer token swap over redesign.

## Per-stage rules

- Ship tokens first (`tokens.css` → production shared layer).
- Map old `--v2-*` / `--sh-*` / `--brief-*` aliases during transition.
- No big-bang template rewrite.
- Accessibility checklist must pass per stage.
- Do not introduce a fourth language while migrating.

## Explicit non-goals

- Rewriting backend services
- Replacing Bootstrap offcanvas behavior in one shot
- Purple-brand revitalization
- Hotlinking imagery to “pretty up” empty states
