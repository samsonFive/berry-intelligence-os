# TEST-RESULTS — PVS Production Slice 3

## Environment

- Branch: `feature/product-visual-system-production-slice3`
- Base: `0ec6904` (frozen Slice 2 HEAD)
- App under test: `uvicorn app.main:app` on `127.0.0.1:18793`
- No POST to `/collection-ops/run` or source mutation endpoints during verification

## Automated

| Suite | Result |
| --- | --- |
| Focused (`test_collection_ops`, `test_monitor_workspace`, `test_source_*`, `test_collection_status`, `test_app` `-k source/collection…`) | **104 passed**, **1 failed** (inherited) |
| `tests/test_collection_ops.py` + `test_monitor_workspace.py` + `test_build_static.py` | **39 passed** |
| `python scripts/validate_records.py` | **All validated records passed** |

### Inherited failure (also fails on `0ec6904`)

`tests/test_collection_status.py::test_live_source_repository_includes_all_onboarded_sources_generically`

- Assertion: `sources_configured` expected `201`, observed `205`
- Unrelated to Slice 3 presentation; fixture/count drift on base HEAD

## Route / template smoke

- `/sources` and `/collection-ops` render `data-pvs-slice="3"`, load `pvs_tokens.css` + `ops_pvs.css`
- All health section ids present: failing/blocked/stale/due/quiet/current/manual
- Live band counts observed: failing 0, blocked 3, stale 78, due 0, quiet 0, current 0, manual 124
- Form action/method tuples identical to `0ec6904`
- `/today` remains Slice 1; `/competitors` remains Slice 2
- Banner query states: `?ran=completed|refused|error` render success/warn banners
- Active lock fixture shows disabled Run now (TestClient)
- No `pending-decision` controls on `/sources`

## Browser evidence

Screenshots under `artifacts/product-visual-system-production-slice3/`:

- `01_desktop_source_health.png`
- `02_desktop_source_health_blocked.png`
- `03_desktop_collection_ops.png`
- `04_desktop_collection_ops_completed.png`
- `05_desktop_collection_ops_refused.png`
- `06_desktop_collection_ops_error.png`
- `07_mobile_source_health.png`
- `08_mobile_collection_ops.png`
- `walkthrough.mp4` (~8.9s)

Capture script: `scripts/capture_pvs_slice3.py`

Transient console note during capture: one 404 resource; re-check showed no 4xx on `/sources` or `/collection-ops`.

## Static build

Focused `test_build_static.py` included in the 39-passed suite above. Full `scripts/build_static.py` site export not re-run end-to-end (heavy); static route leakage for `/collection-ops` covered by existing collection_ops test.

## Live collection runs performed

**0**
