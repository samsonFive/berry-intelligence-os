# SURFACE-INVENTORY — PVS Production Slice 5

Inventory against Slice 4 tip `69465fa`.

## Routes

| Method | Path | Purpose | Mutates? |
| --- | --- | --- | --- |
| GET | `/queues/reading` | Reading Queue buckets / completed table | No |
| POST | `/queues/reading/bulk-read` | Bulk mark visible unread/saved as read | Yes (reading state) |
| POST | `/queues/reading/{id}` | mark_read / keep / dismiss / promote | Yes (reading state) |

Filters: `region`, `show_completed`.

## Templates

- `queue.html` reading branch only (other dimensions unchanged except shared head gating)
- Shared `_intelligence_card.html` (styled via scoped CSS only; forms untouched)

## Buckets

`top_priority`, `saved`, `adjacent`, `backlog` (+ rare `needs_review`)

Empty: per-bucket “Nothing in this reading bucket.” / global “Nothing needs attention…”

## Out of scope

Today/reader, Monitor Alerts/Watches, Source Health, Collection Ops, publication review, testing/commercial queues.
