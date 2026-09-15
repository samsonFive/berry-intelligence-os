# State / Interaction Matrix — Trust Feedback Controls V1

## Thumbs up

| Prior | Condition | User action | Resulting state | UI feedback | Undo |
|---|---|---|---|---|---|
| unreviewed | eligible, no approval | Up | `promoted` | “Promoted into working set… publication review still required” | Yes |
| unreviewed | eligible, approval required | Up | `relevant_pending_approval` | Pending badge + explanation | Yes |
| unreviewed | incomplete provenance | Up | unchanged | Blocking explanation | No (no state change) |
| unreviewed | unreadable / bot-wall / cookie | Up | unchanged | Blocking explanation; not promotable | No |
| promoted | already promoted | Up | `promoted` | Idempotent confirmation | Yes (if last event allows) |
| excluded | (optional future) | Up | out of scope for v1 prototype | — | — |

**Never implied:** thumbs up auto-publishes intelligence or creates Evidence.

## Thumbs down

| Prior | User path | Resulting state | Provenance | Audit |
|---|---|---|---|---|
| unreviewed / promoted / pending | Down → reason chip → confirm | `excluded` | Retained | Event appended |
| any | Down → defer reason | `excluded` + reason deferred | Retained | Event appended |
| excluded | Same reason again | `excluded` idempotent | Retained | Idempotent event |
| excluded | Undo | prior restored | Retained | Compensating event |

Demonstrated reason chips: duplicate, wrong entity, outdated, weak source, unreadable, irrelevant, other.

## Reader integration

| Concern | Behavior |
|---|---|
| Reader close | Only via ×, Esc, or backdrop — not via trust actions |
| Feed position | Focused card preserved |
| Filters | Unchanged when acting from reader |
| Navigation | No route change; no external nav for trust |
| Original source | Visually/semantically separate from trust controls |

## Content honesty

| Honesty | Up success? | Notes |
|---|---|---|
| readable | Maybe | Still subject to provenance / approval |
| unreadable | No | Bot-wall, cookie, empty, nav-shell |
| historical_context | Not as current intel | Can be excluded as outdated |
| unknown_date | Pending / limited | Limitation retained |

## Bulk review (minimal)

Select N cards → “Exclude selected…” with confirm.  
Never bulk-promotes. Scope/count shown.

## Keyboard

| Key | Action |
|---|---|
| j / k | Move card focus |
| Enter | Open reader |
| u | Thumbs up (focused or reader) |
| d | Thumbs down / open reasons |
| z | Undo pending toast action |
| Esc | Close reason panel, then reader |

Shortcuts disabled while typing in inputs.
