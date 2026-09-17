# Test results

## Before edit (exact base `c0de14c`)

The four named tests: **4 failed**.

## After repair (focused)

| Suite | Result |
|---|---|
| Four previously failing tests + new clock/45-day bounds | 15 passed |
| Today + front page + Perplexity + clock | 66 passed |
| Story Threads + morning brief + pending triage | 35 passed |
| `python scripts/validate_records.py` | All validated records passed |

Static build skipped: `build_static.py` does not call `build_front_page` / `build_today`. Live `/today` rendering uses `resolve_now(None)` → `utc_now()` which defaults to `datetime.now(UTC)`, the previous production default.

## Full suite

**2636 passed, 0 failed** in 947s.

On exact base this is the prior 2621 passing tests + the previous 4 calendar failures now passing + 11 new clock/boundary tests (9 in `test_clock.py`, 2 Hortifrut 45/46-day triage cases). Remaining inherited failures from this calendar cluster: **none**.

Canonical `data/` was not rewritten. Frozen Story Threads branch was not modified.
