# SEMANTICS-PRESERVATION — PVS Production Slice 5

Form action/method tuples in `queue.html` identical to base `69465fa`.

Preserved:
- Bucket keys/labels/blurbs
- Bulk-read POST `/queues/reading/bulk-read` and hidden `item_id` selection for top_priority
- Per-item reading actions mark_read / keep / dismiss / promote
- Filter GET params `region`, `show_completed`
- `_intelligence_card.html` form destinations unchanged

No route/service edits. No live collection runs during verification.
