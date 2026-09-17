# Boundary tests

Windows under test are the existing ones: **14-day** recency band (inclusive) and **45-day** pending triage (inclusive).

| Case | Instant / date | Expected |
|---|---|---|
| 14-day inside | published 2026-08-31, now 2026-09-13 (13 days) | `last_14_days` |
| 14-day exact cutoff | published 2026-08-31, now 2026-09-14 (14 days) | `last_14_days` |
| 14-day outside | published 2026-08-31, now 2026-09-15 (15 days) | no band |
| UTC rollover still 14th | now 2026-09-14 16:00-07:00 → 23:00 UTC | in window |
| UTC rollover 15th | now 2026-09-14 17:00-07:00 → 00:00 UTC 15th | out of window |
| 45-day exact cutoff | Hortifrut 2026-07-30, now 2026-09-13 | Review now |
| 45-day outside | same drafts, now 2026-09-14 (46 days) | older backlog |
| `now=None` | freeze `utc_now` to 2026-09-01 | same Top Stories as `now=that instant` |
| Naive input | `datetime(2026, 9, 1, 12, 0)` | treated as UTC |
| Aware input | 2026-09-01 05:00-07:00 | 12:00 UTC |
| Repeat | two `resolve_now(None)` / two `build_front_page(now=None)` under freeze | identical ids |

Helper: `tests/clock_helpers.py::freeze_utc_now`.
