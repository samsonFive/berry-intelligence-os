# Component / State Catalog — Publication Review Workflow V1

## Shell

| Component | Role | Notes |
| --- | --- | --- |
| Skip link | Accessibility | First focus target → `#main` |
| Rail brand | Orientation | Berry Intelligence OS + prototype label |
| Prototype note | Safety | States no mutations / no Evidence |
| Keyboard help | Operator UX | j/k, a, r, x, c, Esc |
| Pending count | Queue summary | Live region updates on decisions |
| Reset demo | Fixture hygiene | Reloads structuredClone of fixtures |

## Queue

| Component | States | Notes |
| --- | --- | --- |
| Filter chips | all / readable / transcript / limited / problem | `aria-pressed` |
| Queue item | selected, attention, handled | Sorted by pending then `needs_attention_rank` |
| Quality badge | readable / transcript / limited / problem | PVS ok/info/warn/danger |
| Warning badges | Probable duplicate, Missing entity, Uncertain date, Blocking | Warn ≠ block unless contractual |
| Source + capture dates | Always shown | `Cap YYYY-MM-DD` |
| Publication-date confidence | high / medium / low / none | Badge when low/none |

## Review workspace

| Block | Content |
| --- | --- |
| Source metadata | Source, URL, type, published + confidence, discovered, captured, acquisition |
| Body | Readable body or transcript; limited explanation when empty |
| Entities & duplicates | Proposed entities; probable-duplicate card (warn only) |
| Warnings | Provenance warnings (`warn`) vs blocking warnings (`block`) |
| Provenance chain | Ordered steps with timestamps |
| Review history | Prior actor/action/note (+ resulting publication id if any) |
| Decision group | Approve publication / Reject / Defer / Request correction |

## Dialogs

| Mode | Required fields | Confirm label |
| --- | --- | --- |
| Approve publication | Explicit confirm | Confirm approve publication |
| Reject | Reason (+ optional notes) | Confirm |
| Defer | Optional notes | Confirm defer |
| Request correction | Reason (+ optional notes) | Confirm |

Dialog focus: close button on open; Tab cycle contained; Esc / backdrop / Cancel restores prior focus.

## Receipts & toasts

| Surface | When |
| --- | --- |
| Success receipt | After recorded decision — actor, time, draft id, resulting publication id (prototype label) |
| Toast | Concurrent/stale, idempotent duplicate click, blocked approval, recorded decision |
| Live region (`#live`) | Filter changes, selection, dialog open/close, decisions |

## Fixture → UI mapping

| Fixture state | Primary UI signal |
| --- | --- |
| `readable_body` | Readable body badge + full extract |
| `transcript` | Transcript section |
| `metadata_only` | Limited explanation, no body |
| `navigation_only_shell` | Limited / shell warning |
| `probable_duplicate` | Dup card + warn badge (not blocker) |
| `uncertain_date` | Low/none confidence badge |
| `missing_entity_match` | Missing entity badge |
| `upgraded_acquisition` | Acquisition outcome upgraded |
| `already_handled_by_another_reviewer` | Handled state; concurrent no-op |
| `validation_failure` | Blocking badge; approve disabled |
