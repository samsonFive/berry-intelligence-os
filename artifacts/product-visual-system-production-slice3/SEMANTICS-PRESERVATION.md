# SEMANTICS-PRESERVATION — PVS Production Slice 3

## Contract checks

Compared templates at Slice 3 tip against frozen Slice 2 HEAD `0ec6904`:

| Surface | Form action/method tuples | Result |
| --- | --- | --- |
| Source Health | GET/POST `/sources`, POST check-now / mark-checked / toggle / blocked-domain remove | Identical |
| Collection Ops | POST `/collection-ops/run` | Identical |
| Run-now disable | `report.lock and report.lock.active and not report.lock.stale` | Identical |

## Operational semantics unchanged

- Health bucket keys/labels/blurbs still from `HEALTH_BUCKETS` / `group_source_health`
- Coverage / execution / acquisition count strings still rendered from the same context objects
- Collection Ops lock branches (`none` / `active` / `stale` / else) unchanged
- `just_ran` banner branches unchanged
- Degraded-source links still `/sources#source-{id}`
- No Python service/route edits for Slice 3 presentation

## Mutation / live-run policy during verification

- Did **not** POST `/collection-ops/run`
- Did **not** POST source check-now / toggle / add / delete
- Banner states exercised via query params only (`?ran=…`)
- Canonical/runtime data not mutated by verification

## Leakage

- `/collection-ops` remains absent from `scripts/build_static.py` route list (existing test)
- Slice 3 CSS/templates do not surface pending/private review payloads
- Today remains `data-pvs-slice="1"`; Landscape remains `data-pvs-slice="2"`
