# TEST-RESULTS — PVS Production Slice 2

## Focused suites

| Suite | Result |
| --- | --- |
| `test_competitor_landscape_v1.py` + profile + completeness + registry + entity identity | **117 passed** |
| `test_today.py` + `test_landscape_v2.py` + competitor intelligence integration | **38 passed** |
| `test_build_static.py` + `test_ui_v2_shell.py` | **23 passed** |

Combined recorded runs: **178 passed**.

## Manual / smoke

- Default Blueberry Landscape roster **33/33**
- Profile HTTP sweep **33/33**
- Company / brand / breeding pages render Profile concerns
- Today regression page loads; publication-review files not modified
- Publication-review branch HEAD remains `d19ee0a`

## Browser

See screenshots + `walkthrough.mp4`. Console note: environment may log Google Fonts ORB block and pre-existing `/favicon.ico` 404 (same class of noise as Slice 1 Today). No application pageerrors observed for Landscape/profile routes.

## Static / Pagefind

- `/competitors` remains in `build_static.py`
- Entity static loop now optionally attaches `competitor_profile` for company/brand/breeding (read-only presentation)
- No new private review routes; no Pagefind ignore regressions introduced on public entity content beyond existing patterns

## Data mutations

CANONICAL/LIVE DATA MUTATED: 0
